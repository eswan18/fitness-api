from unittest.mock import AsyncMock, MagicMock
import datetime

import pytest

from fitness.db.oauth_credentials import OAuthCredentials
from fitness.integrations.strava.client import StravaClient
from fitness.integrations.strava.models import StravaToken


def test_needs_token_refresh_valid():
    one_hour_from_now = datetime.datetime.now(
        datetime.timezone.utc
    ) + datetime.timedelta(hours=1)
    valid_creds = OAuthCredentials(
        provider="strava",
        client_id="123",
        client_secret="456",
        access_token="101",
        refresh_token="789",
        expires_at=one_hour_from_now,
    )
    client = StravaClient(creds=valid_creds)
    assert client.needs_token_refresh() is False


def test_needs_token_refresh_invalid():
    one_minute_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        minutes=1
    )
    invalid_creds = OAuthCredentials(
        provider="strava",
        client_id="123",
        client_secret="456",
        access_token="101",
        refresh_token="789",
        expires_at=one_minute_ago,
    )
    client = StravaClient(creds=invalid_creds)
    assert client.needs_token_refresh() is True


@pytest.mark.asyncio
async def test_refresh_access_token_success(monkeypatch):
    """Test successful token refresh."""
    now = datetime.datetime.now(datetime.timezone.utc)
    one_minute_ago = now - datetime.timedelta(minutes=1)
    expired_creds = OAuthCredentials(
        provider="strava",
        client_id="123",
        client_secret="456",
        access_token="101",
        refresh_token="789",
        expires_at=one_minute_ago,
    )
    client = StravaClient(creds=expired_creds)

    one_hour_from_now_timestamp = int((now + datetime.timedelta(hours=1)).timestamp())
    one_hour_from_now_datetime = datetime.datetime.fromtimestamp(
        one_hour_from_now_timestamp, tz=datetime.timezone.utc
    )
    refresh_access_token = AsyncMock(
        return_value=StravaToken(
            token_type="Bearer",
            access_token="new_access_token",
            expires_at=one_hour_from_now_timestamp,
            expires_in=3600,
            refresh_token="new_refresh_token",
        )
    )
    upsert_credentials = MagicMock()
    with monkeypatch.context() as m:
        m.setattr(
            "fitness.integrations.strava.client.refresh_access_token",
            refresh_access_token,
        )
        m.setattr(
            "fitness.integrations.strava.client.upsert_credentials", upsert_credentials
        )
        await client.refresh_access_token()
    assert refresh_access_token.call_count == 1
    assert upsert_credentials.call_count == 1
    assert client.creds.access_token == "new_access_token"
    assert client.creds.refresh_token == "new_refresh_token"
    assert client.creds.expires_at == one_hour_from_now_datetime
