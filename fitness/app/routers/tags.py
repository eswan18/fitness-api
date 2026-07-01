"""CRUD routes for tags — freeform labels assignable to runs and rides."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from fitness.app.auth import require_viewer, require_editor
from fitness.models.tag import Tag
from fitness.models.user import User
from fitness.db.tags import (
    create_tag,
    get_all_tags,
    get_tag_by_id,
    update_tag_name,
    delete_tag,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tags", tags=["tags"])


# --- Request Models ---


class CreateTagRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class UpdateTagRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


# --- Endpoints ---


@router.get("", response_model=list[Tag])
def list_tags(
    _user: User = Depends(require_viewer),
) -> list[Tag]:
    """List all live tags, ordered by name."""
    return get_all_tags()


@router.post("", status_code=201, response_model=Tag)
def create_new_tag(
    request: CreateTagRequest,
    _user: User = Depends(require_editor),
) -> Tag:
    """Create a tag, or return the existing live tag with the same name.

    Idempotent (case-insensitive against live tags): returning an existing
    tag is still a 201, not a 409, to keep the client-side flow simple.
    """
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tag name cannot be empty")
    return create_tag(name)


@router.patch("/{tag_id}", response_model=Tag)
def rename_tag(
    tag_id: str,
    request: UpdateTagRequest,
    _user: User = Depends(require_editor),
) -> Tag:
    """Rename a tag."""
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tag name cannot be empty")

    if get_tag_by_id(tag_id) is None:
        raise HTTPException(status_code=404, detail=f"Tag '{tag_id}' not found")

    try:
        tag = update_tag_name(tag_id, name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if tag is None:
        raise HTTPException(status_code=404, detail=f"Tag '{tag_id}' not found")
    return tag


@router.delete("/{tag_id}", response_model=dict[str, str])
def remove_tag(
    tag_id: str,
    _user: User = Depends(require_editor),
) -> dict[str, str]:
    """Soft-delete a tag and unassign it from any runs/rides."""
    if get_tag_by_id(tag_id) is None:
        raise HTTPException(status_code=404, detail=f"Tag '{tag_id}' not found")
    delete_tag(tag_id)
    return {"message": f"Tag {tag_id} deleted"}
