"""add synced_lifts table for google calendar sync

Revision ID: fb8efa3c6e02
Revises: 09ac6bfc26af
Create Date: 2026-01-30 04:03:05.044605+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'fb8efa3c6e02'
down_revision: Union[str, Sequence[str], None] = '09ac6bfc26af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE synced_lifts (
            id SERIAL PRIMARY KEY,
            lift_id VARCHAR(255) NOT NULL,
            lift_version INTEGER NOT NULL DEFAULT 1,
            google_event_id VARCHAR(255) NOT NULL,
            synced_at TIMESTAMP NOT NULL DEFAULT NOW(),
            sync_status VARCHAR(20) NOT NULL DEFAULT 'synced'
                CHECK (sync_status IN ('synced', 'failed', 'pending')),
            error_message TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_synced_lifts_lift_id FOREIGN KEY (lift_id) REFERENCES lifts(id),
            CONSTRAINT uq_synced_lifts_lift_id UNIQUE (lift_id)
        );

        CREATE INDEX idx_synced_lifts_lift_id ON synced_lifts(lift_id);
        CREATE INDEX idx_synced_lifts_sync_status ON synced_lifts(sync_status);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS synced_lifts;")