"""JWT validation for OAuth 2.0 access tokens and role-based authorization."""

import os
import time
import logging
from typing import Optional, Dict, Any
from uuid import UUID

import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, status, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from fitness.models.user import User
from fitness.db.users import get_or_create_user

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
    """Get expected JWT audience from environment.

    This is a required environment variable validated at startup.
    """
    return os.environ["JWT_AUDIENCE"]


def get_jwks_client() -> PyJWKClient:
    """Get or refresh JWKS client for JWT validation."""
    global _jwks_client, _jwks_cache_time

    current_time = time.time()
    if _jwks_client is None or (current_time - _jwks_cache_time) > JWKS_CACHE_DURATION:
        identity_url = get_identity_provider_url()
        jwks_url = f"{identity_url}/.well-known/jwks.json"
        _jwks_client = PyJWKClient(
            jwks_url, cache_keys=True, lifespan=JWKS_CACHE_DURATION
        )
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


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth_scheme),
) -> User:
    """FastAPI dependency to get the current authenticated user.

    Validates the JWT token, extracts claims, and gets or creates the user record.
    User profile (email, username) is updated on each login.

    Returns:
        User object with role information.

    Raises:
        HTTPException 401 if token is missing or invalid.
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

    # Extract required claims
    sub = claims.get("sub")
    if not sub:
        logger.error(f"JWT missing sub claim: {claims}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token missing required claims",
        )

    # Extract optional profile claims
    email = claims.get("email")
    username = claims.get("username")

    # Get or create user, updating profile info
    try:
        idp_user_id = UUID(sub)
    except ValueError:
        logger.error(f"Invalid UUID in sub claim: {sub}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid token claims",
        )

    user = get_or_create_user(idp_user_id, email, username)
    return user


async def require_viewer(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency requiring at least viewer role.

    Any authenticated user can access (viewer or editor).
    This is the minimum authorization level for protected endpoints.

    Returns:
        User object.
    """
    # All authenticated users have at least viewer access
    return user


async def require_editor(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency requiring editor role.

    Only users with 'editor' role can access.
    Used for endpoints that modify data.

    Returns:
        User object if authorized.

    Raises:
        HTTPException 403 if user doesn't have editor role.
    """
    if user.role != "editor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor access required",
        )
    return user


def get_trmnl_api_key() -> str:
    """Get TRMNL API key from environment.

    Raises:
        HTTPException 500 if TRMNL_API_KEY is not configured.
    """
    key = os.getenv("TRMNL_API_KEY")
    if not key:
        logger.error("TRMNL_API_KEY environment variable is not set")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key authentication is not configured",
        )
    return key


async def require_viewer_or_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(oauth_scheme),
    x_api_key: str | None = Header(None),
) -> User | None:
    """FastAPI dependency allowing either OAuth or API key authentication.

    Tries JWT Bearer token first. If not present or invalid, falls back to
    checking the X-API-Key header against the TRMNL_API_KEY environment variable.

    Returns:
        User object if authenticated via OAuth, None if authenticated via API key.

    Raises:
        HTTPException 401 if neither authentication method succeeds.
    """
    # Try OAuth first
    if credentials:
        claims = validate_jwt_token(credentials.credentials)
        if claims:
            sub = claims.get("sub")
            if sub:
                try:
                    idp_user_id = UUID(sub)
                    email = claims.get("email")
                    username = claims.get("username")
                    return get_or_create_user(idp_user_id, email, username)
                except ValueError:
                    logger.warning(f"Invalid UUID in sub claim: {sub}")

    # Fall back to API key
    if x_api_key:
        expected_key = get_trmnl_api_key()
        if x_api_key == expected_key:
            logger.debug("Authenticated via API key")
            return None

    # Neither method succeeded
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication",
        headers={"WWW-Authenticate": "Bearer"},
    )
