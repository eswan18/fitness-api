"""Test retirement-related API endpoints."""

from fastapi.testclient import TestClient

from fitness.models.shoe import generate_shoe_id


def test_retire_shoe_endpoint_requires_auth(client: TestClient):
    """Test that the retire shoe endpoint requires authentication."""
    response = client.patch("/shoes/123", json={"retired_at": "2024-12-15"})
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
    assert "Bearer" in response.headers["WWW-Authenticate"]


def test_retire_shoe_endpoint(monkeypatch, auth_client: TestClient):
    """Test the retire shoe endpoint."""

    # Mock database functions
    def mock_get_shoe_by_id(shoe_id):
        from fitness.models.shoe import Shoe

        return Shoe(id=shoe_id, name="Nike Air Zoom")

    def mock_retire_shoe_by_id(shoe_id, retired_at, retirement_notes):
        return True  # Success

    monkeypatch.setattr("fitness.app.routers.shoes.get_shoe_by_id", mock_get_shoe_by_id)
    monkeypatch.setattr(
        "fitness.app.routers.shoes.retire_shoe_by_id", mock_retire_shoe_by_id
    )

    shoe_id = generate_shoe_id("Nike Air Zoom")
    response = auth_client.patch(
        f"/shoes/{shoe_id}",
        json={
            "retired_at": "2024-12-15",
            "retirement_notes": "Worn out after 500 miles",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Shoe 'Nike Air Zoom' has been retired"}


def test_retire_shoe_without_notes(monkeypatch, auth_client: TestClient):
    """Test retiring a shoe without notes."""

    # Mock database functions
    def mock_get_shoe_by_id(shoe_id):
        from fitness.models.shoe import Shoe

        return Shoe(id=shoe_id, name="Nike Air Zoom")

    def mock_retire_shoe_by_id(shoe_id, retired_at, retirement_notes):
        return True  # Success

    monkeypatch.setattr("fitness.app.routers.shoes.get_shoe_by_id", mock_get_shoe_by_id)
    monkeypatch.setattr(
        "fitness.app.routers.shoes.retire_shoe_by_id", mock_retire_shoe_by_id
    )

    shoe_id = generate_shoe_id("Nike Air Zoom")
    response = auth_client.patch(f"/shoes/{shoe_id}", json={"retired_at": "2024-12-15"})

    assert response.status_code == 200


def test_unretire_shoe_endpoint(monkeypatch, auth_client: TestClient):
    """Test the unretire shoe endpoint."""

    # Mock database functions
    def mock_get_shoe_by_id(shoe_id):
        from fitness.models.shoe import Shoe

        return Shoe(id=shoe_id, name="Nike Air Zoom")

    def mock_unretire_shoe_by_id(shoe_id):
        return True  # Success

    monkeypatch.setattr("fitness.app.routers.shoes.get_shoe_by_id", mock_get_shoe_by_id)
    monkeypatch.setattr(
        "fitness.app.routers.shoes.unretire_shoe_by_id", mock_unretire_shoe_by_id
    )

    shoe_id = generate_shoe_id("Nike Air Zoom")
    response = auth_client.patch(f"/shoes/{shoe_id}", json={"retired_at": None})

    assert response.status_code == 200
    assert response.json() == {"message": "Shoe 'Nike Air Zoom' has been unretired"}


def test_unretire_non_retired_shoe(monkeypatch, auth_client: TestClient):
    """Test unretiring a shoe that was never retired."""

    # Mock database functions
    def mock_get_shoe_by_id(shoe_id):
        from fitness.models.shoe import Shoe

        return Shoe(id=shoe_id, name="Nike Air Zoom")

    def mock_unretire_shoe_by_id(shoe_id):
        return True  # Success (idempotent)

    monkeypatch.setattr("fitness.app.routers.shoes.get_shoe_by_id", mock_get_shoe_by_id)
    monkeypatch.setattr(
        "fitness.app.routers.shoes.unretire_shoe_by_id", mock_unretire_shoe_by_id
    )

    shoe_id = generate_shoe_id("Nike Air Zoom")
    response = auth_client.patch(f"/shoes/{shoe_id}", json={"retired_at": None})

    # With PATCH, this should succeed (idempotent operation)
    assert response.status_code == 200
    assert response.json() == {"message": "Shoe 'Nike Air Zoom' has been unretired"}
