"""Pydantic models + helpers for the Health Auto Export (HAE) JSON v2 payload.

HAE POSTs ``{ "data": { "workouts": [...], "metrics": [...] } }``. Each workout
carries camelCase fields and nested ``{qty, units}`` quantity objects. Timestamps
use the format ``yyyy-MM-dd HH:mm:ss Z`` (a space, then a numeric offset — NOT
ISO-8601 ``T``).

Reference: https://github.com/Lybron/health-auto-export/wiki/API-Export---JSON-Format
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# HAE timestamps look like "2026-06-20 07:14:32 -0500" (the primary v2 form), but
# some locales emit a 12-hour AM/PM variant. The reference ingester accepts the
# same set. We try them in order.
_HAE_TIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S %z",  # 24-hour: 2026-06-20 07:14:32 -0500
    "%Y-%m-%d %I:%M:%S %p %z",  # 12-hour: 2026-06-20 7:14:32 PM -0500
)

# 1 kilometre in miles.
_KM_TO_MILES = 0.621371

# Workout-name keywords used to classify a workout into a run or ride. HealthKit
# has one activity type per modality (a treadmill run is still "running"), so we
# match on substrings and rely on `isIndoor` for the indoor/outdoor variant.
_RUN_NAME_KEYWORDS = ("run", "jog")
_RIDE_NAME_KEYWORDS = ("cycl", "bike", "biking")
_INDOOR_NAME_KEYWORDS = ("indoor", "treadmill", "stationary")


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
    is_indoor: bool | None = Field(default=None, alias="isIndoor")
    location: str | None = None
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

    Accepts the 24-hour and 12-hour AM/PM variants. Raises ValueError on
    anything else (including ISO-8601 ``T``-separated strings).
    """
    # HAE sometimes puts a narrow no-break space (U+202F) before AM/PM.
    normalized = value.replace("\u202f", " ")
    for fmt in _HAE_TIME_FORMATS:
        try:
            aware = datetime.strptime(normalized, fmt)
        except ValueError:
            continue
        return aware.astimezone(timezone.utc).replace(tzinfo=None)
    raise ValueError(f"Unrecognized HAE timestamp: {value!r}")


def workout_category(workout: "HaeWorkout") -> Literal["run", "ride"] | None:
    """Classify a workout as a run or ride by its name, else None (skip).

    Matches name substrings rather than exact strings because HAE's workout
    `name` is a HealthKit activity-type label whose exact wording varies
    (e.g. "Running" vs "Outdoor Run").
    """
    name = workout.name.lower()
    if any(keyword in name for keyword in _RUN_NAME_KEYWORDS):
        return "run"
    if any(keyword in name for keyword in _RIDE_NAME_KEYWORDS):
        return "ride"
    return None


def is_indoor_workout(workout: "HaeWorkout") -> bool:
    """Whether a workout is indoor.

    Prefers the explicit ``isIndoor`` flag (HealthKit's indoor metadata); falls
    back to the ``location`` field and then to name keywords.
    """
    if workout.is_indoor is not None:
        return workout.is_indoor
    if (workout.location or "").lower() == "indoor":
        return True
    name = workout.name.lower()
    return any(keyword in name for keyword in _INDOOR_NAME_KEYWORDS)


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
