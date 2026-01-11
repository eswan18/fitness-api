"""Database operations for user management."""

import logging
from typing import Optional
from uuid import UUID

from fitness.models.user import User, Role
from .connection import get_db_cursor

logger = logging.getLogger(__name__)


def get_user_by_idp_id(idp_user_id: UUID) -> Optional[User]:
    """Get a user by their identity provider user ID (sub claim)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, idp_user_id, email, username, role, created_at, updated_at
            FROM users
            WHERE idp_user_id = %s
            """,
            (str(idp_user_id),),
        )
        row = cursor.fetchone()
        return _row_to_user(row) if row else None


def create_user(
    idp_user_id: UUID,
    email: Optional[str],
    username: Optional[str],
    role: Role = "viewer",
) -> User:
    """Create a new user record.

    Args:
        idp_user_id: The 'sub' claim from the JWT token (identity provider user ID).
        email: User's email (cached from JWT, may be None).
        username: User's username (cached from JWT, may be None).
        role: User's role, defaults to 'viewer'.

    Returns:
        The created User object.
    """
    logger.info(
        f"Creating new user with idp_user_id={idp_user_id}, username={username}"
    )

    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO users (idp_user_id, email, username, role)
            VALUES (%s, %s, %s, %s)
            RETURNING id, idp_user_id, email, username, role, created_at, updated_at
            """,
            (str(idp_user_id), email, username, role),
        )
        row = cursor.fetchone()
        user = _row_to_user(row)
        logger.info(f"Created user id={user.id} for idp_user_id={idp_user_id}")
        return user


def update_user_profile(
    idp_user_id: UUID,
    email: Optional[str],
    username: Optional[str],
) -> Optional[User]:
    """Update a user's cached profile information.

    Called on each login to keep email/username in sync with the identity provider.

    Args:
        idp_user_id: The 'sub' claim from the JWT token.
        email: Updated email from the JWT.
        username: Updated username from the JWT.

    Returns:
        The updated User object, or None if user not found.
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE users
            SET email = %s, username = %s
            WHERE idp_user_id = %s
            RETURNING id, idp_user_id, email, username, role, created_at, updated_at
            """,
            (email, username, str(idp_user_id)),
        )
        row = cursor.fetchone()
        return _row_to_user(row) if row else None


def get_or_create_user(
    idp_user_id: UUID,
    email: Optional[str],
    username: Optional[str],
) -> User:
    """Get an existing user or create a new one.

    This is the main entry point for user management during authentication.
    If the user exists, their profile is updated with the latest email/username.
    If the user doesn't exist, a new user is created with 'viewer' role.

    Args:
        idp_user_id: The 'sub' claim from the JWT token.
        email: User's email from the JWT.
        username: User's username from the JWT.

    Returns:
        The User object (existing or newly created).
    """
    existing_user = get_user_by_idp_id(idp_user_id)

    if existing_user:
        # Update cached profile info if it changed
        if existing_user.email != email or existing_user.username != username:
            logger.debug(f"Updating profile for user {idp_user_id}")
            updated_user = update_user_profile(idp_user_id, email, username)
            if updated_user:
                return updated_user
        return existing_user

    # Create new user with default 'viewer' role
    return create_user(idp_user_id, email, username, role="viewer")


def _row_to_user(row) -> User:
    """Convert a database row to a User object."""
    id, idp_user_id, email, username, role, created_at, updated_at = row
    return User(
        id=id,
        idp_user_id=idp_user_id,
        email=email,
        username=username,
        role=role,
        created_at=created_at,
        updated_at=updated_at,
    )
