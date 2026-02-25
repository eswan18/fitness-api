"""add shoe_aliases table

Revision ID: 6dda1ac0535c
Revises: 8995ea55de0a
Create Date: 2026-02-25 02:41:15.260205+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6dda1ac0535c"
down_revision: Union[str, Sequence[str], None] = "8995ea55de0a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE shoe_aliases (
            alias_name VARCHAR(255) PRIMARY KEY,
            shoe_id VARCHAR(255) NOT NULL REFERENCES shoes(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX idx_shoe_aliases_shoe_id ON shoe_aliases (shoe_id)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS idx_shoe_aliases_shoe_id")
    op.execute("DROP TABLE IF EXISTS shoe_aliases") 