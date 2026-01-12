"""Tests for timezone utility functions."""

from datetime import date, datetime
from zoneinfo import ZoneInfoNotFoundError
import pytest

from fitness.utils.timezone import (
    convert_runs_to_user_timezone,
    filter_runs_by_local_date_range,
)
from fitness.models import LocalizedRun
from tests._factories.run import RunFactory


def make_run(**kwargs):
    """Helper function to create a run with given attributes."""
    factory = RunFactory()
    return factory.make(kwargs)


class TestConvertRunsToUserTimezone:
    """Test run conversion to user timezone."""

    def test_no_timezone_returns_original_dates(self):
        """Test that None timezone returns original dates."""
        runs = [
            make_run(date=date(2025, 1, 15)),
            make_run(date=date(2025, 1, 16)),
        ]
        result = convert_runs_to_user_timezone(runs, user_timezone=None)

        assert len(result) == 2
        assert result[0].local_date == date(2025, 1, 15)
        assert result[1].local_date == date(2025, 1, 16)
        assert result[0].datetime_utc == runs[0].datetime_utc
        assert result[1].datetime_utc == runs[1].datetime_utc

    def test_timezone_conversion_applies(self):
        """Test that timezone conversion is applied."""
        runs = [make_run(date=date(2025, 1, 15))]
        result = convert_runs_to_user_timezone(runs, user_timezone="Pacific/Honolulu")

        assert len(result) == 1
        assert result[0].local_date == date(2025, 1, 14)  # Previous day in Honolulu
        assert result[0].datetime_utc == runs[0].datetime_utc


class TestFilterRunsByLocalDateRange:
    """Test filtering runs by local date range."""

    def test_no_timezone_uses_utc_dates(self):
        """Test that None timezone uses original UTC filtering logic."""
        runs = [
            make_run(date=date(2025, 1, 14)),
            make_run(date=date(2025, 1, 15)),
            make_run(date=date(2025, 1, 16)),
        ]

        result = filter_runs_by_local_date_range(
            runs, start=date(2025, 1, 15), end=date(2025, 1, 15), user_timezone=None
        )

        assert len(result) == 1
        assert result[0].datetime_utc.date() == date(2025, 1, 15)

    def test_timezone_filtering_includes_converted_dates(self):
        """Test that timezone filtering includes runs from converted local dates."""
        runs = [
            make_run(date=date(2025, 1, 14)),  # This converts to 2025-01-13 in Honolulu
            make_run(date=date(2025, 1, 15)),  # This converts to 2025-01-14 in Honolulu
            make_run(date=date(2025, 1, 16)),  # This converts to 2025-01-15 in Honolulu
        ]

        # Filter for 2025-01-14 in Honolulu timezone
        result = filter_runs_by_local_date_range(
            runs,
            start=date(2025, 1, 14),
            end=date(2025, 1, 14),
            user_timezone="Pacific/Honolulu",
        )

        # Should return the run with UTC date 2025-01-15 (which converts to 2025-01-14 in Honolulu)
        assert len(result) == 1
        assert result[0].datetime_utc.date() == date(2025, 1, 15)

    def test_timezone_filtering_range(self):
        """Test timezone filtering with a date range."""
        runs = [
            make_run(date=date(2025, 1, 14)),  # Converts to 2025-01-13 in Honolulu
            make_run(date=date(2025, 1, 15)),  # Converts to 2025-01-14 in Honolulu
            make_run(date=date(2025, 1, 16)),  # Converts to 2025-01-15 in Honolulu
            make_run(date=date(2025, 1, 17)),  # Converts to 2025-01-16 in Honolulu
        ]

        # Filter for 2025-01-14 to 2025-01-15 in Honolulu timezone
        result = filter_runs_by_local_date_range(
            runs,
            start=date(2025, 1, 14),
            end=date(2025, 1, 15),
            user_timezone="Pacific/Honolulu",
        )

        # Should return runs with UTC dates 2025-01-15 and 2025-01-16
        # (which convert to 2025-01-14 and 2025-01-15 in Honolulu)
        assert len(result) == 2
        assert result[0].datetime_utc.date() == date(2025, 1, 15)
        assert result[1].datetime_utc.date() == date(2025, 1, 16)


class TestTimezoneEdgeCases:
    """Test edge cases for timezone conversion."""

    def test_empty_runs_list(self):
        """Test timezone functions with empty runs list."""
        result = filter_runs_by_local_date_range(
            [], date(2025, 1, 1), date(2025, 1, 2), "America/Chicago"
        )
        assert result == []

    def test_invalid_timezone_raises_error(self):
        """Test that invalid timezone raises appropriate error."""
        runs = [make_run(datetime_utc=datetime(2025, 1, 15, 12, 0, 0))]
        with pytest.raises(ZoneInfoNotFoundError):
            convert_runs_to_user_timezone(runs, "Invalid/Timezone")


class TestDatetimeBasedTimezoneConversion:
    """Test datetime-based timezone conversion edge cases."""

    def test_1am_utc_run_crosses_date_boundaries(self):
        """Test that a 1 AM UTC run appears on correct days across timezones."""

        # 1 AM UTC on January 15th
        utc_datetime = datetime(2025, 1, 15, 1, 0, 0)

        # Test multiple timezones
        test_cases = [
            # Eastern timezones (ahead of UTC) - should stay same day
            ("Asia/Tokyo", date(2025, 1, 15)),  # UTC+9: 1 AM UTC = 10 AM local
            ("Europe/London", date(2025, 1, 15)),  # UTC+0: 1 AM UTC = 1 AM local
            ("Europe/Berlin", date(2025, 1, 15)),  # UTC+1: 1 AM UTC = 2 AM local
            # Western timezones (behind UTC) - should shift to previous day
            ("America/New_York", date(2025, 1, 14)),  # UTC-5: 1 AM UTC = 8 PM Jan 14
            ("America/Chicago", date(2025, 1, 14)),  # UTC-6: 1 AM UTC = 7 PM Jan 14
            ("America/Denver", date(2025, 1, 14)),  # UTC-7: 1 AM UTC = 6 PM Jan 14
            ("America/Los_Angeles", date(2025, 1, 14)),  # UTC-8: 1 AM UTC = 5 PM Jan 14
            ("Pacific/Honolulu", date(2025, 1, 14)),  # UTC-10: 1 AM UTC = 3 PM Jan 14
        ]

        for timezone_str, expected_date in test_cases:
            # Create a dummy run and convert to get local date
            dummy_run = make_run(datetime_utc=utc_datetime)
            localized_run = LocalizedRun.from_run(dummy_run, timezone_str)
            result = localized_run.local_date
            assert result == expected_date, (
                f"Failed for {timezone_str}: got {result}, expected {expected_date}"
            )

    def test_midnight_utc_vs_1am_utc_difference(self):
        """Test that runs at midnight vs 1 AM UTC can end up on different local dates."""

        # Two runs on same UTC date but different times
        midnight_utc = datetime(2025, 1, 15, 0, 0, 0)
        one_am_utc = datetime(2025, 1, 15, 1, 0, 0)

        # In Chicago (UTC-6 in winter):
        # - Midnight UTC (Jan 15) = 6 PM Jan 14 local
        # - 1 AM UTC (Jan 15) = 7 PM Jan 14 local
        # Both should end up on Jan 14 in Chicago

        # Create dummy runs and convert to get local dates
        midnight_run = make_run(datetime_utc=midnight_utc)
        one_am_run = make_run(datetime_utc=one_am_utc)

        midnight_chicago = LocalizedRun.from_run(
            midnight_run, "America/Chicago"
        ).local_date
        one_am_chicago = LocalizedRun.from_run(one_am_run, "America/Chicago").local_date

        assert midnight_chicago == date(2025, 1, 14)
        assert one_am_chicago == date(2025, 1, 14)

        # But in Tokyo (UTC+9):
        # - Midnight UTC (Jan 15) = 9 AM Jan 15 local
        # - 1 AM UTC (Jan 15) = 10 AM Jan 15 local
        # Both should end up on Jan 15 in Tokyo

        midnight_tokyo = LocalizedRun.from_run(midnight_run, "Asia/Tokyo").local_date
        one_am_tokyo = LocalizedRun.from_run(one_am_run, "Asia/Tokyo").local_date

        assert midnight_tokyo == date(2025, 1, 15)
        assert one_am_tokyo == date(2025, 1, 15)

    def test_run_aggregation_with_timezone_edge_cases(self):
        """Test that runs aggregate correctly across timezone boundaries."""
        from fitness.agg.mileage import total_mileage

        # Create runs at different times on the same UTC date
        runs = [
            make_run(
                date=date(2025, 1, 15),
                datetime_utc=datetime(2025, 1, 15, 1, 0, 0),  # 1 AM UTC
                distance=5.0,
            ),
            make_run(
                date=date(2025, 1, 15),
                datetime_utc=datetime(2025, 1, 15, 12, 0, 0),  # Noon UTC
                distance=3.0,
            ),
            make_run(
                date=date(2025, 1, 15),
                datetime_utc=datetime(2025, 1, 15, 23, 0, 0),  # 11 PM UTC
                distance=2.0,
            ),
        ]

        # In Chicago timezone:
        # - 1 AM UTC (Jan 15) → 7 PM Jan 14 Chicago
        # - Noon UTC (Jan 15) → 6 AM Jan 15 Chicago
        # - 11 PM UTC (Jan 15) → 5 PM Jan 15 Chicago

        # Query for Jan 14 in Chicago should only get the first run
        jan_14_chicago = total_mileage(
            runs, date(2025, 1, 14), date(2025, 1, 14), "America/Chicago"
        )
        assert jan_14_chicago == 5.0

        # Query for Jan 15 in Chicago should get the other two runs
        jan_15_chicago = total_mileage(
            runs, date(2025, 1, 15), date(2025, 1, 15), "America/Chicago"
        )
        assert jan_15_chicago == 5.0  # 3.0 + 2.0

        # In Tokyo timezone:
        # - 1 AM UTC (Jan 15) → 10 AM Jan 15 Tokyo
        # - Noon UTC (Jan 15) → 9 PM Jan 15 Tokyo
        # - 11 PM UTC (Jan 15) → 8 AM Jan 16 Tokyo

        # Query for Jan 15 in Tokyo should get the first two runs
        jan_15_tokyo = total_mileage(
            runs, date(2025, 1, 15), date(2025, 1, 15), "Asia/Tokyo"
        )
        assert jan_15_tokyo == 8.0  # 5.0 + 3.0

        # Query for Jan 16 in Tokyo should get the third run
        jan_16_tokyo = total_mileage(
            runs, date(2025, 1, 16), date(2025, 1, 16), "Asia/Tokyo"
        )
        assert jan_16_tokyo == 2.0

    def test_year_boundary_datetime_conversion(self):
        """Test datetime conversion across year boundaries."""

        # 2 AM UTC on January 1st, 2025
        utc_datetime = datetime(2025, 1, 1, 2, 0, 0)

        # In Honolulu (UTC-10), this should be 4 PM on December 31st, 2024
        # Create dummy run and convert to get local date
        dummy_run = make_run(datetime_utc=utc_datetime)
        honolulu_date = LocalizedRun.from_run(dummy_run, "Pacific/Honolulu").local_date
        assert honolulu_date == date(2024, 12, 31)

        # In Tokyo (UTC+9), this should be 11 AM on January 1st, 2025
        tokyo_date = LocalizedRun.from_run(dummy_run, "Asia/Tokyo").local_date
        assert tokyo_date == date(2025, 1, 1)
