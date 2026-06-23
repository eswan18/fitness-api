"""Tests for the PATCH /runs/{run_id}/notes endpoint."""

from datetime import datetime
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from fitness.models import Run

_MOD = "fitness.app.routers.run"


def _run(notes: str | None = None) -> Run:
    return Run(
        id="test_run_123",
        datetime_utc=datetime(2024, 1, 15, 10, 0, 0),
        type="Outdoor Run",
        distance=5.0,
        duration=1800.0,
        source="Strava",
        avg_heart_rate=150.0,
        shoe_id="nike_pegasus_38",
        notes=notes,
    )


class TestUpdateRunNotes:
    @patch(f"{_MOD}.update_run_notes", return_value=True)
    @patch(f"{_MOD}.get_run_by_id")
    def test_set_note_success(
        self,
        mock_get_run: MagicMock,
        mock_update: MagicMock,
        auth_client: TestClient,
    ):
        mock_get_run.return_value = _run(notes="Felt **great**")
        res = auth_client.patch(
            "/runs/test_run_123/notes", json={"notes": "Felt **great**"}
        )
        assert res.status_code == 200
        assert res.json()["id"] == "test_run_123"
        mock_update.assert_called_once_with("test_run_123", "Felt **great**")

    @patch(f"{_MOD}.update_run_notes", return_value=True)
    @patch(f"{_MOD}.get_run_by_id")
    def test_blank_note_clears_to_null(
        self,
        mock_get_run: MagicMock,
        mock_update: MagicMock,
        auth_client: TestClient,
    ):
        mock_get_run.return_value = _run()
        res = auth_client.patch(
            "/runs/test_run_123/notes", json={"notes": "   "}
        )
        assert res.status_code == 200
        mock_update.assert_called_once_with("test_run_123", None)

    @patch(f"{_MOD}.update_run_notes", return_value=True)
    @patch(f"{_MOD}.get_run_by_id")
    def test_null_note_clears_to_null(
        self,
        mock_get_run: MagicMock,
        mock_update: MagicMock,
        auth_client: TestClient,
    ):
        mock_get_run.return_value = _run()
        res = auth_client.patch("/runs/test_run_123/notes", json={"notes": None})
        assert res.status_code == 200
        mock_update.assert_called_once_with("test_run_123", None)

    @patch(f"{_MOD}.update_run_notes")
    @patch(f"{_MOD}.get_run_by_id", return_value=None)
    def test_404_when_run_missing(
        self,
        _mock_get_run: MagicMock,
        mock_update: MagicMock,
        auth_client: TestClient,
    ):
        res = auth_client.patch(
            "/runs/missing/notes", json={"notes": "hi"}
        )
        assert res.status_code == 404
        mock_update.assert_not_called()

    @patch(f"{_MOD}.update_run_notes", return_value=True)
    @patch(f"{_MOD}.is_run_synced", return_value=True)
    @patch(f"{_MOD}.get_run_by_id")
    def test_allowed_on_synced_run(
        self,
        mock_get_run: MagicMock,
        _mock_synced: MagicMock,
        mock_update: MagicMock,
        auth_client: TestClient,
    ):
        # Notes are editable even on calendar-synced runs (no _reject_if_synced).
        mock_get_run.return_value = _run(notes="note")
        res = auth_client.patch(
            "/runs/test_run_123/notes", json={"notes": "note"}
        )
        assert res.status_code == 200
        mock_update.assert_called_once_with("test_run_123", "note")

    def test_requires_editor(self, viewer_client: TestClient):
        res = viewer_client.patch(
            "/runs/test_run_123/notes", json={"notes": "hi"}
        )
        assert res.status_code == 403

    def test_requires_auth(self, client: TestClient):
        res = client.patch("/runs/test_run_123/notes", json={"notes": "hi"})
        assert res.status_code == 401
