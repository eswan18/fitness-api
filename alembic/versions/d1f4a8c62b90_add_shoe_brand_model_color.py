"""add shoe brand/model/color, runs.imported_shoe_name; drop shoe_aliases

Moves shoe identity to structured brand/model/color (nullable for now; a backfill
script populates them from `name`, then a later migration makes brand/model NOT
NULL and drops `name`). Run imports no longer resolve or auto-create shoes — they
record the raw gear name in `runs.imported_shoe_name` and leave `shoe_id` NULL —
so the `shoe_aliases` table (only used by import resolution) is dropped, and the
`name` UNIQUE constraint is dropped so duplicate brand/model/color pairs (e.g. a
repurchased pair) are allowed.

Revision ID: d1f4a8c62b90
Revises: c9e2f1a7b3d5
Create Date: 2026-06-30 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d1f4a8c62b90"
down_revision: Union[str, Sequence[str], None] = "c9e2f1a7b3d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Structured shoe fields — nullable for now; a backfill populates brand/model
    # before a later migration makes them NOT NULL. color stays nullable.
    op.execute(
        "ALTER TABLE shoes "
        "ADD COLUMN brand VARCHAR(255), "
        "ADD COLUMN model VARCHAR(255), "
        "ADD COLUMN color VARCHAR(255)"
    )
    # Duplicate brand/model/color pairs are now allowed (opaque ids keep rows
    # distinct), so the name is no longer unique.
    op.execute("ALTER TABLE shoes DROP CONSTRAINT IF EXISTS shoes_name_key")
    # Preserve the raw gear name on imported runs; shoes are assigned manually.
    op.execute("ALTER TABLE runs ADD COLUMN imported_shoe_name VARCHAR(255)")
    # Imports no longer resolve shoe names, so aliases have no remaining reader.
    op.execute("DROP TABLE IF EXISTS shoe_aliases")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "CREATE TABLE IF NOT EXISTS shoe_aliases ("
        "alias_name VARCHAR(255) PRIMARY KEY, "
        "shoe_id VARCHAR(255) NOT NULL REFERENCES shoes(id), "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_shoe_aliases_shoe_id "
        "ON shoe_aliases (shoe_id)"
    )
    op.execute("ALTER TABLE runs DROP COLUMN IF EXISTS imported_shoe_name")
    # Re-adding the UNIQUE constraint on downgrade would fail if duplicates exist;
    # leave it off (the column keeps its data).
    op.execute("ALTER TABLE shoes DROP COLUMN IF EXISTS color")
    op.execute("ALTER TABLE shoes DROP COLUMN IF EXISTS model")
    op.execute("ALTER TABLE shoes DROP COLUMN IF EXISTS brand")
