"""Basic tests for OAuth router endpoints."""

from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from fitness.db.oauth_credentials import OAuthCredentials


class TestStravaAuthStatus:
    """Test GET /oauth/strava/status endpoint."""

    def test_status_no_credentials(self, viewer_client: TestClient):
        """Test status endpoint when no credentials exist."""
        with patch("fitness.app.routers.oauth.get_credentials", return_value=None):
            response = viewer_client.get("/oauth/strava/status")

        assert response.status_code == 200
        data = response.json()
        assert data["authorized"] is False
        assert data["access_token_valid"] is None
        assert data["expires_at"] is None

    def test_status_with_valid_credentials(self, viewer_client: TestClient):
        """Test status endpoint when valid credentials exist."""
        future_expiry = datetime.now(timezone.utc).replace(year=2030, month=12, day=31)
        creds = OAuthCredentials(
            provider="strava",
            client_id="test_client_id",
            client_secret="test_secret",
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_at=future_expiry,
        )

        with patch("fitness.app.routers.oauth.get_credentials", return_value=creds):
            response = viewer_client.get("/oauth/strava/status")

        assert response.status_code == 200
        data = response.json()
        assert data["authorized"] is True
        assert data["access_token_valid"] is True
        assert data["expires_at"] is not None

    def test_status_with_expired_credentials(self, viewer_client: TestClient):
        """Test status endpoint when credentials are expired."""
        past_expiry = datetime.now(timezone.utc).replace(year=2020, month=1, day=1)
        creds = OAuthCredentials(
            provider="strava",
            client_id="test_client_id",
            client_secret="test_secret",
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_at=past_expiry,
        )

        with patch("fitness.app.routers.oauth.get_credentials", return_value=creds):
            response = viewer_client.get("/oauth/strava/status")

        assert response.status_code == 200
        data = response.json()
        assert data["authorized"] is True
        assert data["access_token_valid"] is False

    def test_status_requires_auth(self, client: TestClient):
        """Test that status endpoint requires authentication."""
        response = client.get("/oauth/strava/status")
        assert response.status_code == 401


class TestStravaAuthorize:
    """Test GET /oauth/strava/authorize endpoint."""

    def test_authorize_redirects(self, editor_client: TestClient):
        """Test that authorize endpoint redirects to Strava OAuth URL."""
        with patch(
            "fitness.app.routers.oauth.strava.build_oauth_authorize_url"
        ) as mock_build:
            mock_build.return_value = (
                "https://www.strava.com/oauth/authorize?client_id=123"
            )
            with patch(
                "fitness.app.routers.oauth.PUBLIC_API_BASE_URL",
                "https://api.example.com",
            ):
                response = editor_client.get(
                    "/oauth/strava/authorize", follow_redirects=False
                )

        assert response.status_code == 307  # Temporary redirect
        assert (
            response.headers["location"]
            == "https://www.strava.com/oauth/authorize?client_id=123"
        )
        mock_build.assert_called_once_with(
            redirect_uri="https://api.example.com/oauth/strava/callback"
        )

    def test_authorize_requires_editor(self, viewer_client: TestClient):
        """Test that authorize endpoint requires editor role."""
        response = viewer_client.get("/oauth/strava/authorize", follow_redirects=False)
        assert response.status_code == 403


class TestStravaAuthorizeUrl:
    """Test GET /oauth/strava/authorize-url endpoint."""

    def test_authorize_url_returns_json(self, editor_client: TestClient):
        """Test that authorize-url endpoint returns URL as JSON."""
        with patch(
            "fitness.app.routers.oauth.strava.build_oauth_authorize_url"
        ) as mock_build:
            mock_build.return_value = (
                "https://www.strava.com/oauth/authorize?client_id=123"
            )
            with patch(
                "fitness.app.routers.oauth.PUBLIC_API_BASE_URL",
                "https://api.example.com",
            ):
                response = editor_client.get("/oauth/strava/authorize-url")

        assert response.status_code == 200
        data = response.json()
        assert data["url"] == "https://www.strava.com/oauth/authorize?client_id=123"
        mock_build.assert_called_once_with(
            redirect_uri="https://api.example.com/oauth/strava/callback"
        )

    def test_authorize_url_requires_editor(self, viewer_client: TestClient):
        """Test that authorize-url endpoint requires editor role."""
        response = viewer_client.get("/oauth/strava/authorize-url")
        assert response.status_code == 403

    def test_authorize_url_requires_auth(self, client: TestClient):
        """Test that authorize-url endpoint requires authentication."""
        response = client.get("/oauth/strava/authorize-url")
        assert response.status_code == 401


class TestStravaCallback:
    """Test GET /oauth/strava/callback endpoint."""

    def test_callback_missing_code(self, client: TestClient):
        """Test callback endpoint when code is missing."""
        response = client.get("/oauth/strava/callback")

        assert response.status_code == 400
        assert "No code provided" in response.json()["detail"]

    @patch("fitness.app.routers.oauth.upsert_credentials")
    def test_callback_success(self, mock_upsert, client: TestClient):
        """Test successful OAuth callback."""
        # Mock the token exchange
        future_date = datetime.now(timezone.utc).replace(year=2030, month=12, day=31)
        mock_token = type(
            "Token",
            (),
            {
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "expires_at_datetime": lambda self=None: future_date,
            },
        )()

        with patch(
            "fitness.app.routers.oauth.strava.exchange_code_for_token",
            new_callable=AsyncMock,
        ) as mock_exchange:
            mock_exchange.return_value = mock_token
            with patch("fitness.app.routers.oauth.strava.CLIENT_ID", "test_client_id"):
                with patch(
                    "fitness.app.routers.oauth.strava.CLIENT_SECRET", "test_secret"
                ):
                    with patch(
                        "fitness.app.routers.oauth.PUBLIC_DASHBOARD_BASE_URL",
                        "https://dashboard.example.com",
                    ):
                        response = client.get(
                            "/oauth/strava/callback?code=test_code",
                            follow_redirects=False,
                        )

        assert response.status_code == 307  # Temporary redirect
        assert response.headers["location"] == "https://dashboard.example.com"

        # Verify token exchange was called
        mock_exchange.assert_called_once_with("test_code")

        # Verify credentials were saved
        mock_upsert.assert_called_once()
        saved_creds = mock_upsert.call_args[0][0]
        assert isinstance(saved_creds, OAuthCredentials)
        assert saved_creds.provider == "strava"
        assert saved_creds.access_token == "new_access_token"
        assert saved_creds.refresh_token == "new_refresh_token"
        assert saved_creds.client_id == "test_client_id"
        assert saved_creds.client_secret == "test_secret"


class TestGoogleAuthStatus:
    """Test GET /oauth/google/status endpoint."""

    def test_status_no_credentials(self, viewer_client: TestClient):
        """Test status endpoint when no credentials exist."""
        with patch("fitness.app.routers.oauth.get_credentials", return_value=None):
            response = viewer_client.get("/oauth/google/status")

        assert response.status_code == 200
        data = response.json()
        assert data["authorized"] is False
        assert data["access_token_valid"] is None
        assert data["expires_at"] is None

    def test_status_with_valid_credentials(self, viewer_client: TestClient):
        """Test status endpoint when valid credentials exist."""
        future_expiry = datetime.now(timezone.utc).replace(year=2030, month=12, day=31)
        creds = OAuthCredentials(
            provider="google",
            client_id="test_client_id",
            client_secret="test_secret",
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_at=future_expiry,
        )

        with patch("fitness.app.routers.oauth.get_credentials", return_value=creds):
            response = viewer_client.get("/oauth/google/status")

        assert response.status_code == 200
        data = response.json()
        assert data["authorized"] is True
        assert data["access_token_valid"] is True
        assert data["expires_at"] is not None

    def test_status_with_expired_credentials(self, viewer_client: TestClient):
        """Test status endpoint when credentials are expired."""
        past_expiry = datetime.now(timezone.utc).replace(year=2020, month=1, day=1)
        creds = OAuthCredentials(
            provider="google",
            client_id="test_client_id",
            client_secret="test_secret",
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_at=past_expiry,
        )

        with patch("fitness.app.routers.oauth.get_credentials", return_value=creds):
            response = viewer_client.get("/oauth/google/status")

        assert response.status_code == 200
        data = response.json()
        assert data["authorized"] is True
        assert data["access_token_valid"] is False

    def test_status_requires_auth(self, client: TestClient):
        """Test that status endpoint requires authentication."""
        response = client.get("/oauth/google/status")
        assert response.status_code == 401


class TestGoogleAuthorize:
    """Test GET /oauth/google/authorize endpoint."""

    def test_authorize_redirects(self, editor_client: TestClient):
        """Test that authorize endpoint redirects to Google OAuth URL."""
        with patch(
            "fitness.app.routers.oauth.google.auth.build_oauth_authorize_url"
        ) as mock_build:
            mock_build.return_value = (
                "https://accounts.google.com/o/oauth2/v2/auth?client_id=123"
            )
            with patch(
                "fitness.app.routers.oauth.PUBLIC_API_BASE_URL",
                "https://api.example.com",
            ):
                response = editor_client.get(
                    "/oauth/google/authorize", follow_redirects=False
                )

        assert response.status_code == 307  # Temporary redirect
        assert (
            response.headers["location"]
            == "https://accounts.google.com/o/oauth2/v2/auth?client_id=123"
        )
        mock_build.assert_called_once_with(
            redirect_uri="https://api.example.com/oauth/google/callback"
        )

    def test_authorize_requires_editor(self, viewer_client: TestClient):
        """Test that authorize endpoint requires editor role."""
        response = viewer_client.get("/oauth/google/authorize", follow_redirects=False)
        assert response.status_code == 403


class TestGoogleAuthorizeUrl:
    """Test GET /oauth/google/authorize-url endpoint."""

    def test_authorize_url_returns_json(self, editor_client: TestClient):
        """Test that authorize-url endpoint returns URL as JSON."""
        with patch(
            "fitness.app.routers.oauth.google.auth.build_oauth_authorize_url"
        ) as mock_build:
            mock_build.return_value = (
                "https://accounts.google.com/o/oauth2/v2/auth?client_id=123"
            )
            with patch(
                "fitness.app.routers.oauth.PUBLIC_API_BASE_URL",
                "https://api.example.com",
            ):
                response = editor_client.get("/oauth/google/authorize-url")

        assert response.status_code == 200
        data = response.json()
        assert (
            data["url"] == "https://accounts.google.com/o/oauth2/v2/auth?client_id=123"
        )
        mock_build.assert_called_once_with(
            redirect_uri="https://api.example.com/oauth/google/callback"
        )

    def test_authorize_url_requires_editor(self, viewer_client: TestClient):
        """Test that authorize-url endpoint requires editor role."""
        response = viewer_client.get("/oauth/google/authorize-url")
        assert response.status_code == 403

    def test_authorize_url_requires_auth(self, client: TestClient):
        """Test that authorize-url endpoint requires authentication."""
        response = client.get("/oauth/google/authorize-url")
        assert response.status_code == 401


class TestGoogleCallback:
    """Test GET /oauth/google/callback endpoint."""

    def test_callback_missing_code(self, client: TestClient):
        """Test callback endpoint when code is missing."""
        response = client.get("/oauth/google/callback")

        assert response.status_code == 400
        assert "No code provided" in response.json()["detail"]

    def test_callback_with_error(self, client: TestClient):
        """Test callback endpoint when Google returns an error."""
        response = client.get("/oauth/google/callback?error=access_denied")

        assert response.status_code == 400
        assert "Google OAuth authorization failed" in response.json()["detail"]
        assert "access_denied" in response.json()["detail"]

    @patch("fitness.app.routers.oauth.upsert_credentials")
    def test_callback_success(self, mock_upsert, client: TestClient):
        """Test successful OAuth callback."""
        # Mock the token exchange
        future_date = datetime.now(timezone.utc).replace(year=2030, month=12, day=31)
        mock_token = type(
            "Token",
            (),
            {
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "expires_at_datetime": lambda self=None: future_date,
            },
        )()

        with patch(
            "fitness.app.routers.oauth.google.auth.exchange_code_for_token",
            new_callable=AsyncMock,
        ) as mock_exchange:
            mock_exchange.return_value = mock_token
            with patch(
                "fitness.app.routers.oauth.google.auth.GOOGLE_CLIENT_ID",
                "test_client_id",
            ):
                with patch(
                    "fitness.app.routers.oauth.google.auth.GOOGLE_CLIENT_SECRET",
                    "test_secret",
                ):
                    with patch(
                        "fitness.app.routers.oauth.PUBLIC_DASHBOARD_BASE_URL",
                        "https://dashboard.example.com",
                    ):
                        response = client.get(
                            "/oauth/google/callback?code=test_code",
                            follow_redirects=False,
                        )

        assert response.status_code == 307  # Temporary redirect
        assert response.headers["location"] == "https://dashboard.example.com"

        # Verify token exchange was called
        mock_exchange.assert_called_once_with("test_code")

        # Verify credentials were saved
        mock_upsert.assert_called_once()
        saved_creds = mock_upsert.call_args[0][0]
        assert isinstance(saved_creds, OAuthCredentials)
        assert saved_creds.provider == "google"
        assert saved_creds.access_token == "new_access_token"
        assert saved_creds.refresh_token == "new_refresh_token"
        assert saved_creds.client_id == "test_client_id"
        assert saved_creds.client_secret == "test_secret"

    @patch("fitness.app.routers.oauth.upsert_credentials")
    def test_callback_no_refresh_token(self, mock_upsert, client: TestClient):
        """Test callback when Google doesn't return a refresh token."""
        mock_token = type(
            "Token",
            (),
            {
                "access_token": "new_access_token",
                "refresh_token": None,  # No refresh token
                "expires_at_datetime": lambda self=None: None,
            },
        )()

        with patch(
            "fitness.app.routers.oauth.google.auth.exchange_code_for_token",
            new_callable=AsyncMock,
        ) as mock_exchange:
            mock_exchange.return_value = mock_token
            response = client.get("/oauth/google/callback?code=test_code")

        assert response.status_code == 502
        assert "refresh token" in response.json()["detail"].lower()
        # Should not have saved credentials
        mock_upsert.assert_not_called()
