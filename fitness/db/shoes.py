import logging
from datetime import date
from typing import List, Optional

from psycopg import sql

from fitness.models.shoe import Shoe, ShoeRecentUse
from .connection import get_db_cursor, get_db_connection

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
            else sql.SQL("ORDER BY brand, model")
        )

        query = sql.SQL("""
            SELECT id, retired_at, notes, retirement_notes, deleted_at,
                   warning_mileage, maximum_mileage, size, purchased_date,
                   brand, model, color
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
                SELECT id, retired_at, notes, retirement_notes, deleted_at,
                       warning_mileage, maximum_mileage, size, purchased_date,
                       brand, model, color
                FROM shoes
                WHERE id = %s
            """,
                (shoe_id,),
            )
        else:
            cursor.execute(
                """
                SELECT id, retired_at, notes, retirement_notes, deleted_at,
                       warning_mileage, maximum_mileage, size, purchased_date,
                       brand, model, color
                FROM shoes
                WHERE id = %s AND deleted_at IS NULL
            """,
                (shoe_id,),
            )
        row = cursor.fetchone()
        return _row_to_shoe(row) if row else None


def create_shoe(
    brand: str,
    model: str,
    size: float,
    purchased_date: date,
    color: Optional[str] = None,
    warning_mileage: int = 300,
    maximum_mileage: int = 500,
    notes: Optional[str] = None,
) -> Shoe:
    """Create a new shoe with an opaque id.

    Ids are opaque (not derived from the name) so duplicate brand/model/color
    pairs — e.g. a repurchased pair — can coexist. The display ``name`` is
    composed as ``"{brand} {model}"`` (no longer stored).
    """
    import secrets

    shoe_id = f"shoe_{secrets.token_hex(8)}"
    name = f"{brand} {model}"
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO shoes
                (id, brand, model, color, notes,
                 warning_mileage, maximum_mileage, size, purchased_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                shoe_id,
                brand,
                model,
                color,
                notes,
                warning_mileage,
                maximum_mileage,
                size,
                purchased_date,
            ),
        )
    return Shoe(
        id=shoe_id,
        name=name,
        brand=brand,
        model=model,
        color=color,
        notes=notes,
        warning_mileage=warning_mileage,
        maximum_mileage=maximum_mileage,
        size=size,
        purchased_date=purchased_date,
    )


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


# Columns the generic partial-update path is allowed to touch. ``name`` is no
# longer stored — it's composed from brand/model.
_UPDATABLE_SHOE_FIELDS = (
    "brand",
    "model",
    "color",
    "warning_mileage",
    "maximum_mileage",
    "size",
    "purchased_date",
    "retired_at",
    "retirement_notes",
)


def update_shoe(shoe_id: str, fields: dict) -> bool:
    """Apply a partial update to a shoe.

    ``fields`` may contain any of ``name``, ``brand``, ``model``, ``color``,
    ``warning_mileage``, ``maximum_mileage``, ``size``, ``purchased_date``,
    ``retired_at``, ``retirement_notes`` (unknown keys are ignored).

    Returns True if a non-deleted shoe matched and was updated.
    """
    updates = {k: v for k, v in fields.items() if k in _UPDATABLE_SHOE_FIELDS}
    if not updates:
        return False

    assignments: list[sql.Composable] = [
        sql.SQL("{} = %s").format(sql.Identifier(key)) for key in updates
    ]
    assignments.append(sql.SQL("updated_at = CURRENT_TIMESTAMP"))
    query = sql.SQL(
        "UPDATE shoes SET {assignments} WHERE id = %s AND deleted_at IS NULL"
    ).format(assignments=sql.SQL(", ").join(assignments))
    params = list(updates.values()) + [shoe_id]

    with get_db_cursor() as cursor:
        cursor.execute(query, params)
        return cursor.rowcount > 0


def delete_shoe_by_id(shoe_id: str) -> bool:
    """Soft-delete a shoe by ID. Returns True if shoe was found and deleted."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE shoes
            SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND deleted_at IS NULL
        """,
            (shoe_id,),
        )
        return cursor.rowcount > 0


def get_shoes_with_last_used(include_retired: bool = False) -> List[ShoeRecentUse]:
    """Return shoes paired with the datetime of their most recent non-deleted run.

    Results are ordered by last_used_date DESC NULLS LAST. Soft-deleted shoes
    are always excluded. Retired shoes are excluded unless include_retired is True.
    Soft-deleted runs are ignored when determining the last-used datetime.
    """
    conditions: list[sql.Composable] = [sql.SQL("s.deleted_at IS NULL")]
    if not include_retired:
        conditions.append(sql.SQL("s.retired_at IS NULL"))
    where_clause = sql.SQL("WHERE ") + sql.SQL(" AND ").join(conditions)

    query = sql.SQL("""
        SELECT id, retired_at, notes, retirement_notes, deleted_at,
               warning_mileage, maximum_mileage, size, purchased_date,
               brand, model, color, last_used_date
        FROM (
            SELECT DISTINCT ON (s.id)
                s.id, s.retired_at, s.notes, s.retirement_notes, s.deleted_at,
                s.warning_mileage, s.maximum_mileage, s.size, s.purchased_date,
                s.brand, s.model, s.color,
                r.datetime_utc AS last_used_date
            FROM shoes s
            LEFT JOIN runs r ON r.shoe_id = s.id AND r.deleted_at IS NULL
            {where_clause}
            ORDER BY s.id, r.datetime_utc DESC NULLS LAST
        ) sub
        ORDER BY last_used_date DESC NULLS LAST, brand, model
    """).format(where_clause=where_clause)

    with get_db_cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
        return [
            ShoeRecentUse(
                shoe=_row_to_shoe(row[:12]),
                last_used_date=row[12],
            )
            for row in rows
        ]


def _row_to_shoe(row) -> Shoe:
    """Convert a database row to a Shoe object."""
    (
        shoe_id,
        retired_at,
        notes,
        retirement_notes,
        deleted_at,
        warning_mileage,
        maximum_mileage,
        size,
        purchased_date,
        brand,
        model,
        color,
    ) = row
    return Shoe(
        id=shoe_id,
        name=f"{brand} {model}",
        retired_at=retired_at,
        notes=notes,
        retirement_notes=retirement_notes,
        deleted_at=deleted_at,
        warning_mileage=warning_mileage,
        maximum_mileage=maximum_mileage,
        size=size,
        purchased_date=purchased_date,
        brand=brand,
        model=model,
        color=color,
    )


def merge_shoes(keep_shoe_id: str, merge_shoe_id: str, merge_shoe_name: str) -> None:
    """Merge one shoe into another within a single transaction.

    Re-points all runs and history from the merged shoe to keep_shoe_id and
    soft-deletes the merged shoe. (``merge_shoe_name`` is unused now that imports
    no longer resolve shoe names, but kept for a stable call signature.)
    """
    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                # Re-point runs
                cursor.execute(
                    "UPDATE runs SET shoe_id = %s WHERE shoe_id = %s",
                    (keep_shoe_id, merge_shoe_id),
                )
                # Re-point history
                cursor.execute(
                    "UPDATE runs_history SET shoe_id = %s WHERE shoe_id = %s",
                    (keep_shoe_id, merge_shoe_id),
                )
                # Soft-delete merged shoe
                cursor.execute(
                    "UPDATE shoes SET deleted_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (merge_shoe_id,),
                )
