"""Model for tags — freeform labels assignable to runs and rides."""

from datetime import datetime

from pydantic import BaseModel


class Tag(BaseModel):
    """A user-defined label that can be attached to runs and/or rides.

    Tags are soft-deleted (``deleted_at``, not exposed here) with a
    case-insensitive unique name among live tags; a deleted tag's name can be
    reused by a new tag.
    """

    id: str
    name: str
    created_at: datetime | None = None
