"""Test the shoe create (POST /shoes/) API endpoint."""

from datetime import date

from fastapi.testclient import TestClient

from fitness.models.shoe import Shoe, generate_shoe_id

# size + purchased_date are required on create; include them in valid payloads.
REQUIRED = {"size": 10.5, "purchased_date": "2026-01-01"}


def _valid(**extra) -> dict:
    return {**REQUIRED, **extra}


def test_create_shoe_requires_auth(client: TestClient):
    """Creating a shoe requires authentication."""
    response = client.post("/shoes/", json=_valid(name="Nike Pegasus 40"))
    assert response.status_code == 401
    assert "Bearer" in response.headers["WWW-Authenticate"]


def test_create_shoe_requires_editor(viewer_client: TestClient):
    """A viewer (non-editor) cannot create a shoe."""
    response = viewer_client.post("/shoes/", json=_valid(name="Nike Pegasus 40"))
    assert response.status_code == 403


def test_create_shoe_defaults(monkeypatch, auth_client: TestClient):
    """Creating with a name + required fields returns default 300/500 thresholds."""
    captured = {}

    def mock_create_shoe(
        name, size, purchased_date, warning_mileage, maximum_mileage, notes
    ):
        captured.update(
            name=name,
            size=size,
            purchased_date=purchased_date,
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
            size=size,
            purchased_date=purchased_date,
        )

    monkeypatch.setattr("fitness.app.routers.shoes.create_shoe", mock_create_shoe)

    response = auth_client.post("/shoes/", json=_valid(name="Nike Pegasus 40"))

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "nike_pegasus_40"
    assert body["warning_mileage"] == 300
    assert body["maximum_mileage"] == 500
    assert body["size"] == 10.5
    assert body["purchased_date"] == "2026-01-01"
    # size + date were forwarded to the db layer.
    assert captured["size"] == 10.5
    assert captured["purchased_date"] == date(2026, 1, 1)


def test_create_shoe_custom_values(monkeypatch, auth_client: TestClient):
    """Custom mileages, size, and date are forwarded to the db layer and returned."""
    captured = {}

    def mock_create_shoe(
        name, size, purchased_date, warning_mileage, maximum_mileage, notes
    ):
        captured.update(
            size=size,
            purchased_date=purchased_date,
            warning_mileage=warning_mileage,
            maximum_mileage=maximum_mileage,
        )
        return Shoe(
            id=generate_shoe_id(name),
            name=name,
            warning_mileage=warning_mileage,
            maximum_mileage=maximum_mileage,
            size=size,
            purchased_date=purchased_date,
        )

    monkeypatch.setattr("fitness.app.routers.shoes.create_shoe", mock_create_shoe)

    response = auth_client.post(
        "/shoes/",
        json={
            "name": "Custom Shoe",
            "size": 11,
            "purchased_date": "2025-12-25",
            "warning_mileage": 250,
            "maximum_mileage": 450,
        },
    )

    assert response.status_code == 201
    assert captured == {
        "size": 11,
        "purchased_date": date(2025, 12, 25),
        "warning_mileage": 250,
        "maximum_mileage": 450,
    }


def test_create_shoe_requires_size_and_purchased_date(monkeypatch, auth_client: TestClient):
    """Omitting size or purchased_date is a 422, before any db call."""
    called = {"value": False}
    monkeypatch.setattr(
        "fitness.app.routers.shoes.create_shoe",
        lambda **kwargs: called.update(value=True),
    )

    for payload in (
        {"name": "No Size", "purchased_date": "2026-01-01"},
        {"name": "No Date", "size": 10.5},
        {"name": "Neither"},
    ):
        response = auth_client.post("/shoes/", json=payload)
        assert response.status_code == 422, payload

    assert called["value"] is False


def test_create_shoe_rejects_non_positive_size(auth_client: TestClient):
    """size must be > 0."""
    response = auth_client.post("/shoes/", json=_valid(name="Zero Size", size=0))
    assert response.status_code == 422


def test_create_shoe_duplicate(monkeypatch, auth_client: TestClient):
    """A duplicate (create_shoe returns None) yields a 409."""
    monkeypatch.setattr(
        "fitness.app.routers.shoes.create_shoe",
        lambda **kwargs: None,
    )

    response = auth_client.post("/shoes/", json=_valid(name="Existing Shoe"))

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_create_shoe_rejects_maximum_not_above_warning(monkeypatch, auth_client: TestClient):
    """maximum_mileage <= warning_mileage is rejected before any db call."""
    called = {"value": False}
    monkeypatch.setattr(
        "fitness.app.routers.shoes.create_shoe",
        lambda **kwargs: called.update(value=True),
    )

    response = auth_client.post(
        "/shoes/",
        json=_valid(name="Bad Thresholds", warning_mileage=500, maximum_mileage=300),
    )

    assert response.status_code == 422
    assert called["value"] is False


def test_create_shoe_rejects_non_positive_mileage(monkeypatch, auth_client: TestClient):
    """Zero or negative mileage is rejected by the field bounds before any db call."""
    called = {"value": False}
    monkeypatch.setattr(
        "fitness.app.routers.shoes.create_shoe",
        lambda **kwargs: called.update(value=True),
    )

    for extra in ({"warning_mileage": 0}, {"maximum_mileage": -10}):
        response = auth_client.post("/shoes/", json=_valid(name="Bad", **extra))
        assert response.status_code == 422, extra

    assert called["value"] is False
