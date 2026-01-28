"""Factories for creating generic Lift test data."""

from typing import Any, Mapping
from datetime import datetime

from fitness.models.lift import Lift, Exercise, Set


class SetFactory:
    """Factory for creating Set test instances."""

    def __init__(self):
        self.default = Set(
            index=0,
            set_type="normal",
            weight_kg=50.0,
            reps=10,
            distance_meters=None,
            duration_seconds=None,
            rpe=7.0,
        )

    def make(self, update: Mapping[str, Any] | None = None) -> Set:
        return self.default.model_copy(deep=True, update=update)


class ExerciseFactory:
    """Factory for creating Exercise test instances."""

    def __init__(self):
        set_factory = SetFactory()
        self.default = Exercise(
            index=0,
            title="Bench Press",
            notes=None,
            exercise_template_id="hevy_bench_press_001",
            superset_id=None,
            sets=[
                set_factory.make({"index": 0, "weight_kg": 60.0, "reps": 10}),
                set_factory.make({"index": 1, "weight_kg": 70.0, "reps": 8}),
                set_factory.make({"index": 2, "weight_kg": 80.0, "reps": 6}),
            ],
        )

    def make(
        self, update: Mapping[str, Any] | None = None, sets: list[Set] | None = None
    ) -> Exercise:
        exercise = self.default.model_copy(deep=True, update=update)
        if sets is not None:
            exercise = exercise.model_copy(update={"sets": sets})
        return exercise


class LiftFactory:
    """Factory for creating Lift test instances."""

    def __init__(self):
        exercise_factory = ExerciseFactory()
        self.default = Lift(
            id="hevy_workout_001",
            title="Push Day",
            description="Chest and triceps workout",
            start_time=datetime(2024, 1, 15, 10, 0, 0),
            end_time=datetime(2024, 1, 15, 11, 30, 0),
            source="Hevy",
            exercises=[
                exercise_factory.make(
                    {"index": 0, "title": "Bench Press", "exercise_template_id": "hevy_bp_001"}
                ),
                exercise_factory.make(
                    {"index": 1, "title": "Incline Press", "exercise_template_id": "hevy_ip_001"}
                ),
            ],
            deleted_at=None,
        )
        self._counter = 0

    def make(
        self,
        update: Mapping[str, Any] | None = None,
        exercises: list[Exercise] | None = None,
    ) -> Lift:
        self._counter += 1
        # Generate unique ID if not provided
        default_update = {"id": f"hevy_workout_{self._counter:03d}"}
        if update:
            default_update.update(update)
        lift = self.default.model_copy(deep=True, update=default_update)
        if exercises is not None:
            lift = lift.model_copy(update={"exercises": exercises})
        return lift
