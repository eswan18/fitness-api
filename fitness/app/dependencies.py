import logging

from fastapi import HTTPException

from fitness.models import Run
from fitness.db.runs import get_all_runs
from fitness.db.oauth_credentials import get_credentials
from fitness.integrations.strava.client import StravaClient

logger = logging.getLogger(__name__)


def all_runs() -> list[Run]:
    """Get all runs from the database."""
    return get_all_runs()


async def strava_client() -> StravaClient:
    strava_creds = get_credentials("strava")
    if strava_creds is None:
        raise HTTPException(status_code=503, detail="Strava integration not configured")
    client = StravaClient(creds=strava_creds)
    if client.needs_token_refresh():
        await client.refresh_access_token()
    return client
