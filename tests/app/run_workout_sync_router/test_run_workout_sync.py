"""Tests for run workout Google Calendar sync endpoints."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from fitness.models.run_workout import RunWorkout
from fitness.models.sync import SyncedRunWorkout, SyncStatus

_MOD = "fitness.app.routers.run_workout_sync"


def _make_workout(id: str = "rw_1", title: str = "Speed Workout") -> RunWorkout:
    now = datetime(2024, 6, 1, 8, 0, 0, tzinfo=timezone.utc)
    return RunWorkout(
        id=id,
        title=title,
        created_at=now,
        updated_at=now,
    )


def _make_synced_run_workout(
    run_workout_id: str = "rw_1",
    google_event_id: str | None = "gcal_123",
    sync_status: SyncStatus = "synced",
    error_message: str | None = None,
) -> SyncedRunWorkout:
    now = datetime(2024, 6, 1, 9, 0, 0, tzinfo=timezone.utc)
    return SyncedRunWorkout(
        id=1,
        run_workout_id=run_workout_id,
        run_workout_version=1,
        google_event_id=google_event_id,
        synced_at=now,
        sync_status=sync_status,
        error_message=error_message,
        created_at=now,
        updated_at=now,
    )


def _make_run_detail(
    run_id: str = "run_1",
    dt: datetime | None = None,
    distance: float = 3.0,
    duration: float = 900.0,
) -> MagicMock:
    """Create a mock RunDetail-like object for the calendar client."""
    mock = MagicMock()
    mock.id = run_id
    mock.datetime_utc = dt or datetime(2024, 6, 1, 8, 0, 0, tzinfo=timezone.utc)
    mock.distance = distance
    mock.duration = duration
    mock.avg_heart_rate = 150.0
    mock.source = "strava"
    mock.type = "outdoor"
    mock.shoe_name = "Test Shoe"
    return mock


class TestGetSyncStatus:
    """Test GET /sync/run-workouts/{id}/status."""

    @patch(f"{_MOD}.get_synced_run_workout", return_value=None)
    def test_not_synced(
        self,
        _mock: MagicMock,
        viewer_client: TestClient,
    ):
        response = viewer_client.get("/sync/run-workouts/rw_1/status")
        assert response.status_code == 200
        data = response.json()
        assert data["run_workout_id"] == "rw_1"
        assert data["is_synced"] is False
        assert data["sync_status"] is None

    @patch(f"{_MOD}.get_synced_run_workout")
    def test_synced(
        self,
        mock_get: MagicMock,
        viewer_client: TestClient,
    ):
        mock_get.return_value = _make_synced_run_workout()
        response = viewer_client.get("/sync/run-workouts/rw_1/status")
        assert response.status_code == 200
        data = response.json()
        assert data["is_synced"] is True
        assert data["sync_status"] == "synced"
        assert data["google_event_id"] == "gcal_123"

    @patch(f"{_MOD}.get_synced_run_workout")
    def test_failed_status(
        self,
        mock_get: MagicMock,
        viewer_client: TestClient,
    ):
        mock_get.return_value = _make_synced_run_workout(
            sync_status="failed", error_message="API error"
        )
        response = viewer_client.get("/sync/run-workouts/rw_1/status")
        assert response.status_code == 200
        data = response.json()
        assert data["is_synced"] is False
        assert data["sync_status"] == "failed"
        assert data["error_message"] == "API error"


class TestSyncRunWorkout:
    """Test POST /sync/run-workouts/{id}."""

    @patch(f"{_MOD}.GoogleCalendarClient")
    @patch(f"{_MOD}.get_run_by_id")
    @patch(f"{_MOD}.get_run_ids_for_workout")
    @patch(f"{_MOD}.get_run_workout_by_id")
    @patch(f"{_MOD}.create_synced_run_workout")
    @patch(f"{_MOD}.get_synced_run_workout", return_value=None)
    def test_sync_success(
        self,
        _mock_get_sync: MagicMock,
        mock_create_sync: MagicMock,
        mock_get_workout: MagicMock,
        mock_get_run_ids: MagicMock,
        mock_get_run: MagicMock,
        mock_calendar_cls: MagicMock,
        editor_client: TestClient,
    ):
        mock_get_workout.return_value = _make_workout()
        mock_get_run_ids.return_value = ["run_1", "run_2"]
        mock_get_run.side_effect = [
            _make_run_detail("run_1"),
            _make_run_detail("run_2", dt=datetime(2024, 6, 1, 8, 30, 0, tzinfo=timezone.utc)),
        ]
        mock_calendar = MagicMock()
        mock_calendar.create_run_workout_event.return_value = "gcal_456"
        mock_calendar_cls.return_value = mock_calendar
        mock_create_sync.return_value = _make_synced_run_workout(google_event_id="gcal_456")

        response = editor_client.post("/sync/run-workouts/rw_1")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["google_event_id"] == "gcal_456"
        assert data["sync_status"] == "synced"

    @patch(f"{_MOD}.get_synced_run_workout")
    def test_already_synced(
        self,
        mock_get: MagicMock,
        editor_client: TestClient,
    ):
        mock_get.return_value = _make_synced_run_workout()
        response = editor_client.post("/sync/run-workouts/rw_1")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "already synced" in data["message"]

    @patch(f"{_MOD}.get_run_workout_by_id", return_value=None)
    @patch(f"{_MOD}.get_synced_run_workout", return_value=None)
    def test_workout_not_found(
        self,
        _mock_sync: MagicMock,
        _mock_workout: MagicMock,
        editor_client: TestClient,
    ):
        response = editor_client.post("/sync/run-workouts/rw_999")
        assert response.status_code == 404

    @patch(f"{_MOD}.get_run_by_id", return_value=None)
    @patch(f"{_MOD}.get_run_ids_for_workout", return_value=["run_1"])
    @patch(f"{_MOD}.get_run_workout_by_id")
    @patch(f"{_MOD}.get_synced_run_workout", return_value=None)
    def test_fewer_than_2_runs(
        self,
        _mock_sync: MagicMock,
        mock_workout: MagicMock,
        _mock_ids: MagicMock,
        _mock_run: MagicMock,
        editor_client: TestClient,
    ):
        mock_workout.return_value = _make_workout()
        response = editor_client.post("/sync/run-workouts/rw_1")
        assert response.status_code == 400
        assert "fewer than 2" in response.json()["detail"]

    @patch(f"{_MOD}.create_synced_run_workout")
    @patch(f"{_MOD}.GoogleCalendarClient")
    @patch(f"{_MOD}.get_run_by_id")
    @patch(f"{_MOD}.get_run_ids_for_workout")
    @patch(f"{_MOD}.get_run_workout_by_id")
    @patch(f"{_MOD}.get_synced_run_workout", return_value=None)
    def test_calendar_failure(
        self,
        _mock_sync: MagicMock,
        mock_workout: MagicMock,
        mock_ids: MagicMock,
        mock_run: MagicMock,
        mock_calendar_cls: MagicMock,
        mock_create_sync: MagicMock,
        editor_client: TestClient,
    ):
        mock_workout.return_value = _make_workout()
        mock_ids.return_value = ["run_1", "run_2"]
        mock_run.side_effect = [_make_run_detail("run_1"), _make_run_detail("run_2")]
        mock_calendar = MagicMock()
        mock_calendar.create_run_workout_event.side_effect = Exception("API down")
        mock_calendar_cls.return_value = mock_calendar

        response = editor_client.post("/sync/run-workouts/rw_1")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["sync_status"] == "failed"

    @patch(f"{_MOD}.update_synced_run_workout")
    @patch(f"{_MOD}.GoogleCalendarClient")
    @patch(f"{_MOD}.get_run_by_id")
    @patch(f"{_MOD}.get_run_ids_for_workout")
    @patch(f"{_MOD}.get_run_workout_by_id")
    @patch(f"{_MOD}.get_synced_run_workout")
    def test_resync_after_failure(
        self,
        mock_get_sync: MagicMock,
        mock_workout: MagicMock,
        mock_ids: MagicMock,
        mock_run: MagicMock,
        mock_calendar_cls: MagicMock,
        mock_update_sync: MagicMock,
        editor_client: TestClient,
    ):
        # Existing failed sync record
        mock_get_sync.return_value = _make_synced_run_workout(sync_status="failed")
        mock_workout.return_value = _make_workout()
        mock_ids.return_value = ["run_1", "run_2"]
        mock_run.side_effect = [_make_run_detail("run_1"), _make_run_detail("run_2")]
        mock_calendar = MagicMock()
        mock_calendar.create_run_workout_event.return_value = "gcal_789"
        mock_calendar_cls.return_value = mock_calendar
        mock_update_sync.return_value = _make_synced_run_workout(google_event_id="gcal_789")

        response = editor_client.post("/sync/run-workouts/rw_1")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["google_event_id"] == "gcal_789"
        mock_update_sync.assert_called_once()

    def test_viewer_cannot_sync(self, viewer_client: TestClient):
        response = viewer_client.post("/sync/run-workouts/rw_1")
        assert response.status_code == 403


class TestUnsyncRunWorkout:
    """Test DELETE /sync/run-workouts/{id}."""

    @patch(f"{_MOD}.delete_synced_run_workout", return_value=True)
    @patch(f"{_MOD}.GoogleCalendarClient")
    @patch(f"{_MOD}.get_synced_run_workout")
    def test_unsync_success(
        self,
        mock_get: MagicMock,
        mock_calendar_cls: MagicMock,
        mock_delete: MagicMock,
        editor_client: TestClient,
    ):
        mock_get.return_value = _make_synced_run_workout()
        mock_calendar = MagicMock()
        mock_calendar.delete_workout_event.return_value = True
        mock_calendar_cls.return_value = mock_calendar

        response = editor_client.delete("/sync/run-workouts/rw_1")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["sync_status"] == "unsynced"

    @patch(f"{_MOD}.get_synced_run_workout", return_value=None)
    def test_not_synced(
        self,
        _mock: MagicMock,
        editor_client: TestClient,
    ):
        response = editor_client.delete("/sync/run-workouts/rw_999")
        assert response.status_code == 404

    @patch(f"{_MOD}.delete_synced_run_workout", return_value=True)
    @patch(f"{_MOD}.get_synced_run_workout")
    def test_unsync_failed_record(
        self,
        mock_get: MagicMock,
        mock_delete: MagicMock,
        editor_client: TestClient,
    ):
        """A failed sync record should be deletable without calling Google."""
        mock_get.return_value = _make_synced_run_workout(
            sync_status="failed", google_event_id=None
        )
        response = editor_client.delete("/sync/run-workouts/rw_1")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_viewer_cannot_unsync(self, viewer_client: TestClient):
        response = viewer_client.delete("/sync/run-workouts/rw_1")
        assert response.status_code == 403


class TestListSyncRecords:
    """Test GET /sync/run-workouts and /sync/run-workouts/failed."""

    @patch(f"{_MOD}.get_all_synced_run_workouts", return_value=[])
    def test_list_empty(
        self,
        _mock: MagicMock,
        viewer_client: TestClient,
    ):
        response = viewer_client.get("/sync/run-workouts")
        assert response.status_code == 200
        assert response.json() == []

    @patch(f"{_MOD}.get_all_synced_run_workouts")
    def test_list_records(
        self,
        mock_get: MagicMock,
        viewer_client: TestClient,
    ):
        mock_get.return_value = [
            _make_synced_run_workout("rw_1"),
            _make_synced_run_workout("rw_2", google_event_id="gcal_other"),
        ]
        response = viewer_client.get("/sync/run-workouts")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @patch(f"{_MOD}.get_failed_run_workout_syncs", return_value=[])
    def test_list_failed_empty(
        self,
        _mock: MagicMock,
        viewer_client: TestClient,
    ):
        response = viewer_client.get("/sync/run-workouts/failed")
        assert response.status_code == 200
        assert response.json() == []

    @patch(f"{_MOD}.get_failed_run_workout_syncs")
    def test_list_failed(
        self,
        mock_get: MagicMock,
        viewer_client: TestClient,
    ):
        mock_get.return_value = [
            _make_synced_run_workout("rw_1", sync_status="failed", error_message="err"),
        ]
        response = viewer_client.get("/sync/run-workouts/failed")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["sync_status"] == "failed"
