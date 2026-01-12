"""End-to-end tests for /runs/details endpoint."""

import pytest
from datetime import datetime, date

from fitness.models import Run
from fitness.db.runs import bulk_create_runs
from fitness.db.synced_runs import create_synced_run
from fitness.db.shoes import retire_shoe_by_id
from fitness.models.shoe import generate_shoe_id


@pytest.mark.e2e
def test_run_details_basic_and_shoe_notes(client):
    """Create a run with a shoe and verify details and shoe retirement notes appear."""
    # Use a far-future date to avoid collisions with other e2e runs
    run = Run(
        id="details_test_run_1",
        datetime_utc=datetime(2035, 1, 2, 10, 0, 0),
        type="Outdoor Run",
        distance=6.2,
        duration=3000.0,
        source="Strava",
        avg_heart_rate=150.0,
    )
    run._shoe_name = "Details Shoe Alpha"

    inserted = bulk_create_runs([run])
    assert inserted == 1

    # Add retirement notes for the shoe to ensure they show up
    shoe_id = generate_shoe_id("Details Shoe Alpha")
    # Set a retirement date and notes
    retired = retire_shoe_by_id(
        shoe_id=shoe_id,
        retired_at=date(2035, 1, 10),
        retirement_notes="E2E retirement notes for verification",
    )
    assert retired is True

    # Fetch details without date filter (endpoint defaults include all)
    res = client.get("/runs/details")
    assert res.status_code == 200
    details = res.json()

    # Find our run
    item = next((d for d in details if d["id"] == "details_test_run_1"), None)
    assert item is not None

    # Verify core fields
    assert item["distance"] == pytest.approx(6.2)
    assert item["duration"] == pytest.approx(3000.0)
    assert item["type"] == "Outdoor Run"
    assert item["source"] == "Strava"

    # Shoe info and retirement notes
    assert item["shoes"] == "Details Shoe Alpha"
    assert item["shoe_retirement_notes"] == "E2E retirement notes for verification"

    # Sync info should be absent/false by default
    assert item["is_synced"] is False
    assert item["sync_status"] is None
    assert item["google_event_id"] is None
    assert item["synced_version"] is None

    # Version should exist (runs.version defaults to 1)
    assert item["version"] >= 1


@pytest.mark.e2e
def test_run_details_with_sync_and_date_filtering_and_sorting(client):
    """Verify sync fields, date filtering, and sorting behavior."""
    run_a = Run(
        id="details_test_run_2A",
        datetime_utc=datetime(2035, 2, 1, 8, 0, 0),
        type="Outdoor Run",
        distance=3.0,
        duration=1500.0,
        source="Strava",
        avg_heart_rate=140.0,
    )
    run_a._shoe_name = "Details Shoe Beta"

    run_b = Run(
        id="details_test_run_2B",
        datetime_utc=datetime(2035, 2, 5, 9, 0, 0),
        type="Treadmill Run",
        distance=5.0,
        duration=2400.0,
        source="MapMyFitness",
        avg_heart_rate=155.0,
    )
    run_b._shoe_name = "Details Shoe Gamma"

    inserted = bulk_create_runs([run_a, run_b])
    assert inserted == 2

    # Mark run_b as synced
    sync = create_synced_run(
        run_id=run_b.id, google_event_id="evt_details_sync_123", run_version=1
    )
    assert sync.run_id == run_b.id
    assert sync.google_event_id == "evt_details_sync_123"

    # Filter to a narrow range containing only run_b
    res = client.get(
        "/runs/details", params={"start": "2035-02-04", "end": "2035-02-06"}
    )
    assert res.status_code == 200
    filtered = res.json()

    ids = {d["id"] for d in filtered}
    assert "details_test_run_2B" in ids
    assert "details_test_run_2A" not in ids

    # Verify sync fields for run_b
    run_b_item = next(d for d in filtered if d["id"] == "details_test_run_2B")
    assert run_b_item["is_synced"] is True
    assert run_b_item["sync_status"] == "synced"
    assert run_b_item["google_event_id"] == "evt_details_sync_123"
    # Synced version should match what we set
    assert run_b_item["synced_version"] == 1
    # Version exists on the base run
    assert run_b_item["version"] >= 1

    # Now query a broader range that includes both and test sorting by distance asc
    res = client.get(
        "/runs/details",
        params={
            "start": "2035-02-01",
            "end": "2035-02-10",
            "sort_by": "distance",
            "sort_order": "asc",
        },
    )
    assert res.status_code == 200
    all_details = res.json()

    subset = [
        d
        for d in all_details
        if d["id"] in {"details_test_run_2A", "details_test_run_2B"}
    ]
    # Expect 3.0 then 5.0
    distances = [d["distance"] for d in subset]
    assert distances == sorted(distances)
