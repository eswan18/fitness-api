"""Create runs and shoes tables

Revision ID: 0001
Revises:
Create Date: 2024-12-17 22:09:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create shoes table first (needed for foreign key reference)
    op.execute("""
        CREATE TABLE shoes (
            id VARCHAR(255) PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            retired_at DATE,
            notes TEXT,
            retirement_notes TEXT,
            deleted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create runs table with foreign key to shoes
    op.execute("""
        CREATE TABLE runs (
            id VARCHAR(255) PRIMARY KEY,
            datetime_utc TIMESTAMP NOT NULL,
            type VARCHAR(50) NOT NULL CHECK (type IN ('Outdoor Run', 'Treadmill Run')),
            distance FLOAT NOT NULL,
            duration FLOAT NOT NULL,
            source VARCHAR(50) NOT NULL CHECK (source IN ('MapMyFitness', 'Strava')),
            avg_heart_rate FLOAT,
            shoe_id VARCHAR(255) REFERENCES shoes(id),
            deleted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for common queries on runs table (will be large)
    op.execute("CREATE INDEX idx_runs_datetime_utc ON runs (datetime_utc)")
    op.execute("CREATE INDEX idx_runs_source ON runs (source)")
    op.execute("CREATE INDEX idx_runs_shoe_id ON runs (shoe_id)")

    # No indexes needed for shoes table - it will be small


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS runs")
    op.execute("DROP TABLE IF EXISTS shoes")
