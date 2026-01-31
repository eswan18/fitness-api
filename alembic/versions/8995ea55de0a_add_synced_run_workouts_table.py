"""add synced_run_workouts table

Revision ID: 8995ea55de0a
Revises: a5f9c60f97e4
Create Date: 2026-01-31 04:04:45.990749+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '8995ea55de0a'
down_revision: Union[str, Sequence[str], None] = 'a5f9c60f97e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE synced_run_workouts (
            id SERIAL PRIMARY KEY,
            run_workout_id VARCHAR(255) NOT NULL,
            run_workout_version INTEGER NOT NULL DEFAULT 1,
            google_event_id VARCHAR(255),
            synced_at TIMESTAMP NOT NULL DEFAULT NOW(),
            sync_status VARCHAR(20) NOT NULL DEFAULT 'synced'
                CHECK (sync_status IN ('synced', 'failed', 'pending')),
            error_message TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_synced_run_workouts_id FOREIGN KEY (run_workout_id) REFERENCES run_workouts(id),
            CONSTRAINT uq_synced_run_workouts_id UNIQUE (run_workout_id)
        );
        CREATE INDEX idx_synced_run_workouts_id ON synced_run_workouts(run_workout_id);
        CREATE INDEX idx_synced_run_workouts_status ON synced_run_workouts(sync_status);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        DROP INDEX IF EXISTS idx_synced_run_workouts_status;
        DROP INDEX IF EXISTS idx_synced_run_workouts_id;
        DROP TABLE IF EXISTS synced_run_workouts;
    """)