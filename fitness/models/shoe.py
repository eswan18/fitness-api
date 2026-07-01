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
    id: str  # Opaque identifier
    # Structured identity (brand/model are NOT NULL in the db; the display name
    # is composed from them — see `display_name`). color is optional.
    brand: Optional[str] = None
    model: Optional[str] = None
    color: Optional[str] = None
    retired_at: Optional[date] = None
    notes: Optional[str] = None  # General notes
    retirement_notes: Optional[str] = None  # Notes specific to retirement
    deleted_at: Optional[datetime] = None
    # Per-shoe mileage thresholds. `warning_mileage` is where the UI starts
    # nudging; `maximum_mileage` is the replace / 100%-wear point. The UI's
    # intermediate "danger" mileage is the midpoint of the two, derived not stored.
    warning_mileage: int = 300
    maximum_mileage: int = 500
    # Nullable metadata: old/imported shoes may lack these. The API requires them
    # on newly-created shoes (POST /shoes/), but not in the schema.
    size: Optional[float] = None
    purchased_date: Optional[date] = None

    @property
    def display_name(self) -> str:
        """Human label composed from brand + model (not serialized)."""
        return " ".join(p for p in (self.brand, self.model) if p)

    @property
    def is_retired(self) -> bool:
        """Check if the shoe is retired (has a retirement date)."""
        return self.retired_at is not None

    @property
    def is_deleted(self) -> bool:
        """Check if the shoe is soft-deleted."""
        return self.deleted_at is not None

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


class ShoeRecentUse(BaseModel):
    """Shoe with the datetime of its most recent run, if any."""

    shoe: Shoe
    last_used_date: Optional[datetime] = None
