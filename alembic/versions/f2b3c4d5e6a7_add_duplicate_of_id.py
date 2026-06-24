"""add duplicate_of_id self-reference to runs and rides

Lets an activity be marked as a duplicate of another (e.g. the same physical
run/ride arriving from both Strava and Apple Health). Marking sets the existing
`deleted_at` (which already hides the row from every read and skips it on
re-import) plus `duplicate_of_id`, which records the kept activity so the mark
can be displayed and undone.

Revision ID: f2b3c4d5e6a7
Revises: e1a2b3c4d5f6
Create Date: 2026-06-23 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f2b3c4d5e6a7"
down_revision: Union[str, Sequence[str], None] = "e1a2b3c4d5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable self-reference; NULL for every existing row, so no backfill. The
    # existing `INSERT ... ON CONFLICT (id) DO NOTHING` paths simply omit it.
    op.execute("ALTER TABLE runs ADD COLUMN duplicate_of_id VARCHAR(255)")
    op.execute("ALTER TABLE rides ADD COLUMN duplicate_of_id VARCHAR(255)")

    # ON DELETE SET NULL: a hard-delete of the kept activity nulls the link
    # rather than erroring; the duplicate stays soft-deleted (still correct).
    op.execute(
        "ALTER TABLE runs ADD CONSTRAINT runs_duplicate_of_fk "
        "FOREIGN KEY (duplicate_of_id) REFERENCES runs(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE rides ADD CONSTRAINT rides_duplicate_of_fk "
        "FOREIGN KEY (duplicate_of_id) REFERENCES rides(id) ON DELETE SET NULL"
    )

    # Partial index: only the (rare) duplicate rows are indexed.
    op.execute(
        "CREATE INDEX idx_runs_duplicate_of ON runs (duplicate_of_id) "
        "WHERE duplicate_of_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_rides_duplicate_of ON rides (duplicate_of_id) "
        "WHERE duplicate_of_id IS NOT NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS idx_rides_duplicate_of")
    op.execute("DROP INDEX IF EXISTS idx_runs_duplicate_of")
    op.execute("ALTER TABLE rides DROP CONSTRAINT IF EXISTS rides_duplicate_of_fk")
    op.execute("ALTER TABLE runs DROP CONSTRAINT IF EXISTS runs_duplicate_of_fk")
    op.execute("ALTER TABLE rides DROP COLUMN IF EXISTS duplicate_of_id")
    op.execute("ALTER TABLE runs DROP COLUMN IF EXISTS duplicate_of_id")
