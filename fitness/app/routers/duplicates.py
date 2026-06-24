"""Cross-cutting duplicate-detection endpoint (runs + rides).

Surfaces likely-duplicate pairs (the same physical activity arriving from both
Strava and Apple Health) for a review UI. Read-only: accepting a suggestion is
done via the existing `POST /{runs,rides}/{id}/duplicate-of` endpoints.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from fitness.app.auth import require_viewer
from fitness.db.runs import get_all_run_details
from fitness.db.rides import get_all_ride_details
from fitness.models.user import User
from fitness.utils.duplicate_matching import find_duplicate_suggestions

router = APIRouter(tags=["duplicates"])

ActivityKind = Literal["run", "ride"]


class SuggestionActivity(BaseModel):
    """One side of a suggested duplicate pair, projected for display."""

    id: str
    kind: ActivityKind
    datetime_utc: datetime
    type: str
    distance: float
    duration: float
    source: str
    avg_heart_rate: float | None = None
    is_synced: bool = False


class DuplicateSuggestion(BaseModel):
    """A likely-duplicate pair with a default keep/duplicate split."""

    kind: ActivityKind
    score: float
    keep: SuggestionActivity
    duplicate: SuggestionActivity


def _to_activity(detail, kind: ActivityKind) -> SuggestionActivity:
    return SuggestionActivity(
        id=detail.id,
        kind=kind,
        datetime_utc=detail.datetime_utc,
        type=detail.type,
        distance=detail.distance,
        duration=detail.duration,
        source=detail.source,
        avg_heart_rate=detail.avg_heart_rate,
        is_synced=detail.is_synced,
    )


@router.get("/duplicate-suggestions", response_model=list[DuplicateSuggestion])
def get_duplicate_suggestions(
    window_minutes: int = 15,
    distance_tol: float = 0.12,
    duration_tol: float = 0.12,
    _user: User = Depends(require_viewer),
) -> list[DuplicateSuggestion]:
    """List likely-duplicate run and ride pairs, highest-confidence first.

    Scans all non-deleted, non-duplicate activities (the read functions already
    exclude both) and pairs cross-source activities that are close in time,
    distance, and duration. Nothing is mutated — the client confirms each pair.
    """
    run_pairs = find_duplicate_suggestions(
        get_all_run_details(),
        window_minutes=window_minutes,
        distance_tol=distance_tol,
        duration_tol=duration_tol,
    )
    ride_pairs = find_duplicate_suggestions(
        get_all_ride_details(),
        window_minutes=window_minutes,
        distance_tol=distance_tol,
        duration_tol=duration_tol,
    )

    suggestions = [
        DuplicateSuggestion(
            kind="run",
            score=p.score,
            keep=_to_activity(p.keep, "run"),
            duplicate=_to_activity(p.duplicate, "run"),
        )
        for p in run_pairs
    ] + [
        DuplicateSuggestion(
            kind="ride",
            score=p.score,
            keep=_to_activity(p.keep, "ride"),
            duplicate=_to_activity(p.duplicate, "ride"),
        )
        for p in ride_pairs
    ]
    suggestions.sort(key=lambda s: s.score, reverse=True)
    return suggestions
