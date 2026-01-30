"""Google Calendar sync routes for lifts."""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import logging

from fitness.db.lifts import get_lift_by_id
from fitness.db.synced_lifts import (
    get_synced_lift,
    create_synced_lift,
    update_synced_lift,
    delete_synced_lift,
    get_all_synced_lifts,
    get_failed_lift_syncs,
)
from fitness.models.sync import (
    SyncedLift,
    SyncResponse,
    SyncLiftStatusResponse,
)
from fitness.models.user import User
from fitness.integrations.google.calendar_client import GoogleCalendarClient
from fitness.app.auth import require_viewer, require_editor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/lifts/{lift_id}/status", response_model=SyncLiftStatusResponse)
def get_lift_sync_status(
    lift_id: str,
    _user: User = Depends(require_viewer),
) -> SyncLiftStatusResponse:
    """Get the Google Calendar sync status for a specific lift."""
    synced_lift = get_synced_lift(lift_id)

    if synced_lift is None:
        return SyncLiftStatusResponse(
            lift_id=lift_id,
            is_synced=False,
            sync_status=None,
            synced_at=None,
            google_event_id=None,
            lift_version=None,
            error_message=None,
        )

    return SyncLiftStatusResponse(
        lift_id=lift_id,
        is_synced=synced_lift.sync_status == "synced",
        sync_status=synced_lift.sync_status,
        synced_at=synced_lift.synced_at,
        google_event_id=synced_lift.google_event_id,
        lift_version=synced_lift.lift_version,
        error_message=synced_lift.error_message,
    )


@router.post("/lifts/{lift_id}", response_model=SyncResponse)
def sync_lift_to_calendar(
    lift_id: str,
    user: User = Depends(require_editor),
) -> SyncResponse:
    """Sync a lift to Google Calendar using the Google Calendar API."""
    existing_sync = get_synced_lift(lift_id)
    if existing_sync and existing_sync.sync_status == "synced":
        return SyncResponse(
            success=False,
            message=f"Lift {lift_id} is already synced to Google Calendar",
            google_event_id=existing_sync.google_event_id,
            sync_status=existing_sync.sync_status,
            synced_at=existing_sync.synced_at,
        )

    lift = get_lift_by_id(lift_id)
    if lift is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lift {lift_id} not found",
        )

    try:
        calendar_client = GoogleCalendarClient()
        google_event_id = calendar_client.create_lift_event(lift)

        if google_event_id is None:
            raise Exception("Failed to create Google Calendar event")

        if existing_sync:
            updated_sync = update_synced_lift(
                lift_id=lift_id,
                google_event_id=google_event_id,
                sync_status="synced",
                clear_error_message=True,
            )
            if updated_sync is None:
                raise HTTPException(
                    status_code=500, detail="Failed to update sync record"
                )
            synced_lift = updated_sync
        else:
            synced_lift = create_synced_lift(
                lift_id=lift_id,
                google_event_id=google_event_id,
                lift_version=1,
                sync_status="synced",
            )

        logger.info(
            f"Successfully synced lift {lift_id} to Google Calendar event {google_event_id}"
        )

        return SyncResponse(
            success=True,
            message=f"Successfully synced lift {lift_id} to Google Calendar",
            google_event_id=synced_lift.google_event_id,
            sync_status=synced_lift.sync_status,
            synced_at=synced_lift.synced_at,
        )

    except Exception as e:
        error_msg = f"Failed to sync lift {lift_id}: {str(e)}"
        logger.exception(
            f"Error syncing lift to Google Calendar: lift_id={lift_id}, "
            f"exception_type={type(e).__name__}, error={str(e)}"
        )

        try:
            if existing_sync:
                update_synced_lift(
                    lift_id=lift_id,
                    sync_status="failed",
                    error_message=error_msg,
                )
                logger.info(f"Updated sync record to 'failed' status for lift {lift_id}")
            else:
                create_synced_lift(
                    lift_id=lift_id,
                    google_event_id="",
                    sync_status="failed",
                    error_message=error_msg,
                )
                logger.info(f"Created failed sync record for lift {lift_id}")
        except Exception as db_error:
            logger.exception(
                f"Failed to persist sync failure to database: lift_id={lift_id}, "
                f"exception_type={type(db_error).__name__}, error={str(db_error)}"
            )

        return SyncResponse(
            success=False,
            message=error_msg,
            google_event_id=None,
            sync_status="failed",
            synced_at=None,
        )


@router.delete("/lifts/{lift_id}", response_model=SyncResponse)
def unsync_lift_from_calendar(
    lift_id: str,
    user: User = Depends(require_editor),
) -> SyncResponse:
    """Remove a lift's sync from Google Calendar."""
    synced_lift = get_synced_lift(lift_id)

    if synced_lift is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lift {lift_id} is not currently synced",
        )

    try:
        if not synced_lift.google_event_id or synced_lift.sync_status != "synced":
            deleted = delete_synced_lift(lift_id)
            if deleted:
                logger.info(
                    f"Removed local sync record for lift {lift_id} without Google deletion"
                )
                return SyncResponse(
                    success=True,
                    message=f"Removed sync record for lift {lift_id}",
                    google_event_id=None,
                    sync_status="unsynced",
                    synced_at=None,
                )
            else:
                raise Exception("Failed to delete sync record from database")

        calendar_client = GoogleCalendarClient()
        success = calendar_client.delete_workout_event(synced_lift.google_event_id)

        if not success:
            raise Exception(
                f"Failed to delete Google Calendar event {synced_lift.google_event_id}"
            )

        deleted = delete_synced_lift(lift_id)

        if deleted:
            logger.info(f"Successfully unsynced lift {lift_id} from Google Calendar")
            return SyncResponse(
                success=True,
                message=f"Successfully removed sync for lift {lift_id}",
                google_event_id=synced_lift.google_event_id,
                sync_status="unsynced",
                synced_at=None,
            )
        else:
            raise Exception("Failed to delete sync record from database")

    except Exception as e:
        error_msg = f"Failed to unsync lift {lift_id}: {str(e)}"
        logger.exception(
            f"Error unsyncing lift from Google Calendar: lift_id={lift_id}, "
            f"google_event_id={synced_lift.google_event_id if synced_lift else None}, "
            f"exception_type={type(e).__name__}, error={str(e)}"
        )

        return SyncResponse(
            success=False,
            message=error_msg,
            google_event_id=synced_lift.google_event_id,
            sync_status=synced_lift.sync_status,
            synced_at=synced_lift.synced_at,
        )


@router.get("/lifts", response_model=List[SyncedLift])
def get_all_lift_sync_records(_user: User = Depends(require_viewer)) -> List[SyncedLift]:
    """Get all lift sync records for debugging/admin purposes."""
    return get_all_synced_lifts()


@router.get("/lifts/failed", response_model=List[SyncedLift])
def get_failed_lift_sync_records(_user: User = Depends(require_viewer)) -> List[SyncedLift]:
    """Get all lifts with failed sync status for retry/debugging."""
    return get_failed_lift_syncs()
