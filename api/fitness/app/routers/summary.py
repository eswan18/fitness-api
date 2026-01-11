import logging
from datetime import date, datetime, timedelta, timezone
import zoneinfo

from fastapi import APIRouter, Depends

from fitness.app.models import TrmnlSummary, Sex
from fitness.app.dependencies import all_runs
from fitness.app.auth import require_viewer
from fitness.agg import total_mileage, total_seconds
from fitness.agg.training_load import training_stress_balance
from fitness.models import Run, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("/trmnl", response_model=TrmnlSummary)
def get_trmnl_summary(
    user_timezone: str | None = None,
    max_hr: float = 192,
    resting_hr: float = 42,
    sex: Sex = "M",
    runs: list[Run] = Depends(all_runs),
    _user: User = Depends(require_viewer),
) -> TrmnlSummary:
    """Get the summary of the fitness data."""
    miles_all_time = total_mileage(runs, date.min, date.max)
    minutes_all_time = total_seconds(runs, date.min, date.max) / 60

    # Get today's date in the user's timezone (or UTC if no timezone provided)
    if user_timezone is None:
        today = datetime.now(timezone.utc).date()
    else:
        tz = zoneinfo.ZoneInfo(user_timezone)
        today = datetime.now(timezone.utc).astimezone(tz).date()
    current_month_name = today.strftime("%B")
    days_this_month = today.day
    current_year = today.year
    days_this_year = today.timetuple().tm_yday

    # Calendar month and year totals
    month_start = today.replace(day=1)
    year_start = today.replace(day=1, month=1)
    miles_this_calendar_month = total_mileage(
        runs, month_start, date.max, user_timezone
    )
    miles_this_calendar_year = total_mileage(runs, year_start, date.max, user_timezone)
    # Last 30 and 365 days totals
    last_30_days_start = today - timedelta(days=30)
    last_365_days_start = today - timedelta(days=365)
    miles_last_30_days = total_mileage(
        runs, last_30_days_start, date.max, user_timezone
    )
    miles_last_365_days = total_mileage(
        runs, last_365_days_start, date.max, user_timezone
    )

    # Calculate training load series for the last 60 days
    training_load_data = training_stress_balance(
        runs=runs,
        max_hr=max_hr,
        resting_hr=resting_hr,
        sex=sex,
        start_date=today - timedelta(days=60),
        end_date=today,
        user_timezone=user_timezone,
    )

    reversed_data = list(reversed(training_load_data))
    load_data = [
        {
            "name": "tsb",
            "data": [
                [day_data.date.isoformat(), day_data.training_load.tsb]
                for day_data in reversed_data
            ],
        },
        {
            "name": "atl",
            "data": [
                [day_data.date.isoformat(), day_data.training_load.atl]
                for day_data in reversed_data
            ],
        },
        {
            "name": "ctl",
            "data": [
                [day_data.date.isoformat(), day_data.training_load.ctl]
                for day_data in reversed_data
            ],
        },
    ]

    return TrmnlSummary(
        miles_all_time=miles_all_time,
        minutes_all_time=minutes_all_time,
        miles_this_calendar_month=miles_this_calendar_month,
        days_this_calendar_month=days_this_month,
        calendar_month_name=current_month_name,
        days_this_calendar_year=days_this_year,
        miles_this_calendar_year=miles_this_calendar_year,
        calendar_year=current_year,
        miles_last_30_days=miles_last_30_days,
        miles_last_365_days=miles_last_365_days,
        load_data=load_data,
    )
