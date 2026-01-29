"""Test the /strava/sync endpoint."""

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from fitness.models.run import Run
from tests._factories.strava_activity_with_gear import StravaActivityWithGearFactory


class TestSyncStravaData:
    """Test POST /strava/sync endpoint."""

    @patch("fitness.app.routers.strava.update_last_sync_time")
    @patch("fitness.app.routers.strava.get_last_sync_time")
    @patch("fitness.app.routers.strava.bulk_create_runs")
    @patch("fitness.app.routers.strava.get_existing_run_ids")
    @patch("fitness.app.routers.strava.load_strava_runs")
    def test_sync_identifies_new_runs(
        self,
        mock_load_strava_runs: MagicMock,
        mock_get_existing_run_ids: MagicMock,
        mock_bulk_create_runs: MagicMock,
        mock_get_last_sync_time: MagicMock,
        mock_update_last_sync_time: MagicMock,
        auth_client: TestClient,
    ):
        """Test that sync correctly identifies and inserts only new runs."""
        # Create 3 Strava activities
        factory = StravaActivityWithGearFactory()
        strava_run_1 = factory.make({"id": 100, "name": "Morning Run"})
        strava_run_2 = factory.make({"id": 200, "name": "Evening Run"})
        strava_run_3 = factory.make({"id": 300, "name": "Weekend Run"})

        # Mock load_strava_runs to return these 3 activities
        mock_load_strava_runs.return_value = [strava_run_1, strava_run_2, strava_run_3]

        # Mock get_existing_run_ids to return one existing run (strava_200)
        mock_get_existing_run_ids.return_value = {"strava_200"}

        # Mock bulk_create_runs to return the count of inserted runs
        mock_bulk_create_runs.return_value = 2

        # Mock sync metadata - no previous sync
        mock_get_last_sync_time.return_value = None

        response = auth_client.post("/strava/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["inserted_count"] == 2
        assert "2 new runs" in data["message"]
        assert "updated_at" in data

        # Verify load_strava_runs was called with the strava_client and after=None
        mock_load_strava_runs.assert_called_once()

        # Verify get_existing_run_ids was called
        mock_get_existing_run_ids.assert_called_once()

        # Verify bulk_create_runs was called with the 2 new runs (strava_100 and strava_300)
        mock_bulk_create_runs.assert_called_once()
        new_runs = mock_bulk_create_runs.call_args[0][0]
        assert len(new_runs) == 2

        # Verify the runs are Run objects (converted from StravaActivityWithGear)
        for run in new_runs:
            assert isinstance(run, Run)

        # Verify the correct runs were identified as new
        new_run_ids = {run.id for run in new_runs}
        assert "strava_100" in new_run_ids
        assert "strava_300" in new_run_ids
        assert "strava_200" not in new_run_ids  # This one already exists

        # Verify sync time was updated
        mock_update_last_sync_time.assert_called_once()

    @patch("fitness.app.routers.strava.update_last_sync_time")
    @patch("fitness.app.routers.strava.get_last_sync_time")
    @patch("fitness.app.routers.strava.bulk_create_runs")
    @patch("fitness.app.routers.strava.get_existing_run_ids")
    @patch("fitness.app.routers.strava.load_strava_runs")
    def test_sync_no_new_runs(
        self,
        mock_load_strava_runs: MagicMock,
        mock_get_existing_run_ids: MagicMock,
        mock_bulk_create_runs: MagicMock,
        mock_get_last_sync_time: MagicMock,
        mock_update_last_sync_time: MagicMock,
        auth_client: TestClient,
    ):
        """Test that sync handles the case when all runs already exist."""
        factory = StravaActivityWithGearFactory()
        strava_run_1 = factory.make({"id": 100, "name": "Morning Run"})
        strava_run_2 = factory.make({"id": 200, "name": "Evening Run"})

        # Mock load_strava_runs to return 2 activities
        mock_load_strava_runs.return_value = [strava_run_1, strava_run_2]

        # Mock get_existing_run_ids to return both runs as existing
        mock_get_existing_run_ids.return_value = {"strava_100", "strava_200"}

        # Mock sync metadata - no previous sync
        mock_get_last_sync_time.return_value = None

        response = auth_client.post("/strava/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["inserted_count"] == 0
        assert "0 new runs" in data["message"]

        # Verify load_strava_runs was called
        mock_load_strava_runs.assert_called_once()

        # Verify get_existing_run_ids was called
        mock_get_existing_run_ids.assert_called_once()

        # Verify bulk_create_runs was NOT called since there are no new runs
        mock_bulk_create_runs.assert_not_called()

        # Verify sync time was still updated
        mock_update_last_sync_time.assert_called_once()

    @patch("fitness.app.routers.strava.update_last_sync_time")
    @patch("fitness.app.routers.strava.get_last_sync_time")
    @patch("fitness.app.routers.strava.bulk_create_runs")
    @patch("fitness.app.routers.strava.get_existing_run_ids")
    @patch("fitness.app.routers.strava.load_strava_runs")
    def test_incremental_sync_uses_last_sync_time(
        self,
        mock_load_strava_runs: MagicMock,
        mock_get_existing_run_ids: MagicMock,
        mock_bulk_create_runs: MagicMock,
        mock_get_last_sync_time: MagicMock,
        mock_update_last_sync_time: MagicMock,
        auth_client: TestClient,
    ):
        """Test that incremental sync passes the last sync time to load_strava_runs."""
        last_sync = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        mock_get_last_sync_time.return_value = last_sync
        mock_load_strava_runs.return_value = []
        mock_get_existing_run_ids.return_value = set()

        response = auth_client.post("/strava/sync")

        assert response.status_code == 200
        data = response.json()
        assert "incremental" in data["message"]

        # Verify load_strava_runs was called with after parameter
        mock_load_strava_runs.assert_called_once()
        call_kwargs = mock_load_strava_runs.call_args[1]
        assert call_kwargs["after"] == last_sync

    @patch("fitness.app.routers.strava.update_last_sync_time")
    @patch("fitness.app.routers.strava.get_last_sync_time")
    @patch("fitness.app.routers.strava.bulk_create_runs")
    @patch("fitness.app.routers.strava.get_existing_run_ids")
    @patch("fitness.app.routers.strava.load_strava_runs")
    def test_full_sync_ignores_last_sync_time(
        self,
        mock_load_strava_runs: MagicMock,
        mock_get_existing_run_ids: MagicMock,
        mock_bulk_create_runs: MagicMock,
        mock_get_last_sync_time: MagicMock,
        mock_update_last_sync_time: MagicMock,
        auth_client: TestClient,
    ):
        """Test that full_sync=true ignores the last sync time."""
        last_sync = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        mock_get_last_sync_time.return_value = last_sync
        mock_load_strava_runs.return_value = []
        mock_get_existing_run_ids.return_value = set()

        response = auth_client.post("/strava/sync?full_sync=true")

        assert response.status_code == 200
        data = response.json()
        assert "full" in data["message"]

        # Verify load_strava_runs was called with after=None (full sync)
        mock_load_strava_runs.assert_called_once()
        call_kwargs = mock_load_strava_runs.call_args[1]
        assert call_kwargs["after"] is None

        # get_last_sync_time should NOT be called when full_sync=true
        mock_get_last_sync_time.assert_not_called()
