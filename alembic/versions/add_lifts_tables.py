"""Add lifts and exercise_templates tables

Revision ID: add_lifts_tables
Revises: a01ab67814b6
Create Date: 2025-01-27

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "add_lifts_tables"
down_revision: Union[str, Sequence[str], None] = "a01ab67814b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create lifts and exercise_templates tables."""

    # Create exercise_templates table for caching exercise metadata (muscle groups)
    op.execute("""
        CREATE TABLE exercise_templates (
            id VARCHAR(255) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            source VARCHAR(50) NOT NULL,
            type VARCHAR(100),
            primary_muscle_group VARCHAR(100),
            secondary_muscle_groups TEXT[],
            is_custom BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create lifts table
    op.execute("""
        CREATE TABLE lifts (
            id VARCHAR(255) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            source VARCHAR(50) NOT NULL,
            description TEXT,
            start_time TIMESTAMP WITH TIME ZONE NOT NULL,
            end_time TIMESTAMP WITH TIME ZONE NOT NULL,
            exercises JSONB NOT NULL DEFAULT '[]',
            total_volume_kg FLOAT,
            total_sets INT,
            deleted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for common queries
    op.execute("CREATE INDEX idx_lifts_start_time ON lifts (start_time)")
    op.execute("CREATE INDEX idx_lifts_deleted_at ON lifts (deleted_at)")
    op.execute(
        "CREATE INDEX idx_exercise_templates_muscle "
        "ON exercise_templates (primary_muscle_group)"
    )


def downgrade() -> None:
    """Drop lifts and exercise_templates tables."""
    op.execute("DROP TABLE IF EXISTS lifts")
    op.execute("DROP TABLE IF EXISTS exercise_templates")
