import logging
from datetime import datetime
from typing import Optional

from fitness.integrations.strava.client import StravaClient
from fitness.integrations.strava.models import StravaActivityWithGear

logger = logging.getLogger(__name__)


def load_strava_runs(
    client: StravaClient, after: Optional[datetime] = None
) -> list[StravaActivityWithGear]:
    """Fetch runs from Strava along with the gear used in them.

    Args:
        client: The Strava API client.
        after: Only fetch activities after this datetime (for incremental sync).

    Returns:
        List of Strava activities with gear information.
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
        runs_w_gear = [
            run.with_gear(gear=gear_by_id[run.gear_id])
            for run in runs
            if run.gear_id is not None and run.gear_id in gear_by_id
        ]

        logger.info(
            f"Successfully loaded {len(runs_w_gear)} Strava runs with gear information"
        )
        return runs_w_gear

    except Exception as e:
        logger.error(
            f"Failed to load Strava runs: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        raise
