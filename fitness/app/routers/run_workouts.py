"""CRUD routes for run workouts and the unified activity feed."""

import logging
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from fitness.app.auth import require_viewer, require_editor
from fitness.models.user import User
from fitness.models.run_detail import RunDetail
from fitness.models.run_workout import RunWorkout, RunWorkoutDetail
from fitness.db.run_workouts import (
    create_run_workout,
    get_run_workout_by_id,
    get_run_workouts_by_ids,
    get_all_run_workouts,
    update_run_workout,
    set_run_workout_runs,
    delete_run_workout,
    get_run_ids_for_workout,
)
from fitness.db.runs import (
    get_all_run_details,
    get_run_details_by_ids,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/run-workouts", tags=["run-workouts"])


# --- Request Models ---


class CreateRunWorkoutRequest(BaseModel):
    title: str
    notes: Optional[str] = None
    run_ids: list[str]

    @field_validator("run_ids")
    @classmethod
    def validate_run_ids(cls, v: list[str]) -> list[str]:
        if len(v) < 2:
            raise ValueError("A run workout must contain at least 2 runs")
        return v


class UpdateRunWorkoutRequest(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None


class SetRunWorkoutRunsRequest(BaseModel):
    run_ids: list[str]

    @field_validator("run_ids")
    @classmethod
    def validate_run_ids(cls, v: list[str]) -> list[str]:
        if len(v) < 2:
            raise ValueError("A run workout must contain at least 2 runs")
        return v


# --- Response Models ---


class RunWorkoutSummary(BaseModel):
    """For list endpoints — no nested runs."""

    id: str
    title: str
    notes: Optional[str] = None
    run_count: int
    total_distance: float
    total_duration: float
    start_datetime_utc: Optional[datetime] = None
    created_at: Optional[datetime] = None


class RunWorkoutDetailResponse(BaseModel):
    """For single-workout GET — includes nested runs."""

    id: str
    title: str
    notes: Optional[str] = None
    start_datetime_utc: Optional[datetime] = None
    total_distance: float
    total_duration: float
    elapsed_seconds: float
    avg_heart_rate: Optional[float] = None
    run_count: int
    runs: list[RunDetail]
    created_at: Optional[datetime] = None


# --- Activity Feed Models ---


class ActivityFeedRunItem(BaseModel):
    type: Literal["run"] = "run"
    item: RunDetail


class ActivityFeedWorkoutItem(BaseModel):
    type: Literal["run_workout"] = "run_workout"
    item: RunWorkoutDetail


# --- CRUD Endpoints ---


@router.post("", status_code=201, response_model=RunWorkoutDetailResponse)
async def create_workout(
    request: CreateRunWorkoutRequest,
    _user: User = Depends(require_editor),
) -> RunWorkoutDetailResponse:
    """Create a new run workout grouping multiple runs."""
    try:
        workout = create_run_workout(
            title=request.title,
            run_ids=request.run_ids,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _build_workout_detail_response(workout)


@router.get("", response_model=list[RunWorkoutSummary])
async def list_workouts(
    _user: User = Depends(require_viewer),
) -> list[RunWorkoutSummary]:
    """List all run workouts with summary stats."""
    workouts = get_all_run_workouts()
    all_details = get_all_run_details()
    return [_build_workout_summary(w, all_details) for w in workouts]


@router.get("/{workout_id}", response_model=RunWorkoutDetailResponse)
async def get_workout(
    workout_id: str,
    _user: User = Depends(require_viewer),
) -> RunWorkoutDetailResponse:
    """Get a single run workout with full details and nested runs."""
    workout = get_run_workout_by_id(workout_id)
    if workout is None:
        raise HTTPException(status_code=404, detail=f"Run workout {workout_id} not found")
    return _build_workout_detail_response(workout)


@router.patch("/{workout_id}", response_model=RunWorkoutDetailResponse)
async def patch_workout(
    workout_id: str,
    request: UpdateRunWorkoutRequest,
    _user: User = Depends(require_editor),
) -> RunWorkoutDetailResponse:
    """Update a run workout's title and/or notes."""
    if request.title is None and request.notes is None:
        raise HTTPException(status_code=400, detail="No fields to update")

    workout = update_run_workout(
        workout_id,
        title=request.title,
        notes=request.notes,
    )
    if workout is None:
        raise HTTPException(status_code=404, detail=f"Run workout {workout_id} not found")
    return _build_workout_detail_response(workout)


@router.put("/{workout_id}/runs", response_model=RunWorkoutDetailResponse)
async def replace_workout_runs(
    workout_id: str,
    request: SetRunWorkoutRunsRequest,
    _user: User = Depends(require_editor),
) -> RunWorkoutDetailResponse:
    """Replace the set of runs in a workout."""
    try:
        set_run_workout_runs(workout_id, request.run_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    workout = get_run_workout_by_id(workout_id)
    if workout is None:
        raise HTTPException(status_code=404, detail=f"Run workout {workout_id} not found")
    return _build_workout_detail_response(workout)


@router.delete("/{workout_id}", status_code=200)
async def remove_workout(
    workout_id: str,
    _user: User = Depends(require_editor),
) -> dict[str, str]:
    """Soft-delete a run workout and unlink its runs."""
    deleted = delete_run_workout(workout_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Run workout {workout_id} not found")
    return {"message": f"Run workout {workout_id} deleted"}


def build_activity_feed(
    all_runs: list[RunDetail],
    sort_order: str = "desc",
) -> list[ActivityFeedRunItem | ActivityFeedWorkoutItem]:
    """Build a unified activity feed from a list of run details.

    Partitions runs into solo runs and workout-grouped runs, computes
    workout aggregates, and returns a sorted feed.
    """
    # Partition into solo runs and workout-grouped runs
    solo_runs: list[RunDetail] = []
    workout_runs: dict[str, list[RunDetail]] = {}
    for run in all_runs:
        if run.run_workout_id:
            workout_runs.setdefault(run.run_workout_id, []).append(run)
        else:
            solo_runs.append(run)

    # Build feed items
    feed: list[ActivityFeedRunItem | ActivityFeedWorkoutItem] = []

    # Add solo runs
    for run in solo_runs:
        feed.append(ActivityFeedRunItem(item=run))

    # Batch-fetch all referenced workouts to avoid N+1 queries
    workouts_by_id = get_run_workouts_by_ids(list(workout_runs.keys()))

    # Add workouts
    for workout_id, runs in workout_runs.items():
        workout = workouts_by_id.get(workout_id)
        if workout is None:
            # Workout was deleted but runs still have FK — treat as solo
            for run in runs:
                feed.append(ActivityFeedRunItem(item=run))
            continue

        detail = _compute_workout_detail(workout, runs)
        feed.append(ActivityFeedWorkoutItem(item=detail))

    # Sort by effective datetime
    def sort_key(
        item: ActivityFeedRunItem | ActivityFeedWorkoutItem,
    ) -> datetime:
        if isinstance(item, ActivityFeedRunItem):
            return item.item.datetime_utc
        return item.item.start_datetime_utc

    reverse = sort_order == "desc"
    feed.sort(key=sort_key, reverse=reverse)

    return feed


# --- Helpers ---


def _build_workout_summary(
    workout: RunWorkout, all_details: list[RunDetail]
) -> RunWorkoutSummary:
    """Build a summary response for a workout from pre-fetched run details."""
    run_ids = get_run_ids_for_workout(workout.id)
    runs = [r for r in all_details if r.id in set(run_ids)]
    runs.sort(key=lambda r: r.datetime_utc)

    return RunWorkoutSummary(
        id=workout.id,
        title=workout.title,
        notes=workout.notes,
        run_count=len(runs),
        total_distance=sum(r.distance for r in runs),
        total_duration=sum(r.duration for r in runs),
        start_datetime_utc=runs[0].datetime_utc if runs else None,
        created_at=workout.created_at,
    )


def _build_workout_detail_response(
    workout: RunWorkout,
) -> RunWorkoutDetailResponse:
    """Build a detail response for a workout by querying its runs."""
    run_ids = get_run_ids_for_workout(workout.id)
    runs = get_run_details_by_ids(run_ids)
    runs.sort(key=lambda r: r.datetime_utc)

    if not runs:
        return RunWorkoutDetailResponse(
            id=workout.id,
            title=workout.title,
            notes=workout.notes,
            start_datetime_utc=None,
            total_distance=0.0,
            total_duration=0.0,
            elapsed_seconds=0.0,
            avg_heart_rate=None,
            run_count=0,
            runs=[],
            created_at=workout.created_at,
        )

    total_distance = sum(r.distance for r in runs)
    total_duration = sum(r.duration for r in runs)
    elapsed = _compute_elapsed_seconds(runs)
    avg_hr = _compute_weighted_avg_hr(runs)

    return RunWorkoutDetailResponse(
        id=workout.id,
        title=workout.title,
        notes=workout.notes,
        start_datetime_utc=runs[0].datetime_utc,
        total_distance=total_distance,
        total_duration=total_duration,
        elapsed_seconds=elapsed,
        avg_heart_rate=avg_hr,
        run_count=len(runs),
        runs=runs,
        created_at=workout.created_at,
    )


def _compute_workout_detail(
    workout: RunWorkout, runs: list[RunDetail]
) -> RunWorkoutDetail:
    """Compute aggregated RunWorkoutDetail from a workout and its runs."""
    runs.sort(key=lambda r: r.datetime_utc)

    total_distance = sum(r.distance for r in runs)
    total_duration = sum(r.duration for r in runs)
    elapsed = _compute_elapsed_seconds(runs)
    avg_hr = _compute_weighted_avg_hr(runs)

    return RunWorkoutDetail(
        id=workout.id,
        title=workout.title,
        notes=workout.notes,
        start_datetime_utc=runs[0].datetime_utc,
        total_distance=total_distance,
        total_duration=total_duration,
        elapsed_seconds=elapsed,
        avg_heart_rate=avg_hr,
        run_count=len(runs),
        runs=runs,
        created_at=workout.created_at,
        deleted_at=workout.deleted_at,
    )


def _compute_elapsed_seconds(runs: list[RunDetail]) -> float:
    """Elapsed time from first run's start to last run's end."""
    if not runs:
        return 0.0
    first_start = runs[0].datetime_utc
    last_run = runs[-1]
    from datetime import timedelta

    last_end = last_run.datetime_utc + timedelta(seconds=last_run.duration)
    return (last_end - first_start).total_seconds()


def _compute_weighted_avg_hr(runs: list[RunDetail]) -> Optional[float]:
    """Duration-weighted average heart rate across runs."""
    total_weighted = 0.0
    total_duration = 0.0
    for run in runs:
        if run.avg_heart_rate is not None:
            total_weighted += run.avg_heart_rate * run.duration
            total_duration += run.duration
    if total_duration == 0:
        return None
    return round(total_weighted / total_duration, 1)
