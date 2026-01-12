"""Database operations for OAuth credentials."""

import logging
from datetime import datetime, timezone
from typing import Literal
from dataclasses import dataclass

from pydantic import BaseModel

from .connection import get_db_cursor, get_db_connection

OAuthProvider = Literal["google", "strava"]

logger = logging.getLogger(__name__)


@dataclass
class OAuthCredentials:
    """OAuth credentials for a provider."""

    provider: OAuthProvider
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def is_access_token_valid(self) -> bool | None:
        """Check if the access token is currently valid.

        Returns:
            True if the token is valid, False if expired, None if expiration is unknown
        """
        if self.expires_at is None:
            return None

        # Ensure expires_at is timezone-aware
        expires_at_aware = self.expires_at
        if expires_at_aware.tzinfo is None:
            expires_at_aware = expires_at_aware.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        return expires_at_aware > now

    def expires_at_iso(self) -> str | None:
        """Get the expiration time as an ISO format string.

        Returns:
            ISO format string of expires_at, or None if not set
        """
        if self.expires_at is None:
            return None
        return self.expires_at.isoformat()

    def integration_status(self) -> "OAuthIntegrationStatus":
        return OAuthIntegrationStatus(
            authorized=True,
            access_token_valid=self.is_access_token_valid(),
            expires_at=self.expires_at_iso(),
        )


class OAuthIntegrationStatus(BaseModel):
    """Status of OAuth integration for a provider."""

    authorized: bool
    access_token_valid: bool | None = None
    expires_at: str | None = None


def get_credentials(provider: OAuthProvider) -> OAuthCredentials | None:
    """Get OAuth credentials for a provider.

    Args:
        provider: Provider name (e.g., 'google')

    Returns:
        OAuthCredentials if found, None otherwise
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT provider, client_id, client_secret, access_token, refresh_token,
                   expires_at, created_at, updated_at
            FROM oauth_credentials
            WHERE provider = %s
            """,
            (provider,),
        )

        row = cursor.fetchone()
        if row is None:
            return None

        return OAuthCredentials(
            provider=row[0],
            client_id=row[1],
            client_secret=row[2],
            access_token=row[3],
            refresh_token=row[4],
            expires_at=row[5],
            created_at=row[6],
            updated_at=row[7],
        )


def upsert_credentials(credentials: OAuthCredentials) -> None:
    """Insert or update OAuth credentials for a provider.

    Args:
        provider: Provider name (e.g., 'google')
        client_id: OAuth client ID
        client_secret: OAuth client secret
        access_token: OAuth access token
        refresh_token: OAuth refresh token
        expires_at: Optional expiration timestamp for access token
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO oauth_credentials
                    (provider, client_id, client_secret, access_token, refresh_token, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (provider)
                DO UPDATE SET
                    client_id = EXCLUDED.client_id,
                    client_secret = EXCLUDED.client_secret,
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    expires_at = EXCLUDED.expires_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    credentials.provider,
                    credentials.client_id,
                    credentials.client_secret,
                    credentials.access_token,
                    credentials.refresh_token,
                    credentials.expires_at,
                ),
            )
            conn.commit()

    logger.info(f"Upserted OAuth credentials for provider: {credentials.provider}")


def update_access_token(
    provider: OAuthProvider,
    access_token: str,
    expires_at: datetime | None = None,
    refresh_token: str | None = None,
) -> None:
    """Update the access token for a provider, optionally updating refresh token.

    Args:
        provider: Provider name (e.g., 'google')
        access_token: New OAuth access token
        expires_at: Optional expiration timestamp for access token
        refresh_token: Optional new refresh token (if provided by OAuth provider)
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            if refresh_token:
                cursor.execute(
                    """
                    UPDATE oauth_credentials
                    SET access_token = %s,
                        refresh_token = %s,
                        expires_at = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE provider = %s
                    """,
                    (access_token, refresh_token, expires_at, provider),
                )
            else:
                cursor.execute(
                    """
                    UPDATE oauth_credentials
                    SET access_token = %s,
                        expires_at = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE provider = %s
                    """,
                    (access_token, expires_at, provider),
                )
            conn.commit()

    logger.info(f"Updated access token for provider: {provider}")


def credentials_exist(provider: OAuthProvider) -> bool:
    """Check if credentials exist for a provider.

    Args:
        provider: Provider name (e.g., 'google')

    Returns:
        True if credentials exist, False otherwise
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM oauth_credentials WHERE provider = %s",
            (provider,),
        )
        return cursor.fetchone() is not None
