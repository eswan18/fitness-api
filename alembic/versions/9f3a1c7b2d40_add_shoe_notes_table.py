"""add shoe_notes table

Revision ID: 9f3a1c7b2d40
Revises: c2f8d4a91e07
Create Date: 2026-06-21 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9f3a1c7b2d40"
down_revision: Union[str, Sequence[str], None] = "c2f8d4a91e07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE shoe_notes (
            id VARCHAR(255) PRIMARY KEY,
            shoe_id VARCHAR(255) NOT NULL REFERENCES shoes(id),
            note_date DATE NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMP
        );
        CREATE INDEX idx_shoe_notes_shoe_id ON shoe_notes(shoe_id);
        CREATE INDEX idx_shoe_notes_deleted_at ON shoe_notes(deleted_at);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        DROP INDEX IF EXISTS idx_shoe_notes_deleted_at;
        DROP INDEX IF EXISTS idx_shoe_notes_shoe_id;
        DROP TABLE IF EXISTS shoe_notes;
    """)
