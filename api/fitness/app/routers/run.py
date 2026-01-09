"""
API endpoints for run editing and history management.

Provides endpoints to update a run with full history tracking, retrieve the
edit history, fetch a specific historical version, and restore a run to a
previous version.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field

from fitness.db.runs import get_run_by_id
from fitness.db.runs_history import (
    update_run_with_history,
    get_run_history,
    get_run_version,
    RunHistoryRecord,
)
from fitness.app.auth import verify_oauth_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["run-editing"])


class RunUpdateRequest(BaseModel):
    """Request model for updating a run."""

    distance: Optional[float] = Field(None, ge=0, description="Distance in miles")
    duration: Optional[float] = Field(None, ge=0, description="Duration in seconds")
    avg_heart_rate: Optional[float] = Field(
        None, ge=0, le=220, description="Average heart rate"
    )
    type: Optional[str] = Field(
        None, pattern="^(Outdoor Run|Treadmill Run)$", description="Run type"
    )
    shoe_id: Optional[str] = Field(None, description="Shoe ID (foreign key)")
    datetime_utc: Optional[datetime] = Field(
        None, description="When the run occurred (UTC)"
    )
    change_reason: Optional[str] = Field(None, description="Reason for the change")
    changed_by: str = Field(..., description="User making the change")


class RunHistoryResponse(BaseModel):
    """Response model for run history."""

    history_id: int
    run_id: str
    version_number: int
    change_type: str
    datetime_utc: datetime
    type: str
    distance: float
    duration: float
    source: str
    avg_heart_rate: Optional[float]
    shoe_id: Optional[str]
    changed_at: datetime
    changed_by: Optional[str]
    change_reason: Optional[str]

    @classmethod
    def from_history_record(cls, record: RunHistoryRecord) -> "RunHistoryResponse":
        """Convert a RunHistoryRecord to a response model."""
        return cls(
            history_id=record.history_id,
            run_id=record.run_id,
            version_number=record.version_number,
            change_type=record.change_type,
            datetime_utc=record.datetime_utc,
            type=record.type,
            distance=record.distance,
            duration=record.duration,
            source=record.source,
            avg_heart_rate=record.avg_heart_rate,
            shoe_id=record.shoe_id,
            changed_at=record.changed_at,
            changed_by=record.changed_by,
            change_reason=record.change_reason,
        )


@router.patch("/{run_id}", response_model=Dict[str, Any])
def update_run(
    run_id: str,
    update_request: RunUpdateRequest,
    username: str = Depends(verify_oauth_token),
) -> Dict[str, Any]:
    """
    Update a run with change tracking.

    Requires authentication via HTTP Basic Auth.

    This endpoint allows updating specific fields of a run while preserving
    the full edit history. The original state is saved before making changes.

    Args:
        run_id: The ID of the run to update.
        update_request: The fields to update and audit metadata.
        username: Authenticated username (injected by dependency).
    """
    try:
        # Verify the run exists
        existing_run = get_run_by_id(run_id)
        if not existing_run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run with ID {run_id} not found",
            )

        # Build updates dictionary, excluding None values and metadata fields
        updates = update_request.model_dump(
            exclude_none=True, exclude={"changed_by", "change_reason"}
        )

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid fields provided for update",
            )

        # Perform the update with history tracking
        update_run_with_history(
            run_id=run_id,
            updates=updates,
            changed_by=update_request.changed_by,
            change_reason=update_request.change_reason,
        )

        logger.info(f"Successfully updated run {run_id} by {update_request.changed_by}")

        # Return the updated run
        updated_run = get_run_by_id(run_id)
        return {
            "status": "success",
            "message": f"Run {run_id} updated successfully",
            "run": updated_run.model_dump() if updated_run else None,
            "updated_fields": list(updates.keys()),
            "updated_at": datetime.now().isoformat(),
            "updated_by": update_request.changed_by,
        }

    except ValueError as e:
        logger.error(f"Validation error updating run {run_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions as-is (like 404s)
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating run {run_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while updating run",
        )


@router.get("/{run_id}/history", response_model=List[RunHistoryResponse])
def get_run_edit_history(
    run_id: str, limit: Optional[int] = 50
) -> List[RunHistoryResponse]:
    """
    Get the edit history for a specific run.

    Returns all historical versions of the run, ordered by version number (newest first).
    The first entry will be the most recent version, and the last will be the original.

    Args:
        run_id: The run identifier to look up.
        limit: Optional maximum number of history entries to return (newest first).
    """
    try:
        # Verify the run exists
        existing_run = get_run_by_id(run_id)
        if not existing_run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run with ID {run_id} not found",
            )

        history_records = get_run_history(run_id, limit=limit)

        if not history_records:
            # Run exists but has no history - this could happen during migration
            logger.warning(f"Run {run_id} exists but has no history records")
            return []

        response = [
            RunHistoryResponse.from_history_record(record) for record in history_records
        ]

        logger.debug(f"Retrieved {len(response)} history records for run {run_id}")
        return response

    except HTTPException:
        # Re-raise HTTP exceptions as-is (like 404s)
        raise
    except Exception as e:
        logger.error(f"Error retrieving history for run {run_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving run history",
        )


@router.get("/{run_id}/history/{version_number}", response_model=RunHistoryResponse)
def get_run_specific_version(run_id: str, version_number: int) -> RunHistoryResponse:
    """
    Get a specific version of a run from its history.

    This allows you to see exactly what the run looked like at a particular point in time.

    Args:
        run_id: The run identifier to look up.
        version_number: The historical version number to return.
    """
    try:
        # Verify the run exists
        existing_run = get_run_by_id(run_id)
        if not existing_run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run with ID {run_id} not found",
            )

        history_record = get_run_version(run_id, version_number)

        if not history_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version_number} not found for run {run_id}",
            )

        return RunHistoryResponse.from_history_record(history_record)

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Error retrieving version {version_number} for run {run_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving run version",
        )


@router.post("/{run_id}/restore/{version_number}", response_model=Dict[str, Any])
def restore_run_to_version(
    run_id: str,
    version_number: int,
    restored_by: str,
    username: str = Depends(verify_oauth_token),
) -> Dict[str, Any]:
    """
    Restore a run to a previous version.

    Requires authentication via HTTP Basic Auth.

    This creates a new version that copies the data from the specified historical version.
    The original version being restored to is preserved in the history.

    Args:
        run_id: The run identifier to restore.
        version_number: The historical version to restore to.
        restored_by: Username or identifier of the requester.
    """
    try:
        # Verify the run exists
        existing_run = get_run_by_id(run_id)
        if not existing_run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run with ID {run_id} not found",
            )

        # Get the historical version to restore to
        historical_version = get_run_version(run_id, version_number)
        if not historical_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version_number} not found for run {run_id}",
            )

        # Build updates from the historical version
        # Only include fields that can be updated (not source, etc.)
        updates = {
            "distance": historical_version.distance,
            "duration": historical_version.duration,
            "type": historical_version.type,
            "avg_heart_rate": historical_version.avg_heart_rate,
            "shoe_id": historical_version.shoe_id,
            "datetime_utc": historical_version.datetime_utc,
        }

        # Perform the restoration with history tracking
        update_run_with_history(
            run_id=run_id,
            updates=updates,
            changed_by=restored_by,
            change_reason=f"Restored to version {version_number}",
        )

        logger.info(
            f"Successfully restored run {run_id} to version {version_number} by {restored_by}"
        )

        # Return the updated run
        updated_run = get_run_by_id(run_id)
        return {
            "status": "success",
            "message": f"Run {run_id} restored to version {version_number}",
            "run": updated_run.model_dump() if updated_run else None,
            "restored_from_version": version_number,
            "restored_at": datetime.now().isoformat(),
            "restored_by": restored_by,
        }

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Error restoring run {run_id} to version {version_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred during restoration",
        )
