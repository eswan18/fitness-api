from datetime import date
from fitness.agg.seconds import total_seconds
from tests._factories.run import RunFactory


def test_total_seconds():
    """Test total seconds calculation."""
    runs = [
        RunFactory().make(
            {
                "date": date(2024, 1, 15),
                "duration": 1800,  # 30 minutes
            }
        ),
        RunFactory().make(
            {
                "date": date(2024, 1, 16),
                "duration": 2400,  # 40 minutes
            }
        ),
        RunFactory().make(
            {
                "date": date(2024, 1, 17),
                "duration": 3600,  # 60 minutes
            }
        ),
    ]

    result = total_seconds(runs=runs, start=date(2024, 1, 15), end=date(2024, 1, 17))

    assert result == 7800  # 30 + 40 + 60 minutes = 130 minutes = 7800 seconds


def test_total_seconds_date_filtering():
    """Test that total seconds respects date range."""
    runs = [
        RunFactory().make(
            {
                "date": date(2024, 1, 14),  # Before range
                "duration": 1800,
            }
        ),
        RunFactory().make(
            {
                "date": date(2024, 1, 15),  # In range
                "duration": 2400,
            }
        ),
        RunFactory().make(
            {
                "date": date(2024, 1, 16),  # In range
                "duration": 3600,
            }
        ),
        RunFactory().make(
            {
                "date": date(2024, 1, 18),  # After range
                "duration": 1200,
            }
        ),
    ]

    result = total_seconds(runs=runs, start=date(2024, 1, 15), end=date(2024, 1, 17))

    assert result == 6000  # Only the runs on 1/15 and 1/16


def test_total_seconds_empty_runs():
    """Test total seconds with no runs."""
    result = total_seconds(runs=[], start=date(2024, 1, 15), end=date(2024, 1, 17))

    assert result == 0.0


def test_total_seconds_no_runs_in_range():
    """Test total seconds when no runs fall within the date range."""
    runs = [
        RunFactory().make(
            {
                "date": date(2024, 1, 10),
                "duration": 1800,
            }
        ),
        RunFactory().make(
            {
                "date": date(2024, 1, 20),
                "duration": 2400,
            }
        ),
    ]

    result = total_seconds(runs=runs, start=date(2024, 1, 15), end=date(2024, 1, 17))

    assert result == 0.0
