"""Unit tests for the HAE ingest endpoint and its bearer-token auth.

DB access is patched out; the real-Postgres behavior is covered in
tests/e2e/test_hae_ingestion.py.
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from fitness.app.app import app
from fitness.db.api_tokens import ApiToken


def _active_token(name: str = "hae-ingest") -> ApiToken:
    return ApiToken(
        id=1,
        name=name,
        prefix="fitapi_abc123",
        created_at=datetime(2026, 6, 1, 0, 0, 0),
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _workout(**overrides) -> dict:
    base = {
        "id": "WORKOUT-1",
        "name": "Running",
        "start": "2026-06-20 07:00:00 -0500",
        "end": "2026-06-20 07:30:00 -0500",
        "duration": 1800,
        "distance": {"qty": 5.0, "units": "mi"},
        "avgHeartRate": {"qty": 150.0, "units": "count/min"},
        "maxHeartRate": {"qty": 175.0, "units": "count/min"},
        "stepCadence": {"qty": 168.0, "units": "spm"},
    }
    base.update(overrides)
    return base


def _body(*workouts) -> dict:
    return {"data": {"workouts": list(workouts), "metrics": []}}


def test_missing_token_returns_401(client):
    resp = client.post("/ingest/hae", json=_body(_workout()))
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_unknown_token_returns_401(client, monkeypatch):
    monkeypatch.setattr(
        "fitness.app.ingest_auth.get_active_token_by_hash", lambda h: None
    )
    resp = client.post(
        "/ingest/hae",
        json=_body(_workout()),
        headers={"Authorization": "Bearer fitapi_unknown"},
    )
    assert resp.status_code == 401


# A trimmed, anonymized copy of a REAL Health Auto Export workout (GPS route and
# per-sample arrays shortened, location coordinates faked). Captured from a live
# device to lock in the real field shapes: name "Outdoor Run" (not "Running"),
# isIndoor/location, the aggregate avgHeartRate, stepCadence in count/min, a
# float duration, and many extra fields that must be ignored.
_REAL_OUTDOOR_RUN = {
    "id": "AA0FB1AB-5C1E-4224-84D5-F2A6C0EA1444",
    "name": "Outdoor Run",
    "start": "2026-06-23 06:08:21 -0500",
    "end": "2026-06-23 07:08:10 -0500",
    "duration": 3586.641825914383,
    "isIndoor": False,
    "location": "Outdoor",
    "distance": {"qty": 7.004961937937455, "units": "mi"},
    "avgHeartRate": {"qty": 138.88300835654596, "units": "bpm"},
    "maxHeartRate": {"qty": 164, "units": "bpm"},
    "stepCadence": {"qty": 168.71888969566902, "units": "count/min"},
    # extra fields HAE includes that we do not model and must ignore:
    "heartRate": {
        "avg": {"qty": 138.8, "units": "bpm"},
        "max": {"qty": 164, "units": "bpm"},
    },
    "heartRateData": [
        {
            "Avg": 88,
            "Max": 88,
            "Min": 88,
            "date": "2026-06-23 06:08:24 -0500",
            "units": "bpm",
        }
    ],
    "activeEnergyBurned": {"qty": 920.0, "units": "kcal"},
    "avgSpeed": {"qty": 6.88, "units": "mi"},
    "route": [{"latitude": 0.0, "longitude": 0.0, "altitude": 180.0}],
    "metadata": {},
}


def test_ingests_realistic_full_workout(client, monkeypatch):
    """A real-shaped HAE workout (many extra fields) ingests as one Outdoor Run."""
    captured = {}
    monkeypatch.setattr(
        "fitness.app.ingest_auth.get_active_token_by_hash", lambda h: _active_token()
    )
    monkeypatch.setattr("fitness.app.ingest_auth.touch_last_used", lambda i: None)
    monkeypatch.setattr(
        "fitness.app.routers.ingest.bulk_create_runs",
        lambda runs: captured.__setitem__("runs", runs) or len(runs),
    )
    monkeypatch.setattr(
        "fitness.app.routers.ingest.bulk_create_rides", lambda rides: len(rides)
    )

    resp = client.post(
        "/ingest/hae",
        json=_body(_REAL_OUTDOOR_RUN),
        headers={"Authorization": "Bearer fitapi_good"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "received": 1,
        "created": 1,
        "skipped": 0,
        "errors": [],
        "token_name": "hae-ingest",
    }
    run = captured["runs"][0]
    assert run.id == "hae_AA0FB1AB-5C1E-4224-84D5-F2A6C0EA1444"
    assert run.type == "Outdoor Run"
    assert run.distance == pytest.approx(7.004961937937455)
    assert run.avg_heart_rate == pytest.approx(138.88300835654596)
    assert run.max_heart_rate == 164
    assert run.step_cadence == pytest.approx(168.71888969566902)
    assert run.source == "Apple Health"


def test_valid_token_ingests_run(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "fitness.app.ingest_auth.get_active_token_by_hash",
        lambda h: _active_token(),
    )
    monkeypatch.setattr("fitness.app.ingest_auth.touch_last_used", lambda i: None)

    def fake_bulk_create_runs(runs):
        captured["runs"] = runs
        return len(runs)

    def fake_bulk_create_rides(rides):
        captured["rides"] = rides
        return len(rides)

    monkeypatch.setattr(
        "fitness.app.routers.ingest.bulk_create_runs", fake_bulk_create_runs
    )
    monkeypatch.setattr(
        "fitness.app.routers.ingest.bulk_create_rides", fake_bulk_create_rides
    )

    resp = client.post(
        "/ingest/hae",
        json=_body(_workout()),
        headers={"Authorization": "Bearer fitapi_good"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] == 1
    assert data["created"] == 1
    assert data["skipped"] == 0
    assert data["errors"] == []
    assert data["token_name"] == "hae-ingest"
    # the run was built and handed to bulk_create_runs
    assert len(captured["runs"]) == 1
    assert captured["runs"][0].source == "Apple Health"


def test_cycling_routes_to_rides_and_walking_is_skipped(client, monkeypatch):
    captured = {"runs": [], "rides": []}
    monkeypatch.setattr(
        "fitness.app.ingest_auth.get_active_token_by_hash",
        lambda h: _active_token(),
    )
    monkeypatch.setattr("fitness.app.ingest_auth.touch_last_used", lambda i: None)
    monkeypatch.setattr(
        "fitness.app.routers.ingest.bulk_create_runs",
        lambda runs: captured.__setitem__("runs", runs) or len(runs),
    )
    monkeypatch.setattr(
        "fitness.app.routers.ingest.bulk_create_rides",
        lambda rides: captured.__setitem__("rides", rides) or len(rides),
    )

    resp = client.post(
        "/ingest/hae",
        json=_body(
            _workout(id="r1", name="Running"),
            _workout(id="c1", name="Cycling"),
            _workout(id="w1", name="Walking"),
        ),
        headers={"Authorization": "Bearer fitapi_good"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] == 3
    assert data["created"] == 2  # one run + one ride
    assert data["skipped"] == 1  # the walk
    assert len(captured["runs"]) == 1
    assert len(captured["rides"]) == 1


def test_bad_timestamp_recorded_as_error(client, monkeypatch):
    monkeypatch.setattr(
        "fitness.app.ingest_auth.get_active_token_by_hash",
        lambda h: _active_token(),
    )
    monkeypatch.setattr("fitness.app.ingest_auth.touch_last_used", lambda i: None)
    monkeypatch.setattr(
        "fitness.app.routers.ingest.bulk_create_runs", lambda runs: len(runs)
    )
    monkeypatch.setattr(
        "fitness.app.routers.ingest.bulk_create_rides", lambda rides: len(rides)
    )

    resp = client.post(
        "/ingest/hae",
        json=_body(_workout(start="2026-06-20T07:00:00-05:00")),  # ISO-T, invalid
        headers={"Authorization": "Bearer fitapi_good"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 0
    assert len(data["errors"]) == 1
