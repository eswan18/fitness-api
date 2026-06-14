from datetime import date, timedelta

from fastapi import APIRouter, Depends

from fitness.agg import (
    mileage_by_shoes,
    miles_by_day,
    miles_by_week,
    total_mileage,
    rolling_sum,
    total_seconds,
    training_stress_balance,
    week_anchor,
)
from fitness.agg.mileage import WeekStart
from fitness.db.runs import get_runs_for_date_range, get_all_runs
from fitness.db.rides import get_rides_for_date_range
from fitness.db.shoes import get_shoes
from fitness.agg.training_load import hrtss_by_day, CONVERGENCE_WARMUP_DAYS
from fitness.app.constants import DEFAULT_START, DEFAULT_END
from fitness.app.auth import require_viewer
from fitness.models import Sex, DayTrainingLoad, ShoeMileage, User
from fitness.app.models import (
    DayMileage,
    WeekMileage,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/seconds/total", response_model=float)
def read_total_seconds(
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    user_timezone: str | None = None,
    _user: User = Depends(require_viewer),
) -> float:
    """Get total seconds.

    Args:
        start: Inclusive start date for filtering (local to `user_timezone` if provided).
        end: Inclusive end date for filtering (local to `user_timezone` if provided).
        user_timezone: IANA timezone for local-date filtering and display. If None, use UTC dates.
    """
    runs = get_runs_for_date_range(start, end, user_timezone)
    return total_seconds(runs, start, end, user_timezone)


@router.get("/mileage/total", response_model=float)
def read_total_mileage(
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    user_timezone: str | None = None,
    _user: User = Depends(require_viewer),
) -> float:
    """Get total mileage.

    Args:
        start: Inclusive start date for filtering (local to `user_timezone` if provided).
        end: Inclusive end date for filtering (local to `user_timezone` if provided).
        user_timezone: IANA timezone for local-date filtering and display. If None, use UTC dates.
    """
    runs = get_runs_for_date_range(start, end, user_timezone)
    return total_mileage(runs, start, end, user_timezone)


@router.get("/mileage/by-day", response_model=list[DayMileage])
def read_mileage_by_day(
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    user_timezone: str | None = None,
    _user: User = Depends(require_viewer),
) -> list[DayMileage]:
    """Get mileage by day.

    Returns a list of DayMileage entries for each day in [start, end].
    """
    runs = get_runs_for_date_range(start, end, user_timezone)
    tuples: list[tuple[date, float]] = miles_by_day(runs, start, end, user_timezone)
    results = [DayMileage(date=day, mileage=miles) for (day, miles) in tuples]
    return results


@router.get("/mileage/by-week", response_model=list[WeekMileage])
def read_mileage_by_week(
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    week_start: WeekStart = "monday",
    user_timezone: str | None = None,
    _user: User = Depends(require_viewer),
) -> list[WeekMileage]:
    """Get mileage by week.

    Returns one WeekMileage entry (zero-filled) for every week that overlaps
    [start, end]. Edge weeks are full weekly totals: runs in the same week as
    `start`/`end` are counted even if they fall outside [start, end].

    Args:
        start: Inclusive start date for filtering (local to `user_timezone` if provided).
        end: Inclusive end date for filtering (local to `user_timezone` if provided).
        week_start: Which day weeks begin on ("monday" or "sunday").
        user_timezone: IANA timezone for local-date bucketing. If None, use UTC dates.
    """
    # Expand the fetch range to full week boundaries so the first and last
    # weeks have complete totals. Guard against overflow past date.max.
    aligned_start = week_anchor(start, week_start)
    last_week = week_anchor(end, week_start)
    if last_week <= date.max - timedelta(days=6):
        aligned_end = last_week + timedelta(days=6)
    else:
        aligned_end = date.max
    runs = get_runs_for_date_range(aligned_start, aligned_end, user_timezone)
    tuples: list[tuple[date, float]] = miles_by_week(
        runs, start, end, week_start, user_timezone
    )
    return [WeekMileage(week_start=week, mileage=miles) for (week, miles) in tuples]


@router.get("/mileage/rolling-by-day", response_model=list[DayMileage])
def read_rolling_mileage_by_day(
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    window: int = 1,
    user_timezone: str | None = None,
    _user: User = Depends(require_viewer),
) -> list[DayMileage]:
    """Get rolling sum of mileage over a window by day.

    Args:
        window: Number of days in the rolling window (>= 1).
    """
    # Expand start by (window-1) days for the rolling lookback
    lookback_start = start - timedelta(days=window - 1)
    runs = get_runs_for_date_range(lookback_start, end, user_timezone)
    tuples: list[tuple[date, float]] = rolling_sum(
        runs, start, end, window, user_timezone
    )
    results = [DayMileage(date=day, mileage=miles) for (day, miles) in tuples]
    return results


@router.get("/mileage/by-shoe", response_model=list[ShoeMileage])
def read_miles_by_shoe(
    include_retired: bool = False,
    _user: User = Depends(require_viewer),
) -> list[ShoeMileage]:
    """
    Get mileage by shoe with complete shoe information.

    Args:
        include_retired: Whether to include retired shoes in results (default: False)

    Returns:
        List of ShoeMileage objects containing full shoe data including retirement info
    """
    runs = get_all_runs()
    shoes = get_shoes()
    return mileage_by_shoes(runs, shoes=shoes, include_retired=include_retired)


@router.get("/training-load/by-day", response_model=list[DayTrainingLoad])
def read_training_load_by_day(
    start: date,
    end: date,
    max_hr: float,
    resting_hr: float,
    lthr: float,
    sex: Sex,
    user_timezone: str | None = None,
    _user: User = Depends(require_viewer),
) -> list[DayTrainingLoad]:
    """Get training load by day.

    Computes CTL/ATL/TSB over the requested range using hrTSS from HR-bearing
    runs and rides combined. Fetches CONVERGENCE_WARMUP_DAYS of extra history
    before `start` so ATL/CTL have converged by the start of the displayed
    range, without scanning all-time history (cost stays bounded as history grows).
    """
    # Cap the warm-up lead-in fetched before `start`. The displayed range itself
    # is always fully covered; only the convergence warm-up is bounded. Guard
    # against date underflow for very early start dates.
    if start > date.min + timedelta(days=CONVERGENCE_WARMUP_DAYS):
        fetch_start = start - timedelta(days=CONVERGENCE_WARMUP_DAYS)
    else:
        fetch_start = date.min
    activities = [
        *get_runs_for_date_range(fetch_start, end, user_timezone),
        *get_rides_for_date_range(fetch_start, end, user_timezone),
    ]
    return training_stress_balance(
        activities=activities,
        max_hr=max_hr,
        resting_hr=resting_hr,
        lthr=lthr,
        sex=sex,
        start_date=start,
        end_date=end,
        user_timezone=user_timezone,
    )


@router.get("/hrtss/by-day", response_model=list[dict])
def read_hrtss_by_day(
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    max_hr: float = 192,
    resting_hr: float = 42,
    lthr: float = 165,
    sex: Sex = "M",
    user_timezone: str | None = None,
    _user: User = Depends(require_viewer),
) -> list[dict]:
    """Get hrTSS values by day.

    Returns a list of dicts with keys {"date", "hrtss"} for each day. Combines
    hrTSS contributions from both runs and rides on each day.
    """
    activities = [
        *get_runs_for_date_range(start, end, user_timezone),
        *get_rides_for_date_range(start, end, user_timezone),
    ]
    day_hrtss = hrtss_by_day(
        activities, start, end, max_hr, resting_hr, lthr, sex, user_timezone
    )
    return [{"date": dt.date, "hrtss": dt.hrtss} for dt in day_hrtss]
