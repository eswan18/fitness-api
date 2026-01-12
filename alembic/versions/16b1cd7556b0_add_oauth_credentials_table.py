"""add oauth_credentials table

Revision ID: 16b1cd7556b0
Revises: 1d4f4234bffa
Create Date: 2025-11-27 21:09:01.442640+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "16b1cd7556b0"
down_revision: Union[str, Sequence[str], None] = "1d4f4234bffa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS oauth_credentials (
            id SERIAL PRIMARY KEY,
            provider VARCHAR(50) NOT NULL UNIQUE,
            client_id TEXT NOT NULL,
            client_secret TEXT NOT NULL,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            expires_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        -- Create index on provider for fast lookups
        CREATE INDEX IF NOT EXISTS idx_oauth_credentials_provider ON oauth_credentials(provider);

        -- Create trigger to update updated_at timestamp
        CREATE OR REPLACE FUNCTION update_oauth_credentials_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS oauth_credentials_updated_at_trigger ON oauth_credentials;
        CREATE TRIGGER oauth_credentials_updated_at_trigger
            BEFORE UPDATE ON oauth_credentials
            FOR EACH ROW
            EXECUTE FUNCTION update_oauth_credentials_updated_at();
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        DROP TRIGGER IF EXISTS oauth_credentials_updated_at_trigger ON oauth_credentials;
        DROP FUNCTION IF EXISTS update_oauth_credentials_updated_at();
        DROP TABLE IF EXISTS oauth_credentials CASCADE;
    """)
