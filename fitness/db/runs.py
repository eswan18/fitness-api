import logging
from datetime import date, timedelta

from psycopg import sql

from fitness.models import Run
from fitness.models.run_detail import RunDetail
from .connection import get_db_cursor, get_db_connection
from .runs_history import insert_run_history_with_cursor

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
        deleted_filter = sql.SQL("") if include_deleted else sql.SQL(" WHERE r.deleted_at IS NULL")
        query = sql.SQL("""
            SELECT r.id, r.datetime_utc, r.type, r.distance, r.duration, r.source, r.avg_heart_rate, r.shoe_id, r.deleted_at, NULLIF(CONCAT_WS(' ', s.brand, s.model), ''), r.notes
            FROM runs r
            LEFT JOIN shoes s ON r.shoe_id = s.id
            {deleted_filter}
            ORDER BY r.datetime_utc
        """).format(deleted_filter=deleted_filter)
        cursor.execute(query)
        rows = cursor.fetchall()
        return [_row_to_run(row) for row in rows]


def get_runs_in_date_range(
    start_date: date,
    end_date: date,
    include_deleted: bool = False,
) -> list[Run]:
    """Get runs within a date range with shoe information."""
    with get_db_cursor() as cursor:
        deleted_filter = sql.SQL("")
        if not include_deleted:
            deleted_filter = sql.SQL(" AND r.deleted_at IS NULL")
        query = sql.SQL("""
            SELECT r.id, r.datetime_utc, r.type, r.distance, r.duration, r.source,
                   r.avg_heart_rate, r.shoe_id, r.deleted_at, NULLIF(CONCAT_WS(' ', s.brand, s.model), ''), r.notes
            FROM runs r
            LEFT JOIN shoes s ON r.shoe_id = s.id
            WHERE DATE(r.datetime_utc) BETWEEN %s AND %s{deleted_filter}
            ORDER BY r.datetime_utc
        """).format(deleted_filter=deleted_filter)
        cursor.execute(query, [start_date, end_date])
        rows = cursor.fetchall()
        return [_row_to_run(row) for row in rows]


def get_runs_for_date_range(
    start: date,
    end: date,
    user_timezone: str | None = None,
) -> list[Run]:
    """Fetch runs for a date range, widening by 1 day when timezone conversion is needed.

    When user_timezone is set, the SQL query is widened by +-1 day to account for
    UTC-to-local date offset (max +-14 hours). Callers still do exact filtering
    in Python after timezone conversion.
    """
    if user_timezone is not None:
        widened_start = start - timedelta(days=1) if start > date.min else start
        widened_end = end + timedelta(days=1) if end < date.max else end
        return get_runs_in_date_range(widened_start, widened_end)
    return get_runs_in_date_range(start, end)


def bulk_create_runs(runs: list[Run], chunk_size: int = 20) -> int:
    """Insert multiple runs into the database in chunks with automatic history creation. Returns the number of inserted rows."""
    if not runs:
        return 0

    logger.info(f"Starting bulk insert of {len(runs)} runs in chunks of {chunk_size}")

    # Imports no longer resolve or create shoes: each run records its raw gear
    # name in `imported_shoe_name` and leaves `shoe_id` NULL. Shoes are created
    # and assigned to runs manually.
    total_inserted = 0

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                # Process runs in chunks
                for i in range(0, len(runs), chunk_size):
                    chunk = runs[i : i + chunk_size]

                    chunk_inserted = 0
                    for run in chunk:
                        # Imports never assign a shoe; keep the raw gear name so
                        # it can be assigned manually later.
                        shoe_id = None
                        imported_shoe_name = run.shoe_name

                        # ON CONFLICT DO NOTHING ensures a previously-imported
                        # run (including soft-deleted ones) is silently skipped
                        # rather than failing the whole batch on a PK conflict.
                        cursor.execute(
                            """
                            INSERT INTO runs (id, datetime_utc, type, distance, duration, source, avg_heart_rate, shoe_id, deleted_at, max_heart_rate, step_cadence, end_datetime_utc, source_name, imported_shoe_name)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (id) DO NOTHING
                            """,
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
                                run.max_heart_rate,
                                run.step_cadence,
                                run.end_datetime_utc,
                                run.source_name,
                                imported_shoe_name,
                            ),
                        )

                        # Only write the history row when the run was actually
                        # inserted, to keep history rows in lockstep with runs.
                        if cursor.rowcount == 1:
                            chunk_inserted += 1
                            cursor.execute(
                                """
                                INSERT INTO runs_history (
                                    run_id, version_number, change_type, datetime_utc, type,
                                    distance, duration, source, avg_heart_rate, shoe_id,
                                    changed_by, change_reason
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    run.id,
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
                                ),
                            )

                    total_inserted += chunk_inserted

                    logger.info(
                        f"Inserted {chunk_inserted} runs with history in chunk {i // chunk_size + 1} (runs {i + 1}-{min(i + chunk_size, len(runs))})"
                    )

    logger.info(
        f"Bulk insert completed: {total_inserted} total runs inserted with original history entries"
    )
    return total_inserted


def get_run_duplicate_of(run_id: str) -> str | None:
    """Return the id this run is marked as a duplicate of, or None.

    Returns None both when the run does not exist and when it is not a
    duplicate; callers needing to distinguish should check existence first.
    """
    with get_db_cursor() as cursor:
        cursor.execute("SELECT duplicate_of_id FROM runs WHERE id = %s", (run_id,))
        row = cursor.fetchone()
        return row[0] if row else None


def mark_run_duplicate(
    run_id: str,
    duplicate_of_id: str,
    changed_by: str = "user",
) -> bool:
    """Mark a run as a duplicate of another run.

    Sets `deleted_at` (so it disappears from every read and is skipped on
    re-import) and `duplicate_of_id` (the kept run), and records a
    `'deletion'` history row. The caller is responsible for validating that
    `duplicate_of_id` refers to a live, non-duplicate run. Returns False if the
    run does not exist or is already soft-deleted (no-op).
    """
    run = get_run_by_id(run_id)
    if run is None:
        return False

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE runs
                    SET deleted_at = CURRENT_TIMESTAMP,
                        duplicate_of_id = %s,
                        version = version + 1,
                        last_edited_at = CURRENT_TIMESTAMP,
                        last_edited_by = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND deleted_at IS NULL
                    RETURNING version
                    """,
                    (duplicate_of_id, changed_by, run_id),
                )
                row = cursor.fetchone()
                if row is None:
                    return False
                new_version = row[0]
                insert_run_history_with_cursor(
                    cursor,
                    run,
                    new_version,
                    "deletion",
                    changed_by,
                    f"Marked as duplicate of {duplicate_of_id}",
                )
    logger.info(f"Marked run {run_id} as duplicate of {duplicate_of_id}")
    return True


def unmark_run_duplicate(run_id: str, changed_by: str = "user") -> bool:
    """Reverse `mark_run_duplicate`: clear `deleted_at` and `duplicate_of_id`.

    The `duplicate_of_id IS NOT NULL` guard ensures this only resurrects rows
    that were hidden *because* they were duplicates, never a row soft-deleted
    for another reason. Records an `'edit'` history row. Returns False if the
    run is not currently a duplicate.
    """
    run = get_run_by_id(run_id, include_deleted=True)
    if run is None:
        return False

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE runs
                    SET deleted_at = NULL,
                        duplicate_of_id = NULL,
                        version = version + 1,
                        last_edited_at = CURRENT_TIMESTAMP,
                        last_edited_by = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                      AND deleted_at IS NOT NULL
                      AND duplicate_of_id IS NOT NULL
                    RETURNING version
                    """,
                    (changed_by, run_id),
                )
                row = cursor.fetchone()
                if row is None:
                    return False
                new_version = row[0]
                insert_run_history_with_cursor(
                    cursor,
                    run,
                    new_version,
                    "edit",
                    changed_by,
                    "Unmarked as duplicate",
                )
    logger.info(f"Unmarked run {run_id} as duplicate")
    return True


def find_candidate_duplicate_runs(
    run_id: str,
    window_minutes: int = 120,
) -> list[RunDetail]:
    """Find live runs near `run_id` in time that could be its original.

    Returns non-deleted, non-duplicate runs (excluding `run_id` itself) whose
    `datetime_utc` is within ±`window_minutes` of the target, ordered by time
    proximity. Used to populate the "mark as duplicate" picker. Returns an empty
    list if the target run does not exist.
    """
    target = get_run_by_id(run_id, include_deleted=True)
    if target is None:
        return []

    start = target.datetime_utc - timedelta(minutes=window_minutes)
    end = target.datetime_utc + timedelta(minutes=window_minutes)
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT r.id, r.datetime_utc, r.type, r.distance, r.duration, r.source, r.avg_heart_rate, r.shoe_id, r.deleted_at,
                   COALESCE(NULLIF(CONCAT_WS(' ', s.brand, s.model), ''), 'Unknown') as shoe_name, s.retirement_notes,
                   sr.sync_status, sr.synced_at, sr.google_event_id, sr.run_version, sr.error_message, r.version,
                   r.run_workout_id, r.notes, r.duplicate_of_id
            FROM runs r
            LEFT JOIN shoes s ON r.shoe_id = s.id
            LEFT JOIN synced_runs sr ON sr.run_id = r.id
            WHERE r.id != %s
              AND r.deleted_at IS NULL
              AND r.duplicate_of_id IS NULL
              AND r.datetime_utc BETWEEN %s AND %s
            ORDER BY ABS(EXTRACT(EPOCH FROM (r.datetime_utc - %s))) ASC
            """,
            (run_id, start, end, target.datetime_utc),
        )
        rows = cursor.fetchall()
        return [_row_to_run_detail(row) for row in rows]


def get_existing_run_ids() -> set[str]:
    """Get all existing run IDs from the database, including soft-deleted ones.

    Soft-deleted IDs are included so that re-imports from external providers
    (e.g. Strava) skip runs the user has explicitly deleted, rather than
    attempting to re-insert and hitting a primary-key conflict.
    """
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id FROM runs")
        rows = cursor.fetchall()
        existing_ids = {row[0] for row in rows}
        logger.info(f"Found {len(existing_ids)} existing run IDs in database")
        return existing_ids


def get_run_details_in_date_range(
    start_date: date,
    end_date: date,
    include_deleted: bool = False,
    synced: bool | None = None,
    user_timezone: str | None = None,
) -> list[RunDetail]:
    """Get detailed runs with shoes and sync info within a date range.

    Joins `runs` to `shoes` and `synced_runs`.

    When `user_timezone` is set, the SQL range is widened by ±1 day to cover
    runs whose UTC date differs from their local date. Callers must do exact
    local-date filtering in Python after this returns.
    """
    if user_timezone is not None:
        if start_date > date.min:
            start_date = start_date - timedelta(days=1)
        if end_date < date.max:
            end_date = end_date + timedelta(days=1)
    with get_db_cursor() as cursor:
        conditions: list[sql.Composable] = [
            sql.SQL("DATE(r.datetime_utc) BETWEEN %s AND %s")
        ]
        conditions.extend(_build_run_detail_filters(include_deleted, synced))
        params: list = [start_date, end_date]

        where_clause = sql.SQL(" AND ").join(conditions)
        query = sql.SQL("""
            SELECT r.id, r.datetime_utc, r.type, r.distance, r.duration, r.source, r.avg_heart_rate, r.shoe_id, r.deleted_at,
                   COALESCE(NULLIF(CONCAT_WS(' ', s.brand, s.model), ''), 'Unknown') as shoe_name, s.retirement_notes,
                   sr.sync_status, sr.synced_at, sr.google_event_id, sr.run_version, sr.error_message, r.version,
                   r.run_workout_id, r.notes, r.duplicate_of_id
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
                   COALESCE(NULLIF(CONCAT_WS(' ', s.brand, s.model), ''), 'Unknown') as shoe_name, s.retirement_notes,
                   sr.sync_status, sr.synced_at, sr.google_event_id, sr.run_version, sr.error_message, r.version,
                   r.run_workout_id, r.notes, r.duplicate_of_id
            FROM runs r
            LEFT JOIN shoes s ON r.shoe_id = s.id
            LEFT JOIN synced_runs sr ON sr.run_id = r.id
            {where_clause}
            ORDER BY r.datetime_utc DESC
        """).format(where_clause=where_clause)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [_row_to_run_detail(row) for row in rows]


def get_run_details_by_ids(run_ids: list[str]) -> list[RunDetail]:
    """Get detailed runs for a specific set of run IDs."""
    if not run_ids:
        return []
    with get_db_cursor() as cursor:
        placeholders = sql.SQL(", ").join(sql.Placeholder() * len(run_ids))
        query = sql.SQL("""
            SELECT r.id, r.datetime_utc, r.type, r.distance, r.duration, r.source, r.avg_heart_rate, r.shoe_id, r.deleted_at,
                   COALESCE(NULLIF(CONCAT_WS(' ', s.brand, s.model), ''), 'Unknown') as shoe_name, s.retirement_notes,
                   sr.sync_status, sr.synced_at, sr.google_event_id, sr.run_version, sr.error_message, r.version,
                   r.run_workout_id, r.notes, r.duplicate_of_id
            FROM runs r
            LEFT JOIN shoes s ON r.shoe_id = s.id
            LEFT JOIN synced_runs sr ON sr.run_id = r.id
            WHERE r.id IN ({placeholders}) AND r.deleted_at IS NULL
            ORDER BY r.datetime_utc ASC
        """).format(placeholders=placeholders)
        cursor.execute(query, run_ids)
        rows = cursor.fetchall()
        return [_row_to_run_detail(row) for row in rows]


def get_run_by_id(run_id: str, include_deleted: bool = False) -> Run | None:
    """Get a single run by its ID.

    Args:
        run_id: The ID of the run to retrieve.
        include_deleted: If True, include soft-deleted runs. Defaults to False.
    """
    with get_db_cursor() as cursor:
        deleted_filter = sql.SQL("") if include_deleted else sql.SQL(" AND r.deleted_at IS NULL")
        query = sql.SQL("""
            SELECT r.id, r.datetime_utc, r.type, r.distance, r.duration, r.source, r.avg_heart_rate, r.shoe_id, r.deleted_at, NULLIF(CONCAT_WS(' ', s.brand, s.model), ''), r.notes
            FROM runs r
            LEFT JOIN shoes s ON r.shoe_id = s.id
            WHERE r.id = %s{deleted_filter}
        """).format(deleted_filter=deleted_filter)
        cursor.execute(query, (run_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return _row_to_run(row)


def update_run_notes(run_id: str, notes: str | None) -> bool:
    """Set (or clear) a run's freeform markdown note.

    A lightweight, single-field update with no version bump or history record
    (unlike metric edits via ``update_run_with_history``). The note is never
    touched by re-imports (``bulk_create_runs`` skips existing rows), so it
    survives Strava/MMF re-syncs. Returns True if a non-deleted run matched.
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE runs
            SET notes = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND deleted_at IS NULL
            """,
            (notes, run_id),
        )
        return cursor.rowcount > 0


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
        notes,
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
        notes=notes,
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
        notes,
        duplicate_of_id,
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
        notes=notes,
        deleted_at=deleted_at,
        duplicate_of_id=duplicate_of_id,
        version=run_table_version,
        run_workout_id=run_workout_id,
        is_synced=(sync_status == "synced"),
        sync_status=sync_status,
        synced_at=synced_at,
        google_event_id=google_event_id or None,
        synced_version=run_version,
        error_message=error_message,
    )
