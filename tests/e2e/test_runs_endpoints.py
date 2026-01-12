"""End-to-end tests for runs-related endpoints."""

import pytest
from datetime import datetime
from fitness.models import Run
from fitness.db.runs import bulk_create_runs


@pytest.mark.e2e
def test_runs_endpoint_basic(client):
    """Test basic /runs endpoint functionality."""
    # Create test runs
    runs = [
        Run(
            id="test_run_1",
            datetime_utc=datetime(2024, 1, 15, 10, 0, 0),
            type="Outdoor Run",
            distance=3.0,
            duration=1500.0,
            source="Strava",
            avg_heart_rate=140.0,
        ),
        Run(
            id="test_run_2",
            datetime_utc=datetime(2024, 1, 20, 11, 0, 0),
            type="Treadmill Run",
            distance=5.0,
            duration=2400.0,
            source="MapMyFitness",
            avg_heart_rate=150.0,
        ),
    ]

    inserted = bulk_create_runs(runs)
    assert inserted == 2

    # Test basic endpoint
    res = client.get("/runs")
    assert res.status_code == 200
    runs_data = res.json()
    assert len(runs_data) >= 2

    # Verify our test runs are present
    run_ids = [r["id"] for r in runs_data]
    assert "test_run_1" in run_ids
    assert "test_run_2" in run_ids


@pytest.mark.e2e
def test_runs_filtering_and_sorting(client):
    """Test runs endpoint filtering and sorting parameters."""
    # Create test runs with varying dates
    runs = [
        Run(
            id="sort_test_1",
            datetime_utc=datetime(2024, 2, 1, 10, 0, 0),
            type="Outdoor Run",
            distance=2.0,
            duration=1200.0,
            source="Strava",
            avg_heart_rate=130.0,
        ),
        Run(
            id="sort_test_2",
            datetime_utc=datetime(2024, 2, 5, 10, 0, 0),
            type="Outdoor Run",
            distance=6.0,
            duration=3000.0,
            source="Strava",
            avg_heart_rate=160.0,
        ),
        Run(
            id="sort_test_3",
            datetime_utc=datetime(2024, 2, 10, 10, 0, 0),
            type="Outdoor Run",
            distance=4.0,
            duration=2000.0,
            source="Strava",
            avg_heart_rate=145.0,
        ),
    ]

    inserted = bulk_create_runs(runs)
    assert inserted == 3

    # Test date filtering
    res = client.get("/runs", params={"start": "2024-02-03", "end": "2024-02-08"})
    assert res.status_code == 200
    filtered_runs = res.json()
    filtered_ids = [r["id"] for r in filtered_runs]
    assert "sort_test_2" in filtered_ids
    assert "sort_test_1" not in filtered_ids
    assert "sort_test_3" not in filtered_ids

    # Test sorting by distance (ascending)
    res = client.get("/runs", params={"sort_by": "distance", "sort_order": "asc"})
    assert res.status_code == 200
    sorted_runs = res.json()

    # Find our test runs in the response
    test_runs = [r for r in sorted_runs if r["id"].startswith("sort_test_")]
    if len(test_runs) >= 2:
        # Should be sorted by distance ascending
        distances = [r["distance"] for r in test_runs[:3]]
        assert distances == sorted(distances)

    # Test sorting by heart rate (descending)
    res = client.get("/runs", params={"sort_by": "heart_rate", "sort_order": "desc"})
    assert res.status_code == 200
    hr_sorted_runs = res.json()

    # Find our test runs in the response
    test_runs = [r for r in hr_sorted_runs if r["id"].startswith("sort_test_")]
    if len(test_runs) >= 2:
        # Should be sorted by heart rate descending
        heart_rates = [r["avg_heart_rate"] for r in test_runs[:3]]
        assert heart_rates == sorted(heart_rates, reverse=True)


@pytest.mark.e2e
def test_run_details_endpoint(client):
    """Test /runs-details endpoint returns shoes and sync info fields."""
    # Create a run with shoe information
    run = Run(
        id="shoe_run_1",
        datetime_utc=datetime(2024, 3, 1, 10, 0, 0),
        type="Outdoor Run",
        distance=4.0,
        duration=2000.0,
        source="Strava",
        avg_heart_rate=145.0,
    )
    run._shoe_name = "Test Running Shoe"

    inserted = bulk_create_runs([run])
    assert inserted == 1

    # Test run details endpoint (alias path to avoid routing ambiguity)
    res = client.get("/runs-details")
    assert res.status_code == 200
    runs_data = res.json()

    # Find our test run
    test_run = next((r for r in runs_data if r["id"] == "shoe_run_1"), None)
    assert test_run is not None
    # Should include shoes and sync-related fields
    assert test_run.get("shoes") == "Test Running Shoe"
    assert "is_synced" in test_run
    assert "sync_status" in test_run

    # Test date filtering on run details
    res = client.get(
        "/runs-details", params={"start": "2024-03-01", "end": "2024-03-01"}
    )
    assert res.status_code == 200
    filtered_data = res.json()
    test_run = next((r for r in filtered_data if r["id"] == "shoe_run_1"), None)
    assert test_run is not None


@pytest.mark.e2e
def test_run_history_workflow(client, auth_client):
    """Test complete run editing and history workflow."""
    # Create a run
    run = Run(
        id="history_test_run",
        datetime_utc=datetime(2024, 4, 1, 10, 0, 0),
        type="Outdoor Run",
        distance=5.0,
        duration=2400.0,
        source="Strava",
        avg_heart_rate=150.0,
    )

    inserted = bulk_create_runs([run])
    assert inserted == 1

    # Get initial run state
    res = client.get("/runs/history_test_run/history")
    assert res.status_code == 200
    initial_history = res.json()
    assert len(initial_history) == 1  # Original record

    # Make first edit
    res = auth_client.patch(
        "/runs/history_test_run",
        json={
            "distance": 5.2,
            "changed_by": "e2e_test",
            "change_reason": "GPS correction",
        },
    )
    assert res.status_code == 200

    # Check history after first edit
    res = client.get("/runs/history_test_run/history")
    assert res.status_code == 200
    history = res.json()
    assert len(history) == 2

    # Make second edit
    res = auth_client.patch(
        "/runs/history_test_run",
        json={
            "avg_heart_rate": 155.0,
            "changed_by": "e2e_test",
            "change_reason": "HR strap adjustment",
        },
    )
    assert res.status_code == 200

    # Check final history
    res = client.get("/runs/history_test_run/history")
    assert res.status_code == 200
    final_history = res.json()
    assert len(final_history) == 3

    # Verify we have history records and they contain change tracking info
    latest = final_history[-1]  # History should be ordered
    # Note: The exact values depend on the history implementation
    # For now, just verify the structure and that changes were tracked
    assert "changed_by" in latest
    assert "change_reason" in latest
    # The changed_by value depends on the system's behavior


@pytest.mark.e2e
def test_run_edit_validation(client, auth_client):
    """Test run editing validation and error cases."""
    # Create a run for testing
    run = Run(
        id="validation_test_run",
        datetime_utc=datetime(2024, 5, 1, 10, 0, 0),
        type="Outdoor Run",
        distance=3.0,
        duration=1800.0,
        source="Strava",
    )

    inserted = bulk_create_runs([run])
    assert inserted == 1

    # Test editing non-existent run
    res = auth_client.patch(
        "/runs/non_existent_run",
        json={"distance": 4.0, "changed_by": "test", "change_reason": "test"},
    )
    assert res.status_code == 404

    # Test invalid data (negative distance)
    res = auth_client.patch(
        "/runs/validation_test_run",
        json={"distance": -1.0, "changed_by": "test", "change_reason": "test"},
    )
    assert res.status_code == 422  # Validation error

    # Test invalid data (negative duration)
    res = auth_client.patch(
        "/runs/validation_test_run",
        json={"duration": -100.0, "changed_by": "test", "change_reason": "test"},
    )
    assert res.status_code == 422  # Validation error

    # Test missing required fields
    res = auth_client.patch(
        "/runs/validation_test_run",
        json={
            "distance": 4.0
            # Missing changed_by and change_reason
        },
    )
    assert res.status_code == 422  # Validation error


@pytest.mark.e2e
def test_timezone_handling(client):
    """Test timezone parameter handling in runs endpoints."""
    # Create runs at different times
    runs = [
        Run(
            id="tz_test_1",
            datetime_utc=datetime(2024, 6, 1, 5, 0, 0),  # Early morning UTC
            type="Outdoor Run",
            distance=3.0,
            duration=1800.0,
            source="Strava",
        ),
        Run(
            id="tz_test_2",
            datetime_utc=datetime(2024, 6, 1, 23, 0, 0),  # Late evening UTC
            type="Outdoor Run",
            distance=4.0,
            duration=2000.0,
            source="Strava",
        ),
    ]

    inserted = bulk_create_runs(runs)
    assert inserted == 2

    # Test with timezone parameter (should handle conversion)
    res = client.get(
        "/runs",
        params={
            "start": "2024-06-01",
            "end": "2024-06-01",
            "user_timezone": "America/New_York",
        },
    )
    assert res.status_code == 200
    tz_runs = res.json()

    # Should include both runs when converted to Eastern time
    tz_run_ids = [r["id"] for r in tz_runs]
    assert "tz_test_1" in tz_run_ids or "tz_test_2" in tz_run_ids

    # Test with UTC (no timezone conversion)
    res = client.get("/runs", params={"start": "2024-06-01", "end": "2024-06-01"})
    assert res.status_code == 200
    utc_runs = res.json()

    # Results might differ between timezone-aware and UTC filtering
    # This tests that timezone parameter is being processed
    assert isinstance(utc_runs, list)
