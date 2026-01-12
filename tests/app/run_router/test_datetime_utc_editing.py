"""
Tests specifically for datetime_utc editing functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import patch

from fitness.models import Run


@pytest.fixture
def sample_run():
    """Create a sample run for testing."""
    return Run(
        id="test_run_123",
        datetime_utc=datetime(2024, 1, 15, 10, 0, 0),
        type="Outdoor Run",
        distance=5.0,
        duration=1800.0,
        source="Strava",
        avg_heart_rate=150.0,
        shoe_id="nike_pegasus_38",
    )


class TestDatetimeUtcEditing:
    """Test datetime_utc editing scenarios."""

    @patch("fitness.app.routers.run.get_run_by_id")
    @patch("fitness.app.routers.run.update_run_with_history")
    def test_update_datetime_utc_only(
        self, mock_update, mock_get_run, sample_run, auth_client
    ):
        """Test updating only the datetime_utc field."""
        mock_get_run.return_value = sample_run
        mock_update.return_value = None

        # Updated run with new datetime
        updated_run = Run(
            id="test_run_123",
            datetime_utc=datetime(2024, 1, 15, 9, 55, 0),  # 5 minutes earlier
            type="Outdoor Run",
            distance=5.0,
            duration=1800.0,
            source="Strava",
            avg_heart_rate=150.0,
            shoe_id="nike_pegasus_38",
        )

        mock_get_run.side_effect = [sample_run, updated_run]

        update_data = {
            "datetime_utc": "2024-01-15T09:55:00",
            "changed_by": "user123",
            "change_reason": "Corrected start time - forgot to start watch immediately",
        }

        response = auth_client.patch("/runs/test_run_123", json=update_data)

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert "datetime_utc" in result["updated_fields"]

        mock_update.assert_called_once_with(
            run_id="test_run_123",
            updates={"datetime_utc": datetime(2024, 1, 15, 9, 55, 0)},
            changed_by="user123",
            change_reason="Corrected start time - forgot to start watch immediately",
        )

    @patch("fitness.app.routers.run.get_run_by_id")
    @patch("fitness.app.routers.run.update_run_with_history")
    def test_update_multiple_fields_including_datetime(
        self, mock_update, mock_get_run, sample_run, auth_client
    ):
        """Test updating multiple fields including datetime_utc."""
        mock_get_run.return_value = sample_run
        mock_update.return_value = None

        updated_run = Run(
            id="test_run_123",
            datetime_utc=datetime(2024, 1, 15, 10, 10, 0),  # 10 minutes later
            type="Outdoor Run",
            distance=5.2,  # Updated
            duration=1900.0,  # Updated
            source="Strava",
            avg_heart_rate=150.0,
            shoe_id="nike_pegasus_38",
        )

        mock_get_run.side_effect = [sample_run, updated_run]

        update_data = {
            "datetime_utc": "2024-01-15T10:10:00",
            "distance": 5.2,
            "duration": 1900.0,
            "changed_by": "user123",
            "change_reason": "Multiple corrections: start time, distance, and duration",
        }

        response = auth_client.patch("/runs/test_run_123", json=update_data)

        assert response.status_code == 200
        result = response.json()
        expected_fields = {"datetime_utc", "distance", "duration"}
        actual_fields = set(result["updated_fields"])
        assert expected_fields == actual_fields

    def test_datetime_utc_validation(self, auth_client):
        """Test datetime_utc field validation."""
        # Test with invalid datetime format
        update_data = {"datetime_utc": "invalid-date-format", "changed_by": "user123"}

        response = auth_client.patch("/runs/test_run_123", json=update_data)
        assert response.status_code == 422  # Validation error

    @patch("fitness.app.routers.run.get_run_by_id")
    @patch("fitness.app.routers.run.get_run_version")
    @patch("fitness.app.routers.run.update_run_with_history")
    def test_restore_includes_datetime_utc(
        self, mock_update, mock_get_version, mock_get_run, sample_run, auth_client
    ):
        """Test that restoration includes datetime_utc."""
        from fitness.db.runs_history import RunHistoryRecord

        mock_get_run.return_value = sample_run

        # Historical version with different datetime
        historical_version = RunHistoryRecord(
            history_id=1,
            run_id="test_run_123",
            version_number=1,
            change_type="original",
            datetime_utc=datetime(2024, 1, 15, 9, 50, 0),  # Earlier time
            type="Outdoor Run",
            distance=4.8,
            duration=1750.0,
            source="Strava",
            avg_heart_rate=148.0,
            shoe_id="nike_pegasus_38",
            changed_at=datetime(2024, 1, 15, 12, 0, 0),
            changed_by="system",
            change_reason="Initial import",
        )

        mock_get_version.return_value = historical_version
        mock_update.return_value = None
        mock_get_run.side_effect = [sample_run, sample_run]  # Second call for response

        response = auth_client.post("/runs/test_run_123/restore/1?restored_by=user123")

        assert response.status_code == 200

        # Verify the update included datetime_utc
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        updates = call_args[1]["updates"]  # keyword arguments
        assert "datetime_utc" in updates
        assert updates["datetime_utc"] == datetime(2024, 1, 15, 9, 50, 0)

    @patch("fitness.app.routers.run.get_run_by_id")
    @patch("fitness.app.routers.run.update_run_with_history")
    def test_timezone_handling_in_datetime_edit(
        self, mock_update, mock_get_run, sample_run, auth_client
    ):
        """Test that timezone information is handled correctly in datetime edits."""
        mock_get_run.return_value = sample_run
        mock_update.return_value = None
        mock_get_run.side_effect = [sample_run, sample_run]

        # Test with ISO 8601 format with timezone
        update_data = {
            "datetime_utc": "2024-01-15T10:30:00Z",  # UTC timezone explicit
            "changed_by": "user123",
            "change_reason": "Timezone correction",
        }

        response = auth_client.patch("/runs/test_run_123", json=update_data)

        assert response.status_code == 200

        # The datetime should be parsed correctly by Pydantic
        mock_update.assert_called_once()


class TestDatetimeUtcBusinessLogic:
    """Test business logic around datetime_utc editing."""

    @patch("fitness.app.routers.run.get_run_by_id")
    @patch("fitness.app.routers.run.update_run_with_history")
    def test_datetime_utc_common_use_cases(
        self, mock_update, mock_get_run, sample_run, auth_client
    ):
        """Test common use cases for datetime_utc editing."""
        mock_get_run.return_value = sample_run
        mock_update.return_value = None

        # Mock should return the run object each time it's called
        mock_get_run.side_effect = [sample_run, sample_run, sample_run, sample_run]

        # Common scenario: Forgot to start watch, actual start was 3 minutes later
        update_data = {
            "datetime_utc": "2024-01-15T10:03:00",
            "changed_by": "user123",
            "change_reason": "Forgot to start watch at beginning of run",
        }

        response = auth_client.patch("/runs/test_run_123", json=update_data)
        assert response.status_code == 200

        # Another common scenario: GPS watch had wrong timezone
        update_data = {
            "datetime_utc": "2024-01-15T15:00:00",  # 5 hours later
            "changed_by": "user123",
            "change_reason": "GPS watch was set to wrong timezone",
        }

        response = auth_client.patch("/runs/test_run_123", json=update_data)
        assert response.status_code == 200
