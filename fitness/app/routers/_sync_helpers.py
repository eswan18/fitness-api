"""Shared helpers for Google Calendar sync routers.

Extracts the common sync/unsync/error-handling logic used identically
by sync.py (runs), lift_sync.py (lifts), and run_workout_sync.py (run workouts).
"""

import logging
from typing import Any, Callable

from fastapi import HTTPException, status

from fitness.models.sync import SyncResponse
from fitness.integrations.google.calendar_client import GoogleCalendarClient

logger = logging.getLogger(__name__)


def perform_sync(
    *,
    entity_id: str,
    entity_type: str,
    existing_sync: Any,
    create_calendar_event: Callable[[GoogleCalendarClient], str | None],
    create_sync_record: Callable[[str, str], Any],
    update_sync_record: Callable[[str], Any],
    record_failure: Callable[[str | None, str], None],
) -> SyncResponse:
    """Sync an entity to Google Calendar.

    Args:
        entity_id: ID of the entity being synced.
        entity_type: Human-readable type name for messages (e.g. "run", "lift").
        existing_sync: Existing sync record, or None if not yet synced.
        create_calendar_event: Creates the Google Calendar event. Receives a
            GoogleCalendarClient and returns the google_event_id, or None on failure.
        create_sync_record: Called on success when no prior sync exists.
            Receives (google_event_id, sync_status) and returns the new record.
        update_sync_record: Called on success when updating a prior failed sync.
            Receives google_event_id and returns the updated record, or None.
        record_failure: Called to persist a failure. Receives
            (google_event_id_or_none, error_message).
    """
    if existing_sync and existing_sync.sync_status == "synced":
        return SyncResponse(
            success=False,
            message=f"{entity_type.capitalize()} {entity_id} is already synced to Google Calendar",
            google_event_id=existing_sync.google_event_id,
            sync_status=existing_sync.sync_status,
            synced_at=existing_sync.synced_at,
        )

    try:
        calendar_client = GoogleCalendarClient()
        google_event_id = create_calendar_event(calendar_client)

        if google_event_id is None:
            raise Exception("Failed to create Google Calendar event")

        if existing_sync:
            updated = update_sync_record(google_event_id)
            if updated is None:
                raise HTTPException(
                    status_code=500, detail="Failed to update sync record"
                )
            synced = updated
        else:
            synced = create_sync_record(google_event_id, "synced")

        logger.info(
            f"Successfully synced {entity_type} {entity_id} to Google Calendar event {google_event_id}"
        )

        return SyncResponse(
            success=True,
            message=f"Successfully synced {entity_type} {entity_id} to Google Calendar",
            google_event_id=synced.google_event_id,
            sync_status=synced.sync_status,
            synced_at=synced.synced_at,
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        error_msg = f"Failed to sync {entity_type} {entity_id}: {str(e)}"
        logger.exception(
            f"Error syncing {entity_type} to Google Calendar: {entity_type}_id={entity_id}, "
            f"exception_type={type(e).__name__}, error={str(e)}"
        )

        try:
            if existing_sync:
                record_failure(None, error_msg)
                logger.info(
                    f"Updated sync record to 'failed' status for {entity_type} {entity_id}"
                )
            else:
                record_failure("", error_msg)
                logger.info(f"Created failed sync record for {entity_type} {entity_id}")
        except Exception as db_error:
            logger.exception(
                f"Failed to persist sync failure to database: {entity_type}_id={entity_id}, "
                f"exception_type={type(db_error).__name__}, error={str(db_error)}"
            )

        return SyncResponse(
            success=False,
            message=error_msg,
            google_event_id=None,
            sync_status="failed",
            synced_at=None,
        )


def perform_unsync(
    *,
    entity_id: str,
    entity_type: str,
    synced_record: Any,
    delete_sync_record: Callable[[], bool],
) -> SyncResponse:
    """Remove an entity's sync from Google Calendar.

    Args:
        entity_id: ID of the entity being unsynced.
        entity_type: Human-readable type name for messages.
        synced_record: Existing sync record, or None.
        delete_sync_record: Deletes the local sync record. Returns True on success.
    """
    if synced_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity_type.capitalize()} {entity_id} is not currently synced",
        )

    try:
        # If there's no valid event to delete or status isn't 'synced', just remove the record
        if not synced_record.google_event_id or synced_record.sync_status != "synced":
            if not delete_sync_record():
                raise Exception("Failed to delete sync record from database")
            logger.info(
                f"Removed local sync record for {entity_type} {entity_id} without Google deletion"
            )
            return SyncResponse(
                success=True,
                message=f"Removed sync record for {entity_type} {entity_id}",
                google_event_id=None,
                sync_status="unsynced",
                synced_at=None,
            )

        # Delete from Google then remove local record
        calendar_client = GoogleCalendarClient()
        success = calendar_client.delete_workout_event(synced_record.google_event_id)

        if not success:
            raise Exception(
                f"Failed to delete Google Calendar event {synced_record.google_event_id}"
            )

        if not delete_sync_record():
            raise Exception("Failed to delete sync record from database")

        logger.info(
            f"Successfully unsynced {entity_type} {entity_id} from Google Calendar"
        )
        return SyncResponse(
            success=True,
            message=f"Successfully removed sync for {entity_type} {entity_id}",
            google_event_id=synced_record.google_event_id,
            sync_status="unsynced",
            synced_at=None,
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        error_msg = f"Failed to unsync {entity_type} {entity_id}: {str(e)}"
        logger.exception(
            f"Error unsyncing {entity_type} from Google Calendar: {entity_type}_id={entity_id}, "
            f"google_event_id={synced_record.google_event_id if synced_record else None}, "
            f"exception_type={type(e).__name__}, error={str(e)}"
        )

        return SyncResponse(
            success=False,
            message=error_msg,
            google_event_id=synced_record.google_event_id,
            sync_status=synced_record.sync_status,
            synced_at=synced_record.synced_at,
        )
