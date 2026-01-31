"""Test the /lifts endpoints."""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from fitness.db.lifts import LiftWithSync
from tests._factories.lift import LiftFactory


def _unsynced(lift) -> LiftWithSync:
    """Wrap a Lift in a LiftWithSync with no sync data."""
    return LiftWithSync(
        lift=lift,
        is_synced=False,
        sync_status=None,
        synced_at=None,
        google_event_id=None,
        error_message=None,
    )


class TestGetLifts:
    """Test GET /lifts endpoint."""

    @patch("fitness.app.routers.lifts.get_all_lifts_with_sync")
    def test_get_lifts_returns_list(
        self,
        mock_get_lifts: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that get lifts returns lift summaries."""
        workout_factory = LiftFactory()
        # DB returns prefixed IDs
        workout = workout_factory.make({"id": "hevy_100", "title": "Push Day"})

        mock_get_lifts.return_value = [_unsynced(workout)]

        response = viewer_client.get("/lifts")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["lifts"]) == 1
        assert data["lifts"][0]["id"] == "hevy_100"
        assert data["lifts"][0]["title"] == "Push Day"

    @patch("fitness.app.routers.lifts.get_all_lifts_with_sync")
    def test_get_lifts_empty(
        self,
        mock_get_lifts: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that get lifts returns empty list when no lifts."""
        mock_get_lifts.return_value = []

        response = viewer_client.get("/lifts")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        assert data["lifts"] == []

    def test_get_lifts_requires_auth(self, client: TestClient):
        """Test that get lifts endpoint requires authentication."""
        response = client.get("/lifts")
        assert response.status_code == 401


class TestGetLiftsCount:
    """Test GET /lifts/count endpoint."""

    @patch("fitness.app.routers.lifts.get_lift_count")
    def test_get_lifts_count(
        self,
        mock_get_count: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that lift count is returned."""
        mock_get_count.return_value = 42

        response = viewer_client.get("/lifts/count")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 42

    @patch("fitness.app.routers.lifts.get_lift_count")
    def test_get_lifts_count_zero(
        self,
        mock_get_count: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that zero count is returned when no lifts."""
        mock_get_count.return_value = 0

        response = viewer_client.get("/lifts/count")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0

    def test_get_lifts_count_requires_auth(self, client: TestClient):
        """Test that lift count endpoint requires authentication."""
        response = client.get("/lifts/count")
        assert response.status_code == 401


class TestGetLift:
    """Test GET /lifts/{lift_id} endpoint."""

    @patch("fitness.app.routers.lifts.get_lift_by_id")
    def test_get_lift_by_id(
        self,
        mock_get_lift: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that a single lift is returned by ID."""
        workout_factory = LiftFactory()
        workout = workout_factory.make({"id": "hevy_100", "title": "Push Day"})

        mock_get_lift.return_value = workout

        response = viewer_client.get("/lifts/hevy_100")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "hevy_100"
        assert data["title"] == "Push Day"

    @patch("fitness.app.routers.lifts.get_lift_by_id")
    def test_get_lift_not_found(
        self,
        mock_get_lift: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that 404 is returned for non-existent lift."""
        mock_get_lift.return_value = None

        response = viewer_client.get("/lifts/nonexistent")

        assert response.status_code == 404

    def test_get_lift_requires_auth(self, client: TestClient):
        """Test that get lift endpoint requires authentication."""
        response = client.get("/lifts/hevy_100")
        assert response.status_code == 401


class TestGetLiftsDateFiltering:
    """Test GET /lifts endpoint with date filtering."""

    @patch("fitness.app.routers.lifts.get_lifts_in_date_range_with_sync")
    def test_get_lifts_with_start_date_only(
        self,
        mock_get_lifts: MagicMock,
        viewer_client: TestClient,
    ):
        """Test filtering lifts with only start_date."""
        lift_factory = LiftFactory()
        lift = lift_factory.make({"id": "hevy_100"})
        mock_get_lifts.return_value = [_unsynced(lift)]

        response = viewer_client.get("/lifts?start_date=2024-01-01")

        assert response.status_code == 200
        mock_get_lifts.assert_called_once()
        # Verify start_date was passed, end_date is None
        call_args = mock_get_lifts.call_args
        from datetime import date

        assert call_args[0][0] == date(2024, 1, 1)
        assert call_args[0][1] is None

    @patch("fitness.app.routers.lifts.get_lifts_in_date_range_with_sync")
    def test_get_lifts_with_end_date_only(
        self,
        mock_get_lifts: MagicMock,
        viewer_client: TestClient,
    ):
        """Test filtering lifts with only end_date."""
        lift_factory = LiftFactory()
        lift = lift_factory.make({"id": "hevy_100"})
        mock_get_lifts.return_value = [_unsynced(lift)]

        response = viewer_client.get("/lifts?end_date=2024-12-31")

        assert response.status_code == 200
        mock_get_lifts.assert_called_once()
        # Verify end_date was passed, start_date is None
        call_args = mock_get_lifts.call_args
        from datetime import date

        assert call_args[0][0] is None
        assert call_args[0][1] == date(2024, 12, 31)

    @patch("fitness.app.routers.lifts.get_lifts_in_date_range_with_sync")
    def test_get_lifts_with_both_dates(
        self,
        mock_get_lifts: MagicMock,
        viewer_client: TestClient,
    ):
        """Test filtering lifts with both start_date and end_date."""
        lift_factory = LiftFactory()
        lift = lift_factory.make({"id": "hevy_100"})
        mock_get_lifts.return_value = [_unsynced(lift)]

        response = viewer_client.get("/lifts?start_date=2024-01-01&end_date=2024-12-31")

        assert response.status_code == 200
        mock_get_lifts.assert_called_once()
        call_args = mock_get_lifts.call_args
        from datetime import date

        assert call_args[0][0] == date(2024, 1, 1)
        assert call_args[0][1] == date(2024, 12, 31)

    @patch("fitness.app.routers.lifts.get_all_lifts_with_sync")
    def test_get_lifts_without_dates_uses_get_all(
        self,
        mock_get_all: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that no date params uses get_all_lifts_with_sync."""
        mock_get_all.return_value = []

        response = viewer_client.get("/lifts")

        assert response.status_code == 200
        mock_get_all.assert_called_once()


class TestGetLiftsStats:
    """Test GET /lifts/stats endpoint."""

    @patch("fitness.app.routers.lifts.get_all_lifts")
    def test_get_lifts_stats(
        self,
        mock_get_lifts: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that lift stats are returned."""
        workout_factory = LiftFactory()
        workout1 = workout_factory.make({"id": "hevy_100"})
        workout2 = workout_factory.make({"id": "hevy_200"})

        mock_get_lifts.return_value = [workout1, workout2]

        response = viewer_client.get("/lifts/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_sessions"] == 2
        assert "total_volume_kg" in data
        assert "total_sets" in data
        assert "sets_in_period" in data
        # When no date filter, sets_in_period equals total_sets
        assert data["sets_in_period"] == data["total_sets"]

    @patch("fitness.app.routers.lifts.get_lifts_in_date_range")
    @patch("fitness.app.routers.lifts.get_all_lifts")
    def test_get_lifts_stats_with_date_filter(
        self,
        mock_get_all: MagicMock,
        mock_get_range: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that sets_in_period is calculated from filtered lifts."""
        workout_factory = LiftFactory()
        # All-time: 2 workouts
        workout1 = workout_factory.make({"id": "hevy_100"})
        workout2 = workout_factory.make({"id": "hevy_200"})
        mock_get_all.return_value = [workout1, workout2]

        # Period: only 1 workout
        mock_get_range.return_value = [workout1]

        response = viewer_client.get("/lifts/stats?start_date=2024-01-01")

        assert response.status_code == 200
        data = response.json()
        # Total stats are from all lifts
        assert data["total_sessions"] == 2
        # Period stats are from filtered lifts
        assert data["sessions_in_period"] == 1
        # sets_in_period should be from the filtered workout only
        assert data["sets_in_period"] == workout1.total_sets()

    @patch("fitness.app.routers.lifts.get_lifts_in_date_range")
    @patch("fitness.app.routers.lifts.get_all_lifts")
    def test_get_lifts_stats_empty_period(
        self,
        mock_get_all: MagicMock,
        mock_get_range: MagicMock,
        viewer_client: TestClient,
    ):
        """Test stats when date filter returns no lifts."""
        workout_factory = LiftFactory()
        workout = workout_factory.make({"id": "hevy_100"})
        mock_get_all.return_value = [workout]
        mock_get_range.return_value = []

        response = viewer_client.get("/lifts/stats?start_date=2025-01-01")

        assert response.status_code == 200
        data = response.json()
        assert data["total_sessions"] == 1
        assert data["sessions_in_period"] == 0
        assert data["sets_in_period"] == 0
        assert data["volume_in_period_kg"] == 0

    def test_get_lifts_stats_requires_auth(self, client: TestClient):
        """Test that lift stats endpoint requires authentication."""
        response = client.get("/lifts/stats")
        assert response.status_code == 401

    @patch("fitness.app.routers.lifts.get_all_lifts")
    def test_get_lifts_stats_includes_duration_fields(
        self,
        mock_get_lifts: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that lift stats includes duration fields."""
        workout_factory = LiftFactory()
        workout = workout_factory.make({"id": "hevy_100"})
        mock_get_lifts.return_value = [workout]

        response = viewer_client.get("/lifts/stats")

        assert response.status_code == 200
        data = response.json()
        assert "duration_all_time_seconds" in data
        assert "duration_in_period_seconds" in data
        assert "avg_duration_seconds" in data
        # Default workout is 1.5 hours = 5400 seconds
        assert data["duration_all_time_seconds"] == 5400
        assert data["duration_in_period_seconds"] == 5400
        assert data["avg_duration_seconds"] == 5400


class TestGetSetsByMuscle:
    """Test GET /lifts/sets-by-muscle endpoint."""

    @patch("fitness.app.routers.lifts.get_all_exercise_templates")
    @patch("fitness.app.routers.lifts.get_all_lifts")
    def test_get_sets_by_muscle(
        self,
        mock_get_lifts: MagicMock,
        mock_get_templates: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that sets by muscle returns muscle groups with counts."""
        from tests._factories.lift import ExerciseTemplateFactory, ExerciseFactory

        exercise_factory = ExerciseFactory()
        template_factory = ExerciseTemplateFactory()
        workout_factory = LiftFactory()

        # Create exercises with known template IDs
        chest_exercise = exercise_factory.make(
            {
                "title": "Bench Press",
                "exercise_template_id": "hevy_bp_001",
            }
        )
        back_exercise = exercise_factory.make(
            {
                "title": "Rows",
                "exercise_template_id": "hevy_row_001",
            }
        )

        workout = workout_factory.make(
            {"id": "hevy_100"},
            exercises=[chest_exercise, back_exercise],
        )
        mock_get_lifts.return_value = [workout]

        # Create matching templates with muscle groups
        chest_template = template_factory.make(
            {
                "id": "hevy_bp_001",
                "primary_muscle_group": "chest",
            }
        )
        back_template = template_factory.make(
            {
                "id": "hevy_row_001",
                "primary_muscle_group": "lats",
            }
        )
        mock_get_templates.return_value = [chest_template, back_template]

        response = viewer_client.get("/lifts/sets-by-muscle")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # Each exercise has 3 normal sets
        muscles = {item["muscle"]: item["sets"] for item in data}
        assert muscles["chest"] == 3
        assert muscles["lats"] == 3

    @patch("fitness.app.routers.lifts.get_all_exercise_templates")
    @patch("fitness.app.routers.lifts.get_lifts_in_date_range")
    def test_get_sets_by_muscle_with_date_filter(
        self,
        mock_get_lifts: MagicMock,
        mock_get_templates: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that sets by muscle respects date filtering."""
        from tests._factories.lift import ExerciseTemplateFactory

        workout_factory = LiftFactory()
        template_factory = ExerciseTemplateFactory()

        workout = workout_factory.make({"id": "hevy_100"})
        mock_get_lifts.return_value = [workout]

        template = template_factory.make(
            {
                "id": "hevy_bp_001",
                "primary_muscle_group": "chest",
            }
        )
        mock_get_templates.return_value = [template]

        response = viewer_client.get("/lifts/sets-by-muscle?start_date=2024-01-01")

        assert response.status_code == 200
        mock_get_lifts.assert_called_once()
        # Verify correct date arguments were passed
        from datetime import date

        call_args = mock_get_lifts.call_args
        assert call_args[0][0] == date(2024, 1, 1)
        assert call_args[0][1] is None

    def test_get_sets_by_muscle_requires_auth(self, client: TestClient):
        """Test that sets by muscle endpoint requires authentication."""
        response = client.get("/lifts/sets-by-muscle")
        assert response.status_code == 401

    @patch("fitness.app.routers.lifts.get_all_exercise_templates")
    @patch("fitness.app.routers.lifts.get_all_lifts")
    def test_get_sets_by_muscle_empty(
        self,
        mock_get_lifts: MagicMock,
        mock_get_templates: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that sets by muscle returns empty list when no lifts."""
        mock_get_lifts.return_value = []
        mock_get_templates.return_value = []

        response = viewer_client.get("/lifts/sets-by-muscle")

        assert response.status_code == 200
        assert response.json() == []

    @patch("fitness.app.routers.lifts.get_all_exercise_templates")
    @patch("fitness.app.routers.lifts.get_all_lifts")
    def test_get_sets_by_muscle_unmatched_template(
        self,
        mock_get_lifts: MagicMock,
        mock_get_templates: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that exercises with unmatched template_id are skipped."""
        from tests._factories.lift import ExerciseTemplateFactory, ExerciseFactory

        exercise_factory = ExerciseFactory()
        template_factory = ExerciseTemplateFactory()
        workout_factory = LiftFactory()

        # Create exercise with a template ID that won't match any template
        exercise = exercise_factory.make(
            {
                "title": "Unknown Exercise",
                "exercise_template_id": "hevy_unknown_001",
            }
        )
        workout = workout_factory.make({"id": "hevy_100"}, exercises=[exercise])
        mock_get_lifts.return_value = [workout]

        # Templates list doesn't include the exercise's template_id
        template = template_factory.make(
            {
                "id": "hevy_other_001",
                "primary_muscle_group": "chest",
            }
        )
        mock_get_templates.return_value = [template]

        response = viewer_client.get("/lifts/sets-by-muscle")

        assert response.status_code == 200
        # Exercise should be skipped, resulting in empty list
        assert response.json() == []


class TestGetFrequentExercises:
    """Test GET /lifts/frequent-exercises endpoint."""

    @patch("fitness.app.routers.lifts.get_all_lifts")
    def test_get_frequent_exercises(
        self,
        mock_get_lifts: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that frequent exercises returns exercise counts."""
        from tests._factories.lift import ExerciseFactory

        exercise_factory = ExerciseFactory()
        workout_factory = LiftFactory()

        # Create workouts with overlapping exercises
        workout1 = workout_factory.make(
            {"id": "hevy_100"},
            exercises=[
                exercise_factory.make({"title": "Bench Press"}),
                exercise_factory.make({"title": "Squats"}),
            ],
        )
        workout2 = workout_factory.make(
            {"id": "hevy_200"},
            exercises=[
                exercise_factory.make({"title": "Bench Press"}),
                exercise_factory.make({"title": "Deadlift"}),
            ],
        )
        mock_get_lifts.return_value = [workout1, workout2]

        response = viewer_client.get("/lifts/frequent-exercises")

        assert response.status_code == 200
        data = response.json()
        # Bench Press appears in both, others appear once
        exercise_counts = {item["name"]: item["count"] for item in data}
        assert exercise_counts["Bench Press"] == 2
        assert exercise_counts["Squats"] == 1
        assert exercise_counts["Deadlift"] == 1

    @patch("fitness.app.routers.lifts.get_all_lifts")
    def test_get_frequent_exercises_respects_limit(
        self,
        mock_get_lifts: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that limit parameter limits results."""
        from tests._factories.lift import ExerciseFactory

        exercise_factory = ExerciseFactory()
        workout_factory = LiftFactory()

        workout = workout_factory.make(
            {"id": "hevy_100"},
            exercises=[
                exercise_factory.make({"title": "Ex1"}),
                exercise_factory.make({"title": "Ex2"}),
                exercise_factory.make({"title": "Ex3"}),
                exercise_factory.make({"title": "Ex4"}),
                exercise_factory.make({"title": "Ex5"}),
            ],
        )
        mock_get_lifts.return_value = [workout]

        response = viewer_client.get("/lifts/frequent-exercises?limit=3")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    @patch("fitness.app.routers.lifts.get_lifts_in_date_range")
    def test_get_frequent_exercises_with_date_filter(
        self,
        mock_get_lifts: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that frequent exercises respects date filtering."""
        workout_factory = LiftFactory()
        workout = workout_factory.make({"id": "hevy_100"})
        mock_get_lifts.return_value = [workout]

        response = viewer_client.get("/lifts/frequent-exercises?start_date=2024-01-01")

        assert response.status_code == 200
        mock_get_lifts.assert_called_once()
        # Verify correct date arguments were passed
        from datetime import date

        call_args = mock_get_lifts.call_args
        assert call_args[0][0] == date(2024, 1, 1)
        assert call_args[0][1] is None

    def test_get_frequent_exercises_requires_auth(self, client: TestClient):
        """Test that frequent exercises endpoint requires authentication."""
        response = client.get("/lifts/frequent-exercises")
        assert response.status_code == 401

    @patch("fitness.app.routers.lifts.get_all_lifts")
    def test_get_frequent_exercises_empty(
        self,
        mock_get_lifts: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that frequent exercises returns empty list when no lifts."""
        mock_get_lifts.return_value = []

        response = viewer_client.get("/lifts/frequent-exercises")

        assert response.status_code == 200
        assert response.json() == []
