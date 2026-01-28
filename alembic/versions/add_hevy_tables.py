"""Add Hevy workout tables

Revision ID: add_hevy_tables
Revises: d982550cf8a6
Create Date: 2025-01-27

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "add_hevy_tables"
down_revision: Union[str, Sequence[str], None] = "a01ab67814b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Hevy workout and exercise template tables."""

    # Create hevy_exercise_templates table for caching exercise metadata (muscle groups)
    op.execute("""
        CREATE TABLE hevy_exercise_templates (
            id VARCHAR(255) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            type VARCHAR(100),
            primary_muscle_group VARCHAR(100),
            secondary_muscle_groups TEXT[],
            is_custom BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create hevy_workouts table
    op.execute("""
        CREATE TABLE hevy_workouts (
            id VARCHAR(255) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            start_time TIMESTAMP WITH TIME ZONE NOT NULL,
            end_time TIMESTAMP WITH TIME ZONE NOT NULL,
            exercises JSONB NOT NULL DEFAULT '[]',
            total_volume_kg FLOAT,
            total_sets INT,
            hevy_created_at TIMESTAMP WITH TIME ZONE,
            hevy_updated_at TIMESTAMP WITH TIME ZONE,
            deleted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for common queries
    op.execute("CREATE INDEX idx_hevy_workouts_start_time ON hevy_workouts (start_time)")
    op.execute("CREATE INDEX idx_hevy_workouts_deleted_at ON hevy_workouts (deleted_at)")
    op.execute(
        "CREATE INDEX idx_hevy_exercise_templates_muscle "
        "ON hevy_exercise_templates (primary_muscle_group)"
    )


def downgrade() -> None:
    """Drop Hevy tables."""
    op.execute("DROP TABLE IF EXISTS hevy_workouts")
    op.execute("DROP TABLE IF EXISTS hevy_exercise_templates")
