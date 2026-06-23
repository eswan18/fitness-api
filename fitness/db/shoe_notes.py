"""Database operations for shoe notes."""

import logging
import uuid
from datetime import date
from typing import Optional

from psycopg import sql

from .connection import get_db_cursor, get_db_connection
from .shoes import get_shoe_by_id
from fitness.models.shoe_note import ShoeNote

logger = logging.getLogger(__name__)


def create_shoe_note(shoe_id: str, note_date: date, content: str) -> ShoeNote:
    """Create a new dated note for a shoe.

    Args:
        shoe_id: The shoe the note belongs to.
        note_date: The date the note applies to.
        content: Freeform markdown content.

    Returns:
        The created ShoeNote.

    Raises:
        ValueError: If the shoe doesn't exist (or is soft-deleted).
    """
    if get_shoe_by_id(shoe_id) is None:
        raise ValueError(f"Shoe '{shoe_id}' not found")

    note_id = f"sn_{uuid.uuid4()}"
    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO shoe_notes (id, shoe_id, note_date, content)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, shoe_id, note_date, content, created_at, updated_at, deleted_at
                    """,
                    (note_id, shoe_id, note_date, content),
                )
                return _row_to_shoe_note(cursor.fetchone())


def get_shoe_notes(shoe_id: str) -> list[ShoeNote]:
    """Get all non-deleted notes for a shoe, newest first."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, shoe_id, note_date, content, created_at, updated_at, deleted_at
            FROM shoe_notes
            WHERE shoe_id = %s AND deleted_at IS NULL
            ORDER BY note_date DESC, created_at DESC
            """,
            (shoe_id,),
        )
        return [_row_to_shoe_note(row) for row in cursor.fetchall()]


def get_shoe_note_by_id(
    note_id: str, include_deleted: bool = False
) -> Optional[ShoeNote]:
    """Get a single shoe note by ID."""
    with get_db_cursor() as cursor:
        if include_deleted:
            cursor.execute(
                """
                SELECT id, shoe_id, note_date, content, created_at, updated_at, deleted_at
                FROM shoe_notes WHERE id = %s
                """,
                (note_id,),
            )
        else:
            cursor.execute(
                """
                SELECT id, shoe_id, note_date, content, created_at, updated_at, deleted_at
                FROM shoe_notes WHERE id = %s AND deleted_at IS NULL
                """,
                (note_id,),
            )
        row = cursor.fetchone()
        return _row_to_shoe_note(row) if row else None


def update_shoe_note(
    note_id: str,
    note_date: Optional[date] = None,
    content: Optional[str] = None,
) -> Optional[ShoeNote]:
    """Update a note's date and/or content. Returns None if not found."""
    update_parts: list[sql.Composable] = []
    params: list = []
    if note_date is not None:
        update_parts.append(sql.SQL("note_date = %s"))
        params.append(note_date)
    if content is not None:
        update_parts.append(sql.SQL("content = %s"))
        params.append(content)
    if not update_parts:
        return get_shoe_note_by_id(note_id)

    update_parts.append(sql.SQL("updated_at = CURRENT_TIMESTAMP"))
    params.append(note_id)

    with get_db_cursor() as cursor:
        query = sql.SQL("""
            UPDATE shoe_notes
            SET {updates}
            WHERE id = %s AND deleted_at IS NULL
            RETURNING id, shoe_id, note_date, content, created_at, updated_at, deleted_at
        """).format(updates=sql.SQL(", ").join(update_parts))
        cursor.execute(query, params)
        row = cursor.fetchone()
        return _row_to_shoe_note(row) if row else None


def delete_shoe_note(note_id: str) -> bool:
    """Soft-delete a shoe note. Returns True if a note was found and deleted."""
    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE shoe_notes
                    SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND deleted_at IS NULL
                    """,
                    (note_id,),
                )
                return cursor.rowcount > 0


def _row_to_shoe_note(row) -> ShoeNote:
    """Convert a database row to a ShoeNote."""
    id_, shoe_id, note_date, content, created_at, updated_at, deleted_at = row
    return ShoeNote(
        id=id_,
        shoe_id=shoe_id,
        note_date=note_date,
        content=content,
        created_at=created_at,
        updated_at=updated_at,
        deleted_at=deleted_at,
    )
