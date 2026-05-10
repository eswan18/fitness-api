"""Database access functions for synced rides (Google Calendar sync tracking)."""

import logging
from datetime import datetime, timezone

from psycopg import sql

from fitness.models.sync import SyncedRide, SyncStatus
from .connection import get_db_cursor

logger = logging.getLogger(__name__)


def _row_to_synced_ride(row: tuple) -> SyncedRide:
    (
        sync_id,
        ride_id,
        ride_version,
        google_event_id,
        synced_at,
        sync_status,
        error_message,
        created_at,
        updated_at,
    ) = row
    return SyncedRide(
        id=sync_id,
        ride_id=ride_id,
        ride_version=ride_version,
        google_event_id=google_event_id,
        synced_at=synced_at,
        sync_status=sync_status,
        error_message=error_message,
        created_at=created_at,
        updated_at=updated_at,
    )


def get_synced_ride(ride_id: str) -> SyncedRide | None:
    """Get sync record for a specific ride."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, ride_id, ride_version, google_event_id, synced_at,
                   sync_status, error_message, created_at, updated_at
            FROM synced_rides
            WHERE ride_id = %s
            """,
            (ride_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_synced_ride(row)


def create_synced_ride(
    ride_id: str,
    google_event_id: str,
    ride_version: int = 1,
    sync_status: SyncStatus = "synced",
    error_message: str | None = None,
) -> SyncedRide:
    """Create a new sync record for a ride."""
    logger.info(
        f"Creating sync record: ride_id={ride_id}, google_event_id={google_event_id}, "
        f"sync_status={sync_status}, ride_version={ride_version}"
    )
    with get_db_cursor() as cursor:
        now = datetime.now(timezone.utc)
        cursor.execute(
            """
            INSERT INTO synced_rides
            (ride_id, ride_version, google_event_id, synced_at, sync_status, error_message, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at, updated_at
            """,
            (
                ride_id,
                ride_version,
                google_event_id,
                now,
                sync_status,
                error_message,
                now,
                now,
            ),
        )
        result = cursor.fetchone()
        if result is None:
            raise RuntimeError(f"Failed to create sync record for ride_id={ride_id}")
        sync_id, created_at, updated_at = result

        return SyncedRide(
            id=sync_id,
            ride_id=ride_id,
            ride_version=ride_version,
            google_event_id=google_event_id,
            synced_at=now,
            sync_status=sync_status,
            error_message=error_message,
            created_at=created_at,
            updated_at=updated_at,
        )


def update_synced_ride(
    ride_id: str,
    ride_version: int | None = None,
    google_event_id: str | None = None,
    sync_status: SyncStatus | None = None,
    error_message: str | None = None,
    clear_error_message: bool = False,
) -> SyncedRide | None:
    """Update an existing sync record. Returns None if not found."""
    update_fields: list[sql.Composable] = []
    params: list = []

    if ride_version is not None:
        update_fields.append(sql.SQL("ride_version = %s"))
        params.append(ride_version)
    if google_event_id is not None:
        update_fields.append(sql.SQL("google_event_id = %s"))
        params.append(google_event_id)
    if sync_status is not None:
        update_fields.append(sql.SQL("sync_status = %s"))
        params.append(sync_status)
    if error_message is not None:
        update_fields.append(sql.SQL("error_message = %s"))
        params.append(error_message)
    elif clear_error_message:
        update_fields.append(sql.SQL("error_message = NULL"))

    if not update_fields:
        return get_synced_ride(ride_id)

    update_fields.append(sql.SQL("updated_at = %s"))
    params.append(datetime.now(timezone.utc))
    params.append(ride_id)

    query = sql.SQL("""
        UPDATE synced_rides
        SET {update_fields}
        WHERE ride_id = %s
        RETURNING id, ride_id, ride_version, google_event_id, synced_at,
                  sync_status, error_message, created_at, updated_at
    """).format(update_fields=sql.SQL(", ").join(update_fields))

    with get_db_cursor() as cursor:
        cursor.execute(query, params)
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_synced_ride(row)


def delete_synced_ride(ride_id: str) -> bool:
    """Delete a sync record for a ride. Returns True if a row was deleted."""
    with get_db_cursor() as cursor:
        cursor.execute("DELETE FROM synced_rides WHERE ride_id = %s", (ride_id,))
        return cursor.rowcount > 0


def get_all_synced_rides() -> list[SyncedRide]:
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, ride_id, ride_version, google_event_id, synced_at,
                   sync_status, error_message, created_at, updated_at
            FROM synced_rides
            ORDER BY synced_at DESC
        """)
        return [_row_to_synced_ride(row) for row in cursor.fetchall()]


def is_ride_synced(ride_id: str) -> bool:
    """Check if a ride is currently synced to Google Calendar."""
    synced = get_synced_ride(ride_id)
    return synced is not None and synced.sync_status == "synced"


def get_failed_ride_syncs() -> list[SyncedRide]:
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, ride_id, ride_version, google_event_id, synced_at,
                   sync_status, error_message, created_at, updated_at
            FROM synced_rides
            WHERE sync_status = 'failed'
            ORDER BY updated_at DESC
        """)
        return [_row_to_synced_ride(row) for row in cursor.fetchall()]
