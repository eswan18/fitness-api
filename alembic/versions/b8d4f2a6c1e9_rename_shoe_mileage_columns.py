"""rename shoe mileage columns to warning_mileage / maximum_mileage

The first pass added first_warning_mileage / second_warning_mileage. To mirror
the frontend's actual model we instead store a single "warning" threshold and a
"maximum" (replace / 100%-wear) threshold. The intermediate "danger" mileage the
dashboard shows (the 400 in a 300/500 setup) is the midpoint of the two and is
derived in the UI, not stored.

Renaming preserves each column's type, NOT NULL constraint, and default (300 for
warning, 500 for maximum), so existing rows keep their values.

Revision ID: b8d4f2a6c1e9
Revises: a7c3e1b9d2f4
Create Date: 2026-06-30 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b8d4f2a6c1e9"
down_revision: Union[str, Sequence[str], None] = "a7c3e1b9d2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE shoes RENAME COLUMN first_warning_mileage TO warning_mileage")
    op.execute("ALTER TABLE shoes RENAME COLUMN second_warning_mileage TO maximum_mileage")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE shoes RENAME COLUMN maximum_mileage TO second_warning_mileage")
    op.execute("ALTER TABLE shoes RENAME COLUMN warning_mileage TO first_warning_mileage")
