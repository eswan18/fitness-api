"""Models for run workouts — groups of runs that form a single training session."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from fitness.models.run_detail import RunDetail
from fitness.models.sync import SyncStatus


class RunWorkout(BaseModel):
    """A run workout grouping multiple runs into a single session."""

    id: str
    title: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class RunWorkoutDetail(BaseModel):
    """A run workout with computed aggregates and nested runs."""

    id: str
    title: str
    notes: Optional[str] = None
    start_datetime_utc: datetime
    total_distance: float  # miles
    total_duration: float  # seconds
    elapsed_seconds: float  # last end - first start
    avg_heart_rate: Optional[float] = None  # duration-weighted average
    run_count: int
    runs: list[RunDetail]
    is_synced: bool = False
    sync_status: Optional[SyncStatus] = None
    google_event_id: Optional[str] = None
    created_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
