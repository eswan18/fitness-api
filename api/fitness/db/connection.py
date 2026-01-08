import os
from contextlib import contextmanager
from typing import Iterator

import psycopg


def get_database_url() -> str:
    """Get the database URL from environment variables."""
    url = os.environ["DATABASE_URL"]
    return url


def get_sqlalchemy_database_url() -> str:
    """Get the database URL formatted for SQLAlchemy.

    Automatically converts postgresql:// to postgresql+psycopg://
    to ensure psycopg3 is used instead of psycopg2.
    """
    url = get_database_url()
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@contextmanager
def get_db_connection() -> Iterator[psycopg.Connection]:
    """Get a database connection context manager.

    Explicitly closes the connection to ensure proper cleanup in serverless environments.
    """
    url = get_database_url()
    conn = psycopg.connect(url)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_db_cursor() -> Iterator[psycopg.Cursor]:
    """Get a database cursor context manager.

    Automatically commits the transaction on successful completion,
    or rolls back on exception.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            try:
                yield cursor
                # Commit the transaction on successful completion
                conn.commit()
            except Exception:
                # Rollback on error (though psycopg does this automatically)
                conn.rollback()
                raise
