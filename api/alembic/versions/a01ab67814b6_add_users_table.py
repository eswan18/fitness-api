"""add_users_table

Revision ID: a01ab67814b6
Revises: 16b1cd7556b0
Create Date: 2026-01-11 08:21:55.534549+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a01ab67814b6"
down_revision: Union[str, Sequence[str], None] = "16b1cd7556b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            idp_user_id UUID NOT NULL UNIQUE,
            email TEXT,
            username TEXT,
            role VARCHAR(20) NOT NULL DEFAULT 'viewer' CHECK (role IN ('viewer', 'editor')),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        -- Create index on idp_user_id for fast lookups
        CREATE INDEX IF NOT EXISTS idx_users_idp_user_id ON users(idp_user_id);

        -- Create trigger to update updated_at timestamp
        CREATE OR REPLACE FUNCTION update_users_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS users_updated_at_trigger ON users;
        CREATE TRIGGER users_updated_at_trigger
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION update_users_updated_at();
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        DROP TRIGGER IF EXISTS users_updated_at_trigger ON users;
        DROP FUNCTION IF EXISTS update_users_updated_at();
        DROP TABLE IF EXISTS users CASCADE;
    """)
