"""Google Calendar sync routes for lifts."""

from fastapi import APIRouter, HTTPException, status, Depends
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
from fitness.app.auth import require_viewer, require_editor
from ._sync_helpers import perform_sync, perform_unsync

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
        google_event_id=synced_lift.google_event_id or None,
        lift_version=synced_lift.lift_version,
        error_message=synced_lift.error_message,
    )


@router.post("/lifts/{lift_id}", response_model=SyncResponse)
def sync_lift_to_calendar(
    lift_id: str,
    user: User = Depends(require_editor),
) -> SyncResponse:
    """Sync a lift to Google Calendar. Requires OAuth 2.0 Bearer token."""
    existing_sync = get_synced_lift(lift_id)

    lift = get_lift_by_id(lift_id)
    if lift is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lift {lift_id} not found",
        )

    return perform_sync(
        entity_id=lift_id,
        entity_type="lift",
        existing_sync=existing_sync,
        create_calendar_event=lambda client: client.create_lift_event(lift),
        create_sync_record=lambda gid, s: create_synced_lift(
            lift_id=lift_id, google_event_id=gid, lift_version=1, sync_status=s,
        ),
        update_sync_record=lambda gid: update_synced_lift(
            lift_id=lift_id, google_event_id=gid, sync_status="synced", clear_error_message=True,
        ),
        record_failure=lambda gid, msg: (
            update_synced_lift(lift_id=lift_id, sync_status="failed", error_message=msg)
            if existing_sync
            else create_synced_lift(lift_id=lift_id, google_event_id=gid or "", sync_status="failed", error_message=msg)
        ),
    )


@router.delete("/lifts/{lift_id}", response_model=SyncResponse)
def unsync_lift_from_calendar(
    lift_id: str,
    user: User = Depends(require_editor),
) -> SyncResponse:
    """Remove a lift's sync from Google Calendar. Requires OAuth 2.0 Bearer token."""
    return perform_unsync(
        entity_id=lift_id,
        entity_type="lift",
        synced_record=get_synced_lift(lift_id),
        delete_sync_record=lambda: delete_synced_lift(lift_id),
    )


@router.get("/lifts", response_model=list[SyncedLift])
def get_all_lift_sync_records(
    _user: User = Depends(require_viewer),
) -> list[SyncedLift]:
    """Get all lift sync records for debugging/admin purposes."""
    return get_all_synced_lifts()


@router.get("/lifts/failed", response_model=list[SyncedLift])
def get_failed_lift_sync_records(
    _user: User = Depends(require_viewer),
) -> list[SyncedLift]:
    """Get all lifts with failed sync status for retry/debugging."""
    return get_failed_lift_syncs()
