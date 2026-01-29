"""Hevy API router for syncing weightlifting workout data from Hevy.

This router only handles sync operations with the Hevy API.
For data access, use the generic /lifts and /exercise-templates endpoints.
"""

import os
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from fitness.app.auth import require_editor
from fitness.models.user import User
from fitness.models.lift import Lift, ExerciseTemplate
from fitness.integrations.hevy import HevyClient
from fitness.db.lifts import (
    get_existing_lift_ids,
    bulk_create_lifts,
    get_existing_exercise_template_ids,
    bulk_upsert_exercise_templates,
)
from fitness.db.sync_metadata import get_last_sync_time, update_last_sync_time

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hevy", tags=["hevy"])

# Hevy-specific ID prefix for generic tables
HEVY_ID_PREFIX = "hevy_"
PROVIDER_NAME = "hevy"


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


# --- Endpoints ---


@router.post("/sync", response_model=HevySyncResponse)
async def sync_hevy_data(
    full_sync: bool = Query(
        False,
        description="Force a full sync instead of incremental. "
        "Use this to re-fetch all data from the beginning.",
    ),
    user: User = Depends(require_editor),
    client: HevyClient = Depends(hevy_client),
) -> HevySyncResponse:
    """Sync workouts and exercise templates from Hevy API.

    By default, performs an incremental sync fetching only workouts created
    after the last successful sync. Use `full_sync=true` to fetch all data.

    Requires authentication with editor role. Fetches workouts from Hevy and
    inserts only new ones (preserving local edits). Fetches exercise templates
    only for exercises we haven't seen before.
    """
    # Determine sync start time for incremental sync
    since = None
    if not full_sync:
        since = get_last_sync_time(PROVIDER_NAME)
        if since:
            logger.info(f"Performing incremental Hevy sync from {since.isoformat()}")
        else:
            logger.info("No previous sync found, performing full Hevy sync")
    else:
        logger.info("Full Hevy sync requested")

    # Record sync start time before fetching
    sync_time = datetime.now(timezone.utc)

    # 1. Fetch workouts from Hevy API (with optional since filter)
    all_workouts = client.get_all_workouts(since=since)
    logger.info(f"Fetched {len(all_workouts)} workouts from Hevy API")

    # 2. Filter to only new workouts (not already in DB)
    # Note: DB stores prefixed IDs (hevy_xxx), API returns unprefixed (xxx)
    existing_lift_ids = get_existing_lift_ids()
    new_workouts = [
        w for w in all_workouts if f"{HEVY_ID_PREFIX}{w.id}" not in existing_lift_ids
    ]
    logger.info(
        f"Found {len(new_workouts)} new workouts "
        f"({len(existing_lift_ids)} already in database)"
    )

    # 3. Extract unique template IDs from new workouts only
    template_ids_in_new_workouts: set[str] = set()
    for workout in new_workouts:
        for exercise in workout.exercises:
            template_ids_in_new_workouts.add(exercise.exercise_template_id)

    # 4. Find which templates we don't have cached yet
    # Note: DB stores prefixed IDs, so prefix when comparing
    existing_template_ids = get_existing_exercise_template_ids()
    missing_template_ids = {
        tid
        for tid in template_ids_in_new_workouts
        if f"{HEVY_ID_PREFIX}{tid}" not in existing_template_ids
    }
    logger.info(
        f"Need to fetch {len(missing_template_ids)} new exercise templates "
        f"({len(existing_template_ids)} already cached)"
    )

    # 5. Fetch only missing templates and convert to generic ExerciseTemplate
    new_templates: list[ExerciseTemplate] = []
    for template_id in missing_template_ids:
        hevy_template = client.get_exercise_template_by_id(template_id)
        if hevy_template:
            new_templates.append(
                ExerciseTemplate.from_hevy(hevy_template, id_prefix=HEVY_ID_PREFIX)
            )
        else:
            logger.warning(f"Could not fetch exercise template {template_id}")

    # 6. Insert new templates
    templates_synced = bulk_upsert_exercise_templates(new_templates)
    logger.info(f"Synced {templates_synced} new exercise templates")

    # 7. Convert workouts to generic Lift objects and insert
    new_lifts = [Lift.from_hevy(w, id_prefix=HEVY_ID_PREFIX) for w in new_workouts]
    workouts_synced = bulk_create_lifts(new_lifts)
    logger.info(f"Inserted {workouts_synced} new workouts")

    # Update last sync time on successful completion
    update_last_sync_time(PROVIDER_NAME, sync_time)

    sync_type = "full" if full_sync or since is None else "incremental"
    return HevySyncResponse(
        workouts_synced=workouts_synced,
        templates_synced=templates_synced,
        message=f"Synced {workouts_synced} workouts and {templates_synced} templates ({sync_type} sync)",
        synced_at=sync_time,
    )
