"""Shoe management routes."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict

from fitness.db.shoes import (
    get_shoes,
    get_shoe_by_id,
    retire_shoe_by_id,
    unretire_shoe_by_id,
)
from fitness.models.shoe import Shoe
from fitness.models.user import User
from fitness.app.models import UpdateShoeRequest
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
