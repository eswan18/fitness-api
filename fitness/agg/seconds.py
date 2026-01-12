from datetime import date
from fitness.models import Run
from fitness.utils.timezone import filter_runs_by_local_date_range


def total_seconds(
    runs: list[Run], start: date, end: date, user_timezone: str | None = None
) -> float:
    """
    Calculate the total seconds for a list of runs.

    Args:
        runs: List of runs (with UTC dates)
        start: Start date in user's timezone
        end: End date in user's timezone
        user_timezone: User's timezone (e.g., "America/Chicago"). If None, uses UTC dates.
    """
    filtered_runs = filter_runs_by_local_date_range(runs, start, end, user_timezone)
    return sum(run.duration for run in filtered_runs)
