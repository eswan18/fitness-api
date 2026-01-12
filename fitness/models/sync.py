"""Models for Google Calendar sync functionality."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


SyncStatus = Literal["synced", "failed", "pending"]


class SyncedRun(BaseModel):
    """Represents a run that has been synced to Google Calendar."""

    id: int
    run_id: str
    run_version: int = Field(
        default=1, description="Version of the run that was synced"
    )
    google_event_id: str = Field(description="Google Calendar event ID")
    synced_at: datetime = Field(description="When the sync occurred")
    sync_status: SyncStatus = Field(default="synced")
    error_message: Optional[str] = Field(
        default=None, description="Error message if sync failed"
    )
    created_at: datetime
    updated_at: datetime


class SyncRequest(BaseModel):
    """Request to sync a run to Google Calendar."""

    run_id: str = Field(description="ID of the run to sync")


class SyncResponse(BaseModel):
    """Response from syncing a run to Google Calendar."""

    success: bool = Field(description="Whether the sync was successful")
    message: str = Field(description="Human-readable status message")
    google_event_id: Optional[str] = Field(
        default=None, description="Google Calendar event ID if successful"
    )
    sync_status: SyncStatus = Field(description="Current sync status")
    synced_at: Optional[datetime] = Field(
        default=None, description="When sync occurred if successful"
    )


class SyncStatusResponse(BaseModel):
    """Response containing the sync status of a run."""

    run_id: str = Field(description="ID of the run")
    is_synced: bool = Field(description="Whether the run is currently synced")
    sync_status: Optional[SyncStatus] = Field(
        default=None, description="Sync status if synced"
    )
    synced_at: Optional[datetime] = Field(
        default=None, description="When sync occurred if synced"
    )
    google_event_id: Optional[str] = Field(
        default=None, description="Google Calendar event ID if synced"
    )
    run_version: Optional[int] = Field(
        default=None, description="Version that was synced"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if sync failed"
    )
