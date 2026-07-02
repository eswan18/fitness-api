import pytest
from datetime import datetime
from fitness.models import Run
from fitness.db.runs import bulk_create_runs

from tests.e2e.conftest import make_shoe, assign_shoe_to_runs


@pytest.mark.e2e
def test_minimal_workflow(viewer_client, editor_client):
    # Seed: create a run and a shoe attributed to it, plus history.
    run = Run(
        id="e2e_run_1",
        datetime_utc=datetime(2024, 1, 1, 12, 0, 0),
        type="Outdoor Run",
        distance=5.0,
        duration=1800.0,
        source="Strava",
        avg_heart_rate=150.0,
    )

    inserted = bulk_create_runs([run])
    assert inserted == 1

    shoe = make_shoe("E2E Test", "Shoe")
    assign_shoe_to_runs(shoe.id, ["e2e_run_1"])

    # View runs
    res = viewer_client.get("/runs")
    assert res.status_code == 200
    runs = res.json()
    assert any(r["id"] == "e2e_run_1" for r in runs)

    # Edit the run
    res = editor_client.patch(
        "/runs/e2e_run_1",
        json={
            "distance": 5.5,
            "changed_by": "e2e",
            "change_reason": "adjust distance",
        },
    )
    assert res.status_code == 200

    # History should now include original + update
    res = viewer_client.get("/runs/e2e_run_1/history")
    assert res.status_code == 200
    history = res.json()
    assert len(history) >= 2

    # Retire the shoe
    shoe_id = shoe.id
    res = editor_client.patch(
        f"/shoes/{shoe_id}",
        json={"retired_at": "2024-12-31", "retirement_notes": "done"},
    )
    assert res.status_code == 200

    # Verify appears in retired list
    res = viewer_client.get("/shoes", params={"retired": True})
    assert res.status_code == 200
    retired = res.json()
    assert any(s["id"] == shoe_id for s in retired)

    # Unretire
    res = editor_client.patch(f"/shoes/{shoe_id}", json={"retired_at": None})
    assert res.status_code == 200


@pytest.mark.e2e
def test_run_name_is_history_tracked_and_restorable(viewer_client, editor_client):
    """`name` is a first-class edited field: setting it via the full-edit
    endpoint bumps the version, snapshots into history, and restoring an
    older version reverts it (mirrors every other editable run field)."""
    run = Run(
        id="e2e_run_name_1",
        datetime_utc=datetime(2024, 2, 1, 8, 0, 0),
        type="Outdoor Run",
        distance=3.0,
        duration=1200.0,
        source="Strava",
    )
    assert bulk_create_runs([run]) == 1

    # Set the name via the full-edit endpoint (not a lightweight endpoint).
    res = editor_client.patch(
        "/runs/e2e_run_name_1",
        json={
            "name": "Morning Tempo",
            "changed_by": "e2e",
            "change_reason": "named the run",
        },
    )
    assert res.status_code == 200
    assert res.json()["run"]["name"] == "Morning Tempo"

    # History should snapshot the name: newest version first, original (no
    # name) last.
    res = viewer_client.get("/runs/e2e_run_name_1/history")
    assert res.status_code == 200
    history = res.json()
    assert len(history) == 2
    assert history[0]["version_number"] == 2
    assert history[0]["name"] == "Morning Tempo"
    assert history[1]["version_number"] == 1
    assert history[1]["name"] is None

    # Restoring to the original version reverts the name to null.
    res = editor_client.post("/runs/e2e_run_name_1/restore/1?restored_by=e2e")
    assert res.status_code == 200
    assert res.json()["run"]["name"] is None
