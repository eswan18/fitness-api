"""Tests for the OAuth CSRF state token helper."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from fitness.app import oauth_state
from fitness.app.oauth_state import InvalidOAuthState, issue_state, verify_state


def test_roundtrip_accepts_matching_provider():
    token = issue_state("strava")
    # Should not raise.
    verify_state(token, "strava")


def test_rejects_missing_token():
    with pytest.raises(InvalidOAuthState):
        verify_state(None, "strava")
    with pytest.raises(InvalidOAuthState):
        verify_state("", "strava")


def test_rejects_provider_mismatch():
    token = issue_state("strava")
    with pytest.raises(InvalidOAuthState):
        verify_state(token, "google")


def test_rejects_garbage_token():
    with pytest.raises(InvalidOAuthState):
        verify_state("not-a-jwt", "strava")


def test_rejects_token_signed_with_wrong_secret(monkeypatch):
    forged = jwt.encode(
        {
            "provider": "strava",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int(
                (datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp()
            ),
        },
        "wrong-secret",
        algorithm="HS256",
    )
    with pytest.raises(InvalidOAuthState):
        verify_state(forged, "strava")


def test_rejects_expired_token(monkeypatch):
    monkeypatch.setattr(oauth_state, "STATE_TTL_SECONDS", -1)
    expired = issue_state("strava")
    with pytest.raises(InvalidOAuthState):
        verify_state(expired, "strava")
