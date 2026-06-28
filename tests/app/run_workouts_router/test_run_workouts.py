"""Test the /run-workouts and /cardio-activity-feed endpoints."""

import csv
import io
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from fitness.models.ride_detail import RideDetail
from fitness.models.run_workout import RunWorkout
from fitness.models.run_detail import RunDetail


# --- Helpers ---


def _make_run_detail(
    id: str = "run_1",
    datetime_utc: datetime | None = None,
    distance: float = 3.0,
    duration: float = 1200.0,
    avg_heart_rate: float | None = 150.0,
    run_workout_id: str | None = None,
) -> RunDetail:
    return RunDetail(
        id=id,
        datetime_utc=datetime_utc or datetime(2024, 6, 1, 8, 0, 0),
        type="Outdoor Run",
        distance=distance,
        duration=duration,
        source="Strava",
        avg_heart_rate=avg_heart_rate,
        run_workout_id=run_workout_id,
    )


def _make_workout(
    id: str = "rw_test-1",
    title: str = "Speed Workout",
    notes: str | None = None,
) -> RunWorkout:
    return RunWorkout(
        id=id,
        title=title,
        notes=notes,
        created_at=datetime(2024, 6, 1, 10, 0, 0),
        updated_at=datetime(2024, 6, 1, 10, 0, 0),
    )


def _make_ride(
    id: str = "ride_1",
    datetime_utc: datetime | None = None,
    type_: str = "Indoor Ride",
    duration: float = 3600.0,
    avg_heart_rate: float | None = 140.0,
) -> RideDetail:
    return RideDetail(
        id=id,
        datetime_utc=datetime_utc or datetime(2024, 6, 1, 18, 0, 0),
        type=type_,  # ty: ignore[invalid-argument-type]
        distance=0.0,
        duration=duration,
        source="Strava",
        avg_heart_rate=avg_heart_rate,
    )


_DB_MOD = "fitness.app.routers.run_workouts"


class TestCreateRunWorkout:
    """Test POST /run-workouts."""

    @patch(f"{_DB_MOD}.get_run_details_by_ids")
    @patch(f"{_DB_MOD}.get_run_ids_for_workout")
    @patch(f"{_DB_MOD}.create_run_workout")
    def test_create_success(
        self,
        mock_create: MagicMock,
        mock_get_ids: MagicMock,
        mock_get_details: MagicMock,
        editor_client: TestClient,
    ):
        workout = _make_workout()
        mock_create.return_value = workout
        mock_get_ids.return_value = ["run_1", "run_2"]
        mock_get_details.return_value = [
            _make_run_detail("run_1", datetime(2024, 6, 1, 8, 0, 0)),
            _make_run_detail("run_2", datetime(2024, 6, 1, 8, 30, 0)),
        ]

        response = editor_client.post(
            "/run-workouts",
            json={"title": "Speed Workout", "run_ids": ["run_1", "run_2"]},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "rw_test-1"
        assert data["title"] == "Speed Workout"
        assert data["run_count"] == 2

    @patch(f"{_DB_MOD}.create_run_workout")
    def test_create_too_few_runs(
        self,
        mock_create: MagicMock,
        editor_client: TestClient,
    ):
        response = editor_client.post(
            "/run-workouts",
            json={"title": "Bad Workout", "run_ids": ["run_1"]},
        )
        assert response.status_code == 422

    @patch(f"{_DB_MOD}.create_run_workout")
    def test_create_validation_error(
        self,
        mock_create: MagicMock,
        editor_client: TestClient,
    ):
        mock_create.side_effect = ValueError("Runs not found: run_999")
        response = editor_client.post(
            "/run-workouts",
            json={"title": "Bad", "run_ids": ["run_999", "run_998"]},
        )
        assert response.status_code == 400
        assert "Runs not found" in response.json()["detail"]

    def test_create_requires_editor(self, viewer_client: TestClient):
        response = viewer_client.post(
            "/run-workouts",
            json={"title": "Test", "run_ids": ["r1", "r2"]},
        )
        assert response.status_code == 403


class TestListRunWorkouts:
    """Test GET /run-workouts."""

    @patch(f"{_DB_MOD}.get_all_run_details")
    @patch(f"{_DB_MOD}.get_run_ids_for_workout")
    @patch(f"{_DB_MOD}.get_all_run_workouts")
    def test_list_workouts(
        self,
        mock_list: MagicMock,
        mock_get_ids: MagicMock,
        mock_get_details: MagicMock,
        viewer_client: TestClient,
    ):
        mock_list.return_value = [_make_workout()]
        mock_get_ids.return_value = ["run_1", "run_2"]
        mock_get_details.return_value = [
            _make_run_detail("run_1", datetime(2024, 6, 1, 8, 0, 0)),
            _make_run_detail("run_2", datetime(2024, 6, 1, 8, 30, 0)),
        ]

        response = viewer_client.get("/run-workouts")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Speed Workout"
        assert data[0]["run_count"] == 2

    @patch(f"{_DB_MOD}.get_all_run_details")
    @patch(f"{_DB_MOD}.get_all_run_workouts")
    def test_list_empty(
        self,
        mock_list: MagicMock,
        mock_get_details: MagicMock,
        viewer_client: TestClient,
    ):
        mock_list.return_value = []
        mock_get_details.return_value = []
        response = viewer_client.get("/run-workouts")
        assert response.status_code == 200
        assert response.json() == []


class TestGetRunWorkout:
    """Test GET /run-workouts/{id}."""

    @patch(f"{_DB_MOD}.get_run_details_by_ids")
    @patch(f"{_DB_MOD}.get_run_ids_for_workout")
    @patch(f"{_DB_MOD}.get_run_workout_by_id")
    def test_get_workout(
        self,
        mock_get: MagicMock,
        mock_get_ids: MagicMock,
        mock_get_details: MagicMock,
        viewer_client: TestClient,
    ):
        mock_get.return_value = _make_workout()
        mock_get_ids.return_value = ["run_1", "run_2"]
        mock_get_details.return_value = [
            _make_run_detail("run_1", datetime(2024, 6, 1, 8, 0, 0)),
            _make_run_detail("run_2", datetime(2024, 6, 1, 8, 30, 0)),
        ]

        response = viewer_client.get("/run-workouts/rw_test-1")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Speed Workout"
        assert data["run_count"] == 2
        assert len(data["runs"]) == 2

    @patch(f"{_DB_MOD}.get_run_workout_by_id")
    def test_get_not_found(
        self,
        mock_get: MagicMock,
        viewer_client: TestClient,
    ):
        mock_get.return_value = None
        response = viewer_client.get("/run-workouts/rw_missing")
        assert response.status_code == 404


class TestUpdateRunWorkout:
    """Test PATCH /run-workouts/{id}."""

    @patch(f"{_DB_MOD}.is_run_workout_synced", return_value=False)
    @patch(f"{_DB_MOD}.get_run_details_by_ids")
    @patch(f"{_DB_MOD}.get_run_ids_for_workout")
    @patch(f"{_DB_MOD}.update_run_workout")
    def test_update_title(
        self,
        mock_update: MagicMock,
        mock_get_ids: MagicMock,
        mock_get_details: MagicMock,
        _mock_synced: MagicMock,
        editor_client: TestClient,
    ):
        mock_update.return_value = _make_workout(title="Updated Title")
        mock_get_ids.return_value = ["run_1", "run_2"]
        mock_get_details.return_value = [
            _make_run_detail("run_1"),
            _make_run_detail("run_2"),
        ]

        response = editor_client.patch(
            "/run-workouts/rw_test-1",
            json={"title": "Updated Title"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated Title"

    @patch(f"{_DB_MOD}.is_run_workout_synced", return_value=False)
    def test_update_no_fields(
        self,
        _mock_synced: MagicMock,
        editor_client: TestClient,
    ):
        response = editor_client.patch(
            "/run-workouts/rw_test-1",
            json={},
        )
        assert response.status_code == 400

    @patch(f"{_DB_MOD}.is_run_workout_synced", return_value=False)
    @patch(f"{_DB_MOD}.update_run_workout")
    def test_update_not_found(
        self,
        mock_update: MagicMock,
        _mock_synced: MagicMock,
        editor_client: TestClient,
    ):
        mock_update.return_value = None
        response = editor_client.patch(
            "/run-workouts/rw_missing",
            json={"title": "X"},
        )
        assert response.status_code == 404


class TestDeleteRunWorkout:
    """Test DELETE /run-workouts/{id}."""

    @patch(f"{_DB_MOD}.is_run_workout_synced", return_value=False)
    @patch(f"{_DB_MOD}.delete_run_workout")
    def test_delete_success(
        self,
        mock_delete: MagicMock,
        _mock_synced: MagicMock,
        editor_client: TestClient,
    ):
        mock_delete.return_value = True
        response = editor_client.delete("/run-workouts/rw_test-1")
        assert response.status_code == 200

    @patch(f"{_DB_MOD}.is_run_workout_synced", return_value=False)
    @patch(f"{_DB_MOD}.delete_run_workout")
    def test_delete_not_found(
        self,
        mock_delete: MagicMock,
        _mock_synced: MagicMock,
        editor_client: TestClient,
    ):
        mock_delete.return_value = False
        response = editor_client.delete("/run-workouts/rw_missing")
        assert response.status_code == 404

    def test_delete_requires_editor(self, viewer_client: TestClient):
        response = viewer_client.delete("/run-workouts/rw_test-1")
        assert response.status_code == 403


class TestReplaceWorkoutRuns:
    """Test PUT /run-workouts/{id}/runs."""

    @patch(f"{_DB_MOD}.is_run_workout_synced", return_value=False)
    @patch(f"{_DB_MOD}.get_run_details_by_ids")
    @patch(f"{_DB_MOD}.get_run_ids_for_workout")
    @patch(f"{_DB_MOD}.get_run_workout_by_id")
    @patch(f"{_DB_MOD}.set_run_workout_runs")
    def test_replace_runs(
        self,
        mock_set: MagicMock,
        mock_get: MagicMock,
        mock_get_ids: MagicMock,
        mock_get_details: MagicMock,
        _mock_synced: MagicMock,
        editor_client: TestClient,
    ):
        mock_set.return_value = None
        mock_get.return_value = _make_workout()
        mock_get_ids.return_value = ["run_3", "run_4"]
        mock_get_details.return_value = [
            _make_run_detail("run_3"),
            _make_run_detail("run_4"),
        ]

        response = editor_client.put(
            "/run-workouts/rw_test-1/runs",
            json={"run_ids": ["run_3", "run_4"]},
        )
        assert response.status_code == 200
        assert response.json()["run_count"] == 2

    @patch(f"{_DB_MOD}.set_run_workout_runs")
    def test_replace_too_few_runs(
        self,
        mock_set: MagicMock,
        editor_client: TestClient,
    ):
        response = editor_client.put(
            "/run-workouts/rw_test-1/runs",
            json={"run_ids": ["run_1"]},
        )
        assert response.status_code == 422


class TestSyncedWorkoutRejection:
    """Test that synced run workouts cannot be edited."""

    @patch(f"{_DB_MOD}.is_run_workout_synced", return_value=True)
    def test_update_synced_workout_rejected(
        self,
        _mock_synced: MagicMock,
        editor_client: TestClient,
    ):
        """Test that updating a synced workout returns 409 Conflict."""
        response = editor_client.patch(
            "/run-workouts/rw_test-1",
            json={"title": "New Title"},
        )
        assert response.status_code == 409
        assert "synced" in response.json()["detail"]

    @patch(f"{_DB_MOD}.is_run_workout_synced", return_value=True)
    def test_replace_runs_synced_workout_rejected(
        self,
        _mock_synced: MagicMock,
        editor_client: TestClient,
    ):
        """Test that replacing runs in a synced workout returns 409 Conflict."""
        response = editor_client.put(
            "/run-workouts/rw_test-1/runs",
            json={"run_ids": ["run_3", "run_4"]},
        )
        assert response.status_code == 409
        assert "synced" in response.json()["detail"]

    @patch(f"{_DB_MOD}.is_run_workout_synced", return_value=True)
    def test_delete_synced_workout_rejected(
        self,
        _mock_synced: MagicMock,
        editor_client: TestClient,
    ):
        """Test that deleting a synced workout returns 409 Conflict."""
        response = editor_client.delete("/run-workouts/rw_test-1")
        assert response.status_code == 409
        assert "synced" in response.json()["detail"]


class TestActivityFeed:
    """Test GET /cardio-activity-feed."""

    @pytest.fixture(autouse=True)
    def _stub_ride_db(self, monkeypatch):
        """Default rides to empty for every test in this class.

        Individual tests can patch the ride-detail queries to override.
        """
        monkeypatch.setattr(
            "fitness.db.rides.get_all_ride_details", lambda *a, **kw: []
        )
        monkeypatch.setattr(
            "fitness.db.rides.get_ride_details_in_date_range",
            lambda *a, **kw: [],
        )

    @patch("fitness.db.runs.get_all_run_details")
    def test_solo_runs_only(
        self,
        mock_get_details: MagicMock,
        viewer_client: TestClient,
    ):
        mock_get_details.return_value = [
            _make_run_detail("run_1", datetime(2024, 6, 1, 8, 0, 0)),
            _make_run_detail("run_2", datetime(2024, 6, 2, 8, 0, 0)),
        ]

        response = viewer_client.get("/cardio-activity-feed")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(item["type"] == "run" for item in data)

    @patch(f"{_DB_MOD}.get_synced_run_workouts_by_ids", return_value=[])
    @patch(f"{_DB_MOD}.get_run_workouts_by_ids")
    @patch("fitness.db.runs.get_all_run_details")
    def test_workout_grouped(
        self,
        mock_get_details: MagicMock,
        mock_get_workouts: MagicMock,
        _mock_syncs: MagicMock,
        viewer_client: TestClient,
    ):
        mock_get_details.return_value = [
            _make_run_detail("run_1", datetime(2024, 6, 1, 8, 0, 0)),
            _make_run_detail(
                "run_2",
                datetime(2024, 6, 2, 8, 0, 0),
                run_workout_id="rw_1",
            ),
            _make_run_detail(
                "run_3",
                datetime(2024, 6, 2, 8, 30, 0),
                run_workout_id="rw_1",
            ),
        ]
        mock_get_workouts.return_value = {"rw_1": _make_workout(id="rw_1")}

        response = viewer_client.get("/cardio-activity-feed")
        assert response.status_code == 200
        data = response.json()
        # Should have 2 items: 1 solo run + 1 workout
        assert len(data) == 2
        types = {item["type"] for item in data}
        assert types == {"run", "run_workout"}

        # Find the workout item
        workout_item = next(i for i in data if i["type"] == "run_workout")
        assert workout_item["item"]["run_count"] == 2
        assert workout_item["item"]["title"] == "Speed Workout"
        assert len(workout_item["item"]["runs"]) == 2

    @patch("fitness.db.runs.get_all_run_details")
    def test_feed_sorted_desc(
        self,
        mock_get_details: MagicMock,
        viewer_client: TestClient,
    ):
        mock_get_details.return_value = [
            _make_run_detail("run_1", datetime(2024, 6, 1, 8, 0, 0)),
            _make_run_detail("run_2", datetime(2024, 6, 3, 8, 0, 0)),
        ]

        response = viewer_client.get("/cardio-activity-feed?sort_order=desc")
        assert response.status_code == 200
        data = response.json()
        assert data[0]["item"]["id"] == "run_2"
        assert data[1]["item"]["id"] == "run_1"

    @patch("fitness.db.runs.get_all_run_details")
    def test_feed_sorted_asc(
        self,
        mock_get_details: MagicMock,
        viewer_client: TestClient,
    ):
        mock_get_details.return_value = [
            _make_run_detail("run_1", datetime(2024, 6, 1, 8, 0, 0)),
            _make_run_detail("run_2", datetime(2024, 6, 3, 8, 0, 0)),
        ]

        response = viewer_client.get("/cardio-activity-feed?sort_order=asc")
        assert response.status_code == 200
        data = response.json()
        assert data[0]["item"]["id"] == "run_1"
        assert data[1]["item"]["id"] == "run_2"

    @patch(f"{_DB_MOD}.get_synced_run_workouts_by_ids", return_value=[])
    @patch(f"{_DB_MOD}.get_run_workouts_by_ids")
    @patch("fitness.db.runs.get_all_run_details")
    def test_workout_aggregates(
        self,
        mock_get_details: MagicMock,
        mock_get_workouts: MagicMock,
        _mock_syncs: MagicMock,
        viewer_client: TestClient,
    ):
        """Verify computed aggregates for a workout in the feed."""
        mock_get_details.return_value = [
            _make_run_detail(
                "run_1",
                datetime(2024, 6, 1, 8, 0, 0),
                distance=2.0,
                duration=600.0,
                avg_heart_rate=140.0,
                run_workout_id="rw_1",
            ),
            _make_run_detail(
                "run_2",
                datetime(2024, 6, 1, 8, 15, 0),
                distance=3.0,
                duration=900.0,
                avg_heart_rate=160.0,
                run_workout_id="rw_1",
            ),
        ]
        mock_get_workouts.return_value = {"rw_1": _make_workout(id="rw_1")}

        response = viewer_client.get("/cardio-activity-feed")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        workout = data[0]["item"]
        assert workout["total_distance"] == 5.0
        assert workout["total_duration"] == 1500.0
        # Weighted avg HR: (140*600 + 160*900) / 1500 = 228000/1500 = 152.0
        assert workout["avg_heart_rate"] == 152.0
        assert workout["run_count"] == 2
        # Elapsed: from 8:00:00 to 8:15:00 + 900s = 8:30:00 = 1800s
        assert workout["elapsed_seconds"] == 1800.0

    @patch("fitness.db.runs.get_run_details_in_date_range")
    def test_filters_by_local_date_across_utc_midnight_boundary(
        self,
        mock_get_details: MagicMock,
        viewer_client: TestClient,
    ):
        """Two runs sharing a UTC date but straddling midnight in the user's tz
        must be placed on separate local dates.

        Chicago is UTC-5 in April (CDT), so 05:00 UTC = 00:00 Chicago. These
        two runs are only an hour apart but fall on different Chicago dates:

        - 2026-04-10 04:30 UTC → 2026-04-09 23:30 America/Chicago (April 9)
        - 2026-04-10 05:30 UTC → 2026-04-10 00:30 America/Chicago (April 10)

        Both have UTC date = April 10, so filtering by UTC date alone would
        either include both or neither. With user_timezone=America/Chicago
        and a query window of April 9, only the first should appear.
        """
        run_chicago_april_9 = _make_run_detail(
            "run_just_before_midnight_chicago",
            datetime(2026, 4, 10, 4, 30, 0),
        )
        run_chicago_april_10 = _make_run_detail(
            "run_just_after_midnight_chicago",
            datetime(2026, 4, 10, 5, 30, 0),
        )
        mock_get_details.return_value = [
            run_chicago_april_9,
            run_chicago_april_10,
        ]

        response = viewer_client.get(
            "/cardio-activity-feed",
            params={
                "start": "2026-04-09",
                "end": "2026-04-09",
                "user_timezone": "America/Chicago",
            },
        )

        assert response.status_code == 200
        data = response.json()
        ids = {item["item"]["id"] for item in data if item["type"] == "run"}
        assert ids == {"run_just_before_midnight_chicago"}, (
            f"Expected only the pre-midnight Chicago run, got {ids}"
        )

    @patch("fitness.db.runs.get_all_run_details", return_value=[])
    def test_ride_appears_as_ride_variant(
        self,
        _mock_get_details: MagicMock,
        viewer_client: TestClient,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "fitness.db.rides.get_all_ride_details",
            lambda *a, **kw: [
                _make_ride(
                    "strava_ride_1",
                    datetime(2024, 6, 1, 18, 0, 0),
                    type_="Indoor Ride",
                )
            ],
        )

        response = viewer_client.get("/cardio-activity-feed")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "ride"
        assert data[0]["item"]["id"] == "strava_ride_1"
        assert data[0]["item"]["type"] == "Indoor Ride"

    @patch("fitness.db.runs.get_all_run_details")
    def test_ride_and_run_interleave_by_datetime_desc(
        self,
        mock_get_details: MagicMock,
        viewer_client: TestClient,
        monkeypatch,
    ):
        # Run at 08:00, ride at 18:00, both on the same day.
        mock_get_details.return_value = [
            _make_run_detail("run_morning", datetime(2024, 6, 1, 8, 0, 0)),
        ]
        monkeypatch.setattr(
            "fitness.db.rides.get_all_ride_details",
            lambda *a, **kw: [
                _make_ride("ride_evening", datetime(2024, 6, 1, 18, 0, 0)),
            ],
        )

        response = viewer_client.get("/cardio-activity-feed?sort_order=desc")
        assert response.status_code == 200
        data = response.json()
        assert [item["item"]["id"] for item in data] == [
            "ride_evening",
            "run_morning",
        ]

    @patch("fitness.db.runs.get_all_run_details", return_value=[])
    def test_ride_without_hr_still_returned(
        self,
        _mock_get_details: MagicMock,
        viewer_client: TestClient,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "fitness.db.rides.get_all_ride_details",
            lambda *a, **kw: [
                _make_ride(
                    "ride_no_hr",
                    datetime(2024, 6, 1, 18, 0, 0),
                    avg_heart_rate=None,
                ),
            ],
        )

        response = viewer_client.get("/cardio-activity-feed")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["item"]["avg_heart_rate"] is None


class TestActivityFeedExport:
    """Test GET /cardio-activity-feed/export."""

    @pytest.fixture(autouse=True)
    def _stub_ride_db(self, monkeypatch):
        monkeypatch.setattr(
            "fitness.db.rides.get_all_ride_details", lambda *a, **kw: []
        )
        monkeypatch.setattr(
            "fitness.db.rides.get_ride_details_in_date_range",
            lambda *a, **kw: [],
        )

    @staticmethod
    def _csv_rows(text: str) -> list[dict[str, str]]:
        return list(csv.DictReader(io.StringIO(text)))

    @patch("fitness.db.runs.get_all_run_details")
    def test_csv_default_headers_and_attachment(
        self, mock_get_details: MagicMock, viewer_client: TestClient
    ):
        mock_get_details.return_value = [
            _make_run_detail("run_1", datetime(2024, 6, 1, 8, 0, 0)),
        ]
        response = viewer_client.get("/cardio-activity-feed/export")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert (
            'attachment; filename="cardio-activities_'
            in response.headers["content-disposition"]
        )
        first_line = response.text.splitlines()[0]
        assert first_line.startswith("activity_kind,activity_id,datetime_utc")

    @patch("fitness.db.runs.get_all_run_details")
    def test_csv_row_per_activity(
        self, mock_get_details: MagicMock, viewer_client: TestClient, monkeypatch
    ):
        mock_get_details.return_value = [
            _make_run_detail("run_1", datetime(2024, 6, 1, 8, 0, 0)),
            _make_run_detail("run_2", datetime(2024, 6, 2, 8, 0, 0)),
        ]
        monkeypatch.setattr(
            "fitness.db.rides.get_all_ride_details",
            lambda *a, **kw: [_make_ride("ride_1", datetime(2024, 6, 1, 18, 0, 0))],
        )
        rows = self._csv_rows(viewer_client.get("/cardio-activity-feed/export").text)
        assert len(rows) == 3
        kinds = sorted(r["activity_kind"] for r in rows)
        assert kinds == ["ride", "run", "run"]

    @patch(f"{_DB_MOD}.get_synced_run_workouts_by_ids", return_value=[])
    @patch(f"{_DB_MOD}.get_run_workouts_by_ids")
    @patch("fitness.db.runs.get_all_run_details")
    def test_csv_flattens_workout_into_run_rows(
        self,
        mock_get_details: MagicMock,
        mock_get_workouts: MagicMock,
        _mock_syncs: MagicMock,
        viewer_client: TestClient,
    ):
        mock_get_details.return_value = [
            _make_run_detail("run_1", datetime(2024, 6, 1, 8, 0, 0)),
            _make_run_detail(
                "run_2", datetime(2024, 6, 2, 8, 0, 0), run_workout_id="rw_1"
            ),
            _make_run_detail(
                "run_3", datetime(2024, 6, 2, 8, 30, 0), run_workout_id="rw_1"
            ),
        ]
        mock_get_workouts.return_value = {"rw_1": _make_workout(id="rw_1")}

        rows = self._csv_rows(viewer_client.get("/cardio-activity-feed/export").text)
        # 1 solo run + 2 workout runs = 3 rows; no aggregate workout row.
        assert len(rows) == 3
        assert all(r["activity_kind"] == "run" for r in rows)
        tagged = [r for r in rows if r["workout_id"] == "rw_1"]
        assert len(tagged) == 2
        assert all(r["workout_title"] == "Speed Workout" for r in tagged)

    @patch("fitness.db.runs.get_all_run_details", return_value=[])
    def test_csv_ride_blanks_run_only_columns(
        self, _mock_get_details: MagicMock, viewer_client: TestClient, monkeypatch
    ):
        monkeypatch.setattr(
            "fitness.db.rides.get_all_ride_details",
            lambda *a, **kw: [_make_ride("ride_1", datetime(2024, 6, 1, 18, 0, 0))],
        )
        rows = self._csv_rows(viewer_client.get("/cardio-activity-feed/export").text)
        assert len(rows) == 1
        row = rows[0]
        assert row["shoes"] == ""
        assert row["notes"] == ""
        assert row["workout_id"] == ""
        assert row["avg_pace_min_per_mile"] == ""  # distance 0

    @patch("fitness.db.runs.get_all_run_details")
    def test_json_format_returns_feed_array(
        self, mock_get_details: MagicMock, viewer_client: TestClient
    ):
        mock_get_details.return_value = [
            _make_run_detail("run_1", datetime(2024, 6, 1, 8, 0, 0)),
        ]
        response = viewer_client.get("/cardio-activity-feed/export?format=json")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        assert "attachment" in response.headers["content-disposition"]
        data = response.json()
        assert isinstance(data, list)
        assert all(item["type"] in {"run", "run_workout", "ride"} for item in data)

    def test_invalid_format_422(self, viewer_client: TestClient):
        response = viewer_client.get("/cardio-activity-feed/export?format=xml")
        assert response.status_code == 422

    def test_requires_auth(self, client: TestClient):
        response = client.get("/cardio-activity-feed/export")
        assert response.status_code == 401
