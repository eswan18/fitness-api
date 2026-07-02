"""
Tests for runs history database operations.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from fitness.models import Run
from fitness.db.runs_history import (
    insert_run_history,
    get_run_history,
    get_run_version,
    update_run_with_history,
    RunHistoryRecord,
)


@pytest.fixture
def sample_run():
    """Create a sample run for testing."""
    return Run(
        id="test_run_123",
        datetime_utc=datetime(2024, 1, 15, 10, 0, 0),
        type="Outdoor Run",
        distance=5.0,
        duration=1800.0,  # 30 minutes
        source="Strava",
        avg_heart_rate=150.0,
        shoe_id="nike_pegasus_38",
    )


class TestInsertRunHistory:
    """Test run history insertion."""

    @patch("fitness.db.runs_history.get_db_cursor")
    def test_insert_run_history_success(self, mock_get_cursor, sample_run):
        """Test successful insertion of run history."""
        # Setup mock cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [12345]  # Mock history_id
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        # Execute
        history_id = insert_run_history(
            sample_run, version_number=1, change_type="original", changed_by="system"
        )

        # Verify
        assert history_id == 12345
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        assert "INSERT INTO runs_history" in call_args[0][0]

    @patch("fitness.db.runs_history.get_db_cursor")
    def test_insert_run_history_failure(self, mock_get_cursor, sample_run):
        """Test handling of insertion failure."""
        # Setup mock cursor to return None
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        # Execute and verify exception
        with pytest.raises(Exception, match="Failed to insert run history record"):
            insert_run_history(sample_run, 1, "original")


class TestGetRunHistory:
    """Test run history retrieval."""

    @patch("fitness.db.runs_history.get_db_cursor")
    def test_get_run_history_success(self, mock_get_cursor):
        """Test successful retrieval of run history."""
        # Setup mock data
        mock_rows = [
            (
                1,
                "test_run_123",
                2,
                "edit",
                datetime(2024, 1, 15, 10, 0),
                "Outdoor Run",
                5.5,
                1900.0,
                "Strava",
                155.0,
                "nike_pegasus_38",
                datetime(2024, 1, 16, 8, 0),
                "user123",
                "Updated distance",
                "Morning Tempo",
            ),
            (
                2,
                "test_run_123",
                1,
                "original",
                datetime(2024, 1, 15, 10, 0),
                "Outdoor Run",
                5.0,
                1800.0,
                "Strava",
                150.0,
                "nike_pegasus_38",
                datetime(2024, 1, 15, 12, 0),
                "system",
                "Initial import",
                None,
            ),
        ]

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_rows
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        # Execute
        history = get_run_history("test_run_123")

        # Verify
        assert len(history) == 2
        assert isinstance(history[0], RunHistoryRecord)
        assert history[0].run_id == "test_run_123"
        assert history[0].version_number == 2
        assert history[0].change_type == "edit"
        assert history[0].name == "Morning Tempo"
        assert history[1].name is None
        mock_cursor.execute.assert_called_once()

    @patch("fitness.db.runs_history.get_db_cursor")
    def test_get_run_history_with_limit(self, mock_get_cursor):
        """Test retrieval with limit parameter."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        # Execute
        get_run_history("test_run_123", limit=10)

        # Verify limit was applied
        call_args = mock_cursor.execute.call_args[0]
        assert "LIMIT %s" in call_args[0]
        assert 10 in call_args[1]


class TestUpdateRunWithHistory:
    """Test run updates with history tracking."""

    @patch("fitness.db.runs_history.get_db_connection")
    @patch("fitness.db.runs.get_run_by_id")
    def test_update_run_with_history_success(
        self, mock_get_run, mock_get_connection, sample_run
    ):
        """Test successful run update with history tracking."""
        # Setup mocks
        mock_get_run.return_value = sample_run

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [1]  # Current version
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_connection.return_value.__enter__.return_value = mock_connection

        # Execute
        updates = {"distance": 5.5, "avg_heart_rate": 155.0}
        update_run_with_history(
            "test_run_123", updates, "user123", "Corrected GPS data"
        )

        # Verify transaction was used
        mock_connection.transaction.assert_called_once()

        # Verify cursor operations
        assert (
            mock_cursor.execute.call_count >= 2
        )  # At least INSERT into history and UPDATE current

    @patch("fitness.db.runs_history.get_db_connection")
    @patch("fitness.db.runs.get_run_by_id")
    def test_update_run_with_history_snapshots_name(
        self, mock_get_run, mock_get_connection, sample_run
    ):
        """`name` is an allowed field and its new value is snapshotted into
        the history row (run names feed calendar event titles, so they need
        the same history/version tracking as every other editable field)."""
        mock_get_run.return_value = sample_run

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [1]  # Current version
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_connection.return_value.__enter__.return_value = mock_connection

        update_run_with_history(
            "test_run_123", {"name": "Race Day"}, "user123", "Named the run"
        )

        # Find the INSERT INTO runs_history call and check the snapshotted name.
        history_insert_call = next(
            call
            for call in mock_cursor.execute.call_args_list
            if "INSERT INTO runs_history" in call.args[0]
        )
        params = history_insert_call.args[1]
        assert params[-1] == "Race Day"  # `name` is the last column in the INSERT

    @patch("fitness.db.runs_history.get_db_connection")
    @patch("fitness.db.runs.get_run_by_id")
    def test_update_run_with_history_snapshots_cleared_name(
        self, mock_get_run, mock_get_connection, sample_run
    ):
        """Passing `name=None` explicitly clears it to NULL in the history
        snapshot too, not just the live row."""
        mock_get_run.return_value = sample_run

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [1]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_connection.return_value.__enter__.return_value = mock_connection

        update_run_with_history("test_run_123", {"name": None}, "user123")

        history_insert_call = next(
            call
            for call in mock_cursor.execute.call_args_list
            if "INSERT INTO runs_history" in call.args[0]
        )
        params = history_insert_call.args[1]
        assert params[-1] is None

        # The UPDATE ... SET name = %s statement must also carry NULL as a
        # bound parameter (not a literal), which psycopg maps to SQL NULL.
        # The query is a psycopg `sql.Composed` object (not a plain string),
        # so stringify it before substring-matching.
        update_call = next(
            call
            for call in mock_cursor.execute.call_args_list
            if "UPDATE runs" in str(call.args[0])
        )
        assert None in update_call.args[1]

    @patch("fitness.db.runs_history.get_db_connection")
    @patch("fitness.db.runs.get_run_by_id")
    def test_update_run_with_history_run_not_found(
        self, mock_get_run, mock_get_connection
    ):
        """Test handling of non-existent run."""
        mock_get_run.return_value = None
        mock_conn = MagicMock()
        mock_get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.transaction.return_value.__enter__.return_value = None

        with pytest.raises(ValueError, match="Run test_run_123 not found"):
            update_run_with_history("test_run_123", {"distance": 5.5}, "user123")

    @patch("fitness.db.runs_history.get_db_connection")
    @patch("fitness.db.runs.get_run_by_id")
    def test_update_run_with_history_invalid_field(
        self, mock_get_run, mock_get_connection, sample_run
    ):
        """Test handling of invalid update fields."""
        # This test should fail early during field validation, before any DB operations
        mock_get_run.return_value = sample_run

        # We shouldn't even get to database operations due to validation failure
        with pytest.raises(
            ValueError, match="Field 'source' is not allowed to be updated"
        ):
            update_run_with_history(
                "test_run_123", {"source": "MapMyFitness"}, "user123"
            )


class TestGetRunVersion:
    """Test specific version retrieval."""

    @patch("fitness.db.runs_history.get_db_cursor")
    def test_get_run_version_found(self, mock_get_cursor):
        """Test successful retrieval of specific version."""
        mock_row = (
            1,
            "test_run_123",
            1,
            "original",
            datetime(2024, 1, 15, 10, 0),
            "Outdoor Run",
            5.0,
            1800.0,
            "Strava",
            150.0,
            "nike_pegasus_38",
            datetime(2024, 1, 15, 12, 0),
            "system",
            "Initial import",
            "Morning Tempo",
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = mock_row
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        # Execute
        version = get_run_version("test_run_123", 1)

        # Verify
        assert version is not None
        assert isinstance(version, RunHistoryRecord)
        assert version.run_id == "test_run_123"
        assert version.version_number == 1
        assert version.name == "Morning Tempo"

    @patch("fitness.db.runs_history.get_db_cursor")
    def test_get_run_version_not_found(self, mock_get_cursor):
        """Test handling of non-existent version."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        # Execute
        version = get_run_version("test_run_123", 99)

        # Verify
        assert version is None
