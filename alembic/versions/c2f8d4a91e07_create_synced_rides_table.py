"""Create synced_rides table

Revision ID: c2f8d4a91e07
Revises: b3a7e9f2c1d4
Create Date: 2026-05-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c2f8d4a91e07"
down_revision: Union[str, Sequence[str], None] = "b3a7e9f2c1d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE synced_rides (
            id SERIAL PRIMARY KEY,
            ride_id VARCHAR(255) NOT NULL,
            ride_version INTEGER NOT NULL DEFAULT 1,
            google_event_id VARCHAR(255) NOT NULL,
            synced_at TIMESTAMP NOT NULL DEFAULT NOW(),
            sync_status VARCHAR(20) NOT NULL DEFAULT 'synced' CHECK (sync_status IN ('synced', 'failed', 'pending')),
            error_message TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_synced_rides_ride_id FOREIGN KEY (ride_id) REFERENCES rides(id),
            CONSTRAINT uq_synced_rides_ride_id UNIQUE (ride_id)
        );

        CREATE INDEX idx_synced_rides_ride_id ON synced_rides(ride_id);
        CREATE INDEX idx_synced_rides_sync_status ON synced_rides(sync_status);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS synced_rides CASCADE;")
