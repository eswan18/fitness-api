"""Tests for the PATCH /rides/{ride_id}/name endpoint."""

from datetime import datetime
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from fitness.models import Ride

_MOD = "fitness.app.routers.ride"


def _ride(name: str | None = None) -> Ride:
    return Ride(
        id="strava_999",
        datetime_utc=datetime(2024, 6, 1, 14, 0, 0),
        type="Outdoor Ride",
        distance=12.0,
        duration=2700.0,
        source="Strava",
        avg_heart_rate=140.0,
        name=name,
    )


class TestUpdateRideName:
    @patch(f"{_MOD}.update_ride_name", return_value=True)
    @patch(f"{_MOD}.get_ride_by_id")
    def test_set_name_success(
        self,
        mock_get_ride: MagicMock,
        mock_update: MagicMock,
        auth_client: TestClient,
    ):
        mock_get_ride.return_value = _ride(name="Sunday Century")
        res = auth_client.patch(
            "/rides/strava_999/name", json={"name": "Sunday Century"}
        )
        assert res.status_code == 200
        assert res.json()["id"] == "strava_999"
        mock_update.assert_called_once_with("strava_999", "Sunday Century")

    @patch(f"{_MOD}.update_ride_name", return_value=True)
    @patch(f"{_MOD}.get_ride_by_id")
    def test_blank_name_clears_to_null(
        self,
        mock_get_ride: MagicMock,
        mock_update: MagicMock,
        auth_client: TestClient,
    ):
        mock_get_ride.return_value = _ride()
        res = auth_client.patch("/rides/strava_999/name", json={"name": "   "})
        assert res.status_code == 200
        mock_update.assert_called_once_with("strava_999", None)

    @patch(f"{_MOD}.update_ride_name", return_value=True)
    @patch(f"{_MOD}.get_ride_by_id")
    def test_null_name_clears_to_null(
        self,
        mock_get_ride: MagicMock,
        mock_update: MagicMock,
        auth_client: TestClient,
    ):
        mock_get_ride.return_value = _ride()
        res = auth_client.patch("/rides/strava_999/name", json={"name": None})
        assert res.status_code == 200
        mock_update.assert_called_once_with("strava_999", None)

    @patch(f"{_MOD}.update_ride_name")
    @patch(f"{_MOD}.get_ride_by_id", return_value=None)
    def test_404_when_ride_missing(
        self,
        _mock_get_ride: MagicMock,
        mock_update: MagicMock,
        auth_client: TestClient,
    ):
        res = auth_client.patch(
            "/rides/missing/name", json={"name": "hi"}
        )
        assert res.status_code == 404
        mock_update.assert_not_called()

    def test_requires_editor(self, viewer_client: TestClient):
        res = viewer_client.patch(
            "/rides/strava_999/name", json={"name": "hi"}
        )
        assert res.status_code == 403

    def test_requires_auth(self, client: TestClient):
        res = client.patch("/rides/strava_999/name", json={"name": "hi"})
        assert res.status_code == 401
