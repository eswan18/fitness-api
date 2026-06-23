from datetime import datetime

import pytest

from fitness.models.hae import (
    HaeIngestRequest,
    HaeWorkout,
    is_indoor_workout,
    parse_hae_timestamp,
    quantity_to_miles,
    workout_category,
)


# ---- envelope / model parsing ------------------------------------------------


def _workout_dict(**overrides) -> dict:
    base = {
        "id": "ABCD-1234",
        "name": "Running",
        "start": "2026-06-20 07:14:32 -0500",
        "end": "2026-06-20 07:44:32 -0500",
        "duration": 1800,
        "distance": {"qty": 5.0, "units": "mi"},
        "avgHeartRate": {"qty": 150.0, "units": "count/min"},
        "maxHeartRate": {"qty": 175.0, "units": "count/min"},
        "stepCadence": {"qty": 168.0, "units": "spm"},
        # an extra field HAE includes that we don't model:
        "activeEnergyBurned": {"qty": 400.0, "units": "kcal"},
    }
    base.update(overrides)
    return base


def test_envelope_parses_and_exposes_workouts():
    payload = {"data": {"workouts": [_workout_dict()], "metrics": []}}
    req = HaeIngestRequest.model_validate(payload)
    assert len(req.data.workouts) == 1
    assert req.data.workouts[0].id == "ABCD-1234"


def test_camelcase_aliases_map_to_snake_case():
    w = HaeWorkout.model_validate(_workout_dict())
    assert w.avg_heart_rate is not None and w.avg_heart_rate.qty == 150.0
    assert w.max_heart_rate is not None and w.max_heart_rate.qty == 175.0
    assert w.step_cadence is not None and w.step_cadence.qty == 168.0


def test_unknown_fields_are_ignored():
    # activeEnergyBurned is not modeled; must not raise
    w = HaeWorkout.model_validate(_workout_dict())
    assert not hasattr(w, "activeEnergyBurned")


def test_missing_optional_quantities_default_to_none():
    w = HaeWorkout.model_validate(
        _workout_dict(avgHeartRate=None, stepCadence=None, distance=None)
    )
    assert w.avg_heart_rate is None
    assert w.step_cadence is None
    assert w.distance is None


# ---- timestamp parsing -------------------------------------------------------


def test_parse_hae_timestamp_converts_offset_to_naive_utc():
    # 07:14:32 -0500 == 12:14:32 UTC
    assert parse_hae_timestamp("2026-06-20 07:14:32 -0500") == datetime(
        2026, 6, 20, 12, 14, 32
    )


def test_parse_hae_timestamp_utc_offset():
    assert parse_hae_timestamp("2026-01-02 03:04:05 +0000") == datetime(
        2026, 1, 2, 3, 4, 5
    )


def test_parse_hae_timestamp_accepts_12_hour_am_pm_variant():
    # HAE emits a 12-hour locale variant for some users.
    assert parse_hae_timestamp("2026-06-20 7:14:32 PM -0500") == datetime(
        2026, 6, 21, 0, 14, 32
    )


def test_parse_hae_timestamp_rejects_iso8601_t():
    with pytest.raises(ValueError):
        parse_hae_timestamp("2026-06-20T07:14:32-05:00")


def test_parse_hae_timestamp_rejects_garbage():
    with pytest.raises(ValueError):
        parse_hae_timestamp("not a timestamp")


# ---- classification ----------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Running", "run"),
        ("Outdoor Run", "run"),
        ("Indoor Run", "run"),
        ("Trail Running", "run"),
        ("Cycling", "ride"),
        ("Indoor Cycling", "ride"),
        ("Outdoor Cycle", "ride"),
        ("Walking", None),
        ("Traditional Strength Training", None),
        ("Hiking", None),
    ],
)
def test_workout_category(name, expected):
    assert (
        workout_category(HaeWorkout.model_validate(_workout_dict(name=name)))
        == expected
    )


def test_is_indoor_prefers_explicit_flag():
    indoor = HaeWorkout.model_validate(_workout_dict(name="Running", isIndoor=True))
    outdoor = HaeWorkout.model_validate(_workout_dict(name="Running", isIndoor=False))
    assert is_indoor_workout(indoor) is True
    # explicit False wins even if other hints would say indoor
    assert is_indoor_workout(outdoor) is False


def test_is_indoor_falls_back_to_name_and_location():
    by_name = HaeWorkout.model_validate(_workout_dict(name="Treadmill"))
    by_location = HaeWorkout.model_validate(
        _workout_dict(name="Running", location="Indoor")
    )
    plain = HaeWorkout.model_validate(_workout_dict(name="Running"))
    assert is_indoor_workout(by_name) is True
    assert is_indoor_workout(by_location) is True
    assert is_indoor_workout(plain) is False


# ---- unit conversion ---------------------------------------------------------


def test_quantity_to_miles_passthrough_for_miles():
    assert quantity_to_miles(HaeWorkout.model_validate(_workout_dict()).distance) == 5.0


def test_quantity_to_miles_converts_km():
    miles = quantity_to_miles(
        HaeWorkout.model_validate(
            _workout_dict(distance={"qty": 10.0, "units": "km"})
        ).distance
    )
    assert miles == pytest.approx(6.21371, abs=1e-4)


def test_quantity_to_miles_none_is_zero():
    assert quantity_to_miles(None) == 0.0
