from datetime import date, timedelta

from fastapi import APIRouter, Depends

from fitness.agg import (
    mileage_by_shoes,
    miles_by_day,
    total_mileage,
    rolling_sum,
    total_seconds,
    training_stress_balance,
)
from fitness.db.runs import get_runs_for_date_range, get_all_runs
from fitness.db.shoes import get_shoes
from fitness.agg.training_load import trimp_by_day
from fitness.app.constants import DEFAULT_START, DEFAULT_END
from fitness.app.auth import require_viewer
from fitness.models import Sex, DayTrainingLoad, ShoeMileage, User
from fitness.app.models import (
    DayMileage,
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
    sex: Sex,
    user_timezone: str | None = None,
    _user: User = Depends(require_viewer),
) -> list[DayTrainingLoad]:
    """Get training load by day.

    Computes CTL/ATL/TSB over the specified range using heart-rate-enabled runs.
    Needs full history for ATL/CTL convergence.
    """
    runs = get_all_runs()
    return training_stress_balance(
        runs=runs,
        max_hr=max_hr,
        resting_hr=resting_hr,
        sex=sex,
        start_date=start,
        end_date=end,
        user_timezone=user_timezone,
    )


@router.get("/trimp/by-day", response_model=list[dict])
def read_trimp_by_day(
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    max_hr: float = 192,
    resting_hr: float = 42,
    sex: Sex = "M",
    user_timezone: str | None = None,
    _user: User = Depends(require_viewer),
) -> list[dict]:
    """Get TRIMP values by day.

    Returns a list of dicts with keys {"date", "trimp"} for each day.
    """
    runs = get_runs_for_date_range(start, end, user_timezone)
    day_trimps = trimp_by_day(runs, start, end, max_hr, resting_hr, sex, user_timezone)
    return [{"date": dt.date, "trimp": dt.trimp} for dt in day_trimps]
