"""make shoes.brand/model NOT NULL and drop shoes.name

Release 2 of the structured-shoe change. After the backfill populated brand/model
on every shoe, enforce them at the schema level and drop the now-redundant `name`
column. The API keeps returning a `name` composed from brand/model, so consumers
are unaffected.

Precondition: no shoe may have a NULL brand or model (the backfill + manual
cleanup must be complete) — otherwise the SET NOT NULL fails.

Revision ID: e7b3c9d15a24
Revises: d1f4a8c62b90
Create Date: 2026-06-30 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e7b3c9d15a24"
down_revision: Union[str, Sequence[str], None] = "d1f4a8c62b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TABLE shoes "
        "ALTER COLUMN brand SET NOT NULL, "
        "ALTER COLUMN model SET NOT NULL"
    )
    op.execute("ALTER TABLE shoes DROP COLUMN name")


def downgrade() -> None:
    """Downgrade schema."""
    # Re-add name as a plain nullable column (the original values / UNIQUE
    # constraint can't be restored) and relax the NOT NULLs.
    op.execute("ALTER TABLE shoes ADD COLUMN name VARCHAR(255)")
    op.execute("UPDATE shoes SET name = concat_ws(' ', brand, model)")
    op.execute(
        "ALTER TABLE shoes "
        "ALTER COLUMN model DROP NOT NULL, "
        "ALTER COLUMN brand DROP NOT NULL"
    )
