"""
Integration tests for Strava API client.

These tests make real API calls to Strava and require valid credentials
in the database. Run with: pytest -m integration

Skipped by default in CI (no credentials available).
"""

import pytest
from fitness.db.oauth_credentials import get_credentials
from fitness.integrations.strava.client import StravaClient


def _get_strava_creds():
    """Get Strava credentials, or None if not configured."""
    try:
        return get_credentials("strava")
    except Exception:
        return None


# Skip all tests in this module if no Strava credentials
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        _get_strava_creds() is None,
        reason="Strava credentials not configured in database",
    ),
]


@pytest.fixture
def strava_client():
    """Create a StravaClient with real credentials."""
    creds = get_credentials("strava")
    assert creds is not None, "Strava credentials not found"
    return StravaClient(creds=creds)


def test_token_refresh_and_fetch_activities(strava_client):
    """Test that token refresh works and we can fetch activities."""
    # This will trigger proactive refresh if token expires within 5 minutes
    activities = strava_client.get_activities()

    assert isinstance(activities, list)
    assert len(activities) > 0, "Expected at least one activity"

    # Verify activity structure
    activity = activities[0]
    assert activity.id is not None
    assert activity.name is not None
    assert activity.type is not None


def test_credentials_persisted_after_refresh(strava_client):
    """Test that refreshed credentials are persisted to database."""
    original_token = strava_client.creds.access_token

    # Make a request (may trigger refresh)
    strava_client.get_activities()

    # Check if credentials were updated in database
    updated_creds = get_credentials("strava")
    assert updated_creds is not None
    assert updated_creds.access_token is not None

    # If token was refreshed, it should be different and have new expiry
    if updated_creds.access_token != original_token:
        assert updated_creds.expires_at is not None
