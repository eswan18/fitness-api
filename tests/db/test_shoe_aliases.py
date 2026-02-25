from datetime import datetime
from unittest.mock import MagicMock, patch

from fitness.db.runs import bulk_create_runs
from fitness.db.shoes import get_shoe_ids_by_alias_names, merge_shoes
from fitness.models import Run


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



def test_bulk_create_runs_resolves_aliases():
    """When a shoe name matches an alias, use the alias target instead of creating a new shoe."""
    created_shoe_names = set()

    def mock_get_existing(names):
        return {}  # no shoes exist

    def mock_get_aliases(names):
        return {"Nike Zoom Fly 4": "zoom_fly_4"}  # alias exists

    def mock_bulk_create(names):
        created_shoe_names.update(names)
        return {name: f"id_{name}" for name in names}

    # Mock the DB connection for the actual insert
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn_ctx = MagicMock()
    mock_conn_ctx.__enter__ = lambda s: mock_conn
    mock_conn_ctx.__exit__ = MagicMock(return_value=False)

    with (
        patch("fitness.db.shoes.get_existing_shoes_by_names", mock_get_existing),
        patch("fitness.db.shoes.get_shoe_ids_by_alias_names", mock_get_aliases),
        patch("fitness.db.shoes.bulk_create_shoes_by_names", mock_bulk_create),
        patch("fitness.db.runs.get_db_connection", return_value=mock_conn_ctx),
    ):
        run = Run(
            id="test1",
            datetime_utc=datetime(2024, 1, 1),
            type="Outdoor Run",
            distance=5.0,
            duration=2400.0,
            source="Strava",
        )
        run._shoe_name = "Nike Zoom Fly 4"

        bulk_create_runs([run])

    # The aliased name should NOT have been passed to bulk_create_shoes_by_names
    assert "Nike Zoom Fly 4" not in created_shoe_names
