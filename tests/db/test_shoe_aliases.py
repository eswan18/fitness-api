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
