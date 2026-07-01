from __future__ import annotations
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .run import RunType, RunSource
from .sync import SyncStatus
from .tag import Tag


class RunDetail(BaseModel):
    """A run with shoe information and Google Calendar sync status."""

    # Base run fields
    id: str
    datetime_utc: datetime
    type: RunType
    distance: float  # in miles
    duration: float  # in seconds
    source: RunSource
    avg_heart_rate: Optional[float] = None
    shoe_id: Optional[str] = None
    shoes: Optional[str] = None
    shoe_retirement_notes: Optional[str] = None
    notes: Optional[str] = None  # User-authored markdown note on the run
    name: Optional[str] = None  # User-authored display name on the run
    tags: list[Tag] = Field(default_factory=list)
    deleted_at: Optional[datetime] = None
    # Set when this run was marked as a duplicate of another run (the kept one).
    duplicate_of_id: Optional[str] = None
    version: Optional[int] = None
    run_workout_id: Optional[str] = None

    # Sync information (from synced_runs)
    is_synced: bool = False
    sync_status: Optional[SyncStatus] = None
    synced_at: Optional[datetime] = None
    google_event_id: Optional[str] = None
    synced_version: Optional[int] = None
    error_message: Optional[str] = None
