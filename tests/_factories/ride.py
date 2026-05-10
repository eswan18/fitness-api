from typing import Any, Mapping
from datetime import datetime
from fitness.models import Ride


class RideFactory:
    def __init__(self, ride: Ride | None = None):
        if ride is None:
            ride = Ride(
                id="test_ride_1",
                datetime_utc=datetime(2024, 6, 1, 12, 0, 0),
                type="Outdoor Ride",
                distance=12.0,
                duration=2700,
                source="Strava",
                avg_heart_rate=140.0,
                deleted_at=None,
            )
        self.ride = ride

    def make(self, update: Mapping[str, Any] | None = None) -> Ride:
        ride = self.ride.model_copy(deep=True, update=update)
        # Allow `date` shorthand mirroring RunFactory.
        if update and "date" in update and "datetime_utc" not in update:
            new_date = update["date"]
            update = dict(update)
            update["datetime_utc"] = datetime.combine(new_date, datetime.min.time())
            del update["date"]
            ride = self.ride.model_copy(deep=True, update=update)
        return ride
