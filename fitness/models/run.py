from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import date, datetime, timezone, time
from typing import Literal, Self
import os
import logging
import zoneinfo
import hashlib

from pydantic import BaseModel

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    # This prevents circular imports at runtime.
    from fitness.load.mmf import MmfActivity, MmfActivityType
    from fitness.integrations.strava.models import (
        StravaActivityType,
        StravaActivityWithGear,
    )
    from fitness.models.hae import HaeWorkout


RunType = Literal["Outdoor Run", "Treadmill Run"]
RunSource = Literal["MapMyFitness", "Strava", "Apple Health"]

# Map the MMF activity types to our run types.
MmfActivityMap: dict[MmfActivityType, RunType] = {
    "Indoor Run / Jog": "Treadmill Run",
    "Run": "Outdoor Run",
}
# Map the Strava activity types to our run types.
StravaActivityMap: dict[StravaActivityType, RunType] = {
    "Run": "Outdoor Run",
    "Indoor Run": "Treadmill Run",
}


class Run(BaseModel):
    id: str  # Deterministic ID: Strava ID for Strava runs, hash for MMF runs
    datetime_utc: datetime
    type: RunType
    distance: float  # in miles
    duration: float  # in seconds
    source: RunSource
    avg_heart_rate: float | None = None
    shoe_id: str | None = None  # Foreign key to shoes table
    notes: str | None = None  # User-authored markdown note (preserved across re-syncs)
    deleted_at: datetime | None = None
    # Set when this run was marked as a duplicate of another run (the kept one).
    duplicate_of_id: str | None = None
    # Captured from Health Auto Export (Apple Health); None for Strava/MMF runs.
    max_heart_rate: float | None = None
    step_cadence: float | None = None  # steps per minute
    end_datetime_utc: datetime | None = None
    source_name: str | None = None  # raw provider workout name, for provenance

    # Keep shoe name for backward compatibility and data loading
    _shoe_name: str | None = None

    @property
    def is_deleted(self) -> bool:
        """Check if the run is soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Soft delete this run."""
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        """Restore a soft-deleted run."""
        self.deleted_at = None

    def model_dump(self, **kwargs) -> dict:
        """Override model_dump to include date field for backward compatibility.

        Adds a derived `date` field (UTC) and `shoes` when available to maintain
        compatibility with existing API consumers.
        """
        data = super().model_dump(**kwargs)
        # Add the UTC date as 'date' field for backward compatibility
        if self.datetime_utc is not None:
            data["date"] = self.datetime_utc.date()
        else:
            # Fallback or warn about missing datetime
            logger.warning("Run missing datetime_utc: %s", data)
            data["date"] = None

        # Include shoe name for backward compatibility if available
        if self._shoe_name is not None:
            data["shoes"] = self._shoe_name

        return data

    @property
    def shoe_name(self) -> str | None:
        """Get the shoe name (for backward compatibility)."""
        return self._shoe_name

    @classmethod
    def from_mmf(cls, mmf_run: MmfActivity) -> Self:
        """Create a Run from a MapMyFitness activity.

        Uses UTC-normalized date derived from the source file's local timezone
        conversion step, constructs a deterministic ID from the activity link,
        and preserves shoe name if found in notes.
        """
        # Determine the local timezone for MMF data
        mmf_tz_name = os.environ.get("MMF_TIMEZONE", "America/Chicago")
        mmf_tz = zoneinfo.ZoneInfo(mmf_tz_name)

        # Use workout_date (local date) and default the time to 12:00 local time
        # so that activities display on the correct calendar day by default.
        local_date = mmf_run.workout_date
        local_noon = datetime.combine(local_date, time(hour=12, minute=0))
        local_noon_aware = local_noon.replace(tzinfo=mmf_tz)
        workout_datetime_utc = local_noon_aware.astimezone(timezone.utc).replace(
            tzinfo=None
        )

        # Extract the workout ID from the MMF link
        # Link format: https://www.mapmyfitness.com/workout/{workout_id}
        import re

        link_match = re.search(r"/workout/(\d+)", mmf_run.link)
        if link_match:
            workout_id = link_match.group(1)
            deterministic_id = f"mmf_{workout_id}"
        else:
            # Fallback if link doesn't match expected format
            # This shouldn't happen, but provides safety
            fallback_components = [
                "mmf_fallback",
                mmf_run.date_submitted.isoformat(),
                local_date.isoformat(),
                mmf_run.activity_type,
            ]
            fallback_string = "|".join(fallback_components)
            fallback_hash = hashlib.sha256(fallback_string.encode()).hexdigest()[:16]
            deterministic_id = f"mmf_fallback_{fallback_hash}"

        shoe_name = mmf_run.shoes()
        run = cls(
            id=deterministic_id,
            datetime_utc=workout_datetime_utc,
            type=MmfActivityMap[mmf_run.activity_type],
            distance=mmf_run.distance,
            duration=mmf_run.workout_time,
            avg_heart_rate=mmf_run.avg_heart_rate,
            source="MapMyFitness",
        )
        run._shoe_name = shoe_name
        return run

    @classmethod
    def from_hae(cls, workout: "HaeWorkout") -> Self:
        """Create a Run from a Health Auto Export (Apple Health) workout.

        The caller is responsible for confirming the workout is a run
        (``workout_category(workout) == "run"``) before calling this. Indoor vs
        outdoor is taken from the workout's ``isIndoor`` flag, not its name.
        """
        from fitness.models.hae import (
            is_indoor_workout,
            parse_hae_timestamp,
            quantity_to_miles,
            quantity_value,
        )

        run_type: RunType = (
            "Treadmill Run" if is_indoor_workout(workout) else "Outdoor Run"
        )
        return cls(
            id=f"hae_{workout.id}",
            datetime_utc=parse_hae_timestamp(workout.start),
            type=run_type,
            distance=quantity_to_miles(workout.distance),
            duration=workout.duration,
            avg_heart_rate=quantity_value(workout.avg_heart_rate),
            max_heart_rate=quantity_value(workout.max_heart_rate),
            step_cadence=quantity_value(workout.step_cadence),
            end_datetime_utc=parse_hae_timestamp(workout.end),
            source_name=workout.name,
            source="Apple Health",
        )

    @classmethod
    def from_strava(cls, strava_run: StravaActivityWithGear) -> Self:
        """Create a Run from a Strava activity with gear metadata."""
        shoe_name = strava_run.shoes()
        run = cls(
            id=f"strava_{strava_run.id}",  # Use Strava's ID with prefix
            datetime_utc=strava_run.start_date.replace(tzinfo=None),
            type=StravaActivityMap[strava_run.type],
            # Note that we need to convert the distance from meters to miles.
            distance=strava_run.distance_miles(),
            duration=strava_run.elapsed_time,
            avg_heart_rate=strava_run.average_heartrate,
            source="Strava",
        )
        run._shoe_name = shoe_name
        return run


class LocalizedRun(Run):
    """A run with its datetime converted to user's local timezone."""

    localized_datetime: datetime

    @property
    def local_date(self) -> date:
        """Get the local date for this run."""
        return self.localized_datetime.date()

    @classmethod
    def from_run(cls, run: Run, user_timezone: str) -> Self:
        """Create a LocalizedRun from a Run by converting to user timezone."""
        tz = zoneinfo.ZoneInfo(user_timezone)

        # Convert UTC datetime to user's local timezone
        utc_aware = run.datetime_utc.replace(tzinfo=timezone.utc)
        localized_datetime = utc_aware.astimezone(tz).replace(tzinfo=None)

        localized_run = cls(
            id=run.id,
            datetime_utc=run.datetime_utc,
            localized_datetime=localized_datetime,
            type=run.type,
            distance=run.distance,
            duration=run.duration,
            source=run.source,
            avg_heart_rate=run.avg_heart_rate,
            shoe_id=run.shoe_id,
            deleted_at=run.deleted_at,
        )
        localized_run._shoe_name = run._shoe_name
        return localized_run
