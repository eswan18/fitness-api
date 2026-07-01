"""Test the /tags CRUD endpoints."""

from datetime import datetime
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from fitness.models.tag import Tag

_MOD = "fitness.app.routers.tags"


def _make_tag(id: str = "tag_1", name: str = "Speedwork") -> Tag:
    return Tag(id=id, name=name, created_at=datetime(2026, 6, 18, 12, 0, 0))


class TestListTags:
    """GET /tags."""

    @patch(f"{_MOD}.get_all_tags")
    def test_list_success(self, mock_get_all: MagicMock, viewer_client: TestClient):
        mock_get_all.return_value = [
            _make_tag("tag_1", "Hills"),
            _make_tag("tag_2", "Speedwork"),
        ]
        res = viewer_client.get("/tags")
        assert res.status_code == 200
        data = res.json()
        assert [t["name"] for t in data] == ["Hills", "Speedwork"]

    def test_requires_auth(self, client: TestClient):
        res = client.get("/tags")
        assert res.status_code == 401


class TestCreateTag:
    """POST /tags."""

    @patch(f"{_MOD}.create_tag")
    def test_create_success(self, mock_create: MagicMock, editor_client: TestClient):
        mock_create.return_value = _make_tag(name="Hills")
        res = editor_client.post("/tags", json={"name": "Hills"})
        assert res.status_code == 201
        assert res.json()["name"] == "Hills"
        mock_create.assert_called_once_with("Hills")

    @patch(f"{_MOD}.create_tag")
    def test_create_strips_name(
        self, mock_create: MagicMock, editor_client: TestClient
    ):
        mock_create.return_value = _make_tag(name="Hills")
        editor_client.post("/tags", json={"name": "  Hills  "})
        mock_create.assert_called_once_with("Hills")

    @patch(f"{_MOD}.create_tag")
    def test_create_empty_after_strip_rejected(
        self, mock_create: MagicMock, editor_client: TestClient
    ):
        res = editor_client.post("/tags", json={"name": "   "})
        assert res.status_code == 400
        mock_create.assert_not_called()

    def test_create_empty_string_rejected_by_field_validation(
        self, editor_client: TestClient
    ):
        res = editor_client.post("/tags", json={"name": ""})
        assert res.status_code == 422

    def test_create_over_long_name_rejected_by_field_validation(
        self, editor_client: TestClient
    ):
        res = editor_client.post("/tags", json={"name": "x" * 101})
        assert res.status_code == 422

    @patch(f"{_MOD}.create_tag")
    def test_create_idempotent_existing_tag_still_201(
        self, mock_create: MagicMock, editor_client: TestClient
    ):
        # Db layer dedupes and returns the existing tag; router still returns 201.
        mock_create.return_value = _make_tag("tag_existing", "Hills")
        res = editor_client.post("/tags", json={"name": "hills"})
        assert res.status_code == 201
        assert res.json()["id"] == "tag_existing"

    def test_create_requires_editor(self, viewer_client: TestClient):
        res = viewer_client.post("/tags", json={"name": "Hills"})
        assert res.status_code == 403

    def test_create_requires_auth(self, client: TestClient):
        res = client.post("/tags", json={"name": "Hills"})
        assert res.status_code == 401


class TestRenameTag:
    """PATCH /tags/{tag_id}."""

    @patch(f"{_MOD}.update_tag_name")
    @patch(f"{_MOD}.get_tag_by_id")
    def test_rename_success(
        self, mock_get: MagicMock, mock_update: MagicMock, editor_client: TestClient
    ):
        mock_get.return_value = _make_tag("tag_1", "Hills")
        mock_update.return_value = _make_tag("tag_1", "Hill Repeats")
        res = editor_client.patch("/tags/tag_1", json={"name": "Hill Repeats"})
        assert res.status_code == 200
        assert res.json()["name"] == "Hill Repeats"
        mock_update.assert_called_once_with("tag_1", "Hill Repeats")

    @patch(f"{_MOD}.update_tag_name")
    @patch(f"{_MOD}.get_tag_by_id")
    def test_rename_strips_name(
        self, mock_get: MagicMock, mock_update: MagicMock, editor_client: TestClient
    ):
        mock_get.return_value = _make_tag("tag_1", "Hills")
        mock_update.return_value = _make_tag("tag_1", "Hill Repeats")
        editor_client.patch("/tags/tag_1", json={"name": "  Hill Repeats  "})
        mock_update.assert_called_once_with("tag_1", "Hill Repeats")

    def test_rename_empty_after_strip_rejected(self, editor_client: TestClient):
        res = editor_client.patch("/tags/tag_1", json={"name": "   "})
        assert res.status_code == 400

    @patch(f"{_MOD}.get_tag_by_id")
    def test_rename_not_found(self, mock_get: MagicMock, editor_client: TestClient):
        mock_get.return_value = None
        res = editor_client.patch("/tags/tag_missing", json={"name": "Hills"})
        assert res.status_code == 404

    @patch(f"{_MOD}.update_tag_name")
    @patch(f"{_MOD}.get_tag_by_id")
    def test_rename_collision_409(
        self, mock_get: MagicMock, mock_update: MagicMock, editor_client: TestClient
    ):
        mock_get.return_value = _make_tag("tag_1", "Hills")
        mock_update.side_effect = ValueError("A tag named 'Speedwork' already exists")
        res = editor_client.patch("/tags/tag_1", json={"name": "Speedwork"})
        assert res.status_code == 409

    def test_rename_requires_editor(self, viewer_client: TestClient):
        res = viewer_client.patch("/tags/tag_1", json={"name": "Hills"})
        assert res.status_code == 403

    def test_rename_requires_auth(self, client: TestClient):
        res = client.patch("/tags/tag_1", json={"name": "Hills"})
        assert res.status_code == 401


class TestDeleteTag:
    """DELETE /tags/{tag_id}."""

    @patch(f"{_MOD}.delete_tag")
    @patch(f"{_MOD}.get_tag_by_id")
    def test_delete_success(
        self, mock_get: MagicMock, mock_delete: MagicMock, editor_client: TestClient
    ):
        mock_get.return_value = _make_tag("tag_1", "Hills")
        mock_delete.return_value = True
        res = editor_client.delete("/tags/tag_1")
        assert res.status_code == 200
        assert "deleted" in res.json()["message"]
        mock_delete.assert_called_once_with("tag_1")

    @patch(f"{_MOD}.get_tag_by_id")
    def test_delete_not_found(self, mock_get: MagicMock, editor_client: TestClient):
        mock_get.return_value = None
        res = editor_client.delete("/tags/tag_missing")
        assert res.status_code == 404

    def test_delete_requires_editor(self, viewer_client: TestClient):
        res = viewer_client.delete("/tags/tag_1")
        assert res.status_code == 403

    def test_delete_requires_auth(self, client: TestClient):
        res = client.delete("/tags/tag_1")
        assert res.status_code == 401
