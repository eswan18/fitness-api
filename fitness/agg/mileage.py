from collections import deque
from datetime import timedelta, date

from fitness.models import Run
from fitness.utils.timezone import (
    filter_runs_by_local_date_range,
    convert_runs_to_user_timezone,
)


def total_mileage(
    runs: list[Run], start: date, end: date, user_timezone: str | None = None
) -> float:
    """
    Calculate the total mileage for a list of runs.

    Args:
        runs: List of runs (with UTC dates)
        start: Start date in user's timezone
        end: End date in user's timezone
        user_timezone: User's timezone (e.g., "America/Chicago"). If None, uses UTC dates.
    """
    filtered_runs = filter_runs_by_local_date_range(runs, start, end, user_timezone)
    return sum(run.distance for run in filtered_runs)


def avg_miles_per_day(
    runs: list[Run], start: date, end: date, user_timezone: str | None = None
) -> float:
    """
    Calculate the average mileage per day for a list of runs in the range [start, end].

    Args:
        runs: List of runs (with UTC dates)
        start: Start date in user's timezone
        end: End date in user's timezone
        user_timezone: User's timezone (e.g., "America/Chicago"). If None, uses UTC dates.
    """
    total_days = (end - start).days + 1
    if total_days <= 0:
        return 0.0
    return total_mileage(runs, start, end, user_timezone) / total_days


def miles_by_day(
    runs: list[Run], start: date, end: date, user_timezone: str | None = None
) -> list[tuple[date, float]]:
    """
    Calculate the total mileage for each day in the range [start, end].

    Args:
        runs: List of runs (with UTC dates)
        start: Start date in user's timezone
        end: End date in user's timezone
        user_timezone: User's timezone (e.g., "America/Chicago"). If None, uses UTC dates.
    """
    return rolling_sum(runs, start, end, window=1, user_timezone=user_timezone)


def rolling_sum(
    runs: list[Run],
    start: date,
    end: date,
    window: int,
    user_timezone: str | None = None,
) -> list[tuple[date, float]]:
    """
    Calculate the rolling sum of distances for a list of runs.

    The rolling sum is calculated over a window of the previous `window` days, including
    the current day. Returns a list of (day, window_sum).

    Args:
        runs: List of runs (with UTC dates)
        start: Start date in user's timezone
        end: End date in user's timezone
        window: Number of days to include in rolling window
        user_timezone: User's timezone (e.g., "America/Chicago"). If None, uses UTC dates.
    """
    # 1. Convert runs to user timezone if specified
    user_tz_runs = convert_runs_to_user_timezone(runs, user_timezone)

    # 2. Bucket runs into miles-per-day using local dates
    miles_per_day: dict[date, float] = {}
    for localized_run in user_tz_runs:
        miles_per_day.setdefault(localized_run.local_date, 0.0)
        miles_per_day[localized_run.local_date] += localized_run.distance

    # 2. Determine the first day we need to consider
    #    (so that runs up to `window-1` days before `start` are counted)
    initial_date = start - timedelta(days=window - 1)

    result: list[tuple[date, float]] = []
    window_deque: deque[tuple[date, float]] = deque()
    window_sum = 0.0

    # 3. Walk each day from initial_date up through `end`
    total_days = (end - initial_date).days + 1
    for offset in range(total_days):
        today = initial_date + timedelta(days=offset)
        today_miles = miles_per_day.get(today, 0.0)

        # add today's miles into the window
        window_deque.append((today, today_miles))
        window_sum += today_miles

        # evict anything older than `window` days
        cutoff = today - timedelta(days=window - 1)
        while window_deque and window_deque[0][0] < cutoff:
            old_date, old_miles = window_deque.popleft()
            window_sum -= old_miles

        # only start recording once we're at or past the user’s `start` date
        if today >= start:
            # It's important to round because otherwise we can get floating point
            # errors that cause the sum to be off by miniscule amounts.
            result.append((today, round(window_sum, 4)))

    return result
