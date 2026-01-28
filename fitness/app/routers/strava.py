import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from fitness.app.dependencies import strava_client
from fitness.app.auth import require_editor
from fitness.models.user import User
from fitness.models.responses import DataImportResponse
from fitness.integrations.strava.client import StravaClient
from fitness.models import Run
from fitness.db.runs import get_existing_run_ids, bulk_create_runs
from fitness.load.strava import load_strava_runs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strava", tags=["strava"])


@router.post("/sync", response_model=DataImportResponse)
async def sync_strava_data(
    user: User = Depends(require_editor),
    strava_client: StravaClient = Depends(strava_client),
) -> DataImportResponse:
    """Fetch Strava data and insert any new runs not in the database.

    Requires authentication via HTTP Basic Auth.

    Returns a summary including counts of external runs, existing DB runs, new
    runs found and inserted, and IDs of newly inserted runs.
    """
    # Get all the Strava runs from the Strava API and convert them to Run models.
    strava_runs = [Run.from_strava(run) for run in load_strava_runs(strava_client)]
    # Get the IDs of all existing runs in the db.
    existing_run_ids = get_existing_run_ids()
    # Filter to only new runs.
    new_runs = [run for run in strava_runs if run.id not in existing_run_ids]

    if new_runs:
        inserted_count = bulk_create_runs(new_runs)
        logger.info(f"Inserted {inserted_count} new runs into the database")
    else:
        inserted_count = 0
        logger.info("No new runs to insert")
    return DataImportResponse(
        inserted_count=inserted_count,
        updated_at=datetime.now(timezone.utc),
        message=f"Inserted {inserted_count} new runs into the database",
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
