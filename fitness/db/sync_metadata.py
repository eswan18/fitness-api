"""Database operations for sync metadata tracking."""

import logging
from datetime import datetime, timezone
from typing import Optional

from .connection import get_db_cursor

logger = logging.getLogger(__name__)


def get_last_sync_time(provider: str) -> Optional[datetime]:
    """Get the last successful sync time for a provider.

    Args:
        provider: The sync provider name (e.g., 'strava', 'hevy')

    Returns:
        The last sync datetime (timezone-aware UTC), or None if never synced.
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT last_synced_at
            FROM sync_metadata
            WHERE provider = %s
            """,
            (provider,),
        )
        row = cursor.fetchone()
        if row:
            last_synced_at = row[0]
            # Ensure timezone awareness
            if last_synced_at.tzinfo is None:
                last_synced_at = last_synced_at.replace(tzinfo=timezone.utc)
            return last_synced_at
        return None


def update_last_sync_time(provider: str, synced_at: Optional[datetime] = None) -> None:
    """Update the last successful sync time for a provider.

    Uses upsert to create the record if it doesn't exist.

    Args:
        provider: The sync provider name (e.g., 'strava', 'hevy')
        synced_at: The sync timestamp. Defaults to current UTC time.
    """
    if synced_at is None:
        synced_at = datetime.now(timezone.utc)

    # Ensure timezone awareness
    if synced_at.tzinfo is None:
        synced_at = synced_at.replace(tzinfo=timezone.utc)

    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO sync_metadata (provider, last_synced_at, updated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (provider)
            DO UPDATE SET
                last_synced_at = EXCLUDED.last_synced_at,
                updated_at = EXCLUDED.updated_at
            """,
            (provider, synced_at, synced_at),
        )

    logger.info(f"Updated last sync time for {provider}: {synced_at.isoformat()}")
