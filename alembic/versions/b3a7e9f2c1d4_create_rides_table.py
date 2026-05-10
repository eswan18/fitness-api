"""Create rides table

Revision ID: b3a7e9f2c1d4
Revises: 6dda1ac0535c
Create Date: 2026-05-09 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b3a7e9f2c1d4"
down_revision: Union[str, Sequence[str], None] = "6dda1ac0535c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE rides (
            id VARCHAR(255) PRIMARY KEY,
            datetime_utc TIMESTAMP NOT NULL,
            type VARCHAR(50) NOT NULL CHECK (type IN ('Outdoor Ride', 'Indoor Ride')),
            distance FLOAT NOT NULL,
            duration FLOAT NOT NULL,
            source VARCHAR(50) NOT NULL CHECK (source IN ('Strava')),
            avg_heart_rate FLOAT,
            deleted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("CREATE INDEX idx_rides_datetime_utc ON rides (datetime_utc)")
    op.execute("CREATE INDEX idx_rides_source ON rides (source)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS rides")
