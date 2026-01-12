from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, TypeAdapter, AwareDatetime

SHOE_RENAME_MAP = {
    "Adizero SL": "Adidas Adizero SL",
    "M1080K10": "New Balance M1080K10",
    "M1080R10": "New Balance M1080R10",
    "Ghost 15": "Brooks Ghost 15",
    "Ghost 16": "Brooks Ghost 16",
    "Pegasus 38": "Nike Air Zoom Pegasus 38",
}


class StravaAthlete(BaseModel):
    id: int
    resource_state: int


StravaActivityType = Literal[
    "Workout", "Ride", "Walk", "Run", "Indoor Run", "Yoga", "WeightTraining", "Hike"
]


class StravaActivity(BaseModel):
    """An activity pulled from the Strava API."""

    id: int
    name: str
    resource_state: int
    type: StravaActivityType
    commute: bool
    start_date: AwareDatetime
    start_date_local: AwareDatetime
    timezone: str
    utc_offset: float
    distance: float
    moving_time: int
    elapsed_time: int
    total_elevation_gain: float
    has_kudoed: bool
    has_heartrate: bool
    athlete: StravaAthlete
    manual: bool
    kilojoules: float | None = None
    start_latlng: list[float]
    end_latlng: list[float]
    achievement_count: int
    kudos_count: int
    comment_count: int
    athlete_count: int
    total_photo_count: int
    max_speed: float
    from_accepted_tag: bool
    sport_type: str
    trainer: bool
    photo_count: int
    private: bool
    pr_count: int
    heartrate_opt_out: bool
    average_speed: float
    visibility: str
    upload_id: int | None = None
    external_id: str | None = None
    device_watts: bool | None = None
    suffer_score: float | None = None
    workout_type: int | None = None
    gear_id: str | None = None
    elev_low: float | None = None
    elev_high: float | None = None
    max_heartrate: float | None = None
    average_heartrate: float | None = None
    upload_id_str: str | None = None
    average_watts: float | None = None

    def with_gear(self, gear: StravaGear) -> StravaActivityWithGear:
        """Return a new StravaActivityWithGear with the given gear."""
        return StravaActivityWithGear(
            id=self.id,
            name=self.name,
            resource_state=self.resource_state,
            type=self.type,
            commute=self.commute,
            start_date=self.start_date,
            start_date_local=self.start_date_local,
            timezone=self.timezone,
            utc_offset=self.utc_offset,
            distance=self.distance,
            moving_time=self.moving_time,
            elapsed_time=self.elapsed_time,
            total_elevation_gain=self.total_elevation_gain,
            has_kudoed=self.has_kudoed,
            has_heartrate=self.has_heartrate,
            athlete=self.athlete,
            manual=self.manual,
            kilojoules=self.kilojoules,
            start_latlng=self.start_latlng,
            end_latlng=self.end_latlng,
            achievement_count=self.achievement_count,
            kudos_count=self.kudos_count,
            comment_count=self.comment_count,
            athlete_count=self.athlete_count,
            total_photo_count=self.total_photo_count,
            max_speed=self.max_speed,
            from_accepted_tag=self.from_accepted_tag,
            sport_type=self.sport_type,
            trainer=self.trainer,
            photo_count=self.photo_count,
            private=self.private,
            pr_count=self.pr_count,
            heartrate_opt_out=self.heartrate_opt_out,
            average_speed=self.average_speed,
            visibility=self.visibility,
            upload_id=self.upload_id,
            external_id=self.external_id,
            device_watts=self.device_watts,
            suffer_score=self.suffer_score,
            workout_type=self.workout_type,
            gear_id=self.gear_id,
            elev_low=self.elev_low,
            elev_high=self.elev_high,
            max_heartrate=self.max_heartrate,
            average_heartrate=self.average_heartrate,
            upload_id_str=self.upload_id_str,
            average_watts=self.average_watts,
            gear=gear,
        )


activity_list_adapter = TypeAdapter(list[StravaActivity])


class StravaGear(BaseModel):
    """An gear accessory pulled from the Strava API."""

    id: str
    name: str
    nickname: str
    brand_name: str
    model_name: str
    converted_distance: float
    distance: int | float
    notification_distance: int
    primary: bool
    resource_state: int
    retired: bool


gear_list_adapter = TypeAdapter(list[StravaGear])


class StravaToken(BaseModel):
    """An OAuth token for the Strava API."""

    token_type: Literal["Bearer"]
    expires_at: int
    expires_in: int
    refresh_token: str
    access_token: str

    def expires_at_datetime(self) -> datetime:
        return datetime.fromtimestamp(self.expires_at, tz=timezone.utc)


class StravaActivityWithGear(StravaActivity):
    """A merged Strava activity and gear."""

    gear: StravaGear

    def shoes(self) -> str | None:
        """Get the shoes used for this activity."""
        nickname = self.gear.nickname
        if nickname in SHOE_RENAME_MAP:
            return SHOE_RENAME_MAP[nickname]
        return self.gear.nickname

    def distance_miles(self) -> float:
        """Return the distance to miles."""
        return self.distance * 0.000621371
