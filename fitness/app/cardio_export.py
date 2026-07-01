"""Serialize the cardio activity feed to downloadable CSV / JSON.

Pure functions (no DB, no HTTP) so they're easy to unit-test. The CSV flattens
the feed into one row per run or ride: a run-workout contributes one row per
constituent run, each tagged with its workout id/title (no aggregate row).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterator, Sequence
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi.encoders import jsonable_encoder

from fitness.app.constants import DEFAULT_START, DEFAULT_END
from fitness.app.routers.run_workouts import (
    ActivityFeedRideItem,
    ActivityFeedRunItem,
    ActivityFeedWorkoutItem,
)
from fitness.models.ride_detail import RideDetail
from fitness.models.run_detail import RunDetail

FeedItem = ActivityFeedRunItem | ActivityFeedWorkoutItem | ActivityFeedRideItem

# Column order for the CSV export. Run-only columns (shoes/notes/workout_*) are
# left blank for ride rows; pace is blank when distance is 0 (most rides). `name`
# and `tags` apply to both runs and rides (tags joined with "; ").
CSV_COLUMNS = [
    "activity_kind",
    "activity_id",
    "datetime_utc",
    "local_date",
    "type",
    "name",
    "source",
    "distance_mi",
    "duration_sec",
    "duration_hms",
    "avg_pace_min_per_mile",
    "avg_heart_rate",
    "shoes",
    "is_synced",
    "sync_status",
    "workout_id",
    "workout_title",
    "notes",
    "tags",
]


def export_filename(start: date, end: date, fmt: str) -> str:
    """Build a download filename, e.g. cardio-activities_2024-05-01_2024-05-31.csv.

    Open-ended bounds (the API defaults) render as `all` / `present`.
    """
    start_str = "all" if start == DEFAULT_START else start.isoformat()
    end_str = "present" if end == DEFAULT_END else end.isoformat()
    return f"cardio-activities_{start_str}_{end_str}.{fmt}"


def build_cardio_json(feed: Sequence[FeedItem]) -> str:
    """Serialize the feed to a JSON string with the same shape the live
    `/cardio-activity-feed` endpoint returns (a discriminated `{type, item}` array)."""
    return json.dumps(jsonable_encoder(feed))


def build_cardio_csv(feed: Sequence[FeedItem], user_timezone: str | None) -> str:
    """Serialize the feed to a CSV string, one row per run or ride."""
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=CSV_COLUMNS, restval="", extrasaction="ignore"
    )
    writer.writeheader()
    for row in _feed_to_rows(feed, user_timezone):
        writer.writerow(row)
    return buf.getvalue()


# --- Row construction ---


def _feed_to_rows(
    feed: Sequence[FeedItem], user_timezone: str | None
) -> Iterator[dict[str, object]]:
    for entry in feed:
        if isinstance(entry, ActivityFeedRunItem):
            yield _run_row(entry.item, user_timezone)
        elif isinstance(entry, ActivityFeedRideItem):
            yield _ride_row(entry.item, user_timezone)
        elif isinstance(entry, ActivityFeedWorkoutItem):
            for run in entry.item.runs:
                yield _run_row(
                    run,
                    user_timezone,
                    workout_id=entry.item.id,
                    workout_title=entry.item.title,
                )


def _run_row(
    run: RunDetail,
    user_timezone: str | None,
    workout_id: str | None = None,
    workout_title: str | None = None,
) -> dict[str, object]:
    return {
        "activity_kind": "run",
        "activity_id": run.id,
        "datetime_utc": _fmt_datetime_utc(run.datetime_utc),
        "local_date": _fmt_local_date(run.datetime_utc, user_timezone),
        "type": run.type,
        "name": run.name or "",
        "source": run.source,
        "distance_mi": round(run.distance, 2),
        "duration_sec": int(run.duration),
        "duration_hms": _fmt_hms(run.duration),
        "avg_pace_min_per_mile": _fmt_pace(run.distance, run.duration),
        "avg_heart_rate": _fmt_hr(run.avg_heart_rate),
        "shoes": run.shoes or "",
        "is_synced": str(run.is_synced).lower(),
        "sync_status": run.sync_status or "",
        "workout_id": workout_id or "",
        "workout_title": workout_title or "",
        "notes": run.notes or "",
        "tags": "; ".join(t.name for t in run.tags),
    }


def _ride_row(ride: RideDetail, user_timezone: str | None) -> dict[str, object]:
    # Rides carry no shoes/notes/workout membership — those columns stay blank.
    return {
        "activity_kind": "ride",
        "activity_id": ride.id,
        "datetime_utc": _fmt_datetime_utc(ride.datetime_utc),
        "local_date": _fmt_local_date(ride.datetime_utc, user_timezone),
        "type": ride.type,
        "name": ride.name or "",
        "source": ride.source,
        "distance_mi": round(ride.distance, 2),
        "duration_sec": int(ride.duration),
        "duration_hms": _fmt_hms(ride.duration),
        "avg_pace_min_per_mile": _fmt_pace(ride.distance, ride.duration),
        "avg_heart_rate": _fmt_hr(ride.avg_heart_rate),
        "is_synced": str(ride.is_synced).lower(),
        "sync_status": ride.sync_status or "",
        "tags": "; ".join(t.name for t in ride.tags),
    }


# --- Formatting helpers ---


def _fmt_datetime_utc(dt: datetime) -> str:
    """Naive-UTC datetime → ISO 8601 with a trailing `Z`."""
    return dt.isoformat() + "Z"


def _fmt_local_date(dt: datetime, user_timezone: str | None) -> str:
    """Local calendar date (YYYY-MM-DD) in `user_timezone`, else the UTC date.

    Matches the page's date grouping, which interprets `start`/`end` in the
    user's timezone.
    """
    if user_timezone is None:
        return dt.date().isoformat()
    tz = ZoneInfo(user_timezone)
    return dt.replace(tzinfo=timezone.utc).astimezone(tz).date().isoformat()


def _fmt_hms(seconds: float) -> str:
    """Seconds → H:MM:SS."""
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def _fmt_pace(distance: float, duration: float) -> str:
    """Average pace as M:SS per mile. Blank when distance is 0 (e.g. most rides)."""
    if distance <= 0:
        return ""
    sec_per_mile = duration / distance
    minutes, secs = divmod(int(round(sec_per_mile)), 60)
    return f"{minutes}:{secs:02d}"


def _fmt_hr(avg_heart_rate: float | None) -> object:
    """Average heart rate as an integer, or blank when missing."""
    return "" if avg_heart_rate is None else int(round(avg_heart_rate))
