"""Unit tests for the cardio export serializers (no HTTP, no DB)."""

import csv
import io
import json
from datetime import date, datetime

from fitness.app.constants import DEFAULT_START, DEFAULT_END
from fitness.app.cardio_export import (
    CSV_COLUMNS,
    build_cardio_csv,
    build_cardio_json,
    export_filename,
    _fmt_hms,
    _fmt_pace,
)
from fitness.app.routers.run_workouts import (
    ActivityFeedRideItem,
    ActivityFeedRunItem,
    ActivityFeedWorkoutItem,
)
from fitness.models.ride_detail import RideDetail
from fitness.models.run_detail import RunDetail
from fitness.models.run_workout import RunWorkoutDetail


def _run(
    id: str = "run_1",
    dt: datetime | None = None,
    distance: float = 3.0,
    duration: float = 1500.0,
    run_workout_id: str | None = None,
    **kwargs,
) -> RunDetail:
    return RunDetail(
        id=id,
        datetime_utc=dt or datetime(2024, 6, 1, 8, 0, 0),
        type="Outdoor Run",
        distance=distance,
        duration=duration,
        source="Strava",
        avg_heart_rate=kwargs.pop("avg_heart_rate", 150.0),
        run_workout_id=run_workout_id,
        **kwargs,
    )


def _ride(id: str = "ride_1", dt: datetime | None = None) -> RideDetail:
    return RideDetail(
        id=id,
        datetime_utc=dt or datetime(2024, 6, 1, 18, 0, 0),
        type="Indoor Ride",
        distance=0.0,
        duration=3600.0,
        source="Strava",
        avg_heart_rate=140.0,
    )


def _workout(
    runs: list[RunDetail], id: str = "rw_1", title: str = "Intervals"
) -> RunWorkoutDetail:
    return RunWorkoutDetail(
        id=id,
        title=title,
        start_datetime_utc=runs[0].datetime_utc,
        total_distance=sum(r.distance for r in runs),
        total_duration=sum(r.duration for r in runs),
        elapsed_seconds=1800.0,
        avg_heart_rate=160.0,
        run_count=len(runs),
        runs=runs,
    )


def _parse(csv_text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(csv_text)))


class TestBuildCsv:
    def test_header_matches_columns(self):
        text = build_cardio_csv([], None)
        header = next(csv.reader(io.StringIO(text)))
        assert header == CSV_COLUMNS

    def test_one_row_per_run_and_ride(self):
        feed = [
            ActivityFeedRunItem(item=_run("run_1")),
            ActivityFeedRideItem(item=_ride("ride_1")),
        ]
        rows = _parse(build_cardio_csv(feed, None))
        assert len(rows) == 2
        assert [r["activity_kind"] for r in rows] == ["run", "ride"]
        assert {r["activity_id"] for r in rows} == {"run_1", "ride_1"}

    def test_workout_flattened_into_tagged_run_rows(self):
        runs = [
            _run("r2", datetime(2024, 6, 2, 8, 0, 0), run_workout_id="rw_1"),
            _run("r3", datetime(2024, 6, 2, 8, 15, 0), run_workout_id="rw_1"),
        ]
        feed = [
            ActivityFeedRunItem(item=_run("solo")),
            ActivityFeedWorkoutItem(item=_workout(runs)),
        ]
        rows = _parse(build_cardio_csv(feed, None))
        # solo run + 2 workout runs = 3 rows; no aggregate workout row.
        assert len(rows) == 3
        assert all(r["activity_kind"] == "run" for r in rows)
        tagged = [r for r in rows if r["workout_id"]]
        assert len(tagged) == 2
        assert all(r["workout_id"] == "rw_1" for r in tagged)
        assert all(r["workout_title"] == "Intervals" for r in tagged)
        solo = next(r for r in rows if r["activity_id"] == "solo")
        assert solo["workout_id"] == ""

    def test_ride_blanks_run_only_columns_and_pace(self):
        rows = _parse(build_cardio_csv([ActivityFeedRideItem(item=_ride())], None))
        row = rows[0]
        assert row["shoes"] == ""
        assert row["notes"] == ""
        assert row["workout_id"] == ""
        # distance 0 → blank pace
        assert row["avg_pace_min_per_mile"] == ""

    def test_run_columns_populated(self):
        run = _run(
            "run_1", shoes="Pegasus", notes="easy", is_synced=True, sync_status="synced"
        )
        rows = _parse(build_cardio_csv([ActivityFeedRunItem(item=run)], None))
        row = rows[0]
        assert row["shoes"] == "Pegasus"
        assert row["notes"] == "easy"
        assert row["is_synced"] == "true"
        assert row["sync_status"] == "synced"
        assert row["datetime_utc"] == "2024-06-01T08:00:00Z"
        assert row["distance_mi"] == "3.0"
        assert row["duration_hms"] == "0:25:00"
        assert row["avg_pace_min_per_mile"] == "8:20"

    def test_missing_heart_rate_blank(self):
        run = _run("run_1", avg_heart_rate=None)
        rows = _parse(build_cardio_csv([ActivityFeedRunItem(item=run)], None))
        assert rows[0]["avg_heart_rate"] == ""

    def test_local_date_uses_user_timezone(self):
        # 04:30 UTC on Apr 10 is Apr 9 23:30 in Chicago (CDT, UTC-5).
        run = _run("run_1", dt=datetime(2026, 4, 10, 4, 30, 0))
        rows = _parse(
            build_cardio_csv([ActivityFeedRunItem(item=run)], "America/Chicago")
        )
        assert rows[0]["local_date"] == "2026-04-09"
        # Without a tz it falls back to the UTC date.
        rows_utc = _parse(build_cardio_csv([ActivityFeedRunItem(item=run)], None))
        assert rows_utc[0]["local_date"] == "2026-04-10"


class TestBuildJson:
    def test_returns_feed_array_shape(self):
        feed = [
            ActivityFeedRunItem(item=_run("run_1")),
            ActivityFeedRideItem(item=_ride("ride_1")),
        ]
        data = json.loads(build_cardio_json(feed))
        assert isinstance(data, list)
        assert {item["type"] for item in data} == {"run", "ride"}
        assert data[0]["item"]["id"] == "run_1"

    def test_workout_runs_nested(self):
        runs = [_run("r2", run_workout_id="rw_1"), _run("r3", run_workout_id="rw_1")]
        data = json.loads(
            build_cardio_json([ActivityFeedWorkoutItem(item=_workout(runs))])
        )
        assert data[0]["type"] == "run_workout"
        assert len(data[0]["item"]["runs"]) == 2


class TestFormatters:
    def test_fmt_hms(self):
        assert _fmt_hms(0) == "0:00:00"
        assert _fmt_hms(1500) == "0:25:00"
        assert _fmt_hms(3661) == "1:01:01"

    def test_fmt_pace(self):
        assert _fmt_pace(0.0, 3600.0) == ""
        assert _fmt_pace(3.0, 1500.0) == "8:20"
        assert _fmt_pace(1.0, 65.0) == "1:05"


class TestExportFilename:
    def test_bounded_range(self):
        assert export_filename(date(2024, 5, 1), date(2024, 5, 31), "csv") == (
            "cardio-activities_2024-05-01_2024-05-31.csv"
        )

    def test_open_ended_defaults(self):
        assert export_filename(DEFAULT_START, DEFAULT_END, "json") == (
            "cardio-activities_all_present.json"
        )
