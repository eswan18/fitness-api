from datetime import datetime, timezone

from typing import Any, Mapping

from fitness.integrations.strava.models import (
    StravaActivityWithGear,
    StravaGear,
    StravaAthlete,
)


class StravaActivityWithGearFactory:
    def __init__(self, activity: StravaActivityWithGear | None = None):
        if activity is None:
            activity = StravaActivityWithGear(
                id=1,
                name="Test Run",
                resource_state=2,
                type="Run",
                commute=False,
                start_date=datetime(2023, 10, 1, tzinfo=timezone.utc),
                start_date_local=datetime(2023, 10, 1, tzinfo=timezone.utc),
                timezone="UTC",
                utc_offset=0,
                distance=8046.72,  # 5 miles in meters
                moving_time=1800,
                elapsed_time=1800,
                total_elevation_gain=100.0,
                has_kudoed=False,
                has_heartrate=False,
                athlete=StravaAthlete(id=1, resource_state=2),
                manual=False,
                start_latlng=[0.0, 0.0],
                end_latlng=[0.0, 0.0],
                achievement_count=0,
                kudos_count=0,
                comment_count=0,
                athlete_count=0,
                total_photo_count=0,
                max_speed=0.0,
                from_accepted_tag=False,
                sport_type="Run",
                trainer=False,
                photo_count=0,
                private=False,
                pr_count=0,
                heartrate_opt_out=False,
                average_speed=4.0,
                visibility="everyone",
                gear=StravaGear(
                    id="g343",
                    name="Nike Air Zoom Pegasus 37 (Black/White)",
                    nickname="Nike Air Zoom Pegasus 37",
                    brand_name="Nike",
                    model_name="Air Zoom Pegasus 37",
                    converted_distance=0.0,
                    distance=0.0,
                    notification_distance=500,
                    primary=True,
                    resource_state=2,
                    retired=False,
                ),
            )
        self.activity = activity

    def make(self, update: Mapping[str, Any] | None = None) -> StravaActivityWithGear:
        return self.activity.model_copy(deep=True, update=update)
