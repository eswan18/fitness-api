"""Test the /hevy/sync endpoint."""

from unittest.mock import patch, MagicMock
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from fitness.app.app import app
from fitness.app.routers.hevy import hevy_client
from tests._factories.hevy import HevyWorkoutFactory, HevyExerciseTemplateFactory


@pytest.fixture
def mock_hevy_client() -> Generator[MagicMock, None, None]:
    """Override hevy_client dependency with a mock."""
    mock_client = MagicMock()
    app.dependency_overrides[hevy_client] = lambda: mock_client
    yield mock_client
    app.dependency_overrides.pop(hevy_client, None)


class TestSyncHevyData:
    """Test POST /hevy/sync endpoint."""

    @patch("fitness.app.routers.hevy.bulk_create_hevy_workouts")
    @patch("fitness.app.routers.hevy.bulk_upsert_exercise_templates")
    @patch("fitness.app.routers.hevy.get_existing_exercise_template_ids")
    @patch("fitness.app.routers.hevy.get_existing_hevy_workout_ids")
    def test_sync_identifies_new_workouts(
        self,
        mock_get_existing_workout_ids: MagicMock,
        mock_get_existing_template_ids: MagicMock,
        mock_bulk_upsert_templates: MagicMock,
        mock_bulk_create_workouts: MagicMock,
        mock_hevy_client: MagicMock,
        auth_client: TestClient,
    ):
        """Test that sync correctly identifies and inserts only new workouts."""
        workout_factory = HevyWorkoutFactory()

        # Create 3 workouts from Hevy API
        workout_1 = workout_factory.make({"id": "hevy_100", "title": "Push Day"})
        workout_2 = workout_factory.make({"id": "hevy_200", "title": "Pull Day"})
        workout_3 = workout_factory.make({"id": "hevy_300", "title": "Leg Day"})

        # Configure the mock client
        mock_hevy_client.get_all_workouts.return_value = [workout_1, workout_2, workout_3]
        mock_hevy_client.get_exercise_template_by_id.return_value = None

        # Mock existing workout IDs (hevy_200 already exists)
        mock_get_existing_workout_ids.return_value = {"hevy_200"}

        # Mock existing template IDs (all templates already cached)
        mock_get_existing_template_ids.return_value = {"bp_001", "ip_001"}

        # Mock bulk operations
        mock_bulk_upsert_templates.return_value = 0
        mock_bulk_create_workouts.return_value = 2

        response = auth_client.post("/hevy/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["workouts_synced"] == 2
        assert data["templates_synced"] == 0
        assert "synced_at" in data

        # Verify get_all_workouts was called
        mock_hevy_client.get_all_workouts.assert_called_once()

        # Verify existing IDs were checked
        mock_get_existing_workout_ids.assert_called_once()

        # Verify bulk_create_workouts was called with only new workouts
        mock_bulk_create_workouts.assert_called_once()
        new_workouts = mock_bulk_create_workouts.call_args[0][0]
        assert len(new_workouts) == 2
        new_workout_ids = {w.id for w in new_workouts}
        assert "hevy_100" in new_workout_ids
        assert "hevy_300" in new_workout_ids
        assert "hevy_200" not in new_workout_ids  # Already exists

    @patch("fitness.app.routers.hevy.bulk_create_hevy_workouts")
    @patch("fitness.app.routers.hevy.bulk_upsert_exercise_templates")
    @patch("fitness.app.routers.hevy.get_existing_exercise_template_ids")
    @patch("fitness.app.routers.hevy.get_existing_hevy_workout_ids")
    def test_sync_no_new_workouts(
        self,
        mock_get_existing_workout_ids: MagicMock,
        mock_get_existing_template_ids: MagicMock,
        mock_bulk_upsert_templates: MagicMock,
        mock_bulk_create_workouts: MagicMock,
        mock_hevy_client: MagicMock,
        auth_client: TestClient,
    ):
        """Test that sync handles the case when all workouts already exist."""
        workout_factory = HevyWorkoutFactory()

        workout_1 = workout_factory.make({"id": "hevy_100"})
        workout_2 = workout_factory.make({"id": "hevy_200"})

        mock_hevy_client.get_all_workouts.return_value = [workout_1, workout_2]

        # All workouts already exist
        mock_get_existing_workout_ids.return_value = {"hevy_100", "hevy_200"}
        mock_get_existing_template_ids.return_value = {"bp_001", "ip_001"}

        mock_bulk_upsert_templates.return_value = 0
        mock_bulk_create_workouts.return_value = 0

        response = auth_client.post("/hevy/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["workouts_synced"] == 0
        assert data["templates_synced"] == 0

        # bulk_create should be called with empty list
        mock_bulk_create_workouts.assert_called_once()
        assert mock_bulk_create_workouts.call_args[0][0] == []

    @patch("fitness.app.routers.hevy.bulk_create_hevy_workouts")
    @patch("fitness.app.routers.hevy.bulk_upsert_exercise_templates")
    @patch("fitness.app.routers.hevy.get_existing_exercise_template_ids")
    @patch("fitness.app.routers.hevy.get_existing_hevy_workout_ids")
    def test_sync_fetches_missing_templates(
        self,
        mock_get_existing_workout_ids: MagicMock,
        mock_get_existing_template_ids: MagicMock,
        mock_bulk_upsert_templates: MagicMock,
        mock_bulk_create_workouts: MagicMock,
        mock_hevy_client: MagicMock,
        auth_client: TestClient,
    ):
        """Test that sync fetches only missing exercise templates."""
        workout_factory = HevyWorkoutFactory()
        template_factory = HevyExerciseTemplateFactory()

        # Create workout with exercises that have template IDs
        workout = workout_factory.make({"id": "hevy_100"})

        # Create templates that will be returned by the client
        new_template = template_factory.make(
            {"id": "bp_001", "title": "Bench Press", "primary_muscle_group": "chest"}
        )

        mock_hevy_client.get_all_workouts.return_value = [workout]
        mock_hevy_client.get_exercise_template_by_id.return_value = new_template

        # No existing workouts
        mock_get_existing_workout_ids.return_value = set()

        # ip_001 is cached, but bp_001 is not
        mock_get_existing_template_ids.return_value = {"ip_001"}

        mock_bulk_upsert_templates.return_value = 1
        mock_bulk_create_workouts.return_value = 1

        response = auth_client.post("/hevy/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["templates_synced"] == 1
        assert data["workouts_synced"] == 1

        # Verify template was fetched for bp_001 only (not ip_001)
        mock_hevy_client.get_exercise_template_by_id.assert_called_once_with("bp_001")

    def test_sync_requires_auth(self, client: TestClient):
        """Test that sync endpoint requires authentication."""
        response = client.post("/hevy/sync")
        assert response.status_code == 401


class TestGetWorkouts:
    """Test GET /hevy/workouts endpoint."""

    @patch("fitness.app.routers.hevy.get_all_hevy_workouts")
    def test_get_workouts_returns_list(
        self,
        mock_get_workouts: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that get workouts returns workout summaries."""
        workout_factory = HevyWorkoutFactory()
        workout = workout_factory.make({"id": "hevy_100", "title": "Push Day"})

        mock_get_workouts.return_value = [workout]

        response = viewer_client.get("/hevy/workouts")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["workouts"]) == 1
        assert data["workouts"][0]["id"] == "hevy_100"
        assert data["workouts"][0]["title"] == "Push Day"

    def test_get_workouts_requires_auth(self, client: TestClient):
        """Test that get workouts endpoint requires authentication."""
        response = client.get("/hevy/workouts")
        assert response.status_code == 401


class TestGetWorkoutCount:
    """Test GET /hevy/workout-count endpoint."""

    @patch("fitness.app.routers.hevy.get_hevy_workout_count")
    def test_get_workout_count(
        self,
        mock_get_count: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that workout count is returned."""
        mock_get_count.return_value = 42

        response = viewer_client.get("/hevy/workout-count")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 42

    def test_get_workout_count_requires_auth(self, client: TestClient):
        """Test that workout count endpoint requires authentication."""
        response = client.get("/hevy/workout-count")
        assert response.status_code == 401


class TestGetExerciseTemplates:
    """Test GET /hevy/exercise-templates endpoint."""

    @patch("fitness.app.routers.hevy.get_all_exercise_templates")
    def test_get_exercise_templates(
        self,
        mock_get_templates: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that exercise templates are returned."""
        template_factory = HevyExerciseTemplateFactory()
        template = template_factory.make({"id": "bp_001", "title": "Bench Press"})

        mock_get_templates.return_value = [template]

        response = viewer_client.get("/hevy/exercise-templates")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "bp_001"
        assert data[0]["title"] == "Bench Press"

    def test_get_exercise_templates_requires_auth(self, client: TestClient):
        """Test that exercise templates endpoint requires authentication."""
        response = client.get("/hevy/exercise-templates")
        assert response.status_code == 401
