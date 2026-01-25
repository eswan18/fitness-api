from unittest.mock import MagicMock, patch, Mock
import datetime

import pytest

from fitness.db.oauth_credentials import OAuthCredentials
from fitness.integrations.strava.client import StravaClient
from fitness.integrations.strava.models import StravaToken


def test_needs_token_refresh_valid():
    """Token that expires in more than 5 minutes should not need refresh."""
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


def test_needs_token_refresh_within_5_minutes():
    """Token that expires within 5 minutes should need refresh (proactive refresh)."""
    three_minutes_from_now = datetime.datetime.now(
        datetime.timezone.utc
    ) + datetime.timedelta(minutes=3)
    creds = OAuthCredentials(
        provider="strava",
        client_id="123",
        client_secret="456",
        access_token="101",
        refresh_token="789",
        expires_at=three_minutes_from_now,
    )
    client = StravaClient(creds=creds)
    assert client.needs_token_refresh() is True


def test_needs_token_refresh_expired():
    """Expired token should need refresh."""
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


def test_needs_token_refresh_unknown_expiration():
    """Token with unknown expiration should not trigger proactive refresh."""
    creds = OAuthCredentials(
        provider="strava",
        client_id="123",
        client_secret="456",
        access_token="101",
        refresh_token="789",
        expires_at=None,
    )
    client = StravaClient(creds=creds)
    assert client.needs_token_refresh() is False


def test_refresh_access_token_success(monkeypatch):
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
    refresh_access_token_sync = MagicMock(
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
            "fitness.integrations.strava.client.refresh_access_token_sync",
            refresh_access_token_sync,
        )
        m.setattr(
            "fitness.integrations.strava.client.upsert_credentials", upsert_credentials
        )
        result = client._refresh_access_token()
    assert result is True
    assert refresh_access_token_sync.call_count == 1
    assert upsert_credentials.call_count == 1
    assert client.creds.access_token == "new_access_token"
    assert client.creds.refresh_token == "new_refresh_token"
    assert client.creds.expires_at == one_hour_from_now_datetime


def test_refresh_access_token_invalid_grant(monkeypatch):
    """Test token refresh when refresh token is revoked."""
    expired_creds = OAuthCredentials(
        provider="strava",
        client_id="123",
        client_secret="456",
        access_token="101",
        refresh_token="789",
        expires_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(minutes=1),
    )
    client = StravaClient(creds=expired_creds)

    refresh_access_token_sync = MagicMock(
        side_effect=ValueError("Refresh token expired or revoked")
    )
    with monkeypatch.context() as m:
        m.setattr(
            "fitness.integrations.strava.client.refresh_access_token_sync",
            refresh_access_token_sync,
        )
        with pytest.raises(ValueError, match="Refresh token expired"):
            client._refresh_access_token()


def test_make_request_success(monkeypatch):
    """Test successful request without token refresh."""
    one_hour_from_now = datetime.datetime.now(
        datetime.timezone.utc
    ) + datetime.timedelta(hours=1)
    creds = OAuthCredentials(
        provider="strava",
        client_id="123",
        client_secret="456",
        access_token="valid_token",
        refresh_token="789",
        expires_at=one_hour_from_now,
    )
    client = StravaClient(creds=creds)

    mock_response = Mock()
    mock_response.status_code = 200

    with patch("httpx.Client") as mock_client:
        mock_client_instance = MagicMock()
        mock_client.return_value.__enter__.return_value = mock_client_instance
        mock_client_instance.request.return_value = mock_response

        response = client._make_request("GET", "https://api.strava.com/test")

    assert response is not None
    assert response.status_code == 200
    mock_client_instance.request.assert_called_once()


def test_make_request_proactive_refresh(monkeypatch):
    """Test request triggers proactive refresh when token is about to expire."""
    three_minutes_from_now = datetime.datetime.now(
        datetime.timezone.utc
    ) + datetime.timedelta(minutes=3)
    creds = OAuthCredentials(
        provider="strava",
        client_id="123",
        client_secret="456",
        access_token="expiring_token",
        refresh_token="789",
        expires_at=three_minutes_from_now,
    )
    client = StravaClient(creds=creds)

    now = datetime.datetime.now(datetime.timezone.utc)
    one_hour_from_now_timestamp = int((now + datetime.timedelta(hours=1)).timestamp())
    refresh_access_token_sync = MagicMock(
        return_value=StravaToken(
            token_type="Bearer",
            access_token="new_token",
            expires_at=one_hour_from_now_timestamp,
            expires_in=3600,
            refresh_token="new_refresh",
        )
    )
    upsert_credentials = MagicMock()

    mock_response = Mock()
    mock_response.status_code = 200

    with monkeypatch.context() as m:
        m.setattr(
            "fitness.integrations.strava.client.refresh_access_token_sync",
            refresh_access_token_sync,
        )
        m.setattr(
            "fitness.integrations.strava.client.upsert_credentials", upsert_credentials
        )

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_client_instance
            mock_client_instance.request.return_value = mock_response

            response = client._make_request("GET", "https://api.strava.com/test")

    # Verify token was refreshed proactively
    assert refresh_access_token_sync.call_count == 1
    assert response is not None
    assert response.status_code == 200


def test_make_request_401_retry(monkeypatch):
    """Test request retries on 401 after refreshing token."""
    one_hour_from_now = datetime.datetime.now(
        datetime.timezone.utc
    ) + datetime.timedelta(hours=1)
    creds = OAuthCredentials(
        provider="strava",
        client_id="123",
        client_secret="456",
        access_token="stale_token",
        refresh_token="789",
        expires_at=one_hour_from_now,
    )
    client = StravaClient(creds=creds)

    now = datetime.datetime.now(datetime.timezone.utc)
    one_hour_from_now_timestamp = int((now + datetime.timedelta(hours=1)).timestamp())
    refresh_access_token_sync = MagicMock(
        return_value=StravaToken(
            token_type="Bearer",
            access_token="new_token",
            expires_at=one_hour_from_now_timestamp,
            expires_in=3600,
            refresh_token="new_refresh",
        )
    )
    upsert_credentials = MagicMock()

    # First response is 401, second is 200
    mock_401_response = Mock()
    mock_401_response.status_code = 401
    mock_200_response = Mock()
    mock_200_response.status_code = 200

    with monkeypatch.context() as m:
        m.setattr(
            "fitness.integrations.strava.client.refresh_access_token_sync",
            refresh_access_token_sync,
        )
        m.setattr(
            "fitness.integrations.strava.client.upsert_credentials", upsert_credentials
        )

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_client_instance
            mock_client_instance.request.side_effect = [
                mock_401_response,
                mock_200_response,
            ]

            response = client._make_request("GET", "https://api.strava.com/test")

    # Verify token was refreshed and request retried
    assert refresh_access_token_sync.call_count == 1
    assert mock_client_instance.request.call_count == 2
    assert response is not None
    assert response.status_code == 200


def test_make_request_401_refresh_failure(monkeypatch):
    """Test request returns original response when 401 retry refresh fails."""
    one_hour_from_now = datetime.datetime.now(
        datetime.timezone.utc
    ) + datetime.timedelta(hours=1)
    creds = OAuthCredentials(
        provider="strava",
        client_id="123",
        client_secret="456",
        access_token="stale_token",
        refresh_token="789",
        expires_at=one_hour_from_now,
    )
    client = StravaClient(creds=creds)

    refresh_access_token_sync = MagicMock(
        side_effect=ValueError("Refresh token expired")
    )

    mock_401_response = Mock()
    mock_401_response.status_code = 401

    with monkeypatch.context() as m:
        m.setattr(
            "fitness.integrations.strava.client.refresh_access_token_sync",
            refresh_access_token_sync,
        )

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_client_instance
            mock_client_instance.request.return_value = mock_401_response

            response = client._make_request("GET", "https://api.strava.com/test")

    # Should return None when refresh token is revoked
    assert response is None
