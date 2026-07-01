"""CRUD routes for rides (currently: PATCH only)."""

import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from fitness.app.auth import require_editor, require_viewer
from fitness.app.routers._sync_helpers import perform_unsync
from fitness.db.rides import (
    get_ride_by_id,
    update_ride,
    update_ride_name,
    get_ride_duplicate_of,
    mark_ride_duplicate,
    unmark_ride_duplicate,
    find_candidate_duplicate_rides,
)
from fitness.db.synced_rides import (
    is_ride_synced,
    get_synced_ride,
    delete_synced_ride,
)
from fitness.db.tags import set_ride_tags
from fitness.models import Ride
from fitness.models.ride_detail import RideDetail
from fitness.models.tag import Tag
from fitness.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rides", tags=["ride-editing"])


class RideUpdateRequest(BaseModel):
    """Request model for updating a ride.

    All fields are optional; only fields explicitly set are applied. The
    backend rejects post-update states where an Outdoor Ride has no
    positive distance.
    """

    type: Literal["Outdoor Ride", "Indoor Ride"] | None = None
    distance: float | None = Field(None, ge=0, description="Distance in miles")
    duration: float | None = Field(None, ge=0, description="Duration in seconds")
    avg_heart_rate: float | None = Field(
        None, ge=0, le=220, description="Average heart rate"
    )
    datetime_utc: datetime | None = Field(
        None, description="When the ride occurred (UTC)"
    )


class RideUpdateResponse(BaseModel):
    """Response model for ride update operations."""

    status: str
    message: str
    ride: Ride


@router.patch("/{ride_id}", response_model=RideUpdateResponse)
def update_ride_endpoint(
    ride_id: str,
    update_request: RideUpdateRequest,
    _user: User = Depends(require_editor),
) -> RideUpdateResponse:
    """Update a ride.

    Indoor and outdoor rides share the same shape; the type field
    determines whether distance is meaningful. An update that leaves the
    ride as an Outdoor Ride with `distance <= 0` is rejected.
    """
    existing = get_ride_by_id(ride_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ride {ride_id} not found",
        )

    updates = update_request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    # Validate post-update invariant: Outdoor Ride must have a positive distance.
    final_type = updates.get("type", existing.type)
    final_distance = updates.get("distance", existing.distance)
    if final_type == "Outdoor Ride" and final_distance <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outdoor Ride requires a positive distance",
        )

    try:
        updated = update_ride(ride_id, updates)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    return RideUpdateResponse(
        status="success",
        message="Ride updated",
        ride=updated,
    )


class RideNameUpdateRequest(BaseModel):
    """Request model for setting a ride's user-authored display name."""

    name: str | None = Field(
        None, max_length=255, description="Display name; null or empty clears it"
    )


@router.patch("/{ride_id}/name", response_model=Ride)
def update_ride_name_endpoint(
    ride_id: str,
    request: RideNameUpdateRequest,
    _user: User = Depends(require_editor),
) -> Ride:
    """Set or clear a ride's user-authored display name.

    Unlike metric edits (`PATCH /rides/{id}`), this is a lightweight single-field
    update: it is NOT version-tracked and IS allowed on calendar-synced rides
    (a name doesn't affect the synced event).
    """
    if get_ride_by_id(ride_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ride {ride_id} not found",
        )
    name = (request.name or "").strip() or None
    update_ride_name(ride_id, name)
    updated = get_ride_by_id(ride_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ride {ride_id} not found",
        )
    return updated


class SetRideTagsRequest(BaseModel):
    """Request model for replacing a ride's tag assignments."""

    tag_ids: list[str]


@router.put("/{ride_id}/tags", response_model=list[Tag])
def set_ride_tags_endpoint(
    ride_id: str,
    request: SetRideTagsRequest,
    _user: User = Depends(require_editor),
) -> list[Tag]:
    """Replace the full set of tags assigned to a ride.

    Unlike metric edits (`PATCH /rides/{id}`), this is allowed on
    calendar-synced rides (tags don't affect the synced event).
    """
    if get_ride_by_id(ride_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ride {ride_id} not found",
        )
    try:
        return set_ride_tags(ride_id, request.tag_ids)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


class MarkDuplicateRequest(BaseModel):
    """Request model for marking a ride as a duplicate of another ride."""

    duplicate_of_id: str = Field(
        ..., description="ID of the ride this is a duplicate of (the one to keep)"
    )


class MarkDuplicateResponse(BaseModel):
    """Response model for mark/unmark duplicate operations."""

    status: str
    message: str
    ride_id: str
    duplicate_of_id: str | None = None


@router.post("/{ride_id}/duplicate-of", response_model=MarkDuplicateResponse)
def mark_ride_as_duplicate(
    ride_id: str,
    request: MarkDuplicateRequest,
    _user: User = Depends(require_editor),
) -> MarkDuplicateResponse:
    """Mark a ride as a duplicate of another ride.

    Hides this ride from the feed and metrics (via ``deleted_at``, which also
    prevents re-import) and records which ride it duplicates. If the ride is
    synced to Google Calendar, it is unsynced first so no orphaned event remains.
    """
    if get_ride_by_id(ride_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ride {ride_id} not found",
        )

    target_id = request.duplicate_of_id
    if target_id == ride_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A ride cannot be a duplicate of itself",
        )

    # The kept ride must exist and be live. Look it up including soft-deleted so
    # a duplicate (always soft-deleted) yields a precise error, not a plain 404.
    target = get_ride_by_id(target_id, include_deleted=True)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ride to keep ({target_id}) not found",
        )
    if target.deleted_at is not None:
        if get_ride_duplicate_of(target_id) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Ride to keep ({target_id}) is itself a duplicate; "
                    "point at the original ride instead"
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ride to keep ({target_id}) has been deleted",
        )

    if is_ride_synced(ride_id):
        result = perform_unsync(
            entity_id=ride_id,
            entity_type="ride",
            synced_record=get_synced_ride(ride_id),
            delete_sync_record=lambda: delete_synced_ride(ride_id),
        )
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Could not unsync ride before marking duplicate: {result.message}",
            )

    if not mark_ride_duplicate(ride_id, target_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ride {ride_id} could not be marked as a duplicate",
        )

    return MarkDuplicateResponse(
        status="success",
        message=f"Ride {ride_id} marked as duplicate of {target_id}",
        ride_id=ride_id,
        duplicate_of_id=target_id,
    )


@router.delete("/{ride_id}/duplicate-of", response_model=MarkDuplicateResponse)
def unmark_ride_as_duplicate(
    ride_id: str,
    _user: User = Depends(require_editor),
) -> MarkDuplicateResponse:
    """Reverse a duplicate marking, restoring the ride to the feed."""
    if not unmark_ride_duplicate(ride_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ride {ride_id} is not currently marked as a duplicate",
        )
    return MarkDuplicateResponse(
        status="success",
        message=f"Ride {ride_id} is no longer marked as a duplicate",
        ride_id=ride_id,
        duplicate_of_id=None,
    )


@router.get("/{ride_id}/duplicate-candidates", response_model=list[RideDetail])
def get_ride_duplicate_candidates(
    ride_id: str,
    window_minutes: int = 120,
    _user: User = Depends(require_viewer),
) -> list[RideDetail]:
    """List live rides near this one in time that it could be a duplicate of."""
    if get_ride_by_id(ride_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ride {ride_id} not found",
        )
    return find_candidate_duplicate_rides(ride_id, window_minutes=window_minutes)
