from datetime import date, timedelta
import math
from collections import defaultdict
from collections.abc import Sequence
from typing import NamedTuple

from fitness.models import Run, Ride, DayTrainingLoad, TrainingLoad, Sex
from fitness.utils.timezone import convert_activities_to_user_timezone


class DayHrtss(NamedTuple):
    date: date
    hrtss: float


ATL_LOOKBACK = 7
CTL_LOOKBACK = 42

# Days of activity history to feed the model *before* the requested start date,
# so CTL/ATL have converged by the time the displayed range begins. CTL's
# 42-day time constant means the influence of older data decays as
# e^(-days/42); at 730 days the residual error is ~1e-4 hrTSS, i.e. results are
# indistinguishable from using all-time history, while the query cost stays
# bounded as total history grows.
CONVERGENCE_WARMUP_DAYS = 730


def trimp(activity: Run | Ride, max_hr: float, resting_hr: float, sex: Sex) -> float:
    """
    Calculate the Banister TRaining IMPulse score for a HR-bearing activity.

    TRIMP = Duration (minutes) x HR_Relative x Y
    where HR_Relative is the relative heart rate:
        - HR_Relative = (avg_hr_during_for_activity - resting_hr) / (max_hr - resting_hr)
    where Y is a sex-based weighting factor:
        - For men: Y = 0.64 * e^(1.92 x HR_Relative)
        - For women: Y = 0.86 * e^(1.67 x HR_Relative)
    """
    if activity.avg_heart_rate is None:
        raise ValueError(
            "Activity must have an average heart rate to calculate TRIMP."
        )
    hr_relative = (activity.avg_heart_rate - resting_hr) / (max_hr - resting_hr)
    # Clamp hr_relative to the range [0, 1]
    hr_relative = max(0.0, min(1.0, hr_relative))
    match sex:
        case "M":
            y = 0.64 * math.exp(1.92 * hr_relative)
        case "F":
            y = 0.86 * math.exp(1.67 * hr_relative)
    duration_minutes = activity.duration / 60
    return duration_minutes * hr_relative * y


def threshold_trimp(max_hr: float, resting_hr: float, lthr: float, sex: Sex) -> float:
    """Calculate the TRIMP for a hypothetical 60-minute run at lactate threshold heart rate.

    This serves as the normalization reference for hrTSS: 1 hour at LTHR = 100 hrTSS.
    """
    hr_relative = (lthr - resting_hr) / (max_hr - resting_hr)
    hr_relative = max(0.0, min(1.0, hr_relative))
    match sex:
        case "M":
            y = 0.64 * math.exp(1.92 * hr_relative)
        case "F":
            y = 0.86 * math.exp(1.67 * hr_relative)
    return 60.0 * hr_relative * y


def hrtss(
    activity: Run | Ride, max_hr: float, resting_hr: float, lthr: float, sex: Sex
) -> float:
    """Calculate Heart Rate Training Stress Score for an activity.

    hrTSS = (activity_TRIMP / threshold_TRIMP) * 100

    A 60-minute activity at LTHR produces hrTSS ≈ 100.
    """
    activity_trimp = trimp(activity, max_hr, resting_hr, sex)
    thr_trimp = threshold_trimp(max_hr, resting_hr, lthr, sex)
    if thr_trimp == 0:
        return 0.0
    return (activity_trimp / thr_trimp) * 100.0


def _exponential_training_load(trimp_values: list[float], tau: int) -> list[float]:
    alpha = 1 - math.exp(-1 / tau)
    load = []
    prev = 0.0
    for trimp in trimp_values:
        current = prev + alpha * (trimp - prev)
        load.append(current)
        prev = current
    return load


def _calculate_atl_and_ctl(
    trimp_values: list[float],
) -> tuple[list[float], list[float]]:
    """
    Calculate Acute Training Load (ATL) and Chronic Training Load (CTL).

    The ATL is calculated over a 7-day lookback period, and the CTL is calculated over a 42-day lookback period.
    """
    atl_values = _exponential_training_load(trimp_values, ATL_LOOKBACK)
    ctl_values = _exponential_training_load(trimp_values, CTL_LOOKBACK)
    return atl_values, ctl_values


def training_stress_balance(
    activities: Sequence[Run | Ride],
    max_hr: float,
    resting_hr: float,
    lthr: float,
    sex: Sex,
    start_date: date,
    end_date: date,
    user_timezone: str | None = None,
) -> list[DayTrainingLoad]:
    """
    Calculate Training Stress Balance (TSB) as the difference between CTL and ATL.

    ATL, CTL, and TSB are computed from daily hrTSS values (TRIMP normalized so
    that 1 hour at LTHR = 100).

    Args:
        activities: List of HR-bearing activities (runs and/or rides) with UTC dates.
            Activities without an `avg_heart_rate` are skipped.
        max_hr: Maximum heart rate
        resting_hr: Resting heart rate
        lthr: Lactate threshold heart rate
        sex: Sex ("M" or "F")
        start_date: Start date in user's timezone
        end_date: End date in user's timezone
        user_timezone: User's timezone (e.g., "America/Chicago"). If None, uses UTC dates.
    """
    hr_activities = [a for a in activities if a.avg_heart_rate is not None]
    user_tz_activities = convert_activities_to_user_timezone(
        hr_activities, user_timezone
    )

    hrtss_by_date: list[tuple[date, float]] = []

    if not user_tz_activities:
        current_date = start_date
        while current_date <= end_date:
            hrtss_by_date.append((current_date, 0.0))
            current_date += timedelta(days=1)
        atl = [0.0] * len(hrtss_by_date)
        ctl = [0.0] * len(hrtss_by_date)
        tsb = [0.0] * len(hrtss_by_date)
        dates = [dt for dt, _ in hrtss_by_date]
        hrtss_values = [h for _, h in hrtss_by_date]
        return [
            DayTrainingLoad(date=d, training_load=TrainingLoad(ctl=c, atl=a, tsb=t, hrtss=h))
            for (d, c, a, t, h) in zip(dates, ctl, atl, tsb, hrtss_values)
        ]

    # Always start calculations from the earliest activity, because these metrics converge over time.
    # If we start at the start date, metrics will be inaccurately close to zero.
    first_activity_date = min(a.local_date for a in user_tz_activities)

    # Sum each activity's hrTSS into its local-date bucket in a single pass, so
    # building the daily series below is O(days) rather than O(days x activities).
    # (Mirrors the bucketing already used by hrtss_by_day.) Activities after
    # end_date never enter the series, so don't bother scoring them.
    hrtss_by_local_date: dict[date, float] = defaultdict(float)
    for a in user_tz_activities:
        if a.local_date <= end_date:
            hrtss_by_local_date[a.local_date] += hrtss(
                a, max_hr, resting_hr, lthr, sex
            )

    for i in range((end_date - first_activity_date).days + 1):
        current_date = first_activity_date + timedelta(days=i)
        hrtss_by_date.append(
            (current_date, hrtss_by_local_date.get(current_date, 0.0))
        )
    atl, ctl = _calculate_atl_and_ctl([h for _, h in hrtss_by_date])
    tsb = [ctl_value - atl_value for ctl_value, atl_value in zip(ctl, atl)]
    dates = [dt for dt, _ in hrtss_by_date]
    hrtss_values = [h for _, h in hrtss_by_date]
    return [
        DayTrainingLoad(date=d, training_load=TrainingLoad(ctl=c, atl=a, tsb=t, hrtss=h))
        for (d, c, a, t, h) in zip(dates, ctl, atl, tsb, hrtss_values)
        if start_date <= d <= end_date
    ]


def hrtss_by_day(
    activities: Sequence[Run | Ride],
    start: date,
    end: date,
    max_hr: float,
    resting_hr: float,
    lthr: float,
    sex: Sex,
    user_timezone: str | None = None,
) -> list[DayHrtss]:
    """
    Calculate hrTSS values for each day in the date range.

    Args:
        activities: List of activities (runs and/or rides) with UTC dates.
            Activities without `avg_heart_rate` are skipped.
        start: Start date in user's timezone
        end: End date in user's timezone
        max_hr: Maximum heart rate
        resting_hr: Resting heart rate
        lthr: Lactate threshold heart rate
        sex: Sex ("M" or "F")
        user_timezone: User's timezone (e.g., "America/Chicago"). If None, uses UTC dates.
    """
    activities_with_hr = [a for a in activities if a.avg_heart_rate is not None]
    user_tz_activities = convert_activities_to_user_timezone(
        activities_with_hr, user_timezone
    )

    activities_by_date = defaultdict(list)
    for a in user_tz_activities:
        if start <= a.local_date <= end:
            activities_by_date[a.local_date].append(a)

    day_hrtss_list = []
    current_date = start
    while current_date <= end:
        day_activities = activities_by_date[current_date]
        daily_hrtss = 0.0
        for a in day_activities:
            daily_hrtss += hrtss(a, max_hr, resting_hr, lthr, sex)
        day_hrtss_list.append(DayHrtss(date=current_date, hrtss=daily_hrtss))
        current_date += timedelta(days=1)

    return day_hrtss_list
