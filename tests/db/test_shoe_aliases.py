from unittest.mock import MagicMock, patch
from fitness.db.shoes import get_shoe_ids_by_alias_names


def test_get_shoe_ids_by_alias_names_returns_mapping():
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("Nike Zoom Fly 4", "zoom_fly_4")]

    with patch("fitness.db.shoes.get_db_cursor") as mock_ctx:
        mock_ctx.return_value.__enter__ = lambda s: mock_cursor
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        result = get_shoe_ids_by_alias_names({"Nike Zoom Fly 4", "Unknown Shoe"})

    assert result == {"Nike Zoom Fly 4": "zoom_fly_4"}


def test_get_shoe_ids_by_alias_names_empty_input():
    result = get_shoe_ids_by_alias_names(set())
    assert result == {}


from fitness.db.shoes import merge_shoes


def test_merge_shoes_executes_all_statements():
    """Verify merge_shoes runs the expected SQL statements in a transaction."""
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("fitness.db.shoes.get_db_connection") as mock_ctx:
        mock_ctx.return_value.__enter__ = lambda s: mock_conn
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        merge_shoes(
            keep_shoe_id="zoom_fly_4",
            merge_shoe_id="nike_zoom_fly_4",
            merge_shoe_name="Nike Zoom Fly 4",
        )

    # Should have executed: update runs, update runs_history, insert alias, soft-delete shoe
    assert mock_cursor.execute.call_count == 4
