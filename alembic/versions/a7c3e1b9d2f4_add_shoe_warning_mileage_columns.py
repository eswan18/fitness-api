"""add first/second warning mileage columns to shoes

Makes the two mileage-warning thresholds per-shoe and customizable. They were
previously hardcoded in the frontend (300 / 500 for every shoe). Adding them as
NOT NULL columns with server defaults backfills every existing row to 300 / 500
in one statement; the create endpoint can override them and the update endpoint
can edit them.

Revision ID: a7c3e1b9d2f4
Revises: f2b3c4d5e6a7
Create Date: 2026-06-30 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a7c3e1b9d2f4"
down_revision: Union[str, Sequence[str], None] = "f2b3c4d5e6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOT NULL with a server default: Postgres applies the default to every
    # existing row, so all current shoes read 300 / 500 with no separate backfill.
    op.execute(
        "ALTER TABLE shoes "
        "ADD COLUMN first_warning_mileage INTEGER NOT NULL DEFAULT 300, "
        "ADD COLUMN second_warning_mileage INTEGER NOT NULL DEFAULT 500"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE shoes DROP COLUMN IF EXISTS second_warning_mileage")
    op.execute("ALTER TABLE shoes DROP COLUMN IF EXISTS first_warning_mileage")
