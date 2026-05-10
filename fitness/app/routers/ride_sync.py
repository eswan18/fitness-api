"""Google Calendar sync routes for rides."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from fitness.app.auth import require_editor, require_viewer
from fitness.db.rides import get_ride_by_id
from fitness.db.synced_rides import (
    create_synced_ride,
    delete_synced_ride,
    get_all_synced_rides,
    get_failed_ride_syncs,
    get_synced_ride,
    update_synced_ride,
)
from fitness.models.sync import (
    SyncedRide,
    SyncResponse,
    SyncRideStatusResponse,
)
from fitness.models.user import User
from ._sync_helpers import perform_sync, perform_unsync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["ride-sync"])


@router.get("/rides/{ride_id}/status", response_model=SyncRideStatusResponse)
def get_ride_sync_status(
    ride_id: str,
    _user: User = Depends(require_viewer),
) -> SyncRideStatusResponse:
    """Get the Google Calendar sync status for a specific ride."""
    synced = get_synced_ride(ride_id)
    if synced is None:
        return SyncRideStatusResponse(
            ride_id=ride_id,
            is_synced=False,
            sync_status=None,
            synced_at=None,
            google_event_id=None,
            ride_version=None,
            error_message=None,
        )
    return SyncRideStatusResponse(
        ride_id=ride_id,
        is_synced=synced.sync_status == "synced",
        sync_status=synced.sync_status,
        synced_at=synced.synced_at,
        google_event_id=synced.google_event_id,
        ride_version=synced.ride_version,
        error_message=synced.error_message,
    )


@router.post("/rides/{ride_id}", response_model=SyncResponse)
def sync_ride_to_calendar(
    ride_id: str,
    _user: User = Depends(require_editor),
) -> SyncResponse:
    """Sync a ride to Google Calendar."""
    existing_sync = get_synced_ride(ride_id)

    ride = get_ride_by_id(ride_id)
    if ride is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ride {ride_id} not found",
        )

    return perform_sync(
        entity_id=ride_id,
        entity_type="ride",
        existing_sync=existing_sync,
        create_calendar_event=lambda client: client.create_ride_event(ride),
        create_sync_record=lambda gid, s: create_synced_ride(
            ride_id=ride_id,
            google_event_id=gid,
            ride_version=1,
            sync_status=s,
        ),
        update_sync_record=lambda gid: update_synced_ride(
            ride_id=ride_id,
            google_event_id=gid,
            sync_status="synced",
            clear_error_message=True,
        ),
        record_failure=lambda gid, msg: (
            update_synced_ride(ride_id=ride_id, sync_status="failed", error_message=msg)
            if existing_sync
            else create_synced_ride(
                ride_id=ride_id,
                google_event_id=gid or "",
                sync_status="failed",
                error_message=msg,
            )
        ),
    )


@router.delete("/rides/{ride_id}", response_model=SyncResponse)
def unsync_ride_from_calendar(
    ride_id: str,
    _user: User = Depends(require_editor),
) -> SyncResponse:
    """Remove a ride's sync from Google Calendar."""
    return perform_unsync(
        entity_id=ride_id,
        entity_type="ride",
        synced_record=get_synced_ride(ride_id),
        delete_sync_record=lambda: delete_synced_ride(ride_id),
    )


@router.get("/rides", response_model=list[SyncedRide])
def get_all_ride_sync_records(
    _user: User = Depends(require_viewer),
) -> list[SyncedRide]:
    """Get all ride sync records (admin/debugging)."""
    return get_all_synced_rides()


@router.get("/rides/failed", response_model=list[SyncedRide])
def get_failed_ride_sync_records(
    _user: User = Depends(require_viewer),
) -> list[SyncedRide]:
    """Get all rides with failed sync status."""
    return get_failed_ride_syncs()
