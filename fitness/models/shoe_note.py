"""Model for shoe notes — dated, freeform (markdown) log entries about a shoe."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class ShoeNote(BaseModel):
    """A dated note attached to a shoe.

    Notes accumulate over time and form a running log of thoughts about a pair
    of shoes. ``content`` is freeform markdown; ``note_date`` is the date the
    note applies to (defaults to today on create, but can be backdated).
    """

    id: str
    shoe_id: str
    note_date: date
    content: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
