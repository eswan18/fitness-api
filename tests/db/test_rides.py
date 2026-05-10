"""Tests for rides database operations."""

from datetime import date, datetime
from unittest.mock import patch, MagicMock

import pytest

from fitness.models import Ride
from fitness.db.rides import (
    bulk_create_rides,
    get_existing_ride_ids,
    get_rides_for_date_range,
)


@pytest.fixture
def sample_ride():
    return Ride(
        id="strava_999",
        datetime_utc=datetime(2024, 6, 1, 14, 0, 0),
        type="Outdoor Ride",
        distance=12.0,
        duration=2700,
        source="Strava",
        avg_heart_rate=140.0,
    )


class TestBulkCreateRides:
    @patch("fitness.db.rides.get_db_connection")
    def test_returns_zero_for_empty_input(self, mock_get_conn):
        assert bulk_create_rides([]) == 0
        mock_get_conn.assert_not_called()

    @patch("fitness.db.rides.get_db_connection")
    def test_inserts_into_rides_table(self, mock_get_conn, sample_ride):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        inserted = bulk_create_rides([sample_ride])

        assert inserted == 1
        # The cursor should have run executemany once with an INSERT INTO rides
        mock_cursor.executemany.assert_called_once()
        call_args = mock_cursor.executemany.call_args
        assert "INSERT INTO rides" in call_args[0][0]
        # Defends against PK conflicts on previously-imported (incl. soft-deleted) rides.
        assert "ON CONFLICT (id) DO NOTHING" in call_args[0][0]
        # No history table interaction (rides have no history table in v1)
        assert "rides_history" not in call_args[0][0]


class TestGetExistingRideIds:
    @patch("fitness.db.rides.get_db_cursor")
    def test_returns_all_ids_including_soft_deleted(self, mock_get_cursor):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("strava_1",), ("strava_2",)]
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        result = get_existing_ride_ids()

        assert result == {"strava_1", "strava_2"}
        # Soft-deleted rides must appear here so re-imports skip them
        # instead of attempting an insert that hits a PK conflict.
        executed_sql = mock_cursor.execute.call_args[0][0]
        assert "deleted_at" not in executed_sql


class TestGetRidesForDateRange:
    @patch("fitness.db.rides.get_rides_in_date_range", return_value=[])
    def test_widens_with_timezone(self, mock_db):
        get_rides_for_date_range(date(2025, 6, 1), date(2025, 6, 30), "America/New_York")
        mock_db.assert_called_once_with(date(2025, 5, 31), date(2025, 7, 1))

    @patch("fitness.db.rides.get_rides_in_date_range", return_value=[])
    def test_exact_without_timezone(self, mock_db):
        get_rides_for_date_range(date(2025, 6, 1), date(2025, 6, 30), None)
        mock_db.assert_called_once_with(date(2025, 6, 1), date(2025, 6, 30))

    @patch("fitness.db.rides.get_rides_in_date_range", return_value=[])
    def test_defaults_to_no_timezone(self, mock_db):
        get_rides_for_date_range(date(2025, 6, 1), date(2025, 6, 30))
        mock_db.assert_called_once_with(date(2025, 6, 1), date(2025, 6, 30))
