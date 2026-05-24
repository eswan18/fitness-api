"""Shared API response models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


SkippedRunReason = Literal["no_gear_assigned", "gear_fetch_failed"]


class SkippedRun(BaseModel):
    """A run that was deliberately not imported, with a user-facing reason.

    Currently surfaced only by Strava sync when a run is missing usable gear,
    so the user can fix it in Strava and re-import with `?full_sync=true`.
    """

    id: str = Field(description="Provider activity ID (e.g. Strava activity ID)")
    name: str = Field(description="Activity name as reported by the provider")
    reason: SkippedRunReason = Field(description="Why the run was skipped")


class DataImportResponse(BaseModel):
    """Response model for data import operations (Strava, MMF, etc.)."""

    inserted_count: int = Field(
        description="Total number of activities inserted (runs + rides)"
    )
    updated_at: datetime = Field(description="When the import occurred")
    message: str = Field(description="Human-readable status message")
    total_runs_found: int | None = Field(
        default=None, description="Total runs found in source data"
    )
    existing_runs: int | None = Field(
        default=None, description="Number of runs that already existed"
    )
    inserted_runs: int | None = Field(
        default=None, description="Number of runs inserted"
    )
    inserted_rides: int | None = Field(
        default=None, description="Number of rides inserted"
    )
    skipped_runs: list[SkippedRun] = Field(
        default_factory=list,
        description="Runs that were not imported and need user attention",
    )
