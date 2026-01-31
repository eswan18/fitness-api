"""add run_workouts table and runs FK

Revision ID: a5f9c60f97e4
Revises: fb8efa3c6e02
Create Date: 2026-01-31 01:17:57.872244+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a5f9c60f97e4'
down_revision: Union[str, Sequence[str], None] = 'fb8efa3c6e02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE run_workouts (
            id VARCHAR(255) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMP
        );
        CREATE INDEX idx_run_workouts_deleted_at ON run_workouts(deleted_at);

        ALTER TABLE runs ADD COLUMN run_workout_id VARCHAR(255)
            REFERENCES run_workouts(id) ON DELETE SET NULL;
        CREATE INDEX idx_runs_run_workout_id ON runs(run_workout_id);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        DROP INDEX IF EXISTS idx_runs_run_workout_id;
        ALTER TABLE runs DROP COLUMN IF EXISTS run_workout_id;
        DROP INDEX IF EXISTS idx_run_workouts_deleted_at;
        DROP TABLE IF EXISTS run_workouts;
    """)