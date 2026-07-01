"""Tests for the PUT /rides/{ride_id}/tags endpoint."""

from datetime import datetime
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from fitness.models import Ride
from fitness.models.tag import Tag

_MOD = "fitness.app.routers.ride"


def _ride() -> Ride:
    return Ride(
        id="test_ride_123",
        datetime_utc=datetime(2024, 1, 15, 10, 0, 0),
        type="Outdoor Ride",
        distance=10.0,
        duration=1800.0,
        source="Strava",
        avg_heart_rate=130.0,
    )


def _tag(id: str, name: str) -> Tag:
    return Tag(id=id, name=name, created_at=datetime(2026, 6, 18, 12, 0, 0))


class TestSetRideTags:
    @patch(f"{_MOD}.set_ride_tags")
    @patch(f"{_MOD}.get_ride_by_id")
    def test_replaces_set(
        self,
        mock_get_ride: MagicMock,
        mock_set: MagicMock,
        auth_client: TestClient,
    ):
        mock_get_ride.return_value = _ride()
        mock_set.return_value = [_tag("tag_1", "Crit"), _tag("tag_2", "Endurance")]
        res = auth_client.put(
            "/rides/test_ride_123/tags", json={"tag_ids": ["tag_1", "tag_2"]}
        )
        assert res.status_code == 200
        assert [t["name"] for t in res.json()] == ["Crit", "Endurance"]
        mock_set.assert_called_once_with("test_ride_123", ["tag_1", "tag_2"])

    @patch(f"{_MOD}.set_ride_tags")
    @patch(f"{_MOD}.get_ride_by_id")
    def test_unknown_tag_id_400(
        self,
        mock_get_ride: MagicMock,
        mock_set: MagicMock,
        auth_client: TestClient,
    ):
        mock_get_ride.return_value = _ride()
        mock_set.side_effect = ValueError("Unknown tag id(s): tag_ghost")
        res = auth_client.put(
            "/rides/test_ride_123/tags", json={"tag_ids": ["tag_ghost"]}
        )
        assert res.status_code == 400

    @patch(f"{_MOD}.set_ride_tags")
    @patch(f"{_MOD}.get_ride_by_id", return_value=None)
    def test_unknown_ride_404(
        self,
        _mock_get_ride: MagicMock,
        mock_set: MagicMock,
        auth_client: TestClient,
    ):
        res = auth_client.put("/rides/missing/tags", json={"tag_ids": ["tag_1"]})
        assert res.status_code == 404
        mock_set.assert_not_called()

    def test_requires_editor(self, viewer_client: TestClient):
        res = viewer_client.put(
            "/rides/test_ride_123/tags", json={"tag_ids": ["tag_1"]}
        )
        assert res.status_code == 403

    def test_requires_auth(self, client: TestClient):
        res = client.put("/rides/test_ride_123/tags", json={"tag_ids": ["tag_1"]})
        assert res.status_code == 401
