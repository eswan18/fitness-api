import pytest
from datetime import datetime
from fitness.models import Run
from fitness.db.runs import bulk_create_runs
from fitness.models.shoe import generate_shoe_id


@pytest.mark.e2e
def test_minimal_workflow(client, auth_client):
    # Seed: create a run with a shoe name so it auto-creates the shoe and history
    run = Run(
        id="e2e_run_1",
        datetime_utc=datetime(2024, 1, 1, 12, 0, 0),
        type="Outdoor Run",
        distance=5.0,
        duration=1800.0,
        source="Strava",
        avg_heart_rate=150.0,
    )
    run._shoe_name = "E2E Test Shoe"

    inserted = bulk_create_runs([run])
    assert inserted == 1

    # View runs
    res = client.get("/runs")
    assert res.status_code == 200
    runs = res.json()
    assert any(r["id"] == "e2e_run_1" for r in runs)

    # Edit the run
    res = auth_client.patch(
        "/runs/e2e_run_1",
        json={
            "distance": 5.5,
            "changed_by": "e2e",
            "change_reason": "adjust distance",
        },
    )
    assert res.status_code == 200

    # History should now include original + update
    res = client.get("/runs/e2e_run_1/history")
    assert res.status_code == 200
    history = res.json()
    assert len(history) >= 2

    # Retire the shoe
    shoe_id = generate_shoe_id("E2E Test Shoe")
    res = auth_client.patch(
        f"/shoes/{shoe_id}",
        json={"retired_at": "2024-12-31", "retirement_notes": "done"},
    )
    assert res.status_code == 200

    # Verify appears in retired list
    res = client.get("/shoes", params={"retired": True})
    assert res.status_code == 200
    retired = res.json()
    assert any(s["id"] == shoe_id for s in retired)

    # Unretire
    res = auth_client.patch(f"/shoes/{shoe_id}", json={"retired_at": None})
    assert res.status_code == 200
