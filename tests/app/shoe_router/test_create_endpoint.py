"""Test the shoe create (POST /shoes/) API endpoint."""

from fastapi.testclient import TestClient

from fitness.models.shoe import Shoe, generate_shoe_id


def test_create_shoe_requires_auth(client: TestClient):
    """Creating a shoe requires authentication."""
    response = client.post("/shoes/", json={"name": "Nike Pegasus 40"})
    assert response.status_code == 401
    assert "Bearer" in response.headers["WWW-Authenticate"]


def test_create_shoe_requires_editor(viewer_client: TestClient):
    """A viewer (non-editor) cannot create a shoe."""
    response = viewer_client.post("/shoes/", json={"name": "Nike Pegasus 40"})
    assert response.status_code == 403


def test_create_shoe_defaults(monkeypatch, auth_client: TestClient):
    """Creating with just a name returns the shoe with default 300/500 thresholds."""
    captured = {}

    def mock_create_shoe(name, warning_mileage, maximum_mileage, notes):
        captured.update(
            name=name,
            warning_mileage=warning_mileage,
            maximum_mileage=maximum_mileage,
            notes=notes,
        )
        return Shoe(
            id=generate_shoe_id(name),
            name=name,
            notes=notes,
            warning_mileage=warning_mileage,
            maximum_mileage=maximum_mileage,
        )

    monkeypatch.setattr("fitness.app.routers.shoes.create_shoe", mock_create_shoe)

    response = auth_client.post("/shoes/", json={"name": "Nike Pegasus 40"})

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "nike_pegasus_40"
    assert body["name"] == "Nike Pegasus 40"
    assert body["warning_mileage"] == 300
    assert body["maximum_mileage"] == 500
    # Defaults were passed through to the db layer.
    assert captured["warning_mileage"] == 300
    assert captured["maximum_mileage"] == 500


def test_create_shoe_custom_mileages(monkeypatch, auth_client: TestClient):
    """Custom warning/maximum mileages are forwarded to the db layer and returned."""
    captured = {}

    def mock_create_shoe(name, warning_mileage, maximum_mileage, notes):
        captured.update(
            warning_mileage=warning_mileage,
            maximum_mileage=maximum_mileage,
        )
        return Shoe(
            id=generate_shoe_id(name),
            name=name,
            warning_mileage=warning_mileage,
            maximum_mileage=maximum_mileage,
        )

    monkeypatch.setattr("fitness.app.routers.shoes.create_shoe", mock_create_shoe)

    response = auth_client.post(
        "/shoes/",
        json={
            "name": "Custom Shoe",
            "warning_mileage": 250,
            "maximum_mileage": 450,
        },
    )

    assert response.status_code == 201
    assert captured == {"warning_mileage": 250, "maximum_mileage": 450}
    body = response.json()
    assert body["warning_mileage"] == 250
    assert body["maximum_mileage"] == 450


def test_create_shoe_duplicate(monkeypatch, auth_client: TestClient):
    """A duplicate (create_shoe returns None) yields a 409."""
    monkeypatch.setattr(
        "fitness.app.routers.shoes.create_shoe",
        lambda **kwargs: None,
    )

    response = auth_client.post("/shoes/", json={"name": "Existing Shoe"})

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_create_shoe_rejects_maximum_not_above_warning(monkeypatch, auth_client: TestClient):
    """maximum_mileage <= warning_mileage is rejected before any db call."""
    called = {"value": False}

    def mock_create_shoe(**kwargs):
        called["value"] = True
        return None

    monkeypatch.setattr("fitness.app.routers.shoes.create_shoe", mock_create_shoe)

    response = auth_client.post(
        "/shoes/",
        json={
            "name": "Bad Thresholds",
            "warning_mileage": 500,
            "maximum_mileage": 300,
        },
    )

    assert response.status_code == 422
    assert called["value"] is False


def test_create_shoe_rejects_non_positive_mileage(monkeypatch, auth_client: TestClient):
    """Zero or negative mileage is rejected by the field bounds before any db call."""
    called = {"value": False}

    def mock_create_shoe(**kwargs):
        called["value"] = True
        return None

    monkeypatch.setattr("fitness.app.routers.shoes.create_shoe", mock_create_shoe)

    for payload in (
        {"name": "Zero Warning", "warning_mileage": 0},
        {"name": "Negative Max", "maximum_mileage": -10},
    ):
        response = auth_client.post("/shoes/", json=payload)
        assert response.status_code == 422, payload

    assert called["value"] is False
