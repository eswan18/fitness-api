"""Test the /shoes/{shoe_id}/notes endpoints."""

from datetime import date, datetime
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from fitness.models.shoe import Shoe
from fitness.models.shoe_note import ShoeNote


# --- Helpers ---

_SHOE_ID = "nike_pegasus_41"
_MOD = "fitness.app.routers.shoe_notes"


def _make_shoe(
    id: str = _SHOE_ID, brand: str = "Nike", model: str = "Pegasus 41"
) -> Shoe:
    return Shoe(id=id, brand=brand, model=model)


def _make_note(
    id: str = "sn_1",
    shoe_id: str = _SHOE_ID,
    note_date: date | None = None,
    content: str = "Felt springy today",
) -> ShoeNote:
    return ShoeNote(
        id=id,
        shoe_id=shoe_id,
        note_date=note_date or date(2026, 6, 18),
        content=content,
        created_at=datetime(2026, 6, 18, 12, 0, 0),
        updated_at=datetime(2026, 6, 18, 12, 0, 0),
    )


class TestListShoeNotes:
    """GET /shoes/{shoe_id}/notes."""

    @patch(f"{_MOD}.get_shoe_notes")
    @patch(f"{_MOD}.get_shoe_by_id")
    def test_list_success(
        self,
        mock_get_shoe: MagicMock,
        mock_get_notes: MagicMock,
        viewer_client: TestClient,
    ):
        mock_get_shoe.return_value = _make_shoe()
        mock_get_notes.return_value = [
            _make_note("sn_2", note_date=date(2026, 6, 18), content="Newer"),
            _make_note("sn_1", note_date=date(2026, 5, 2), content="Older"),
        ]

        res = viewer_client.get(f"/shoes/{_SHOE_ID}/notes")

        assert res.status_code == 200
        data = res.json()
        assert [n["id"] for n in data] == ["sn_2", "sn_1"]
        assert data[0]["note_date"] == "2026-06-18"
        assert data[0]["content"] == "Newer"
        mock_get_notes.assert_called_once_with(_SHOE_ID)

    @patch(f"{_MOD}.get_shoe_by_id")
    def test_list_shoe_not_found(
        self, mock_get_shoe: MagicMock, viewer_client: TestClient
    ):
        mock_get_shoe.return_value = None
        res = viewer_client.get(f"/shoes/{_SHOE_ID}/notes")
        assert res.status_code == 404

    def test_list_requires_auth(self, client: TestClient):
        res = client.get(f"/shoes/{_SHOE_ID}/notes")
        assert res.status_code == 401


class TestCreateShoeNote:
    """POST /shoes/{shoe_id}/notes."""

    @patch(f"{_MOD}.create_shoe_note")
    def test_create_success(
        self, mock_create: MagicMock, editor_client: TestClient
    ):
        mock_create.return_value = _make_note(content="Backfilled note")
        res = editor_client.post(
            f"/shoes/{_SHOE_ID}/notes",
            json={"content": "Backfilled note", "note_date": "2026-06-18"},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["content"] == "Backfilled note"
        assert data["shoe_id"] == _SHOE_ID
        mock_create.assert_called_once_with(
            _SHOE_ID, note_date=date(2026, 6, 18), content="Backfilled note"
        )

    @patch(f"{_MOD}.create_shoe_note")
    def test_create_defaults_to_today(
        self, mock_create: MagicMock, editor_client: TestClient
    ):
        mock_create.return_value = _make_note()
        res = editor_client.post(
            f"/shoes/{_SHOE_ID}/notes", json={"content": "No date given"}
        )
        assert res.status_code == 201
        _, kwargs = mock_create.call_args
        assert kwargs["note_date"] == date.today()

    @patch(f"{_MOD}.create_shoe_note")
    def test_create_trims_content(
        self, mock_create: MagicMock, editor_client: TestClient
    ):
        mock_create.return_value = _make_note()
        editor_client.post(
            f"/shoes/{_SHOE_ID}/notes", json={"content": "  spaced  "}
        )
        _, kwargs = mock_create.call_args
        assert kwargs["content"] == "spaced"

    @patch(f"{_MOD}.create_shoe_note")
    def test_create_empty_content_rejected(
        self, mock_create: MagicMock, editor_client: TestClient
    ):
        res = editor_client.post(
            f"/shoes/{_SHOE_ID}/notes", json={"content": "   "}
        )
        assert res.status_code == 400
        mock_create.assert_not_called()

    @patch(f"{_MOD}.create_shoe_note")
    def test_create_shoe_not_found(
        self, mock_create: MagicMock, editor_client: TestClient
    ):
        mock_create.side_effect = ValueError("Shoe 'ghost' not found")
        res = editor_client.post(
            f"/shoes/{_SHOE_ID}/notes", json={"content": "hi"}
        )
        assert res.status_code == 404

    def test_create_requires_editor(self, viewer_client: TestClient):
        res = viewer_client.post(
            f"/shoes/{_SHOE_ID}/notes", json={"content": "hi"}
        )
        assert res.status_code == 403

    def test_create_requires_auth(self, client: TestClient):
        res = client.post(f"/shoes/{_SHOE_ID}/notes", json={"content": "hi"})
        assert res.status_code == 401


class TestPatchShoeNote:
    """PATCH /shoes/{shoe_id}/notes/{note_id}."""

    @patch(f"{_MOD}.update_shoe_note")
    @patch(f"{_MOD}.get_shoe_note_by_id")
    def test_patch_success(
        self,
        mock_get: MagicMock,
        mock_update: MagicMock,
        editor_client: TestClient,
    ):
        mock_get.return_value = _make_note()
        mock_update.return_value = _make_note(content="Edited")
        res = editor_client.patch(
            f"/shoes/{_SHOE_ID}/notes/sn_1", json={"content": "Edited"}
        )
        assert res.status_code == 200
        assert res.json()["content"] == "Edited"
        mock_update.assert_called_once_with(
            "sn_1", note_date=None, content="Edited"
        )

    def test_patch_no_fields(self, editor_client: TestClient):
        res = editor_client.patch(f"/shoes/{_SHOE_ID}/notes/sn_1", json={})
        assert res.status_code == 400

    @patch(f"{_MOD}.get_shoe_note_by_id")
    def test_patch_not_found(
        self, mock_get: MagicMock, editor_client: TestClient
    ):
        mock_get.return_value = None
        res = editor_client.patch(
            f"/shoes/{_SHOE_ID}/notes/sn_1", json={"content": "x"}
        )
        assert res.status_code == 404

    @patch(f"{_MOD}.get_shoe_note_by_id")
    def test_patch_wrong_shoe(
        self, mock_get: MagicMock, editor_client: TestClient
    ):
        mock_get.return_value = _make_note(shoe_id="some_other_shoe")
        res = editor_client.patch(
            f"/shoes/{_SHOE_ID}/notes/sn_1", json={"content": "x"}
        )
        assert res.status_code == 404

    def test_patch_empty_content_rejected(self, editor_client: TestClient):
        res = editor_client.patch(
            f"/shoes/{_SHOE_ID}/notes/sn_1", json={"content": "   "}
        )
        assert res.status_code == 400

    def test_patch_requires_editor(self, viewer_client: TestClient):
        res = viewer_client.patch(
            f"/shoes/{_SHOE_ID}/notes/sn_1", json={"content": "x"}
        )
        assert res.status_code == 403


class TestDeleteShoeNote:
    """DELETE /shoes/{shoe_id}/notes/{note_id}."""

    @patch(f"{_MOD}.delete_shoe_note")
    @patch(f"{_MOD}.get_shoe_note_by_id")
    def test_delete_success(
        self,
        mock_get: MagicMock,
        mock_delete: MagicMock,
        editor_client: TestClient,
    ):
        mock_get.return_value = _make_note()
        mock_delete.return_value = True
        res = editor_client.delete(f"/shoes/{_SHOE_ID}/notes/sn_1")
        assert res.status_code == 200
        assert "deleted" in res.json()["message"]
        mock_delete.assert_called_once_with("sn_1")

    @patch(f"{_MOD}.get_shoe_note_by_id")
    def test_delete_not_found(
        self, mock_get: MagicMock, editor_client: TestClient
    ):
        mock_get.return_value = None
        res = editor_client.delete(f"/shoes/{_SHOE_ID}/notes/sn_1")
        assert res.status_code == 404

    def test_delete_requires_editor(self, viewer_client: TestClient):
        res = viewer_client.delete(f"/shoes/{_SHOE_ID}/notes/sn_1")
        assert res.status_code == 403
