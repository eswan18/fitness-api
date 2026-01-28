"""Tests for Hevy models."""

from datetime import datetime, timezone

from tests._factories.hevy import (
    HevySetFactory,
    HevyExerciseFactory,
    HevyWorkoutFactory,
)


class TestHevySet:
    """Tests for HevySet model."""

    def test_volume_calculation(self):
        """Test that volume is calculated correctly."""
        set_factory = HevySetFactory()
        hevy_set = set_factory.make({"weight_kg": 100.0, "reps": 5})
        assert hevy_set.volume() == 500.0

    def test_volume_with_none_weight(self):
        """Test that volume returns 0 when weight is None."""
        set_factory = HevySetFactory()
        hevy_set = set_factory.make({"weight_kg": None, "reps": 10})
        assert hevy_set.volume() == 0.0

    def test_volume_with_none_reps(self):
        """Test that volume returns 0 when reps is None."""
        set_factory = HevySetFactory()
        hevy_set = set_factory.make({"weight_kg": 50.0, "reps": None})
        assert hevy_set.volume() == 0.0


class TestHevyExercise:
    """Tests for HevyExercise model."""

    def test_total_volume(self):
        """Test that total volume sums all sets."""
        set_factory = HevySetFactory()
        sets = [
            set_factory.make({"index": 0, "weight_kg": 60.0, "reps": 10}),  # 600
            set_factory.make({"index": 1, "weight_kg": 70.0, "reps": 8}),  # 560
            set_factory.make({"index": 2, "weight_kg": 80.0, "reps": 6}),  # 480
        ]
        exercise_factory = HevyExerciseFactory()
        exercise = exercise_factory.make(sets=sets)
        assert exercise.total_volume() == 1640.0

    def test_total_sets_excludes_warmup(self):
        """Test that total_sets excludes warmup sets."""
        set_factory = HevySetFactory()
        sets = [
            set_factory.make({"index": 0, "set_type": "warmup"}),
            set_factory.make({"index": 1, "set_type": "warmup"}),
            set_factory.make({"index": 2, "set_type": "normal"}),
            set_factory.make({"index": 3, "set_type": "normal"}),
            set_factory.make({"index": 4, "set_type": "failure"}),
        ]
        exercise_factory = HevyExerciseFactory()
        exercise = exercise_factory.make(sets=sets)
        # Should count normal and failure, but not warmup
        assert exercise.total_sets() == 3


class TestHevyWorkout:
    """Tests for HevyWorkout model."""

    def test_total_volume_across_exercises(self):
        """Test that workout total volume sums all exercises."""
        set_factory = HevySetFactory()
        exercise_factory = HevyExerciseFactory()

        # Exercise 1: 3 sets of 100kg x 5 = 1500 total
        exercise1 = exercise_factory.make(
            {"title": "Squat"},
            sets=[
                set_factory.make({"weight_kg": 100.0, "reps": 5}),
                set_factory.make({"weight_kg": 100.0, "reps": 5}),
                set_factory.make({"weight_kg": 100.0, "reps": 5}),
            ],
        )

        # Exercise 2: 2 sets of 50kg x 10 = 1000 total
        exercise2 = exercise_factory.make(
            {"title": "Lunges"},
            sets=[
                set_factory.make({"weight_kg": 50.0, "reps": 10}),
                set_factory.make({"weight_kg": 50.0, "reps": 10}),
            ],
        )

        workout_factory = HevyWorkoutFactory()
        workout = workout_factory.make(exercises=[exercise1, exercise2])
        assert workout.total_volume() == 2500.0

    def test_total_sets_across_exercises(self):
        """Test that workout total sets counts all exercises."""
        set_factory = HevySetFactory()
        exercise_factory = HevyExerciseFactory()

        exercise1 = exercise_factory.make(
            sets=[
                set_factory.make({"set_type": "warmup"}),
                set_factory.make({"set_type": "normal"}),
                set_factory.make({"set_type": "normal"}),
            ]
        )

        exercise2 = exercise_factory.make(
            sets=[
                set_factory.make({"set_type": "normal"}),
                set_factory.make({"set_type": "normal"}),
            ]
        )

        workout_factory = HevyWorkoutFactory()
        workout = workout_factory.make(exercises=[exercise1, exercise2])
        # 2 normal from exercise1 + 2 normal from exercise2 = 4
        assert workout.total_sets() == 4

    def test_duration_seconds(self):
        """Test that workout duration is calculated correctly."""
        workout_factory = HevyWorkoutFactory()
        workout = workout_factory.make(
            {
                "start_time": datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
                "end_time": datetime(2024, 1, 15, 11, 30, 0, tzinfo=timezone.utc),
            }
        )
        # 1.5 hours = 5400 seconds
        assert workout.duration_seconds() == 5400
