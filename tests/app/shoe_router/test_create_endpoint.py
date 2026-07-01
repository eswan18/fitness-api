"""Test the shoe create (POST /shoes/) API endpoint."""

from datetime import date

from fastapi.testclient import TestClient

from fitness.models.shoe import Shoe

# brand/model/size/purchased_date are required on create.
REQUIRED = {
    "brand": "Nike",
    "model": "Pegasus 41",
    "size": 10.5,
    "purchased_date": "2026-01-01",
}


def _valid(**extra) -> dict:
    return {**REQUIRED, **extra}


def _mock_create_shoe(
    brand, model, size, purchased_date, color=None, warning_mileage=300,
    maximum_mileage=500, notes=None,
):
    return Shoe(
        id="shoe_test1234",
        name=f"{brand} {model}",
        brand=brand,
        model=model,
        color=color,
        size=size,
        purchased_date=purchased_date,
        warning_mileage=warning_mileage,
        maximum_mileage=maximum_mileage,
        notes=notes,
    )


def test_create_shoe_requires_auth(client: TestClient):
    response = client.post("/shoes/", json=_valid())
    assert response.status_code == 401
    assert "Bearer" in response.headers["WWW-Authenticate"]


def test_create_shoe_requires_editor(viewer_client: TestClient):
    response = viewer_client.post("/shoes/", json=_valid())
    assert response.status_code == 403


def test_create_shoe_defaults(monkeypatch, auth_client: TestClient):
    captured = {}

    def mock_create_shoe(**kwargs):
        captured.update(kwargs)
        return _mock_create_shoe(**kwargs)

    monkeypatch.setattr("fitness.app.routers.shoes.create_shoe", mock_create_shoe)

    response = auth_client.post("/shoes/", json=_valid())

    assert response.status_code == 201
    body = response.json()
    assert body["brand"] == "Nike"
    assert body["model"] == "Pegasus 41"
    assert body["name"] == "Nike Pegasus 41"  # composed
    assert body["color"] is None
    assert body["warning_mileage"] == 300
    assert body["maximum_mileage"] == 500
    assert body["size"] == 10.5
    assert body["purchased_date"] == "2026-01-01"
    assert captured["brand"] == "Nike"
    assert captured["purchased_date"] == date(2026, 1, 1)


def test_create_shoe_custom_values(monkeypatch, auth_client: TestClient):
    captured = {}

    def mock_create_shoe(**kwargs):
        captured.update(kwargs)
        return _mock_create_shoe(**kwargs)

    monkeypatch.setattr("fitness.app.routers.shoes.create_shoe", mock_create_shoe)

    response = auth_client.post(
        "/shoes/",
        json=_valid(
            color="Volt", warning_mileage=250, maximum_mileage=450, size=11
        ),
    )

    assert response.status_code == 201
    assert captured["color"] == "Volt"
    assert captured["warning_mileage"] == 250
    assert captured["maximum_mileage"] == 450
    assert response.json()["color"] == "Volt"


def test_create_shoe_requires_brand_model_size_date(monkeypatch, auth_client: TestClient):
    called = {"value": False}
    monkeypatch.setattr(
        "fitness.app.routers.shoes.create_shoe",
        lambda **kwargs: called.update(value=True),
    )

    for missing in ("brand", "model", "size", "purchased_date"):
        payload = _valid()
        del payload[missing]
        response = auth_client.post("/shoes/", json=payload)
        assert response.status_code == 422, missing

    assert called["value"] is False


def test_create_shoe_rejects_bad_numbers(monkeypatch, auth_client: TestClient):
    called = {"value": False}
    monkeypatch.setattr(
        "fitness.app.routers.shoes.create_shoe",
        lambda **kwargs: called.update(value=True),
    )

    for extra in ({"size": 0}, {"warning_mileage": 0}, {"maximum_mileage": 300, "warning_mileage": 500}):
        response = auth_client.post("/shoes/", json=_valid(**extra))
        assert response.status_code == 422, extra

    assert called["value"] is False
