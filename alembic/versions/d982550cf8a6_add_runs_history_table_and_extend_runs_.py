"""Add runs history table and extend runs table for edit tracking

Revision ID: d982550cf8a6
Revises: 0001
Create Date: 2025-08-07 03:14:52.665352+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d982550cf8a6"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create runs_history table for audit trail
    op.execute("""
        CREATE TABLE runs_history (
            history_id SERIAL PRIMARY KEY,
            run_id VARCHAR(255) NOT NULL,
            version_number INTEGER NOT NULL,
            change_type VARCHAR(20) NOT NULL CHECK (change_type IN ('original', 'edit', 'deletion')),
            
            -- Full snapshot of run data at this point in time
            datetime_utc TIMESTAMP NOT NULL,
            type VARCHAR(50) NOT NULL CHECK (type IN ('Outdoor Run', 'Treadmill Run')),
            distance FLOAT NOT NULL,
            duration FLOAT NOT NULL,
            source VARCHAR(50) NOT NULL CHECK (source IN ('MapMyFitness', 'Strava')),
            avg_heart_rate FLOAT,
            shoe_id VARCHAR(255),
            
            -- Edit metadata
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            changed_by VARCHAR(255),
            change_reason TEXT,
            
            -- Constraints
            CONSTRAINT unique_run_version UNIQUE (run_id, version_number),
            CONSTRAINT fk_runs_history_run_id FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
        )
    """)

    # Create indexes for performance on runs_history table
    op.execute("CREATE INDEX idx_runs_history_run_id ON runs_history (run_id)")
    op.execute(
        "CREATE INDEX idx_runs_history_run_id_version ON runs_history (run_id, version_number DESC)"
    )

    # Extend runs table with edit tracking columns
    op.execute("""
        ALTER TABLE runs 
        ADD COLUMN last_edited_at TIMESTAMP,
        ADD COLUMN last_edited_by VARCHAR(255),
        ADD COLUMN version INTEGER DEFAULT 1 NOT NULL
    """)

    # Create index on runs table for version queries
    op.execute("CREATE INDEX idx_runs_version ON runs (version)")


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes first
    op.execute("DROP INDEX IF EXISTS idx_runs_version")
    op.execute("DROP INDEX IF EXISTS idx_runs_history_run_id_version")
    op.execute("DROP INDEX IF EXISTS idx_runs_history_run_id")

    # Remove columns from runs table
    op.execute("""
        ALTER TABLE runs 
        DROP COLUMN IF EXISTS version,
        DROP COLUMN IF EXISTS last_edited_by,
        DROP COLUMN IF EXISTS last_edited_at
    """)

    # Drop runs_history table (CASCADE will handle foreign key constraints)
    op.execute("DROP TABLE IF EXISTS runs_history")
