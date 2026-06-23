"""End-to-end tests for shoe notes workflows."""

import pytest
from datetime import datetime
from fitness.models import Run
from fitness.db.runs import bulk_create_runs
from fitness.models.shoe import generate_shoe_id


@pytest.mark.e2e
def test_shoe_notes_crud_lifecycle(viewer_client, editor_client):
    """Create, list (newest-first), update, and delete dated notes on a shoe."""
    # Seed a shoe by creating a run that references it.
    shoe_name = "Notes Test Shoe"
    run = Run(
        id="shoe_notes_run_1",
        datetime_utc=datetime(2025, 1, 1, 10, 0, 0),
        type="Outdoor Run",
        distance=5.0,
        duration=2400.0,
        source="Strava",
        avg_heart_rate=150.0,
    )
    run._shoe_name = shoe_name
    assert bulk_create_runs([run]) == 1

    shoe_id = generate_shoe_id(shoe_name)

    # No notes yet.
    res = viewer_client.get(f"/shoes/{shoe_id}/notes")
    assert res.status_code == 200
    assert res.json() == []

    # Create a backdated note (the backfill use case).
    res = editor_client.post(
        f"/shoes/{shoe_id}/notes",
        json={"content": "Bought these in **March 2024**", "note_date": "2024-03-15"},
    )
    assert res.status_code == 201
    older = res.json()
    assert older["note_date"] == "2024-03-15"
    assert older["shoe_id"] == shoe_id

    # Create a newer note (defaults to today).
    res = editor_client.post(
        f"/shoes/{shoe_id}/notes",
        json={"content": "Still going strong"},
    )
    assert res.status_code == 201
    newer = res.json()

    # List is newest-first.
    res = viewer_client.get(f"/shoes/{shoe_id}/notes")
    assert res.status_code == 200
    notes = res.json()
    assert len(notes) == 2
    assert notes[0]["id"] == newer["id"]
    assert notes[1]["id"] == older["id"]

    # Update the older note's content.
    res = editor_client.patch(
        f"/shoes/{shoe_id}/notes/{older['id']}",
        json={"content": "Bought these in spring 2024"},
    )
    assert res.status_code == 200
    assert res.json()["content"] == "Bought these in spring 2024"

    # Soft-delete the newer note.
    res = editor_client.delete(f"/shoes/{shoe_id}/notes/{newer['id']}")
    assert res.status_code == 200

    # Only the older note remains.
    res = viewer_client.get(f"/shoes/{shoe_id}/notes")
    assert [n["id"] for n in res.json()] == [older["id"]]


@pytest.mark.e2e
def test_shoe_notes_auth_and_validation(client, editor_client):
    """Writes require an editor token; notes require an existing shoe."""
    # Unauthenticated create is rejected before any shoe lookup.
    res = client.post("/shoes/whatever/notes", json={"content": "hi"})
    assert res.status_code == 401

    # A note on a nonexistent shoe → 404.
    res = editor_client.post(
        "/shoes/nonexistent_shoe_xyz/notes", json={"content": "hi"}
    )
    assert res.status_code == 404
