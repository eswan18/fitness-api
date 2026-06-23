"""End-to-end tests for the HAE ingest endpoint against real Postgres.

Covers the issue's acceptance criteria: a WOD-recorded run POSTed with a valid
ingest token lands as exactly one row; re-POSTing does not duplicate; avg HR +
duration populate hrTSS; a revoked/unknown token gets 401.
"""

from fastapi.testclient import TestClient

import pytest

from fitness.auth.tokens import generate_token, hash_token, token_prefix
from fitness.db.api_tokens import create_api_token, revoke_api_token
from fitness.db.connection import get_db_cursor
from fitness.db.rides import get_ride_by_id
from fitness.db.runs import get_run_by_id, update_run_notes


def _mint_token(name: str = "hae-ingest") -> str:
    raw = generate_token()
    create_api_token(
        name=name, token_hash=hash_token(raw), prefix=token_prefix(raw), expires_at=None
    )
    return raw


def _run_workout(
    workout_id: str,
    *,
    name: str = "Running",
    start: str = "2026-06-20 07:00:00 -0500",
    end: str = "2026-06-20 07:30:00 -0500",
    **extra,
) -> dict:
    w = {
        "id": workout_id,
        "name": name,
        "start": start,
        "end": end,
        "duration": 1800,
        "distance": {"qty": 5.0, "units": "mi"},
        "avgHeartRate": {"qty": 150.0, "units": "count/min"},
        "maxHeartRate": {"qty": 175.0, "units": "count/min"},
        "stepCadence": {"qty": 168.0, "units": "spm"},
    }
    w.update(extra)
    return w


def _body(*workouts: dict) -> dict:
    return {"data": {"workouts": list(workouts), "metrics": []}}


def _auth(raw: str) -> dict:
    return {"Authorization": f"Bearer {raw}"}


@pytest.mark.e2e
def test_happy_path_persists_run_with_cadence(client: TestClient):
    raw = _mint_token()
    resp = client.post(
        "/ingest/hae", json=_body(_run_workout("e2e-happy-1")), headers=_auth(raw)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] == 1
    assert data["created"] == 1
    assert data["skipped"] == 0
    assert data["token_name"] == "hae-ingest"

    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT source, avg_heart_rate, max_heart_rate, step_cadence, source_name "
            "FROM runs WHERE id = %s",
            ("hae_e2e-happy-1",),
        )
        row = cursor.fetchone()
    assert row == ("Apple Health", 150.0, 175.0, 168.0, "Running")


@pytest.mark.e2e
def test_repost_is_idempotent(client: TestClient):
    raw = _mint_token()
    workout = _run_workout("e2e-idem-1")

    first = client.post("/ingest/hae", json=_body(workout), headers=_auth(raw))
    assert first.json()["created"] == 1

    second = client.post("/ingest/hae", json=_body(workout), headers=_auth(raw))
    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert second.json()["skipped"] == 1

    with get_db_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM runs WHERE id = %s", ("hae_e2e-idem-1",))
        count_row = cursor.fetchone()
    assert count_row is not None
    assert count_row[0] == 1


@pytest.mark.e2e
def test_user_notes_survive_repost(client: TestClient):
    raw = _mint_token()
    workout = _run_workout("e2e-notes-1")
    client.post("/ingest/hae", json=_body(workout), headers=_auth(raw))

    update_run_notes("hae_e2e-notes-1", "felt great")
    # Re-POST the same workout; the insert is a no-op and must not touch notes.
    client.post("/ingest/hae", json=_body(workout), headers=_auth(raw))

    run = get_run_by_id("hae_e2e-notes-1")
    assert run is not None
    assert run.notes == "felt great"


@pytest.mark.e2e
def test_cycling_workout_lands_in_rides(client: TestClient):
    raw = _mint_token()
    resp = client.post(
        "/ingest/hae",
        json=_body(_run_workout("e2e-ride-1", name="Cycling")),
        headers=_auth(raw),
    )
    assert resp.json()["created"] == 1
    ride = get_ride_by_id("hae_e2e-ride-1")
    assert ride is not None
    assert ride.source == "Apple Health"
    assert ride.type == "Outdoor Ride"
    # The new HAE columns are persisted (read model doesn't surface them yet).
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT max_heart_rate, source_name FROM rides WHERE id = %s",
            ("hae_e2e-ride-1",),
        )
        assert cursor.fetchone() == (175.0, "Cycling")
    # and it did NOT create a run
    assert get_run_by_id("hae_e2e-ride-1") is None


@pytest.mark.e2e
def test_non_run_ride_workout_is_skipped(client: TestClient):
    raw = _mint_token()
    resp = client.post(
        "/ingest/hae",
        json=_body(_run_workout("e2e-walk-1", name="Walking")),
        headers=_auth(raw),
    )
    data = resp.json()
    assert data["created"] == 0
    assert data["skipped"] == 1
    assert get_run_by_id("hae_e2e-walk-1") is None


@pytest.mark.e2e
def test_revoked_token_is_rejected(client: TestClient):
    raw = _mint_token("to-revoke")
    revoke_api_token(prefix=token_prefix(raw))
    resp = client.post(
        "/ingest/hae", json=_body(_run_workout("e2e-revoked-1")), headers=_auth(raw)
    )
    assert resp.status_code == 401
    # nothing was written
    assert get_run_by_id("hae_e2e-revoked-1") is None


@pytest.mark.e2e
def test_unknown_token_is_rejected(client: TestClient):
    resp = client.post(
        "/ingest/hae",
        json=_body(_run_workout("e2e-unknown-1")),
        headers=_auth("fitapi_does-not-exist"),
    )
    assert resp.status_code == 401


@pytest.mark.e2e
def test_ingested_run_contributes_to_hrtss(
    client: TestClient, viewer_client: TestClient
):
    raw = _mint_token()
    # Use an isolated date so other tests' runs don't affect the assertion.
    client.post(
        "/ingest/hae",
        json=_body(
            _run_workout(
                "e2e-hrtss-1",
                start="2026-03-15 07:00:00 -0500",
                end="2026-03-15 07:30:00 -0500",
            )
        ),
        headers=_auth(raw),
    )

    resp = viewer_client.get(
        "/metrics/hrtss/by-day",
        params={"start": "2026-03-15", "end": "2026-03-15"},
    )
    assert resp.status_code == 200
    by_day = {d["date"]: d["hrtss"] for d in resp.json()}
    assert by_day.get("2026-03-15", 0) > 0
