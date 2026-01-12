"""End-to-end tests for metrics endpoints."""

import pytest
from datetime import datetime
from fitness.models import Run
from fitness.db.runs import bulk_create_runs


@pytest.mark.e2e
def test_mileage_metrics(client):
    """Test mileage-related metrics endpoints."""
    # Create test runs with known distances and dates
    runs = [
        Run(
            id="mileage_test_1",
            datetime_utc=datetime(2024, 7, 1, 10, 0, 0),
            type="Outdoor Run",
            distance=3.0,
            duration=1800.0,
            source="Strava",
        ),
        Run(
            id="mileage_test_2",
            datetime_utc=datetime(2024, 7, 2, 10, 0, 0),
            type="Outdoor Run",
            distance=5.0,
            duration=2400.0,
            source="Strava",
        ),
        Run(
            id="mileage_test_3",
            datetime_utc=datetime(2024, 7, 3, 10, 0, 0),
            type="Outdoor Run",
            distance=2.0,
            duration=1200.0,
            source="Strava",
        ),
    ]

    inserted = bulk_create_runs(runs)
    assert inserted == 3

    # Test total mileage
    res = client.get(
        "/metrics/mileage/total", params={"start": "2024-07-01", "end": "2024-07-03"}
    )
    assert res.status_code == 200
    total_mileage = res.json()
    assert total_mileage >= 10.0  # Our test runs total 10 miles

    # Test mileage by day
    res = client.get(
        "/metrics/mileage/by-day", params={"start": "2024-07-01", "end": "2024-07-03"}
    )
    assert res.status_code == 200
    daily_mileage = res.json()

    # Should have entries for the days we have runs
    dates_with_mileage = [
        entry["date"] for entry in daily_mileage if entry["mileage"] > 0
    ]
    assert "2024-07-01" in dates_with_mileage
    assert "2024-07-02" in dates_with_mileage
    assert "2024-07-03" in dates_with_mileage

    # Verify specific day mileage
    july_2_entry = next(
        (entry for entry in daily_mileage if entry["date"] == "2024-07-02"), None
    )
    assert july_2_entry is not None
    assert july_2_entry["mileage"] >= 5.0  # Should include our 5-mile run

    # Test rolling mileage
    res = client.get(
        "/metrics/mileage/rolling-by-day",
        params={
            "start": "2024-07-01",
            "end": "2024-07-03",
            "window": 2,  # 2-day rolling window
        },
    )
    assert res.status_code == 200
    rolling_mileage = res.json()
    assert isinstance(rolling_mileage, list)
    assert len(rolling_mileage) > 0


@pytest.mark.e2e
def test_seconds_metrics(client):
    """Test time-based metrics endpoints."""
    # Create test runs with known durations
    runs = [
        Run(
            id="seconds_test_1",
            datetime_utc=datetime(2024, 8, 1, 10, 0, 0),
            type="Outdoor Run",
            distance=3.0,
            duration=1800.0,  # 30 minutes
            source="Strava",
        ),
        Run(
            id="seconds_test_2",
            datetime_utc=datetime(2024, 8, 2, 10, 0, 0),
            type="Outdoor Run",
            distance=5.0,
            duration=2400.0,  # 40 minutes
            source="Strava",
        ),
    ]

    inserted = bulk_create_runs(runs)
    assert inserted == 2

    # Test total seconds
    res = client.get(
        "/metrics/seconds/total", params={"start": "2024-08-01", "end": "2024-08-02"}
    )
    assert res.status_code == 200
    total_seconds = res.json()
    assert total_seconds >= 4200.0  # Our test runs total 70 minutes = 4200 seconds


@pytest.mark.e2e
def test_shoe_mileage_metrics(client):
    """Test shoe mileage tracking."""
    # Create runs with different shoes
    runs = [
        Run(
            id="shoe_mileage_test_1",
            datetime_utc=datetime(2024, 9, 1, 10, 0, 0),
            type="Outdoor Run",
            distance=5.0,
            duration=2400.0,
            source="Strava",
        ),
        Run(
            id="shoe_mileage_test_2",
            datetime_utc=datetime(2024, 9, 2, 10, 0, 0),
            type="Outdoor Run",
            distance=3.0,
            duration=1800.0,
            source="Strava",
        ),
        Run(
            id="shoe_mileage_test_3",
            datetime_utc=datetime(2024, 9, 3, 10, 0, 0),
            type="Outdoor Run",
            distance=4.0,
            duration=2000.0,
            source="Strava",
        ),
    ]

    # Set shoe names
    runs[0]._shoe_name = "Test Shoe A"
    runs[1]._shoe_name = "Test Shoe B"
    runs[2]._shoe_name = "Test Shoe A"  # Same shoe as first run

    inserted = bulk_create_runs(runs)
    assert inserted == 3

    # Test mileage by shoe
    res = client.get("/metrics/mileage/by-shoe")
    assert res.status_code == 200
    shoe_mileage = res.json()

    # Find our test shoes
    test_shoe_a = next(
        (shoe for shoe in shoe_mileage if shoe["shoe"]["name"] == "Test Shoe A"), None
    )
    test_shoe_b = next(
        (shoe for shoe in shoe_mileage if shoe["shoe"]["name"] == "Test Shoe B"), None
    )

    assert test_shoe_a is not None
    assert test_shoe_b is not None

    # Test Shoe A should have 5.0 + 4.0 = 9.0 miles
    assert test_shoe_a["mileage"] >= 9.0

    # Test Shoe B should have 3.0 miles
    assert test_shoe_b["mileage"] >= 3.0

    # Test include_retired parameter
    res = client.get("/metrics/mileage/by-shoe", params={"include_retired": True})
    assert res.status_code == 200
    all_shoes = res.json()
    assert isinstance(all_shoes, list)


@pytest.mark.e2e
def test_training_load_metrics(client):
    """Test training load and TRIMP metrics."""
    # Create runs with heart rate data
    runs = [
        Run(
            id="trimp_test_1",
            datetime_utc=datetime(2024, 10, 1, 10, 0, 0),
            type="Outdoor Run",
            distance=5.0,
            duration=2400.0,
            source="Strava",
            avg_heart_rate=150.0,
        ),
        Run(
            id="trimp_test_2",
            datetime_utc=datetime(2024, 10, 2, 10, 0, 0),
            type="Outdoor Run",
            distance=3.0,
            duration=1800.0,
            source="Strava",
            avg_heart_rate=160.0,
        ),
        Run(
            id="trimp_test_3",
            datetime_utc=datetime(2024, 10, 3, 10, 0, 0),
            type="Outdoor Run",
            distance=4.0,
            duration=2000.0,
            source="Strava",
            avg_heart_rate=145.0,
        ),
    ]

    inserted = bulk_create_runs(runs)
    assert inserted == 3

    # Test TRIMP by day
    res = client.get(
        "/metrics/trimp/by-day",
        params={
            "start": "2024-10-01",
            "end": "2024-10-03",
            "max_hr": 190.0,
            "resting_hr": 50.0,
            "sex": "M",
        },
    )
    assert res.status_code == 200
    trimp_data = res.json()

    # Should have TRIMP values for days with runs
    assert isinstance(trimp_data, list)
    assert len(trimp_data) > 0

    # Check structure of TRIMP data
    trimp_entry = trimp_data[0]
    assert "date" in trimp_entry
    assert "trimp" in trimp_entry
    assert isinstance(trimp_entry["trimp"], (int, float))

    # Find specific days
    oct_1_trimp = next(
        (entry for entry in trimp_data if entry["date"] == "2024-10-01"), None
    )
    if oct_1_trimp:
        assert oct_1_trimp["trimp"] > 0  # Should have positive TRIMP for day with run

    # Test training load by day (requires more parameters)
    res = client.get(
        "/metrics/training-load/by-day",
        params={
            "start": "2024-10-01",
            "end": "2024-10-03",
            "max_hr": 190.0,
            "resting_hr": 50.0,
            "sex": "M",
        },
    )
    assert res.status_code == 200
    training_load = res.json()

    # Should have training load data
    assert isinstance(training_load, list)
    assert len(training_load) > 0

    # Check structure of training load data
    tl_entry = training_load[0]
    assert "date" in tl_entry
    assert "training_load" in tl_entry
    assert "atl" in tl_entry["training_load"]  # Acute training load
    assert "ctl" in tl_entry["training_load"]  # Chronic training load
    assert "tsb" in tl_entry["training_load"]  # Training stress balance


@pytest.mark.e2e
def test_metrics_with_timezone(client):
    """Test metrics endpoints with timezone parameters."""
    # Create runs around timezone boundaries
    runs = [
        Run(
            id="tz_metrics_test_1",
            datetime_utc=datetime(2024, 11, 1, 4, 0, 0),  # Early morning UTC
            type="Outdoor Run",
            distance=3.0,
            duration=1800.0,
            source="Strava",
            avg_heart_rate=140.0,
        ),
        Run(
            id="tz_metrics_test_2",
            datetime_utc=datetime(2024, 11, 1, 22, 0, 0),  # Late evening UTC
            type="Outdoor Run",
            distance=4.0,
            duration=2000.0,
            source="Strava",
            avg_heart_rate=150.0,
        ),
    ]

    inserted = bulk_create_runs(runs)
    assert inserted == 2

    # Test mileage with timezone
    res = client.get(
        "/metrics/mileage/total",
        params={
            "start": "2024-11-01",
            "end": "2024-11-01",
            "user_timezone": "America/New_York",
        },
    )
    assert res.status_code == 200
    tz_mileage = res.json()
    assert tz_mileage >= 0.0  # Should handle timezone conversion

    # Test TRIMP with timezone
    res = client.get(
        "/metrics/trimp/by-day",
        params={
            "start": "2024-11-01",
            "end": "2024-11-01",
            "user_timezone": "America/New_York",
            "max_hr": 190.0,
            "resting_hr": 50.0,
            "sex": "M",
        },
    )
    assert res.status_code == 200
    tz_trimp = res.json()
    assert isinstance(tz_trimp, list)


@pytest.mark.e2e
def test_metrics_error_cases(client):
    """Test error handling in metrics endpoints."""
    # Test training load without required parameters
    res = client.get("/metrics/training-load/by-day")
    assert res.status_code == 422  # Should require start, end, max_hr, resting_hr, sex

    # Test with invalid date format
    res = client.get(
        "/metrics/mileage/total", params={"start": "invalid-date", "end": "2024-01-01"}
    )
    assert res.status_code == 422  # Should reject invalid date

    # Test with invalid heart rate values
    res = client.get(
        "/metrics/trimp/by-day",
        params={
            "start": "2024-01-01",
            "end": "2024-01-02",
            "max_hr": -1.0,  # Invalid negative heart rate
            "resting_hr": 50.0,
            "sex": "M",
        },
    )

    # Test with invalid sex value
    res = client.get(
        "/metrics/trimp/by-day",
        params={
            "start": "2024-01-01",
            "end": "2024-01-02",
            "max_hr": 190.0,
            "resting_hr": 50.0,
            "sex": "X",  # Invalid sex value
        },
    )
    assert res.status_code == 422  # Should reject invalid sex value


@pytest.mark.e2e
def test_metrics_empty_data(client):
    """Test metrics endpoints with no data in date range."""
    # Test mileage for a date range with no runs
    res = client.get(
        "/metrics/mileage/total", params={"start": "1990-01-01", "end": "1990-01-01"}
    )
    assert res.status_code == 200
    empty_mileage = res.json()
    assert empty_mileage == 0.0

    # Test mileage by day for empty range
    res = client.get(
        "/metrics/mileage/by-day", params={"start": "1990-01-01", "end": "1990-01-01"}
    )
    assert res.status_code == 200
    empty_daily = res.json()
    assert isinstance(empty_daily, list)
    # Should return empty list or list with zero mileage

    # Test TRIMP for empty range
    res = client.get(
        "/metrics/trimp/by-day",
        params={
            "start": "1990-01-01",
            "end": "1990-01-01",
            "max_hr": 190.0,
            "resting_hr": 50.0,
            "sex": "M",
        },
    )
    assert res.status_code == 200
    empty_trimp = res.json()
    assert isinstance(empty_trimp, list)
