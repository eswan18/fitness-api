"""Test GET /shoes/recent endpoint."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from fitness.models.shoe import Shoe, ShoeRecentUse


def test_recent_shoes_endpoint_requires_auth(client: TestClient):
    """Unauthenticated requests are rejected with a Bearer challenge."""
    response = client.get("/shoes/recent")
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
    assert "Bearer" in response.headers["WWW-Authenticate"]


def test_recent_shoes_endpoint_returns_sorted_list(
    monkeypatch, viewer_client: TestClient
):
    """Viewer can fetch shoes ordered by last_used_date DESC NULLS LAST."""
    newer = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
    older = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)

    recent = [
        ShoeRecentUse(
            shoe=Shoe(id="pegasus", name="Pegasus"),
            last_used_date=newer,
        ),
        ShoeRecentUse(
            shoe=Shoe(id="ghost", name="Ghost"),
            last_used_date=older,
        ),
        ShoeRecentUse(
            shoe=Shoe(id="unused", name="Unused"),
            last_used_date=None,
        ),
    ]

    captured: dict = {}

    def mock_get_shoes_with_last_used(include_retired: bool = False):
        captured["include_retired"] = include_retired
        return recent

    monkeypatch.setattr(
        "fitness.app.routers.shoes.get_shoes_with_last_used",
        mock_get_shoes_with_last_used,
    )

    response = viewer_client.get("/shoes/recent")

    assert response.status_code == 200
    body = response.json()
    assert [item["shoe"]["id"] for item in body] == ["pegasus", "ghost", "unused"]
    assert body[0]["last_used_date"].startswith("2026-04-10")
    assert body[2]["last_used_date"] is None
    assert captured["include_retired"] is False


def test_recent_shoes_endpoint_include_retired_param(
    monkeypatch, viewer_client: TestClient
):
    """The include_retired query param is forwarded to the DB function."""
    captured: dict = {}

    def mock_get_shoes_with_last_used(include_retired: bool = False):
        captured["include_retired"] = include_retired
        return []

    monkeypatch.setattr(
        "fitness.app.routers.shoes.get_shoes_with_last_used",
        mock_get_shoes_with_last_used,
    )

    response = viewer_client.get("/shoes/recent?include_retired=true")

    assert response.status_code == 200
    assert captured["include_retired"] is True
