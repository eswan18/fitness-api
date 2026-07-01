"""Database operations for tags.

Tags are freeform labels assignable to runs and/or rides. They soft-delete
(``deleted_at``) with a partial unique index on ``LOWER(name)`` among live
tags — this gives case-insensitive dedupe for active tags while letting a
deleted tag's name be reused by a new tag. Join rows (``run_tags``,
``ride_tags``) are pure assignment state and are hard-deleted.
"""

import logging
import uuid

from psycopg import sql

from .connection import get_db_cursor, get_db_connection
from fitness.models.tag import Tag

logger = logging.getLogger(__name__)


def create_tag(name: str) -> Tag:
    """Create a tag, or return the existing live tag with the same name.

    Idempotent: name matching is case-insensitive against live tags. The name
    is expected to arrive pre-stripped from the router, but ``.strip()`` is
    applied defensively.

    Args:
        name: The tag's display name.

    Returns:
        The existing live tag if one matches (case-insensitively), otherwise
        the newly created Tag.
    """
    name = name.strip()
    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, name, created_at FROM tags
                    WHERE LOWER(name) = LOWER(%s) AND deleted_at IS NULL
                    """,
                    (name,),
                )
                row = cursor.fetchone()
                if row:
                    return _row_to_tag(row)

                tag_id = f"tag_{uuid.uuid4()}"
                cursor.execute(
                    """
                    INSERT INTO tags (id, name)
                    VALUES (%s, %s)
                    RETURNING id, name, created_at
                    """,
                    (tag_id, name),
                )
                return _row_to_tag(cursor.fetchone())


def get_all_tags() -> list[Tag]:
    """Get all live (non-deleted) tags, ordered by name."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name, created_at FROM tags
            WHERE deleted_at IS NULL
            ORDER BY name
            """
        )
        return [_row_to_tag(row) for row in cursor.fetchall()]


def get_tag_by_id(tag_id: str) -> Tag | None:
    """Get a single live tag by ID, or None if missing/deleted."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name, created_at FROM tags
            WHERE id = %s AND deleted_at IS NULL
            """,
            (tag_id,),
        )
        row = cursor.fetchone()
        return _row_to_tag(row) if row else None


def get_tags_by_ids(tag_ids: list[str]) -> list[Tag]:
    """Get live tags matching the given IDs. Returns [] for empty input."""
    if not tag_ids:
        return []
    with get_db_cursor() as cursor:
        placeholders = sql.SQL(", ").join(sql.Placeholder() * len(tag_ids))
        query = sql.SQL("""
            SELECT id, name, created_at FROM tags
            WHERE id IN ({placeholders}) AND deleted_at IS NULL
        """).format(placeholders=placeholders)
        cursor.execute(query, tag_ids)
        return [_row_to_tag(row) for row in cursor.fetchall()]


def update_tag_name(tag_id: str, name: str) -> Tag | None:
    """Rename a live tag. Returns None if the tag doesn't exist (or is deleted).

    Raises:
        ValueError: If another live tag already has that name
            (case-insensitive).
    """
    name = name.strip()
    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id FROM tags
                    WHERE LOWER(name) = LOWER(%s) AND deleted_at IS NULL AND id != %s
                    """,
                    (name, tag_id),
                )
                if cursor.fetchone():
                    raise ValueError(f"A tag named '{name}' already exists")

                cursor.execute(
                    """
                    UPDATE tags
                    SET name = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND deleted_at IS NULL
                    RETURNING id, name, created_at
                    """,
                    (name, tag_id),
                )
                row = cursor.fetchone()
                return _row_to_tag(row) if row else None


def delete_tag(tag_id: str) -> bool:
    """Soft-delete a tag and hard-delete its run/ride assignments.

    Returns True if a live tag was found and deleted.
    """
    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE tags
                    SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND deleted_at IS NULL
                    """,
                    (tag_id,),
                )
                found = cursor.rowcount > 0
                if found:
                    cursor.execute(
                        "DELETE FROM run_tags WHERE tag_id = %s", (tag_id,)
                    )
                    cursor.execute(
                        "DELETE FROM ride_tags WHERE tag_id = %s", (tag_id,)
                    )
                return found


def set_run_tags(run_id: str, tag_ids: list[str]) -> list[Tag]:
    """Replace the full set of tags assigned to a run.

    Args:
        run_id: The run to assign tags to.
        tag_ids: The complete desired set of tag IDs (replaces any existing
            assignment).

    Returns:
        The assigned tags, ordered by name.

    Raises:
        ValueError: If any tag_id doesn't reference a live tag.
    """
    # Dedupe (preserving first-seen order) so a repeated id can't violate the
    # join table's primary key.
    tag_ids = list(dict.fromkeys(tag_ids))
    tags = get_tags_by_ids(tag_ids)
    _raise_if_unknown_ids(tag_ids, tags)

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM run_tags WHERE run_id = %s", (run_id,))
                if tag_ids:
                    cursor.executemany(
                        "INSERT INTO run_tags (run_id, tag_id) VALUES (%s, %s)",
                        [(run_id, tag_id) for tag_id in tag_ids],
                    )
    return sorted(tags, key=lambda t: t.name.lower())


def set_ride_tags(ride_id: str, tag_ids: list[str]) -> list[Tag]:
    """Replace the full set of tags assigned to a ride.

    Args:
        ride_id: The ride to assign tags to.
        tag_ids: The complete desired set of tag IDs (replaces any existing
            assignment).

    Returns:
        The assigned tags, ordered by name.

    Raises:
        ValueError: If any tag_id doesn't reference a live tag.
    """
    # Dedupe (preserving first-seen order) so a repeated id can't violate the
    # join table's primary key.
    tag_ids = list(dict.fromkeys(tag_ids))
    tags = get_tags_by_ids(tag_ids)
    _raise_if_unknown_ids(tag_ids, tags)

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM ride_tags WHERE ride_id = %s", (ride_id,))
                if tag_ids:
                    cursor.executemany(
                        "INSERT INTO ride_tags (ride_id, tag_id) VALUES (%s, %s)",
                        [(ride_id, tag_id) for tag_id in tag_ids],
                    )
    return sorted(tags, key=lambda t: t.name.lower())


def get_tags_for_run_ids(run_ids: list[str]) -> dict[str, list[Tag]]:
    """Get live tags for a set of runs, grouped by run ID. {} for empty input."""
    if not run_ids:
        return {}
    with get_db_cursor() as cursor:
        placeholders = sql.SQL(", ").join(sql.Placeholder() * len(run_ids))
        query = sql.SQL("""
            SELECT rt.run_id, t.id, t.name, t.created_at
            FROM run_tags rt
            JOIN tags t ON t.id = rt.tag_id
            WHERE rt.run_id IN ({placeholders}) AND t.deleted_at IS NULL
            ORDER BY t.name
        """).format(placeholders=placeholders)
        cursor.execute(query, run_ids)
        result: dict[str, list[Tag]] = {}
        for run_id, tag_id, name, created_at in cursor.fetchall():
            result.setdefault(run_id, []).append(
                Tag(id=tag_id, name=name, created_at=created_at)
            )
        return result


def get_tags_for_ride_ids(ride_ids: list[str]) -> dict[str, list[Tag]]:
    """Get live tags for a set of rides, grouped by ride ID. {} for empty input."""
    if not ride_ids:
        return {}
    with get_db_cursor() as cursor:
        placeholders = sql.SQL(", ").join(sql.Placeholder() * len(ride_ids))
        query = sql.SQL("""
            SELECT rt.ride_id, t.id, t.name, t.created_at
            FROM ride_tags rt
            JOIN tags t ON t.id = rt.tag_id
            WHERE rt.ride_id IN ({placeholders}) AND t.deleted_at IS NULL
            ORDER BY t.name
        """).format(placeholders=placeholders)
        cursor.execute(query, ride_ids)
        result: dict[str, list[Tag]] = {}
        for ride_id, tag_id, name, created_at in cursor.fetchall():
            result.setdefault(ride_id, []).append(
                Tag(id=tag_id, name=name, created_at=created_at)
            )
        return result


def _raise_if_unknown_ids(tag_ids: list[str], found_tags: list[Tag]) -> None:
    """Raise ValueError naming any tag_ids not present among found_tags."""
    found_ids = {tag.id for tag in found_tags}
    unknown = [tag_id for tag_id in tag_ids if tag_id not in found_ids]
    if unknown:
        raise ValueError(f"Unknown tag id(s): {', '.join(unknown)}")


def _row_to_tag(row) -> Tag:
    """Convert a database row to a Tag."""
    tag_id, name, created_at = row
    return Tag(id=tag_id, name=name, created_at=created_at)
