"""RideDetail model — Ride enriched with Google Calendar sync status."""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from fitness.models.ride import RideType, RideSource
from fitness.models.sync import SyncStatus


class RideDetail(BaseModel):
    """A Ride enriched with sync status, suitable for the activity feed.

    Mirrors RunDetail in shape (minus shoes / version / workout-id, which
    rides don't carry in v1).
    """

    id: str
    datetime_utc: datetime
    type: RideType
    distance: float
    duration: float
    source: RideSource
    avg_heart_rate: float | None = None
    deleted_at: datetime | None = None
    # Set when this ride was marked as a duplicate of another ride (the kept one).
    duplicate_of_id: str | None = None

    # Sync info (joined from `synced_rides`).
    is_synced: bool = False
    sync_status: Optional[SyncStatus] = None
    synced_at: Optional[datetime] = None
    google_event_id: Optional[str] = None
    synced_version: Optional[int] = None
    error_message: Optional[str] = None

    def model_dump(self, **kwargs) -> dict:
        """Override to add a derived `date` field for parity with Run/RunDetail."""
        data = super().model_dump(**kwargs)
        data["date"] = (
            self.datetime_utc.date() if self.datetime_utc is not None else None
        )
        return data
