import logging

from fastapi import HTTPException

from fitness.db.oauth_credentials import get_credentials
from fitness.integrations.strava.client import StravaClient

logger = logging.getLogger(__name__)


def strava_client() -> StravaClient:
    """Get a StravaClient with credentials from the database.

    Token refresh is handled automatically by the client on each request.
    """
    strava_creds = get_credentials("strava")
    if strava_creds is None:
        raise HTTPException(status_code=503, detail="Strava integration not configured")
    return StravaClient(creds=strava_creds)
