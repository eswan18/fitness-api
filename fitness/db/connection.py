import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


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


def init_pool() -> None:
    """Create the connection pool. Call once at app startup."""
    global _pool
    _pool = ConnectionPool(get_database_url(), min_size=2, max_size=10)


def close_pool() -> None:
    """Close the connection pool. Call once at app shutdown."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def get_db_connection() -> Iterator[psycopg.Connection]:
    """Get a database connection from the pool, or create one directly if no pool exists."""
    if _pool is not None:
        with _pool.connection() as conn:
            yield conn
    else:
        conn = psycopg.connect(get_database_url())
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
