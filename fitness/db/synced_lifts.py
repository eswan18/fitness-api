"""Database access functions for synced lifts (Google Calendar sync tracking)."""

import logging
from datetime import datetime, timezone

from psycopg import sql

from fitness.models.sync import SyncedLift, SyncStatus
from .connection import get_db_cursor

logger = logging.getLogger(__name__)


def _row_to_synced_lift(row: tuple) -> SyncedLift:
    """Convert a database row to a SyncedLift object."""
    (
        sync_id,
        lift_id,
        lift_version,
        google_event_id,
        synced_at,
        sync_status,
        error_message,
        created_at,
        updated_at,
    ) = row
    return SyncedLift(
        id=sync_id,
        lift_id=lift_id,
        lift_version=lift_version,
        google_event_id=google_event_id,
        synced_at=synced_at,
        sync_status=sync_status,
        error_message=error_message,
        created_at=created_at,
        updated_at=updated_at,
    )


def get_synced_lift(lift_id: str) -> SyncedLift | None:
    """Get sync record for a specific lift."""
    try:
        with get_db_cursor() as cursor:
            logger.debug(f"Querying sync record for lift_id={lift_id}")
            cursor.execute(
                """
                SELECT id, lift_id, lift_version, google_event_id, synced_at,
                       sync_status, error_message, created_at, updated_at
                FROM synced_lifts
                WHERE lift_id = %s
            """,
                (lift_id,),
            )

            row = cursor.fetchone()
            if row is None:
                logger.debug(f"No sync record found for lift_id={lift_id}")
                return None

            synced_lift = _row_to_synced_lift(row)
            logger.debug(
                f"Found sync record: lift_id={lift_id}, sync_status={synced_lift.sync_status}, "
                f"google_event_id={synced_lift.google_event_id}"
            )
            return synced_lift
    except Exception as e:
        logger.exception(
            f"Database error retrieving sync record: lift_id={lift_id}, "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def create_synced_lift(
    lift_id: str,
    google_event_id: str,
    lift_version: int = 1,
    sync_status: SyncStatus = "synced",
    error_message: str | None = None,
) -> SyncedLift:
    """Create a new sync record for a lift."""
    try:
        logger.info(
            f"Creating sync record: lift_id={lift_id}, google_event_id={google_event_id}, "
            f"sync_status={sync_status}, lift_version={lift_version}"
        )

        with get_db_cursor() as cursor:
            now = datetime.now(timezone.utc)
            cursor.execute(
                """
                INSERT INTO synced_lifts
                (lift_id, lift_version, google_event_id, synced_at, sync_status, error_message, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at, updated_at
            """,
                (
                    lift_id,
                    lift_version,
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
                raise RuntimeError(
                    f"Failed to create sync record for lift_id={lift_id}"
                )
            sync_id, created_at, updated_at = result

            logger.info(
                f"Successfully created sync record: sync_id={sync_id}, lift_id={lift_id}, "
                f"google_event_id={google_event_id}, sync_status={sync_status}"
            )

            return SyncedLift(
                id=sync_id,
                lift_id=lift_id,
                lift_version=lift_version,
                google_event_id=google_event_id,
                synced_at=now,
                sync_status=sync_status,
                error_message=error_message,
                created_at=created_at,
                updated_at=updated_at,
            )
    except Exception as e:
        logger.exception(
            f"Database error creating sync record: lift_id={lift_id}, "
            f"google_event_id={google_event_id}, sync_status={sync_status}, "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def update_synced_lift(
    lift_id: str,
    lift_version: int | None = None,
    google_event_id: str | None = None,
    sync_status: SyncStatus | None = None,
    error_message: str | None = None,
    clear_error_message: bool = False,
) -> SyncedLift | None:
    """Update an existing sync record."""
    try:
        update_details = []
        if lift_version is not None:
            update_details.append(f"lift_version={lift_version}")
        if google_event_id is not None:
            update_details.append(f"google_event_id={google_event_id}")
        if sync_status is not None:
            update_details.append(f"sync_status={sync_status}")
        if error_message is not None:
            update_details.append(f"error_message={error_message[:100]}...")
        if clear_error_message:
            update_details.append("clear_error_message=True")

        logger.info(
            f"Updating sync record: lift_id={lift_id}, updates=[{', '.join(update_details)}]"
        )

        with get_db_cursor() as cursor:
            update_fields: list[sql.Composable] = []
            params: list = []

            if lift_version is not None:
                update_fields.append(sql.SQL("lift_version = %s"))
                params.append(lift_version)

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
                logger.debug(
                    f"No fields to update for lift_id={lift_id}, returning existing record"
                )
                return get_synced_lift(lift_id)

            update_fields.append(sql.SQL("updated_at = %s"))
            params.append(datetime.now(timezone.utc))

            params.append(lift_id)

            query = sql.SQL("""
                UPDATE synced_lifts
                SET {update_fields}
                WHERE lift_id = %s
                RETURNING id, lift_id, lift_version, google_event_id, synced_at,
                          sync_status, error_message, created_at, updated_at
            """).format(update_fields=sql.SQL(", ").join(update_fields))

            cursor.execute(query, params)
            row = cursor.fetchone()

            if row is None:
                logger.warning(f"No sync record found to update: lift_id={lift_id}")
                return None

            synced_lift = _row_to_synced_lift(row)
            logger.info(
                f"Successfully updated sync record: lift_id={lift_id}, "
                f"new_sync_status={synced_lift.sync_status}, google_event_id={synced_lift.google_event_id}"
            )

            return synced_lift
    except Exception as e:
        logger.exception(
            f"Database error updating sync record: lift_id={lift_id}, "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def delete_synced_lift(lift_id: str) -> bool:
    """Delete a sync record for a lift (when unsyncing from calendar)."""
    try:
        logger.info(f"Deleting sync record: lift_id={lift_id}")

        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM synced_lifts WHERE lift_id = %s", (lift_id,))
            deleted_count = cursor.rowcount

            if deleted_count > 0:
                logger.info(
                    f"Successfully deleted sync record: lift_id={lift_id}, "
                    f"rows_deleted={deleted_count}"
                )
                return True
            else:
                logger.warning(
                    f"No sync record found to delete: lift_id={lift_id}, "
                    f"rows_deleted={deleted_count}"
                )
                return False
    except Exception as e:
        logger.exception(
            f"Database error deleting sync record: lift_id={lift_id}, "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def get_all_synced_lifts() -> list[SyncedLift]:
    """Get all sync records."""
    try:
        logger.debug("Querying all lift sync records")

        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT id, lift_id, lift_version, google_event_id, synced_at,
                       sync_status, error_message, created_at, updated_at
                FROM synced_lifts
                ORDER BY synced_at DESC
            """)

            results = [_row_to_synced_lift(row) for row in cursor.fetchall()]

            logger.info(f"Retrieved all lift sync records: count={len(results)}")
            return results
    except Exception as e:
        logger.exception(
            f"Database error retrieving all lift sync records: "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def is_lift_synced(lift_id: str) -> bool:
    """Check if a lift is currently synced to Google Calendar."""
    synced_lift = get_synced_lift(lift_id)
    return synced_lift is not None and synced_lift.sync_status == "synced"


def get_failed_lift_syncs() -> list[SyncedLift]:
    """Get all lifts with failed sync status for retry."""
    try:
        logger.debug("Querying failed lift sync records")

        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT id, lift_id, lift_version, google_event_id, synced_at,
                       sync_status, error_message, created_at, updated_at
                FROM synced_lifts
                WHERE sync_status = 'failed'
                ORDER BY updated_at DESC
            """)

            results = [_row_to_synced_lift(row) for row in cursor.fetchall()]

            logger.info(f"Retrieved failed lift sync records: count={len(results)}")
            return results
    except Exception as e:
        logger.exception(
            f"Database error retrieving failed lift sync records: "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise
