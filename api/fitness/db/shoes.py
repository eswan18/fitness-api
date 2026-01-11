import logging
from datetime import date
from typing import List, Optional

from psycopg import sql

from fitness.models.shoe import Shoe
from .connection import get_db_cursor

logger = logging.getLogger(__name__)


def get_shoes(
    retired: Optional[bool] = None, include_deleted: bool = False
) -> List[Shoe]:
    """Get shoes from the database with optional retirement status filter.

    Args:
        retired: If None, return all shoes. If True, return only retired shoes.
                If False, return only active shoes.
        include_deleted: Whether to include soft-deleted shoes.
    """
    with get_db_cursor() as cursor:
        # Build WHERE clause conditions
        conditions: list[sql.Composable] = []

        if not include_deleted:
            conditions.append(sql.SQL("deleted_at IS NULL"))

        if retired is True:
            conditions.append(sql.SQL("retired_at IS NOT NULL"))
        elif retired is False:
            conditions.append(sql.SQL("retired_at IS NULL"))
        # If retired is None, no retirement filter is applied

        # Build the query
        where_clause = (
            sql.SQL("WHERE ") + sql.SQL(" AND ").join(conditions)
            if conditions
            else sql.SQL("")
        )

        # Choose ORDER BY based on retirement filter
        order_by = (
            sql.SQL("ORDER BY retired_at DESC")
            if retired is True
            else sql.SQL("ORDER BY name")
        )

        query = sql.SQL("""
            SELECT id, name, retired_at, notes, retirement_notes, deleted_at
            FROM shoes
            {where_clause}
            {order_by}
        """).format(where_clause=where_clause, order_by=order_by)

        cursor.execute(query)
        rows = cursor.fetchall()
        return [_row_to_shoe(row) for row in rows]


def get_shoe_by_id(shoe_id: str, include_deleted: bool = False) -> Optional[Shoe]:
    """Get a specific shoe by its ID."""
    with get_db_cursor() as cursor:
        if include_deleted:
            cursor.execute(
                """
                SELECT id, name, retired_at, notes, retirement_notes, deleted_at
                FROM shoes
                WHERE id = %s
            """,
                (shoe_id,),
            )
        else:
            cursor.execute(
                """
                SELECT id, name, retired_at, notes, retirement_notes, deleted_at
                FROM shoes
                WHERE id = %s AND deleted_at IS NULL
            """,
                (shoe_id,),
            )
        row = cursor.fetchone()
        return _row_to_shoe(row) if row else None


def retire_shoe_by_id(
    shoe_id: str, retired_at: date, retirement_notes: Optional[str] = None
) -> bool:
    """Retire a shoe by ID. Returns True if shoe was found and retired."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE shoes 
            SET retired_at = %s, retirement_notes = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND deleted_at IS NULL
        """,
            (retired_at, retirement_notes, shoe_id),
        )
        return cursor.rowcount > 0


def unretire_shoe_by_id(shoe_id: str) -> bool:
    """Unretire a shoe by ID. Returns True if shoe was found and unretired."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE shoes 
            SET retired_at = NULL, retirement_notes = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND deleted_at IS NULL
        """,
            (shoe_id,),
        )
        return cursor.rowcount > 0


def _row_to_shoe(row) -> Shoe:
    """Convert a database row to a Shoe object."""
    shoe_id, name, retired_at, notes, retirement_notes, deleted_at = row
    return Shoe(
        id=shoe_id,
        name=name,
        retired_at=retired_at,
        notes=notes,
        retirement_notes=retirement_notes,
        deleted_at=deleted_at,
    )


def get_existing_shoes_by_names(shoe_names: set[str]) -> dict[str, str]:
    """Get existing shoes by their names. Returns dict mapping shoe_name -> shoe_id."""
    if not shoe_names:
        return {}

    logger.debug(f"Checking existence of {len(shoe_names)} shoes: {shoe_names}")

    with get_db_cursor() as cursor:
        # Create placeholders for IN clause using sql.SQL
        placeholders = sql.SQL(",").join(sql.Placeholder() * len(shoe_names))
        query = sql.SQL("""
            SELECT name, id FROM shoes
            WHERE name IN ({placeholders}) AND deleted_at IS NULL
        """).format(placeholders=placeholders)
        cursor.execute(query, list(shoe_names))

        result = {name: shoe_id for name, shoe_id in cursor.fetchall()}
        logger.debug(f"Found {len(result)} existing shoes in database")
        return result


def bulk_create_shoes_by_names(shoe_names: set[str]) -> dict[str, str]:
    """Create multiple shoes by names. Returns dict mapping shoe_name -> shoe_id."""
    if not shoe_names:
        return {}

    logger.info(f"Creating {len(shoe_names)} new shoes: {shoe_names}")

    from fitness.models.shoe import generate_shoe_id

    # Generate shoe data
    shoe_data = [(generate_shoe_id(name), name) for name in shoe_names]

    with get_db_cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO shoes (id, name, retired_at, notes, retirement_notes, deleted_at)
            VALUES (%s, %s, NULL, NULL, NULL, NULL)
        """,
            shoe_data,
        )

        logger.info(f"Successfully created {len(shoe_data)} shoes")

        # Return mapping of name -> id
        return {name: shoe_id for shoe_id, name in shoe_data}
