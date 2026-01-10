"""JWT validation for OAuth 2.0 access tokens."""

import os
import time
import logging
from typing import Optional, Dict, Any

import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)
oauth_scheme = HTTPBearer(auto_error=False)

# JWKS client cache
_jwks_client: Optional[PyJWKClient] = None
_jwks_cache_time: float = 0
JWKS_CACHE_DURATION = 3600  # 1 hour


def get_identity_provider_url() -> str:
    """Get identity provider base URL from environment."""
    url = os.getenv("IDENTITY_PROVIDER_URL", "http://localhost:8080")
    return url.rstrip("/")


def get_jwt_audience() -> str:
    """Get expected JWT audience from environment."""
    return os.getenv("JWT_AUDIENCE", "http://localhost:8000")


def get_jwks_client() -> PyJWKClient:
    """Get or refresh JWKS client for JWT validation."""
    global _jwks_client, _jwks_cache_time

    current_time = time.time()
    if _jwks_client is None or (current_time - _jwks_cache_time) > JWKS_CACHE_DURATION:
        identity_url = get_identity_provider_url()
        jwks_url = f"{identity_url}/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=JWKS_CACHE_DURATION)
        _jwks_cache_time = current_time
        logger.info(f"Refreshed JWKS client from {jwks_url}")

    return _jwks_client


def validate_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate JWT access token locally using JWKS.

    Returns decoded claims if valid, None if invalid.
    """
    try:
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        identity_url = get_identity_provider_url()
        audience = get_jwt_audience()

        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            issuer=identity_url,
            audience=audience,
            options={"require": ["exp", "iss", "sub", "aud"]},
        )
        return decoded
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None
    except Exception as e:
        logger.error(f"JWT validation error: {e}")
        return None


async def verify_oauth_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth_scheme),
) -> str:
    """FastAPI dependency to verify OAuth access token.

    Returns username if valid, raises 401 if invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    claims = validate_jwt_token(token)

    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = claims.get("username")
    if not username:
        logger.error(f"JWT missing username claim: {claims}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token missing required claims",
        )

    return username
