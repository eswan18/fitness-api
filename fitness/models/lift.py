"""Generic lift models (provider-agnostic)."""

from __future__ import annotations
from typing import TYPE_CHECKING, Literal, Self
from datetime import datetime, timezone

from pydantic import BaseModel

if TYPE_CHECKING:
    from fitness.integrations.hevy.models import (
        HevyWorkout,
        HevyExercise,
        HevySet,
        HevyExerciseTemplate,
    )


# Lift source providers
LiftSource = Literal["Hevy"]

# Set types (shared across providers)
SetType = Literal["warmup", "normal", "failure", "dropset"]

# Muscle groups (shared across providers)
MuscleGroup = Literal[
    "abdominals",
    "shoulders",
    "biceps",
    "triceps",
    "forearms",
    "quadriceps",
    "hamstrings",
    "calves",
    "glutes",
    "abductors",
    "adductors",
    "lats",
    "upper_back",
    "traps",
    "lower_back",
    "chest",
    "cardio",
    "neck",
    "full_body",
    "other",
]


class Set(BaseModel):
    """A single set within an exercise (provider-agnostic)."""

    index: int
    set_type: SetType | None = None
    weight_kg: float | None = None
    reps: int | None = None
    distance_meters: float | None = None
    duration_seconds: int | None = None
    rpe: float | None = None  # Rating of Perceived Exertion (1-10)

    def volume(self) -> float:
        """Calculate volume (weight × reps) for this set."""
        if self.weight_kg is not None and self.reps is not None:
            return self.weight_kg * self.reps
        return 0.0

    @classmethod
    def from_hevy(cls, hevy_set: HevySet) -> Self:
        """Create a Set from a Hevy set."""
        return cls(
            index=hevy_set.index,
            set_type=hevy_set.set_type,
            weight_kg=hevy_set.weight_kg,
            reps=hevy_set.reps,
            distance_meters=hevy_set.distance_meters,
            duration_seconds=hevy_set.duration_seconds,
            rpe=hevy_set.rpe,
        )


class Exercise(BaseModel):
    """An exercise within a lift (provider-agnostic)."""

    index: int
    title: str
    notes: str | None = None
    exercise_template_id: str | None = None
    superset_id: int | None = None
    sets: list[Set]

    def total_volume(self) -> float:
        """Calculate total volume for this exercise."""
        return sum(s.volume() for s in self.sets)

    def total_sets(self) -> int:
        """Count total sets (excluding warmup)."""
        return len([s for s in self.sets if s.set_type != "warmup"])

    def total_reps(self) -> int:
        """Count total reps across all sets."""
        return sum(s.reps or 0 for s in self.sets)

    @classmethod
    def from_hevy(cls, hevy_exercise: HevyExercise, id_prefix: str = "hevy_") -> Self:
        """Create an Exercise from a Hevy exercise."""
        return cls(
            index=hevy_exercise.index,
            title=hevy_exercise.title,
            notes=hevy_exercise.notes,
            exercise_template_id=f"{id_prefix}{hevy_exercise.exercise_template_id}",
            superset_id=hevy_exercise.superset_id,
            sets=[Set.from_hevy(s) for s in hevy_exercise.sets],
        )


class Lift(BaseModel):
    """A lifting workout (provider-agnostic).

    Similar to the Run model, this is a generic representation of a lifting
    session that can be populated from any provider (Hevy, Strong, etc.).
    """

    id: str  # Prefixed ID: hevy_xxx, strong_xxx, etc.
    title: str
    description: str | None = None
    start_time: datetime
    end_time: datetime
    source: LiftSource
    exercises: list[Exercise]
    deleted_at: datetime | None = None

    @property
    def is_deleted(self) -> bool:
        """Check if the lift is soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Soft delete this lift."""
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        """Restore a soft-deleted lift."""
        self.deleted_at = None

    def total_volume(self) -> float:
        """Calculate total volume (kg × reps) for the workout."""
        return sum(e.total_volume() for e in self.exercises)

    def total_sets(self) -> int:
        """Count total sets in the workout (excluding warmup)."""
        return sum(e.total_sets() for e in self.exercises)

    def duration_seconds(self) -> int:
        """Calculate workout duration in seconds."""
        return int((self.end_time - self.start_time).total_seconds())

    @classmethod
    def from_hevy(cls, hevy_workout: HevyWorkout, id_prefix: str = "hevy_") -> Self:
        """Create a Lift from a Hevy workout.

        Args:
            hevy_workout: The Hevy workout to convert.
            id_prefix: Prefix for the ID (default "hevy_").

        Returns:
            A generic Lift object.
        """
        return cls(
            id=f"{id_prefix}{hevy_workout.id}",
            title=hevy_workout.title,
            description=hevy_workout.description,
            start_time=hevy_workout.start_time.replace(tzinfo=None),
            end_time=hevy_workout.end_time.replace(tzinfo=None),
            source="Hevy",
            exercises=[Exercise.from_hevy(e, id_prefix) for e in hevy_workout.exercises],
        )


class ExerciseTemplate(BaseModel):
    """An exercise template (provider-agnostic).

    Defines the exercise type and muscle groups targeted.
    """

    id: str  # Prefixed ID: hevy_xxx, strong_xxx, etc.
    title: str
    type: str  # e.g., "weight_reps", "duration", etc.
    primary_muscle_group: MuscleGroup | None = None
    secondary_muscle_groups: list[MuscleGroup] = []
    source: LiftSource
    is_custom: bool = False

    @classmethod
    def from_hevy(
        cls, hevy_template: HevyExerciseTemplate, id_prefix: str = "hevy_"
    ) -> Self:
        """Create an ExerciseTemplate from a Hevy exercise template."""
        return cls(
            id=f"{id_prefix}{hevy_template.id}",
            title=hevy_template.title,
            type=hevy_template.type,
            primary_muscle_group=hevy_template.primary_muscle_group,
            secondary_muscle_groups=hevy_template.secondary_muscle_groups,
            source="Hevy",
            is_custom=hevy_template.is_custom,
        )
