"""Shoe management routes."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict

from fitness.db.shoes import (
    get_shoes,
    get_shoe_by_id,
    retire_shoe_by_id,
    unretire_shoe_by_id,
    merge_shoes,
)
from fitness.models.shoe import Shoe
from fitness.models.user import User
from fitness.app.models import UpdateShoeRequest, MergeShoesRequest
from fitness.app.auth import require_viewer, require_editor

router = APIRouter(prefix="/shoes", tags=["shoes"])


@router.get("/", response_model=List[Shoe])
def read_shoes(
    retired: bool | None = None,
    _user: User = Depends(require_viewer),
) -> list[Shoe]:
    """Get shoes, optionally filtered by retirement status.

    Args:
        retired: If True, return only retired shoes. If False, return only active shoes.
                If None, return all shoes.
    """
    return get_shoes(retired=retired)


@router.patch("/{shoe_id}", response_model=Dict[str, str])
def update_shoe(
    shoe_id: str,
    request: UpdateShoeRequest,
    user: User = Depends(require_editor),
) -> dict:
    """Update shoe properties.

    Requires OAuth 2.0 Bearer token authentication.

    Use `retired_at=null` to unretire, or provide a date to retire.

    Args:
        shoe_id: Deterministic shoe identifier derived from name.
        request: Partial update payload for retirement/unretirement.
    """
    # First check if shoe exists
    shoe = get_shoe_by_id(shoe_id)
    if not shoe:
        raise HTTPException(
            status_code=404, detail=f"Shoe with ID '{shoe_id}' not found"
        )

    if request.retired_at is None:
        # Unretire the shoe
        unretire_shoe_by_id(shoe_id)
        return {"message": f"Shoe '{shoe.name}' has been unretired"}
    else:
        # Retire the shoe
        success = retire_shoe_by_id(
            shoe_id=shoe_id,
            retired_at=request.retired_at,
            retirement_notes=request.retirement_notes,
        )
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Shoe with ID '{shoe_id}' not found"
            )
        return {"message": f"Shoe '{shoe.name}' has been retired"}


@router.post("/merge", response_model=Dict[str, str])
def merge_shoes_endpoint(
    request: MergeShoesRequest,
    user: User = Depends(require_editor),
) -> dict:
    """Merge two shoes into one.

    Re-points all runs from merge_shoe to keep_shoe, creates a name alias
    so future imports resolve to keep_shoe, and soft-deletes merge_shoe.
    """
    if request.keep_shoe_id == request.merge_shoe_id:
        raise HTTPException(status_code=400, detail="Cannot merge a shoe with itself")

    keep_shoe = get_shoe_by_id(request.keep_shoe_id)
    if not keep_shoe:
        raise HTTPException(
            status_code=404,
            detail=f"Shoe '{request.keep_shoe_id}' not found",
        )

    merge_shoe = get_shoe_by_id(request.merge_shoe_id)
    if not merge_shoe:
        raise HTTPException(
            status_code=404,
            detail=f"Shoe '{request.merge_shoe_id}' not found",
        )

    merge_shoes(
        keep_shoe_id=keep_shoe.id,
        merge_shoe_id=merge_shoe.id,
        merge_shoe_name=merge_shoe.name,
    )

    return {"message": f"Merged '{merge_shoe.name}' into '{keep_shoe.name}'"}
