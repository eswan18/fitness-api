"""Unit tests for the duplicate-suggestion matcher (pure, no DB)."""

from datetime import datetime

from fitness.models.run_detail import RunDetail
from fitness.models.run import RunSource
from fitness.models.ride_detail import RideDetail
from fitness.models.ride import RideSource
from fitness.utils.duplicate_matching import find_duplicate_suggestions


def _run(
    rid: str,
    source: RunSource,
    dt: datetime,
    *,
    distance: float = 5.0,
    duration: float = 1800.0,
    is_synced: bool = False,
) -> RunDetail:
    return RunDetail(
        id=rid,
        datetime_utc=dt,
        type="Outdoor Run",
        distance=distance,
        duration=duration,
        source=source,
        is_synced=is_synced,
    )


def _ride(
    rid: str,
    source: RideSource,
    dt: datetime,
    *,
    distance: float = 12.0,
    duration: float = 3600.0,
) -> RideDetail:
    return RideDetail(
        id=rid,
        datetime_utc=dt,
        type="Outdoor Ride",
        distance=distance,
        duration=duration,
        source=source,
    )


def test_matches_cross_source_near_pair():
    runs = [
        _run("strava_1", "Strava", datetime(2025, 1, 1, 7, 0, 0)),
        _run("hae_1", "Apple Health", datetime(2025, 1, 1, 7, 2, 0)),
    ]
    pairs = find_duplicate_suggestions(runs)
    assert len(pairs) == 1
    ids = {pairs[0].keep.id, pairs[0].duplicate.id}
    assert ids == {"strava_1", "hae_1"}
    assert 0.0 <= pairs[0].score <= 1.0


def test_rejects_same_source():
    runs = [
        _run("strava_1", "Strava", datetime(2025, 1, 1, 7, 0, 0)),
        _run("strava_2", "Strava", datetime(2025, 1, 1, 7, 2, 0)),
    ]
    assert find_duplicate_suggestions(runs) == []


def test_rejects_out_of_window():
    runs = [
        _run("strava_1", "Strava", datetime(2025, 1, 1, 7, 0, 0)),
        _run("hae_1", "Apple Health", datetime(2025, 1, 1, 7, 30, 0)),
    ]
    assert find_duplicate_suggestions(runs, window_minutes=15) == []


def test_rejects_dissimilar_distance():
    runs = [
        _run("strava_1", "Strava", datetime(2025, 1, 1, 7, 0, 0), distance=5.0),
        _run("hae_1", "Apple Health", datetime(2025, 1, 1, 7, 1, 0), distance=9.0),
    ]
    assert find_duplicate_suggestions(runs) == []


def test_rejects_dissimilar_duration():
    runs = [
        _run("strava_1", "Strava", datetime(2025, 1, 1, 7, 0, 0), duration=1800.0),
        _run("hae_1", "Apple Health", datetime(2025, 1, 1, 7, 1, 0), duration=3600.0),
    ]
    assert find_duplicate_suggestions(runs) == []


def test_greedy_best_match_avoids_double_listing():
    # A matches both B (closer) and C; A must appear in only the best pair.
    runs = [
        _run("strava_A", "Strava", datetime(2025, 1, 1, 7, 0, 0)),
        _run("hae_B", "Apple Health", datetime(2025, 1, 1, 7, 1, 0)),
        _run("hae_C", "Apple Health", datetime(2025, 1, 1, 7, 10, 0)),
    ]
    pairs = find_duplicate_suggestions(runs)
    assert len(pairs) == 1
    assert {pairs[0].keep.id, pairs[0].duplicate.id} == {"strava_A", "hae_B"}


def test_keep_policy_prefers_synced():
    runs = [
        _run("strava_1", "Strava", datetime(2025, 1, 1, 7, 0, 0), is_synced=False),
        _run("hae_1", "Apple Health", datetime(2025, 1, 1, 7, 1, 0), is_synced=True),
    ]
    pair = find_duplicate_suggestions(runs)[0]
    assert pair.keep.id == "hae_1"
    assert pair.duplicate.id == "strava_1"


def test_keep_policy_falls_back_to_strava():
    runs = [
        _run("hae_1", "Apple Health", datetime(2025, 1, 1, 7, 0, 0)),
        _run("strava_1", "Strava", datetime(2025, 1, 1, 7, 1, 0)),
    ]
    pair = find_duplicate_suggestions(runs)[0]
    assert pair.keep.id == "strava_1"
    assert pair.duplicate.id == "hae_1"


def test_zero_distance_ride_matches_on_duration():
    rides = [
        _ride("strava_1", "Strava", datetime(2025, 1, 1, 7, 0, 0), distance=0.0),
        _ride("hae_1", "Apple Health", datetime(2025, 1, 1, 7, 2, 0), distance=0.0),
    ]
    pairs = find_duplicate_suggestions(rides)
    assert len(pairs) == 1
    assert {pairs[0].keep.id, pairs[0].duplicate.id} == {"strava_1", "hae_1"}
