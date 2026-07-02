"""add name to runs_history

Revision ID: bd552ba841fd
Revises: 62128cf4b300
Create Date: 2026-07-02 01:19:20.625650+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "bd552ba841fd"
down_revision: Union[str, Sequence[str], None] = "62128cf4b300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE runs_history ADD COLUMN name VARCHAR(255)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE runs_history DROP COLUMN IF EXISTS name")
