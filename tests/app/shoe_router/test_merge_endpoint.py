"""Test shoe merge API endpoint."""

from fastapi.testclient import TestClient
from fitness.models.shoe import Shoe


def test_merge_shoes_requires_auth(client: TestClient):
    response = client.post(
        "/shoes/merge",
        json={"keep_shoe_id": "a", "merge_shoe_id": "b"},
    )
    assert response.status_code == 401


def test_merge_shoes_success(monkeypatch, auth_client: TestClient):
    shoes = {
        "zoom_fly_4": Shoe(id="zoom_fly_4", name="Zoom Fly 4"),
        "nike_zoom_fly_4": Shoe(id="nike_zoom_fly_4", name="Nike Zoom Fly 4"),
    }

    monkeypatch.setattr(
        "fitness.app.routers.shoes.get_shoe_by_id",
        lambda shoe_id, **kw: shoes.get(shoe_id),
    )
    merge_called_with = {}

    def mock_merge(keep_shoe_id, merge_shoe_id, merge_shoe_name):
        merge_called_with.update(
            keep_shoe_id=keep_shoe_id,
            merge_shoe_id=merge_shoe_id,
            merge_shoe_name=merge_shoe_name,
        )

    monkeypatch.setattr("fitness.app.routers.shoes.merge_shoes", mock_merge)

    response = auth_client.post(
        "/shoes/merge",
        json={"keep_shoe_id": "zoom_fly_4", "merge_shoe_id": "nike_zoom_fly_4"},
    )
    assert response.status_code == 200
    assert "merged" in response.json()["message"].lower()
    assert merge_called_with["keep_shoe_id"] == "zoom_fly_4"
    assert merge_called_with["merge_shoe_name"] == "Nike Zoom Fly 4"


def test_merge_shoes_same_id(monkeypatch, auth_client: TestClient):
    shoe = Shoe(id="zoom_fly_4", name="Zoom Fly 4")
    monkeypatch.setattr(
        "fitness.app.routers.shoes.get_shoe_by_id",
        lambda shoe_id, **kw: shoe,
    )

    response = auth_client.post(
        "/shoes/merge",
        json={"keep_shoe_id": "zoom_fly_4", "merge_shoe_id": "zoom_fly_4"},
    )
    assert response.status_code == 400


def test_merge_shoes_not_found(monkeypatch, auth_client: TestClient):
    monkeypatch.setattr(
        "fitness.app.routers.shoes.get_shoe_by_id",
        lambda shoe_id, **kw: None,
    )

    response = auth_client.post(
        "/shoes/merge",
        json={"keep_shoe_id": "nonexistent", "merge_shoe_id": "also_nonexistent"},
    )
    assert response.status_code == 404
