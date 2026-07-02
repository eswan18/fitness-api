"""Tests for the PATCH /rides/{ride_id} endpoint."""

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from fitness.models import Ride


@pytest.fixture
def outdoor_ride() -> Ride:
    return Ride(
        id="strava_999",
        datetime_utc=datetime(2024, 6, 1, 14, 0, 0),
        type="Outdoor Ride",
        distance=12.0,
        duration=2700,
        source="Strava",
        avg_heart_rate=140.0,
    )


@pytest.fixture
def indoor_ride() -> Ride:
    return Ride(
        id="strava_1000",
        datetime_utc=datetime(2024, 6, 2, 18, 0, 0),
        type="Indoor Ride",
        distance=0.0,
        duration=3600,
        source="Strava",
        avg_heart_rate=145.0,
    )


class TestUpdateRide:
    @patch("fitness.app.routers.ride.update_ride")
    @patch("fitness.app.routers.ride.get_ride_by_id")
    def test_update_duration_and_hr(
        self,
        mock_get: MagicMock,
        mock_update: MagicMock,
        outdoor_ride: Ride,
        editor_client: TestClient,
    ):
        mock_get.return_value = outdoor_ride
        updated = outdoor_ride.model_copy(
            update={"duration": 3000.0, "avg_heart_rate": 150.0}
        )
        mock_update.return_value = updated

        response = editor_client.patch(
            f"/rides/{outdoor_ride.id}",
            json={"duration": 3000, "avg_heart_rate": 150},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["ride"]["duration"] == 3000
        assert body["ride"]["avg_heart_rate"] == 150
        mock_update.assert_called_once_with(
            outdoor_ride.id, {"duration": 3000.0, "avg_heart_rate": 150.0}
        )

    @patch("fitness.app.routers.ride.get_ride_by_id")
    def test_404_when_ride_missing(
        self,
        mock_get: MagicMock,
        editor_client: TestClient,
    ):
        mock_get.return_value = None

        response = editor_client.patch(
            "/rides/strava_does_not_exist",
            json={"duration": 1800},
        )
        assert response.status_code == 404

    @patch("fitness.app.routers.ride.get_ride_by_id")
    def test_400_when_no_fields(
        self,
        mock_get: MagicMock,
        outdoor_ride: Ride,
        editor_client: TestClient,
    ):
        mock_get.return_value = outdoor_ride

        response = editor_client.patch(f"/rides/{outdoor_ride.id}", json={})
        assert response.status_code == 400

    @patch("fitness.app.routers.ride.get_ride_by_id")
    def test_400_when_outdoor_distance_zero(
        self,
        mock_get: MagicMock,
        outdoor_ride: Ride,
        editor_client: TestClient,
    ):
        """Cannot leave an Outdoor Ride with distance=0."""
        mock_get.return_value = outdoor_ride

        response = editor_client.patch(
            f"/rides/{outdoor_ride.id}",
            json={"distance": 0},
        )
        assert response.status_code == 400
        assert "distance" in response.json()["detail"].lower()

    @patch("fitness.app.routers.ride.update_ride")
    @patch("fitness.app.routers.ride.get_ride_by_id")
    def test_400_when_switching_to_outdoor_without_distance(
        self,
        mock_get: MagicMock,
        mock_update: MagicMock,
        indoor_ride: Ride,
        editor_client: TestClient,
    ):
        """Switching Indoor → Outdoor without supplying a distance is rejected."""
        mock_get.return_value = indoor_ride

        response = editor_client.patch(
            f"/rides/{indoor_ride.id}",
            json={"type": "Outdoor Ride"},
        )
        assert response.status_code == 400
        mock_update.assert_not_called()

    @patch("fitness.app.routers.ride.update_ride")
    @patch("fitness.app.routers.ride.get_ride_by_id")
    def test_switching_to_outdoor_with_distance_succeeds(
        self,
        mock_get: MagicMock,
        mock_update: MagicMock,
        indoor_ride: Ride,
        editor_client: TestClient,
    ):
        mock_get.return_value = indoor_ride
        updated = indoor_ride.model_copy(
            update={"type": "Outdoor Ride", "distance": 14.5}
        )
        mock_update.return_value = updated

        response = editor_client.patch(
            f"/rides/{indoor_ride.id}",
            json={"type": "Outdoor Ride", "distance": 14.5},
        )
        assert response.status_code == 200
        assert response.json()["ride"]["type"] == "Outdoor Ride"
        assert response.json()["ride"]["distance"] == 14.5

    @patch("fitness.app.routers.ride.update_ride")
    @patch("fitness.app.routers.ride.get_ride_by_id")
    def test_switching_to_indoor_zeros_distance(
        self,
        mock_get: MagicMock,
        mock_update: MagicMock,
        outdoor_ride: Ride,
        editor_client: TestClient,
    ):
        """Indoor Ride with distance=0 passes validation; client is responsible
        for sending distance=0 alongside the type switch."""
        mock_get.return_value = outdoor_ride
        updated = outdoor_ride.model_copy(
            update={"type": "Indoor Ride", "distance": 0.0}
        )
        mock_update.return_value = updated

        response = editor_client.patch(
            f"/rides/{outdoor_ride.id}",
            json={"type": "Indoor Ride", "distance": 0},
        )
        assert response.status_code == 200
        assert response.json()["ride"]["type"] == "Indoor Ride"
        assert response.json()["ride"]["distance"] == 0

    def test_requires_editor(self, viewer_client: TestClient):
        response = viewer_client.patch("/rides/x", json={"duration": 1800})
        assert response.status_code == 403

    @patch("fitness.app.routers.ride.update_ride")
    @patch("fitness.app.routers.ride.get_ride_by_id")
    def test_set_name(
        self,
        mock_get: MagicMock,
        mock_update: MagicMock,
        outdoor_ride: Ride,
        editor_client: TestClient,
    ):
        mock_get.return_value = outdoor_ride
        updated = outdoor_ride.model_copy(update={"name": "Sunday Century"})
        mock_update.return_value = updated

        response = editor_client.patch(
            f"/rides/{outdoor_ride.id}", json={"name": "Sunday Century"}
        )

        assert response.status_code == 200
        assert response.json()["ride"]["name"] == "Sunday Century"
        mock_update.assert_called_once_with(
            outdoor_ride.id, {"name": "Sunday Century"}
        )

    @patch("fitness.app.routers.ride.update_ride")
    @patch("fitness.app.routers.ride.get_ride_by_id")
    def test_blank_name_clears_to_null(
        self,
        mock_get: MagicMock,
        mock_update: MagicMock,
        outdoor_ride: Ride,
        editor_client: TestClient,
    ):
        mock_get.return_value = outdoor_ride
        updated = outdoor_ride.model_copy(update={"name": None})
        mock_update.return_value = updated

        response = editor_client.patch(
            f"/rides/{outdoor_ride.id}", json={"name": "   "}
        )

        assert response.status_code == 200
        mock_update.assert_called_once_with(outdoor_ride.id, {"name": None})

    @patch("fitness.app.routers.ride.update_ride")
    @patch("fitness.app.routers.ride.get_ride_by_id")
    def test_null_name_clears_to_null(
        self,
        mock_get: MagicMock,
        mock_update: MagicMock,
        outdoor_ride: Ride,
        editor_client: TestClient,
    ):
        mock_get.return_value = outdoor_ride
        updated = outdoor_ride.model_copy(update={"name": None})
        mock_update.return_value = updated

        response = editor_client.patch(
            f"/rides/{outdoor_ride.id}", json={"name": None}
        )

        assert response.status_code == 200
        mock_update.assert_called_once_with(outdoor_ride.id, {"name": None})

    @patch("fitness.app.routers.ride.update_ride")
    @patch("fitness.app.routers.ride.get_ride_by_id")
    def test_omitted_name_leaves_it_unchanged(
        self,
        mock_get: MagicMock,
        mock_update: MagicMock,
        outdoor_ride: Ride,
        editor_client: TestClient,
    ):
        """Editing another field without touching `name` must not clear it."""
        mock_get.return_value = outdoor_ride
        updated = outdoor_ride.model_copy(update={"duration": 3000.0})
        mock_update.return_value = updated

        response = editor_client.patch(
            f"/rides/{outdoor_ride.id}", json={"duration": 3000}
        )

        assert response.status_code == 200
        mock_update.assert_called_once_with(outdoor_ride.id, {"duration": 3000.0})

    @patch("fitness.app.routers.ride.get_ride_by_id")
    def test_rejects_invalid_type(
        self,
        mock_get: MagicMock,
        outdoor_ride: Ride,
        editor_client: TestClient,
    ):
        mock_get.return_value = outdoor_ride

        response = editor_client.patch(
            f"/rides/{outdoor_ride.id}",
            json={"type": "Outdoor Run"},
        )
        assert response.status_code == 422
