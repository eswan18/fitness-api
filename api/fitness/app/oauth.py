"""OAuth 2.0 token validation via UserInfo endpoint."""

import os
import logging
import httpx
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# OAuth security scheme
oauth_scheme = HTTPBearer(auto_error=False)


def get_identity_provider_url() -> str:
    """Get identity provider base URL from environment."""
    url = os.getenv("IDENTITY_PROVIDER_URL", "http://localhost:8080")
    return url.rstrip("/")


async def validate_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate access token via UserInfo endpoint.

    Returns user info dict if valid, None if invalid.
    """
    try:
        identity_url = get_identity_provider_url()
        userinfo_url = f"{identity_url}/oauth/userinfo"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            logger.warning("Invalid or expired token")
            return None
        else:
            logger.error(
                f"Unexpected response from UserInfo: {response.status_code}"
            )
            return None
    except Exception as e:
        logger.error(f"Token validation error: {e}")
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
    user_info = await validate_access_token(token)

    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract username from user info, checking for its existence
    username = user_info.get("username")
    if not username:
        logger.error(f"UserInfo response missing username field: {user_info}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Identity provider returned incomplete user information",
        )

    return username
