import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

from fitness.app.dependencies import strava_client
from fitness.app.auth import require_editor
from fitness.models.user import User
from fitness.models.responses import DataImportResponse
from fitness.integrations.strava.client import StravaClient
from fitness.models import Run
from fitness.db.runs import get_existing_run_ids, bulk_create_runs
from fitness.db.sync_metadata import get_last_sync_time, update_last_sync_time
from fitness.load.strava import load_strava_runs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strava", tags=["strava"])

PROVIDER_NAME = "strava"


@router.post("/sync", response_model=DataImportResponse)
async def sync_strava_data(
    full_sync: bool = Query(
        False,
        description="Force a full sync instead of incremental. "
        "Use this to re-fetch all data from the beginning.",
    ),
    user: User = Depends(require_editor),
    strava_client: StravaClient = Depends(strava_client),
) -> DataImportResponse:
    """Sync Strava data, fetching only new activities since last sync.

    By default, performs an incremental sync fetching only activities created
    after the last successful sync. Use `full_sync=true` to fetch all data.

    Requires authentication with editor role.

    Returns a summary of the sync operation including count of new runs inserted.
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

    # Get Strava runs from the API (with optional after filter)
    strava_runs = [
        Run.from_strava(run) for run in load_strava_runs(strava_client, after=after)
    ]

    # Get the IDs of all existing runs in the db.
    existing_run_ids = get_existing_run_ids()

    # Filter to only new runs (double-check even with incremental sync)
    new_runs = [run for run in strava_runs if run.id not in existing_run_ids]

    if new_runs:
        inserted_count = bulk_create_runs(new_runs)
        logger.info(f"Inserted {inserted_count} new runs into the database")
    else:
        inserted_count = 0
        logger.info("No new runs to insert")

    # Update last sync time on successful completion
    update_last_sync_time(PROVIDER_NAME, sync_time)

    sync_type = "full" if full_sync or after is None else "incremental"
    return DataImportResponse(
        inserted_count=inserted_count,
        updated_at=sync_time,
        message=f"Inserted {inserted_count} new runs ({sync_type} sync)",
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
