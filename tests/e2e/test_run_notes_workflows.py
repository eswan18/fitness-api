"""End-to-end tests for per-run markdown notes."""

import pytest
from datetime import datetime

from fitness.models import Run
from fitness.db.runs import bulk_create_runs

_RANGE = {"start": "2025-03-01", "end": "2025-03-01"}


def _detail(client, run_id: str):
    res = client.get("/runs-details", params=_RANGE)
    assert res.status_code == 200
    return next((r for r in res.json() if r["id"] == run_id), None)


@pytest.mark.e2e
def test_run_note_set_preserve_clear(viewer_client, editor_client):
    """A run note is settable, survives a re-import, and is clearable."""
    run = Run(
        id="run_notes_e2e_1",
        datetime_utc=datetime(2025, 3, 1, 9, 0, 0),
        type="Outdoor Run",
        distance=4.0,
        duration=1800.0,
        source="Strava",
        avg_heart_rate=150.0,
    )
    assert bulk_create_runs([run]) == 1

    # Starts with no note (and the RunDetail read path carries the column).
    assert _detail(viewer_client, "run_notes_e2e_1")["notes"] is None

    # Set a markdown note.
    res = editor_client.patch(
        "/runs/run_notes_e2e_1/notes", json={"notes": "Felt **strong** today"}
    )
    assert res.status_code == 200
    assert res.json()["notes"] == "Felt **strong** today"

    # Re-importing the same run id is a no-op and must NOT clobber the note.
    assert bulk_create_runs([run]) == 0
    assert _detail(viewer_client, "run_notes_e2e_1")["notes"] == "Felt **strong** today"

    # Clearing: blank content normalizes to NULL.
    res = editor_client.patch(
        "/runs/run_notes_e2e_1/notes", json={"notes": "   "}
    )
    assert res.status_code == 200
    assert res.json()["notes"] is None
    assert _detail(viewer_client, "run_notes_e2e_1")["notes"] is None


@pytest.mark.e2e
def test_run_note_requires_existing_run(editor_client):
    res = editor_client.patch(
        "/runs/nonexistent_run_xyz/notes", json={"notes": "hi"}
    )
    assert res.status_code == 404
