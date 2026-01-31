# This file loads env variables and must thus be imported before anything else.
from . import env_loader  # noqa: F401
from .env_loader import get_current_environment

import os
import logging
from datetime import date, datetime
from typing import Literal, TypeVar

from fastapi import FastAPI, Depends, Response
from fastapi.middleware.cors import CORSMiddleware

from fitness.models import Run
from fitness.models.run_detail import RunDetail
from fitness.app.routers.run_workouts import (
    ActivityFeedRunItem,
    ActivityFeedWorkoutItem,
)
from .constants import DEFAULT_START, DEFAULT_END
from .dependencies import all_runs
from .routers import (
    metrics_router,
    shoe_router,
    run_router,
    sync_router,
    oauth_router,
    strava_router,
    mmf_router,
    summary_router,
    hevy_router,
    lifts_router,
    exercise_templates_router,
    lift_sync_router,
    run_workouts_router,
    run_workout_sync_router,
)
from .models import EnvironmentResponse
from .auth import require_viewer
from fitness.models.user import User
from fitness.utils.timezone import convert_runs_to_user_timezone

# Type alias for values that can be used as sort keys
SortableValue = datetime | float | str

"""FastAPI application setup for the fitness API.

Exposes routes for reading runs, runs-with-shoes, metrics, shoe management,
run editing, and updating data from external sources. This module configures
CORS, logging behavior, and provides helper types for sorting.
"""


RunSortBy = Literal[
    "date", "distance", "duration", "pace", "heart_rate", "source", "type", "shoes"
]
SortOrder = Literal["asc", "desc"]

# Type variable for generic sorting function
# Supports Run and RunDetail (which shares the sorted fields)
T = TypeVar("T", Run, RunDetail)

PUBLIC_API_BASE_URL = os.environ["PUBLIC_API_BASE_URL"]

logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(metrics_router)
app.include_router(shoe_router)
app.include_router(run_router)
app.include_router(sync_router)
app.include_router(oauth_router)
app.include_router(strava_router)
app.include_router(mmf_router)
app.include_router(summary_router)
app.include_router(hevy_router)
app.include_router(lifts_router)
app.include_router(exercise_templates_router)
app.include_router(lift_sync_router)
app.include_router(run_workouts_router)
app.include_router(run_workout_sync_router)
app.add_middleware(
    CORSMiddleware,  # type: ignore[arg-type]
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
        "https://fitness.ethanswan.com",  # Production dashboard
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Configure basic logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(filename)s:%(lineno)d",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Configure the logging for the API itself if the user specifies it.
if "LOG_LEVEL" in os.environ:
    match os.environ["LOG_LEVEL"].upper():
        case "DEBUG":
            log_level = logging.DEBUG
        case "INFO":
            log_level = logging.INFO
        case "WARNING":
            log_level = logging.WARNING
        case "ERROR":
            log_level = logging.ERROR
        case "CRITICAL":
            log_level = logging.CRITICAL
        case _:
            raise ValueError(f"Invalid log level: {os.environ['LOG_LEVEL']}")
    logging.getLogger("fitness").setLevel(log_level)


@app.get("/runs", response_model=list[Run])
def read_all_runs(
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    user_timezone: str | None = None,
    sort_by: RunSortBy = "date",
    sort_order: SortOrder = "desc",
    runs: list[Run] = Depends(all_runs),
    _user: User = Depends(require_viewer),
) -> list[Run]:
    """Get all runs with optional sorting.

    Args:
        start: Inclusive start date for filtering (local to `user_timezone` if provided).
        end: Inclusive end date for filtering (local to `user_timezone` if provided).
        user_timezone: IANA timezone for local-date filtering and display. If None, use UTC dates.
        sort_by: Field to sort by (date, distance, duration, pace, heart_rate, source, type, shoes).
        sort_order: Sort order, ascending or descending.
        runs: Dependency injection of all runs from the database.
    """
    # Filter first to get the right date range
    if user_timezone is None:
        # Simple UTC filtering
        filtered_runs = [run for run in runs if start <= run.datetime_utc.date() <= end]
    else:
        # Convert to user timezone and filter by local dates
        localized_runs = convert_runs_to_user_timezone(runs, user_timezone)
        filtered_runs = [
            run for run in localized_runs if start <= run.local_date <= end
        ]

    # Apply sorting to filtered runs
    return sort_runs_generic(filtered_runs, sort_by, sort_order)


@app.get("/runs/details", response_model=list[RunDetail])
def read_run_details(
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    sort_by: RunSortBy = "date",
    sort_order: SortOrder = "desc",
    synced: bool | None = None,
    _user: User = Depends(require_viewer),
) -> list[RunDetail]:
    """Get detailed runs with shoes and sync info.

    Uses server-side date filtering and ordering by UTC datetime for efficiency.
    """
    from fitness.db.runs import get_run_details_in_date_range, get_all_run_details

    # Get run details from database
    if start != DEFAULT_START or end != DEFAULT_END:
        details = get_run_details_in_date_range(start, end, synced=synced)
    else:
        details = get_all_run_details(synced=synced)

    # Apply sorting
    # Reuse sort_runs_generic since RunDetail is compatible on the used fields
    return sort_runs_generic(details, sort_by, sort_order)


# Avoid potential ambiguity with dynamic route `/runs/{run_id}` in some setups
# by providing an alternate, unambiguous path for the same data.
@app.get("/runs-details", response_model=list[RunDetail])
def read_run_details_alt(
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    sort_by: RunSortBy = "date",
    sort_order: SortOrder = "desc",
    synced: bool | None = None,
    _user: User = Depends(require_viewer),
) -> list[RunDetail]:
    return read_run_details(
        start=start, end=end, sort_by=sort_by, sort_order=sort_order, synced=synced
    )


@app.get("/run-activity-feed")
def read_activity_feed(
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    sort_order: Literal["asc", "desc"] = "desc",
    _user: User = Depends(require_viewer),
) -> list[ActivityFeedRunItem | ActivityFeedWorkoutItem]:
    """Get a unified activity feed of solo runs and run workouts.

    Runs that belong to a workout appear nested inside their workout entry
    rather than as separate items. Sorted by date.
    """
    from fitness.db.runs import get_run_details_in_date_range, get_all_run_details
    from fitness.app.routers.run_workouts import build_activity_feed

    if start != DEFAULT_START or end != DEFAULT_END:
        all_runs = get_run_details_in_date_range(start, end)
    else:
        all_runs = get_all_run_details()

    return build_activity_feed(all_runs, sort_order=sort_order)


def sort_runs_generic(
    runs: list[T], sort_by: RunSortBy, sort_order: SortOrder
) -> list[T]:
    """Sort runs by the specified field and order.

    Works with both `Run` and `RunDetail` types.
    """
    reverse = sort_order == "desc"

    def get_sort_key(run: T) -> SortableValue:
        if sort_by == "date":
            # Use localized_datetime for LocalizedRun, otherwise datetime_utc
            return getattr(run, "localized_datetime", run.datetime_utc)
        elif sort_by == "distance":
            return run.distance
        elif sort_by == "duration":
            return run.duration
        elif sort_by == "pace":
            # Calculate pace (minutes per mile) - avoid division by zero
            if run.distance > 0:
                return (run.duration / 60) / run.distance
            return float("inf")  # Put zero-distance runs at the end
        elif sort_by == "heart_rate":
            return (
                run.avg_heart_rate or 0
            )  # Handle None values, put them first when asc
        elif sort_by == "source":
            return run.source
        elif sort_by == "type":
            return run.type
        elif sort_by == "shoes":
            # Handle RunDetail (shoes) and base Run (shoe_name)
            return str(
                getattr(run, "shoes", None) or getattr(run, "shoe_name", "") or ""
            )
        else:
            # Default to date if unknown sort field
            return getattr(run, "localized_datetime", run.datetime_utc)

    return sorted(runs, key=get_sort_key, reverse=reverse)


@app.get("/health")
@app.options("/health")
def health_check(response: Response) -> dict[str, str]:
    """Health check endpoint that returns 200 status with CORS from anywhere."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return {"status": "healthy"}


@app.get("/environment", response_model=EnvironmentResponse)
def get_environment(_user: User = Depends(require_viewer)) -> EnvironmentResponse:
    """Get the current environment configuration."""
    environment = get_current_environment()
    return EnvironmentResponse(environment=environment)


@app.get("/auth/verify")
def verify_auth(user: User = Depends(require_viewer)) -> dict[str, str]:
    """Verify authentication credentials.

    This endpoint does nothing except validate credentials. It's used by the
    dashboard to test login credentials without triggering any side effects.

    Returns:
        Success message if credentials are valid.

    Raises:
        HTTPException 401 if credentials are invalid.
    """
    return {"status": "authenticated", "username": user.username or ""}
