"""add tags tables

Revision ID: 62128cf4b300
Revises: 9d4c4e3c66b3
Create Date: 2026-07-01 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "62128cf4b300"
down_revision: Union[str, Sequence[str], None] = "9d4c4e3c66b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE tags (
            id VARCHAR(255) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMP
        );
        CREATE UNIQUE INDEX idx_tags_name_lower ON tags (LOWER(name)) WHERE deleted_at IS NULL;
        CREATE INDEX idx_tags_deleted_at ON tags(deleted_at);

        CREATE TABLE run_tags (
            run_id VARCHAR(255) NOT NULL REFERENCES runs(id),
            tag_id VARCHAR(255) NOT NULL REFERENCES tags(id),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            PRIMARY KEY (run_id, tag_id)
        );
        CREATE INDEX idx_run_tags_tag_id ON run_tags(tag_id);

        CREATE TABLE ride_tags (
            ride_id VARCHAR(255) NOT NULL REFERENCES rides(id),
            tag_id VARCHAR(255) NOT NULL REFERENCES tags(id),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            PRIMARY KEY (ride_id, tag_id)
        );
        CREATE INDEX idx_ride_tags_tag_id ON ride_tags(tag_id);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        DROP TABLE IF EXISTS ride_tags;
        DROP TABLE IF EXISTS run_tags;
        DROP TABLE IF EXISTS tags;
    """)
