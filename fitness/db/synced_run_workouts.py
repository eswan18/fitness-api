"""Database access functions for synced run workouts (Google Calendar sync tracking)."""

import logging
from datetime import datetime, timezone

from psycopg import sql

from fitness.models.sync import SyncedRunWorkout, SyncStatus
from .connection import get_db_cursor

logger = logging.getLogger(__name__)


def _row_to_synced_run_workout(row: tuple) -> SyncedRunWorkout:
    """Convert a database row to a SyncedRunWorkout object."""
    (
        sync_id,
        run_workout_id,
        run_workout_version,
        google_event_id,
        synced_at,
        sync_status,
        error_message,
        created_at,
        updated_at,
    ) = row
    return SyncedRunWorkout(
        id=sync_id,
        run_workout_id=run_workout_id,
        run_workout_version=run_workout_version,
        google_event_id=google_event_id,
        synced_at=synced_at,
        sync_status=sync_status,
        error_message=error_message,
        created_at=created_at,
        updated_at=updated_at,
    )


def get_synced_run_workout(run_workout_id: str) -> SyncedRunWorkout | None:
    """Get sync record for a specific run workout."""
    try:
        with get_db_cursor() as cursor:
            logger.debug(f"Querying sync record for run_workout_id={run_workout_id}")
            cursor.execute(
                """
                SELECT id, run_workout_id, run_workout_version, google_event_id, synced_at,
                       sync_status, error_message, created_at, updated_at
                FROM synced_run_workouts
                WHERE run_workout_id = %s
            """,
                (run_workout_id,),
            )

            row = cursor.fetchone()
            if row is None:
                logger.debug(f"No sync record found for run_workout_id={run_workout_id}")
                return None

            synced = _row_to_synced_run_workout(row)
            logger.debug(
                f"Found sync record: run_workout_id={run_workout_id}, sync_status={synced.sync_status}, "
                f"google_event_id={synced.google_event_id}"
            )
            return synced
    except Exception as e:
        logger.exception(
            f"Database error retrieving sync record: run_workout_id={run_workout_id}, "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def create_synced_run_workout(
    run_workout_id: str,
    google_event_id: str | None,
    run_workout_version: int = 1,
    sync_status: SyncStatus = "synced",
    error_message: str | None = None,
) -> SyncedRunWorkout:
    """Create a new sync record for a run workout."""
    try:
        logger.info(
            f"Creating sync record: run_workout_id={run_workout_id}, google_event_id={google_event_id}, "
            f"sync_status={sync_status}, run_workout_version={run_workout_version}"
        )

        with get_db_cursor() as cursor:
            now = datetime.now(timezone.utc)
            cursor.execute(
                """
                INSERT INTO synced_run_workouts
                (run_workout_id, run_workout_version, google_event_id, synced_at, sync_status, error_message, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at, updated_at
            """,
                (
                    run_workout_id,
                    run_workout_version,
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
                    f"Failed to create sync record for run_workout_id={run_workout_id}"
                )
            sync_id, created_at, updated_at = result

            logger.info(
                f"Successfully created sync record: sync_id={sync_id}, run_workout_id={run_workout_id}, "
                f"google_event_id={google_event_id}, sync_status={sync_status}"
            )

            return SyncedRunWorkout(
                id=sync_id,
                run_workout_id=run_workout_id,
                run_workout_version=run_workout_version,
                google_event_id=google_event_id,
                synced_at=now,
                sync_status=sync_status,
                error_message=error_message,
                created_at=created_at,
                updated_at=updated_at,
            )
    except Exception as e:
        logger.exception(
            f"Database error creating sync record: run_workout_id={run_workout_id}, "
            f"google_event_id={google_event_id}, sync_status={sync_status}, "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def update_synced_run_workout(
    run_workout_id: str,
    run_workout_version: int | None = None,
    google_event_id: str | None = None,
    sync_status: SyncStatus | None = None,
    error_message: str | None = None,
    clear_error_message: bool = False,
) -> SyncedRunWorkout | None:
    """Update an existing sync record."""
    try:
        update_details = []
        if run_workout_version is not None:
            update_details.append(f"run_workout_version={run_workout_version}")
        if google_event_id is not None:
            update_details.append(f"google_event_id={google_event_id}")
        if sync_status is not None:
            update_details.append(f"sync_status={sync_status}")
        if error_message is not None:
            update_details.append(f"error_message={error_message[:100]}...")
        if clear_error_message:
            update_details.append("clear_error_message=True")

        logger.info(
            f"Updating sync record: run_workout_id={run_workout_id}, updates=[{', '.join(update_details)}]"
        )

        with get_db_cursor() as cursor:
            update_fields: list[sql.Composable] = []
            params: list = []

            if run_workout_version is not None:
                update_fields.append(sql.SQL("run_workout_version = %s"))
                params.append(run_workout_version)

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
                    f"No fields to update for run_workout_id={run_workout_id}, returning existing record"
                )
                return get_synced_run_workout(run_workout_id)

            update_fields.append(sql.SQL("updated_at = %s"))
            params.append(datetime.now(timezone.utc))

            params.append(run_workout_id)

            query = sql.SQL("""
                UPDATE synced_run_workouts
                SET {update_fields}
                WHERE run_workout_id = %s
                RETURNING id, run_workout_id, run_workout_version, google_event_id, synced_at,
                          sync_status, error_message, created_at, updated_at
            """).format(update_fields=sql.SQL(", ").join(update_fields))

            cursor.execute(query, params)
            row = cursor.fetchone()

            if row is None:
                logger.warning(f"No sync record found to update: run_workout_id={run_workout_id}")
                return None

            synced = _row_to_synced_run_workout(row)
            logger.info(
                f"Successfully updated sync record: run_workout_id={run_workout_id}, "
                f"new_sync_status={synced.sync_status}, google_event_id={synced.google_event_id}"
            )

            return synced
    except Exception as e:
        logger.exception(
            f"Database error updating sync record: run_workout_id={run_workout_id}, "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def delete_synced_run_workout(run_workout_id: str) -> bool:
    """Delete a sync record for a run workout (when unsyncing from calendar)."""
    try:
        logger.info(f"Deleting sync record: run_workout_id={run_workout_id}")

        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM synced_run_workouts WHERE run_workout_id = %s", (run_workout_id,))
            deleted_count = cursor.rowcount

            if deleted_count > 0:
                logger.info(
                    f"Successfully deleted sync record: run_workout_id={run_workout_id}, "
                    f"rows_deleted={deleted_count}"
                )
                return True
            else:
                logger.warning(
                    f"No sync record found to delete: run_workout_id={run_workout_id}, "
                    f"rows_deleted={deleted_count}"
                )
                return False
    except Exception as e:
        logger.exception(
            f"Database error deleting sync record: run_workout_id={run_workout_id}, "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def get_synced_run_workouts_by_ids(run_workout_ids: list[str]) -> list[SyncedRunWorkout]:
    """Get sync records for a specific set of run workout IDs."""
    if not run_workout_ids:
        return []
    try:
        logger.debug(f"Querying sync records for {len(run_workout_ids)} workout IDs")

        with get_db_cursor() as cursor:
            placeholders = sql.SQL(", ").join([sql.Placeholder()] * len(run_workout_ids))
            query = sql.SQL("""
                SELECT id, run_workout_id, run_workout_version, google_event_id, synced_at,
                       sync_status, error_message, created_at, updated_at
                FROM synced_run_workouts
                WHERE run_workout_id IN ({placeholders})
            """).format(placeholders=placeholders)
            cursor.execute(query, run_workout_ids)

            results = [_row_to_synced_run_workout(row) for row in cursor.fetchall()]

            logger.debug(f"Retrieved sync records: requested={len(run_workout_ids)}, found={len(results)}")
            return results
    except Exception as e:
        logger.exception(
            f"Database error retrieving sync records by IDs: "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def get_all_synced_run_workouts() -> list[SyncedRunWorkout]:
    """Get all sync records."""
    try:
        logger.debug("Querying all run workout sync records")

        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT id, run_workout_id, run_workout_version, google_event_id, synced_at,
                       sync_status, error_message, created_at, updated_at
                FROM synced_run_workouts
                ORDER BY synced_at DESC
            """)

            results = [_row_to_synced_run_workout(row) for row in cursor.fetchall()]

            logger.info(f"Retrieved all run workout sync records: count={len(results)}")
            return results
    except Exception as e:
        logger.exception(
            f"Database error retrieving all run workout sync records: "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def is_run_workout_synced(run_workout_id: str) -> bool:
    """Check if a run workout is currently synced to Google Calendar."""
    synced = get_synced_run_workout(run_workout_id)
    return synced is not None and synced.sync_status == "synced"


def get_failed_run_workout_syncs() -> list[SyncedRunWorkout]:
    """Get all run workouts with failed sync status for retry."""
    try:
        logger.debug("Querying failed run workout sync records")

        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT id, run_workout_id, run_workout_version, google_event_id, synced_at,
                       sync_status, error_message, created_at, updated_at
                FROM synced_run_workouts
                WHERE sync_status = 'failed'
                ORDER BY updated_at DESC
            """)

            results = [_row_to_synced_run_workout(row) for row in cursor.fetchall()]

            logger.info(f"Retrieved failed run workout sync records: count={len(results)}")
            return results
    except Exception as e:
        logger.exception(
            f"Database error retrieving failed run workout sync records: "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise
