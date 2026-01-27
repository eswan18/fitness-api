"""Hevy API router for weightlifting workout data."""

import os
import logging
from datetime import datetime, timezone, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from fitness.app.auth import require_editor
from fitness.models.user import User
from fitness.integrations.hevy import HevyClient, HevyWorkout, HevyExerciseTemplate
from fitness.db.hevy import (
    get_all_hevy_workouts,
    get_hevy_workouts_in_date_range,
    get_hevy_workout_by_id,
    get_hevy_workout_count,
    bulk_upsert_hevy_workouts,
    get_all_exercise_templates,
    bulk_upsert_exercise_templates,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hevy", tags=["hevy"])


# --- Dependency ---


def hevy_client() -> HevyClient:
    """Get a HevyClient with API key from environment."""
    api_key = os.environ.get("HEVY_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Hevy integration not configured - HEVY_API_KEY not set",
        )
    return HevyClient(api_key=api_key)


# --- Response Models ---


class HevySyncResponse(BaseModel):
    """Response from syncing Hevy data."""

    workouts_synced: int
    templates_synced: int
    message: str
    synced_at: datetime


class HevyWorkoutSummary(BaseModel):
    """Summary of a workout for list responses."""

    id: str
    title: str
    start_time: datetime
    end_time: datetime
    total_volume_kg: float
    total_sets: int
    exercise_count: int


class HevyWorkoutsResponse(BaseModel):
    """Response containing list of workouts."""

    workouts: list[HevyWorkoutSummary]
    total_count: int


class HevyStatsResponse(BaseModel):
    """Aggregated stats for Hevy workouts."""

    total_workouts: int
    total_volume_kg: float
    total_sets: int
    workouts_in_period: int
    volume_in_period_kg: float


# --- Endpoints ---


@router.get("/workouts", response_model=HevyWorkoutsResponse)
async def get_workouts(
    start_date: Optional[date] = Query(None, description="Filter workouts after this date"),
    end_date: Optional[date] = Query(None, description="Filter workouts before this date"),
) -> HevyWorkoutsResponse:
    """Get Hevy workouts from the database.

    Optionally filter by date range. Returns workouts in descending order by start time.
    """
    if start_date and end_date:
        workouts = get_hevy_workouts_in_date_range(start_date, end_date)
    else:
        workouts = get_all_hevy_workouts()

    summaries = [
        HevyWorkoutSummary(
            id=w.id,
            title=w.title,
            start_time=w.start_time,
            end_time=w.end_time,
            total_volume_kg=w.total_volume(),
            total_sets=w.total_sets(),
            exercise_count=len(w.exercises),
        )
        for w in workouts
    ]

    return HevyWorkoutsResponse(
        workouts=summaries,
        total_count=len(summaries),
    )


@router.get("/workouts/{workout_id}")
async def get_workout(workout_id: str) -> HevyWorkout:
    """Get a single Hevy workout by ID with full exercise details."""
    workout = get_hevy_workout_by_id(workout_id)
    if workout is None:
        raise HTTPException(status_code=404, detail=f"Workout {workout_id} not found")
    return workout


@router.get("/stats", response_model=HevyStatsResponse)
async def get_stats(
    start_date: Optional[date] = Query(None, description="Filter stats after this date"),
    end_date: Optional[date] = Query(None, description="Filter stats before this date"),
) -> HevyStatsResponse:
    """Get aggregated statistics for Hevy workouts."""
    all_workouts = get_all_hevy_workouts()
    total_workouts = len(all_workouts)
    total_volume = sum(w.total_volume() for w in all_workouts)
    total_sets = sum(w.total_sets() for w in all_workouts)

    # Period-specific stats
    if start_date and end_date:
        period_workouts = get_hevy_workouts_in_date_range(start_date, end_date)
    else:
        period_workouts = all_workouts

    return HevyStatsResponse(
        total_workouts=total_workouts,
        total_volume_kg=total_volume,
        total_sets=total_sets,
        workouts_in_period=len(period_workouts),
        volume_in_period_kg=sum(w.total_volume() for w in period_workouts),
    )


@router.get("/exercise-templates", response_model=list[HevyExerciseTemplate])
async def get_exercise_templates_endpoint() -> list[HevyExerciseTemplate]:
    """Get all cached exercise templates (for muscle group mapping)."""
    return get_all_exercise_templates()


@router.post("/sync", response_model=HevySyncResponse)
async def sync_hevy_data(
    user: User = Depends(require_editor),
    client: HevyClient = Depends(hevy_client),
) -> HevySyncResponse:
    """Sync workouts and exercise templates from Hevy API.

    Requires authentication. Fetches all workouts and templates from Hevy
    and upserts them into the database.
    """
    logger.info("Starting Hevy sync")

    # Sync exercise templates first (needed for muscle group mapping)
    templates = client.get_all_exercise_templates()
    templates_synced = bulk_upsert_exercise_templates(templates)
    logger.info(f"Synced {templates_synced} exercise templates")

    # Sync workouts
    workouts = client.get_all_workouts()
    workouts_synced = bulk_upsert_hevy_workouts(workouts)
    logger.info(f"Synced {workouts_synced} workouts")

    return HevySyncResponse(
        workouts_synced=workouts_synced,
        templates_synced=templates_synced,
        message=f"Successfully synced {workouts_synced} workouts and {templates_synced} exercise templates",
        synced_at=datetime.now(timezone.utc),
    )


@router.get("/workout-count")
async def get_workout_count() -> dict[str, int]:
    """Get the total count of Hevy workouts in the database."""
    count = get_hevy_workout_count()
    return {"count": count}
