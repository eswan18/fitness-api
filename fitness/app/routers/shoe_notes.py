"""CRUD routes for shoe notes — dated markdown log entries on a shoe."""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from fitness.app.auth import require_viewer, require_editor
from fitness.models.shoe_note import ShoeNote
from fitness.models.user import User
from fitness.db.shoes import get_shoe_by_id
from fitness.db.shoe_notes import (
    create_shoe_note,
    get_shoe_notes,
    get_shoe_note_by_id,
    update_shoe_note,
    delete_shoe_note,
)

logger = logging.getLogger(__name__)

# Shares the /shoes prefix with the shoes router; these routes all live under
# /shoes/{shoe_id}/notes so they never collide with the single-segment shoe routes.
router = APIRouter(prefix="/shoes", tags=["shoe-notes"])


# --- Request Models ---


class CreateShoeNoteRequest(BaseModel):
    content: str
    # Defaults to today (server-side) when omitted; can be backdated for old notes.
    note_date: Optional[date] = None


class UpdateShoeNoteRequest(BaseModel):
    content: Optional[str] = None
    note_date: Optional[date] = None


# --- Endpoints ---


@router.get("/{shoe_id}/notes", response_model=list[ShoeNote])
def list_shoe_notes(
    shoe_id: str,
    _user: User = Depends(require_viewer),
) -> list[ShoeNote]:
    """List a shoe's dated notes, newest first."""
    if get_shoe_by_id(shoe_id) is None:
        raise HTTPException(status_code=404, detail=f"Shoe '{shoe_id}' not found")
    return get_shoe_notes(shoe_id)


@router.post("/{shoe_id}/notes", status_code=201, response_model=ShoeNote)
def create_note(
    shoe_id: str,
    request: CreateShoeNoteRequest,
    _user: User = Depends(require_editor),
) -> ShoeNote:
    """Add a dated note to a shoe. ``note_date`` defaults to today when omitted."""
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Note content cannot be empty")

    note_date = request.note_date or date.today()
    try:
        return create_shoe_note(shoe_id, note_date=note_date, content=content)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{shoe_id}/notes/{note_id}", response_model=ShoeNote)
def patch_note(
    shoe_id: str,
    note_id: str,
    request: UpdateShoeNoteRequest,
    _user: User = Depends(require_editor),
) -> ShoeNote:
    """Update a note's content and/or date."""
    if request.content is None and request.note_date is None:
        raise HTTPException(status_code=400, detail="No fields to update")

    content = request.content
    if content is not None:
        content = content.strip()
        if not content:
            raise HTTPException(status_code=400, detail="Note content cannot be empty")

    # Ensure the note exists and belongs to this shoe before updating.
    existing = get_shoe_note_by_id(note_id)
    if existing is None or existing.shoe_id != shoe_id:
        raise HTTPException(status_code=404, detail=f"Note '{note_id}' not found")

    note = update_shoe_note(note_id, note_date=request.note_date, content=content)
    if note is None:
        raise HTTPException(status_code=404, detail=f"Note '{note_id}' not found")
    return note


@router.delete("/{shoe_id}/notes/{note_id}", response_model=dict[str, str])
def remove_note(
    shoe_id: str,
    note_id: str,
    _user: User = Depends(require_editor),
) -> dict[str, str]:
    """Soft-delete a shoe note."""
    existing = get_shoe_note_by_id(note_id)
    if existing is None or existing.shoe_id != shoe_id:
        raise HTTPException(status_code=404, detail=f"Note '{note_id}' not found")
    delete_shoe_note(note_id)
    return {"message": f"Note {note_id} deleted"}
