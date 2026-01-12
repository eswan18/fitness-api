"""Tests for JWT validation logic in oauth.py.

These tests verify the actual JWT validation, not mocked versions.
"""

import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend

from fitness.app.oauth import (
    validate_jwt_token,
    get_jwks_client,
    get_identity_provider_url,
    get_jwt_audience,
    JWKS_CACHE_DURATION,
)


# Generate a test EC key pair for signing JWTs
def generate_ec_key_pair():
    """Generate an EC P-256 key pair for testing."""
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    public_key = private_key.public_key()
    return private_key, public_key


# Test fixtures
@pytest.fixture
def ec_key_pair():
    """Generate a fresh EC key pair for each test."""
    return generate_ec_key_pair()


@pytest.fixture
def mock_jwks_client(ec_key_pair):
    """Create a mock JWKS client that returns our test public key."""
    _, public_key = ec_key_pair

    mock_client = MagicMock()
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

    return mock_client


def create_test_token(
    private_key,
    issuer: str = "http://localhost:8080",
    audience: str = "test-audience",
    subject: str = "user-123",
    expires_in: int = 3600,
    extra_claims: dict | None = None,
    algorithm: str = "ES256",
) -> str:
    """Create a signed JWT token for testing."""
    now = datetime.now(timezone.utc)
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "exp": now + timedelta(seconds=expires_in),
        "iat": now,
        "username": "test_user",
        "email": "test@example.com",
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, private_key, algorithm=algorithm)


class TestValidateJwtToken:
    """Test the validate_jwt_token function."""

    def test_valid_token(self, ec_key_pair, mock_jwks_client):
        """Test that a valid token returns decoded claims."""
        private_key, _ = ec_key_pair

        token = create_test_token(
            private_key,
            issuer="http://localhost:8080",
            audience="test-audience",
        )

        with patch("fitness.app.oauth.get_jwks_client", return_value=mock_jwks_client):
            with patch(
                "fitness.app.oauth.get_identity_provider_url",
                return_value="http://localhost:8080",
            ):
                with patch(
                    "fitness.app.oauth.get_jwt_audience", return_value="test-audience"
                ):
                    claims = validate_jwt_token(token)

        assert claims is not None
        assert claims["sub"] == "user-123"
        assert claims["username"] == "test_user"
        assert claims["email"] == "test@example.com"
        assert claims["iss"] == "http://localhost:8080"
        assert claims["aud"] == "test-audience"

    def test_expired_token(self, ec_key_pair, mock_jwks_client):
        """Test that an expired token returns None."""
        private_key, _ = ec_key_pair

        # Create a token that expired 1 hour ago
        token = create_test_token(
            private_key,
            issuer="http://localhost:8080",
            audience="test-audience",
            expires_in=-3600,  # Expired 1 hour ago
        )

        with patch("fitness.app.oauth.get_jwks_client", return_value=mock_jwks_client):
            with patch(
                "fitness.app.oauth.get_identity_provider_url",
                return_value="http://localhost:8080",
            ):
                with patch(
                    "fitness.app.oauth.get_jwt_audience", return_value="test-audience"
                ):
                    claims = validate_jwt_token(token)

        assert claims is None

    def test_wrong_issuer(self, ec_key_pair, mock_jwks_client):
        """Test that a token with wrong issuer returns None."""
        private_key, _ = ec_key_pair

        token = create_test_token(
            private_key,
            issuer="http://wrong-issuer.com",
            audience="test-audience",
        )

        with patch("fitness.app.oauth.get_jwks_client", return_value=mock_jwks_client):
            with patch(
                "fitness.app.oauth.get_identity_provider_url",
                return_value="http://localhost:8080",
            ):
                with patch(
                    "fitness.app.oauth.get_jwt_audience", return_value="test-audience"
                ):
                    claims = validate_jwt_token(token)

        assert claims is None

    def test_wrong_audience(self, ec_key_pair, mock_jwks_client):
        """Test that a token with wrong audience returns None."""
        private_key, _ = ec_key_pair

        token = create_test_token(
            private_key,
            issuer="http://localhost:8080",
            audience="wrong-audience",
        )

        with patch("fitness.app.oauth.get_jwks_client", return_value=mock_jwks_client):
            with patch(
                "fitness.app.oauth.get_identity_provider_url",
                return_value="http://localhost:8080",
            ):
                with patch(
                    "fitness.app.oauth.get_jwt_audience", return_value="test-audience"
                ):
                    claims = validate_jwt_token(token)

        assert claims is None

    def test_invalid_signature(self, ec_key_pair, mock_jwks_client):
        """Test that a token signed with wrong key returns None."""
        # Generate a different key pair for signing
        wrong_private_key, _ = generate_ec_key_pair()

        token = create_test_token(
            wrong_private_key,  # Signed with wrong key
            issuer="http://localhost:8080",
            audience="test-audience",
        )

        with patch("fitness.app.oauth.get_jwks_client", return_value=mock_jwks_client):
            with patch(
                "fitness.app.oauth.get_identity_provider_url",
                return_value="http://localhost:8080",
            ):
                with patch(
                    "fitness.app.oauth.get_jwt_audience", return_value="test-audience"
                ):
                    claims = validate_jwt_token(token)

        assert claims is None

    def test_malformed_token(self, mock_jwks_client):
        """Test that a malformed token returns None."""
        with patch("fitness.app.oauth.get_jwks_client", return_value=mock_jwks_client):
            with patch(
                "fitness.app.oauth.get_identity_provider_url",
                return_value="http://localhost:8080",
            ):
                with patch(
                    "fitness.app.oauth.get_jwt_audience", return_value="test-audience"
                ):
                    claims = validate_jwt_token("not.a.valid.jwt.token")

        assert claims is None

    def test_missing_required_claims(self, ec_key_pair, mock_jwks_client):
        """Test that a token missing required claims returns None."""
        private_key, _ = ec_key_pair

        # Create a token without 'sub' claim
        now = datetime.now(timezone.utc)
        payload = {
            "iss": "http://localhost:8080",
            "aud": "test-audience",
            # Missing 'sub' claim
            "exp": now + timedelta(seconds=3600),
            "iat": now,
        }
        token = jwt.encode(payload, private_key, algorithm="ES256")

        with patch("fitness.app.oauth.get_jwks_client", return_value=mock_jwks_client):
            with patch(
                "fitness.app.oauth.get_identity_provider_url",
                return_value="http://localhost:8080",
            ):
                with patch(
                    "fitness.app.oauth.get_jwt_audience", return_value="test-audience"
                ):
                    claims = validate_jwt_token(token)

        assert claims is None

    def test_audience_as_list(self, ec_key_pair, mock_jwks_client):
        """Test that audience claim as a list is handled correctly."""
        private_key, _ = ec_key_pair

        # Create token with audience as list (common in OAuth)
        now = datetime.now(timezone.utc)
        payload = {
            "iss": "http://localhost:8080",
            "aud": ["test-audience", "other-audience"],  # List of audiences
            "sub": "user-123",
            "exp": now + timedelta(seconds=3600),
            "iat": now,
            "username": "test_user",
        }
        token = jwt.encode(payload, private_key, algorithm="ES256")

        with patch("fitness.app.oauth.get_jwks_client", return_value=mock_jwks_client):
            with patch(
                "fitness.app.oauth.get_identity_provider_url",
                return_value="http://localhost:8080",
            ):
                with patch(
                    "fitness.app.oauth.get_jwt_audience", return_value="test-audience"
                ):
                    claims = validate_jwt_token(token)

        # PyJWT should accept if expected audience is in the list
        assert claims is not None
        assert claims["sub"] == "user-123"


class TestGetJwksClient:
    """Test the JWKS client caching behavior."""

    def test_creates_new_client_on_first_call(self):
        """Test that a new JWKS client is created on first call."""
        # Reset the global cache
        import fitness.app.oauth as oauth_module

        oauth_module._jwks_client = None
        oauth_module._jwks_cache_time = 0

        with patch("fitness.app.oauth.PyJWKClient") as mock_client_class:
            with patch(
                "fitness.app.oauth.get_identity_provider_url",
                return_value="http://test.com",
            ):
                mock_instance = MagicMock()
                mock_client_class.return_value = mock_instance

                client = get_jwks_client()

                mock_client_class.assert_called_once_with(
                    "http://test.com/.well-known/jwks.json",
                    cache_keys=True,
                    lifespan=JWKS_CACHE_DURATION,
                )
                assert client == mock_instance

    def test_returns_cached_client_within_duration(self):
        """Test that cached client is returned within cache duration."""
        import fitness.app.oauth as oauth_module

        mock_client = MagicMock()
        oauth_module._jwks_client = mock_client
        oauth_module._jwks_cache_time = time.time()  # Just cached

        with patch("fitness.app.oauth.PyJWKClient") as mock_client_class:
            client = get_jwks_client()

            # Should not create new client
            mock_client_class.assert_not_called()
            assert client == mock_client

    def test_refreshes_client_after_cache_expires(self):
        """Test that client is refreshed after cache expires."""
        import fitness.app.oauth as oauth_module

        old_client = MagicMock()
        oauth_module._jwks_client = old_client
        oauth_module._jwks_cache_time = time.time() - JWKS_CACHE_DURATION - 1  # Expired

        with patch("fitness.app.oauth.PyJWKClient") as mock_client_class:
            with patch(
                "fitness.app.oauth.get_identity_provider_url",
                return_value="http://test.com",
            ):
                new_client = MagicMock()
                mock_client_class.return_value = new_client

                client = get_jwks_client()

                # Should create new client
                mock_client_class.assert_called_once()
                assert client == new_client
                assert client != old_client


class TestEnvironmentConfig:
    """Test environment variable configuration functions."""

    def test_get_identity_provider_url_default(self):
        """Test default identity provider URL."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove the env var if it exists
            import os

            os.environ.pop("IDENTITY_PROVIDER_URL", None)
            url = get_identity_provider_url()
            assert url == "http://localhost:8080"

    def test_get_identity_provider_url_from_env(self):
        """Test identity provider URL from environment."""
        with patch.dict(
            "os.environ", {"IDENTITY_PROVIDER_URL": "https://auth.example.com"}
        ):
            url = get_identity_provider_url()
            assert url == "https://auth.example.com"

    def test_get_identity_provider_url_strips_trailing_slash(self):
        """Test that trailing slash is stripped from URL."""
        with patch.dict(
            "os.environ", {"IDENTITY_PROVIDER_URL": "https://auth.example.com/"}
        ):
            url = get_identity_provider_url()
            assert url == "https://auth.example.com"

    def test_get_jwt_audience_from_env(self):
        """Test JWT audience from environment."""
        with patch.dict("os.environ", {"JWT_AUDIENCE": "my-api-audience"}):
            audience = get_jwt_audience()
            assert audience == "my-api-audience"

    def test_get_jwt_audience_raises_when_missing(self):
        """Test that missing JWT_AUDIENCE raises KeyError."""
        with patch.dict("os.environ", {}, clear=True):
            import os

            os.environ.pop("JWT_AUDIENCE", None)
            with pytest.raises(KeyError):
                get_jwt_audience()
