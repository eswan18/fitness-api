"""Test the /hevy/sync endpoint."""

from datetime import datetime, timezone
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

    @patch("fitness.app.routers.hevy.update_last_sync_time")
    @patch("fitness.app.routers.hevy.get_last_sync_time")
    @patch("fitness.app.routers.hevy.bulk_create_lifts")
    @patch("fitness.app.routers.hevy.bulk_upsert_exercise_templates")
    @patch("fitness.app.routers.hevy.get_existing_exercise_template_ids")
    @patch("fitness.app.routers.hevy.get_existing_lift_ids")
    def test_sync_identifies_new_workouts(
        self,
        mock_get_existing_lift_ids: MagicMock,
        mock_get_existing_template_ids: MagicMock,
        mock_bulk_upsert_templates: MagicMock,
        mock_bulk_create_lifts: MagicMock,
        mock_get_last_sync_time: MagicMock,
        mock_update_last_sync_time: MagicMock,
        mock_hevy_client: MagicMock,
        auth_client: TestClient,
    ):
        """Test that sync correctly identifies and inserts only new workouts."""
        workout_factory = HevyWorkoutFactory()

        # Create 3 workouts from Hevy API (unprefixed IDs)
        workout_1 = workout_factory.make({"id": "100", "title": "Push Day"})
        workout_2 = workout_factory.make({"id": "200", "title": "Pull Day"})
        workout_3 = workout_factory.make({"id": "300", "title": "Leg Day"})

        # Configure the mock client
        mock_hevy_client.get_all_workouts.return_value = [
            workout_1,
            workout_2,
            workout_3,
        ]
        mock_hevy_client.get_exercise_template_by_id.return_value = None

        # Mock existing lift IDs in DB (prefixed) - "200" already exists
        mock_get_existing_lift_ids.return_value = {"hevy_200"}

        # Mock existing template IDs (prefixed, all templates already cached)
        mock_get_existing_template_ids.return_value = {"hevy_bp_001", "hevy_ip_001"}

        # Mock bulk operations
        mock_bulk_upsert_templates.return_value = 0
        mock_bulk_create_lifts.return_value = 2

        # Mock sync metadata - no previous sync
        mock_get_last_sync_time.return_value = None

        response = auth_client.post("/hevy/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["workouts_synced"] == 2
        assert data["templates_synced"] == 0
        assert "synced_at" in data

        # Verify get_all_workouts was called
        mock_hevy_client.get_all_workouts.assert_called_once()

        # Verify existing IDs were checked
        mock_get_existing_lift_ids.assert_called_once()

        # Verify bulk_create_lifts was called with only new Lift objects (prefixed IDs)
        mock_bulk_create_lifts.assert_called_once()
        call_args = mock_bulk_create_lifts.call_args
        new_lifts = call_args[0][0]
        assert len(new_lifts) == 2
        new_lift_ids = {lift.id for lift in new_lifts}
        assert "hevy_100" in new_lift_ids
        assert "hevy_300" in new_lift_ids
        assert "hevy_200" not in new_lift_ids  # Already exists

        # Verify sync time was updated
        mock_update_last_sync_time.assert_called_once()

    @patch("fitness.app.routers.hevy.update_last_sync_time")
    @patch("fitness.app.routers.hevy.get_last_sync_time")
    @patch("fitness.app.routers.hevy.bulk_create_lifts")
    @patch("fitness.app.routers.hevy.bulk_upsert_exercise_templates")
    @patch("fitness.app.routers.hevy.get_existing_exercise_template_ids")
    @patch("fitness.app.routers.hevy.get_existing_lift_ids")
    def test_sync_no_new_workouts(
        self,
        mock_get_existing_lift_ids: MagicMock,
        mock_get_existing_template_ids: MagicMock,
        mock_bulk_upsert_templates: MagicMock,
        mock_bulk_create_lifts: MagicMock,
        mock_get_last_sync_time: MagicMock,
        mock_update_last_sync_time: MagicMock,
        mock_hevy_client: MagicMock,
        auth_client: TestClient,
    ):
        """Test that sync handles the case when all workouts already exist."""
        workout_factory = HevyWorkoutFactory()

        # API returns workouts with unprefixed IDs
        workout_1 = workout_factory.make({"id": "100"})
        workout_2 = workout_factory.make({"id": "200"})

        mock_hevy_client.get_all_workouts.return_value = [workout_1, workout_2]

        # All workouts already exist in DB (prefixed IDs)
        mock_get_existing_lift_ids.return_value = {"hevy_100", "hevy_200"}
        mock_get_existing_template_ids.return_value = {"hevy_bp_001", "hevy_ip_001"}

        mock_bulk_upsert_templates.return_value = 0
        mock_bulk_create_lifts.return_value = 0

        # Mock sync metadata - no previous sync
        mock_get_last_sync_time.return_value = None

        response = auth_client.post("/hevy/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["workouts_synced"] == 0
        assert data["templates_synced"] == 0

        # bulk_create should be called with empty list
        mock_bulk_create_lifts.assert_called_once()
        assert mock_bulk_create_lifts.call_args[0][0] == []

        # Verify sync time was still updated
        mock_update_last_sync_time.assert_called_once()

    @patch("fitness.app.routers.hevy.update_last_sync_time")
    @patch("fitness.app.routers.hevy.get_last_sync_time")
    @patch("fitness.app.routers.hevy.bulk_create_lifts")
    @patch("fitness.app.routers.hevy.bulk_upsert_exercise_templates")
    @patch("fitness.app.routers.hevy.get_existing_exercise_template_ids")
    @patch("fitness.app.routers.hevy.get_existing_lift_ids")
    def test_sync_fetches_missing_templates(
        self,
        mock_get_existing_lift_ids: MagicMock,
        mock_get_existing_template_ids: MagicMock,
        mock_bulk_upsert_templates: MagicMock,
        mock_bulk_create_lifts: MagicMock,
        mock_get_last_sync_time: MagicMock,
        mock_update_last_sync_time: MagicMock,
        mock_hevy_client: MagicMock,
        auth_client: TestClient,
    ):
        """Test that sync fetches only missing exercise templates."""
        workout_factory = HevyWorkoutFactory()
        template_factory = HevyExerciseTemplateFactory()

        # Create workout with exercises that have template IDs (unprefixed from API)
        workout = workout_factory.make({"id": "100"})

        # Create templates that will be returned by the client
        new_template = template_factory.make(
            {"id": "bp_001", "title": "Bench Press", "primary_muscle_group": "chest"}
        )

        mock_hevy_client.get_all_workouts.return_value = [workout]
        mock_hevy_client.get_exercise_template_by_id.return_value = new_template

        # No existing workouts
        mock_get_existing_lift_ids.return_value = set()

        # ip_001 is cached (prefixed), but bp_001 is not
        mock_get_existing_template_ids.return_value = {"hevy_ip_001"}

        mock_bulk_upsert_templates.return_value = 1
        mock_bulk_create_lifts.return_value = 1

        # Mock sync metadata - no previous sync
        mock_get_last_sync_time.return_value = None

        response = auth_client.post("/hevy/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["templates_synced"] == 1
        assert data["workouts_synced"] == 1

        # Verify template was fetched for bp_001 only (unprefixed API ID)
        mock_hevy_client.get_exercise_template_by_id.assert_called_once_with("bp_001")

    @patch("fitness.app.routers.hevy.update_last_sync_time")
    @patch("fitness.app.routers.hevy.get_last_sync_time")
    @patch("fitness.app.routers.hevy.bulk_create_lifts")
    @patch("fitness.app.routers.hevy.bulk_upsert_exercise_templates")
    @patch("fitness.app.routers.hevy.get_existing_exercise_template_ids")
    @patch("fitness.app.routers.hevy.get_existing_lift_ids")
    def test_incremental_sync_uses_last_sync_time(
        self,
        mock_get_existing_lift_ids: MagicMock,
        mock_get_existing_template_ids: MagicMock,
        mock_bulk_upsert_templates: MagicMock,
        mock_bulk_create_lifts: MagicMock,
        mock_get_last_sync_time: MagicMock,
        mock_update_last_sync_time: MagicMock,
        mock_hevy_client: MagicMock,
        auth_client: TestClient,
    ):
        """Test that incremental sync passes the last sync time to get_all_workouts."""
        last_sync = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        mock_get_last_sync_time.return_value = last_sync
        mock_hevy_client.get_all_workouts.return_value = []
        mock_get_existing_lift_ids.return_value = set()
        mock_get_existing_template_ids.return_value = set()
        mock_bulk_upsert_templates.return_value = 0
        mock_bulk_create_lifts.return_value = 0

        response = auth_client.post("/hevy/sync")

        assert response.status_code == 200
        data = response.json()
        assert "incremental" in data["message"]

        # Verify get_all_workouts was called with since parameter
        mock_hevy_client.get_all_workouts.assert_called_once_with(since=last_sync)

    @patch("fitness.app.routers.hevy.update_last_sync_time")
    @patch("fitness.app.routers.hevy.get_last_sync_time")
    @patch("fitness.app.routers.hevy.bulk_create_lifts")
    @patch("fitness.app.routers.hevy.bulk_upsert_exercise_templates")
    @patch("fitness.app.routers.hevy.get_existing_exercise_template_ids")
    @patch("fitness.app.routers.hevy.get_existing_lift_ids")
    def test_full_sync_ignores_last_sync_time(
        self,
        mock_get_existing_lift_ids: MagicMock,
        mock_get_existing_template_ids: MagicMock,
        mock_bulk_upsert_templates: MagicMock,
        mock_bulk_create_lifts: MagicMock,
        mock_get_last_sync_time: MagicMock,
        mock_update_last_sync_time: MagicMock,
        mock_hevy_client: MagicMock,
        auth_client: TestClient,
    ):
        """Test that full_sync=true ignores the last sync time."""
        last_sync = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        mock_get_last_sync_time.return_value = last_sync
        mock_hevy_client.get_all_workouts.return_value = []
        mock_get_existing_lift_ids.return_value = set()
        mock_get_existing_template_ids.return_value = set()
        mock_bulk_upsert_templates.return_value = 0
        mock_bulk_create_lifts.return_value = 0

        response = auth_client.post("/hevy/sync?full_sync=true")

        assert response.status_code == 200
        data = response.json()
        assert "full" in data["message"]

        # Verify get_all_workouts was called with since=None (full sync)
        mock_hevy_client.get_all_workouts.assert_called_once_with(since=None)

        # get_last_sync_time should NOT be called when full_sync=true
        mock_get_last_sync_time.assert_not_called()

    def test_sync_requires_auth(self, client: TestClient):
        """Test that sync endpoint requires authentication."""
        response = client.post("/hevy/sync")
        assert response.status_code == 401
