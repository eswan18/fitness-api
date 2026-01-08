"""Google Calendar sync routes."""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import logging

from fitness.db.runs import get_run_by_id
from fitness.db.synced_runs import (
    get_synced_run,
    create_synced_run,
    update_synced_run,
    delete_synced_run,
    get_all_synced_runs,
    get_failed_syncs,
)
from fitness.models.sync import (
    SyncedRun,
    SyncResponse,
    SyncStatusResponse,
)
from fitness.integrations.google.calendar_client import GoogleCalendarClient
from fitness.app.auth import verify_credentials

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/runs/{run_id}/status", response_model=SyncStatusResponse)
def get_sync_status(run_id: str) -> SyncStatusResponse:
    """Get the Google Calendar sync status for a specific run.

    Args:
        run_id: The ID of the run to check sync status for.

    Returns:
        SyncStatusResponse with current sync status information.
    """
    synced_run = get_synced_run(run_id)

    if synced_run is None:
        return SyncStatusResponse(
            run_id=run_id,
            is_synced=False,
            sync_status=None,
            synced_at=None,
            google_event_id=None,
            run_version=None,
            error_message=None,
        )

    return SyncStatusResponse(
        run_id=run_id,
        is_synced=synced_run.sync_status == "synced",
        sync_status=synced_run.sync_status,
        synced_at=synced_run.synced_at,
        google_event_id=synced_run.google_event_id,
        run_version=synced_run.run_version,
        error_message=synced_run.error_message,
    )


@router.post("/runs/{run_id}", response_model=SyncResponse)
def sync_run_to_calendar(
    run_id: str, username: str = Depends(verify_credentials)
) -> SyncResponse:
    """Sync a run to Google Calendar using the Google Calendar API.

    Requires authentication via HTTP Basic Auth.

    Args:
        run_id: The ID of the run to sync.
        username: Authenticated username (injected by dependency).

    Returns:
        SyncResponse indicating the result of the sync operation.
    """
    # Check if run is already synced
    existing_sync = get_synced_run(run_id)
    if existing_sync and existing_sync.sync_status == "synced":
        return SyncResponse(
            success=False,
            message=f"Run {run_id} is already synced to Google Calendar",
            google_event_id=existing_sync.google_event_id,
            sync_status=existing_sync.sync_status,
            synced_at=existing_sync.synced_at,
        )

    # Get the run data from the database
    run = get_run_by_id(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )

    try:
        # Initialize Google Calendar client
        calendar_client = GoogleCalendarClient()

        # Create the calendar event
        google_event_id = calendar_client.create_workout_event(run)

        if google_event_id is None:
            raise Exception("Failed to create Google Calendar event")

        if existing_sync:
            # Update existing failed sync
            updated_sync = update_synced_run(
                run_id=run_id,
                google_event_id=google_event_id,
                sync_status="synced",
                clear_error_message=True,
            )
            if updated_sync is None:
                raise HTTPException(
                    status_code=500, detail="Failed to update sync record"
                )
            synced_run = updated_sync
        else:
            # Create new sync record
            synced_run = create_synced_run(
                run_id=run_id,
                google_event_id=google_event_id,
                run_version=1,
                sync_status="synced",
            )

        logger.info(
            f"Successfully synced run {run_id} to Google Calendar event {google_event_id}"
        )

        return SyncResponse(
            success=True,
            message=f"Successfully synced run {run_id} to Google Calendar",
            google_event_id=synced_run.google_event_id,
            sync_status=synced_run.sync_status,
            synced_at=synced_run.synced_at,
        )

    except Exception as e:
        # Handle any errors (Google API, database, etc.)
        error_msg = f"Failed to sync run {run_id}: {str(e)}"
        logger.exception(
            f"Error syncing run to Google Calendar: run_id={run_id}, "
            f"exception_type={type(e).__name__}, error={str(e)}"
        )

        # Try to create/update a failed sync record
        try:
            if existing_sync:
                update_synced_run(
                    run_id=run_id,
                    sync_status="failed",
                    error_message=error_msg,
                )
                logger.info(f"Updated sync record to 'failed' status for run {run_id}")
            else:
                create_synced_run(
                    run_id=run_id,
                    google_event_id="",
                    sync_status="failed",
                    error_message=error_msg,
                )
                logger.info(f"Created failed sync record for run {run_id}")
        except Exception as db_error:
            logger.exception(
                f"Failed to persist sync failure to database: run_id={run_id}, "
                f"exception_type={type(db_error).__name__}, error={str(db_error)}"
            )

        return SyncResponse(
            success=False,
            message=error_msg,
            google_event_id=None,
            sync_status="failed",
            synced_at=None,
        )


@router.delete("/runs/{run_id}", response_model=SyncResponse)
def unsync_run_from_calendar(
    run_id: str, username: str = Depends(verify_credentials)
) -> SyncResponse:
    """Remove a run's sync from Google Calendar using the Google Calendar API.

    Requires authentication via HTTP Basic Auth.

    Args:
        run_id: The ID of the run to unsync.
        username: Authenticated username (injected by dependency).

    Returns:
        SyncResponse indicating the result of the unsync operation.
    """
    synced_run = get_synced_run(run_id)

    if synced_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} is not currently synced",
        )

    try:
        # If there's no valid event to delete or status isn't 'synced', just remove the record
        if not synced_run.google_event_id or synced_run.sync_status != "synced":
            deleted = delete_synced_run(run_id)
            if deleted:
                logger.info(
                    f"Removed local sync record for run {run_id} without Google deletion"
                )
                return SyncResponse(
                    success=True,
                    message=f"Removed sync record for run {run_id}",
                    google_event_id=None,
                    sync_status="failed",
                    synced_at=None,
                )
            else:
                raise Exception("Failed to delete sync record from database")

        # Otherwise, delete from Google then remove local record
        calendar_client = GoogleCalendarClient()
        success = calendar_client.delete_workout_event(synced_run.google_event_id)

        if not success:
            raise Exception(
                f"Failed to delete Google Calendar event {synced_run.google_event_id}"
            )

        deleted = delete_synced_run(run_id)

        if deleted:
            logger.info(f"Successfully unsynced run {run_id} from Google Calendar")
            return SyncResponse(
                success=True,
                message=f"Successfully removed sync for run {run_id}",
                google_event_id=synced_run.google_event_id,
                sync_status="failed",
                synced_at=None,
            )
        else:
            raise Exception("Failed to delete sync record from database")

    except Exception as e:
        error_msg = f"Failed to unsync run {run_id}: {str(e)}"
        logger.exception(
            f"Error unsyncing run from Google Calendar: run_id={run_id}, "
            f"google_event_id={synced_run.google_event_id if synced_run else None}, "
            f"exception_type={type(e).__name__}, error={str(e)}"
        )

        return SyncResponse(
            success=False,
            message=error_msg,
            google_event_id=synced_run.google_event_id,
            sync_status=synced_run.sync_status,
            synced_at=synced_run.synced_at,
        )


@router.get("/runs", response_model=List[SyncedRun])
def get_all_sync_records() -> List[SyncedRun]:
    """Get all sync records for debugging/admin purposes.

    Returns:
        List of all SyncedRun records.
    """
    return get_all_synced_runs()


@router.get("/runs/failed", response_model=List[SyncedRun])
def get_failed_sync_records() -> List[SyncedRun]:
    """Get all runs with failed sync status for retry/debugging.

    Returns:
        List of SyncedRun records with 'failed' status.
    """
    return get_failed_syncs()
