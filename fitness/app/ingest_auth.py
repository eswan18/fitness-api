"""Bearer-token auth for ingestion endpoints (separate from human OAuth/JWT).

A request must carry ``Authorization: Bearer fitapi_…``. The token is hashed and
matched against an active (non-revoked, non-expired) row in ``api_tokens``.
"""

import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from fitness.auth.tokens import hash_token
from fitness.db.api_tokens import get_active_token_by_hash, touch_last_used

logger = logging.getLogger(__name__)

ingest_scheme = HTTPBearer(auto_error=False)


async def require_ingest_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(ingest_scheme),
) -> str:
    """Validate the bearer token and return its name (for attribution).

    Raises 401 if the header is missing or the token is not active.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = get_active_token_by_hash(hash_token(credentials.credentials))
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    touch_last_used(token.id)
    # Attach the token name so handlers/logs can attribute the request.
    request.state.ingest_token_name = token.name
    logger.info("Ingest request authenticated via token '%s'", token.name)
    return token.name
