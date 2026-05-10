"""Timezone utility functions for converting between UTC and user timezones."""

from datetime import date

from fitness.models import Run, LocalizedRun, Ride, LocalizedRide


def convert_runs_to_user_timezone(
    runs: list[Run], user_timezone: str | None = None
) -> list[LocalizedRun]:
    """
    Convert a list of runs to use the user's local timezone.

    Uses the run's datetime_utc field for accurate timezone conversion.
    If user_timezone is None, returns LocalizedRun objects with UTC datetime as localized_datetime.
    """
    if user_timezone is None:
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


def convert_rides_to_user_timezone(
    rides: list[Ride], user_timezone: str | None = None
) -> list[LocalizedRide]:
    """
    Convert a list of rides to use the user's local timezone.

    Mirrors convert_runs_to_user_timezone for the Ride model.
    If user_timezone is None, returns LocalizedRide objects with UTC datetime as localized_datetime.
    """
    if user_timezone is None:
        return [
            LocalizedRide(
                id=ride.id,
                datetime_utc=ride.datetime_utc,
                localized_datetime=ride.datetime_utc,
                type=ride.type,
                distance=ride.distance,
                duration=ride.duration,
                source=ride.source,
                avg_heart_rate=ride.avg_heart_rate,
                deleted_at=ride.deleted_at,
            )
            for ride in rides
        ]
    return [LocalizedRide.from_ride(ride, user_timezone) for ride in rides]


def convert_activities_to_user_timezone(
    activities: list[Run | Ride], user_timezone: str | None = None
) -> list[LocalizedRun | LocalizedRide]:
    """
    Convert a mixed list of runs and rides to the user's local timezone.

    Dispatches to the run- or ride-specific converter per element so each
    activity is returned with its concrete `Localized*` type intact.
    """
    runs = [a for a in activities if isinstance(a, Run)]
    rides = [a for a in activities if isinstance(a, Ride)]
    return [
        *convert_runs_to_user_timezone(runs, user_timezone),
        *convert_rides_to_user_timezone(rides, user_timezone),
    ]


def filter_runs_by_local_date_range(
    runs: list[Run], start: date, end: date, user_timezone: str | None = None
) -> list[Run]:
    """
    Filter runs to only include those that fall within the date range in the user's timezone.

    If user_timezone is None, uses UTC dates (existing behavior).
    """
    if user_timezone is None:
        return [run for run in runs if start <= run.datetime_utc.date() <= end]

    localized_runs = convert_runs_to_user_timezone(runs, user_timezone)
    return [
        localized_run
        for localized_run in localized_runs
        if start <= localized_run.local_date <= end
    ]
