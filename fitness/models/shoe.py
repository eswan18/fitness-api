from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Optional
import re

from pydantic import BaseModel


class ShoeRetirementInfo(BaseModel):
    """Information about a retired shoe."""

    retired_at: date
    retirement_notes: Optional[str] = None


def generate_shoe_id(shoe_name: str) -> str:
    """
    Generate a deterministic ID from a shoe name.

    Normalizes the name by:
    - Converting to lowercase
    - Replacing spaces and special chars with underscores
    - Removing consecutive underscores
    - Stripping leading/trailing underscores
    """
    # Convert to lowercase and replace spaces/special chars with underscores
    normalized = re.sub(r"[^a-z0-9]+", "_", shoe_name.lower())
    # Remove consecutive underscores and strip
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


class Shoe(BaseModel):
    id: str  # Generated from shoe name
    name: str  # The display name of the shoe
    retired_at: Optional[date] = None
    notes: Optional[str] = None  # General notes
    retirement_notes: Optional[str] = None  # Notes specific to retirement
    deleted_at: Optional[datetime] = None

    @property
    def is_retired(self) -> bool:
        """Check if the shoe is retired (has a retirement date)."""
        return self.retired_at is not None

    @property
    def is_deleted(self) -> bool:
        """Check if the shoe is soft-deleted."""
        return self.deleted_at is not None

    @classmethod
    def from_name(cls, name: str) -> Shoe:
        """Create a new shoe from just a name."""
        return cls(
            id=generate_shoe_id(name),
            name=name,
        )

    @classmethod
    def retired_shoe(
        cls, name: str, retired_at: date, retirement_notes: Optional[str] = None
    ) -> Shoe:
        """Create a retired shoe."""
        return cls(
            id=generate_shoe_id(name),
            name=name,
            retired_at=retired_at,
            retirement_notes=retirement_notes,
        )

    def retire(self, retired_at: date, retirement_notes: Optional[str] = None) -> None:
        """Mark this shoe as retired."""
        self.retired_at = retired_at
        self.retirement_notes = retirement_notes

    def unretire(self) -> None:
        """Mark this shoe as active (not retired)."""
        self.retired_at = None
        self.retirement_notes = None

    def soft_delete(self) -> None:
        """Soft delete this shoe."""
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        """Restore a soft-deleted shoe."""
        self.deleted_at = None


class ShoeMileage(BaseModel):
    """Shoe with associated mileage data."""

    model_config = {"arbitrary_types_allowed": True}

    shoe: Shoe
    mileage: float

    def __lt__(self, other: "ShoeMileage") -> bool:
        return self.mileage < other.mileage
