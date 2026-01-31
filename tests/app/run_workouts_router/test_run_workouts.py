"""Test the /run-workouts and /run-activity-feed endpoints."""

from datetime import datetime
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

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


_DB_MOD = "fitness.app.routers.run_workouts"


class TestCreateRunWorkout:
    """Test POST /run-workouts."""

    @patch(f"{_DB_MOD}.get_all_run_details")
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

    @patch(f"{_DB_MOD}.get_all_run_workouts")
    def test_list_empty(
        self,
        mock_list: MagicMock,
        viewer_client: TestClient,
    ):
        mock_list.return_value = []
        response = viewer_client.get("/run-workouts")
        assert response.status_code == 200
        assert response.json() == []


class TestGetRunWorkout:
    """Test GET /run-workouts/{id}."""

    @patch(f"{_DB_MOD}.get_all_run_details")
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

    @patch(f"{_DB_MOD}.get_all_run_details")
    @patch(f"{_DB_MOD}.get_run_ids_for_workout")
    @patch(f"{_DB_MOD}.update_run_workout")
    def test_update_title(
        self,
        mock_update: MagicMock,
        mock_get_ids: MagicMock,
        mock_get_details: MagicMock,
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

    def test_update_no_fields(self, editor_client: TestClient):
        response = editor_client.patch(
            "/run-workouts/rw_test-1",
            json={},
        )
        assert response.status_code == 400

    @patch(f"{_DB_MOD}.update_run_workout")
    def test_update_not_found(
        self,
        mock_update: MagicMock,
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

    @patch(f"{_DB_MOD}.delete_run_workout")
    def test_delete_success(
        self,
        mock_delete: MagicMock,
        editor_client: TestClient,
    ):
        mock_delete.return_value = True
        response = editor_client.delete("/run-workouts/rw_test-1")
        assert response.status_code == 200

    @patch(f"{_DB_MOD}.delete_run_workout")
    def test_delete_not_found(
        self,
        mock_delete: MagicMock,
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

    @patch(f"{_DB_MOD}.get_all_run_details")
    @patch(f"{_DB_MOD}.get_run_ids_for_workout")
    @patch(f"{_DB_MOD}.get_run_workout_by_id")
    @patch(f"{_DB_MOD}.set_run_workout_runs")
    def test_replace_runs(
        self,
        mock_set: MagicMock,
        mock_get: MagicMock,
        mock_get_ids: MagicMock,
        mock_get_details: MagicMock,
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


class TestActivityFeed:
    """Test GET /run-activity-feed."""

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

        response = viewer_client.get("/run-activity-feed")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(item["type"] == "run" for item in data)

    @patch(f"{_DB_MOD}.get_run_workout_by_id")
    @patch("fitness.db.runs.get_all_run_details")
    def test_workout_grouped(
        self,
        mock_get_details: MagicMock,
        mock_get_workout: MagicMock,
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
        mock_get_workout.return_value = _make_workout(id="rw_1")

        response = viewer_client.get("/run-activity-feed")
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

        response = viewer_client.get("/run-activity-feed?sort_order=desc")
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

        response = viewer_client.get("/run-activity-feed?sort_order=asc")
        assert response.status_code == 200
        data = response.json()
        assert data[0]["item"]["id"] == "run_1"
        assert data[1]["item"]["id"] == "run_2"

    @patch(f"{_DB_MOD}.get_run_workout_by_id")
    @patch("fitness.db.runs.get_all_run_details")
    def test_workout_aggregates(
        self,
        mock_get_details: MagicMock,
        mock_get_workout: MagicMock,
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
        mock_get_workout.return_value = _make_workout(id="rw_1")

        response = viewer_client.get("/run-activity-feed")
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
