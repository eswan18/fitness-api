import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

from fitness.app.dependencies import strava_client
from fitness.app.auth import require_editor
from fitness.models.user import User
from fitness.models.responses import DataImportResponse
from fitness.integrations.strava.client import StravaClient
from fitness.models import Run, Ride
from fitness.db.runs import get_existing_run_ids, bulk_create_runs
from fitness.db.rides import get_existing_ride_ids, bulk_create_rides
from fitness.db.sync_metadata import get_last_sync_time, update_last_sync_time
from fitness.load.strava import load_strava_runs, load_strava_rides

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strava", tags=["strava"])

PROVIDER_NAME = "strava"


@router.post("/sync", response_model=DataImportResponse)
async def sync_strava_data(
    full_sync: bool = Query(
        False,
        description="Force a full sync instead of incremental. "
        "Use this to re-fetch all data from the beginning, including runs "
        "previously skipped for missing gear after you've assigned shoes "
        "in Strava.",
    ),
    user: User = Depends(require_editor),
    strava_client: StravaClient = Depends(strava_client),
) -> DataImportResponse:
    """Sync Strava data, fetching only new activities since last sync.

    By default, performs an incremental sync fetching only activities created
    after the last successful sync. Use `full_sync=true` to fetch all data.

    Runs without shoes assigned in Strava are reported in `skipped_runs` rather
    than imported. After assigning shoes in Strava, re-sync with
    `?full_sync=true`; incremental sync filters by activity start time and
    will not re-fetch the older run.

    Requires authentication with editor role.
    """
    # Determine sync start time for incremental sync
    after = None
    if not full_sync:
        after = get_last_sync_time(PROVIDER_NAME)
        if after:
            logger.info(f"Performing incremental Strava sync from {after.isoformat()}")
        else:
            logger.info("No previous sync found, performing full Strava sync")
    else:
        logger.info("Full Strava sync requested")

    # Record sync start time before fetching
    sync_time = datetime.now(timezone.utc)

    # Runs ingestion
    runs_load = load_strava_runs(strava_client, after=after)
    strava_runs = [Run.from_strava(run) for run in runs_load.runs]
    existing_run_ids = get_existing_run_ids()
    new_runs = [run for run in strava_runs if run.id not in existing_run_ids]
    if new_runs:
        inserted_runs = bulk_create_runs(new_runs)
        logger.info(f"Inserted {inserted_runs} new runs into the database")
    else:
        inserted_runs = 0
        logger.info("No new runs to insert")

    # Rides ingestion
    strava_rides = [
        Ride.from_strava(ride) for ride in load_strava_rides(strava_client, after=after)
    ]
    existing_ride_ids = get_existing_ride_ids()
    new_rides = [ride for ride in strava_rides if ride.id not in existing_ride_ids]
    if new_rides:
        inserted_rides = bulk_create_rides(new_rides)
        logger.info(f"Inserted {inserted_rides} new rides into the database")
    else:
        inserted_rides = 0
        logger.info("No new rides to insert")

    inserted_count = inserted_runs + inserted_rides

    # Update last sync time on successful completion
    update_last_sync_time(PROVIDER_NAME, sync_time)

    sync_type = "full" if full_sync or after is None else "incremental"
    skipped_msg = (
        f"; {len(runs_load.skipped)} runs skipped (missing shoes)"
        if runs_load.skipped
        else ""
    )
    return DataImportResponse(
        inserted_count=inserted_count,
        inserted_runs=inserted_runs,
        inserted_rides=inserted_rides,
        updated_at=sync_time,
        skipped_runs=runs_load.skipped,
        message=(
            f"Inserted {inserted_runs} new runs and {inserted_rides} new rides "
            f"({sync_type} sync){skipped_msg}"
        ),
    )


@router.post(
    "/update-data",
    response_class=RedirectResponse,
    status_code=307,
    deprecated=True,
    include_in_schema=True,
)
async def update_strava_data_deprecated() -> RedirectResponse:
    """Deprecated: Use /strava/sync instead.

    This endpoint redirects to /strava/sync and will be removed in a future version.
    """
    logger.warning(
        "Deprecated endpoint /strava/update-data called. Use /strava/sync instead."
    )
    return RedirectResponse(url="/strava/sync", status_code=307)
