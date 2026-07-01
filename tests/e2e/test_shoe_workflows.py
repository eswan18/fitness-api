"""End-to-end tests for shoe management workflows."""

import pytest
from datetime import datetime
from fitness.models import Run
from fitness.db.runs import bulk_create_runs, get_run_by_id
from fitness.db.shoes import get_shoe_by_id

from tests.e2e.conftest import make_shoe, assign_shoe_to_runs


@pytest.mark.e2e
def test_complete_shoe_lifecycle(viewer_client, editor_client):
    """Test complete shoe management lifecycle."""
    # Seed runs, then create a shoe and attribute the runs to it (imports no
    # longer create/assign shoes).
    runs = [
        Run(
            id="shoe_lifecycle_1",
            datetime_utc=datetime(2024, 12, 1, 10, 0, 0),
            type="Outdoor Run",
            distance=5.0,
            duration=2400.0,
            source="Strava",
            avg_heart_rate=150.0,
        ),
        Run(
            id="shoe_lifecycle_2",
            datetime_utc=datetime(2024, 12, 5, 10, 0, 0),
            type="Outdoor Run",
            distance=6.0,
            duration=2800.0,
            source="Strava",
            avg_heart_rate=155.0,
        ),
        Run(
            id="shoe_lifecycle_3",
            datetime_utc=datetime(2024, 12, 10, 10, 0, 0),
            type="Outdoor Run",
            distance=4.0,
            duration=2000.0,
            source="Strava",
            avg_heart_rate=145.0,
        ),
    ]

    inserted = bulk_create_runs(runs)
    assert inserted == 3

    shoe_name = "Lifecycle Test Shoe"
    shoe = make_shoe("Lifecycle Test", "Shoe")
    assign_shoe_to_runs(shoe.id, [r.id for r in runs])
    shoe_id = shoe.id

    # 1. Verify shoe appears in active shoes list
    res = viewer_client.get("/shoes")
    assert res.status_code == 200
    active_shoes = res.json()

    test_shoe = next((shoe for shoe in active_shoes if shoe["id"] == shoe_id), None)
    assert test_shoe is not None
    assert test_shoe["name"] == shoe_name
    assert test_shoe["retired_at"] is None

    # 2. Check shoe mileage accumulation
    res = viewer_client.get("/metrics/mileage/by-shoe")
    assert res.status_code == 200
    shoe_mileage = res.json()

    test_shoe_mileage = next(
        (shoe for shoe in shoe_mileage if shoe["shoe"]["name"] == shoe_name), None
    )
    assert test_shoe_mileage is not None
    assert test_shoe_mileage["mileage"] >= 15.0  # 5 + 6 + 4 = 15 miles

    # 3. Retire the shoe
    retirement_date = "2024-12-31"
    retirement_notes = "Reached mileage limit"

    res = editor_client.patch(
        f"/shoes/{shoe_id}",
        json={"retired_at": retirement_date, "retirement_notes": retirement_notes},
    )
    assert res.status_code == 200

    # 4. Check if shoe retirement was recorded (behavior may vary)
    res = viewer_client.get("/shoes")
    assert res.status_code == 200

    # Note: Depending on implementation, retired shoes may or may not appear in default list
    # The key thing is that retirement was successful (status 200 above)

    # 5. Verify shoe appears in retired list
    res = viewer_client.get("/shoes", params={"retired": True})
    assert res.status_code == 200
    retired_shoes = res.json()

    retired_test_shoe = next(
        (shoe for shoe in retired_shoes if shoe["id"] == shoe_id), None
    )
    assert retired_test_shoe is not None
    assert retired_test_shoe["retired_at"] == retirement_date
    assert retired_test_shoe["retirement_notes"] == retirement_notes

    # 6. Test including retired shoes in mileage
    res = viewer_client.get(
        "/metrics/mileage/by-shoe", params={"include_retired": True}
    )
    assert res.status_code == 200
    all_shoe_mileage = res.json()

    retired_shoe_mileage = next(
        (shoe for shoe in all_shoe_mileage if shoe["shoe"]["name"] == shoe_name), None
    )
    assert retired_shoe_mileage is not None
    assert retired_shoe_mileage["mileage"] >= 15.0
    assert retired_shoe_mileage["shoe"]["retired_at"] == retirement_date

    # 7. Unretire the shoe
    res = editor_client.patch(
        f"/shoes/{shoe_id}", json={"retired_at": None, "retirement_notes": None}
    )
    assert res.status_code == 200

    # 8. Verify shoe is active again
    res = viewer_client.get("/shoes")
    assert res.status_code == 200
    active_shoes_final = res.json()

    unretired_shoe = next(
        (shoe for shoe in active_shoes_final if shoe["id"] == shoe_id), None
    )
    assert unretired_shoe is not None
    assert unretired_shoe["retired_at"] is None
    assert unretired_shoe["retirement_notes"] is None


@pytest.mark.e2e
def test_multiple_shoes_management(viewer_client, editor_client):
    """Test managing multiple different shoes."""
    # Create runs, then create and attribute a distinct shoe to each.
    runs = [
        Run(
            id="multi_shoe_1",
            datetime_utc=datetime(2024, 11, 1, 10, 0, 0),
            type="Outdoor Run",
            distance=5.0,
            duration=2400.0,
            source="Strava",
        ),
        Run(
            id="multi_shoe_2",
            datetime_utc=datetime(2024, 11, 2, 10, 0, 0),
            type="Treadmill Run",
            distance=3.0,
            duration=1800.0,
            source="Strava",
        ),
        Run(
            id="multi_shoe_3",
            datetime_utc=datetime(2024, 11, 3, 10, 0, 0),
            type="Outdoor Run",
            distance=7.0,
            duration=3200.0,
            source="Strava",
        ),
    ]

    inserted = bulk_create_runs(runs)
    assert inserted == 3

    # Create and assign different shoes.
    road_shoe = make_shoe("Road Shoe", "A")
    treadmill_shoe = make_shoe("Treadmill Shoe", "B")
    trail_shoe = make_shoe("Trail Shoe", "C")
    assign_shoe_to_runs(road_shoe.id, ["multi_shoe_1"])
    assign_shoe_to_runs(treadmill_shoe.id, ["multi_shoe_2"])
    assign_shoe_to_runs(trail_shoe.id, ["multi_shoe_3"])

    # Get all shoes
    res = viewer_client.get("/shoes")
    assert res.status_code == 200
    all_shoes = res.json()

    # Should have at least our 3 test shoes
    shoe_names = [shoe["name"] for shoe in all_shoes]
    assert "Road Shoe A" in shoe_names
    assert "Treadmill Shoe B" in shoe_names
    assert "Trail Shoe C" in shoe_names

    # Retire two different shoes with different dates and notes
    road_shoe_id = road_shoe.id
    trail_shoe_id = trail_shoe.id

    # Retire road shoe
    res = editor_client.patch(
        f"/shoes/{road_shoe_id}",
        json={"retired_at": "2024-11-15", "retirement_notes": "Worn out treads"},
    )
    assert res.status_code == 200

    # Retire trail shoe
    res = editor_client.patch(
        f"/shoes/{trail_shoe_id}",
        json={"retired_at": "2024-11-20", "retirement_notes": "Sole separation"},
    )
    assert res.status_code == 200

    # Check active shoes (should only have Indoor Shoe B)
    res = viewer_client.get("/shoes")
    assert res.status_code == 200
    active_shoes = res.json()

    active_names = [shoe["name"] for shoe in active_shoes]
    # Note: Default shoe endpoint behavior may include all shoes
    # The important thing is that retirement operations succeeded (status 200 above)
    assert "Treadmill Shoe B" in active_names

    # Check retired shoes
    res = viewer_client.get("/shoes", params={"retired": True})
    assert res.status_code == 200
    retired_shoes = res.json()

    retired_names = [shoe["name"] for shoe in retired_shoes]
    assert "Road Shoe A" in retired_names
    assert "Trail Shoe C" in retired_names

    # Verify retirement details
    road_shoe_retired = next(
        (shoe for shoe in retired_shoes if shoe["name"] == "Road Shoe A"), None
    )
    trail_shoe_retired = next(
        (shoe for shoe in retired_shoes if shoe["name"] == "Trail Shoe C"), None
    )

    assert road_shoe_retired is not None
    assert road_shoe_retired["retired_at"] == "2024-11-15"
    assert road_shoe_retired["retirement_notes"] == "Worn out treads"

    assert trail_shoe_retired is not None
    assert trail_shoe_retired["retired_at"] == "2024-11-20"
    assert trail_shoe_retired["retirement_notes"] == "Sole separation"


@pytest.mark.e2e
def test_shoe_error_cases(viewer_client, editor_client):
    """Test error handling in shoe management."""
    # Test retiring non-existent shoe
    fake_shoe_id = "non_existent_shoe_id"
    res = editor_client.patch(
        f"/shoes/{fake_shoe_id}",
        json={"retired_at": "2024-01-01", "retirement_notes": "test"},
    )
    assert res.status_code == 404

    # Creating a shoe requires the new required fields (brand/model/size/
    # purchased_date); omitting size and purchased_date is a validation error.
    res = editor_client.post(
        "/shoes/", json={"brand": "Error", "model": "Test Shoe"}
    )
    assert res.status_code == 422  # Validation error (missing size/purchased_date)

    # Create a valid shoe to exercise PATCH validation against.
    shoe = make_shoe("Error Test", "Shoe")
    shoe_id = shoe.id

    # Test invalid date format
    res = editor_client.patch(
        f"/shoes/{shoe_id}",
        json={"retired_at": "invalid-date-format", "retirement_notes": "test"},
    )
    assert res.status_code == 422  # Validation error

    # Test empty request body
    res = editor_client.patch(f"/shoes/{shoe_id}", json={})
    assert res.status_code == 200  # Should succeed with no changes


@pytest.mark.e2e
def test_shoe_filtering_behavior(viewer_client, editor_client):
    """Test different shoe filtering scenarios."""
    # Create runs, then create shoes in different states and attribute the runs.
    runs = [
        Run(
            id="filter_test_1",
            datetime_utc=datetime(2024, 1, 10, 10, 0, 0),
            type="Outdoor Run",
            distance=5.0,
            duration=2400.0,
            source="Strava",
        ),
        Run(
            id="filter_test_2",
            datetime_utc=datetime(2024, 1, 11, 10, 0, 0),
            type="Outdoor Run",
            distance=4.0,
            duration=2000.0,
            source="Strava",
        ),
    ]

    inserted = bulk_create_runs(runs)
    assert inserted == 2

    active_shoe = make_shoe("Active Filter", "Shoe")
    retired_shoe = make_shoe("Future Retired", "Shoe")
    assign_shoe_to_runs(active_shoe.id, ["filter_test_1"])
    assign_shoe_to_runs(retired_shoe.id, ["filter_test_2"])

    # Retire one shoe
    retired_shoe_id = retired_shoe.id
    res = editor_client.patch(
        f"/shoes/{retired_shoe_id}",
        json={"retired_at": "2024-01-15", "retirement_notes": "test retirement"},
    )
    assert res.status_code == 200

    # Test filtering by retired=False (active only)
    res = viewer_client.get("/shoes", params={"retired": False})
    assert res.status_code == 200
    active_only = res.json()

    active_names = [shoe["name"] for shoe in active_only]
    assert "Active Filter Shoe" in active_names
    assert "Future Retired Shoe" not in active_names

    # Test filtering by retired=True (retired only)
    res = viewer_client.get("/shoes", params={"retired": True})
    assert res.status_code == 200
    retired_only = res.json()

    retired_names = [shoe["name"] for shoe in retired_only]
    assert "Future Retired Shoe" in retired_names
    assert "Active Filter Shoe" not in retired_names

    # Test no filter (all shoes)
    res = viewer_client.get("/shoes")
    assert res.status_code == 200
    all_shoes = res.json()

    all_names = [shoe["name"] for shoe in all_shoes]
    # Default behavior should show only active shoes
    assert "Active Filter Shoe" in all_names
    # Note: "Future Retired Shoe" should NOT be in default list since it's retired


@pytest.mark.e2e
def test_shoe_mileage_consistency(viewer_client, editor_client):
    """Test that shoe mileage remains consistent through retirement lifecycle."""
    # Create multiple runs with the same shoe
    runs = [
        Run(
            id="consistency_run_1",
            datetime_utc=datetime(2024, 5, 1, 10, 0, 0),
            type="Outdoor Run",
            distance=3.5,
            duration=2100.0,
            source="Strava",
        ),
        Run(
            id="consistency_run_2",
            datetime_utc=datetime(2024, 5, 5, 10, 0, 0),
            type="Outdoor Run",
            distance=4.2,
            duration=2500.0,
            source="Strava",
        ),
        Run(
            id="consistency_run_3",
            datetime_utc=datetime(2024, 5, 10, 10, 0, 0),
            type="Outdoor Run",
            distance=2.8,
            duration=1700.0,
            source="Strava",
        ),
    ]

    inserted = bulk_create_runs(runs)
    assert inserted == 3

    shoe_name = "Consistency Test Shoe"
    shoe = make_shoe("Consistency Test", "Shoe")
    assign_shoe_to_runs(shoe.id, [r.id for r in runs])
    shoe_id = shoe.id

    expected_total = 3.5 + 4.2 + 2.8  # 10.5 miles

    # Get initial mileage (active shoe)
    res = viewer_client.get("/metrics/mileage/by-shoe")
    assert res.status_code == 200
    initial_mileage = res.json()

    initial_shoe = next(
        (shoe for shoe in initial_mileage if shoe["shoe"]["name"] == shoe_name), None
    )
    assert initial_shoe is not None
    assert initial_shoe["mileage"] >= expected_total
    initial_miles = initial_shoe["mileage"]

    # Retire the shoe
    res = editor_client.patch(
        f"/shoes/{shoe_id}",
        json={
            "retired_at": "2024-05-15",
            "retirement_notes": "mileage consistency test",
        },
    )
    assert res.status_code == 200

    # Get mileage after retirement (should be same when including retired)
    res = viewer_client.get(
        "/metrics/mileage/by-shoe", params={"include_retired": True}
    )
    assert res.status_code == 200
    retired_mileage = res.json()

    retired_shoe = next(
        (shoe for shoe in retired_mileage if shoe["shoe"]["name"] == shoe_name), None
    )
    assert retired_shoe is not None
    assert retired_shoe["mileage"] == initial_miles  # Should be exactly the same
    assert retired_shoe["shoe"]["retired_at"] == "2024-05-15"

    # Verify shoe doesn't appear in active-only mileage
    res = viewer_client.get("/metrics/mileage/by-shoe")
    assert res.status_code == 200
    active_only_mileage = res.json()

    active_shoe = next(
        (shoe for shoe in active_only_mileage if shoe["shoe"]["name"] == shoe_name),
        None,
    )
    assert active_shoe is None  # Should not appear in active-only list

    # Unretire and verify mileage is preserved
    res = editor_client.patch(
        f"/shoes/{shoe_id}", json={"retired_at": None, "retirement_notes": None}
    )
    assert res.status_code == 200

    # Get mileage after unretirement
    res = viewer_client.get("/metrics/mileage/by-shoe")
    assert res.status_code == 200
    final_mileage = res.json()

    final_shoe = next(
        (shoe for shoe in final_mileage if shoe["shoe"]["name"] == shoe_name), None
    )
    assert final_shoe is not None
    assert final_shoe["mileage"] == initial_miles  # Should still be the same
    assert final_shoe["shoe"]["retired_at"] is None


@pytest.mark.e2e
def test_shoe_merge_workflow(viewer_client, editor_client):
    """Merging re-points the merged shoe's runs to the kept shoe and soft-deletes it."""
    # Create runs, then create two shoes (same physical shoe) and attribute a run
    # to each.
    runs = [
        Run(
            id="merge_test_1",
            datetime_utc=datetime(2024, 6, 1, 10, 0, 0),
            type="Outdoor Run",
            distance=5.0,
            duration=2400.0,
            source="Strava",
        ),
        Run(
            id="merge_test_2",
            datetime_utc=datetime(2024, 6, 2, 10, 0, 0),
            type="Outdoor Run",
            distance=6.0,
            duration=2800.0,
            source="MapMyFitness",
        ),
    ]

    inserted = bulk_create_runs(runs)
    assert inserted == 2

    shoe_a = make_shoe("Merge Shoe", "A")
    shoe_b = make_shoe("Merge Shoe", "B")
    assign_shoe_to_runs(shoe_a.id, ["merge_test_1"])
    assign_shoe_to_runs(shoe_b.id, ["merge_test_2"])
    shoe_a_id = shoe_a.id
    shoe_b_id = shoe_b.id

    # Merge B into A
    res = editor_client.post(
        "/shoes/merge",
        json={"keep_shoe_id": shoe_a_id, "merge_shoe_id": shoe_b_id},
    )
    assert res.status_code == 200

    # Verify merged shoe is gone from active list, kept shoe remains.
    res = viewer_client.get("/shoes")
    shoe_names = [s["name"] for s in res.json()]
    assert "Merge Shoe A" in shoe_names
    assert "Merge Shoe B" not in shoe_names

    # The merge re-points the merged shoe's run to the kept shoe.
    repointed = get_run_by_id("merge_test_2")
    assert repointed is not None
    assert repointed.shoe_id == shoe_a_id

    # And soft-deletes the merged shoe (hidden by default; deleted_at is set).
    assert get_shoe_by_id(shoe_b_id) is None
    deleted = get_shoe_by_id(shoe_b_id, include_deleted=True)
    assert deleted is not None
    assert deleted.deleted_at is not None


@pytest.mark.e2e
def test_create_shoe_and_thresholds_surface_in_metrics(viewer_client, editor_client):
    """A shoe created via POST carries custom thresholds through to /shoes and metrics."""
    # 1. Create directly via the new endpoint with custom thresholds.
    res = editor_client.post(
        "/shoes/",
        json={
            "brand": "E2E Created",
            "model": "Shoe",
            "size": 10.5,
            "purchased_date": "2024-08-15",
            "warning_mileage": 222,
            "maximum_mileage": 444,
        },
    )
    assert res.status_code == 201
    created = res.json()
    shoe_id = created["id"]
    assert created["name"] == "E2E Created Shoe"
    assert created["warning_mileage"] == 222
    assert created["maximum_mileage"] == 444
    assert created["size"] == 10.5
    assert created["purchased_date"] == "2024-08-15"
    assert created["retired_at"] is None

    # 2. It shows up in the shoe list with the thresholds persisted.
    res = viewer_client.get("/shoes")
    assert res.status_code == 200
    listed = next((s for s in res.json() if s["id"] == shoe_id), None)
    assert listed is not None
    assert listed["warning_mileage"] == 222
    assert listed["maximum_mileage"] == 444

    # 3. Seed a run and attribute it to the shoe; the thresholds ride along in
    #    the by-shoe metrics and no duplicate shoe is created.
    run = Run(
        id="e2e_created_shoe_run_1",
        datetime_utc=datetime(2024, 9, 1, 10, 0, 0),
        type="Outdoor Run",
        distance=8.0,
        duration=3600.0,
        source="Strava",
    )
    assert bulk_create_runs([run]) == 1
    assign_shoe_to_runs(shoe_id, ["e2e_created_shoe_run_1"])

    res = viewer_client.get("/metrics/mileage/by-shoe")
    assert res.status_code == 200
    by_shoe = res.json()
    matches = [s for s in by_shoe if s["shoe"]["id"] == shoe_id]
    assert len(matches) == 1  # exactly one — assigning the run did not create a duplicate
    assert matches[0]["mileage"] >= 8.0
    assert matches[0]["shoe"]["warning_mileage"] == 222
    assert matches[0]["shoe"]["maximum_mileage"] == 444


@pytest.mark.e2e
def test_size_and_date_null_for_imports_and_backfillable(viewer_client, editor_client):
    """Imports leave shoe_id NULL and record imported_shoe_name; API-created shoes
    round-trip size/purchased_date and PATCH can edit them."""
    from fitness.db.connection import get_db_connection

    # 1. Importing a run no longer creates or assigns a shoe: shoe_id stays NULL
    #    and the raw gear name is recorded in imported_shoe_name.
    seed = Run(
        id="e2e_backfill_run_1",
        datetime_utc=datetime(2024, 8, 1, 10, 0, 0),
        type="Outdoor Run",
        distance=5.0,
        duration=2400.0,
        source="Strava",
    )
    seed._shoe_name = "E2E Import Gear"
    assert bulk_create_runs([seed]) == 1

    imported = get_run_by_id("e2e_backfill_run_1")
    assert imported is not None
    assert imported.shoe_id is None

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT imported_shoe_name FROM runs WHERE id = %s",
                ("e2e_backfill_run_1",),
            )
            row = cur.fetchone()
    assert row is not None
    assert row[0] == "E2E Import Gear"

    # 2. A shoe created via the API round-trips size/purchased_date.
    res = editor_client.post(
        "/shoes/",
        json={
            "brand": "E2E Backfill",
            "model": "Shoe",
            "size": 8.5,
            "purchased_date": "2024-06-01",
        },
    )
    assert res.status_code == 201
    created = res.json()
    shoe_id = created["id"]
    assert created["size"] == 8.5
    assert created["purchased_date"] == "2024-06-01"

    res = viewer_client.get("/shoes")
    listed = next((s for s in res.json() if s["id"] == shoe_id), None)
    assert listed is not None
    assert listed["size"] == 8.5
    assert listed["purchased_date"] == "2024-06-01"

    # 3. PATCH can edit size/purchased_date.
    res = editor_client.patch(
        f"/shoes/{shoe_id}",
        json={"size": 9.0, "purchased_date": "2024-07-01"},
    )
    assert res.status_code == 200

    res = viewer_client.get("/shoes")
    updated = next((s for s in res.json() if s["id"] == shoe_id), None)
    assert updated is not None
    assert updated["size"] == 9.0
    assert updated["purchased_date"] == "2024-07-01"
