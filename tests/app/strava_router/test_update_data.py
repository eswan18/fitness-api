"""Test the /strava/update-data endpoint."""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from fitness.models.run import Run
from tests._factories.strava_activity_with_gear import StravaActivityWithGearFactory


class TestUpdateStravaData:
    """Test POST /strava/update-data endpoint."""

    @patch("fitness.app.routers.strava.bulk_create_runs")
    @patch("fitness.app.routers.strava.get_existing_run_ids")
    @patch("fitness.app.routers.strava.load_strava_runs")
    def test_update_data_identifies_new_runs(
        self,
        mock_load_strava_runs: MagicMock,
        mock_get_existing_run_ids: MagicMock,
        mock_bulk_create_runs: MagicMock,
        auth_client: TestClient,
    ):
        """Test that update-data correctly identifies and inserts only new runs."""
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

        response = auth_client.post("/strava/update-data")

        assert response.status_code == 200
        data = response.json()
        assert data["inserted_count"] == 2
        assert "Inserted 2 new runs into the database" in data["message"]
        assert "updated_at" in data

        # Verify load_strava_runs was called with the strava_client
        mock_load_strava_runs.assert_called_once()
        # The client should be passed as an argument
        assert len(mock_load_strava_runs.call_args[0]) == 1

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

    @patch("fitness.app.routers.strava.bulk_create_runs")
    @patch("fitness.app.routers.strava.get_existing_run_ids")
    @patch("fitness.app.routers.strava.load_strava_runs")
    def test_update_data_no_new_runs(
        self,
        mock_load_strava_runs: MagicMock,
        mock_get_existing_run_ids: MagicMock,
        mock_bulk_create_runs: MagicMock,
        auth_client: TestClient,
    ):
        """Test that update-data handles the case when all runs already exist."""
        factory = StravaActivityWithGearFactory()
        strava_run_1 = factory.make({"id": 100, "name": "Morning Run"})
        strava_run_2 = factory.make({"id": 200, "name": "Evening Run"})

        # Mock load_strava_runs to return 2 activities
        mock_load_strava_runs.return_value = [strava_run_1, strava_run_2]

        # Mock get_existing_run_ids to return both runs as existing
        mock_get_existing_run_ids.return_value = {"strava_100", "strava_200"}

        response = auth_client.post("/strava/update-data")

        assert response.status_code == 200
        data = response.json()
        assert data["inserted_count"] == 0
        assert "Inserted 0 new runs into the database" in data["message"]

        # Verify load_strava_runs was called
        mock_load_strava_runs.assert_called_once()

        # Verify get_existing_run_ids was called
        mock_get_existing_run_ids.assert_called_once()

        # Verify bulk_create_runs was NOT called since there are no new runs
        mock_bulk_create_runs.assert_not_called()
