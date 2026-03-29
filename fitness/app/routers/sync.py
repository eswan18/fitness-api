"""Google Calendar sync routes."""

from fastapi import APIRouter, HTTPException, status, Depends
import logging

from fitness.db.runs import get_run_by_id
from fitness.db.synced_runs import (
    get_synced_run,
    create_synced_run,
    update_synced_run,
    delete_synced_run,
    get_all_synced_runs,
    get_failed_syncs,
)
from fitness.models.sync import (
    SyncedRun,
    SyncResponse,
    SyncStatusResponse,
)
from fitness.models.user import User
from fitness.app.auth import require_viewer, require_editor
from ._sync_helpers import perform_sync, perform_unsync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/runs/{run_id}/status", response_model=SyncStatusResponse)
def get_sync_status(
    run_id: str,
    _user: User = Depends(require_viewer),
) -> SyncStatusResponse:
    """Get the Google Calendar sync status for a specific run."""
    synced_run = get_synced_run(run_id)

    if synced_run is None:
        return SyncStatusResponse(
            run_id=run_id,
            is_synced=False,
            sync_status=None,
            synced_at=None,
            google_event_id=None,
            run_version=None,
            error_message=None,
        )

    return SyncStatusResponse(
        run_id=run_id,
        is_synced=synced_run.sync_status == "synced",
        sync_status=synced_run.sync_status,
        synced_at=synced_run.synced_at,
        google_event_id=synced_run.google_event_id,
        run_version=synced_run.run_version,
        error_message=synced_run.error_message,
    )


@router.post("/runs/{run_id}", response_model=SyncResponse)
def sync_run_to_calendar(
    run_id: str,
    user: User = Depends(require_editor),
) -> SyncResponse:
    """Sync a run to Google Calendar. Requires OAuth 2.0 Bearer token."""
    existing_sync = get_synced_run(run_id)

    run = get_run_by_id(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )

    return perform_sync(
        entity_id=run_id,
        entity_type="run",
        existing_sync=existing_sync,
        create_calendar_event=lambda client: client.create_workout_event(run),
        create_sync_record=lambda gid, s: create_synced_run(
            run_id=run_id, google_event_id=gid, run_version=1, sync_status=s,
        ),
        update_sync_record=lambda gid: update_synced_run(
            run_id=run_id, google_event_id=gid, sync_status="synced", clear_error_message=True,
        ),
        record_failure=lambda gid, msg: (
            update_synced_run(run_id=run_id, sync_status="failed", error_message=msg)
            if existing_sync
            else create_synced_run(run_id=run_id, google_event_id=gid or "", sync_status="failed", error_message=msg)
        ),
    )


@router.delete("/runs/{run_id}", response_model=SyncResponse)
def unsync_run_from_calendar(
    run_id: str,
    user: User = Depends(require_editor),
) -> SyncResponse:
    """Remove a run's sync from Google Calendar. Requires OAuth 2.0 Bearer token."""
    return perform_unsync(
        entity_id=run_id,
        entity_type="run",
        synced_record=get_synced_run(run_id),
        delete_sync_record=lambda: delete_synced_run(run_id),
    )


@router.get("/runs", response_model=list[SyncedRun])
def get_all_sync_records(_user: User = Depends(require_viewer)) -> list[SyncedRun]:
    """Get all sync records for debugging/admin purposes."""
    return get_all_synced_runs()


@router.get("/runs/failed", response_model=list[SyncedRun])
def get_failed_sync_records(_user: User = Depends(require_viewer)) -> list[SyncedRun]:
    """Get all runs with failed sync status for retry/debugging."""
    return get_failed_syncs()
