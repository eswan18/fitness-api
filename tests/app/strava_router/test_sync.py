"""Test the /strava/sync endpoint."""

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from fitness.load.strava import StravaRunLoadResult
from fitness.models.responses import SkippedRun
from fitness.models.run import Run
from fitness.models.ride import Ride
from tests._factories.strava_activity_with_gear import StravaActivityWithGearFactory
from tests._factories.strava_ride_activity import StravaRideActivityFactory


def _runs(*activities) -> StravaRunLoadResult:
    """Shorthand to wrap a list of StravaActivityWithGear in a load result."""
    return StravaRunLoadResult(runs=list(activities), skipped=[])


class TestSyncStravaData:
    """Test POST /strava/sync endpoint."""

    @patch("fitness.app.routers.strava.update_last_sync_time")
    @patch("fitness.app.routers.strava.get_last_sync_time")
    @patch("fitness.app.routers.strava.bulk_create_rides")
    @patch("fitness.app.routers.strava.get_existing_ride_ids")
    @patch("fitness.app.routers.strava.load_strava_rides")
    @patch("fitness.app.routers.strava.bulk_create_runs")
    @patch("fitness.app.routers.strava.get_existing_run_ids")
    @patch("fitness.app.routers.strava.load_strava_runs")
    def test_sync_identifies_new_runs(
        self,
        mock_load_strava_runs: MagicMock,
        mock_get_existing_run_ids: MagicMock,
        mock_bulk_create_runs: MagicMock,
        mock_load_strava_rides: MagicMock,
        mock_get_existing_ride_ids: MagicMock,
        mock_bulk_create_rides: MagicMock,
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
        mock_load_strava_runs.return_value = _runs(
            strava_run_1, strava_run_2, strava_run_3
        )

        # Mock get_existing_run_ids to return one existing run (strava_200)
        mock_get_existing_run_ids.return_value = {"strava_200"}

        # Mock bulk_create_runs to return the count of inserted runs
        mock_bulk_create_runs.return_value = 2

        # No rides in this test
        mock_load_strava_rides.return_value = []
        mock_get_existing_ride_ids.return_value = set()

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
    @patch("fitness.app.routers.strava.bulk_create_rides")
    @patch("fitness.app.routers.strava.get_existing_ride_ids")
    @patch("fitness.app.routers.strava.load_strava_rides")
    @patch("fitness.app.routers.strava.bulk_create_runs")
    @patch("fitness.app.routers.strava.get_existing_run_ids")
    @patch("fitness.app.routers.strava.load_strava_runs")
    def test_sync_no_new_runs(
        self,
        mock_load_strava_runs: MagicMock,
        mock_get_existing_run_ids: MagicMock,
        mock_bulk_create_runs: MagicMock,
        mock_load_strava_rides: MagicMock,
        mock_get_existing_ride_ids: MagicMock,
        mock_bulk_create_rides: MagicMock,
        mock_get_last_sync_time: MagicMock,
        mock_update_last_sync_time: MagicMock,
        auth_client: TestClient,
    ):
        """Test that sync handles the case when all runs already exist."""
        factory = StravaActivityWithGearFactory()
        strava_run_1 = factory.make({"id": 100, "name": "Morning Run"})
        strava_run_2 = factory.make({"id": 200, "name": "Evening Run"})

        # Mock load_strava_runs to return 2 activities
        mock_load_strava_runs.return_value = _runs(strava_run_1, strava_run_2)

        # Mock get_existing_run_ids to return both runs as existing
        mock_get_existing_run_ids.return_value = {"strava_100", "strava_200"}

        # No rides in this test
        mock_load_strava_rides.return_value = []
        mock_get_existing_ride_ids.return_value = set()

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
    @patch("fitness.app.routers.strava.bulk_create_rides")
    @patch("fitness.app.routers.strava.get_existing_ride_ids")
    @patch("fitness.app.routers.strava.load_strava_rides")
    @patch("fitness.app.routers.strava.bulk_create_runs")
    @patch("fitness.app.routers.strava.get_existing_run_ids")
    @patch("fitness.app.routers.strava.load_strava_runs")
    def test_incremental_sync_uses_last_sync_time(
        self,
        mock_load_strava_runs: MagicMock,
        mock_get_existing_run_ids: MagicMock,
        mock_bulk_create_runs: MagicMock,
        mock_load_strava_rides: MagicMock,
        mock_get_existing_ride_ids: MagicMock,
        mock_bulk_create_rides: MagicMock,
        mock_get_last_sync_time: MagicMock,
        mock_update_last_sync_time: MagicMock,
        auth_client: TestClient,
    ):
        """Test that incremental sync passes the last sync time to load_strava_runs."""
        last_sync = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        mock_get_last_sync_time.return_value = last_sync
        mock_load_strava_runs.return_value = _runs()
        mock_get_existing_run_ids.return_value = set()
        mock_load_strava_rides.return_value = []
        mock_get_existing_ride_ids.return_value = set()

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
    @patch("fitness.app.routers.strava.bulk_create_rides")
    @patch("fitness.app.routers.strava.get_existing_ride_ids")
    @patch("fitness.app.routers.strava.load_strava_rides")
    @patch("fitness.app.routers.strava.bulk_create_runs")
    @patch("fitness.app.routers.strava.get_existing_run_ids")
    @patch("fitness.app.routers.strava.load_strava_runs")
    def test_full_sync_ignores_last_sync_time(
        self,
        mock_load_strava_runs: MagicMock,
        mock_get_existing_run_ids: MagicMock,
        mock_bulk_create_runs: MagicMock,
        mock_load_strava_rides: MagicMock,
        mock_get_existing_ride_ids: MagicMock,
        mock_bulk_create_rides: MagicMock,
        mock_get_last_sync_time: MagicMock,
        mock_update_last_sync_time: MagicMock,
        auth_client: TestClient,
    ):
        """Test that full_sync=true ignores the last sync time."""
        last_sync = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        mock_get_last_sync_time.return_value = last_sync
        mock_load_strava_runs.return_value = _runs()
        mock_get_existing_run_ids.return_value = set()
        mock_load_strava_rides.return_value = []
        mock_get_existing_ride_ids.return_value = set()

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

    @patch("fitness.app.routers.strava.update_last_sync_time")
    @patch("fitness.app.routers.strava.get_last_sync_time")
    @patch("fitness.app.routers.strava.bulk_create_rides")
    @patch("fitness.app.routers.strava.get_existing_ride_ids")
    @patch("fitness.app.routers.strava.load_strava_rides")
    @patch("fitness.app.routers.strava.bulk_create_runs")
    @patch("fitness.app.routers.strava.get_existing_run_ids")
    @patch("fitness.app.routers.strava.load_strava_runs")
    def test_sync_inserts_runs_and_rides_together(
        self,
        mock_load_strava_runs: MagicMock,
        mock_get_existing_run_ids: MagicMock,
        mock_bulk_create_runs: MagicMock,
        mock_load_strava_rides: MagicMock,
        mock_get_existing_ride_ids: MagicMock,
        mock_bulk_create_rides: MagicMock,
        mock_get_last_sync_time: MagicMock,
        mock_update_last_sync_time: MagicMock,
        auth_client: TestClient,
    ):
        """Sync should ingest runs and rides in the same call."""
        run_factory = StravaActivityWithGearFactory()
        ride_factory = StravaRideActivityFactory()

        mock_load_strava_runs.return_value = _runs(run_factory.make({"id": 100}))
        mock_get_existing_run_ids.return_value = set()
        mock_bulk_create_runs.return_value = 1

        mock_load_strava_rides.return_value = [
            ride_factory.make({"id": 500}),
            ride_factory.make({"id": 600, "type": "VirtualRide", "trainer": True}),
        ]
        mock_get_existing_ride_ids.return_value = set()
        mock_bulk_create_rides.return_value = 2

        mock_get_last_sync_time.return_value = None

        response = auth_client.post("/strava/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["inserted_count"] == 3  # 1 run + 2 rides
        assert data["inserted_runs"] == 1
        assert data["inserted_rides"] == 2

        # Both bulk creators were called with the right model types
        run_arg = mock_bulk_create_runs.call_args[0][0]
        ride_arg = mock_bulk_create_rides.call_args[0][0]
        assert all(isinstance(r, Run) for r in run_arg)
        assert all(isinstance(r, Ride) for r in ride_arg)
        assert {r.type for r in ride_arg} == {"Outdoor Ride", "Indoor Ride"}

    @patch("fitness.app.routers.strava.update_last_sync_time")
    @patch("fitness.app.routers.strava.get_last_sync_time")
    @patch("fitness.app.routers.strava.bulk_create_rides")
    @patch("fitness.app.routers.strava.get_existing_ride_ids")
    @patch("fitness.app.routers.strava.load_strava_rides")
    @patch("fitness.app.routers.strava.bulk_create_runs")
    @patch("fitness.app.routers.strava.get_existing_run_ids")
    @patch("fitness.app.routers.strava.load_strava_runs")
    def test_sync_dedupes_existing_rides(
        self,
        mock_load_strava_runs: MagicMock,
        mock_get_existing_run_ids: MagicMock,
        mock_bulk_create_runs: MagicMock,
        mock_load_strava_rides: MagicMock,
        mock_get_existing_ride_ids: MagicMock,
        mock_bulk_create_rides: MagicMock,
        mock_get_last_sync_time: MagicMock,
        mock_update_last_sync_time: MagicMock,
        auth_client: TestClient,
    ):
        """Existing ride IDs should be filtered out before bulk insert."""
        ride_factory = StravaRideActivityFactory()
        mock_load_strava_runs.return_value = _runs()
        mock_get_existing_run_ids.return_value = set()
        mock_load_strava_rides.return_value = [
            ride_factory.make({"id": 700}),
            ride_factory.make({"id": 800}),
        ]
        mock_get_existing_ride_ids.return_value = {"strava_700"}
        mock_bulk_create_rides.return_value = 1
        mock_get_last_sync_time.return_value = None

        response = auth_client.post("/strava/sync")

        assert response.status_code == 200
        new_rides = mock_bulk_create_rides.call_args[0][0]
        assert {r.id for r in new_rides} == {"strava_800"}

    @patch("fitness.app.routers.strava.update_last_sync_time")
    @patch("fitness.app.routers.strava.get_last_sync_time")
    @patch("fitness.app.routers.strava.bulk_create_rides")
    @patch("fitness.app.routers.strava.get_existing_ride_ids")
    @patch("fitness.app.routers.strava.load_strava_rides")
    @patch("fitness.app.routers.strava.bulk_create_runs")
    @patch("fitness.app.routers.strava.get_existing_run_ids")
    @patch("fitness.app.routers.strava.load_strava_runs")
    def test_sync_surfaces_skipped_runs_in_response(
        self,
        mock_load_strava_runs: MagicMock,
        mock_get_existing_run_ids: MagicMock,
        mock_bulk_create_runs: MagicMock,
        mock_load_strava_rides: MagicMock,
        mock_get_existing_ride_ids: MagicMock,
        mock_bulk_create_rides: MagicMock,
        mock_get_last_sync_time: MagicMock,
        mock_update_last_sync_time: MagicMock,
        auth_client: TestClient,
    ):
        """Runs the loader couldn't import (missing shoes) must reach the API response."""
        run_factory = StravaActivityWithGearFactory()
        mock_load_strava_runs.return_value = StravaRunLoadResult(
            runs=[run_factory.make({"id": 100})],
            skipped=[
                SkippedRun(id="999", name="Treadmill, no shoes", reason="no_gear_assigned"),
                SkippedRun(id="1001", name="Run with deleted gear", reason="gear_fetch_failed"),
            ],
        )
        mock_get_existing_run_ids.return_value = set()
        mock_bulk_create_runs.return_value = 1
        mock_load_strava_rides.return_value = []
        mock_get_existing_ride_ids.return_value = set()
        mock_get_last_sync_time.return_value = None

        response = auth_client.post("/strava/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["inserted_runs"] == 1
        assert len(data["skipped_runs"]) == 2
        skipped_by_id = {s["id"]: s for s in data["skipped_runs"]}
        assert skipped_by_id["999"]["reason"] == "no_gear_assigned"
        assert skipped_by_id["1001"]["reason"] == "gear_fetch_failed"
        assert "2 runs skipped" in data["message"]
