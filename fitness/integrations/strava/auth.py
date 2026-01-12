import os
from urllib.parse import urlencode
import logging

import httpx
from fastapi import HTTPException

from .models import StravaToken

TOKEN_URL = os.environ["STRAVA_TOKEN_URL"]
OAUTH_URL = os.environ["STRAVA_OAUTH_URL"]
CLIENT_ID = os.environ["STRAVA_CLIENT_ID"]
CLIENT_SECRET = os.environ["STRAVA_CLIENT_SECRET"]
PUBLIC_API_BASE_URL = os.environ["PUBLIC_API_BASE_URL"]

logger = logging.getLogger(__name__)


async def exchange_code_for_token(code: str) -> StravaToken:
    """Exchange a Strava authorization code for an access token.

    Args:
        code: The authorization code to use for obtaining a new access token

    Returns:
        StravaToken: A new token containing both access_token and refresh_token

    Raises:
        HTTPException: If the exchange request fails
    """
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": f"{PUBLIC_API_BASE_URL}/oauth/strava/callback",
            },
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to exchange Strava code (status {response.status_code})",
        )
    return StravaToken.model_validate_json(response.content)


async def refresh_access_token(refresh_token: str) -> StravaToken:
    """Refresh a Strava access token using a refresh token.

    Args:
        refresh_token: The refresh token to use for obtaining a new access token

    Returns:
        StravaToken: A new token containing both access_token and refresh_token

    Raises:
        HTTPException: If the refresh request fails
    """
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to refresh Strava token (status {response.status_code}): {response.text}",
        )
    return StravaToken.model_validate_json(response.content)


def build_oauth_authorize_url(redirect_uri: str, state: str | None = None) -> str:
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "activity:read_all",
        "response_type": "code",
    }
    if state is not None:
        params["state"] = state
    url = f"{OAUTH_URL}?{urlencode(params)}"
    logger.info(f"Building OAuth authorize URL: {url}")
    return url
