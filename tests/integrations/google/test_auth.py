"""Tests for Google OAuth auth module."""

from unittest.mock import patch, AsyncMock, Mock
import pytest
from fastapi import HTTPException

from fitness.integrations.google.auth import (
    build_oauth_authorize_url,
    exchange_code_for_token,
    GoogleToken,
)


def test_build_oauth_authorize_url(monkeypatch):
    """Test building Google OAuth authorization URL."""
    monkeypatch.setattr(
        "fitness.integrations.google.auth.GOOGLE_CLIENT_ID", "test_client_id"
    )
    url = build_oauth_authorize_url("https://examplecallback.com")
    assert "https://accounts.google.com/o/oauth2/v2/auth" in url
    assert "client_id=test_client_id" in url
    assert "redirect_uri=https%3A%2F%2Fexamplecallback.com" in url
    assert "scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcalendar" in url
    assert "response_type=code" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url


def test_build_oauth_authorize_url_with_state(monkeypatch):
    """Test building Google OAuth URL with state parameter."""
    monkeypatch.setattr(
        "fitness.integrations.google.auth.GOOGLE_CLIENT_ID", "test_client_id"
    )
    url = build_oauth_authorize_url(
        "https://examplecallback.com", state="test_state_123"
    )
    assert "state=test_state_123" in url


def test_build_oauth_authorize_url_missing_client_id(monkeypatch):
    """Test that missing CLIENT_ID raises ValueError."""
    monkeypatch.setattr("fitness.integrations.google.auth.GOOGLE_CLIENT_ID", None)
    with pytest.raises(ValueError, match="GOOGLE_CLIENT_ID"):
        build_oauth_authorize_url("https://examplecallback.com")


@pytest.mark.asyncio
async def test_exchange_code_for_token_success(monkeypatch):
    """Test successful token exchange."""
    monkeypatch.setattr(
        "fitness.integrations.google.auth.GOOGLE_CLIENT_ID", "test_client_id"
    )
    monkeypatch.setattr(
        "fitness.integrations.google.auth.GOOGLE_CLIENT_SECRET", "test_client_secret"
    )
    monkeypatch.setattr(
        "fitness.integrations.google.auth.PUBLIC_API_BASE_URL",
        "https://api.example.com",
    )

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "https://www.googleapis.com/auth/calendar",
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.post.return_value = mock_response

        token = await exchange_code_for_token("test_code")

    assert isinstance(token, GoogleToken)
    assert token.access_token == "test_access_token"
    assert token.refresh_token == "test_refresh_token"
    assert token.expires_in == 3600
    assert token.token_type == "Bearer"

    # Verify the request was made correctly
    mock_client_instance.post.assert_called_once()
    call_args = mock_client_instance.post.call_args
    assert call_args[0][0] == "https://oauth2.googleapis.com/token"
    assert call_args[1]["data"]["code"] == "test_code"
    assert call_args[1]["data"]["grant_type"] == "authorization_code"
    assert call_args[1]["data"]["client_id"] == "test_client_id"
    assert call_args[1]["data"]["client_secret"] == "test_client_secret"
    assert (
        call_args[1]["data"]["redirect_uri"]
        == "https://api.example.com/oauth/google/callback"
    )


@pytest.mark.asyncio
async def test_exchange_code_for_token_missing_credentials(monkeypatch):
    """Test token exchange when credentials are missing."""
    monkeypatch.setattr("fitness.integrations.google.auth.GOOGLE_CLIENT_ID", None)
    monkeypatch.setattr("fitness.integrations.google.auth.GOOGLE_CLIENT_SECRET", None)

    with pytest.raises(HTTPException) as exc_info:
        await exchange_code_for_token("test_code")

    assert isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == 503
    assert "not configured" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_exchange_code_for_token_api_error(monkeypatch):
    """Test token exchange when Google API returns an error."""
    monkeypatch.setattr(
        "fitness.integrations.google.auth.GOOGLE_CLIENT_ID", "test_client_id"
    )
    monkeypatch.setattr(
        "fitness.integrations.google.auth.GOOGLE_CLIENT_SECRET", "test_client_secret"
    )
    monkeypatch.setattr(
        "fitness.integrations.google.auth.PUBLIC_API_BASE_URL",
        "https://api.example.com",
    )

    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.text = '{"error": "invalid_grant"}'

    with patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.post.return_value = mock_response

        with pytest.raises(HTTPException) as exc_info:
            await exchange_code_for_token("test_code")

    assert isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == 502
    assert "Failed to exchange" in exc_info.value.detail


@pytest.mark.asyncio
async def test_exchange_code_for_token_no_refresh_token(monkeypatch):
    """Test token exchange when Google doesn't return refresh token."""
    monkeypatch.setattr(
        "fitness.integrations.google.auth.GOOGLE_CLIENT_ID", "test_client_id"
    )
    monkeypatch.setattr(
        "fitness.integrations.google.auth.GOOGLE_CLIENT_SECRET", "test_client_secret"
    )
    monkeypatch.setattr(
        "fitness.integrations.google.auth.PUBLIC_API_BASE_URL",
        "https://api.example.com",
    )

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "test_access_token",
        # No refresh_token
        "expires_in": 3600,
        "token_type": "Bearer",
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.post.return_value = mock_response

        token = await exchange_code_for_token("test_code")

    assert token.refresh_token is None


def test_google_token_expires_at_datetime():
    """Test GoogleToken expires_at_datetime method."""
    from datetime import datetime, timezone

    # Token with expires_in
    token = GoogleToken(
        access_token="test",
        refresh_token="test",
        expires_in=3600,
    )
    expires_at = token.expires_at_datetime()
    assert expires_at is not None
    assert isinstance(expires_at, datetime)
    # Should be approximately 1 hour from now
    now = datetime.now(timezone.utc)
    assert (expires_at - now).total_seconds() > 3500
    assert (expires_at - now).total_seconds() < 3700

    # Token without expires_in
    token_no_expiry = GoogleToken(
        access_token="test",
        refresh_token="test",
        expires_in=None,
    )
    assert token_no_expiry.expires_at_datetime() is None
