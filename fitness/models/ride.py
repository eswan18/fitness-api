from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import date, datetime, timezone
from typing import Literal, Self
import zoneinfo

from pydantic import BaseModel

if TYPE_CHECKING:
    from fitness.integrations.strava.models import (
        StravaActivity,
        StravaActivityType,
    )


RideType = Literal["Outdoor Ride", "Indoor Ride"]
RideSource = Literal["Strava"]


def _classify_strava_ride(strava_activity: "StravaActivity") -> RideType:
    """Map a Strava cycling activity to our RideType.

    Strava's `VirtualRide` is set automatically by virtual cycling apps
    (Zwift, MyWhoosh, TrainerRoad, etc.) — it is not a user-selectable
    type in Strava's UI. For a regular indoor trainer ride uploaded
    directly to Strava, the convention is `type="Ride"` with the
    `trainer` flag set to `true`. So both shapes map to "Indoor Ride".
    """
    if strava_activity.type == "VirtualRide":
        return "Indoor Ride"
    if strava_activity.type == "Ride":
        return "Indoor Ride" if strava_activity.trainer else "Outdoor Ride"
    raise ValueError(
        f"Unsupported Strava activity type for Ride: {strava_activity.type!r}"
    )


class Ride(BaseModel):
    id: str  # Deterministic ID: f"strava_{strava_id}"
    datetime_utc: datetime
    type: RideType
    distance: float  # in miles
    duration: float  # in seconds (Strava elapsed_time)
    source: RideSource
    avg_heart_rate: float | None = None
    deleted_at: datetime | None = None

    @property
    def is_deleted(self) -> bool:
        """Check if the ride is soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Soft delete this ride."""
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        """Restore a soft-deleted ride."""
        self.deleted_at = None

    def model_dump(self, **kwargs) -> dict:
        """Override model_dump to include date field for parity with Run."""
        data = super().model_dump(**kwargs)
        data["date"] = (
            self.datetime_utc.date() if self.datetime_utc is not None else None
        )
        return data

    @classmethod
    def from_strava(cls, strava_activity: "StravaActivity") -> Self:
        """Create a Ride from a raw Strava activity.

        Unlike Run.from_strava, takes StravaActivity directly (no gear lookup):
        rides do not currently track bike gear.
        """
        return cls(
            id=f"strava_{strava_activity.id}",
            datetime_utc=strava_activity.start_date.replace(tzinfo=None),
            type=_classify_strava_ride(strava_activity),
            distance=strava_activity.distance * 0.000621371,  # meters -> miles
            duration=strava_activity.elapsed_time,
            avg_heart_rate=strava_activity.average_heartrate,
            source="Strava",
        )


class LocalizedRide(Ride):
    """A ride with its datetime converted to user's local timezone."""

    localized_datetime: datetime

    @property
    def local_date(self) -> date:
        """Get the local date for this ride."""
        return self.localized_datetime.date()

    @classmethod
    def from_ride(cls, ride: Ride, user_timezone: str) -> Self:
        """Create a LocalizedRide from a Ride by converting to user timezone."""
        tz = zoneinfo.ZoneInfo(user_timezone)
        utc_aware = ride.datetime_utc.replace(tzinfo=timezone.utc)
        localized_datetime = utc_aware.astimezone(tz).replace(tzinfo=None)

        return cls(
            id=ride.id,
            datetime_utc=ride.datetime_utc,
            localized_datetime=localized_datetime,
            type=ride.type,
            distance=ride.distance,
            duration=ride.duration,
            source=ride.source,
            avg_heart_rate=ride.avg_heart_rate,
            deleted_at=ride.deleted_at,
        )
