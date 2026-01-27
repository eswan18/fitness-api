"""Pydantic models for Hevy API responses."""

from __future__ import annotations
from typing import Literal

from pydantic import BaseModel, TypeAdapter, AwareDatetime


# Muscle groups as defined by Hevy API
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

# Set types as defined by Hevy API
SetType = Literal["warmup", "normal", "failure", "dropset"]


class HevySet(BaseModel):
    """A single set within an exercise."""

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


class HevyExercise(BaseModel):
    """An exercise within a workout."""

    index: int
    title: str
    notes: str | None = None
    exercise_template_id: str
    superset_id: int | None = None
    sets: list[HevySet]

    def total_volume(self) -> float:
        """Calculate total volume for this exercise."""
        return sum(s.volume() for s in self.sets)

    def total_sets(self) -> int:
        """Count total sets (excluding warmup)."""
        return len([s for s in self.sets if s.set_type != "warmup"])


class HevyWorkout(BaseModel):
    """A workout from the Hevy API."""

    id: str
    title: str
    description: str | None = None
    start_time: AwareDatetime
    end_time: AwareDatetime
    created_at: AwareDatetime
    updated_at: AwareDatetime
    exercises: list[HevyExercise]

    def total_volume(self) -> float:
        """Calculate total volume (kg × reps) for the workout."""
        return sum(e.total_volume() for e in self.exercises)

    def total_sets(self) -> int:
        """Count total sets in the workout."""
        return sum(e.total_sets() for e in self.exercises)

    def duration_seconds(self) -> int:
        """Calculate workout duration in seconds."""
        return int((self.end_time - self.start_time).total_seconds())


class HevyExerciseTemplate(BaseModel):
    """An exercise template from Hevy (defines the exercise type and muscle groups)."""

    id: str
    title: str
    type: str  # e.g., "weight_reps", "duration", etc.
    primary_muscle_group: MuscleGroup | None = None
    secondary_muscle_groups: list[MuscleGroup] = []
    is_custom: bool = False


class HevyWorkoutsResponse(BaseModel):
    """Paginated response from /v1/workouts endpoint."""

    page: int
    page_count: int
    workouts: list[HevyWorkout]


class HevyExerciseTemplatesResponse(BaseModel):
    """Paginated response from /v1/exercise_templates endpoint."""

    page: int
    page_count: int
    exercise_templates: list[HevyExerciseTemplate]


# Type adapters for parsing API responses
workout_list_adapter = TypeAdapter(list[HevyWorkout])
exercise_template_list_adapter = TypeAdapter(list[HevyExerciseTemplate])
