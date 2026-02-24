"""Tests for get_runs_for_date_range helper logic."""

from datetime import date
from unittest.mock import patch


@patch("fitness.db.runs.get_runs_in_date_range", return_value=[])
def test_for_date_range_widens_with_timezone(mock_db):
    """get_runs_for_date_range should widen by +-1 day when user_timezone is set."""
    from fitness.db.runs import get_runs_for_date_range

    get_runs_for_date_range(date(2025, 6, 1), date(2025, 6, 30), "America/New_York")
    mock_db.assert_called_once_with(date(2025, 5, 31), date(2025, 7, 1))


@patch("fitness.db.runs.get_runs_in_date_range", return_value=[])
def test_for_date_range_exact_without_timezone(mock_db):
    """get_runs_for_date_range should use exact dates when user_timezone is None."""
    from fitness.db.runs import get_runs_for_date_range

    get_runs_for_date_range(date(2025, 6, 1), date(2025, 6, 30), None)
    mock_db.assert_called_once_with(date(2025, 6, 1), date(2025, 6, 30))


@patch("fitness.db.runs.get_runs_in_date_range", return_value=[])
def test_for_date_range_defaults_to_no_timezone(mock_db):
    """get_runs_for_date_range should default to exact dates when timezone omitted."""
    from fitness.db.runs import get_runs_for_date_range

    get_runs_for_date_range(date(2025, 6, 1), date(2025, 6, 30))
    mock_db.assert_called_once_with(date(2025, 6, 1), date(2025, 6, 30))
