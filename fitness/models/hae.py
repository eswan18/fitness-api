"""Pydantic models + helpers for the Health Auto Export (HAE) JSON v2 payload.

HAE POSTs ``{ "data": { "workouts": [...], "metrics": [...] } }``. Each workout
carries camelCase fields and nested ``{qty, units}`` quantity objects. Timestamps
use the format ``yyyy-MM-dd HH:mm:ss Z`` (a space, then a numeric offset — NOT
ISO-8601 ``T``).

Reference: https://github.com/Lybron/health-auto-export/wiki/API-Export---JSON-Format
"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

# HAE timestamps look like "2026-06-20 07:14:32 -0500".
_HAE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S %z"

# 1 kilometre in miles.
_KM_TO_MILES = 0.621371


class HaeQuantity(BaseModel):
    """A nested ``{qty, units}`` measurement object."""

    model_config = ConfigDict(extra="ignore")

    qty: float | None = None
    units: str | None = None


class HaeWorkout(BaseModel):
    """A single HAE v2 workout. Unknown fields are ignored."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    name: str
    start: str
    end: str
    duration: float  # seconds
    distance: HaeQuantity | None = None
    avg_heart_rate: HaeQuantity | None = Field(default=None, alias="avgHeartRate")
    max_heart_rate: HaeQuantity | None = Field(default=None, alias="maxHeartRate")
    step_cadence: HaeQuantity | None = Field(default=None, alias="stepCadence")


class HaeData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    workouts: list[HaeWorkout] = Field(default_factory=list)
    metrics: list[dict] = Field(default_factory=list)  # accepted, ignored for v1


class HaeIngestRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: HaeData


def parse_hae_timestamp(value: str) -> datetime:
    """Parse a HAE timestamp into a naive-UTC datetime.

    Raises ValueError on anything that isn't ``yyyy-MM-dd HH:mm:ss Z`` (this
    includes ISO-8601 ``T``-separated strings).
    """
    aware = datetime.strptime(value, _HAE_TIME_FORMAT)
    return aware.astimezone(timezone.utc).replace(tzinfo=None)


def quantity_to_miles(distance: HaeQuantity | None) -> float:
    """Convert a HAE distance quantity to miles. Missing distance -> 0.0."""
    if distance is None or distance.qty is None:
        return 0.0
    units = (distance.units or "").lower()
    if units.startswith("km") or units == "kilometers" or units == "kilometres":
        return distance.qty * _KM_TO_MILES
    # Default: assume miles (HAE's default distance unit for US locales).
    return distance.qty


def quantity_value(quantity: HaeQuantity | None) -> float | None:
    """Return a quantity's raw ``qty`` (bpm, spm, …), or None if absent."""
    if quantity is None:
        return None
    return quantity.qty
