"""CSRF state tokens for OAuth authorize/callback flows.

The OAuth `state` parameter is a short-lived HS256-signed JWT bound to the
provider initiating the flow. The callback handler verifies the signature
and provider claim before accepting the authorization code, which prevents
an attacker from forging or replaying a callback against another provider.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt

OAuthProvider = Literal["strava", "google"]

STATE_TTL_SECONDS = 600  # 10 minutes
_ALGORITHM = "HS256"


class InvalidOAuthState(Exception):
    """Raised when an OAuth callback `state` is missing, malformed, or expired."""


def _secret() -> str:
    secret = os.environ["OAUTH_STATE_SECRET"]
    if not secret:
        raise RuntimeError("OAUTH_STATE_SECRET is set but empty")
    return secret


def issue_state(provider: OAuthProvider) -> str:
    """Issue a signed state token bound to `provider`."""
    now = datetime.now(timezone.utc)
    payload = {
        "provider": provider,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=STATE_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def verify_state(token: str | None, expected_provider: OAuthProvider) -> None:
    """Validate a callback `state` token. Raises InvalidOAuthState on failure."""
    if not token:
        raise InvalidOAuthState("Missing state parameter")
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=[_ALGORITHM],
            options={"require": ["exp", "iat", "provider"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise InvalidOAuthState("State token expired") from e
    except jwt.InvalidTokenError as e:
        raise InvalidOAuthState("Invalid state token") from e

    if claims.get("provider") != expected_provider:
        raise InvalidOAuthState("State token provider mismatch")
