"""Test the extended shoe update (PATCH /shoes/{id}) behavior.

Retire/unretire is covered in test_retirement_endpoints.py; this file covers the
added name-rename and warning-mileage editing, plus the regression that a
name/mileage-only edit must NOT disturb a shoe's retirement status.
"""

from datetime import date

from fastapi.testclient import TestClient

from fitness.models.shoe import Shoe, generate_shoe_id


def _install_capturing_db(monkeypatch, shoe: Shoe):
    """Patch the shoe router's db calls, capturing mutating calls.

    Returns a dict recording calls to update_shoe / retire / unretire and the
    value shoe_name_taken should return (override per-test via calls["name_taken"]).
    """
    calls: dict = {
        "name_taken": False,
        "update_shoe": None,
        "retired": None,
        "unretired": False,
    }

    monkeypatch.setattr(
        "fitness.app.routers.shoes.get_shoe_by_id", lambda shoe_id: shoe
    )
    monkeypatch.setattr(
        "fitness.app.routers.shoes.shoe_name_taken",
        lambda name, exclude_shoe_id=None: calls["name_taken"],
    )

    def mock_update_shoe(shoe_id, fields, alias_old_name=None):
        calls["update_shoe"] = {
            "shoe_id": shoe_id,
            "fields": fields,
            "alias_old_name": alias_old_name,
        }
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


def test_update_requires_auth(client: TestClient):
    response = client.patch("/shoes/abc", json={"name": "New Name"})
    assert response.status_code == 401


def test_update_unknown_shoe_404(monkeypatch, auth_client: TestClient):
    monkeypatch.setattr(
        "fitness.app.routers.shoes.get_shoe_by_id", lambda shoe_id: None
    )
    response = auth_client.patch("/shoes/nope", json={"name": "New Name"})
    assert response.status_code == 404


def test_rename_creates_alias(monkeypatch, auth_client: TestClient):
    """Renaming updates the name and passes the old name as an alias."""
    shoe = Shoe(id="old_shoe", name="Old Shoe")
    calls = _install_capturing_db(monkeypatch, shoe)

    response = auth_client.patch("/shoes/old_shoe", json={"name": "New Shoe"})

    assert response.status_code == 200
    assert calls["update_shoe"]["fields"] == {"name": "New Shoe"}
    assert calls["update_shoe"]["alias_old_name"] == "Old Shoe"
    # Retirement was never touched.
    assert calls["retired"] is None and calls["unretired"] is False


def test_rename_collision_409(monkeypatch, auth_client: TestClient):
    shoe = Shoe(id="old_shoe", name="Old Shoe")
    calls = _install_capturing_db(monkeypatch, shoe)
    calls["name_taken"] = True

    response = auth_client.patch("/shoes/old_shoe", json={"name": "Taken Name"})

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]
    assert calls["update_shoe"] is None  # never attempted


def test_rename_to_same_name_is_noop(monkeypatch, auth_client: TestClient):
    """PATCHing the name to its current value changes nothing."""
    shoe = Shoe(id="same", name="Same Name")
    calls = _install_capturing_db(monkeypatch, shoe)

    response = auth_client.patch("/shoes/same", json={"name": "Same Name"})

    assert response.status_code == 200
    assert calls["update_shoe"] is None
    assert "No changes" in response.json()["message"]


def test_update_warning_mileages(monkeypatch, auth_client: TestClient):
    shoe = Shoe(id="s", name="S")
    calls = _install_capturing_db(monkeypatch, shoe)

    response = auth_client.patch(
        "/shoes/s",
        json={"warning_mileage": 200, "maximum_mileage": 400},
    )

    assert response.status_code == 200
    assert calls["update_shoe"]["fields"] == {
        "warning_mileage": 200,
        "maximum_mileage": 400,
    }
    assert calls["update_shoe"]["alias_old_name"] is None


def test_update_size_and_purchased_date(monkeypatch, auth_client: TestClient):
    """size / purchased_date can be set (e.g. backfilling an old shoe)."""
    shoe = Shoe(id="s", name="S")
    calls = _install_capturing_db(monkeypatch, shoe)

    response = auth_client.patch(
        "/shoes/s",
        json={"size": 9.5, "purchased_date": "2026-02-02"},
    )

    assert response.status_code == 200
    assert calls["update_shoe"]["fields"] == {
        "size": 9.5,
        "purchased_date": date(2026, 2, 2),
    }


def test_update_mileage_validated_against_existing(monkeypatch, auth_client: TestClient):
    """Setting maximum below the shoe's existing warning is a 422 with no db write."""
    shoe = Shoe(id="s", name="S", warning_mileage=300, maximum_mileage=500)
    calls = _install_capturing_db(monkeypatch, shoe)

    response = auth_client.patch("/shoes/s", json={"maximum_mileage": 200})

    assert response.status_code == 422
    assert calls["update_shoe"] is None


def test_name_only_edit_preserves_retirement(monkeypatch, auth_client: TestClient):
    """REGRESSION: editing only the name must not unretire a retired shoe."""
    shoe = Shoe(id="retired_shoe", name="Retired Shoe", retired_at=date(2025, 1, 1))
    calls = _install_capturing_db(monkeypatch, shoe)

    response = auth_client.patch("/shoes/retired_shoe", json={"name": "Renamed Shoe"})

    assert response.status_code == 200
    # The name was updated...
    assert calls["update_shoe"]["fields"] == {"name": "Renamed Shoe"}
    # ...but retirement was left completely alone (the bug would call unretire).
    assert calls["unretired"] is False
    assert calls["retired"] is None


def test_combined_rename_and_unretire(monkeypatch, auth_client: TestClient):
    """A rename plus an explicit retired_at=null does both."""
    shoe = Shoe(id="r", name="R", retired_at=date(2025, 1, 1))
    calls = _install_capturing_db(monkeypatch, shoe)

    response = auth_client.patch(
        "/shoes/r", json={"name": "R2", "retired_at": None}
    )

    assert response.status_code == 200
    assert calls["update_shoe"]["fields"] == {"name": "R2"}
    assert calls["unretired"] is True
    assert "updated and unretired" in response.json()["message"]


def test_empty_patch_is_noop(monkeypatch, auth_client: TestClient):
    shoe = Shoe(id="s", name="S")
    calls = _install_capturing_db(monkeypatch, shoe)

    response = auth_client.patch("/shoes/s", json={})

    assert response.status_code == 200
    assert calls["update_shoe"] is None
    assert calls["retired"] is None and calls["unretired"] is False
    assert "No changes" in response.json()["message"]


def test_generate_shoe_id_used_for_path():
    """Sanity: the id we PATCH against is the normalized name id."""
    assert generate_shoe_id("Old Shoe") == "old_shoe"
