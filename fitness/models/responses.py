"""Shared API response models."""

from datetime import datetime

from pydantic import BaseModel, Field


class DataImportResponse(BaseModel):
    """Response model for data import operations (Strava, MMF, etc.)."""

    inserted_count: int = Field(description="Number of runs inserted")
    updated_at: datetime = Field(description="When the import occurred")
    message: str = Field(description="Human-readable status message")
    total_runs_found: int | None = Field(
        default=None, description="Total runs found in source data"
    )
    existing_runs: int | None = Field(
        default=None, description="Number of runs that already existed"
    )
