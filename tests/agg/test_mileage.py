import pytest
from datetime import date

from fitness.agg.mileage import (
    total_mileage,
    rolling_sum,
    miles_by_day,
    avg_miles_per_day,
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
