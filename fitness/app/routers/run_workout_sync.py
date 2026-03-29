"""Google Calendar sync routes for run workouts."""

import logging

from fastapi import APIRouter, HTTPException, status, Depends

from fitness.db.run_workouts import get_run_workout_by_id, get_run_ids_for_workout
from fitness.db.runs import get_run_by_id
from fitness.db.synced_run_workouts import (
    get_synced_run_workout,
    create_synced_run_workout,
    update_synced_run_workout,
    delete_synced_run_workout,
    get_all_synced_run_workouts,
    get_failed_run_workout_syncs,
)
from fitness.models.sync import (
    SyncedRunWorkout,
    SyncResponse,
    SyncRunWorkoutStatusResponse,
)
from fitness.models.user import User
from fitness.app.auth import require_viewer, require_editor
from ._sync_helpers import perform_sync, perform_unsync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


# Static routes must be registered before parameterized routes to avoid
# path parameters like {run_workout_id} matching "failed".


@router.get("/run-workouts", response_model=list[SyncedRunWorkout])
def get_all_run_workout_sync_records(
    _user: User = Depends(require_viewer),
) -> list[SyncedRunWorkout]:
    """Get all run workout sync records for debugging/admin purposes."""
    return get_all_synced_run_workouts()


@router.get("/run-workouts/failed", response_model=list[SyncedRunWorkout])
def get_failed_run_workout_sync_records(
    _user: User = Depends(require_viewer),
) -> list[SyncedRunWorkout]:
    """Get all run workouts with failed sync status for retry/debugging."""
    return get_failed_run_workout_syncs()


@router.get(
    "/run-workouts/{run_workout_id}/status", response_model=SyncRunWorkoutStatusResponse
)
def get_run_workout_sync_status(
    run_workout_id: str,
    _user: User = Depends(require_viewer),
) -> SyncRunWorkoutStatusResponse:
    """Get the Google Calendar sync status for a specific run workout."""
    synced = get_synced_run_workout(run_workout_id)

    if synced is None:
        return SyncRunWorkoutStatusResponse(
            run_workout_id=run_workout_id,
            is_synced=False,
            sync_status=None,
            synced_at=None,
            google_event_id=None,
            run_workout_version=None,
            error_message=None,
        )

    return SyncRunWorkoutStatusResponse(
        run_workout_id=run_workout_id,
        is_synced=synced.sync_status == "synced",
        sync_status=synced.sync_status,
        synced_at=synced.synced_at,
        google_event_id=synced.google_event_id or None,
        run_workout_version=synced.run_workout_version,
        error_message=synced.error_message,
    )


@router.post("/run-workouts/{run_workout_id}", response_model=SyncResponse)
def sync_run_workout_to_calendar(
    run_workout_id: str,
    user: User = Depends(require_editor),
) -> SyncResponse:
    """Sync a run workout to Google Calendar as a single event."""
    existing_sync = get_synced_run_workout(run_workout_id)
    if existing_sync and existing_sync.sync_status == "synced":
        return SyncResponse(
            success=False,
            message=f"Run workout {run_workout_id} is already synced to Google Calendar",
            google_event_id=existing_sync.google_event_id,
            sync_status=existing_sync.sync_status,
            synced_at=existing_sync.synced_at,
        )

    workout = get_run_workout_by_id(run_workout_id)
    if workout is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run workout {run_workout_id} not found",
        )

    # Fetch constituent runs
    run_ids = get_run_ids_for_workout(run_workout_id)
    runs = [run for rid in run_ids if (run := get_run_by_id(rid)) is not None]

    if len(runs) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Run workout {run_workout_id} has fewer than 2 valid runs",
        )

    return perform_sync(
        entity_id=run_workout_id,
        entity_type="run workout",
        existing_sync=existing_sync,
        create_calendar_event=lambda client: client.create_run_workout_event(workout, runs),
        create_sync_record=lambda gid, s: create_synced_run_workout(
            run_workout_id=run_workout_id, google_event_id=gid, run_workout_version=1, sync_status=s,
        ),
        update_sync_record=lambda gid: update_synced_run_workout(
            run_workout_id=run_workout_id, google_event_id=gid, sync_status="synced", clear_error_message=True,
        ),
        record_failure=lambda gid, msg: (
            update_synced_run_workout(run_workout_id=run_workout_id, sync_status="failed", error_message=msg)
            if existing_sync
            else create_synced_run_workout(run_workout_id=run_workout_id, google_event_id=gid, sync_status="failed", error_message=msg)
        ),
    )


@router.delete("/run-workouts/{run_workout_id}", response_model=SyncResponse)
def unsync_run_workout_from_calendar(
    run_workout_id: str,
    user: User = Depends(require_editor),
) -> SyncResponse:
    """Remove a run workout's sync from Google Calendar."""
    return perform_unsync(
        entity_id=run_workout_id,
        entity_type="run workout",
        synced_record=get_synced_run_workout(run_workout_id),
        delete_sync_record=lambda: delete_synced_run_workout(run_workout_id),
    )
