"""Google Calendar sync routes for run workouts."""

import logging
from typing import List

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
from fitness.integrations.google.calendar_client import GoogleCalendarClient
from fitness.app.auth import require_viewer, require_editor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


# Static routes must be registered before parameterized routes to avoid
# path parameters like {run_workout_id} matching "failed".


@router.get("/run-workouts", response_model=List[SyncedRunWorkout])
def get_all_run_workout_sync_records(
    _user: User = Depends(require_viewer),
) -> List[SyncedRunWorkout]:
    """Get all run workout sync records for debugging/admin purposes."""
    return get_all_synced_run_workouts()


@router.get("/run-workouts/failed", response_model=List[SyncedRunWorkout])
def get_failed_run_workout_sync_records(
    _user: User = Depends(require_viewer),
) -> List[SyncedRunWorkout]:
    """Get all run workouts with failed sync status for retry/debugging."""
    return get_failed_run_workout_syncs()


@router.get("/run-workouts/{run_workout_id}/status", response_model=SyncRunWorkoutStatusResponse)
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
    runs = []
    for rid in run_ids:
        run = get_run_by_id(rid)
        if run is not None:
            runs.append(run)

    if len(runs) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Run workout {run_workout_id} has fewer than 2 valid runs",
        )

    try:
        calendar_client = GoogleCalendarClient()
        google_event_id = calendar_client.create_run_workout_event(workout, runs)

        if google_event_id is None:
            raise Exception("Failed to create Google Calendar event")

        if existing_sync:
            updated_sync = update_synced_run_workout(
                run_workout_id=run_workout_id,
                google_event_id=google_event_id,
                sync_status="synced",
                clear_error_message=True,
            )
            if updated_sync is None:
                raise HTTPException(
                    status_code=500, detail="Failed to update sync record"
                )
            synced = updated_sync
        else:
            synced = create_synced_run_workout(
                run_workout_id=run_workout_id,
                google_event_id=google_event_id,
                run_workout_version=1,
                sync_status="synced",
            )

        logger.info(
            f"Successfully synced run workout {run_workout_id} to Google Calendar event {google_event_id}"
        )

        return SyncResponse(
            success=True,
            message=f"Successfully synced run workout {run_workout_id} to Google Calendar",
            google_event_id=synced.google_event_id,
            sync_status=synced.sync_status,
            synced_at=synced.synced_at,
        )

    except Exception as e:
        error_msg = f"Failed to sync run workout {run_workout_id}: {str(e)}"
        logger.exception(
            f"Error syncing run workout to Google Calendar: run_workout_id={run_workout_id}, "
            f"exception_type={type(e).__name__}, error={str(e)}"
        )

        try:
            if existing_sync:
                update_synced_run_workout(
                    run_workout_id=run_workout_id,
                    sync_status="failed",
                    error_message=error_msg,
                )
            else:
                create_synced_run_workout(
                    run_workout_id=run_workout_id,
                    google_event_id=None,
                    sync_status="failed",
                    error_message=error_msg,
                )
        except Exception as db_error:
            logger.exception(
                f"Failed to persist sync failure to database: run_workout_id={run_workout_id}, "
                f"exception_type={type(db_error).__name__}, error={str(db_error)}"
            )

        return SyncResponse(
            success=False,
            message=error_msg,
            google_event_id=None,
            sync_status="failed",
            synced_at=None,
        )


@router.delete("/run-workouts/{run_workout_id}", response_model=SyncResponse)
def unsync_run_workout_from_calendar(
    run_workout_id: str,
    user: User = Depends(require_editor),
) -> SyncResponse:
    """Remove a run workout's sync from Google Calendar."""
    synced = get_synced_run_workout(run_workout_id)

    if synced is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run workout {run_workout_id} is not currently synced",
        )

    try:
        if not synced.google_event_id or synced.sync_status != "synced":
            deleted = delete_synced_run_workout(run_workout_id)
            if deleted:
                logger.info(
                    f"Removed local sync record for run workout {run_workout_id} without Google deletion"
                )
                return SyncResponse(
                    success=True,
                    message=f"Removed sync record for run workout {run_workout_id}",
                    google_event_id=None,
                    sync_status="unsynced",
                    synced_at=None,
                )
            else:
                raise Exception("Failed to delete sync record from database")

        calendar_client = GoogleCalendarClient()
        success = calendar_client.delete_workout_event(synced.google_event_id)

        if not success:
            raise Exception(
                f"Failed to delete Google Calendar event {synced.google_event_id}"
            )

        deleted = delete_synced_run_workout(run_workout_id)

        if deleted:
            logger.info(f"Successfully unsynced run workout {run_workout_id} from Google Calendar")
            return SyncResponse(
                success=True,
                message=f"Successfully removed sync for run workout {run_workout_id}",
                google_event_id=synced.google_event_id,
                sync_status="unsynced",
                synced_at=None,
            )
        else:
            raise Exception("Failed to delete sync record from database")

    except Exception as e:
        error_msg = f"Failed to unsync run workout {run_workout_id}: {str(e)}"
        logger.exception(
            f"Error unsyncing run workout from Google Calendar: run_workout_id={run_workout_id}, "
            f"google_event_id={synced.google_event_id if synced else None}, "
            f"exception_type={type(e).__name__}, error={str(e)}"
        )

        return SyncResponse(
            success=False,
            message=error_msg,
            google_event_id=synced.google_event_id,
            sync_status=synced.sync_status,
            synced_at=synced.synced_at,
        )
