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
    sessions_in_period: int
    volume_in_period_kg: float


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

    # Period-specific stats
    if start_date or end_date:
        period_lifts = get_lifts_in_date_range(start_date, end_date)
    else:
        period_lifts = all_lifts

    return LiftStatsResponse(
        total_sessions=total_sessions,
        total_volume_kg=total_volume,
        total_sets=total_sets,
        sessions_in_period=len(period_lifts),
        volume_in_period_kg=sum(lift.total_volume() for lift in period_lifts),
    )


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
