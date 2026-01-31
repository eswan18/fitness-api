import logging
from datetime import date

from psycopg import sql

from fitness.models import Run
from fitness.models.run_detail import RunDetail
from .connection import get_db_cursor, get_db_connection

logger = logging.getLogger(__name__)


def _build_run_detail_filters(
    include_deleted: bool = False,
    synced: bool | None = None,
) -> list[sql.Composable]:
    """Build common WHERE clause conditions for run detail queries.

    Returns a list of SQL conditions that can be joined with AND.
    """
    conditions: list[sql.Composable] = []
    if not include_deleted:
        conditions.append(sql.SQL("r.deleted_at IS NULL"))
    if synced is True:
        conditions.append(sql.SQL("sr.sync_status = 'synced'"))
    elif synced is False:
        conditions.append(
            sql.SQL("(sr.sync_status IS DISTINCT FROM 'synced' OR sr.run_id IS NULL)")
        )
    return conditions


def get_all_runs(include_deleted: bool = False) -> list[Run]:
    """Get all runs from the database with shoe information."""
    with get_db_cursor() as cursor:
        if include_deleted:
            cursor.execute("""
                SELECT r.id, r.datetime_utc, r.type, r.distance, r.duration, r.source, r.avg_heart_rate, r.shoe_id, r.deleted_at, s.name
                FROM runs r
                LEFT JOIN shoes s ON r.shoe_id = s.id
                ORDER BY r.datetime_utc
            """)
        else:
            cursor.execute("""
                SELECT r.id, r.datetime_utc, r.type, r.distance, r.duration, r.source, r.avg_heart_rate, r.shoe_id, r.deleted_at, s.name
                FROM runs r
                LEFT JOIN shoes s ON r.shoe_id = s.id
                WHERE r.deleted_at IS NULL
                ORDER BY r.datetime_utc
            """)
        rows = cursor.fetchall()
        return [_row_to_run(row) for row in rows]


def bulk_create_runs(runs: list[Run], chunk_size: int = 20) -> int:
    """Insert multiple runs into the database in chunks with automatic history creation. Returns the number of inserted rows."""
    if not runs:
        return 0

    logger.info(f"Starting bulk insert of {len(runs)} runs in chunks of {chunk_size}")

    # Batch check and create shoes - much more efficient!
    from fitness.db.shoes import get_existing_shoes_by_names, bulk_create_shoes_by_names

    # Get unique shoe names (excluding None)
    unique_shoe_names = {run.shoe_name for run in runs if run.shoe_name is not None}
    logger.debug(f"Found {len(unique_shoe_names)} unique shoes: {unique_shoe_names}")

    # Batch check which shoes already exist
    existing_shoes = get_existing_shoes_by_names(unique_shoe_names)
    logger.debug(f"Found {len(existing_shoes)} existing shoes in database")

    # Create missing shoes in one batch
    missing_shoe_names = unique_shoe_names - existing_shoes.keys()
    if missing_shoe_names:
        logger.info(
            f"Creating {len(missing_shoe_names)} new shoes: {missing_shoe_names}"
        )
        new_shoes = bulk_create_shoes_by_names(missing_shoe_names)
        # Combine existing and newly created shoes
        all_shoes = {**existing_shoes, **new_shoes}
    else:
        all_shoes = existing_shoes
        logger.debug("No new shoes needed")

    total_inserted = 0

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                # Process runs in chunks
                for i in range(0, len(runs), chunk_size):
                    chunk = runs[i : i + chunk_size]

                    # Prepare run data for insertion
                    run_data = []
                    history_data = []

                    for run in chunk:
                        shoe_id = (
                            all_shoes.get(run.shoe_name) if run.shoe_name else None
                        )

                        # Add to runs table data
                        run_data.append(
                            (
                                run.id,
                                run.datetime_utc,
                                run.type,
                                run.distance,
                                run.duration,
                                run.source,
                                run.avg_heart_rate,
                                shoe_id,
                                run.deleted_at,
                            )
                        )

                        # Add to history table data (original entry)
                        history_data.append(
                            (
                                run.id,  # run_id
                                1,  # version_number
                                "original",  # change_type
                                run.datetime_utc,
                                run.type,
                                run.distance,
                                run.duration,
                                run.source,
                                run.avg_heart_rate,
                                shoe_id,
                                "system",  # changed_by
                                "Initial import",  # change_reason
                            )
                        )

                    # Insert runs
                    cursor.executemany(
                        """
                        INSERT INTO runs (id, datetime_utc, type, distance, duration, source, avg_heart_rate, shoe_id, deleted_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        run_data,
                    )

                    chunk_inserted = cursor.rowcount
                    total_inserted += chunk_inserted

                    # Insert corresponding history entries
                    cursor.executemany(
                        """
                        INSERT INTO runs_history (
                            run_id, version_number, change_type, datetime_utc, type, 
                            distance, duration, source, avg_heart_rate, shoe_id,
                            changed_by, change_reason
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        history_data,
                    )

                    logger.info(
                        f"Inserted {chunk_inserted} runs with history in chunk {i // chunk_size + 1} (runs {i + 1}-{min(i + chunk_size, len(runs))})"
                    )

    logger.info(
        f"Bulk insert completed: {total_inserted} total runs inserted with original history entries"
    )
    return total_inserted


def get_existing_run_ids() -> set[str]:
    """Get all existing run IDs from the database."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id FROM runs WHERE deleted_at IS NULL")
        rows = cursor.fetchall()
        existing_ids = {row[0] for row in rows}
        logger.info(f"Found {len(existing_ids)} existing run IDs in database")
        return existing_ids


def get_run_details_in_date_range(
    start_date: date,
    end_date: date,
    include_deleted: bool = False,
    synced: bool | None = None,
) -> list[RunDetail]:
    """Get detailed runs with shoes and sync info within a date range.

    Joins `runs` to `shoes` and `synced_runs`.
    """
    with get_db_cursor() as cursor:
        conditions = [sql.SQL("DATE(r.datetime_utc) BETWEEN %s AND %s")]
        conditions.extend(_build_run_detail_filters(include_deleted, synced))
        params: list = [start_date, end_date]

        where_clause = sql.SQL(" AND ").join(conditions)
        query = sql.SQL("""
            SELECT r.id, r.datetime_utc, r.type, r.distance, r.duration, r.source, r.avg_heart_rate, r.shoe_id, r.deleted_at,
                   COALESCE(s.name, 'Unknown') as shoe_name, s.retirement_notes,
                   sr.sync_status, sr.synced_at, sr.google_event_id, sr.run_version, sr.error_message, r.version,
                   r.run_workout_id
            FROM runs r
            LEFT JOIN shoes s ON r.shoe_id = s.id
            LEFT JOIN synced_runs sr ON sr.run_id = r.id
            WHERE {where_clause}
            ORDER BY r.datetime_utc DESC
        """).format(where_clause=where_clause)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [_row_to_run_detail(row) for row in rows]


def get_all_run_details(
    include_deleted: bool = False, synced: bool | None = None
) -> list[RunDetail]:
    """Get all detailed runs with shoes and sync info."""
    with get_db_cursor() as cursor:
        conditions = _build_run_detail_filters(include_deleted, synced)
        params: list = []
        where_clause = (
            sql.SQL("WHERE ") + sql.SQL(" AND ").join(conditions)
            if conditions
            else sql.SQL("")
        )
        query = sql.SQL("""
            SELECT r.id, r.datetime_utc, r.type, r.distance, r.duration, r.source, r.avg_heart_rate, r.shoe_id, r.deleted_at,
                   COALESCE(s.name, 'Unknown') as shoe_name, s.retirement_notes,
                   sr.sync_status, sr.synced_at, sr.google_event_id, sr.run_version, sr.error_message, r.version,
                   r.run_workout_id
            FROM runs r
            LEFT JOIN shoes s ON r.shoe_id = s.id
            LEFT JOIN synced_runs sr ON sr.run_id = r.id
            {where_clause}
            ORDER BY r.datetime_utc DESC
        """).format(where_clause=where_clause)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [_row_to_run_detail(row) for row in rows]


def get_run_by_id(run_id: str, include_deleted: bool = False) -> Run | None:
    """Get a single run by its ID.

    Args:
        run_id: The ID of the run to retrieve.
        include_deleted: If True, include soft-deleted runs. Defaults to False.
    """
    with get_db_cursor() as cursor:
        if include_deleted:
            cursor.execute(
                """
                SELECT r.id, r.datetime_utc, r.type, r.distance, r.duration, r.source, r.avg_heart_rate, r.shoe_id, r.deleted_at, s.name
                FROM runs r
                LEFT JOIN shoes s ON r.shoe_id = s.id
                WHERE r.id = %s
            """,
                (run_id,),
            )
        else:
            cursor.execute(
                """
                SELECT r.id, r.datetime_utc, r.type, r.distance, r.duration, r.source, r.avg_heart_rate, r.shoe_id, r.deleted_at, s.name
                FROM runs r
                LEFT JOIN shoes s ON r.shoe_id = s.id
                WHERE r.id = %s AND r.deleted_at IS NULL
            """,
                (run_id,),
            )
        row = cursor.fetchone()
        if not row:
            return None
        return _row_to_run(row)


# Removed RunWithShoes helpers; superseded by RunDetail flows


def _row_to_run(row) -> Run:
    """Convert a database row to a Run object."""
    (
        run_id,
        datetime_utc,
        type_,
        distance,
        duration,
        source,
        avg_heart_rate,
        shoe_id,
        deleted_at,
        shoe_name,
    ) = row
    run = Run(
        id=run_id,
        datetime_utc=datetime_utc,
        type=type_,
        distance=distance,
        duration=duration,
        source=source,
        avg_heart_rate=avg_heart_rate,
        shoe_id=shoe_id,
        deleted_at=deleted_at,
    )
    run._shoe_name = shoe_name
    return run


def _row_to_run_detail(row) -> RunDetail:
    (
        run_id,
        datetime_utc,
        type_,
        distance,
        duration,
        source,
        avg_heart_rate,
        shoe_id,
        deleted_at,
        shoe_name,
        retirement_notes,
        sync_status,
        synced_at,
        google_event_id,
        run_version,
        error_message,
        run_table_version,
        run_workout_id,
    ) = row

    # Normalize shoe_name
    if shoe_name == "Unknown" or shoe_name is None:
        shoe_name = None

    return RunDetail(
        id=run_id,
        datetime_utc=datetime_utc,
        type=type_,
        distance=distance,
        duration=duration,
        source=source,
        avg_heart_rate=avg_heart_rate,
        shoe_id=shoe_id,
        shoes=shoe_name,
        shoe_retirement_notes=retirement_notes,
        deleted_at=deleted_at,
        version=run_table_version,
        run_workout_id=run_workout_id,
        is_synced=(sync_status == "synced"),
        sync_status=sync_status,
        synced_at=synced_at,
        google_event_id=google_event_id or None,
        synced_version=run_version,
        error_message=error_message,
    )
