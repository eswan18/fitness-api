import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from fitness.integrations.strava.client import StravaClient
from fitness.integrations.strava.models import StravaActivity, StravaActivityWithGear
from fitness.models.responses import SkippedRun

logger = logging.getLogger(__name__)


@dataclass
class StravaRunLoadResult:
    """Output of `load_strava_runs`: imported runs and per-run skip reasons.

    A Strava run is only imported when it has usable gear (shoes) attached.
    Runs missing gear are surfaced via `skipped` so the caller can return
    them to the user for follow-up (assign shoes in Strava and re-sync with
    `full_sync=true`, since incremental sync filters by activity start time).
    """

    runs: list[StravaActivityWithGear]
    skipped: list[SkippedRun] = field(default_factory=list)


def load_strava_rides(
    client: StravaClient, after: Optional[datetime] = None
) -> list[StravaActivity]:
    """Fetch outdoor (`Ride`) and indoor (`VirtualRide`) cycling activities.

    Unlike runs, rides are not joined with gear in v1 (no bike tracking yet),
    so this returns raw `StravaActivity` instances.

    Args:
        client: The Strava API client.
        after: Only fetch activities after this datetime (for incremental sync).

    Returns:
        List of Strava cycling activities.
    """
    if after:
        logger.info(
            f"Starting Strava ride load (incremental, after {after.isoformat()})"
        )
    else:
        logger.info("Starting Strava ride load (full sync)")

    try:
        activities = client.get_activities(after=after)
        logger.info(f"Retrieved {len(activities)} total activities from Strava")
        rides = [a for a in activities if a.type in ("Ride", "VirtualRide")]
        logger.info(
            f"Filtered to {len(rides)} rides (excluded {len(activities) - len(rides)} non-ride activities)"
        )
        return rides
    except Exception as e:
        logger.error(
            f"Failed to load Strava rides: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        raise


def load_strava_runs(
    client: StravaClient, after: Optional[datetime] = None
) -> StravaRunLoadResult:
    """Fetch runs from Strava along with the gear used in them.

    Runs without usable gear are excluded from the imported list and reported
    via `StravaRunLoadResult.skipped` so the caller can show them to the user.
    See `StravaRunLoadResult` for re-import semantics.

    Args:
        client: The Strava API client.
        after: Only fetch activities after this datetime (for incremental sync).
    """
    if after:
        logger.info(
            f"Starting Strava data load (incremental, after {after.isoformat()})"
        )
    else:
        logger.info("Starting Strava data load (full sync)")

    try:
        # Get activities and the gear used in them.
        logger.info("Fetching activities from Strava API")
        activities = client.get_activities(after=after)
        logger.info(f"Retrieved {len(activities)} total activities from Strava")

        # Limit down to only runs.
        initial_count = len(activities)
        runs = [
            activity
            for activity in activities
            if activity.type in ("Run", "Indoor Run")
        ]
        non_run_count = initial_count - len(runs)
        logger.info(
            f"Filtered to {len(runs)} runs (excluded {non_run_count} non-run activities)"
        )

        # Get gear information for runs that have gear
        gear_ids = {run.gear_id for run in runs if run.gear_id}
        logger.info(f"Found {len(gear_ids)} unique gear items used in runs")

        if gear_ids:
            logger.info(
                f"Fetching gear details for {len(gear_ids)} items from Strava API"
            )
            gear = client.get_gear(gear_ids)
            logger.info(f"Retrieved details for {len(gear)} gear items")
        else:
            logger.info("No gear to fetch (runs have no gear assigned)")
            gear = []

        gear_by_id = {g.id: g for g in gear}

        runs_w_gear: list[StravaActivityWithGear] = []
        skipped: list[SkippedRun] = []
        for run in runs:
            if run.gear_id is None:
                # User-actionable: assign shoes in Strava and re-sync.
                logger.info(
                    f"Skipping Strava run {run.id} ({run.name!r}): no gear assigned"
                )
                skipped.append(
                    SkippedRun(
                        id=str(run.id), name=run.name, reason="no_gear_assigned"
                    )
                )
                continue
            if run.gear_id not in gear_by_id:
                # Strava-side anomaly: gear referenced but the gear fetch
                # didn't return it (deleted, permission change, partial response).
                logger.warning(
                    f"Skipping Strava run {run.id} ({run.name!r}): "
                    f"gear_id={run.gear_id} not returned by gear fetch"
                )
                skipped.append(
                    SkippedRun(
                        id=str(run.id), name=run.name, reason="gear_fetch_failed"
                    )
                )
                continue
            runs_w_gear.append(run.with_gear(gear=gear_by_id[run.gear_id]))

        logger.info(
            f"Successfully loaded {len(runs_w_gear)} Strava runs with gear "
            f"information ({len(skipped)} skipped for missing gear)"
        )
        return StravaRunLoadResult(runs=runs_w_gear, skipped=skipped)

    except Exception as e:
        logger.error(
            f"Failed to load Strava runs: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        raise
