"""Test the shoe update (PATCH /shoes/{id}) behavior.

Retire/unretire is covered in test_retirement_endpoints.py; this file covers
brand/model/color + mileage/size/date editing, plus the regression that a
profile-only edit must NOT disturb a shoe's retirement status.
"""

from datetime import date

from fastapi.testclient import TestClient

from fitness.models.shoe import Shoe


def _install_capturing_db(monkeypatch, shoe: Shoe):
    """Patch the shoe router's db calls, capturing the mutating ones."""
    calls: dict = {"update_shoe": None, "retired": None, "unretired": False}

    monkeypatch.setattr(
        "fitness.app.routers.shoes.get_shoe_by_id", lambda shoe_id: shoe
    )

    def mock_update_shoe(shoe_id, fields):
        calls["update_shoe"] = {"shoe_id": shoe_id, "fields": fields}
        return True

    def mock_retire(shoe_id, retired_at, retirement_notes=None):
        calls["retired"] = {"retired_at": retired_at, "notes": retirement_notes}
        return True

    def mock_unretire(shoe_id):
        calls["unretired"] = True
        return True

    monkeypatch.setattr("fitness.app.routers.shoes.update_shoe", mock_update_shoe)
    monkeypatch.setattr("fitness.app.routers.shoes.retire_shoe_by_id", mock_retire)
    monkeypatch.setattr("fitness.app.routers.shoes.unretire_shoe_by_id", mock_unretire)
    return calls


def _shoe(**over) -> Shoe:
    return Shoe(
        id="s", name="Old Model", brand="Old", model="Model"
    ).model_copy(update=over)


def test_update_requires_auth(client: TestClient):
    response = client.patch("/shoes/s", json={"brand": "New"})
    assert response.status_code == 401


def test_update_unknown_shoe_404(monkeypatch, auth_client: TestClient):
    monkeypatch.setattr(
        "fitness.app.routers.shoes.get_shoe_by_id", lambda shoe_id: None
    )
    response = auth_client.patch("/shoes/nope", json={"brand": "New"})
    assert response.status_code == 404


def test_update_brand_model_syncs_name(monkeypatch, auth_client: TestClient):
    calls = _install_capturing_db(monkeypatch, _shoe())

    response = auth_client.patch("/shoes/s", json={"brand": "New", "model": "Shoe"})

    assert response.status_code == 200
    assert calls["update_shoe"]["fields"] == {
        "brand": "New",
        "model": "Shoe",
        "name": "New Shoe",  # kept in sync
    }
    assert calls["retired"] is None and calls["unretired"] is False


def test_update_brand_only_syncs_name_with_existing_model(monkeypatch, auth_client: TestClient):
    calls = _install_capturing_db(monkeypatch, _shoe(brand="Old", model="Model"))

    response = auth_client.patch("/shoes/s", json={"brand": "New"})

    assert response.status_code == 200
    assert calls["update_shoe"]["fields"] == {"brand": "New", "name": "New Model"}


def test_update_color_can_be_set_and_cleared(monkeypatch, auth_client: TestClient):
    calls = _install_capturing_db(monkeypatch, _shoe())
    r1 = auth_client.patch("/shoes/s", json={"color": "Volt"})
    assert r1.status_code == 200
    assert calls["update_shoe"]["fields"] == {"color": "Volt"}

    calls2 = _install_capturing_db(monkeypatch, _shoe())
    r2 = auth_client.patch("/shoes/s", json={"color": None})
    assert r2.status_code == 200
    assert calls2["update_shoe"]["fields"] == {"color": None}


def test_update_warning_mileages(monkeypatch, auth_client: TestClient):
    calls = _install_capturing_db(monkeypatch, _shoe())
    response = auth_client.patch(
        "/shoes/s", json={"warning_mileage": 200, "maximum_mileage": 400}
    )
    assert response.status_code == 200
    assert calls["update_shoe"]["fields"] == {
        "warning_mileage": 200,
        "maximum_mileage": 400,
    }


def test_update_size_and_purchased_date(monkeypatch, auth_client: TestClient):
    calls = _install_capturing_db(monkeypatch, _shoe())
    response = auth_client.patch(
        "/shoes/s", json={"size": 9.5, "purchased_date": "2026-02-02"}
    )
    assert response.status_code == 200
    assert calls["update_shoe"]["fields"] == {
        "size": 9.5,
        "purchased_date": date(2026, 2, 2),
    }


def test_update_mileage_validated_against_existing(monkeypatch, auth_client: TestClient):
    shoe = _shoe(warning_mileage=300, maximum_mileage=500)
    calls = _install_capturing_db(monkeypatch, shoe)
    response = auth_client.patch("/shoes/s", json={"maximum_mileage": 200})
    assert response.status_code == 422
    assert calls["update_shoe"] is None


def test_profile_edit_preserves_retirement(monkeypatch, auth_client: TestClient):
    """REGRESSION: editing brand/model must not unretire a retired shoe."""
    shoe = _shoe(retired_at=date(2025, 1, 1))
    calls = _install_capturing_db(monkeypatch, shoe)

    response = auth_client.patch("/shoes/s", json={"brand": "Renamed"})

    assert response.status_code == 200
    assert "brand" in calls["update_shoe"]["fields"]
    assert calls["unretired"] is False
    assert calls["retired"] is None


def test_combined_edit_and_unretire(monkeypatch, auth_client: TestClient):
    shoe = _shoe(retired_at=date(2025, 1, 1))
    calls = _install_capturing_db(monkeypatch, shoe)

    response = auth_client.patch(
        "/shoes/s", json={"brand": "New", "retired_at": None}
    )

    assert response.status_code == 200
    assert "brand" in calls["update_shoe"]["fields"]
    assert calls["unretired"] is True
    assert "updated and unretired" in response.json()["message"]


def test_empty_patch_is_noop(monkeypatch, auth_client: TestClient):
    calls = _install_capturing_db(monkeypatch, _shoe())
    response = auth_client.patch("/shoes/s", json={})
    assert response.status_code == 200
    assert calls["update_shoe"] is None
    assert calls["retired"] is None and calls["unretired"] is False
    assert "No changes" in response.json()["message"]
