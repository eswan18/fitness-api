"""add name to runs and rides

Revision ID: 9d4c4e3c66b3
Revises: e7b3c9d15a24
Create Date: 2026-07-01 22:13:42.253687+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9d4c4e3c66b3"
down_revision: Union[str, Sequence[str], None] = "e7b3c9d15a24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE runs ADD COLUMN name VARCHAR(255)")
    op.execute("ALTER TABLE rides ADD COLUMN name VARCHAR(255)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE runs DROP COLUMN IF EXISTS name")
    op.execute("ALTER TABLE rides DROP COLUMN IF EXISTS name")
