"""End-to-end tests for the tags DB layer against real Postgres."""

from datetime import datetime

import pytest

from fitness.models import Run, Ride
from fitness.db.runs import bulk_create_runs
from fitness.db.rides import bulk_create_rides
from fitness.db.tags import (
    create_tag,
    delete_tag,
    get_all_tags,
    get_tag_by_id,
    get_tags_for_ride_ids,
    get_tags_for_run_ids,
    set_ride_tags,
    set_run_tags,
    update_tag_name,
)


def _make_run(run_id: str) -> None:
    run = Run(
        id=run_id,
        datetime_utc=datetime(2025, 4, 1, 9, 0, 0),
        type="Outdoor Run",
        distance=3.0,
        duration=1500.0,
        source="Strava",
        avg_heart_rate=145.0,
    )
    assert bulk_create_runs([run]) == 1


def _make_ride(ride_id: str) -> None:
    ride = Ride(
        id=ride_id,
        datetime_utc=datetime(2025, 4, 1, 9, 0, 0),
        type="Outdoor Ride",
        distance=10.0,
        duration=1800.0,
        source="Strava",
        avg_heart_rate=130.0,
    )
    assert bulk_create_rides([ride]) == 1


@pytest.mark.e2e
def test_create_tag_is_idempotent_case_insensitive(db_url: str):
    created = create_tag("Long Run")
    assert created.name == "Long Run"
    assert created.id.startswith("tag_")

    again = create_tag("long run")
    assert again.id == created.id
    assert again.name == "Long Run"  # existing casing is preserved, not overwritten


@pytest.mark.e2e
def test_get_all_tags_excludes_deleted(db_url: str):
    keep = create_tag("Tempo")
    gone = create_tag("Fartlek")
    assert delete_tag(gone.id) is True

    names = {t.name for t in get_all_tags()}
    assert keep.name in names
    assert gone.name not in names


@pytest.mark.e2e
def test_set_run_tags_replaces_full_set(db_url: str):
    _make_run("tag_e2e_run_1")
    speed = create_tag("Speedwork")
    hills = create_tag("Hills")
    recovery = create_tag("Recovery")

    result = set_run_tags("tag_e2e_run_1", [speed.id, hills.id])
    assert [t.name for t in result] == ["Hills", "Speedwork"]  # ordered by name

    # Replacing with a different set drops the old assignment entirely.
    result = set_run_tags("tag_e2e_run_1", [recovery.id])
    assert [t.id for t in result] == [recovery.id]

    grouped = get_tags_for_run_ids(["tag_e2e_run_1"])
    assert [t.id for t in grouped["tag_e2e_run_1"]] == [recovery.id]

    # Clearing with an empty list removes all assignments.
    result = set_run_tags("tag_e2e_run_1", [])
    assert result == []
    assert get_tags_for_run_ids(["tag_e2e_run_1"]) == {}


@pytest.mark.e2e
def test_set_run_tags_unknown_id_raises(db_url: str):
    _make_run("tag_e2e_run_2")
    with pytest.raises(ValueError):
        set_run_tags("tag_e2e_run_2", ["tag_does_not_exist"])
    # No partial assignment happened.
    assert get_tags_for_run_ids(["tag_e2e_run_2"]) == {}


@pytest.mark.e2e
def test_set_run_tags_dedupes_repeated_ids(db_url: str):
    """A duplicated tag id succeeds (no PK violation) and appears once."""
    _make_run("tag_e2e_run_6")
    tag = create_tag("Dedupe Me")

    result = set_run_tags("tag_e2e_run_6", [tag.id, tag.id])
    assert [t.id for t in result] == [tag.id]

    grouped = get_tags_for_run_ids(["tag_e2e_run_6"])
    assert [t.id for t in grouped["tag_e2e_run_6"]] == [tag.id]


@pytest.mark.e2e
def test_get_tags_for_run_ids_groups_and_excludes_deleted(db_url: str):
    _make_run("tag_e2e_run_3")
    _make_run("tag_e2e_run_4")
    a = create_tag("Group A")
    b = create_tag("Group B")

    set_run_tags("tag_e2e_run_3", [a.id, b.id])
    set_run_tags("tag_e2e_run_4", [b.id])

    grouped = get_tags_for_run_ids(["tag_e2e_run_3", "tag_e2e_run_4"])
    assert {t.id for t in grouped["tag_e2e_run_3"]} == {a.id, b.id}
    assert {t.id for t in grouped["tag_e2e_run_4"]} == {b.id}

    # Deleting a tag removes it from grouped results (assignments hard-deleted).
    delete_tag(b.id)
    grouped = get_tags_for_run_ids(["tag_e2e_run_3", "tag_e2e_run_4"])
    assert {t.id for t in grouped["tag_e2e_run_3"]} == {a.id}
    assert "tag_e2e_run_4" not in grouped

    # Empty input short-circuits to {}.
    assert get_tags_for_run_ids([]) == {}


@pytest.mark.e2e
def test_delete_tag_removes_assignments_and_frees_name(db_url: str):
    _make_run("tag_e2e_run_5")
    tag = create_tag("Interval")
    set_run_tags("tag_e2e_run_5", [tag.id])
    assert get_tags_for_run_ids(["tag_e2e_run_5"]) == {"tag_e2e_run_5": [tag]}

    assert delete_tag(tag.id) is True
    assert get_tags_for_run_ids(["tag_e2e_run_5"]) == {}
    # Deleting an already-deleted (or nonexistent) tag reports no match.
    assert delete_tag(tag.id) is False

    # The freed name can be recreated as a brand-new tag.
    recreated = create_tag("Interval")
    assert recreated.id != tag.id
    assert recreated.name == "Interval"
    assert recreated.id in {t.id for t in get_all_tags()}


@pytest.mark.e2e
def test_update_tag_name_renames_and_propagates_to_run_tags(db_url: str):
    _make_run("tag_e2e_run_7")
    tag = create_tag("Base Building")
    set_run_tags("tag_e2e_run_7", [tag.id])

    renamed = update_tag_name(tag.id, "Marathon Block")
    assert renamed is not None
    assert renamed.id == tag.id
    assert renamed.name == "Marathon Block"

    fetched = get_tag_by_id(tag.id)
    assert fetched is not None
    assert fetched.name == "Marathon Block"

    grouped = get_tags_for_run_ids(["tag_e2e_run_7"])
    assert [t.name for t in grouped["tag_e2e_run_7"]] == ["Marathon Block"]


@pytest.mark.e2e
def test_update_tag_name_conflict_with_live_tag_is_case_insensitive(db_url: str):
    create_tag("Easy Run")
    other = create_tag("Hard Run")

    with pytest.raises(ValueError):
        update_tag_name(other.id, "easy run")

    # The rename didn't happen.
    unchanged = get_tag_by_id(other.id)
    assert unchanged is not None
    assert unchanged.name == "Hard Run"


@pytest.mark.e2e
def test_update_tag_name_unknown_id_returns_none(db_url: str):
    assert update_tag_name("tag_does_not_exist", "New Name") is None


@pytest.mark.e2e
def test_set_ride_tags_replaces_full_set_and_groups(db_url: str):
    _make_ride("tag_e2e_ride_1")
    endurance = create_tag("Endurance Ride")
    crit = create_tag("Crit")

    result = set_ride_tags("tag_e2e_ride_1", [endurance.id, crit.id])
    assert {t.id for t in result} == {endurance.id, crit.id}

    result = set_ride_tags("tag_e2e_ride_1", [crit.id])
    assert [t.id for t in result] == [crit.id]

    grouped = get_tags_for_ride_ids(["tag_e2e_ride_1"])
    assert {t.id for t in grouped["tag_e2e_ride_1"]} == {crit.id}

    with pytest.raises(ValueError):
        set_ride_tags("tag_e2e_ride_1", ["tag_does_not_exist"])

    assert get_tags_for_ride_ids([]) == {}
