"""Timezone utility functions for converting between UTC and user timezones."""

from datetime import date

from fitness.models import Run, LocalizedRun


def convert_runs_to_user_timezone(
    runs: list[Run], user_timezone: str | None = None
) -> list[LocalizedRun]:
    """
    Convert a list of runs to use the user's local timezone.

    Uses the run's datetime_utc field for accurate timezone conversion.
    If user_timezone is None, returns LocalizedRun objects with UTC datetime as localized_datetime.
    """
    if user_timezone is None:
        # No conversion needed - use UTC datetime as localized_datetime
        localized_runs = []
        for run in runs:
            localized_run = LocalizedRun(
                id=run.id,
                datetime_utc=run.datetime_utc,
                localized_datetime=run.datetime_utc,
                type=run.type,
                distance=run.distance,
                duration=run.duration,
                source=run.source,
                avg_heart_rate=run.avg_heart_rate,
                shoe_id=run.shoe_id,
                deleted_at=run.deleted_at,
            )
            localized_run._shoe_name = run._shoe_name
            localized_runs.append(localized_run)
        return localized_runs

    return [LocalizedRun.from_run(run, user_timezone) for run in runs]


def filter_runs_by_local_date_range(
    runs: list[Run], start: date, end: date, user_timezone: str | None = None
) -> list[Run]:
    """
    Filter runs to only include those that fall within the date range in the user's timezone.

    If user_timezone is None, uses UTC dates (existing behavior).
    """
    if user_timezone is None:
        # Existing behavior - filter by UTC dates
        return [run for run in runs if start <= run.datetime_utc.date() <= end]

    # Convert runs to user timezone and filter by local dates
    localized_runs = convert_runs_to_user_timezone(runs, user_timezone)
    return [
        localized_run
        for localized_run in localized_runs
        if start <= localized_run.local_date <= end
    ]
