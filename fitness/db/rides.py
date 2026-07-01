import logging
from datetime import date, timedelta

from psycopg import sql

from fitness.models import Ride
from fitness.models.ride_detail import RideDetail
from .connection import get_db_cursor, get_db_connection

logger = logging.getLogger(__name__)


_RIDE_SELECT = sql.SQL("""
    SELECT id, datetime_utc, type, distance, duration, source, avg_heart_rate, deleted_at, name
    FROM rides
""")

_RIDE_DETAIL_SELECT = sql.SQL("""
    SELECT r.id, r.datetime_utc, r.type, r.distance, r.duration, r.source,
           r.avg_heart_rate, r.deleted_at, r.duplicate_of_id,
           sr.sync_status, sr.synced_at, sr.google_event_id,
           sr.ride_version, sr.error_message, r.name
    FROM rides r
    LEFT JOIN synced_rides sr ON sr.ride_id = r.id
""")


def _row_to_ride_detail(row) -> RideDetail:
    (
        ride_id,
        datetime_utc,
        type_,
        distance,
        duration,
        source,
        avg_heart_rate,
        deleted_at,
        duplicate_of_id,
        sync_status,
        synced_at,
        google_event_id,
        synced_version,
        error_message,
        name,
    ) = row
    return RideDetail(
        id=ride_id,
        datetime_utc=datetime_utc,
        type=type_,
        distance=distance,
        duration=duration,
        source=source,
        avg_heart_rate=avg_heart_rate,
        deleted_at=deleted_at,
        duplicate_of_id=duplicate_of_id,
        name=name,
        is_synced=(sync_status == "synced"),
        sync_status=sync_status,
        synced_at=synced_at,
        google_event_id=google_event_id or None,
        synced_version=synced_version,
        error_message=error_message,
    )


def get_all_rides(include_deleted: bool = False) -> list[Ride]:
    """Get all rides from the database."""
    with get_db_cursor() as cursor:
        deleted_filter = (
            sql.SQL("") if include_deleted else sql.SQL(" WHERE deleted_at IS NULL")
        )
        query = sql.SQL("{select} {deleted_filter} ORDER BY datetime_utc").format(
            select=_RIDE_SELECT, deleted_filter=deleted_filter
        )
        cursor.execute(query)
        rows = cursor.fetchall()
        return [_row_to_ride(row) for row in rows]


def get_rides_in_date_range(
    start_date: date,
    end_date: date,
    include_deleted: bool = False,
) -> list[Ride]:
    """Get rides within a UTC date range."""
    with get_db_cursor() as cursor:
        deleted_filter = sql.SQL("")
        if not include_deleted:
            deleted_filter = sql.SQL(" AND deleted_at IS NULL")
        query = sql.SQL(
            "{select} WHERE DATE(datetime_utc) BETWEEN %s AND %s{deleted_filter} ORDER BY datetime_utc"
        ).format(select=_RIDE_SELECT, deleted_filter=deleted_filter)
        cursor.execute(query, [start_date, end_date])
        rows = cursor.fetchall()
        return [_row_to_ride(row) for row in rows]


def get_rides_for_date_range(
    start: date,
    end: date,
    user_timezone: str | None = None,
) -> list[Ride]:
    """Fetch rides for a date range, widening by 1 day when timezone conversion is needed.

    Mirrors `get_runs_for_date_range`: when user_timezone is set, the SQL query
    is widened by ±1 day to account for UTC-to-local date offset. Callers do
    exact filtering in Python after timezone conversion.
    """
    if user_timezone is not None:
        widened_start = start - timedelta(days=1) if start > date.min else start
        widened_end = end + timedelta(days=1) if end < date.max else end
        return get_rides_in_date_range(widened_start, widened_end)
    return get_rides_in_date_range(start, end)


def bulk_create_rides(rides: list[Ride], chunk_size: int = 20) -> int:
    """Insert multiple rides into the database in chunks. Returns the number of inserted rows."""
    if not rides:
        return 0

    logger.info(f"Starting bulk insert of {len(rides)} rides in chunks of {chunk_size}")

    total_inserted = 0
    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                for i in range(0, len(rides), chunk_size):
                    chunk = rides[i : i + chunk_size]
                    ride_data = [
                        (
                            ride.id,
                            ride.datetime_utc,
                            ride.type,
                            ride.distance,
                            ride.duration,
                            ride.source,
                            ride.avg_heart_rate,
                            ride.deleted_at,
                            ride.max_heart_rate,
                            ride.end_datetime_utc,
                            ride.source_name,
                        )
                        for ride in chunk
                    ]
                    cursor.executemany(
                        """
                        INSERT INTO rides (id, datetime_utc, type, distance, duration, source, avg_heart_rate, deleted_at, max_heart_rate, end_datetime_utc, source_name)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        ride_data,
                    )
                    chunk_inserted = cursor.rowcount
                    total_inserted += chunk_inserted
                    logger.info(
                        f"Inserted {chunk_inserted} rides in chunk {i // chunk_size + 1} (rides {i + 1}-{min(i + chunk_size, len(rides))})"
                    )

    logger.info(f"Bulk insert completed: {total_inserted} total rides inserted")
    return total_inserted


def get_ride_details_in_date_range(
    start_date: date,
    end_date: date,
    include_deleted: bool = False,
    synced: bool | None = None,
    user_timezone: str | None = None,
) -> list[RideDetail]:
    """Get rides with sync info within a UTC date range.

    When `user_timezone` is set, the SQL range is widened by ±1 day; callers
    must do exact local-date filtering after this returns.
    """
    if user_timezone is not None:
        if start_date > date.min:
            start_date = start_date - timedelta(days=1)
        if end_date < date.max:
            end_date = end_date + timedelta(days=1)

    conditions: list[sql.Composable] = [
        sql.SQL("DATE(r.datetime_utc) BETWEEN %s AND %s")
    ]
    params: list = [start_date, end_date]
    if not include_deleted:
        conditions.append(sql.SQL("r.deleted_at IS NULL"))
    if synced is True:
        conditions.append(sql.SQL("sr.sync_status = 'synced'"))
    elif synced is False:
        conditions.append(
            sql.SQL("(sr.sync_status IS DISTINCT FROM 'synced' OR sr.ride_id IS NULL)")
        )

    where_clause = sql.SQL(" AND ").join(conditions)
    query = sql.SQL("{select} WHERE {where} ORDER BY r.datetime_utc DESC").format(
        select=_RIDE_DETAIL_SELECT, where=where_clause
    )
    with get_db_cursor() as cursor:
        cursor.execute(query, params)
        return [_row_to_ride_detail(row) for row in cursor.fetchall()]


def get_all_ride_details(
    include_deleted: bool = False,
    synced: bool | None = None,
) -> list[RideDetail]:
    conditions: list[sql.Composable] = []
    if not include_deleted:
        conditions.append(sql.SQL("r.deleted_at IS NULL"))
    if synced is True:
        conditions.append(sql.SQL("sr.sync_status = 'synced'"))
    elif synced is False:
        conditions.append(
            sql.SQL("(sr.sync_status IS DISTINCT FROM 'synced' OR sr.ride_id IS NULL)")
        )

    where_clause = (
        sql.SQL("WHERE ") + sql.SQL(" AND ").join(conditions)
        if conditions
        else sql.SQL("")
    )
    query = sql.SQL("{select} {where} ORDER BY r.datetime_utc DESC").format(
        select=_RIDE_DETAIL_SELECT, where=where_clause
    )
    with get_db_cursor() as cursor:
        cursor.execute(query)
        return [_row_to_ride_detail(row) for row in cursor.fetchall()]


def get_ride_detail_by_id(
    ride_id: str, include_deleted: bool = False
) -> RideDetail | None:
    deleted_filter = (
        sql.SQL("") if include_deleted else sql.SQL(" AND r.deleted_at IS NULL")
    )
    query = sql.SQL("{select} WHERE r.id = %s{deleted_filter}").format(
        select=_RIDE_DETAIL_SELECT, deleted_filter=deleted_filter
    )
    with get_db_cursor() as cursor:
        cursor.execute(query, (ride_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return _row_to_ride_detail(row)


def get_ride_by_id(ride_id: str, include_deleted: bool = False) -> Ride | None:
    """Get a single ride by its ID."""
    with get_db_cursor() as cursor:
        deleted_filter = (
            sql.SQL("") if include_deleted else sql.SQL(" AND deleted_at IS NULL")
        )
        query = sql.SQL("{select} WHERE id = %s{deleted_filter}").format(
            select=_RIDE_SELECT, deleted_filter=deleted_filter
        )
        cursor.execute(query, (ride_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return _row_to_ride(row)


def update_ride_name(ride_id: str, name: str | None) -> bool:
    """Set (or clear) a ride's user-authored display name.

    Mirrors `update_run_name`: a lightweight, single-field update with no
    version bump or history record. Never touched by re-imports, so it
    survives Strava re-syncs. Returns True if a non-deleted ride matched.
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE rides
            SET name = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND deleted_at IS NULL
            """,
            (name, ride_id),
        )
        return cursor.rowcount > 0


_UPDATABLE_RIDE_FIELDS: tuple[str, ...] = (
    "datetime_utc",
    "type",
    "distance",
    "duration",
    "avg_heart_rate",
)


def update_ride(ride_id: str, updates: dict) -> Ride:
    """Apply field-level updates to a ride and return the updated row.

    Raises ValueError if the ride is not found or no valid fields are provided.
    Only fields in `_UPDATABLE_RIDE_FIELDS` are honored.
    """
    if not updates:
        raise ValueError("No updates provided")

    set_fields = [f for f in _UPDATABLE_RIDE_FIELDS if f in updates]
    if not set_fields:
        raise ValueError("No updatable fields provided")

    set_assignments = sql.SQL(", ").join(
        sql.SQL("{} = {}").format(sql.Identifier(f), sql.Placeholder())
        for f in set_fields
    )
    query = sql.SQL(
        "UPDATE rides SET {set_assignments}, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = {id} AND deleted_at IS NULL"
    ).format(set_assignments=set_assignments, id=sql.Placeholder())
    params = [updates[f] for f in set_fields] + [ride_id]

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                if cursor.rowcount == 0:
                    raise ValueError(f"Ride {ride_id} not found")

    updated = get_ride_by_id(ride_id)
    if updated is None:  # Should be unreachable given rowcount check above.
        raise ValueError(f"Ride {ride_id} not found after update")
    return updated


def get_ride_duplicate_of(ride_id: str) -> str | None:
    """Return the id this ride is marked as a duplicate of, or None.

    Returns None both when the ride does not exist and when it is not a
    duplicate; callers needing to distinguish should check existence first.
    """
    with get_db_cursor() as cursor:
        cursor.execute("SELECT duplicate_of_id FROM rides WHERE id = %s", (ride_id,))
        row = cursor.fetchone()
        return row[0] if row else None


def mark_ride_duplicate(ride_id: str, duplicate_of_id: str) -> bool:
    """Mark a ride as a duplicate of another ride.

    Sets `deleted_at` (so it disappears from every read and is skipped on
    re-import) and `duplicate_of_id` (the kept ride). The caller is responsible
    for validating that `duplicate_of_id` refers to a live, non-duplicate ride.
    Returns False if the ride does not exist or is already soft-deleted.
    Rides have no history table, so no audit row is written.
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE rides
            SET deleted_at = CURRENT_TIMESTAMP,
                duplicate_of_id = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND deleted_at IS NULL
            """,
            (duplicate_of_id, ride_id),
        )
        return cursor.rowcount > 0


def unmark_ride_duplicate(ride_id: str) -> bool:
    """Reverse `mark_ride_duplicate`: clear `deleted_at` and `duplicate_of_id`.

    The `duplicate_of_id IS NOT NULL` guard ensures this only resurrects rides
    hidden *because* they were duplicates. Returns False if the ride is not
    currently a duplicate.
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE rides
            SET deleted_at = NULL,
                duplicate_of_id = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
              AND deleted_at IS NOT NULL
              AND duplicate_of_id IS NOT NULL
            """,
            (ride_id,),
        )
        return cursor.rowcount > 0


def find_candidate_duplicate_rides(
    ride_id: str,
    window_minutes: int = 120,
) -> list[RideDetail]:
    """Find live rides near `ride_id` in time that could be its original.

    Returns non-deleted, non-duplicate rides (excluding `ride_id` itself) whose
    `datetime_utc` is within ±`window_minutes` of the target, ordered by time
    proximity. Returns an empty list if the target ride does not exist.
    """
    target = get_ride_by_id(ride_id, include_deleted=True)
    if target is None:
        return []

    start = target.datetime_utc - timedelta(minutes=window_minutes)
    end = target.datetime_utc + timedelta(minutes=window_minutes)
    query = sql.SQL(
        "{select} WHERE r.id != %s AND r.deleted_at IS NULL "
        "AND r.duplicate_of_id IS NULL AND r.datetime_utc BETWEEN %s AND %s "
        "ORDER BY ABS(EXTRACT(EPOCH FROM (r.datetime_utc - %s))) ASC"
    ).format(select=_RIDE_DETAIL_SELECT)
    with get_db_cursor() as cursor:
        cursor.execute(query, (ride_id, start, end, target.datetime_utc))
        return [_row_to_ride_detail(row) for row in cursor.fetchall()]


def get_existing_ride_ids() -> set[str]:
    """Get all existing ride IDs from the database, including soft-deleted ones.

    Soft-deleted IDs are included so that re-imports from external providers
    (e.g. Strava) skip rides the user has explicitly deleted, rather than
    attempting to re-insert and hitting a primary-key conflict.
    """
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id FROM rides")
        rows = cursor.fetchall()
        existing_ids = {row[0] for row in rows}
        logger.info(f"Found {len(existing_ids)} existing ride IDs in database")
        return existing_ids


def _row_to_ride(row) -> Ride:
    (
        ride_id,
        datetime_utc,
        type_,
        distance,
        duration,
        source,
        avg_heart_rate,
        deleted_at,
        name,
    ) = row
    return Ride(
        id=ride_id,
        datetime_utc=datetime_utc,
        type=type_,
        distance=distance,
        duration=duration,
        source=source,
        avg_heart_rate=avg_heart_rate,
        deleted_at=deleted_at,
        name=name,
    )
