"""Tests for sync metadata database operations."""

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from fitness.db.sync_metadata import (
    get_last_sync_time,
    update_last_sync_time,
)


class TestGetLastSyncTime:
    """Test get_last_sync_time function."""

    @patch("fitness.db.sync_metadata.get_db_cursor")
    def test_returns_sync_time_when_exists(self, mock_get_cursor):
        """Test successful sync time retrieval."""
        sync_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (sync_time,)
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        result = get_last_sync_time("strava")

        assert result == sync_time
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        assert "SELECT last_synced_at" in call_args[0]
        assert call_args[1] == ("strava",)

    @patch("fitness.db.sync_metadata.get_db_cursor")
    def test_returns_none_when_never_synced(self, mock_get_cursor):
        """Test handling of provider that has never been synced."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        result = get_last_sync_time("strava")

        assert result is None

    @patch("fitness.db.sync_metadata.get_db_cursor")
    def test_adds_timezone_if_naive(self, mock_get_cursor):
        """Test that naive datetime gets UTC timezone added."""
        naive_time = datetime(2024, 1, 15, 10, 0, 0)  # No timezone
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (naive_time,)
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        result = get_last_sync_time("hevy")

        assert result is not None
        assert result.tzinfo == timezone.utc


class TestUpdateLastSyncTime:
    """Test update_last_sync_time function."""

    @patch("fitness.db.sync_metadata.get_db_cursor")
    def test_upserts_sync_time(self, mock_get_cursor):
        """Test that sync time is upserted correctly."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        sync_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        update_last_sync_time("strava", sync_time)

        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        assert "INSERT INTO sync_metadata" in call_args[0]
        assert "ON CONFLICT" in call_args[0]
        assert call_args[1][0] == "strava"
        assert call_args[1][1] == sync_time

    @patch("fitness.db.sync_metadata.get_db_cursor")
    def test_uses_current_time_when_not_provided(self, mock_get_cursor):
        """Test that current time is used when synced_at not provided."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        update_last_sync_time("hevy")

        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        # Verify a datetime was passed (second parameter)
        assert isinstance(call_args[1][1], datetime)
        assert call_args[1][1].tzinfo is not None

    @patch("fitness.db.sync_metadata.get_db_cursor")
    def test_adds_timezone_to_naive_datetime(self, mock_get_cursor):
        """Test that naive datetime gets UTC timezone added."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        naive_time = datetime(2024, 1, 15, 10, 0, 0)  # No timezone
        update_last_sync_time("strava", naive_time)

        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        # The time should have UTC timezone added
        assert call_args[1][1].tzinfo == timezone.utc
