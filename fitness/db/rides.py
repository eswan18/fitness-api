import logging
from datetime import date, timedelta

from psycopg import sql

from fitness.models import Ride
from .connection import get_db_cursor, get_db_connection

logger = logging.getLogger(__name__)


def get_all_rides(include_deleted: bool = False) -> list[Ride]:
    """Get all rides from the database."""
    with get_db_cursor() as cursor:
        deleted_filter = (
            sql.SQL("") if include_deleted else sql.SQL(" WHERE deleted_at IS NULL")
        )
        query = sql.SQL("""
            SELECT id, datetime_utc, type, distance, duration, source, avg_heart_rate, deleted_at
            FROM rides
            {deleted_filter}
            ORDER BY datetime_utc
        """).format(deleted_filter=deleted_filter)
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
        query = sql.SQL("""
            SELECT id, datetime_utc, type, distance, duration, source,
                   avg_heart_rate, deleted_at
            FROM rides
            WHERE DATE(datetime_utc) BETWEEN %s AND %s{deleted_filter}
            ORDER BY datetime_utc
        """).format(deleted_filter=deleted_filter)
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
        return get_rides_in_date_range(
            start - timedelta(days=1), end + timedelta(days=1)
        )
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
                        )
                        for ride in chunk
                    ]
                    cursor.executemany(
                        """
                        INSERT INTO rides (id, datetime_utc, type, distance, duration, source, avg_heart_rate, deleted_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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


def get_existing_ride_ids() -> set[str]:
    """Get all existing (non-deleted) ride IDs from the database."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id FROM rides WHERE deleted_at IS NULL")
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
    )
