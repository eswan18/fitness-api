"""Generic router for lifting workout data."""

import logging
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from fitness.app.auth import require_viewer
from fitness.models.user import User
from fitness.models.lift import Lift
from fitness.db.lifts import (
    get_all_lifts,
    get_lifts_in_date_range,
    get_lift_by_id,
    get_lift_count,
    get_all_exercise_templates,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lifts", tags=["lifts"])


# --- Response Models ---


class LiftSummary(BaseModel):
    """Summary of a lifting session for list responses."""

    id: str
    title: str
    start_time: datetime
    end_time: datetime
    total_volume_kg: float
    total_sets: int
    exercise_count: int


class LiftsResponse(BaseModel):
    """Response containing list of lifts."""

    lifts: list[LiftSummary]
    total_count: int


class LiftStatsResponse(BaseModel):
    """Aggregated stats for lifting sessions."""

    total_sessions: int
    total_volume_kg: float
    total_sets: int
    duration_all_time_seconds: int
    sessions_in_period: int
    volume_in_period_kg: float
    sets_in_period: int
    duration_in_period_seconds: int
    avg_duration_seconds: int


class SetsByMuscleItem(BaseModel):
    """Sets count for a single muscle group."""

    muscle: str
    sets: int


class FrequentExerciseItem(BaseModel):
    """An exercise with its occurrence count."""

    name: str
    count: int


# --- Endpoints ---


@router.get("", response_model=LiftsResponse)
async def get_lifts(
    start_date: Optional[date] = Query(None, description="Filter lifts on or after this date"),
    end_date: Optional[date] = Query(None, description="Filter lifts before this date"),
    _user: User = Depends(require_viewer),
) -> LiftsResponse:
    """Get lifting sessions from the database.

    Optionally filter by date range. Either, both, or neither date can be provided.
    Returns lifts in descending order by start time.
    """
    if start_date or end_date:
        lifts = get_lifts_in_date_range(start_date, end_date)
    else:
        lifts = get_all_lifts()

    summaries = [
        LiftSummary(
            id=lift.id,
            title=lift.title,
            start_time=lift.start_time,
            end_time=lift.end_time,
            total_volume_kg=lift.total_volume(),
            total_sets=lift.total_sets(),
            exercise_count=len(lift.exercises),
        )
        for lift in lifts
    ]

    return LiftsResponse(
        lifts=summaries,
        total_count=len(summaries),
    )


@router.get("/count")
async def get_lifts_count(
    _user: User = Depends(require_viewer),
) -> dict[str, int]:
    """Get the total count of lifting sessions in the database."""
    count = get_lift_count()
    return {"count": count}


@router.get("/stats", response_model=LiftStatsResponse)
async def get_lifts_stats(
    start_date: Optional[date] = Query(None, description="Filter stats on or after this date"),
    end_date: Optional[date] = Query(None, description="Filter stats before this date"),
    _user: User = Depends(require_viewer),
) -> LiftStatsResponse:
    """Get aggregated statistics for lifting sessions.

    Either, both, or neither date can be provided for period filtering.
    """
    all_lifts = get_all_lifts()
    total_sessions = len(all_lifts)
    total_volume = sum(lift.total_volume() for lift in all_lifts)
    total_sets = sum(lift.total_sets() for lift in all_lifts)
    duration_all_time = sum(lift.duration_seconds() for lift in all_lifts)

    # Period-specific stats
    if start_date or end_date:
        period_lifts = get_lifts_in_date_range(start_date, end_date)
    else:
        period_lifts = all_lifts

    duration_in_period = sum(lift.duration_seconds() for lift in period_lifts)
    avg_duration = duration_in_period // len(period_lifts) if period_lifts else 0

    return LiftStatsResponse(
        total_sessions=total_sessions,
        total_volume_kg=total_volume,
        total_sets=total_sets,
        duration_all_time_seconds=duration_all_time,
        sessions_in_period=len(period_lifts),
        volume_in_period_kg=sum(lift.total_volume() for lift in period_lifts),
        sets_in_period=sum(lift.total_sets() for lift in period_lifts),
        duration_in_period_seconds=duration_in_period,
        avg_duration_seconds=avg_duration,
    )


@router.get("/sets-by-muscle", response_model=list[SetsByMuscleItem])
async def get_sets_by_muscle(
    start_date: Optional[date] = Query(None, description="Filter on or after this date"),
    end_date: Optional[date] = Query(None, description="Filter before this date"),
    _user: User = Depends(require_viewer),
) -> list[SetsByMuscleItem]:
    """Get sets grouped by primary muscle group.

    Returns non-warmup sets counted by muscle group for the given period.
    """
    # Get lifts in period
    if start_date or end_date:
        lifts = get_lifts_in_date_range(start_date, end_date)
    else:
        lifts = get_all_lifts()

    # Build template lookup for muscle groups
    templates = get_all_exercise_templates()
    template_muscle_map = {t.id: t.primary_muscle_group for t in templates}

    # Count sets by muscle group
    muscle_sets: dict[str, int] = {}
    for lift in lifts:
        for exercise in lift.exercises:
            muscle = template_muscle_map.get(exercise.exercise_template_id)
            if muscle:
                # Count non-warmup sets
                non_warmup = sum(1 for s in exercise.sets if s.set_type != "warmup")
                muscle_sets[muscle] = muscle_sets.get(muscle, 0) + non_warmup

    # Sort by sets descending
    sorted_muscles = sorted(muscle_sets.items(), key=lambda x: x[1], reverse=True)

    return [SetsByMuscleItem(muscle=m, sets=s) for m, s in sorted_muscles]


@router.get("/frequent-exercises", response_model=list[FrequentExerciseItem])
async def get_frequent_exercises(
    start_date: Optional[date] = Query(None, description="Filter on or after this date"),
    end_date: Optional[date] = Query(None, description="Filter before this date"),
    limit: int = Query(5, description="Number of exercises to return", ge=1, le=20),
    _user: User = Depends(require_viewer),
) -> list[FrequentExerciseItem]:
    """Get most frequently performed exercises in the period.

    Returns exercises sorted by occurrence count.
    """
    # Get lifts in period
    if start_date or end_date:
        lifts = get_lifts_in_date_range(start_date, end_date)
    else:
        lifts = get_all_lifts()

    # Count exercise occurrences
    exercise_counts: dict[str, int] = {}
    for lift in lifts:
        for exercise in lift.exercises:
            name = exercise.title
            exercise_counts[name] = exercise_counts.get(name, 0) + 1

    # Sort by count descending and limit
    sorted_exercises = sorted(exercise_counts.items(), key=lambda x: x[1], reverse=True)
    top_exercises = sorted_exercises[:limit]

    return [FrequentExerciseItem(name=name, count=count) for name, count in top_exercises]


@router.get("/{lift_id}")
async def get_lift(
    lift_id: str,
    _user: User = Depends(require_viewer),
) -> Lift:
    """Get a single lifting session by ID with full exercise details."""
    lift = get_lift_by_id(lift_id)
    if lift is None:
        raise HTTPException(status_code=404, detail=f"Lift {lift_id} not found")
    return lift
