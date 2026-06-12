import pytest
from datetime import date, datetime

from fitness.agg.mileage import (
    total_mileage,
    rolling_sum,
    miles_by_day,
    miles_by_week,
    avg_miles_per_day,
    week_anchor,
)


def test_total_mileage(run_factory):
    miles = total_mileage(
        [
            run_factory.make(update={"distance": 5.0}),
            run_factory.make(update={"distance": 3.0}),
            run_factory.make(update={"distance": 2.0}),
        ],
        start=date(2023, 10, 1),
        end=date(2023, 10, 8),
    )
    assert miles == 10.0


def test_avg_miles_per_day(run_factory):
    runs = [
        run_factory.make(update={"distance": 5.0, "date": date(2023, 10, 1)}),
        run_factory.make(update={"distance": 3.0, "date": date(2023, 10, 2)}),
        run_factory.make(update={"distance": 1.0, "date": date(2023, 10, 2)}),
        run_factory.make(update={"distance": 2.0, "date": date(2023, 10, 5)}),
        run_factory.make(update={"distance": 2.0, "date": date(2023, 10, 6)}),
    ]
    avg = avg_miles_per_day(
        runs=runs,
        start=date(2023, 10, 1),
        end=date(2023, 10, 8),  # Note this date is beyond the last run date.
    )
    assert avg == pytest.approx(13 / 8)


def test_rolling_sum(run_factory):
    runs = [
        run_factory.make(update={"distance": 5.0, "date": date(2023, 10, 1)}),
        run_factory.make(update={"distance": 3.0, "date": date(2023, 10, 2)}),
        run_factory.make(update={"distance": 1.0, "date": date(2023, 10, 2)}),
        run_factory.make(update={"distance": 2.0, "date": date(2023, 10, 5)}),
        run_factory.make(update={"distance": 2.0, "date": date(2023, 10, 6)}),
    ]
    # Check a few different window sizes.
    window_1_results = rolling_sum(
        runs=runs, start=date(2023, 10, 1), end=date(2023, 10, 6), window=1
    )
    assert window_1_results == [
        (date(2023, 10, 1), 5),
        (date(2023, 10, 2), 4),
        (date(2023, 10, 3), 0),
        (date(2023, 10, 4), 0),
        (date(2023, 10, 5), 2),
        (date(2023, 10, 6), 2),
    ]
    window_2_results = rolling_sum(
        runs=runs, start=date(2023, 10, 1), end=date(2023, 10, 6), window=2
    )
    assert window_2_results == [
        (date(2023, 10, 1), 5),
        (date(2023, 10, 2), 9),
        (date(2023, 10, 3), 4),
        (date(2023, 10, 4), 0),
        (date(2023, 10, 5), 2),
        (date(2023, 10, 6), 4),
    ]
    window_3_results = rolling_sum(
        runs=runs, start=date(2023, 10, 1), end=date(2023, 10, 6), window=3
    )
    assert window_3_results == [
        (date(2023, 10, 1), 5),
        (date(2023, 10, 2), 9),
        (date(2023, 10, 3), 9),
        (date(2023, 10, 4), 4),
        (date(2023, 10, 5), 2),
        (date(2023, 10, 6), 4),
    ]
    # Make sure that runs outside the range are included if they are in the window.
    later_window = rolling_sum(
        runs=runs, start=date(2023, 10, 3), end=date(2023, 10, 6), window=3
    )
    assert later_window == [
        (date(2023, 10, 3), 9),
        (date(2023, 10, 4), 4),
        (date(2023, 10, 5), 2),
        (date(2023, 10, 6), 4),
    ]


def test_week_anchor_monday():
    # 2023-10-02 is a Monday.
    assert week_anchor(date(2023, 10, 2)) == date(2023, 10, 2)
    assert week_anchor(date(2023, 10, 4)) == date(2023, 10, 2)
    assert week_anchor(date(2023, 10, 8)) == date(2023, 10, 2)  # Sunday
    # A Sunday belongs to the week that started the previous Monday.
    assert week_anchor(date(2023, 10, 1)) == date(2023, 9, 25)


def test_week_anchor_sunday():
    # 2023-10-01 is a Sunday.
    assert week_anchor(date(2023, 10, 1), "sunday") == date(2023, 10, 1)
    assert week_anchor(date(2023, 10, 4), "sunday") == date(2023, 10, 1)
    assert week_anchor(date(2023, 10, 7), "sunday") == date(2023, 10, 1)  # Saturday
    assert week_anchor(date(2023, 10, 8), "sunday") == date(2023, 10, 8)


def test_miles_by_week(run_factory):
    runs = [
        # 2023-10-01 is a Sunday; 2023-10-02 is a Monday.
        run_factory.make(update={"distance": 5.0, "date": date(2023, 10, 1)}),
        run_factory.make(update={"distance": 3.0, "date": date(2023, 10, 2)}),
        run_factory.make(update={"distance": 1.0, "date": date(2023, 10, 2)}),
        run_factory.make(update={"distance": 2.0, "date": date(2023, 10, 5)}),
        run_factory.make(update={"distance": 2.0, "date": date(2023, 10, 6)}),
        run_factory.make(update={"distance": 4.0, "date": date(2023, 10, 9)}),
    ]
    results = miles_by_week(runs, start=date(2023, 10, 1), end=date(2023, 10, 9))
    assert results == [
        (date(2023, 9, 25), 5.0),  # Oct 1 (Sunday) falls in the Sep 25 week
        (date(2023, 10, 2), 8.0),
        (date(2023, 10, 9), 4.0),
    ]


def test_miles_by_week_zero_fills_empty_weeks(run_factory):
    runs = [
        run_factory.make(update={"distance": 5.0, "date": date(2023, 10, 2)}),
    ]
    results = miles_by_week(runs, start=date(2023, 10, 2), end=date(2023, 10, 29))
    assert results == [
        (date(2023, 10, 2), 5.0),
        (date(2023, 10, 9), 0.0),
        (date(2023, 10, 16), 0.0),
        (date(2023, 10, 23), 0.0),
    ]


def test_miles_by_week_sunday_start(run_factory):
    runs = [
        run_factory.make(update={"distance": 5.0, "date": date(2023, 10, 1)}),
        run_factory.make(update={"distance": 4.0, "date": date(2023, 10, 2)}),
        run_factory.make(update={"distance": 2.0, "date": date(2023, 10, 7)}),
        run_factory.make(update={"distance": 4.0, "date": date(2023, 10, 9)}),
    ]
    results = miles_by_week(
        runs, start=date(2023, 10, 1), end=date(2023, 10, 9), week_start="sunday"
    )
    assert results == [
        (date(2023, 10, 1), 11.0),  # Sun Oct 1 through Sat Oct 7
        (date(2023, 10, 8), 4.0),
    ]


def test_miles_by_week_counts_runs_outside_range_but_in_edge_weeks(run_factory):
    runs = [
        run_factory.make(update={"distance": 3.0, "date": date(2023, 10, 2)}),
        run_factory.make(update={"distance": 2.0, "date": date(2023, 10, 5)}),
        run_factory.make(update={"distance": 1.0, "date": date(2023, 10, 8)}),
    ]
    # The range starts mid-week, but the Oct 2 run still counts toward the
    # Oct 2 week because weekly totals are always full-week totals.
    results = miles_by_week(runs, start=date(2023, 10, 4), end=date(2023, 10, 6))
    assert results == [
        (date(2023, 10, 2), 6.0),
    ]


def test_miles_by_week_with_user_timezone(run_factory):
    # 2 AM UTC on Monday Oct 2 is still Sunday Oct 1 in Chicago, which belongs
    # to the previous Monday-start week.
    runs = [
        run_factory.make(
            update={"distance": 5.0, "datetime_utc": datetime(2023, 10, 2, 2, 0, 0)}
        ),
    ]
    utc_results = miles_by_week(runs, start=date(2023, 9, 25), end=date(2023, 10, 8))
    assert utc_results == [
        (date(2023, 9, 25), 0.0),
        (date(2023, 10, 2), 5.0),
    ]
    chicago_results = miles_by_week(
        runs,
        start=date(2023, 9, 25),
        end=date(2023, 10, 8),
        user_timezone="America/Chicago",
    )
    assert chicago_results == [
        (date(2023, 9, 25), 5.0),
        (date(2023, 10, 2), 0.0),
    ]


def test_miles_by_day(run_factory):
    runs = [
        run_factory.make(update={"distance": 5.0, "date": date(2023, 10, 1)}),
        run_factory.make(update={"distance": 3.0, "date": date(2023, 10, 2)}),
        run_factory.make(update={"distance": 1.0, "date": date(2023, 10, 2)}),
        run_factory.make(update={"distance": 2.0, "date": date(2023, 10, 5)}),
        run_factory.make(update={"distance": 2.0, "date": date(2023, 10, 6)}),
    ]
    # Check a few different window sizes.
    results = miles_by_day(runs=runs, start=date(2023, 10, 1), end=date(2023, 10, 6))
    assert results == [
        (date(2023, 10, 1), 5),
        (date(2023, 10, 2), 4),
        (date(2023, 10, 3), 0),
        (date(2023, 10, 4), 0),
        (date(2023, 10, 5), 2),
        (date(2023, 10, 6), 2),
    ]
