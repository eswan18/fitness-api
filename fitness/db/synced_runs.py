"""Database access functions for synced runs (Google Calendar sync tracking)."""

import logging
from datetime import datetime, timezone

from psycopg import sql

from fitness.models.sync import SyncedRun, SyncStatus
from .connection import get_db_cursor

logger = logging.getLogger(__name__)


def _row_to_synced_run(row: tuple) -> SyncedRun:
    """Convert a database row to a SyncedRun object."""
    (
        sync_id,
        run_id,
        run_version,
        google_event_id,
        synced_at,
        sync_status,
        error_message,
        created_at,
        updated_at,
    ) = row
    return SyncedRun(
        id=sync_id,
        run_id=run_id,
        run_version=run_version,
        google_event_id=google_event_id,
        synced_at=synced_at,
        sync_status=sync_status,
        error_message=error_message,
        created_at=created_at,
        updated_at=updated_at,
    )


def get_synced_run(run_id: str) -> SyncedRun | None:
    """Get sync record for a specific run."""
    try:
        with get_db_cursor() as cursor:
            logger.debug(f"Querying sync record for run_id={run_id}")
            cursor.execute(
                """
                SELECT id, run_id, run_version, google_event_id, synced_at,
                       sync_status, error_message, created_at, updated_at
                FROM synced_runs
                WHERE run_id = %s
            """,
                (run_id,),
            )

            row = cursor.fetchone()
            if row is None:
                logger.debug(f"No sync record found for run_id={run_id}")
                return None

            synced_run = _row_to_synced_run(row)
            logger.debug(
                f"Found sync record: run_id={run_id}, sync_status={synced_run.sync_status}, "
                f"google_event_id={synced_run.google_event_id}"
            )
            return synced_run
    except Exception as e:
        logger.exception(
            f"Database error retrieving sync record: run_id={run_id}, "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def create_synced_run(
    run_id: str,
    google_event_id: str,
    run_version: int = 1,
    sync_status: SyncStatus = "synced",
    error_message: str | None = None,
) -> SyncedRun:
    """Create a new sync record for a run."""
    try:
        logger.info(
            f"Creating sync record: run_id={run_id}, google_event_id={google_event_id}, "
            f"sync_status={sync_status}, run_version={run_version}"
        )

        with get_db_cursor() as cursor:
            now = datetime.now(timezone.utc)
            cursor.execute(
                """
                INSERT INTO synced_runs
                (run_id, run_version, google_event_id, synced_at, sync_status, error_message, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at, updated_at
            """,
                (
                    run_id,
                    run_version,
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
                raise RuntimeError(f"Failed to create sync record for run_id={run_id}")
            sync_id, created_at, updated_at = result

            logger.info(
                f"Successfully created sync record: sync_id={sync_id}, run_id={run_id}, "
                f"google_event_id={google_event_id}, sync_status={sync_status}"
            )

            return SyncedRun(
                id=sync_id,
                run_id=run_id,
                run_version=run_version,
                google_event_id=google_event_id,
                synced_at=now,
                sync_status=sync_status,
                error_message=error_message,
                created_at=created_at,
                updated_at=updated_at,
            )
    except Exception as e:
        logger.exception(
            f"Database error creating sync record: run_id={run_id}, "
            f"google_event_id={google_event_id}, sync_status={sync_status}, "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def update_synced_run(
    run_id: str,
    run_version: int | None = None,
    google_event_id: str | None = None,
    sync_status: SyncStatus | None = None,
    error_message: str | None = None,
    clear_error_message: bool = False,
) -> SyncedRun | None:
    """Update an existing sync record."""
    try:
        # Build update details for logging
        update_details = []
        if run_version is not None:
            update_details.append(f"run_version={run_version}")
        if google_event_id is not None:
            update_details.append(f"google_event_id={google_event_id}")
        if sync_status is not None:
            update_details.append(f"sync_status={sync_status}")
        if error_message is not None:
            update_details.append(f"error_message={error_message[:100]}...")
        if clear_error_message:
            update_details.append("clear_error_message=True")

        logger.info(
            f"Updating sync record: run_id={run_id}, updates=[{', '.join(update_details)}]"
        )

        with get_db_cursor() as cursor:
            # Build dynamic UPDATE query based on provided fields
            update_fields: list[sql.Composable] = []
            params: list = []

            if run_version is not None:
                update_fields.append(sql.SQL("run_version = %s"))
                params.append(run_version)

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
                # No parameter needed for NULL

            if not update_fields:
                # Nothing to update
                logger.debug(
                    f"No fields to update for run_id={run_id}, returning existing record"
                )
                return get_synced_run(run_id)

            # Always update the updated_at timestamp
            update_fields.append(sql.SQL("updated_at = %s"))
            params.append(datetime.now(timezone.utc))

            # Add run_id for WHERE clause
            params.append(run_id)

            query = sql.SQL("""
                UPDATE synced_runs
                SET {update_fields}
                WHERE run_id = %s
                RETURNING id, run_id, run_version, google_event_id, synced_at,
                          sync_status, error_message, created_at, updated_at
            """).format(update_fields=sql.SQL(", ").join(update_fields))

            cursor.execute(query, params)
            row = cursor.fetchone()

            if row is None:
                logger.warning(f"No sync record found to update: run_id={run_id}")
                return None

            synced_run = _row_to_synced_run(row)
            logger.info(
                f"Successfully updated sync record: run_id={run_id}, "
                f"new_sync_status={synced_run.sync_status}, google_event_id={synced_run.google_event_id}"
            )

            return synced_run
    except Exception as e:
        logger.exception(
            f"Database error updating sync record: run_id={run_id}, "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def delete_synced_run(run_id: str) -> bool:
    """Delete a sync record for a run (when unsyncing from calendar)."""
    try:
        logger.info(f"Deleting sync record: run_id={run_id}")

        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM synced_runs WHERE run_id = %s", (run_id,))
            deleted_count = cursor.rowcount

            if deleted_count > 0:
                logger.info(
                    f"Successfully deleted sync record: run_id={run_id}, "
                    f"rows_deleted={deleted_count}"
                )
                return True
            else:
                logger.warning(
                    f"No sync record found to delete: run_id={run_id}, "
                    f"rows_deleted={deleted_count}"
                )
                return False
    except Exception as e:
        logger.exception(
            f"Database error deleting sync record: run_id={run_id}, "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def get_all_synced_runs() -> list[SyncedRun]:
    """Get all sync records."""
    try:
        logger.debug("Querying all sync records")

        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT id, run_id, run_version, google_event_id, synced_at,
                       sync_status, error_message, created_at, updated_at
                FROM synced_runs
                ORDER BY synced_at DESC
            """)

            results = [_row_to_synced_run(row) for row in cursor.fetchall()]

            logger.info(f"Retrieved all sync records: count={len(results)}")
            return results
    except Exception as e:
        logger.exception(
            f"Database error retrieving all sync records: "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise


def is_run_synced(run_id: str) -> bool:
    """Check if a run is currently synced to Google Calendar."""
    synced_run = get_synced_run(run_id)
    return synced_run is not None and synced_run.sync_status == "synced"


def get_failed_syncs() -> list[SyncedRun]:
    """Get all runs with failed sync status for retry."""
    try:
        logger.debug("Querying failed sync records")

        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT id, run_id, run_version, google_event_id, synced_at,
                       sync_status, error_message, created_at, updated_at
                FROM synced_runs
                WHERE sync_status = 'failed'
                ORDER BY updated_at DESC
            """)

            results = [_row_to_synced_run(row) for row in cursor.fetchall()]

            logger.info(f"Retrieved failed sync records: count={len(results)}")
            return results
    except Exception as e:
        logger.exception(
            f"Database error retrieving failed sync records: "
            f"exception_type={type(e).__name__}, error={e}"
        )
        raise
