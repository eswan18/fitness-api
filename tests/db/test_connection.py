"""Tests for the database connection helpers in fitness.db.connection."""

from unittest.mock import MagicMock, patch

import psycopg
import pytest


@patch("fitness.db.connection.get_database_url", return_value="postgresql://x/y")
@patch("fitness.db.connection.ConnectionPool")
def test_init_pool_enables_connection_check(mock_pool_cls, _mock_url):
    """The pool must validate connections on checkout.

    Neon closes idle connections server-side; without a check the pool hands out
    dead connections and queries fail with "SSL connection has been closed
    unexpectedly". check_connection recycles dead connections on checkout.
    """
    from fitness.db import connection

    connection._pool = None
    try:
        connection.init_pool()
    finally:
        connection._pool = None

    mock_pool_cls.assert_called_once()
    _, kwargs = mock_pool_cls.call_args
    assert kwargs.get("check") is connection.ConnectionPool.check_connection


@patch("fitness.db.connection.get_db_connection")
def test_get_db_cursor_commits_on_success(mock_get_conn):
    from fitness.db.connection import get_db_cursor

    mock_conn = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    with get_db_cursor() as cursor:
        assert cursor is mock_conn.cursor.return_value.__enter__.return_value

    mock_conn.commit.assert_called_once()
    mock_conn.rollback.assert_not_called()


@patch("fitness.db.connection.get_db_connection")
def test_get_db_cursor_rolls_back_on_error(mock_get_conn):
    from fitness.db.connection import get_db_cursor

    mock_conn = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    with pytest.raises(ValueError, match="boom"):
        with get_db_cursor():
            raise ValueError("boom")

    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()


@patch("fitness.db.connection.get_db_connection")
def test_get_db_cursor_failed_rollback_preserves_original_error(mock_get_conn):
    """A rollback that fails on a dead connection must not mask the original error.

    Reproduces the production traceback where conn.rollback() raised "the
    connection is lost", hiding the real query failure.
    """
    from fitness.db.connection import get_db_cursor

    mock_conn = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    # Simulate a connection that's already dead: the rollback itself raises.
    mock_conn.rollback.side_effect = psycopg.OperationalError("the connection is lost")

    # The ORIGINAL error should surface, not the rollback's OperationalError.
    with pytest.raises(ValueError, match="original failure"):
        with get_db_cursor():
            raise ValueError("original failure")
