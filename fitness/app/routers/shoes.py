"""Shoe management routes."""

from fastapi import APIRouter, HTTPException, Depends

from fitness.db.shoes import (
    get_shoes,
    get_shoes_with_last_used,
    get_shoe_by_id,
    create_shoe,
    update_shoe,
    retire_shoe_by_id,
    unretire_shoe_by_id,
    merge_shoes,
    delete_shoe_by_id,
)
from fitness.models.shoe import Shoe, ShoeRecentUse
from fitness.models.user import User
from fitness.app.models import CreateShoeRequest, UpdateShoeRequest, MergeShoesRequest
from fitness.app.auth import require_viewer, require_editor

router = APIRouter(prefix="/shoes", tags=["shoes"])


@router.get("/", response_model=list[Shoe])
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


@router.get("/recent", response_model=list[ShoeRecentUse])
def read_recent_shoes(
    include_retired: bool = False,
    _user: User = Depends(require_viewer),
) -> list[ShoeRecentUse]:
    """Get shoes ordered by most-recently-used.

    Returns all non-deleted shoes paired with the datetime of their most
    recent run, sorted by last_used_date DESC NULLS LAST. Retired shoes are
    excluded unless ``include_retired=true``.
    """
    return get_shoes_with_last_used(include_retired=include_retired)


@router.post("/", response_model=Shoe, status_code=201)
def create_shoe_endpoint(
    request: CreateShoeRequest,
    user: User = Depends(require_editor),
) -> Shoe:
    """Create a new shoe.

    Requires OAuth 2.0 Bearer token authentication with editor role. ``brand``,
    ``model``, ``size`` and ``purchased_date`` are required; ``color`` is
    optional. The id is opaque and duplicate brand/model/color pairs are allowed
    (e.g. a repurchased pair). Mileage thresholds default to 300 (warning) / 500
    (maximum) if omitted (validated so maximum > warning).
    """
    return create_shoe(
        brand=request.brand,
        model=request.model,
        color=request.color,
        size=request.size,
        purchased_date=request.purchased_date,
        warning_mileage=request.warning_mileage,
        maximum_mileage=request.maximum_mileage,
        notes=request.notes,
    )


@router.patch("/{shoe_id}", response_model=dict[str, str])
def update_shoe_endpoint(
    shoe_id: str,
    request: UpdateShoeRequest,
    user: User = Depends(require_editor),
) -> dict:
    """Update shoe properties.

    Requires OAuth 2.0 Bearer token authentication with editor role.

    All fields are optional and only fields explicitly present in the request
    body are changed (so a brand/mileage-only edit leaves retirement untouched).
    Specifically:

    - ``brand`` / ``model`` / ``color``: edit the shoe's identity. The id stays
      stable; the displayed ``name`` is composed from ``"{brand} {model}"``.
    - ``warning_mileage`` / ``maximum_mileage``: edit the thresholds (validated so
      maximum > warning).
    - ``size`` / ``purchased_date``: edit or backfill these.
    - ``retired_at``: only touched when present — a date retires the shoe, an
      explicit ``null`` unretires it.

    Args:
        shoe_id: Opaque shoe identifier.
        request: Partial update payload.
    """
    shoe = get_shoe_by_id(shoe_id)
    if not shoe:
        raise HTTPException(
            status_code=404, detail=f"Shoe with ID '{shoe_id}' not found"
        )

    sent = request.model_fields_set

    # --- Build the profile update from explicitly-set fields ---
    fields: dict = {}

    # brand / model / color. brand & model can't be nulled; color may be cleared.
    if "brand" in sent and request.brand is not None:
        fields["brand"] = request.brand
    if "model" in sent and request.model is not None:
        fields["model"] = request.model
    if "color" in sent:
        fields["color"] = request.color

    effective_warning = shoe.warning_mileage
    effective_maximum = shoe.maximum_mileage
    if "warning_mileage" in sent and request.warning_mileage is not None:
        fields["warning_mileage"] = request.warning_mileage
        effective_warning = request.warning_mileage
    if "maximum_mileage" in sent and request.maximum_mileage is not None:
        fields["maximum_mileage"] = request.maximum_mileage
        effective_maximum = request.maximum_mileage
    if (
        "warning_mileage" in fields or "maximum_mileage" in fields
    ) and effective_maximum <= effective_warning:
        raise HTTPException(
            status_code=422,
            detail="maximum_mileage must be greater than warning_mileage",
        )

    if "size" in sent and request.size is not None:
        fields["size"] = request.size
    if "purchased_date" in sent and request.purchased_date is not None:
        fields["purchased_date"] = request.purchased_date

    if fields:
        update_shoe(shoe_id, fields)

    # --- Retirement: only touched when retired_at is explicitly present ---
    retire_action: str | None = None
    if "retired_at" in sent:
        if request.retired_at is None:
            unretire_shoe_by_id(shoe_id)
            retire_action = "unretired"
        else:
            retire_shoe_by_id(
                shoe_id=shoe_id,
                retired_at=request.retired_at,
                retirement_notes=request.retirement_notes,
            )
            retire_action = "retired"

    profile_changed = bool(fields)
    # Preserve the exact legacy messages for retirement-only requests.
    if retire_action and not profile_changed:
        return {"message": f"Shoe '{shoe.display_name}' has been {retire_action}"}
    if profile_changed and not retire_action:
        return {"message": f"Shoe '{shoe.display_name}' has been updated"}
    if profile_changed and retire_action:
        return {"message": f"Shoe '{shoe.display_name}' has been updated and {retire_action}"}
    return {"message": f"No changes applied to shoe '{shoe.display_name}'"}


@router.post("/merge", response_model=dict[str, str])
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
        merge_shoe_name=merge_shoe.display_name,
    )

    return {"message": f"Merged '{merge_shoe.display_name}' into '{keep_shoe.display_name}'"}


@router.delete("/{shoe_id}", response_model=dict[str, str])
def delete_shoe(
    shoe_id: str,
    user: User = Depends(require_editor),
) -> dict:
    """Soft-delete a shoe by ID.

    Requires OAuth 2.0 Bearer token authentication with editor role.
    """
    success = delete_shoe_by_id(shoe_id)
    if not success:
        raise HTTPException(
            status_code=404, detail=f"Shoe with ID '{shoe_id}' not found"
        )
    return {"message": f"Shoe {shoe_id} deleted"}
