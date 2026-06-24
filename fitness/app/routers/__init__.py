from .metrics import router as metrics_router
from .shoes import router as shoe_router
from .shoe_notes import router as shoe_notes_router
from .ride import router as ride_router
from .ride_sync import router as ride_sync_router
from .run import router as run_router
from .sync import router as sync_router
from .oauth import router as oauth_router
from .strava import router as strava_router
from .mmf import router as mmf_router
from .summary import router as summary_router
from .hevy import router as hevy_router
from .lifts import router as lifts_router
from .exercise_templates import router as exercise_templates_router
from .lift_sync import router as lift_sync_router
from .run_workouts import router as run_workouts_router
from .run_workout_sync import router as run_workout_sync_router
from .ingest import router as ingest_router
from .duplicates import router as duplicates_router

__all__ = [
    "metrics_router",
    "shoe_router",
    "shoe_notes_router",
    "oauth_router",
    "ride_router",
    "ride_sync_router",
    "run_router",
    "sync_router",
    "strava_router",
    "mmf_router",
    "summary_router",
    "hevy_router",
    "lifts_router",
    "exercise_templates_router",
    "lift_sync_router",
    "run_workouts_router",
    "run_workout_sync_router",
    "ingest_router",
    "duplicates_router",
]
