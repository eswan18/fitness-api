from typing import Callable
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from fitness.integrations.strava.models import StravaActivity, StravaAthlete, StravaGear
from fitness.load.strava import load_strava_runs


@pytest.fixture()
def make_sample_strava_activity() -> Callable[[], StravaActivity]:
    """Fixture to create a sample Strava activity."""
    next_id = 0

    def create_activity() -> StravaActivity:
        # Increment the ID for each new activity created.
        nonlocal next_id
        next_id += 1
        return StravaActivity(
            id=next_id,
            name="blah",
            resource_state=1,
            type="Run",
            commute=False,
            start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            start_date_local=datetime(2025, 1, 1, tzinfo=timezone.utc),
            timezone="UTC",
            utc_offset=0.0,
            distance=5000,
            moving_time=3600,
            elapsed_time=4000,
            total_elevation_gain=100,
            has_kudoed=False,
            has_heartrate=False,
            athlete=StravaAthlete(id=1, resource_state=1),
            manual=False,
            kilojoules=None,
            start_latlng=[37.7749, -122.4194],
            end_latlng=[37.7749, -122.4194],
            achievement_count=0,
            kudos_count=0,
            comment_count=0,
            athlete_count=1,
            total_photo_count=0,
            max_speed=5.0,
            from_accepted_tag=False,
            sport_type="Run",
            trainer=False,
            photo_count=0,
            private=False,
            pr_count=0,
            heartrate_opt_out=False,
            average_speed=5.0,
            visibility="everyone",
        )

    return create_activity


@pytest.fixture()
def make_sample_strava_gear() -> Callable[[], StravaGear]:
    """Fixture to create a sample Strava gear."""
    next_id = 0

    def create_gear() -> StravaGear:
        # Increment the ID for each new gear created.
        nonlocal next_id
        next_id += 1
        return StravaGear(
            id=str(next_id),
            name="blah",
            nickname="blah",
            brand_name="Nike",
            model_name="Air Zoom",
            converted_distance=0.0,
            distance=0,
            notification_distance=0,
            primary=False,
            resource_state=1,
            retired=False,
        )

    return create_gear


def test_strava_load(make_sample_strava_activity, make_sample_strava_gear, monkeypatch):
    # Mock the StravaClient to avoid making real HTTP requests.
    mock_client = MagicMock()
    run = make_sample_strava_activity()
    run.type = "Run"
    run.gear_id = "1"
    indoor_run = make_sample_strava_activity()
    indoor_run.type = "Indoor Run"
    indoor_run.gear_id = "2"
    bike = make_sample_strava_activity()
    bike.type = "Ride"
    bike.gear_id = "3"
    mock_client.get_activities.return_value = [run, indoor_run, bike]

    # Set up mocking of the gear fetching.
    gear1 = make_sample_strava_gear()
    gear1.id = "1"
    gear1.nickname = "Brooks Shoes"
    gear2 = make_sample_strava_gear()
    gear2.id = "2"
    gear2.nickname = "Nike Shoes"
    mock_client.get_gear.return_value = [gear1, gear2]
    result = load_strava_runs(mock_client)
    assert len(result.runs) == 2
    assert result.runs[0].gear.nickname == "Brooks Shoes"
    assert result.runs[1].gear.nickname == "Nike Shoes"
    assert result.skipped == []

    mock_client.get_gear.assert_called_once_with({"1", "2"})


def test_skips_runs_without_gear_id(make_sample_strava_activity, make_sample_strava_gear):
    """Runs with no gear_id are excluded and reported as 'no_gear_assigned'."""
    mock_client = MagicMock()
    shod = make_sample_strava_activity()
    shod.type = "Run"
    shod.gear_id = "1"
    shod.name = "Morning run"
    barefoot = make_sample_strava_activity()
    barefoot.type = "Run"
    barefoot.gear_id = None
    barefoot.name = "Treadmill, forgot to set shoes"
    mock_client.get_activities.return_value = [shod, barefoot]

    gear1 = make_sample_strava_gear()
    gear1.id = "1"
    mock_client.get_gear.return_value = [gear1]

    result = load_strava_runs(mock_client)

    assert [r.gear.id for r in result.runs] == ["1"]
    assert len(result.skipped) == 1
    skipped = result.skipped[0]
    assert skipped.id == str(barefoot.id)
    assert skipped.name == "Treadmill, forgot to set shoes"
    assert skipped.reason == "no_gear_assigned"


def test_skips_runs_when_gear_fetch_misses(make_sample_strava_activity, make_sample_strava_gear):
    """Runs whose gear_id isn't returned by the gear fetch are reported as 'gear_fetch_failed'."""
    mock_client = MagicMock()
    shod = make_sample_strava_activity()
    shod.type = "Run"
    shod.gear_id = "1"
    orphan = make_sample_strava_activity()
    orphan.type = "Run"
    orphan.gear_id = "deleted-gear"
    orphan.name = "Run with deleted gear"
    mock_client.get_activities.return_value = [shod, orphan]

    gear1 = make_sample_strava_gear()
    gear1.id = "1"
    # Note: only gear "1" is returned; "deleted-gear" is missing from the response.
    mock_client.get_gear.return_value = [gear1]

    result = load_strava_runs(mock_client)

    assert [r.gear.id for r in result.runs] == ["1"]
    assert len(result.skipped) == 1
    skipped = result.skipped[0]
    assert skipped.id == str(orphan.id)
    assert skipped.reason == "gear_fetch_failed"
