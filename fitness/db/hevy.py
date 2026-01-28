"""Database operations for Hevy workouts and exercise templates."""

import json
import logging
from datetime import date
from typing import Optional

from .connection import get_db_cursor, get_db_connection
from fitness.integrations.hevy.models import (
    HevyWorkout,
    HevyExerciseTemplate,
    HevyExercise,
    HevySet,
)

logger = logging.getLogger(__name__)


# --- Hevy Workouts ---


def get_all_hevy_workouts(include_deleted: bool = False) -> list[HevyWorkout]:
    """Get all Hevy workouts from the database."""
    with get_db_cursor() as cursor:
        if include_deleted:
            cursor.execute("""
                SELECT id, title, description, start_time, end_time, exercises,
                       total_volume_kg, total_sets, hevy_created_at, hevy_updated_at
                FROM hevy_workouts
                ORDER BY start_time DESC
            """)
        else:
            cursor.execute("""
                SELECT id, title, description, start_time, end_time, exercises,
                       total_volume_kg, total_sets, hevy_created_at, hevy_updated_at
                FROM hevy_workouts
                WHERE deleted_at IS NULL
                ORDER BY start_time DESC
            """)
        rows = cursor.fetchall()
        return [_row_to_hevy_workout(row) for row in rows]


def get_hevy_workouts_in_date_range(
    start_date: date,
    end_date: date,
    include_deleted: bool = False,
) -> list[HevyWorkout]:
    """Get Hevy workouts within a date range."""
    with get_db_cursor() as cursor:
        if include_deleted:
            cursor.execute(
                """
                SELECT id, title, description, start_time, end_time, exercises,
                       total_volume_kg, total_sets, hevy_created_at, hevy_updated_at
                FROM hevy_workouts
                WHERE start_time >= %s AND start_time < %s
                ORDER BY start_time DESC
                """,
                (start_date, end_date),
            )
        else:
            cursor.execute(
                """
                SELECT id, title, description, start_time, end_time, exercises,
                       total_volume_kg, total_sets, hevy_created_at, hevy_updated_at
                FROM hevy_workouts
                WHERE start_time >= %s AND start_time < %s
                  AND deleted_at IS NULL
                ORDER BY start_time DESC
                """,
                (start_date, end_date),
            )
        rows = cursor.fetchall()
        return [_row_to_hevy_workout(row) for row in rows]


def get_hevy_workout_by_id(workout_id: str) -> Optional[HevyWorkout]:
    """Get a single Hevy workout by ID."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, title, description, start_time, end_time, exercises,
                   total_volume_kg, total_sets, hevy_created_at, hevy_updated_at
            FROM hevy_workouts
            WHERE id = %s AND deleted_at IS NULL
            """,
            (workout_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_hevy_workout(row)


def get_hevy_workout_count(include_deleted: bool = False) -> int:
    """Get total count of Hevy workouts."""
    with get_db_cursor() as cursor:
        if include_deleted:
            cursor.execute("SELECT COUNT(*) FROM hevy_workouts")
        else:
            cursor.execute("SELECT COUNT(*) FROM hevy_workouts WHERE deleted_at IS NULL")
        result = cursor.fetchone()
        return result[0] if result else 0


def get_existing_hevy_workout_ids() -> set[str]:
    """Get the set of all existing Hevy workout IDs in the database."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id FROM hevy_workouts")
        return {row[0] for row in cursor.fetchall()}


def bulk_create_hevy_workouts(workouts: list[HevyWorkout]) -> int:
    """Bulk insert new Hevy workouts. Returns count of inserted rows.

    Skips workouts that already exist (by ID) to preserve local edits.
    """
    if not workouts:
        return 0

    logger.info(f"Bulk inserting {len(workouts)} Hevy workouts")

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                count = 0
                for workout in workouts:
                    exercises_json = json.dumps(
                        [_exercise_to_dict(e) for e in workout.exercises]
                    )
                    cursor.execute(
                        """
                        INSERT INTO hevy_workouts (
                            id, title, description, start_time, end_time, exercises,
                            total_volume_kg, total_sets, hevy_created_at, hevy_updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (
                            workout.id,
                            workout.title,
                            workout.description,
                            workout.start_time,
                            workout.end_time,
                            exercises_json,
                            workout.total_volume(),
                            workout.total_sets(),
                            workout.created_at,
                            workout.updated_at,
                        ),
                    )
                    count += cursor.rowcount  # Only count actually inserted rows

    logger.info(f"Successfully inserted {count} new Hevy workouts")
    return count


# --- Hevy Exercise Templates ---


def get_existing_exercise_template_ids() -> set[str]:
    """Get the set of all cached exercise template IDs."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id FROM hevy_exercise_templates")
        return {row[0] for row in cursor.fetchall()}


def get_all_exercise_templates() -> list[HevyExerciseTemplate]:
    """Get all cached exercise templates."""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, title, type, primary_muscle_group, secondary_muscle_groups, is_custom
            FROM hevy_exercise_templates
            ORDER BY title
        """)
        rows = cursor.fetchall()
        return [_row_to_exercise_template(row) for row in rows]


def get_exercise_template_by_id(template_id: str) -> Optional[HevyExerciseTemplate]:
    """Get a single exercise template by ID."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, title, type, primary_muscle_group, secondary_muscle_groups, is_custom
            FROM hevy_exercise_templates
            WHERE id = %s
            """,
            (template_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_exercise_template(row)


def bulk_upsert_exercise_templates(templates: list[HevyExerciseTemplate]) -> int:
    """Bulk upsert exercise templates. Returns count of affected rows."""
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
                        INSERT INTO hevy_exercise_templates (
                            id, title, type, primary_muscle_group, secondary_muscle_groups, is_custom
                        ) VALUES (%s, %s, %s, %s, %s, %s)
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
                            template.type,
                            template.primary_muscle_group,
                            template.secondary_muscle_groups,
                            template.is_custom,
                        ),
                    )
                    count += 1

    logger.info(f"Successfully upserted {count} exercise templates")
    return count


# --- Helper functions ---


def _row_to_hevy_workout(row: tuple) -> HevyWorkout:
    """Convert a database row to a HevyWorkout model."""
    (
        id_,
        title,
        description,
        start_time,
        end_time,
        exercises_json,
        total_volume_kg,
        total_sets,
        hevy_created_at,
        hevy_updated_at,
    ) = row

    # Parse exercises from JSON
    exercises_data = exercises_json if isinstance(exercises_json, list) else json.loads(exercises_json or "[]")
    exercises = [_dict_to_exercise(e) for e in exercises_data]

    return HevyWorkout(
        id=id_,
        title=title,
        description=description,
        start_time=start_time,
        end_time=end_time,
        exercises=exercises,
        created_at=hevy_created_at or start_time,
        updated_at=hevy_updated_at or start_time,
    )


def _row_to_exercise_template(row: tuple) -> HevyExerciseTemplate:
    """Convert a database row to a HevyExerciseTemplate model."""
    id_, title, type_, primary_muscle, secondary_muscles, is_custom = row
    return HevyExerciseTemplate(
        id=id_,
        title=title,
        type=type_ or "",
        primary_muscle_group=primary_muscle,
        secondary_muscle_groups=secondary_muscles or [],
        is_custom=is_custom or False,
    )


def _exercise_to_dict(exercise: HevyExercise) -> dict:
    """Convert a HevyExercise to a dictionary for JSON serialization."""
    return {
        "index": exercise.index,
        "title": exercise.title,
        "notes": exercise.notes,
        "exercise_template_id": exercise.exercise_template_id,
        "superset_id": exercise.superset_id,
        "sets": [_set_to_dict(s) for s in exercise.sets],
    }


def _set_to_dict(set_: HevySet) -> dict:
    """Convert a HevySet to a dictionary for JSON serialization."""
    return {
        "index": set_.index,
        "set_type": set_.set_type,
        "weight_kg": set_.weight_kg,
        "reps": set_.reps,
        "distance_meters": set_.distance_meters,
        "duration_seconds": set_.duration_seconds,
        "rpe": set_.rpe,
    }


def _dict_to_exercise(data: dict) -> HevyExercise:
    """Convert a dictionary to a HevyExercise model."""
    return HevyExercise(
        index=data.get("index", 0),
        title=data.get("title", ""),
        notes=data.get("notes"),
        exercise_template_id=data.get("exercise_template_id", ""),
        superset_id=data.get("superset_id"),
        sets=[_dict_to_set(s) for s in data.get("sets", [])],
    )


def _dict_to_set(data: dict) -> HevySet:
    """Convert a dictionary to a HevySet model."""
    return HevySet(
        index=data.get("index", 0),
        set_type=data.get("set_type"),
        weight_kg=data.get("weight_kg"),
        reps=data.get("reps"),
        distance_meters=data.get("distance_meters"),
        duration_seconds=data.get("duration_seconds"),
        rpe=data.get("rpe"),
    )
