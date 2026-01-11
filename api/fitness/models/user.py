"""User model for application-level user management."""

from __future__ import annotations
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


Role = Literal["viewer", "editor"]


class User(BaseModel):
    """Application user with role-based access control.

    Users are created automatically on first login via the identity provider.
    The idp_user_id links to the 'sub' claim from the JWT token.
    """

    id: UUID
    idp_user_id: UUID
    email: str | None
    username: str | None
    role: Role
    created_at: datetime
    updated_at: datetime

    @property
    def is_editor(self) -> bool:
        """Check if user has editor role."""
        return self.role == "editor"

    @property
    def is_viewer(self) -> bool:
        """Check if user has at least viewer role (all authenticated users)."""
        return self.role in ("viewer", "editor")
