"""MCP server for querying fitness data via LLM tool calls.

Provides read-only tools for runs, lifts, shoes, and training metrics.
Mounted as a sub-application on the existing FastAPI app at /mcp.
"""

import json
from datetime import date

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("fitness-api", stateless_http=True)


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


@mcp.tool()
def get_runs(
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
) -> str:
    """Get running activities with optional date filtering.

    Args:
        start_date: Start date in YYYY-MM-DD format (default: all time).
        end_date: End date in YYYY-MM-DD format (default: today).
        limit: Maximum number of runs to return (default: 100).

    Returns runs sorted by date descending, including distance (miles),
    duration (seconds), type (Outdoor/Treadmill), source, and heart rate.
    """
    from fitness.db.runs import get_runs_for_date_range
    from fitness.app.constants import DEFAULT_START, DEFAULT_END

    start = _parse_date(start_date) or DEFAULT_START
    end = _parse_date(end_date) or DEFAULT_END
    runs = get_runs_for_date_range(start, end)
    runs.sort(key=lambda r: r.datetime_utc, reverse=True)
    runs = runs[:limit]
    return json.dumps([r.model_dump(mode="json") for r in runs])


@mcp.tool()
def get_run_details(
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
) -> str:
    """Get enriched run data including shoe names and calendar sync status.

    Args:
        start_date: Start date in YYYY-MM-DD format (default: all time).
        end_date: End date in YYYY-MM-DD format (default: today).
        limit: Maximum number of runs to return (default: 100).

    Returns runs with shoe name, sync status, and Google Calendar event info.
    """
    from fitness.db.runs import get_run_details_in_date_range, get_all_run_details
    from fitness.app.constants import DEFAULT_START, DEFAULT_END

    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start or end:
        details = get_run_details_in_date_range(
            start or DEFAULT_START, end or DEFAULT_END
        )
    else:
        details = get_all_run_details()
    details.sort(key=lambda r: r.datetime_utc, reverse=True)
    details = details[:limit]
    return json.dumps([r.model_dump(mode="json") for r in details])


@mcp.tool()
def get_mileage_total(
    start_date: str,
    end_date: str,
) -> str:
    """Get total miles run in a date range.

    Args:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.

    Returns the total mileage as a number.
    """
    from fitness.db.runs import get_runs_for_date_range
    from fitness.agg.mileage import total_mileage

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    runs = get_runs_for_date_range(start, end)
    total = total_mileage(runs, start, end)
    return json.dumps(
        {"total_miles": round(total, 2), "start": start_date, "end": end_date}
    )


@mcp.tool()
def get_mileage_by_day(
    start_date: str,
    end_date: str,
) -> str:
    """Get daily mileage breakdown for a date range.

    Args:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.

    Returns a list of {date, mileage} objects for each day with running activity.
    """
    from fitness.db.runs import get_runs_for_date_range
    from fitness.agg.mileage import miles_by_day

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    runs = get_runs_for_date_range(start, end)
    daily = miles_by_day(runs, start, end)
    return json.dumps([{"date": str(d), "mileage": round(m, 2)} for d, m in daily])


@mcp.tool()
def get_training_load(
    start_date: str,
    end_date: str,
    max_hr: float,
    resting_hr: float,
    sex: str,
) -> str:
    """Get training load metrics (CTL, ATL, TSB) for a date range.

    CTL = Chronic Training Load (42-day fitness), ATL = Acute Training Load
    (7-day fatigue), TSB = Training Stress Balance (form: positive = fresh,
    negative = fatigued).

    Args:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        max_hr: Maximum heart rate (e.g. 190).
        resting_hr: Resting heart rate (e.g. 55).
        sex: "M" or "F" (affects TRIMP calculation weighting).

    Returns daily training load values.
    """
    from fitness.db.runs import get_all_runs
    from fitness.agg.training_load import training_stress_balance

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    runs = get_all_runs()
    tsb = training_stress_balance(runs, max_hr, resting_hr, sex, start, end)  # type: ignore[arg-type]
    return json.dumps(
        [
            {
                "date": str(day.date),
                "ctl": round(day.training_load.ctl, 2),
                "atl": round(day.training_load.atl, 2),
                "tsb": round(day.training_load.tsb, 2),
            }
            for day in tsb
        ]
    )


@mcp.tool()
def get_lifts(
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
) -> str:
    """Get lifting/weightlifting sessions with optional date filtering.

    Args:
        start_date: Start date in YYYY-MM-DD format (default: all time).
        end_date: End date in YYYY-MM-DD format (default: all time).
        limit: Maximum number of sessions to return (default: 50).

    Returns lifting sessions with exercises, sets, weights, reps, and RPE.
    Each session includes full exercise details with set-by-set data.
    """
    from fitness.db.lifts import get_all_lifts, get_lifts_in_date_range

    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start or end:
        lifts = get_lifts_in_date_range(start, end)
    else:
        lifts = get_all_lifts()
    lifts.sort(key=lambda lift: lift.start_time, reverse=True)
    lifts = lifts[:limit]
    return json.dumps([lift.model_dump(mode="json") for lift in lifts])


@mcp.tool()
def get_lift_stats(
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Get aggregated lifting statistics.

    Args:
        start_date: Period start in YYYY-MM-DD format (default: all time).
        end_date: Period end in YYYY-MM-DD format (default: all time).

    Returns all-time totals (sessions, volume, sets, duration) plus
    period-specific stats (avg duration, avg RPE).
    """
    from fitness.db.lifts import get_all_lifts, get_lifts_in_date_range
    from fitness.agg.lifts import compute_lift_stats

    all_lifts = get_all_lifts()
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start or end:
        period_lifts = get_lifts_in_date_range(start, end)
    else:
        period_lifts = all_lifts
    return json.dumps(compute_lift_stats(all_lifts, period_lifts))


@mcp.tool()
def get_volume_by_muscle(
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Get lifting volume (weight x reps) grouped by muscle group.

    Args:
        start_date: Start date in YYYY-MM-DD format (default: all time).
        end_date: End date in YYYY-MM-DD format (default: all time).

    Returns volume in kg for each muscle group, sorted by volume descending.
    Useful for identifying training balance across muscle groups.
    """
    from fitness.db.lifts import (
        get_all_lifts,
        get_lifts_in_date_range,
        get_all_exercise_templates,
    )
    from fitness.agg.lifts import compute_volume_by_muscle

    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start or end:
        lifts = get_lifts_in_date_range(start, end)
    else:
        lifts = get_all_lifts()
    templates = get_all_exercise_templates()
    return json.dumps(compute_volume_by_muscle(lifts, templates))


@mcp.tool()
def get_shoes(
    retired: bool | None = None,
) -> str:
    """Get running shoes.

    Args:
        retired: Filter by retirement status. None = all shoes,
                 True = retired only, False = active only.

    Returns shoe name, retirement status, and notes.
    """
    from fitness.db.shoes import get_shoes as db_get_shoes

    shoes = db_get_shoes(retired=retired)
    return json.dumps([s.model_dump(mode="json") for s in shoes])


@mcp.tool()
def get_shoe_mileage(
    include_retired: bool = False,
) -> str:
    """Get total mileage for each pair of running shoes.

    Args:
        include_retired: Whether to include retired shoes (default: False).

    Returns shoe name and total miles run in each pair.
    """
    from fitness.db.runs import get_all_runs
    from fitness.db.shoes import get_shoes as db_get_shoes
    from fitness.agg.shoes import mileage_by_shoes

    runs = get_all_runs()
    shoes = db_get_shoes()
    results = mileage_by_shoes(runs, shoes, include_retired=include_retired)
    return json.dumps(
        [{"shoe": r.shoe.name, "mileage": round(r.mileage, 2)} for r in results]
    )
