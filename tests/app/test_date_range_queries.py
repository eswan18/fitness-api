"""Test that endpoints call DB functions with correctly widened date ranges."""

import sys
from datetime import date, timedelta
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


# -- Endpoint wiring tests for /runs --


def test_runs_endpoint_widens_dates_for_timezone(
    monkeypatch, viewer_client: TestClient
):
    """The /runs endpoint should pass user_timezone through to get_runs_for_date_range."""
    mock = MagicMock(return_value=[])
    monkeypatch.setattr(
        sys.modules["fitness.app.app"],
        "get_runs_for_date_range",
        mock,
    )

    viewer_client.get(
        "/runs",
        params={
            "start": "2025-06-01",
            "end": "2025-06-30",
            "user_timezone": "America/Chicago",
        },
    )

    mock.assert_called_once_with(date(2025, 6, 1), date(2025, 6, 30), "America/Chicago")


def test_runs_endpoint_no_buffer_without_timezone(
    monkeypatch, viewer_client: TestClient
):
    """The /runs endpoint should use exact dates when no timezone is provided."""
    mock = MagicMock(return_value=[])
    monkeypatch.setattr(
        sys.modules["fitness.app.app"],
        "get_runs_for_date_range",
        mock,
    )

    viewer_client.get(
        "/runs",
        params={"start": "2025-06-01", "end": "2025-06-30"},
    )

    mock.assert_called_once_with(date(2025, 6, 1), date(2025, 6, 30))


# -- Endpoint wiring tests for /metrics --


def test_mileage_total_widens_dates_for_timezone(
    monkeypatch, viewer_client: TestClient
):
    """When user_timezone is provided, the query date range should be widened by +-1 day."""
    mock = MagicMock(return_value=[])
    monkeypatch.setattr("fitness.app.routers.metrics.get_runs_for_date_range", mock)

    viewer_client.get(
        "/metrics/mileage/total",
        params={
            "start": "2025-06-01",
            "end": "2025-06-30",
            "user_timezone": "America/New_York",
        },
    )

    mock.assert_called_once_with(
        date(2025, 6, 1), date(2025, 6, 30), "America/New_York"
    )


def test_mileage_total_no_buffer_without_timezone(
    monkeypatch, viewer_client: TestClient
):
    """Without user_timezone, the query should use exact dates (no buffer)."""
    mock = MagicMock(return_value=[])
    monkeypatch.setattr("fitness.app.routers.metrics.get_runs_for_date_range", mock)

    viewer_client.get(
        "/metrics/mileage/total",
        params={"start": "2025-06-01", "end": "2025-06-30"},
    )

    mock.assert_called_once_with(date(2025, 6, 1), date(2025, 6, 30), None)


def test_rolling_mileage_includes_lookback_window(
    monkeypatch, viewer_client: TestClient
):
    """Rolling mileage should expand start by (window-1) days for the lookback."""
    mock = MagicMock(return_value=[])
    monkeypatch.setattr("fitness.app.routers.metrics.get_runs_for_date_range", mock)

    viewer_client.get(
        "/metrics/mileage/rolling-by-day",
        params={
            "start": "2025-06-01",
            "end": "2025-06-30",
            "window": "7",
            "user_timezone": "America/Chicago",
        },
    )

    expected_start = date(2025, 6, 1) - timedelta(days=6)  # window-1 = 6
    mock.assert_called_once_with(expected_start, date(2025, 6, 30), "America/Chicago")


def test_training_load_uses_all_runs(monkeypatch, viewer_client: TestClient):
    """Training load needs full history for ATL/CTL convergence, not date-filtered."""
    mock_all = MagicMock(return_value=[])
    mock_date_range = MagicMock(return_value=[])
    monkeypatch.setattr("fitness.app.routers.metrics.get_all_runs", mock_all)
    monkeypatch.setattr(
        "fitness.app.routers.metrics.get_runs_for_date_range", mock_date_range
    )

    viewer_client.get(
        "/metrics/training-load/by-day",
        params={
            "start": "2025-06-01",
            "end": "2025-06-30",
            "max_hr": "192",
            "resting_hr": "42",
            "lthr": "165",
            "sex": "M",
        },
    )

    mock_all.assert_called_once()
    mock_date_range.assert_not_called()
