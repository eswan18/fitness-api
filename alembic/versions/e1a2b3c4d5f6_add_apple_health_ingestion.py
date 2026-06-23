"""add apple health (HAE) ingestion: api_tokens table, runs/rides columns, widened source checks

Revision ID: e1a2b3c4d5f6
Revises: c4e9b1f7a2d8
Create Date: 2026-06-23 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e1a2b3c4d5f6"
down_revision: Union[str, Sequence[str], None] = "c4e9b1f7a2d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Per-service bearer tokens for ingestion endpoints. Only a hash is stored.
    op.execute("""
        CREATE TABLE api_tokens (
            id           SERIAL PRIMARY KEY,
            name         VARCHAR(255) NOT NULL,
            token_hash   VARCHAR(64)  NOT NULL UNIQUE,
            prefix       VARCHAR(32)  NOT NULL,
            created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at   TIMESTAMP,
            last_used_at TIMESTAMP,
            revoked_at   TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX idx_api_tokens_prefix ON api_tokens (prefix)")

    # New nullable columns captured from Health Auto Export workouts. NULL for
    # existing MapMyFitness/Strava rows, so no backfill is needed.
    op.execute("""
        ALTER TABLE runs
            ADD COLUMN max_heart_rate   FLOAT,
            ADD COLUMN step_cadence     FLOAT,
            ADD COLUMN end_datetime_utc TIMESTAMP,
            ADD COLUMN source_name      VARCHAR(255)
    """)
    op.execute("""
        ALTER TABLE rides
            ADD COLUMN max_heart_rate   FLOAT,
            ADD COLUMN end_datetime_utc TIMESTAMP,
            ADD COLUMN source_name      VARCHAR(255)
    """)

    # Widen the source CHECK constraints to allow 'Apple Health'. These are the
    # inline column checks from the create-table migrations, auto-named
    # `<table>_source_check` by PostgreSQL.
    op.execute("ALTER TABLE runs DROP CONSTRAINT IF EXISTS runs_source_check")
    op.execute(
        "ALTER TABLE runs ADD CONSTRAINT runs_source_check "
        "CHECK (source IN ('MapMyFitness', 'Strava', 'Apple Health'))"
    )
    op.execute(
        "ALTER TABLE runs_history DROP CONSTRAINT IF EXISTS runs_history_source_check"
    )
    op.execute(
        "ALTER TABLE runs_history ADD CONSTRAINT runs_history_source_check "
        "CHECK (source IN ('MapMyFitness', 'Strava', 'Apple Health'))"
    )
    op.execute("ALTER TABLE rides DROP CONSTRAINT IF EXISTS rides_source_check")
    op.execute(
        "ALTER TABLE rides ADD CONSTRAINT rides_source_check "
        "CHECK (source IN ('Strava', 'Apple Health'))"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Restore the narrower source CHECK constraints.
    op.execute("ALTER TABLE rides DROP CONSTRAINT IF EXISTS rides_source_check")
    op.execute(
        "ALTER TABLE rides ADD CONSTRAINT rides_source_check "
        "CHECK (source IN ('Strava'))"
    )
    op.execute(
        "ALTER TABLE runs_history DROP CONSTRAINT IF EXISTS runs_history_source_check"
    )
    op.execute(
        "ALTER TABLE runs_history ADD CONSTRAINT runs_history_source_check "
        "CHECK (source IN ('MapMyFitness', 'Strava'))"
    )
    op.execute("ALTER TABLE runs DROP CONSTRAINT IF EXISTS runs_source_check")
    op.execute(
        "ALTER TABLE runs ADD CONSTRAINT runs_source_check "
        "CHECK (source IN ('MapMyFitness', 'Strava'))"
    )

    op.execute("""
        ALTER TABLE rides
            DROP COLUMN IF EXISTS max_heart_rate,
            DROP COLUMN IF EXISTS end_datetime_utc,
            DROP COLUMN IF EXISTS source_name
    """)
    op.execute("""
        ALTER TABLE runs
            DROP COLUMN IF EXISTS max_heart_rate,
            DROP COLUMN IF EXISTS step_cadence,
            DROP COLUMN IF EXISTS end_datetime_utc,
            DROP COLUMN IF EXISTS source_name
    """)

    op.execute("DROP TABLE IF EXISTS api_tokens")
