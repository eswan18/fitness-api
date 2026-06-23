from datetime import datetime, timezone, date
import zoneinfo

import pytest

from fitness.models import Run
from fitness.models.hae import HaeWorkout
from tests._factories import StravaActivityWithGearFactory, MmfActivityFactory


def _hae_run_workout(**overrides) -> HaeWorkout:
    base = {
        "id": "AAAA-1111",
        "name": "Running",
        "start": "2026-06-20 07:00:00 -0500",
        "end": "2026-06-20 07:30:00 -0500",
        "duration": 1800,
        "distance": {"qty": 10.0, "units": "km"},
        "avgHeartRate": {"qty": 150.0, "units": "count/min"},
        "maxHeartRate": {"qty": 175.0, "units": "count/min"},
        "stepCadence": {"qty": 168.0, "units": "spm"},
    }
    base.update(overrides)
    return HaeWorkout.model_validate(base)


def test_run_from_hae():
    run = Run.from_hae(_hae_run_workout())
    assert run.id == "hae_AAAA-1111"
    assert run.datetime_utc == datetime(2026, 6, 20, 12, 0, 0)  # -0500 -> UTC
    assert run.end_datetime_utc == datetime(2026, 6, 20, 12, 30, 0)
    assert run.type == "Outdoor Run"
    assert run.distance == pytest.approx(6.21371, abs=1e-4)  # 10 km -> miles
    assert run.duration == 1800
    assert run.avg_heart_rate == 150.0
    assert run.max_heart_rate == 175.0
    assert run.step_cadence == 168.0
    assert run.source == "Apple Health"
    assert run.source_name == "Running"
    assert run.deleted_at is None


def test_run_from_hae_indoor_maps_to_treadmill():
    run = Run.from_hae(_hae_run_workout(name="Indoor Running"))
    assert run.type == "Treadmill Run"


def test_run_from_strava(
    strava_activity_with_gear_factory: StravaActivityWithGearFactory,
):
    activity = strava_activity_with_gear_factory.make(
        update={
            "start_date": datetime(2024, 11, 4, tzinfo=timezone.utc),
            "type": "Run",
            "distance": 8046.72,  # 5 miles in meters
            "moving_time": 1800,
            "elapsed_time": 1800,
            "average_heartrate": 150.0,
        }
    )
    run = Run.from_strava(activity)
    assert run.datetime_utc == datetime(2024, 11, 4)
    assert run.type == "Outdoor Run"
    assert run.distance == pytest.approx(5)
    assert run.duration == 1800
    assert run.avg_heart_rate == 150.0
    assert run.shoe_name == activity.gear.nickname
    assert run.source == "Strava"
    assert run.id.startswith("strava_")  # Should be deterministic Strava ID
    assert run.deleted_at is None  # Should not be deleted by default


def test_run_from_mmf_activity(mmf_activity_factory: MmfActivityFactory):
    activity = mmf_activity_factory.make(
        update={
            "workout_date": datetime(2024, 11, 5, tzinfo=timezone.utc),
            "activity_type": "Run",
            "distance": 6,  # Unlike strava, MMF uses miles
            "workout_time": 1800,
            "avg_heart_rate": 154.0,
            "notes": "Shoes: Nike Air Zoom",
        }
    )
    run = Run.from_mmf(activity)
    # Robustly verify MMF default time behavior: stored UTC maps to 12:00 local on workout_date
    mmf_tz = zoneinfo.ZoneInfo(
        "America/Chicago"
    )  # default when MMF_TIMEZONE not set in tests
    local_dt = run.datetime_utc.replace(tzinfo=timezone.utc).astimezone(mmf_tz)
    assert local_dt.date() == date(2024, 11, 5)
    assert local_dt.hour == 12 and local_dt.minute == 0
    assert run.type == "Outdoor Run"
    assert run.distance == 6
    assert run.duration == 1800
    assert run.avg_heart_rate == 154.0
    assert run.shoe_name == "Nike Air Zoom"
    assert run.source == "MapMyFitness"
    assert run.id.startswith("mmf_")  # Should be deterministic MMF ID
    assert run.deleted_at is None  # Should not be deleted by default
