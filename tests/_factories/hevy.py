"""Factories for creating Hevy test data."""

from typing import Any, Mapping
from datetime import datetime, timezone

from fitness.integrations.hevy.models import (
    HevyWorkout,
    HevyExercise,
    HevySet,
    HevyExerciseTemplate,
)


class HevySetFactory:
    """Factory for creating HevySet test instances."""

    def __init__(self):
        self.default = HevySet(
            index=0,
            set_type="normal",
            weight_kg=50.0,
            reps=10,
            distance_meters=None,
            duration_seconds=None,
            rpe=7.0,
        )

    def make(self, update: Mapping[str, Any] | None = None) -> HevySet:
        return self.default.model_copy(deep=True, update=update)


class HevyExerciseFactory:
    """Factory for creating HevyExercise test instances."""

    def __init__(self):
        set_factory = HevySetFactory()
        self.default = HevyExercise(
            index=0,
            title="Bench Press",
            notes=None,
            exercise_template_id="bench_press_001",
            superset_id=None,
            sets=[
                set_factory.make({"index": 0, "weight_kg": 60.0, "reps": 10}),
                set_factory.make({"index": 1, "weight_kg": 70.0, "reps": 8}),
                set_factory.make({"index": 2, "weight_kg": 80.0, "reps": 6}),
            ],
        )

    def make(
        self, update: Mapping[str, Any] | None = None, sets: list[HevySet] | None = None
    ) -> HevyExercise:
        exercise = self.default.model_copy(deep=True, update=update)
        if sets is not None:
            exercise = exercise.model_copy(update={"sets": sets})
        return exercise


class HevyWorkoutFactory:
    """Factory for creating HevyWorkout test instances."""

    def __init__(self):
        exercise_factory = HevyExerciseFactory()
        self.default = HevyWorkout(
            id="workout_001",
            title="Push Day",
            description="Chest and triceps workout",
            start_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 15, 11, 30, 0, tzinfo=timezone.utc),
            created_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 15, 11, 30, 0, tzinfo=timezone.utc),
            exercises=[
                exercise_factory.make(
                    {"index": 0, "title": "Bench Press", "exercise_template_id": "bp_001"}
                ),
                exercise_factory.make(
                    {"index": 1, "title": "Incline Press", "exercise_template_id": "ip_001"}
                ),
            ],
        )
        self._counter = 0

    def make(
        self,
        update: Mapping[str, Any] | None = None,
        exercises: list[HevyExercise] | None = None,
    ) -> HevyWorkout:
        self._counter += 1
        # Generate unique ID if not provided
        default_update = {"id": f"workout_{self._counter:03d}"}
        if update:
            default_update.update(update)
        workout = self.default.model_copy(deep=True, update=default_update)
        if exercises is not None:
            workout = workout.model_copy(update={"exercises": exercises})
        return workout


class HevyExerciseTemplateFactory:
    """Factory for creating HevyExerciseTemplate test instances."""

    def __init__(self):
        self.default = HevyExerciseTemplate(
            id="template_001",
            title="Bench Press (Barbell)",
            type="weight_reps",
            primary_muscle_group="chest",
            secondary_muscle_groups=["triceps", "shoulders"],
            is_custom=False,
        )
        self._counter = 0

    def make(self, update: Mapping[str, Any] | None = None) -> HevyExerciseTemplate:
        self._counter += 1
        default_update = {"id": f"template_{self._counter:03d}"}
        if update:
            default_update.update(update)
        return self.default.model_copy(deep=True, update=default_update)
