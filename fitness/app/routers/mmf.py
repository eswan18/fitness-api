import logging
import os
from datetime import datetime, timezone as tz
from io import BytesIO

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status

from fitness.app.auth import require_editor
from fitness.models import Run
from fitness.models.user import User
from fitness.models.responses import DataImportResponse
from fitness.db.runs import get_existing_run_ids, bulk_create_runs
from fitness.load.mmf import load_mmf_runs_from_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mmf", tags=["mmf"])


@router.post("/upload-csv", response_model=DataImportResponse)
async def upload_mmf_csv(
    file: UploadFile = File(...),
    timezone: str | None = None,
    user: User = Depends(require_editor),
) -> DataImportResponse:
    """Upload MapMyFitness CSV data and insert any new runs not in the database.

    Requires OAuth 2.0 Bearer token authentication.

    Args:
        file: CSV file upload via multipart/form-data (required).
        timezone: Optional IANA timezone name (e.g., "America/Chicago").
                  If not provided, uses MMF_TIMEZONE env var or defaults to "America/Chicago".

    Returns:
        Summary including counts of external runs, existing DB runs, new runs found
        and inserted, and IDs of newly inserted runs.
    """
    try:
        # Determine timezone to use
        if timezone is None:
            timezone = os.environ.get("MMF_TIMEZONE", "America/Chicago")

        # Load MMF runs from uploaded file
        logger.info(f"Loading MMF data from uploaded file: {file.filename}")
        file_content = await file.read()
        file_obj = BytesIO(file_content)
        mmf_activities = load_mmf_runs_from_file(file_obj, timezone)

        # Convert MMF activities to Run models
        mmf_runs = [Run.from_mmf(activity) for activity in mmf_activities]

        # Get the IDs of all existing runs in the db
        existing_run_ids = get_existing_run_ids()

        # Filter to only new runs
        new_runs = [run for run in mmf_runs if run.id not in existing_run_ids]

        if new_runs:
            inserted_count = bulk_create_runs(new_runs)
            logger.info(f"Inserted {inserted_count} new MMF runs into the database")
        else:
            inserted_count = 0
            logger.info("No new MMF runs to insert")

        return DataImportResponse(
            inserted_count=inserted_count,
            total_runs_found=len(mmf_runs),
            existing_runs=len(mmf_runs) - len(new_runs),
            updated_at=datetime.now(tz.utc),
            message=f"Inserted {inserted_count} new runs into the database",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to update MMF data: {type(e).__name__}: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process MMF data: {str(e)}",
        )
