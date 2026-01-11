import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, cast
from dataclasses import dataclass

from psycopg import sql

from fitness.models import Run
from fitness.models.run import RunType, RunSource
from .connection import get_db_cursor, get_db_connection

logger = logging.getLogger(__name__)


@dataclass
class RunHistoryRecord:
    """Represents a historical version of a run."""

    history_id: int
    run_id: str
    version_number: int
    change_type: str
    datetime_utc: datetime
    type: str
    distance: float
    duration: float
    source: str
    avg_heart_rate: Optional[float]
    shoe_id: Optional[str]
    changed_at: datetime
    changed_by: Optional[str]
    change_reason: Optional[str]

    def to_run(self) -> Run:
        """Convert history record back to a Run object."""
        # Note: We need to handle the fact that Run model may not have all the history fields
        # This is a simplified conversion - you may need to adjust based on your Run model
        from fitness.models.run import Run

        return Run(
            id=self.run_id,
            datetime_utc=self.datetime_utc,
            type=cast(RunType, self.type),
            distance=self.distance,
            duration=self.duration,
            source=cast(RunSource, self.source),
            avg_heart_rate=self.avg_heart_rate,
            shoe_id=self.shoe_id,
        )


def insert_run_history(
    run: Run,
    version_number: int,
    change_type: str,
    changed_by: Optional[str] = None,
    change_reason: Optional[str] = None,
) -> int:
    """Insert a run into the history table and return the history_id."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO runs_history (
                run_id, version_number, change_type, datetime_utc, type, 
                distance, duration, source, avg_heart_rate, shoe_id,
                changed_by, change_reason
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING history_id
        """,
            (
                run.id,
                version_number,
                change_type,
                run.datetime_utc,
                run.type,
                run.distance,
                run.duration,
                run.source,
                run.avg_heart_rate,
                run.shoe_id,
                changed_by,
                change_reason,
            ),
        )

        result = cursor.fetchone()
        history_id = result[0] if result else None

        if not history_id:
            raise Exception("Failed to insert run history record")

        logger.info(
            f"Inserted run history record {history_id} for run {run.id} (version {version_number})"
        )
        return history_id


def get_run_history(run_id: str, limit: Optional[int] = None) -> List[RunHistoryRecord]:
    """Get the edit history for a specific run, ordered by version (newest first)."""
    with get_db_cursor() as cursor:
        query = """
            SELECT history_id, run_id, version_number, change_type, datetime_utc, 
                   type, distance, duration, source, avg_heart_rate, shoe_id,
                   changed_at, changed_by, change_reason
            FROM runs_history 
            WHERE run_id = %s 
            ORDER BY version_number DESC
        """
        params = [run_id]

        if limit:
            query += " LIMIT %s"
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        history_records = []
        for row in rows:
            history_records.append(
                RunHistoryRecord(
                    history_id=row[0],
                    run_id=row[1],
                    version_number=row[2],
                    change_type=row[3],
                    datetime_utc=row[4],
                    type=row[5],
                    distance=row[6],
                    duration=row[7],
                    source=row[8],
                    avg_heart_rate=row[9],
                    shoe_id=row[10],
                    changed_at=row[11],
                    changed_by=row[12],
                    change_reason=row[13],
                )
            )

        logger.debug(
            f"Retrieved {len(history_records)} history records for run {run_id}"
        )
        return history_records


def get_run_version(run_id: str, version_number: int) -> Optional[RunHistoryRecord]:
    """Get a specific version of a run from history."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT history_id, run_id, version_number, change_type, datetime_utc, 
                   type, distance, duration, source, avg_heart_rate, shoe_id,
                   changed_at, changed_by, change_reason
            FROM runs_history 
            WHERE run_id = %s AND version_number = %s
        """,
            (run_id, version_number),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return RunHistoryRecord(
            history_id=row[0],
            run_id=row[1],
            version_number=row[2],
            change_type=row[3],
            datetime_utc=row[4],
            type=row[5],
            distance=row[6],
            duration=row[7],
            source=row[8],
            avg_heart_rate=row[9],
            shoe_id=row[10],
            changed_at=row[11],
            changed_by=row[12],
            change_reason=row[13],
        )


def get_latest_version_number(run_id: str) -> int:
    """Get the latest version number for a run."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT COALESCE(MAX(version_number), 0) 
            FROM runs_history 
            WHERE run_id = %s
        """,
            (run_id,),
        )

        result = cursor.fetchone()
        return result[0] if result else 0


def update_run_with_history(
    run_id: str,
    updates: Dict[str, Any],
    changed_by: str,
    change_reason: Optional[str] = None,
) -> None:
    """
    Update a run and record the change in history.
    This function performs both operations in a single transaction.
    """
    from .runs import get_run_by_id

    # Validate allowed fields BEFORE any database operations
    allowed_fields = {
        "distance",
        "duration",
        "avg_heart_rate",
        "shoe_id",
        "type",
        "datetime_utc",
        # Note: We don't allow editing 'source' as it maintains data lineage
    }

    for field, value in updates.items():
        if field not in allowed_fields:
            raise ValueError(f"Field '{field}' is not allowed to be updated")

    with get_db_connection() as conn:
        with conn.transaction():
            # Get the current run data
            current_run = get_run_by_id(run_id)
            if not current_run:
                raise ValueError(f"Run {run_id} not found")

            # Get the next version number
            with conn.cursor() as cursor:
                cursor.execute("SELECT version FROM runs WHERE id = %s", (run_id,))
                result = cursor.fetchone()
                current_version = result[0] if result else 1
                new_version = current_version + 1

                # Build the UPDATE query dynamically based on provided updates
                set_clauses: list[sql.Composable] = []
                params: list[Any] = []

                for field, value in updates.items():
                    set_clauses.append(sql.SQL("{} = %s").format(sql.Identifier(field)))
                    params.append(value)

                # Add metadata updates
                set_clauses.extend(
                    [
                        sql.SQL("last_edited_at = CURRENT_TIMESTAMP"),
                        sql.SQL("last_edited_by = %s"),
                        sql.SQL("version = %s"),
                    ]
                )
                params.extend([changed_by, new_version])

                # Add the WHERE clause parameter
                params.append(run_id)

                # Execute the update of the current run row
                update_query = sql.SQL("""
                    UPDATE runs
                    SET {set_clauses}
                    WHERE id = %s
                """).format(set_clauses=sql.SQL(", ").join(set_clauses))

                cursor.execute(update_query, params)

                if cursor.rowcount == 0:
                    raise ValueError(f"No run found with ID {run_id}")

                # Construct the updated run snapshot to record in history
                from fitness.models.run import Run as RunModel

                updated_run = RunModel(
                    id=current_run.id,
                    datetime_utc=updates.get("datetime_utc", current_run.datetime_utc),
                    type=updates.get("type", current_run.type),
                    distance=updates.get("distance", current_run.distance),
                    duration=updates.get("duration", current_run.duration),
                    source=current_run.source,
                    avg_heart_rate=updates.get(
                        "avg_heart_rate", current_run.avg_heart_rate
                    ),
                    shoe_id=updates.get("shoe_id", current_run.shoe_id),
                    deleted_at=current_run.deleted_at,
                )

                # Insert the NEW state into history with the incremented version
                insert_run_history_with_cursor(
                    cursor,
                    updated_run,
                    new_version,
                    "edit",
                    changed_by,
                    change_reason,
                )

                logger.info(
                    f"Updated run {run_id} to version {new_version} by {changed_by}"
                )


def insert_run_history_with_cursor(
    cursor,
    run: Run,
    version_number: int,
    change_type: str,
    changed_by: Optional[str] = None,
    change_reason: Optional[str] = None,
) -> int:
    """Insert a run into the history table using an existing cursor (for transactions)."""
    cursor.execute(
        """
        INSERT INTO runs_history (
            run_id, version_number, change_type, datetime_utc, type, 
            distance, duration, source, avg_heart_rate, shoe_id,
            changed_by, change_reason
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING history_id
    """,
        (
            run.id,
            version_number,
            change_type,
            run.datetime_utc,
            run.type,
            run.distance,
            run.duration,
            run.source,
            run.avg_heart_rate,
            run.shoe_id,
            changed_by,
            change_reason,
        ),
    )

    result = cursor.fetchone()
    history_id = result[0] if result else None

    if not history_id:
        raise Exception("Failed to insert run history record")

    return history_id
