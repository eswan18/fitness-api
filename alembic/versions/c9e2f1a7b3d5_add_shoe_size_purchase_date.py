"""add size and purchased_date columns to shoes

Tracks each shoe's size and purchase date. Both are nullable — old/imported
shoes won't have this info, and shoes created implicitly during run imports
(bulk_create_shoes_by_names) leave them null. The API enforces them on newly
created shoes at the POST /shoes/ layer (CreateShoeRequest), not in the schema.

Revision ID: c9e2f1a7b3d5
Revises: b8d4f2a6c1e9
Create Date: 2026-06-30 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c9e2f1a7b3d5"
down_revision: Union[str, Sequence[str], None] = "b8d4f2a6c1e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Both nullable, no default: existing rows stay null (intended).
    op.execute(
        "ALTER TABLE shoes "
        "ADD COLUMN size DOUBLE PRECISION, "
        "ADD COLUMN purchased_date DATE"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE shoes DROP COLUMN IF EXISTS purchased_date")
    op.execute("ALTER TABLE shoes DROP COLUMN IF EXISTS size")
