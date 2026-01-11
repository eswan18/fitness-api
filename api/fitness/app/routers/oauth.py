import os
import logging

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse

from fitness.db.oauth_credentials import (
    OAuthCredentials,
    get_credentials,
    upsert_credentials,
    OAuthIntegrationStatus,
)
from fitness.models.user import User
from fitness.app.auth import require_viewer, require_editor
from fitness.integrations import strava
from fitness.integrations import google

PUBLIC_API_BASE_URL = os.environ["PUBLIC_API_BASE_URL"]
PUBLIC_DASHBOARD_BASE_URL = os.environ["PUBLIC_DASHBOARD_BASE_URL"]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["oauth"])


@router.get("/strava/status", response_model=OAuthIntegrationStatus)
def strava_auth_status(_user: User = Depends(require_viewer)) -> OAuthIntegrationStatus:
    """Get the current authorization status for Strava.

    Returns whether the user has authorized Strava and if the access token is valid.
    """
    creds = get_credentials("strava")
    if creds is None:
        return OAuthIntegrationStatus(authorized=False)
    return creds.integration_status()


@router.get("/strava/authorize")
def strava_oauth_authorize(user: User = Depends(require_editor)) -> RedirectResponse:
    """Log into Strava and redirect to the callback endpoint.

    Requires editor role as this connects an external data source.
    """
    url = strava.build_oauth_authorize_url(
        redirect_uri=f"{PUBLIC_API_BASE_URL}/oauth/strava/callback"
    )
    return RedirectResponse(url)


@router.get("/strava/callback")
async def strava_oauth_callback(
    code: str | None = None, state: str | None = None
) -> RedirectResponse:
    """Strava OAuth callback endpoint."""
    if code is None:
        raise HTTPException(
            status_code=400,
            detail="No code provided",
        )
    token = await strava.exchange_code_for_token(code)
    # Store the token in the db.
    upsert_credentials(
        OAuthCredentials(
            provider="strava",
            client_id=strava.CLIENT_ID,
            client_secret=strava.CLIENT_SECRET,
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_at=token.expires_at_datetime(),
        )
    )
    # Redirect back to the frontend.
    return RedirectResponse(PUBLIC_DASHBOARD_BASE_URL)


@router.get("/google/status", response_model=OAuthIntegrationStatus)
def google_auth_status(_user: User = Depends(require_viewer)) -> OAuthIntegrationStatus:
    """Get the current authorization status for Google.

    Returns whether the user has authorized Google and if the access token is valid.
    """
    creds = get_credentials("google")
    if creds is None:
        return OAuthIntegrationStatus(authorized=False)
    return creds.integration_status()


@router.get("/google/authorize")
def google_oauth_authorize(user: User = Depends(require_editor)) -> RedirectResponse:
    """Log into Google and redirect to the callback endpoint.

    Requires editor role as this connects an external data source.
    """
    url = google.auth.build_oauth_authorize_url(
        redirect_uri=f"{PUBLIC_API_BASE_URL}/oauth/google/callback"
    )
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_oauth_callback(
    code: str | None = None, state: str | None = None, error: str | None = None
) -> RedirectResponse:
    """Google OAuth callback endpoint."""
    if error:
        logger.error(f"Google OAuth error: {error}")
        raise HTTPException(
            status_code=400,
            detail=f"Google OAuth authorization failed: {error}",
        )

    if code is None:
        raise HTTPException(
            status_code=400,
            detail="No code provided",
        )

    token = await google.auth.exchange_code_for_token(code)

    if not token.refresh_token:
        logger.warning("Google OAuth did not return a refresh token")
        raise HTTPException(
            status_code=502,
            detail="Google OAuth did not return a refresh token. This may happen if you have previously authorized the app. Please revoke access at https://myaccount.google.com/permissions and try again.",
        )

    # Store the token in the db.
    upsert_credentials(
        OAuthCredentials(
            provider="google",
            client_id=google.auth.GOOGLE_CLIENT_ID,
            client_secret=google.auth.GOOGLE_CLIENT_SECRET,
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_at=token.expires_at_datetime(),
        )
    )

    # Redirect back to the frontend.
    return RedirectResponse(PUBLIC_DASHBOARD_BASE_URL)
