"""Tests for /sync/rides/* endpoints."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from fitness.models import Ride
from fitness.models.sync import SyncedRide


@pytest.fixture
def outdoor_ride() -> Ride:
    return Ride(
        id="strava_ride_1",
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
        id="strava_ride_2",
        datetime_utc=datetime(2024, 6, 1, 18, 0, 0),
        type="Indoor Ride",
        distance=0.0,
        duration=3600,
        source="Strava",
        avg_heart_rate=145.0,
    )


def _synced_ride_record(ride_id: str, status: str = "synced") -> SyncedRide:
    now = datetime.now(timezone.utc)
    return SyncedRide(
        id=1,
        ride_id=ride_id,
        ride_version=1,
        google_event_id="evt_abc123",
        synced_at=now,
        sync_status=status,  # ty: ignore[invalid-argument-type]
        error_message=None,
        created_at=now,
        updated_at=now,
    )


class TestSyncRide:
    @patch("fitness.app.routers.ride_sync.create_synced_ride")
    @patch("fitness.app.routers._sync_helpers.GoogleCalendarClient")
    @patch("fitness.app.routers.ride_sync.get_synced_ride")
    @patch("fitness.app.routers.ride_sync.get_ride_by_id")
    def test_sync_outdoor_ride_creates_event_with_outdoor_title(
        self,
        mock_get: MagicMock,
        mock_get_synced: MagicMock,
        mock_client_cls: MagicMock,
        mock_create_record: MagicMock,
        outdoor_ride: Ride,
        editor_client: TestClient,
    ):
        mock_get.return_value = outdoor_ride
        mock_get_synced.return_value = None
        client_instance = MagicMock()
        client_instance.create_ride_event.return_value = "evt_abc123"
        mock_client_cls.return_value = client_instance
        mock_create_record.return_value = _synced_ride_record(outdoor_ride.id)

        response = editor_client.post(f"/sync/rides/{outdoor_ride.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["google_event_id"] == "evt_abc123"
        client_instance.create_ride_event.assert_called_once_with(outdoor_ride)
        mock_create_record.assert_called_once()

    @patch("fitness.app.routers.ride_sync.get_synced_ride")
    @patch("fitness.app.routers.ride_sync.get_ride_by_id")
    def test_sync_404_when_ride_missing(
        self,
        mock_get: MagicMock,
        mock_get_synced: MagicMock,
        editor_client: TestClient,
    ):
        mock_get.return_value = None
        mock_get_synced.return_value = None
        response = editor_client.post("/sync/rides/strava_missing")
        assert response.status_code == 404

    @patch("fitness.app.routers.ride_sync.get_synced_ride")
    @patch("fitness.app.routers.ride_sync.get_ride_by_id")
    def test_sync_already_synced_returns_no_op(
        self,
        mock_get: MagicMock,
        mock_get_synced: MagicMock,
        outdoor_ride: Ride,
        editor_client: TestClient,
    ):
        mock_get.return_value = outdoor_ride
        mock_get_synced.return_value = _synced_ride_record(outdoor_ride.id)

        response = editor_client.post(f"/sync/rides/{outdoor_ride.id}")
        assert response.status_code == 200
        assert response.json()["success"] is False
        assert "already synced" in response.json()["message"].lower()


class TestUnsyncRide:
    @patch("fitness.app.routers.ride_sync.delete_synced_ride")
    @patch("fitness.app.routers._sync_helpers.GoogleCalendarClient")
    @patch("fitness.app.routers.ride_sync.get_synced_ride")
    def test_unsync_calls_calendar_delete_and_removes_record(
        self,
        mock_get_synced: MagicMock,
        mock_client_cls: MagicMock,
        mock_delete_record: MagicMock,
        editor_client: TestClient,
    ):
        mock_get_synced.return_value = _synced_ride_record("strava_ride_1")
        client_instance = MagicMock()
        client_instance.delete_workout_event.return_value = True
        mock_client_cls.return_value = client_instance
        mock_delete_record.return_value = True

        response = editor_client.delete("/sync/rides/strava_ride_1")
        assert response.status_code == 200
        assert response.json()["success"] is True
        client_instance.delete_workout_event.assert_called_once_with("evt_abc123")
        mock_delete_record.assert_called_once()

    @patch("fitness.app.routers.ride_sync.get_synced_ride")
    def test_unsync_404_when_not_synced(
        self,
        mock_get_synced: MagicMock,
        editor_client: TestClient,
    ):
        mock_get_synced.return_value = None
        response = editor_client.delete("/sync/rides/strava_unsynced")
        assert response.status_code == 404


class TestSyncStatus:
    @patch("fitness.app.routers.ride_sync.get_synced_ride")
    def test_status_unsynced(
        self, mock_get_synced: MagicMock, viewer_client: TestClient
    ):
        mock_get_synced.return_value = None
        response = viewer_client.get("/sync/rides/strava_x/status")
        assert response.status_code == 200
        assert response.json()["is_synced"] is False

    @patch("fitness.app.routers.ride_sync.get_synced_ride")
    def test_status_synced(
        self, mock_get_synced: MagicMock, viewer_client: TestClient
    ):
        mock_get_synced.return_value = _synced_ride_record("strava_x")
        response = viewer_client.get("/sync/rides/strava_x/status")
        body = response.json()
        assert body["is_synced"] is True
        assert body["google_event_id"] == "evt_abc123"


def test_sync_requires_editor(viewer_client: TestClient):
    response = viewer_client.post("/sync/rides/strava_x")
    assert response.status_code == 403


def test_create_ride_event_title_for_indoor(indoor_ride: Ride):
    """Smoke-test the event title format without actually hitting Google."""
    from fitness.integrations.google.calendar_client import GoogleCalendarClient

    client = GoogleCalendarClient.__new__(GoogleCalendarClient)
    client.base_url = "https://example.invalid"
    client.calendar_id = "primary"
    captured = {}

    def fake_request(method, url, **kwargs):
        captured["json"] = kwargs.get("json")
        return MagicMock(status_code=200, json=lambda: {"id": "evt_zzz"})

    client._make_request = fake_request
    client.create_ride_event(indoor_ride)
    assert captured["json"]["summary"] == "Indoor Bike Ride"


def test_create_ride_event_title_for_outdoor(outdoor_ride: Ride):
    from fitness.integrations.google.calendar_client import GoogleCalendarClient

    client = GoogleCalendarClient.__new__(GoogleCalendarClient)
    client.base_url = "https://example.invalid"
    client.calendar_id = "primary"
    captured = {}

    def fake_request(method, url, **kwargs):
        captured["json"] = kwargs.get("json")
        return MagicMock(status_code=200, json=lambda: {"id": "evt_zzz"})

    client._make_request = fake_request
    client.create_ride_event(outdoor_ride)
    assert captured["json"]["summary"] == "Outdoor Bike Ride"
    assert "12.00 mi" in captured["json"]["description"]
