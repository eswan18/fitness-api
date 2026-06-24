"""Heuristic detection of likely duplicate activities across sources.

The same physical run/ride can arrive from both Strava and Apple Health. This
module pairs activities that look like the same session so the user can review
and confirm them. It is pure (no DB / no I/O) and works on any object exposing
the `_Activity` shape — in practice `RunDetail` / `RideDetail`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Generic, Protocol, Sequence, TypeVar

# Distance equal within this many miles always counts (covers 0-distance indoor
# rides, where the duration check carries the match).
_DISTANCE_FLOOR_MILES = 0.1
# Duration equal within this many seconds always counts.
_DURATION_FLOOR_SECONDS = 90.0


class _Activity(Protocol):
    # Read-only (property) members so subtypes with narrower attribute types
    # (e.g. RunDetail.source: Literal[...]) satisfy the protocol covariantly.
    @property
    def id(self) -> str: ...
    @property
    def datetime_utc(self) -> datetime: ...
    @property
    def distance(self) -> float: ...
    @property
    def duration(self) -> float: ...
    @property
    def source(self) -> str: ...
    @property
    def is_synced(self) -> bool: ...


A = TypeVar("A", bound=_Activity)


@dataclass
class SuggestionPair(Generic[A]):
    """A likely-duplicate pair, with a default-suggested keep/duplicate split."""

    keep: A
    duplicate: A
    score: float


def _relative_closeness(x: float, y: float) -> float:
    """1.0 when equal, → 0.0 as they diverge (by fraction of the larger)."""
    larger = max(x, y)
    if larger == 0:
        return 1.0
    return 1.0 - min(abs(x - y) / larger, 1.0)


def _distance_matches(d1: float, d2: float, tol: float) -> bool:
    if abs(d1 - d2) <= _DISTANCE_FLOOR_MILES:
        return True
    return _relative_closeness(d1, d2) >= 1.0 - tol


def _duration_matches(s1: float, s2: float, tol: float) -> bool:
    if abs(s1 - s2) <= _DURATION_FLOOR_SECONDS:
        return True
    return _relative_closeness(s1, s2) >= 1.0 - tol


def _score(a: _Activity, b: _Activity, window: timedelta) -> float:
    """Confidence in [0, 1]: closer in time/distance/duration scores higher."""
    time_gap = abs((a.datetime_utc - b.datetime_utc).total_seconds())
    time_score = 1.0 - min(time_gap / window.total_seconds(), 1.0)
    dist_score = _relative_closeness(a.distance, b.distance)
    dur_score = _relative_closeness(a.duration, b.duration)
    return round((time_score + dist_score + dur_score) / 3.0, 4)


def _choose_keep(earlier: A, later: A) -> tuple[A, A]:
    """Pick which side to keep by default; the other is the duplicate.

    Policy (per product decision): keep the calendar-synced copy if exactly one
    is synced; else keep the Strava copy; else keep the earlier-recorded copy.
    The review UI lets the user flip this per pair.
    """
    if earlier.is_synced != later.is_synced:
        keep = earlier if earlier.is_synced else later
    elif (earlier.source == "Strava") != (later.source == "Strava"):
        keep = earlier if earlier.source == "Strava" else later
    else:
        keep = earlier  # already the earlier of the two
    duplicate = later if keep is earlier else earlier
    return keep, duplicate


def find_duplicate_suggestions(
    activities: Sequence[A],
    *,
    window_minutes: int = 15,
    distance_tol: float = 0.12,
    duration_tol: float = 0.12,
) -> list[SuggestionPair[A]]:
    """Find likely-duplicate pairs among same-kind activities.

    A pair qualifies when the two come from *different* sources, start within
    `window_minutes` of each other, and have similar distance and duration.
    Pairs are returned greedily by descending confidence so that each activity
    appears in at most one suggestion.
    """
    window = timedelta(minutes=window_minutes)
    ordered = sorted(activities, key=lambda a: a.datetime_utc)

    scored: list[tuple[float, A, A]] = []
    for i, earlier in enumerate(ordered):
        for later in ordered[i + 1 :]:
            if later.datetime_utc - earlier.datetime_utc > window:
                break  # sorted by time → nothing further can match `earlier`
            if earlier.source == later.source:
                continue
            if not _distance_matches(earlier.distance, later.distance, distance_tol):
                continue
            if not _duration_matches(earlier.duration, later.duration, duration_tol):
                continue
            scored.append((_score(earlier, later, window), earlier, later))

    # Greedy best-match: highest-confidence pairs first, one use per activity.
    scored.sort(key=lambda t: t[0], reverse=True)
    used: set[str] = set()
    result: list[SuggestionPair[A]] = []
    for score, earlier, later in scored:
        if earlier.id in used or later.id in used:
            continue
        used.add(earlier.id)
        used.add(later.id)
        keep, duplicate = _choose_keep(earlier, later)
        result.append(SuggestionPair(keep=keep, duplicate=duplicate, score=score))
    return result
