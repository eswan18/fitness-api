"""Google OAuth authentication functions."""

import os
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone
import logging

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

PUBLIC_API_BASE_URL = os.environ["PUBLIC_API_BASE_URL"]
GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]

logger = logging.getLogger(__name__)


class GoogleToken(BaseModel):
    """An OAuth token for the Google API."""

    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None
    token_type: str = "Bearer"
    scope: str | None = None

    def expires_at_datetime(self) -> datetime | None:
        """Convert expires_in to a datetime."""
        if self.expires_in is None:
            return None
        return datetime.now(timezone.utc) + timedelta(seconds=self.expires_in)


async def exchange_code_for_token(code: str) -> GoogleToken:
    """Exchange a Google authorization code for an access token.

    Args:
        code: The authorization code to use for obtaining a new access token

    Returns:
        GoogleToken: A new token containing access_token and refresh_token

    Raises:
        HTTPException: If the exchange request fails
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth not configured. Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET",
        )

    redirect_uri = f"{PUBLIC_API_BASE_URL}/oauth/google/callback"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        error_text = response.text
        logger.error(
            f"Failed to exchange Google code: {response.status_code} - {error_text}"
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to exchange Google code (status {response.status_code}): {error_text}",
        )

    token_data = response.json()
    return GoogleToken(
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        expires_in=token_data.get("expires_in"),
        token_type=token_data.get("token_type", "Bearer"),
        scope=token_data.get("scope"),
    )


def build_oauth_authorize_url(redirect_uri: str, state: str | None = None) -> str:
    """Build the Google OAuth authorization URL.

    Args:
        redirect_uri: The redirect URI to use after authorization
        state: Optional state parameter for CSRF protection

    Returns:
        The authorization URL

    Raises:
        ValueError: If GOOGLE_CLIENT_ID is not configured
    """
    if not GOOGLE_CLIENT_ID:
        raise ValueError("GOOGLE_CLIENT_ID environment variable is not set")

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "https://www.googleapis.com/auth/calendar",
        "response_type": "code",
        "access_type": "offline",  # Required to get refresh token
        "prompt": "consent",  # Force consent screen to ensure refresh token
    }
    if state is not None:
        params["state"] = state

    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    logger.info(f"Building Google OAuth authorize URL: {url}")
    return url
