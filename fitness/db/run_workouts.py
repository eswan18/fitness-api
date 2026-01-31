"""Database operations for run workouts."""

import logging
import uuid
from typing import Optional

from .connection import get_db_cursor, get_db_connection
from fitness.models.run_workout import RunWorkout

logger = logging.getLogger(__name__)


def create_run_workout(
    title: str,
    run_ids: list[str],
    notes: Optional[str] = None,
) -> RunWorkout:
    """Create a new run workout and assign runs to it.

    Args:
        title: The workout title.
        run_ids: List of run IDs to include (must be >= 2).
        notes: Optional notes.

    Returns:
        The created RunWorkout.

    Raises:
        ValueError: If validation fails (< 2 runs, nonexistent runs, runs already in a workout).
    """
    if len(run_ids) < 2:
        raise ValueError("A run workout must contain at least 2 runs")

    workout_id = f"rw_{uuid.uuid4()}"

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                # Validate runs exist and aren't in another workout
                _validate_run_ids(cursor, run_ids)

                # Insert the workout
                cursor.execute(
                    """
                    INSERT INTO run_workouts (id, title, notes)
                    VALUES (%s, %s, %s)
                    RETURNING id, title, notes, created_at, updated_at, deleted_at
                    """,
                    (workout_id, title, notes),
                )
                row = cursor.fetchone()

                # Assign runs to the workout
                _assign_runs_to_workout(cursor, workout_id, run_ids)

                return _row_to_run_workout(row)


def get_run_workout_by_id(
    workout_id: str, include_deleted: bool = False
) -> Optional[RunWorkout]:
    """Get a single run workout by ID."""
    with get_db_cursor() as cursor:
        if include_deleted:
            cursor.execute(
                """
                SELECT id, title, notes, created_at, updated_at, deleted_at
                FROM run_workouts WHERE id = %s
                """,
                (workout_id,),
            )
        else:
            cursor.execute(
                """
                SELECT id, title, notes, created_at, updated_at, deleted_at
                FROM run_workouts WHERE id = %s AND deleted_at IS NULL
                """,
                (workout_id,),
            )
        row = cursor.fetchone()
        return _row_to_run_workout(row) if row else None


def get_run_workouts_by_ids(workout_ids: list[str]) -> dict[str, RunWorkout]:
    """Get multiple run workouts by ID (non-deleted only). Returns a dict keyed by ID."""
    if not workout_ids:
        return {}
    from psycopg import sql as psql

    with get_db_cursor() as cursor:
        placeholders = psql.SQL(", ").join(psql.Placeholder() * len(workout_ids))
        cursor.execute(
            psql.SQL("""
                SELECT id, title, notes, created_at, updated_at, deleted_at
                FROM run_workouts
                WHERE id IN ({}) AND deleted_at IS NULL
            """).format(placeholders),
            workout_ids,
        )
        return {row[0]: _row_to_run_workout(row) for row in cursor.fetchall()}


def get_all_run_workouts(include_deleted: bool = False) -> list[RunWorkout]:
    """Get all run workouts."""
    with get_db_cursor() as cursor:
        if include_deleted:
            cursor.execute("""
                SELECT id, title, notes, created_at, updated_at, deleted_at
                FROM run_workouts
                ORDER BY created_at DESC
            """)
        else:
            cursor.execute("""
                SELECT id, title, notes, created_at, updated_at, deleted_at
                FROM run_workouts
                WHERE deleted_at IS NULL
                ORDER BY created_at DESC
            """)
        return [_row_to_run_workout(row) for row in cursor.fetchall()]


def update_run_workout(
    workout_id: str,
    title: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[RunWorkout]:
    """Update a run workout's title and/or notes. Returns None if not found."""
    from psycopg import sql as psql

    update_parts: list[psql.Composable] = []
    params: list = []
    if title is not None:
        update_parts.append(psql.SQL("title = %s"))
        params.append(title)
    if notes is not None:
        update_parts.append(psql.SQL("notes = %s"))
        params.append(notes)
    if not update_parts:
        return get_run_workout_by_id(workout_id)

    update_parts.append(psql.SQL("updated_at = CURRENT_TIMESTAMP"))
    params.append(workout_id)

    with get_db_cursor() as cursor:
        query = psql.SQL("""
            UPDATE run_workouts
            SET {updates}
            WHERE id = %s AND deleted_at IS NULL
            RETURNING id, title, notes, created_at, updated_at, deleted_at
        """).format(updates=psql.SQL(", ").join(update_parts))
        cursor.execute(query, params)
        row = cursor.fetchone()
        return _row_to_run_workout(row) if row else None


def set_run_workout_runs(workout_id: str, run_ids: list[str]) -> None:
    """Replace the runs in a workout.

    Clears existing run associations and sets the new ones.

    Raises:
        ValueError: If validation fails.
    """
    if len(run_ids) < 2:
        raise ValueError("A run workout must contain at least 2 runs")

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                # Validate the workout exists
                cursor.execute(
                    "SELECT id FROM run_workouts WHERE id = %s AND deleted_at IS NULL",
                    (workout_id,),
                )
                if cursor.fetchone() is None:
                    raise ValueError(f"Run workout {workout_id} not found")

                # Validate new run IDs (exclude runs currently in THIS workout)
                _validate_run_ids(cursor, run_ids, exclude_workout_id=workout_id)

                # Clear existing associations
                cursor.execute(
                    "UPDATE runs SET run_workout_id = NULL WHERE run_workout_id = %s",
                    (workout_id,),
                )

                # Set new associations
                _assign_runs_to_workout(cursor, workout_id, run_ids)

                # Update timestamp
                cursor.execute(
                    "UPDATE run_workouts SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (workout_id,),
                )


def delete_run_workout(workout_id: str) -> bool:
    """Soft-delete a run workout and unlink its runs. Returns True if found."""
    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                # Unlink runs
                cursor.execute(
                    "UPDATE runs SET run_workout_id = NULL WHERE run_workout_id = %s",
                    (workout_id,),
                )
                # Soft delete
                cursor.execute(
                    """
                    UPDATE run_workouts
                    SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND deleted_at IS NULL
                    """,
                    (workout_id,),
                )
                return cursor.rowcount > 0


def get_run_ids_for_workout(workout_id: str) -> list[str]:
    """Get the run IDs belonging to a workout, ordered by datetime."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id FROM runs
            WHERE run_workout_id = %s AND deleted_at IS NULL
            ORDER BY datetime_utc
            """,
            (workout_id,),
        )
        return [row[0] for row in cursor.fetchall()]


# --- Helpers ---


def _validate_run_ids(
    cursor,
    run_ids: list[str],
    exclude_workout_id: Optional[str] = None,
) -> None:
    """Validate that all run IDs exist, aren't deleted, and aren't in another workout.

    Args:
        cursor: Active DB cursor.
        run_ids: IDs to validate.
        exclude_workout_id: If set, runs currently in this workout are allowed.

    Raises:
        ValueError: If any validation fails.
    """
    # Check for duplicates
    if len(set(run_ids)) != len(run_ids):
        raise ValueError("Duplicate run IDs provided")

    from psycopg import sql

    placeholders = sql.SQL(",").join(sql.Placeholder() * len(run_ids))
    cursor.execute(
        sql.SQL(
            "SELECT id, deleted_at, run_workout_id FROM runs WHERE id IN ({placeholders})"
        ).format(placeholders=placeholders),
        run_ids,
    )
    found = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

    # Check all exist
    missing = set(run_ids) - set(found.keys())
    if missing:
        raise ValueError(f"Runs not found: {', '.join(sorted(missing))}")

    # Check none are deleted
    deleted = [rid for rid, (del_at, _) in found.items() if del_at is not None]
    if deleted:
        raise ValueError(f"Runs are deleted: {', '.join(sorted(deleted))}")

    # Check none are in another workout
    in_other = [
        rid
        for rid, (_, wid) in found.items()
        if wid is not None and wid != exclude_workout_id
    ]
    if in_other:
        raise ValueError(
            f"Runs already in another workout: {', '.join(sorted(in_other))}"
        )


def _assign_runs_to_workout(cursor, workout_id: str, run_ids: list[str]) -> None:
    """Set run_workout_id on the given runs."""
    from psycopg import sql

    placeholders = sql.SQL(",").join(sql.Placeholder() * len(run_ids))
    cursor.execute(
        sql.SQL(
            "UPDATE runs SET run_workout_id = %s WHERE id IN ({placeholders})"
        ).format(placeholders=placeholders),
        [workout_id] + run_ids,
    )


def _row_to_run_workout(row) -> RunWorkout:
    """Convert a database row to a RunWorkout."""
    id_, title, notes, created_at, updated_at, deleted_at = row
    return RunWorkout(
        id=id_,
        title=title,
        notes=notes,
        created_at=created_at,
        updated_at=updated_at,
        deleted_at=deleted_at,
    )
