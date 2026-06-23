"""add notes column to runs

Revision ID: c4e9b1f7a2d8
Revises: 9f3a1c7b2d40
Create Date: 2026-06-23 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c4e9b1f7a2d8"
down_revision: Union[str, Sequence[str], None] = "9f3a1c7b2d40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE runs ADD COLUMN notes TEXT")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE runs DROP COLUMN IF EXISTS notes")
