"""Tests for the PUT /runs/{run_id}/tags endpoint."""

from datetime import datetime
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from fitness.models import Run
from fitness.models.tag import Tag

_MOD = "fitness.app.routers.run"


def _run() -> Run:
    return Run(
        id="test_run_123",
        datetime_utc=datetime(2024, 1, 15, 10, 0, 0),
        type="Outdoor Run",
        distance=5.0,
        duration=1800.0,
        source="Strava",
        avg_heart_rate=150.0,
        shoe_id="nike_pegasus_38",
    )


def _tag(id: str, name: str) -> Tag:
    return Tag(id=id, name=name, created_at=datetime(2026, 6, 18, 12, 0, 0))


class TestSetRunTags:
    @patch(f"{_MOD}.set_run_tags")
    @patch(f"{_MOD}.get_run_by_id")
    def test_replaces_set(
        self,
        mock_get_run: MagicMock,
        mock_set: MagicMock,
        auth_client: TestClient,
    ):
        mock_get_run.return_value = _run()
        mock_set.return_value = [_tag("tag_1", "Hills"), _tag("tag_2", "Speedwork")]
        res = auth_client.put(
            "/runs/test_run_123/tags", json={"tag_ids": ["tag_1", "tag_2"]}
        )
        assert res.status_code == 200
        assert [t["name"] for t in res.json()] == ["Hills", "Speedwork"]
        mock_set.assert_called_once_with("test_run_123", ["tag_1", "tag_2"])

    @patch(f"{_MOD}.set_run_tags")
    @patch(f"{_MOD}.get_run_by_id")
    def test_unknown_tag_id_400(
        self,
        mock_get_run: MagicMock,
        mock_set: MagicMock,
        auth_client: TestClient,
    ):
        mock_get_run.return_value = _run()
        mock_set.side_effect = ValueError("Unknown tag id(s): tag_ghost")
        res = auth_client.put(
            "/runs/test_run_123/tags", json={"tag_ids": ["tag_ghost"]}
        )
        assert res.status_code == 400

    @patch(f"{_MOD}.set_run_tags")
    @patch(f"{_MOD}.get_run_by_id", return_value=None)
    def test_unknown_run_404(
        self,
        _mock_get_run: MagicMock,
        mock_set: MagicMock,
        auth_client: TestClient,
    ):
        res = auth_client.put("/runs/missing/tags", json={"tag_ids": ["tag_1"]})
        assert res.status_code == 404
        mock_set.assert_not_called()

    def test_requires_editor(self, viewer_client: TestClient):
        res = viewer_client.put("/runs/test_run_123/tags", json={"tag_ids": ["tag_1"]})
        assert res.status_code == 403

    def test_requires_auth(self, client: TestClient):
        res = client.put("/runs/test_run_123/tags", json={"tag_ids": ["tag_1"]})
        assert res.status_code == 401
