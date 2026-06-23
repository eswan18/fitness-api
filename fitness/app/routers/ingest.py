"""Push-ingestion endpoints for external fitness sources.

Currently: ``POST /ingest/hae`` for the Health Auto Export (HAE) iOS app, which
forwards Apple Health workouts (originally recorded by WorkOutDoors). Running
workouts land in the ``runs`` table and cycling workouts in ``rides`` — both feed
the existing TRIMP/hrTSS training-load calc with no further wiring.

Idempotency: rows are keyed by ``hae_<HealthKit UUID>`` and inserted with
``ON CONFLICT (id) DO NOTHING``, so HAE's overlapping "Since Last Sync" windows
and background retries never create duplicates.

Body size: this service runs uvicorn directly behind a Cloudflare Tunnel (~100 MB
cap) — there is no nginx ``client_max_body_size`` to raise. If a 413 is ever seen
with large GPS payloads, enable HAE's "Batch Requests" to shrink each POST.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from fitness.app.ingest_auth import require_ingest_token
from fitness.db.runs import bulk_create_runs
from fitness.db.rides import bulk_create_rides
from fitness.models.hae import HaeIngestRequest, HaeWorkout
from fitness.models.ride import HaeRideMap, Ride
from fitness.models.run import HaeRunMap, Run

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestSummary(BaseModel):
    received: int
    created: int
    skipped: int
    errors: list[str]
    token_name: str


@router.post("/hae", response_model=IngestSummary)
async def ingest_hae(
    payload: HaeIngestRequest,
    token_name: str = Depends(require_ingest_token),
) -> IngestSummary:
    """Ingest Health Auto Export workouts. Returns a per-batch summary.

    Non-run/ride workouts are counted as ``skipped``; per-workout parse failures
    are recorded in ``errors`` without failing the rest of the batch.
    """
    workouts = payload.data.workouts
    runs: list[Run] = []
    rides: list[Ride] = []
    skipped = 0
    errors: list[str] = []

    for workout in workouts:
        try:
            if workout.name in HaeRunMap:
                runs.append(Run.from_hae(workout))
            elif workout.name in HaeRideMap:
                rides.append(Ride.from_hae(workout))
            else:
                skipped += 1
        except (ValueError, KeyError) as exc:
            errors.append(f"{_workout_label(workout)}: {exc}")

    created = 0
    if runs:
        created += bulk_create_runs(runs)
    if rides:
        created += bulk_create_rides(rides)

    # Workouts that parsed and matched a run/ride type but were duplicates
    # (ON CONFLICT DO NOTHING) count as skipped, not created.
    matched = len(runs) + len(rides)
    skipped += matched - created

    summary = IngestSummary(
        received=len(workouts),
        created=created,
        skipped=skipped,
        errors=errors,
        token_name=token_name,
    )
    logger.info(
        "HAE ingest by '%s': received=%d created=%d skipped=%d errors=%d",
        token_name,
        summary.received,
        summary.created,
        summary.skipped,
        len(summary.errors),
    )
    return summary


def _workout_label(workout: HaeWorkout) -> str:
    """A short identifier for error messages (id may be missing on bad input)."""
    return f"workout {getattr(workout, 'id', '?')}"
