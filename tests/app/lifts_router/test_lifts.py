"""Test the /lifts endpoints."""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from tests._factories.lift import LiftFactory


class TestGetLifts:
    """Test GET /lifts endpoint."""

    @patch("fitness.app.routers.lifts.get_all_lifts")
    def test_get_lifts_returns_list(
        self,
        mock_get_lifts: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that get lifts returns lift summaries."""
        workout_factory = LiftFactory()
        # DB returns prefixed IDs
        workout = workout_factory.make({"id": "hevy_100", "title": "Push Day"})

        mock_get_lifts.return_value = [workout]

        response = viewer_client.get("/lifts")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["lifts"]) == 1
        assert data["lifts"][0]["id"] == "hevy_100"
        assert data["lifts"][0]["title"] == "Push Day"

    @patch("fitness.app.routers.lifts.get_all_lifts")
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

    def test_get_lifts_stats_requires_auth(self, client: TestClient):
        """Test that lift stats endpoint requires authentication."""
        response = client.get("/lifts/stats")
        assert response.status_code == 401
