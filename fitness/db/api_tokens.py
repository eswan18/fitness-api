"""Database operations for per-service API tokens (ingestion auth).

Tokens are stored as a SHA-256 hash plus a non-secret identifying prefix. See
``fitness/auth/tokens.py`` for the hashing rationale.
"""

import logging
from datetime import datetime

from pydantic import BaseModel

from .connection import get_db_cursor

logger = logging.getLogger(__name__)

# Columns selected for an ApiToken (never includes token_hash).
_COLUMNS = "id, name, prefix, created_at, expires_at, last_used_at, revoked_at"

# Skip a last_used_at write if the token was already touched within this window,
# to avoid a DB write on every single authenticated request (Neon write cost).
_TOUCH_THROTTLE = "1 minute"


class ApiToken(BaseModel):
    id: int
    name: str
    prefix: str
    created_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


def create_api_token(
    name: str,
    token_hash: str,
    prefix: str,
    expires_at: datetime | None = None,
) -> ApiToken:
    """Insert a new token row and return it (without the raw token or hash)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO api_tokens (name, token_hash, prefix, expires_at)
            VALUES (%s, %s, %s, %s)
            RETURNING {_COLUMNS}
            """,
            (name, token_hash, prefix, expires_at),
        )
        return _row_to_token(cursor.fetchone())


def get_active_token_by_hash(token_hash: str) -> ApiToken | None:
    """Return the matching token iff it is active (not revoked, not expired)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {_COLUMNS}
            FROM api_tokens
            WHERE token_hash = %s
              AND revoked_at IS NULL
              AND (expires_at IS NULL OR expires_at > NOW())
            """,
            (token_hash,),
        )
        row = cursor.fetchone()
        return _row_to_token(row) if row else None


def touch_last_used(token_id: int) -> None:
    """Best-effort update of last_used_at; never raises into the request path.

    Throttled so a token used in a burst only writes once per minute.
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE api_tokens
                SET last_used_at = NOW()
                WHERE id = %s
                  AND (last_used_at IS NULL
                       OR last_used_at < NOW() - INTERVAL '{_TOUCH_THROTTLE}')
                """,
                (token_id,),
            )
    except Exception:
        logger.warning("Failed to update last_used_at for token %s", token_id)


def list_api_tokens(include_revoked: bool = False) -> list[ApiToken]:
    """List tokens, newest first. Excludes revoked tokens unless requested."""
    with get_db_cursor() as cursor:
        where = "" if include_revoked else "WHERE revoked_at IS NULL"
        cursor.execute(
            f"""
            SELECT {_COLUMNS}
            FROM api_tokens
            {where}
            ORDER BY created_at DESC
            """
        )
        return [_row_to_token(row) for row in cursor.fetchall()]


def revoke_api_token(*, token_id: int | None = None, prefix: str | None = None) -> bool:
    """Revoke a token by id or prefix. Returns True if a row was revoked."""
    if (token_id is None) == (prefix is None):
        raise ValueError("Pass exactly one of token_id or prefix")
    with get_db_cursor() as cursor:
        if token_id is not None:
            cursor.execute(
                "UPDATE api_tokens SET revoked_at = NOW() "
                "WHERE id = %s AND revoked_at IS NULL",
                (token_id,),
            )
        else:
            cursor.execute(
                "UPDATE api_tokens SET revoked_at = NOW() "
                "WHERE prefix = %s AND revoked_at IS NULL",
                (prefix,),
            )
        return cursor.rowcount > 0


def _row_to_token(row) -> ApiToken:
    id, name, prefix, created_at, expires_at, last_used_at, revoked_at = row
    return ApiToken(
        id=id,
        name=name,
        prefix=prefix,
        created_at=created_at,
        expires_at=expires_at,
        last_used_at=last_used_at,
        revoked_at=revoked_at,
    )
