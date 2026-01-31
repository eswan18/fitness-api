"""Database operations for lifts (weightlifting workouts) and exercise templates."""

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from .connection import get_db_cursor, get_db_connection
from fitness.models.lift import Lift, Exercise, Set, ExerciseTemplate
from fitness.models.sync import SyncStatus

logger = logging.getLogger(__name__)


# --- Lifts ---


def get_all_lifts(include_deleted: bool = False) -> list[Lift]:
    """Get all lifts from the database."""
    with get_db_cursor() as cursor:
        if include_deleted:
            cursor.execute("""
                SELECT id, title, description, start_time, end_time, exercises,
                       source, deleted_at
                FROM lifts
                ORDER BY start_time DESC
            """)
        else:
            cursor.execute("""
                SELECT id, title, description, start_time, end_time, exercises,
                       source, deleted_at
                FROM lifts
                WHERE deleted_at IS NULL
                ORDER BY start_time DESC
            """)
        rows = cursor.fetchall()
        return [_row_to_lift(row) for row in rows]


def get_lifts_in_date_range(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    include_deleted: bool = False,
) -> list[Lift]:
    """Get lifts within a date range.

    Args:
        start_date: If provided, only return lifts on or after this date.
        end_date: If provided, only return lifts before this date.
        include_deleted: If True, include soft-deleted lifts.

    Returns:
        List of lifts matching the criteria, ordered by start_time descending.
    """
    from psycopg import sql

    with get_db_cursor() as cursor:
        # Build query dynamically based on which dates are provided
        conditions: list[sql.Composable] = []
        params: list = []

        if not include_deleted:
            conditions.append(sql.SQL("deleted_at IS NULL"))

        if start_date is not None:
            conditions.append(sql.SQL("start_time >= %s"))
            params.append(start_date)

        if end_date is not None:
            conditions.append(sql.SQL("start_time < %s"))
            params.append(end_date)

        where_clause = (
            sql.SQL(" AND ").join(conditions) if conditions else sql.SQL("TRUE")
        )

        query = sql.SQL("""
            SELECT id, title, description, start_time, end_time, exercises,
                   source, deleted_at
            FROM lifts
            WHERE {where_clause}
            ORDER BY start_time DESC
        """).format(where_clause=where_clause)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [_row_to_lift(row) for row in rows]


@dataclass
class LiftWithSync:
    """A lift with its sync metadata from synced_lifts."""

    lift: Lift
    is_synced: bool
    sync_status: Optional[SyncStatus]
    synced_at: Optional[datetime]
    google_event_id: Optional[str]
    error_message: Optional[str]


_LIFT_WITH_SYNC_QUERY = """
    SELECT l.id, l.title, l.description, l.start_time, l.end_time, l.exercises,
           l.source, l.deleted_at,
           sl.sync_status, sl.synced_at, sl.google_event_id, sl.error_message
    FROM lifts l
    LEFT JOIN synced_lifts sl ON sl.lift_id = l.id
"""


def get_all_lifts_with_sync(include_deleted: bool = False) -> list[LiftWithSync]:
    """Get all lifts with sync metadata from synced_lifts."""
    from psycopg import sql

    with get_db_cursor() as cursor:
        conditions: list[sql.Composable] = []
        if not include_deleted:
            conditions.append(sql.SQL("l.deleted_at IS NULL"))

        where_clause = (
            sql.SQL("WHERE ") + sql.SQL(" AND ").join(conditions)
            if conditions
            else sql.SQL("")
        )
        query = sql.SQL(
            _LIFT_WITH_SYNC_QUERY
            + """
            {where_clause}
            ORDER BY l.start_time DESC
        """
        ).format(where_clause=where_clause)
        cursor.execute(query)
        return [_row_to_lift_with_sync(row) for row in cursor.fetchall()]


def get_lifts_in_date_range_with_sync(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    include_deleted: bool = False,
) -> list[LiftWithSync]:
    """Get lifts with sync metadata within a date range."""
    from psycopg import sql

    with get_db_cursor() as cursor:
        conditions: list[sql.Composable] = []
        params: list = []

        if not include_deleted:
            conditions.append(sql.SQL("l.deleted_at IS NULL"))
        if start_date is not None:
            conditions.append(sql.SQL("l.start_time >= %s"))
            params.append(start_date)
        if end_date is not None:
            conditions.append(sql.SQL("l.start_time < %s"))
            params.append(end_date)

        where_clause = (
            sql.SQL(" AND ").join(conditions) if conditions else sql.SQL("TRUE")
        )
        query = sql.SQL(
            _LIFT_WITH_SYNC_QUERY
            + """
            WHERE {where_clause}
            ORDER BY l.start_time DESC
        """
        ).format(where_clause=where_clause)
        cursor.execute(query, params)
        return [_row_to_lift_with_sync(row) for row in cursor.fetchall()]


def get_lift_by_id(lift_id: str) -> Optional[Lift]:
    """Get a single lift by ID."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, title, description, start_time, end_time, exercises,
                   source, deleted_at
            FROM lifts
            WHERE id = %s AND deleted_at IS NULL
            """,
            (lift_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_lift(row)


def get_lift_count(include_deleted: bool = False) -> int:
    """Get total count of lifts."""
    with get_db_cursor() as cursor:
        if include_deleted:
            cursor.execute("SELECT COUNT(*) FROM lifts")
        else:
            cursor.execute("SELECT COUNT(*) FROM lifts WHERE deleted_at IS NULL")
        result = cursor.fetchone()
        return result[0] if result else 0


def get_existing_lift_ids() -> set[str]:
    """Get the set of all existing lift IDs in the database."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id FROM lifts")
        return {row[0] for row in cursor.fetchall()}


def bulk_create_lifts(lifts: list[Lift]) -> int:
    """Bulk insert new lifts. Returns count of inserted rows.

    Skips lifts that already exist (by ID) to preserve local edits.

    Args:
        lifts: List of Lift objects to insert (already converted from provider format)
    """
    if not lifts:
        return 0

    logger.info(f"Bulk inserting {len(lifts)} lifts")

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                count = 0
                for lift in lifts:
                    exercises_json = json.dumps(
                        [_generic_exercise_to_dict(e) for e in lift.exercises]
                    )
                    cursor.execute(
                        """
                        INSERT INTO lifts (
                            id, title, source, description, start_time, end_time,
                            exercises, total_volume_kg, total_sets
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (
                            lift.id,
                            lift.title,
                            lift.source,
                            lift.description,
                            lift.start_time,
                            lift.end_time,
                            exercises_json,
                            lift.total_volume(),
                            lift.total_sets(),
                        ),
                    )
                    count += cursor.rowcount  # Only count actually inserted rows

    logger.info(f"Successfully inserted {count} new lifts")
    return count


# --- Exercise Templates ---


def get_existing_exercise_template_ids() -> set[str]:
    """Get the set of all cached exercise template IDs."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id FROM exercise_templates")
        return {row[0] for row in cursor.fetchall()}


def get_all_exercise_templates() -> list[ExerciseTemplate]:
    """Get all cached exercise templates."""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, title, type, primary_muscle_group, secondary_muscle_groups,
                   source, is_custom
            FROM exercise_templates
            ORDER BY title
        """)
        rows = cursor.fetchall()
        return [_row_to_exercise_template(row) for row in rows]


def get_exercise_template_by_id(template_id: str) -> Optional[ExerciseTemplate]:
    """Get a single exercise template by ID."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, title, type, primary_muscle_group, secondary_muscle_groups,
                   source, is_custom
            FROM exercise_templates
            WHERE id = %s
            """,
            (template_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_exercise_template(row)


def bulk_upsert_exercise_templates(templates: list[ExerciseTemplate]) -> int:
    """Bulk upsert exercise templates. Returns count of rows affected.

    Uses ON CONFLICT DO UPDATE, so rowcount reflects actual database operations.

    Args:
        templates: List of ExerciseTemplate objects to upsert (already converted from provider format)

    Returns:
        Number of rows actually inserted or updated in the database.
    """
    if not templates:
        return 0

    logger.info(f"Bulk upserting {len(templates)} exercise templates")

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                count = 0
                for template in templates:
                    cursor.execute(
                        """
                        INSERT INTO exercise_templates (
                            id, title, source, type, primary_muscle_group,
                            secondary_muscle_groups, is_custom
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            title = EXCLUDED.title,
                            type = EXCLUDED.type,
                            primary_muscle_group = EXCLUDED.primary_muscle_group,
                            secondary_muscle_groups = EXCLUDED.secondary_muscle_groups,
                            is_custom = EXCLUDED.is_custom,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            template.id,
                            template.title,
                            template.source,
                            template.type,
                            template.primary_muscle_group,
                            template.secondary_muscle_groups,
                            template.is_custom,
                        ),
                    )
                    count += cursor.rowcount

    logger.info(f"Successfully upserted {count} exercise templates")
    return count


# --- Helper functions ---


def _row_to_lift(row: tuple) -> Lift:
    """Convert a database row to a generic Lift model."""
    (
        id_,
        title,
        description,
        start_time,
        end_time,
        exercises_json,
        source,
        deleted_at,
    ) = row

    # Parse exercises from JSON
    exercises_data = (
        exercises_json
        if isinstance(exercises_json, list)
        else json.loads(exercises_json or "[]")
    )
    exercises = [_dict_to_exercise(e) for e in exercises_data]

    return Lift(
        id=id_,
        title=title,
        description=description,
        start_time=start_time,
        end_time=end_time,
        source=source,
        exercises=exercises,
        deleted_at=deleted_at,
    )


def _row_to_lift_with_sync(row: tuple) -> LiftWithSync:
    """Convert a database row (with sync columns) to a LiftWithSync."""
    (
        id_,
        title,
        description,
        start_time,
        end_time,
        exercises_json,
        source,
        deleted_at,
        sync_status,
        synced_at,
        google_event_id,
        error_message,
    ) = row

    exercises_data = (
        exercises_json
        if isinstance(exercises_json, list)
        else json.loads(exercises_json or "[]")
    )
    exercises = [_dict_to_exercise(e) for e in exercises_data]

    lift = Lift(
        id=id_,
        title=title,
        description=description,
        start_time=start_time,
        end_time=end_time,
        source=source,
        exercises=exercises,
        deleted_at=deleted_at,
    )
    return LiftWithSync(
        lift=lift,
        is_synced=(sync_status == "synced"),
        sync_status=sync_status,
        synced_at=synced_at,
        google_event_id=google_event_id or None,
        error_message=error_message,
    )


def _row_to_exercise_template(row: tuple) -> ExerciseTemplate:
    """Convert a database row to a generic ExerciseTemplate model."""
    id_, title, type_, primary_muscle, secondary_muscles, source, is_custom = row
    return ExerciseTemplate(
        id=id_,
        title=title,
        type=type_ or "",
        primary_muscle_group=primary_muscle,
        secondary_muscle_groups=secondary_muscles or [],
        source=source,
        is_custom=is_custom or False,
    )


def _generic_exercise_to_dict(exercise: Exercise) -> dict:
    """Convert a generic Exercise to a dictionary for JSON serialization."""
    return {
        "index": exercise.index,
        "title": exercise.title,
        "notes": exercise.notes,
        "exercise_template_id": exercise.exercise_template_id,
        "superset_id": exercise.superset_id,
        "sets": [_generic_set_to_dict(s) for s in exercise.sets],
    }


def _generic_set_to_dict(set_: Set) -> dict:
    """Convert a generic Set to a dictionary for JSON serialization."""
    return {
        "index": set_.index,
        "set_type": set_.set_type,
        "weight_kg": set_.weight_kg,
        "reps": set_.reps,
        "distance_meters": set_.distance_meters,
        "duration_seconds": set_.duration_seconds,
        "rpe": set_.rpe,
    }


def _dict_to_exercise(data: dict) -> Exercise:
    """Convert a dictionary to a generic Exercise model."""
    return Exercise(
        index=data.get("index", 0),
        title=data.get("title", ""),
        notes=data.get("notes"),
        exercise_template_id=data.get("exercise_template_id"),
        superset_id=data.get("superset_id"),
        sets=[_dict_to_set(s) for s in data.get("sets", [])],
    )


def _dict_to_set(data: dict) -> Set:
    """Convert a dictionary to a generic Set model."""
    return Set(
        index=data.get("index", 0),
        set_type=data.get("set_type"),
        weight_kg=data.get("weight_kg"),
        reps=data.get("reps"),
        distance_meters=data.get("distance_meters"),
        duration_seconds=data.get("duration_seconds"),
        rpe=data.get("rpe"),
    )
