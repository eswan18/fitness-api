"""Add sync_metadata table for tracking incremental sync timestamps.

Revision ID: 09ac6bfc26af
Revises: add_lifts_tables
Create Date: 2026-01-28 05:39:58.106509+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "09ac6bfc26af"
down_revision: Union[str, Sequence[str], None] = "add_lifts_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create sync_metadata table for tracking last sync time per provider."""
    op.execute("""
        CREATE TABLE sync_metadata (
            provider VARCHAR(50) PRIMARY KEY,
            last_synced_at TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)


def downgrade() -> None:
    """Drop sync_metadata table."""
    op.execute("DROP TABLE IF EXISTS sync_metadata")
