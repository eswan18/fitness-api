from datetime import datetime, timezone
from typing import Any, Mapping

from fitness.integrations.strava.models import StravaActivity, StravaAthlete


class StravaRideActivityFactory:
    """Factory for bare StravaActivity instances representing rides.

    Sibling of StravaActivityWithGearFactory, but for rides — rides do not
    track gear in v1, so the factory builds StravaActivity directly.
    """

    def __init__(self, activity: StravaActivity | None = None):
        if activity is None:
            activity = StravaActivity(
                id=1001,
                name="Test Outdoor Ride",
                resource_state=2,
                type="Ride",
                commute=False,
                start_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
                start_date_local=datetime(2024, 6, 1, tzinfo=timezone.utc),
                timezone="UTC",
                utc_offset=0,
                distance=20921.5,  # ~13 miles in meters
                moving_time=2700,
                elapsed_time=3000,
                total_elevation_gain=200.0,
                has_kudoed=False,
                has_heartrate=True,
                athlete=StravaAthlete(id=1, resource_state=2),
                manual=False,
                start_latlng=[0.0, 0.0],
                end_latlng=[0.0, 0.0],
                achievement_count=0,
                kudos_count=0,
                comment_count=0,
                athlete_count=0,
                total_photo_count=0,
                max_speed=12.0,
                from_accepted_tag=False,
                sport_type="Ride",
                trainer=False,
                photo_count=0,
                private=False,
                pr_count=0,
                heartrate_opt_out=False,
                average_speed=7.7,
                visibility="everyone",
            )
        self.activity = activity

    def make(self, update: Mapping[str, Any] | None = None) -> StravaActivity:
        return self.activity.model_copy(deep=True, update=update)
