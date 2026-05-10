"""CRUD routes for rides (currently: PATCH only)."""

import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from fitness.app.auth import require_editor
from fitness.db.rides import get_ride_by_id, update_ride
from fitness.models import Ride
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
