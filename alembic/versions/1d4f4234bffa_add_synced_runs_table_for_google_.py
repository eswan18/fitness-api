"""Add synced_runs table for Google Calendar sync tracking

Revision ID: 1d4f4234bffa
Revises: d982550cf8a6
Create Date: 2025-08-10 03:40:34.738525+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1d4f4234bffa"
down_revision: Union[str, Sequence[str], None] = "d982550cf8a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE synced_runs (
            id SERIAL PRIMARY KEY,
            run_id VARCHAR(255) NOT NULL,
            run_version INTEGER NOT NULL DEFAULT 1,
            google_event_id VARCHAR(255) NOT NULL,
            synced_at TIMESTAMP NOT NULL DEFAULT NOW(),
            sync_status VARCHAR(20) NOT NULL DEFAULT 'synced' CHECK (sync_status IN ('synced', 'failed', 'pending')),
            error_message TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_synced_runs_run_id FOREIGN KEY (run_id) REFERENCES runs(id),
            CONSTRAINT uq_synced_runs_run_id UNIQUE (run_id)
        );
        
        -- Create index for faster lookups by run_id
        CREATE INDEX idx_synced_runs_run_id ON synced_runs(run_id);
        CREATE INDEX idx_synced_runs_sync_status ON synced_runs(sync_status);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        DROP TABLE IF EXISTS synced_runs CASCADE;
    """)
