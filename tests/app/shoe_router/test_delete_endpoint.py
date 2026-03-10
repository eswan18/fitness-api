"""Test shoe deletion API endpoint."""

from fastapi.testclient import TestClient

from fitness.models.shoe import generate_shoe_id


def test_delete_shoe_endpoint_requires_auth(client: TestClient):
    """Test that the delete shoe endpoint requires authentication."""
    response = client.delete("/shoes/123")
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
    assert "Bearer" in response.headers["WWW-Authenticate"]


def test_delete_shoe_endpoint(monkeypatch, auth_client: TestClient):
    """Test successful shoe deletion."""

    def mock_delete_shoe_by_id(shoe_id):
        return True

    monkeypatch.setattr(
        "fitness.app.routers.shoes.delete_shoe_by_id", mock_delete_shoe_by_id
    )

    shoe_id = generate_shoe_id("Nike Air Zoom")
    response = auth_client.delete(f"/shoes/{shoe_id}")

    assert response.status_code == 200
    assert response.json() == {"message": f"Shoe {shoe_id} deleted"}


def test_delete_shoe_not_found(monkeypatch, auth_client: TestClient):
    """Test deleting a shoe that doesn't exist returns 404."""

    def mock_delete_shoe_by_id(shoe_id):
        return False

    monkeypatch.setattr(
        "fitness.app.routers.shoes.delete_shoe_by_id", mock_delete_shoe_by_id
    )

    shoe_id = generate_shoe_id("Nonexistent Shoe")
    response = auth_client.delete(f"/shoes/{shoe_id}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
