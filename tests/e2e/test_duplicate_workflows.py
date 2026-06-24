"""End-to-end tests for marking runs and rides as cross-source duplicates."""

import pytest
from datetime import datetime

from fitness.models import Run, Ride
from fitness.models.run import RunSource
from fitness.models.ride import RideSource
from fitness.db.runs import bulk_create_runs
from fitness.db.rides import bulk_create_rides


def _run(run_id: str, source: RunSource, dt: datetime, distance: float = 5.0) -> Run:
    return Run(
        id=run_id,
        datetime_utc=dt,
        type="Outdoor Run",
        distance=distance,
        duration=1800.0,
        source=source,
        avg_heart_rate=150.0,
    )


def _ride(ride_id: str, source: RideSource, dt: datetime, distance: float = 12.0) -> Ride:
    return Ride(
        id=ride_id,
        datetime_utc=dt,
        type="Outdoor Ride",
        distance=distance,
        duration=2700.0,
        source=source,
        avg_heart_rate=140.0,
    )


def _run_ids(client, rng) -> set[str]:
    res = client.get("/runs-details", params=rng)
    assert res.status_code == 200
    return {r["id"] for r in res.json()}


def _ride_ids(client, rng) -> set[str]:
    res = client.get("/rides-details", params=rng)
    assert res.status_code == 200
    return {r["id"] for r in res.json()}


@pytest.mark.e2e
def test_mark_and_unmark_run_duplicate_flow(viewer_client, editor_client):
    """Mark a HAE run as a duplicate of its Strava twin, then undo."""
    rng = {"start": "2025-04-01", "end": "2025-04-01"}
    strava = _run("dup_run_strava_1", "Strava", datetime(2025, 4, 1, 7, 0, 0))
    hae = _run("dup_run_hae_1", "Apple Health", datetime(2025, 4, 1, 7, 1, 0))
    assert bulk_create_runs([strava, hae]) == 2

    assert {"dup_run_strava_1", "dup_run_hae_1"} <= _run_ids(viewer_client, rng)
    total_before = editor_client.get("/metrics/mileage/total", params=rng).json()

    # The candidate picker for the HAE run surfaces the Strava twin, never itself.
    cands = viewer_client.get("/runs/dup_run_hae_1/duplicate-candidates").json()
    cand_ids = [c["id"] for c in cands]
    assert "dup_run_strava_1" in cand_ids
    assert "dup_run_hae_1" not in cand_ids

    # Mark it.
    res = editor_client.post(
        "/runs/dup_run_hae_1/duplicate-of",
        json={"duplicate_of_id": "dup_run_strava_1"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["duplicate_of_id"] == "dup_run_strava_1"

    # Gone from the feed; the kept run stays. Mileage drops by its distance.
    ids_after = _run_ids(viewer_client, rng)
    assert "dup_run_hae_1" not in ids_after
    assert "dup_run_strava_1" in ids_after
    total_after = editor_client.get("/metrics/mileage/total", params=rng).json()
    assert total_after == pytest.approx(total_before - 5.0, abs=0.01)

    # Re-import is a no-op and must NOT resurrect the marked duplicate.
    assert bulk_create_runs([strava, hae]) == 0
    assert "dup_run_hae_1" not in _run_ids(viewer_client, rng)

    # Undo restores it.
    res = editor_client.delete("/runs/dup_run_hae_1/duplicate-of")
    assert res.status_code == 200, res.text
    assert "dup_run_hae_1" in _run_ids(viewer_client, rng)
    total_restored = editor_client.get("/metrics/mileage/total", params=rng).json()
    assert total_restored == pytest.approx(total_before, abs=0.01)


@pytest.mark.e2e
def test_run_duplicate_error_cases(viewer_client, editor_client, client):
    """Self-reference, missing ids, chains, bad unmark, and auth are rejected."""
    a = _run("dup_err_a", "Strava", datetime(2025, 4, 2, 7, 0, 0))
    b = _run("dup_err_b", "Apple Health", datetime(2025, 4, 2, 7, 2, 0))
    c = _run("dup_err_c", "Apple Health", datetime(2025, 4, 2, 7, 3, 0))
    assert bulk_create_runs([a, b, c]) == 3

    # Self-reference -> 400.
    assert (
        editor_client.post(
            "/runs/dup_err_a/duplicate-of", json={"duplicate_of_id": "dup_err_a"}
        ).status_code
        == 400
    )
    # Missing source -> 404.
    assert (
        editor_client.post(
            "/runs/nope_src/duplicate-of", json={"duplicate_of_id": "dup_err_a"}
        ).status_code
        == 404
    )
    # Missing target -> 404.
    assert (
        editor_client.post(
            "/runs/dup_err_a/duplicate-of", json={"duplicate_of_id": "nope_target"}
        ).status_code
        == 404
    )

    # Chain: mark b as dup of a, then pointing c at b (a duplicate) -> 409.
    assert (
        editor_client.post(
            "/runs/dup_err_b/duplicate-of", json={"duplicate_of_id": "dup_err_a"}
        ).status_code
        == 200
    )
    assert (
        editor_client.post(
            "/runs/dup_err_c/duplicate-of", json={"duplicate_of_id": "dup_err_b"}
        ).status_code
        == 409
    )

    # Unmark a non-duplicate -> 404.
    assert editor_client.delete("/runs/dup_err_a/duplicate-of").status_code == 404

    # Auth: viewer is forbidden (403), unauthenticated is unauthorized (401).
    assert (
        viewer_client.post(
            "/runs/dup_err_c/duplicate-of", json={"duplicate_of_id": "dup_err_a"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/runs/dup_err_c/duplicate-of", json={"duplicate_of_id": "dup_err_a"}
        ).status_code
        == 401
    )


@pytest.mark.e2e
def test_run_duplicate_candidates_exclude_marked(viewer_client, editor_client):
    """Already-marked duplicates drop out of the candidate list."""
    a = _run("dup_cand_a", "Strava", datetime(2025, 4, 3, 6, 0, 0))
    b = _run("dup_cand_b", "Apple Health", datetime(2025, 4, 3, 6, 1, 0))
    far = _run("dup_cand_far", "Strava", datetime(2025, 4, 3, 20, 0, 0))
    assert bulk_create_runs([a, b, far]) == 3

    # `far` is >2h away, so it's outside the default window.
    cand_ids = {
        c["id"]
        for c in viewer_client.get("/runs/dup_cand_a/duplicate-candidates").json()
    }
    assert "dup_cand_b" in cand_ids
    assert "dup_cand_far" not in cand_ids

    # Once b is marked a duplicate, it can no longer be a candidate target.
    assert (
        editor_client.post(
            "/runs/dup_cand_b/duplicate-of", json={"duplicate_of_id": "dup_cand_a"}
        ).status_code
        == 200
    )
    cand_ids = {
        c["id"]
        for c in viewer_client.get("/runs/dup_cand_a/duplicate-candidates").json()
    }
    assert "dup_cand_b" not in cand_ids


@pytest.mark.e2e
def test_mark_and_unmark_ride_duplicate_flow(viewer_client, editor_client):
    """Rides support the same mark/unmark flow (no history table)."""
    rng = {"start": "2025-04-04", "end": "2025-04-04"}
    strava = _ride("dup_ride_strava_1", "Strava", datetime(2025, 4, 4, 7, 0, 0))
    hae = _ride("dup_ride_hae_1", "Apple Health", datetime(2025, 4, 4, 7, 2, 0))
    assert bulk_create_rides([strava, hae]) == 2

    assert {"dup_ride_strava_1", "dup_ride_hae_1"} <= _ride_ids(viewer_client, rng)

    cand_ids = [
        c["id"]
        for c in viewer_client.get(
            "/rides/dup_ride_hae_1/duplicate-candidates"
        ).json()
    ]
    assert "dup_ride_strava_1" in cand_ids

    res = editor_client.post(
        "/rides/dup_ride_hae_1/duplicate-of",
        json={"duplicate_of_id": "dup_ride_strava_1"},
    )
    assert res.status_code == 200, res.text

    ids_after = _ride_ids(viewer_client, rng)
    assert "dup_ride_hae_1" not in ids_after
    assert "dup_ride_strava_1" in ids_after

    assert bulk_create_rides([strava, hae]) == 0
    assert "dup_ride_hae_1" not in _ride_ids(viewer_client, rng)

    assert (
        editor_client.delete("/rides/dup_ride_hae_1/duplicate-of").status_code == 200
    )
    assert "dup_ride_hae_1" in _ride_ids(viewer_client, rng)


@pytest.mark.e2e
def test_marking_run_writes_history_audit(editor_client):
    """Marking/unmarking a run leaves a 'deletion'/'edit' trail in runs_history."""
    from fitness.db.runs_history import get_run_history

    a = _run("dup_hist_a", "Strava", datetime(2025, 4, 6, 7, 0, 0))
    b = _run("dup_hist_b", "Apple Health", datetime(2025, 4, 6, 7, 1, 0))
    assert bulk_create_runs([a, b]) == 2

    assert (
        editor_client.post(
            "/runs/dup_hist_b/duplicate-of", json={"duplicate_of_id": "dup_hist_a"}
        ).status_code
        == 200
    )

    history = get_run_history("dup_hist_b")  # newest first
    assert history[0].change_type == "deletion"
    assert "duplicate of dup_hist_a" in (history[0].change_reason or "")

    assert editor_client.delete("/runs/dup_hist_b/duplicate-of").status_code == 200
    assert get_run_history("dup_hist_b")[0].change_type == "edit"


@pytest.mark.e2e
def test_duplicate_suggestions_surfaces_and_clears(viewer_client, editor_client):
    """The suggestions endpoint flags a cross-source pair, then drops it once marked."""
    strava = _run("sugg_strava_1", "Strava", datetime(2025, 5, 1, 6, 0, 0))
    hae = _run("sugg_hae_1", "Apple Health", datetime(2025, 5, 1, 6, 2, 0))
    assert bulk_create_runs([strava, hae]) == 2

    def my_suggestion():
        # The endpoint scans all-time, so other tests' data may also appear;
        # locate our specific pair by id rather than asserting a global count.
        res = viewer_client.get("/duplicate-suggestions")
        assert res.status_code == 200
        for s in res.json():
            if {s["keep"]["id"], s["duplicate"]["id"]} == {
                "sugg_strava_1",
                "sugg_hae_1",
            }:
                return s
        return None

    s = my_suggestion()
    assert s is not None
    assert s["kind"] == "run"
    # Neither is calendar-synced → default keep is the Strava copy.
    assert s["keep"]["id"] == "sugg_strava_1"
    assert s["duplicate"]["id"] == "sugg_hae_1"
    assert 0.0 <= s["score"] <= 1.0

    # Accept the suggestion via the existing mark endpoint.
    res = editor_client.post(
        f"/runs/{s['duplicate']['id']}/duplicate-of",
        json={"duplicate_of_id": s["keep"]["id"]},
    )
    assert res.status_code == 200, res.text

    # Once marked, the pair no longer shows up.
    assert my_suggestion() is None


@pytest.mark.e2e
def test_duplicate_suggestions_requires_auth(client):
    assert client.get("/duplicate-suggestions").status_code == 401


@pytest.mark.e2e
def test_ride_duplicate_error_cases(viewer_client, editor_client):
    """Ride self-reference and auth mirror the run rules."""
    a = _ride("dup_ride_err_a", "Strava", datetime(2025, 4, 5, 7, 0, 0))
    assert bulk_create_rides([a]) == 1

    assert (
        editor_client.post(
            "/rides/dup_ride_err_a/duplicate-of",
            json={"duplicate_of_id": "dup_ride_err_a"},
        ).status_code
        == 400
    )
    assert (
        editor_client.post(
            "/rides/dup_ride_err_a/duplicate-of",
            json={"duplicate_of_id": "missing_ride"},
        ).status_code
        == 404
    )
    assert editor_client.delete("/rides/dup_ride_err_a/duplicate-of").status_code == 404
    assert (
        viewer_client.post(
            "/rides/dup_ride_err_a/duplicate-of",
            json={"duplicate_of_id": "anything"},
        ).status_code
        == 403
    )
