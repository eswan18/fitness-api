from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from fitness.models import Ride, LocalizedRide
from tests._factories import StravaRideActivityFactory


def test_ride_from_strava_outdoor(
    strava_ride_activity_factory: StravaRideActivityFactory,
):
    activity = strava_ride_activity_factory.make(
        update={
            "start_date": datetime(2024, 11, 4, tzinfo=timezone.utc),
            "type": "Ride",
            "distance": 16093.4,  # 10 miles in meters
            "moving_time": 1700,
            "elapsed_time": 1800,
            "average_heartrate": 142.0,
        }
    )
    ride = Ride.from_strava(activity)
    assert ride.datetime_utc == datetime(2024, 11, 4)
    assert ride.type == "Outdoor Ride"
    assert ride.distance == pytest.approx(10, rel=1e-4)
    assert ride.duration == 1800  # elapsed_time, parity with Run
    assert ride.avg_heart_rate == 142.0
    assert ride.source == "Strava"
    assert ride.id == f"strava_{activity.id}"
    assert ride.deleted_at is None


def test_ride_from_strava_virtual(
    strava_ride_activity_factory: StravaRideActivityFactory,
):
    activity = strava_ride_activity_factory.make(
        update={
            "type": "VirtualRide",
            "trainer": True,
            "average_heartrate": 158.0,
        }
    )
    ride = Ride.from_strava(activity)
    assert ride.type == "Indoor Ride"
    assert ride.avg_heart_rate == 158.0


def test_ride_from_strava_trainer_ride_classified_indoor(
    strava_ride_activity_factory: StravaRideActivityFactory,
):
    """Strava's VirtualRide type is set automatically by Zwift/etc.; manually
    uploaded indoor rides come in as type='Ride' with trainer=True. Both
    shapes must classify as 'Indoor Ride'."""
    activity = strava_ride_activity_factory.make(
        update={"type": "Ride", "trainer": True, "average_heartrate": 150.0}
    )
    ride = Ride.from_strava(activity)
    assert ride.type == "Indoor Ride"


def test_ride_from_strava_outdoor_explicit_no_trainer(
    strava_ride_activity_factory: StravaRideActivityFactory,
):
    """Confirm trainer=False on a regular Ride still maps to Outdoor Ride."""
    activity = strava_ride_activity_factory.make(
        update={"type": "Ride", "trainer": False, "average_heartrate": 145.0}
    )
    ride = Ride.from_strava(activity)
    assert ride.type == "Outdoor Ride"


def test_ride_from_strava_no_heartrate(
    strava_ride_activity_factory: StravaRideActivityFactory,
):
    activity = strava_ride_activity_factory.make(
        update={"average_heartrate": None}
    )
    ride = Ride.from_strava(activity)
    assert ride.avg_heart_rate is None


def test_ride_rejects_invalid_type():
    with pytest.raises(ValidationError):
        Ride(
            id="strava_1",
            datetime_utc=datetime(2024, 1, 1),
            type="Outdoor Run",  # ty: ignore[invalid-argument-type]
            distance=10.0,
            duration=1800,
            source="Strava",
        )


def test_localized_ride_from_ride():
    ride = Ride(
        id="strava_1",
        datetime_utc=datetime(2024, 6, 1, 14, 0),  # 14:00 UTC
        type="Outdoor Ride",
        distance=10.0,
        duration=1800,
        source="Strava",
        avg_heart_rate=140.0,
    )
    localized = LocalizedRide.from_ride(ride, "America/Chicago")
    # 14:00 UTC = 09:00 CDT (CST is -6, CDT is -5; June -> CDT)
    assert localized.localized_datetime.hour == 9
    assert localized.local_date == ride.datetime_utc.date()
    assert localized.id == ride.id
    assert localized.avg_heart_rate == 140.0


def test_ride_soft_delete_and_restore():
    ride = Ride(
        id="strava_1",
        datetime_utc=datetime(2024, 1, 1),
        type="Outdoor Ride",
        distance=5.0,
        duration=900,
        source="Strava",
    )
    assert ride.is_deleted is False
    ride.soft_delete()
    assert ride.is_deleted is True
    assert ride.deleted_at is not None
    ride.restore()
    assert ride.is_deleted is False
    assert ride.deleted_at is None
