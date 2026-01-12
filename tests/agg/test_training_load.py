import pytest
from datetime import date
from fitness.agg.training_load import (
    trimp,
    trimp_by_day,
    training_stress_balance,
    _exponential_training_load,
    _calculate_atl_and_ctl,
)
from tests._factories.run import RunFactory


class TestTrimp:
    """Tests for the trimp() function."""

    def test_trimp_calculation_male(self):
        """Test TRIMP calculation for male runner."""
        run = RunFactory().make(
            {
                "date": date(2024, 1, 1),
                "duration": 2400,  # 40 minutes
                "avg_heart_rate": 150,
            }
        )

        result = trimp(run, max_hr=190, resting_hr=50, sex="M")

        # Expected calculation:
        # hr_relative = (150 - 50) / (190 - 50) = 100/140 ≈ 0.714
        # y = 0.64 * exp(1.92 * 0.714) ≈ 0.64 * exp(1.371) ≈ 0.64 * 3.94 ≈ 2.52
        # duration_minutes = 2400 / 60 = 40
        # trimp = 40 * 0.714 * 2.52 ≈ 72.1
        assert result == pytest.approx(72.1, abs=1.0)

    def test_trimp_calculation_female(self):
        """Test TRIMP calculation for female runner."""
        run = RunFactory().make(
            {
                "date": date(2024, 1, 1),
                "duration": 2400,  # 40 minutes
                "avg_heart_rate": 150,
            }
        )

        result = trimp(run, max_hr=190, resting_hr=50, sex="F")

        # Expected calculation:
        # hr_relative = (150 - 50) / (190 - 50) = 100/140 ≈ 0.714
        # y = 0.86 * exp(1.67 * 0.714) ≈ 0.86 * exp(1.192) ≈ 0.86 * 3.29 ≈ 2.83
        # duration_minutes = 2400 / 60 = 40
        # trimp = 40 * 0.714 * 2.83 ≈ 80.9
        assert result == pytest.approx(80.9, abs=1.0)

    def test_trimp_no_heart_rate(self):
        """Test that TRIMP calculation raises error when no heart rate."""
        run = RunFactory().make(
            {
                "date": date(2024, 1, 1),
                "duration": 2400,
                "avg_heart_rate": None,
            }
        )

        with pytest.raises(ValueError, match="Run must have an average heart rate"):
            trimp(run, max_hr=190, resting_hr=50, sex="M")

    def test_trimp_hr_clamping(self):
        """Test that heart rate relative is clamped to [0, 1] range."""
        # Test with heart rate above max_hr
        run_high = RunFactory().make(
            {
                "date": date(2024, 1, 1),
                "duration": 3600,  # 60 minutes
                "avg_heart_rate": 200,  # Above max_hr of 190
            }
        )

        result_high = trimp(run_high, max_hr=190, resting_hr=50, sex="M")

        # Should be clamped to hr_relative = 1.0
        # y = 0.64 * exp(1.92 * 1.0) ≈ 0.64 * 6.82 ≈ 4.36
        # trimp = 60 * 1.0 * 4.36 ≈ 261.8
        assert result_high == pytest.approx(261.8, abs=5.0)

        # Test with heart rate below resting_hr
        run_low = RunFactory().make(
            {
                "date": date(2024, 1, 1),
                "duration": 3600,  # 60 minutes
                "avg_heart_rate": 40,  # Below resting_hr of 50
            }
        )

        result_low = trimp(run_low, max_hr=190, resting_hr=50, sex="M")

        # Should be clamped to hr_relative = 0.0
        # y = 0.64 * exp(1.92 * 0.0) = 0.64 * 1 = 0.64
        # trimp = 60 * 0.0 * 0.64 = 0
        assert result_low == 0.0


class TestTrimpByDay:
    """Tests for the trimp_by_day() function."""

    def test_single_run_day(self):
        """Test TRIMP calculation for a single run on one day."""
        runs = [
            RunFactory().make(
                {
                    "date": date(2024, 1, 15),
                    "duration": 2400,  # 40 minutes
                    "avg_heart_rate": 150,
                }
            )
        ]

        result = trimp_by_day(
            runs=runs,
            start=date(2024, 1, 15),
            end=date(2024, 1, 15),
            max_hr=190,
            resting_hr=50,
            sex="M",
        )

        assert len(result) == 1
        assert result[0].date == date(2024, 1, 15)
        assert result[0].trimp == pytest.approx(72.1, abs=1.0)

    def test_multiple_runs_same_day(self):
        """Test TRIMP calculation for multiple runs on the same day."""
        runs = [
            RunFactory().make(
                {
                    "date": date(2024, 1, 15),
                    "distance": 3.0,
                    "duration": 1800,  # 30 minutes
                    "avg_heart_rate": 140,
                }
            ),
            RunFactory().make(
                {
                    "date": date(2024, 1, 15),
                    "distance": 2.0,
                    "duration": 1200,  # 20 minutes
                    "avg_heart_rate": 160,
                }
            ),
        ]

        result = trimp_by_day(
            runs=runs,
            start=date(2024, 1, 15),
            end=date(2024, 1, 15),
            max_hr=190,
            resting_hr=50,
            sex="M",
        )

        assert len(result) == 1
        assert result[0].date == date(2024, 1, 15)
        # Should be sum of both runs' TRIMP values
        assert result[0].trimp > 0

    def test_multiple_days_with_gaps(self):
        """Test TRIMP calculation across multiple days including days with no runs."""
        runs = [
            RunFactory().make(
                {
                    "date": date(2024, 1, 15),
                    "duration": 2400,
                    "avg_heart_rate": 150,
                }
            ),
            RunFactory().make(
                {
                    "date": date(2024, 1, 17),  # Skip Jan 16
                    "distance": 3.0,
                    "duration": 1800,
                    "avg_heart_rate": 140,
                }
            ),
        ]

        result = trimp_by_day(
            runs=runs,
            start=date(2024, 1, 15),
            end=date(2024, 1, 17),
            max_hr=190,
            resting_hr=50,
            sex="M",
        )

        assert len(result) == 3  # 3 days total
        assert result[0].date == date(2024, 1, 15)
        assert result[0].trimp > 0  # Has a run
        assert result[1].date == date(2024, 1, 16)
        assert result[1].trimp == 0.0  # No runs
        assert result[2].date == date(2024, 1, 17)
        assert result[2].trimp > 0  # Has a run

    def test_runs_without_heart_rate_excluded(self):
        """Test that runs without heart rate data are excluded from TRIMP calculation."""
        runs = [
            RunFactory().make(
                {
                    "date": date(2024, 1, 15),
                    "duration": 2400,
                    "avg_heart_rate": 150,  # Has heart rate
                }
            ),
            RunFactory().make(
                {
                    "date": date(2024, 1, 15),
                    "distance": 3.0,
                    "duration": 1800,
                    "avg_heart_rate": None,  # No heart rate
                }
            ),
        ]

        result = trimp_by_day(
            runs=runs,
            start=date(2024, 1, 15),
            end=date(2024, 1, 15),
            max_hr=190,
            resting_hr=50,
            sex="M",
        )

        assert len(result) == 1
        assert result[0].date == date(2024, 1, 15)
        # Should only include TRIMP from the run with heart rate data
        expected_trimp = trimp(runs[0], max_hr=190, resting_hr=50, sex="M")
        assert result[0].trimp == pytest.approx(expected_trimp, abs=0.1)

    def test_no_runs_in_range(self):
        """Test TRIMP calculation when no runs exist in the date range."""
        runs = []

        result = trimp_by_day(
            runs=runs,
            start=date(2024, 1, 15),
            end=date(2024, 1, 17),
            max_hr=190,
            resting_hr=50,
            sex="M",
        )

        assert len(result) == 3  # 3 days in range
        for day_trimp in result:
            assert day_trimp.trimp == 0.0

    def test_runs_outside_date_range_excluded(self):
        """Test that runs outside the specified date range are excluded."""
        runs = [
            RunFactory().make(
                {
                    "date": date(2024, 1, 14),  # Before range
                    "duration": 2400,
                    "avg_heart_rate": 150,
                }
            ),
            RunFactory().make(
                {
                    "date": date(2024, 1, 15),  # In range
                    "distance": 3.0,
                    "duration": 1800,
                    "avg_heart_rate": 140,
                }
            ),
            RunFactory().make(
                {
                    "date": date(2024, 1, 18),  # After range
                    "distance": 4.0,
                    "duration": 2000,
                    "avg_heart_rate": 145,
                }
            ),
        ]

        result = trimp_by_day(
            runs=runs,
            start=date(2024, 1, 15),
            end=date(2024, 1, 17),
            max_hr=190,
            resting_hr=50,
            sex="M",
        )

        assert len(result) == 3  # 3 days in range
        assert result[0].date == date(2024, 1, 15)
        assert result[0].trimp > 0  # Only the run on Jan 15
        assert result[1].trimp == 0.0  # No runs on Jan 16
        assert result[2].trimp == 0.0  # No runs on Jan 17

    def test_start_date_before_any_runs(self):
        """Test TRIMP calculation when start date is before any runs exist."""
        runs = [
            RunFactory().make(
                {
                    "date": date(2024, 1, 20),  # Run on Jan 20
                    "duration": 2400,
                    "avg_heart_rate": 150,
                }
            )
        ]

        # Request TRIMP data starting from Jan 15 (before any runs)
        result = trimp_by_day(
            runs=runs,
            start=date(2024, 1, 15),
            end=date(2024, 1, 22),
            max_hr=190,
            resting_hr=50,
            sex="M",
        )

        assert len(result) == 8  # 8 days from Jan 15-22
        assert result[0].date == date(2024, 1, 15)
        assert result[0].trimp == 0.0  # No runs on Jan 15
        assert result[5].date == date(2024, 1, 20)
        assert result[5].trimp > 0  # Has the run on Jan 20


class TestExponentialTrainingLoad:
    """Tests for the _exponential_training_load() function."""

    def test_exponential_training_load_basic(self):
        """Test basic exponential training load calculation."""
        trimp_values = [100.0, 50.0, 75.0, 0.0, 25.0]
        tau = 7  # 7-day time constant

        result = _exponential_training_load(trimp_values, tau)

        assert len(result) == 5
        # First value should be close to input since there's no history
        assert result[0] == pytest.approx(13.3, abs=1.0)
        # Values should be positive and reasonable
        for val in result:
            assert val >= 0
            assert val <= 200  # Should not exceed reasonable bounds

    def test_exponential_training_load_zero_values(self):
        """Test exponential training load with zero TRIMP values."""
        trimp_values = [0.0, 0.0, 0.0, 0.0]
        tau = 7

        result = _exponential_training_load(trimp_values, tau)

        assert len(result) == 4
        for val in result:
            assert val == 0.0

    def test_exponential_training_load_single_spike(self):
        """Test exponential training load with a single high value."""
        trimp_values = [0.0, 100.0, 0.0, 0.0, 0.0]
        tau = 7

        result = _exponential_training_load(trimp_values, tau)

        assert len(result) == 5
        assert result[0] == 0.0
        assert result[1] > result[0]  # Should increase after spike
        assert result[2] < result[1]  # Should decay after spike
        assert result[3] < result[2]  # Should continue decaying
        assert result[4] < result[3]  # Should continue decaying

    def test_exponential_training_load_different_tau(self):
        """Test that different tau values produce different decay rates."""
        trimp_values = [100.0, 0.0, 0.0, 0.0, 0.0]

        result_fast = _exponential_training_load(trimp_values, tau=3)  # Fast response
        result_slow = _exponential_training_load(trimp_values, tau=14)  # Slow response

        # Larger tau means smaller alpha (less responsive)
        # Fast response should have different values than slow response
        assert result_fast[1] != result_slow[1]  # Different immediate response
        assert result_fast[2] != result_slow[2]  # Different decay behavior

        # Both should start with the spike
        assert result_fast[0] > 0
        assert result_slow[0] > 0

        # Both should decay after the spike
        assert result_fast[2] < result_fast[1]
        assert result_slow[2] < result_slow[1]


class TestCalculateAtlAndCtl:
    """Tests for the _calculate_atl_and_ctl() function."""

    def test_calculate_atl_and_ctl_basic(self):
        """Test basic ATL and CTL calculation."""
        trimp_values = [50.0, 60.0, 55.0, 70.0, 45.0, 65.0, 50.0]

        atl, ctl = _calculate_atl_and_ctl(trimp_values)

        assert len(atl) == 7
        assert len(ctl) == 7

        # ATL should generally be more responsive (higher values) than CTL
        # for recent high training loads
        assert atl[-1] > ctl[-1]  # Acute should be higher than chronic

        # All values should be positive
        for val in atl + ctl:
            assert val >= 0

    def test_calculate_atl_and_ctl_empty(self):
        """Test ATL and CTL calculation with empty input."""
        atl, ctl = _calculate_atl_and_ctl([])

        assert atl == []
        assert ctl == []

    def test_calculate_atl_and_ctl_single_value(self):
        """Test ATL and CTL calculation with single value."""
        trimp_values = [100.0]

        atl, ctl = _calculate_atl_and_ctl(trimp_values)

        assert len(atl) == 1
        assert len(ctl) == 1
        assert atl[0] > 0
        assert ctl[0] > 0
        # ATL should be higher than CTL for single spike
        assert atl[0] > ctl[0]


class TestTrainingStressBalance:
    """Tests for the training_stress_balance() function."""

    def test_training_stress_balance_basic(self):
        """Test basic TSB calculation with sample data."""
        runs = [
            RunFactory().make(
                {
                    "date": date(2024, 1, 15),
                    "duration": 3000,  # 50 minutes
                    "avg_heart_rate": 150,
                }
            ),
            RunFactory().make(
                {
                    "date": date(2024, 1, 16),
                    "duration": 2400,  # 40 minutes
                    "avg_heart_rate": 145,
                }
            ),
            RunFactory().make(
                {
                    "date": date(2024, 1, 17),
                    "duration": 1800,  # 30 minutes
                    "avg_heart_rate": 140,
                }
            ),
        ]

        result = training_stress_balance(
            runs=runs,
            max_hr=190,
            resting_hr=50,
            sex="M",
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 17),
        )

        assert len(result) == 3

        for day_load in result:
            assert day_load.date >= date(2024, 1, 15)
            assert day_load.date <= date(2024, 1, 17)
            assert day_load.training_load.ctl >= 0
            assert day_load.training_load.atl >= 0
            # TSB = CTL - ATL, so it can be negative
            assert isinstance(day_load.training_load.tsb, float)

    def test_training_stress_balance_no_heart_rate_runs_excluded(self):
        """Test that runs without heart rate are excluded from TSB calculation."""
        runs = [
            RunFactory().make(
                {
                    "date": date(2024, 1, 15),
                    "duration": 3000,
                    "avg_heart_rate": 150,  # Has heart rate
                }
            ),
            RunFactory().make(
                {
                    "date": date(2024, 1, 15),
                    "duration": 2400,
                    "avg_heart_rate": None,  # No heart rate - should be excluded
                }
            ),
        ]

        result = training_stress_balance(
            runs=runs,
            max_hr=190,
            resting_hr=50,
            sex="M",
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 15),
        )

        assert len(result) == 1
        # Should only reflect the run with heart rate data
        assert result[0].training_load.atl > 0
        assert result[0].training_load.ctl > 0

    def test_training_stress_balance_empty_runs(self):
        """Test TSB calculation with no runs."""
        result = training_stress_balance(
            runs=[],
            max_hr=190,
            resting_hr=50,
            sex="M",
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 17),
        )

        assert len(result) == 3  # Should still return entries for each day
        for day_load in result:
            assert day_load.training_load.ctl == 0.0
            assert day_load.training_load.atl == 0.0
            assert day_load.training_load.tsb == 0.0

    def test_training_stress_balance_different_sex(self):
        """Test that male and female calculations produce different results."""
        runs = [
            RunFactory().make(
                {
                    "date": date(2024, 1, 15),
                    "duration": 3000,
                    "avg_heart_rate": 150,
                }
            )
        ]

        result_male = training_stress_balance(
            runs=runs,
            max_hr=190,
            resting_hr=50,
            sex="M",
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 15),
        )

        result_female = training_stress_balance(
            runs=runs,
            max_hr=190,
            resting_hr=50,
            sex="F",
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 15),
        )

        # Results should be different due to different TRIMP calculations
        assert result_male[0].training_load.atl != result_female[0].training_load.atl
        assert result_male[0].training_load.ctl != result_female[0].training_load.ctl

    def test_training_stress_balance_date_range_filtering(self):
        """Test that runs outside the calculation start are included for context."""
        runs = [
            RunFactory().make(
                {
                    "date": date(
                        2024, 1, 10
                    ),  # Before requested range but should affect calculations
                    "duration": 3000,
                    "avg_heart_rate": 150,
                }
            ),
            RunFactory().make(
                {
                    "date": date(2024, 1, 15),  # In requested range
                    "duration": 2400,
                    "avg_heart_rate": 145,
                }
            ),
        ]

        result = training_stress_balance(
            runs=runs,
            max_hr=190,
            resting_hr=50,
            sex="M",
            start_date=date(2024, 1, 15),  # Only want results from this date
            end_date=date(2024, 1, 15),
        )

        assert len(result) == 1
        assert result[0].date == date(2024, 1, 15)
        # The earlier run should have affected the CTL/ATL values
        assert result[0].training_load.ctl > 0
        assert result[0].training_load.atl > 0
