"""Generic router for exercise template data."""

import logging

from fastapi import APIRouter, Depends

from fitness.app.auth import require_viewer
from fitness.models.user import User
from fitness.models.lift import ExerciseTemplate
from fitness.db.lifts import get_all_exercise_templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/exercise-templates", tags=["exercise-templates"])


# --- Endpoints ---


@router.get("", response_model=list[ExerciseTemplate])
async def get_exercise_templates(
    _user: User = Depends(require_viewer),
) -> list[ExerciseTemplate]:
    """Get all cached exercise templates (for muscle group mapping)."""
    return get_all_exercise_templates()
