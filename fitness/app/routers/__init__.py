from .metrics import router as metrics_router
from .shoes import router as shoe_router
from .run import router as run_router
from .sync import router as sync_router
from .oauth import router as oauth_router
from .strava import router as strava_router
from .mmf import router as mmf_router
from .summary import router as summary_router

__all__ = [
    "metrics_router",
    "shoe_router",
    "oauth_router",
    "run_router",
    "sync_router",
    "strava_router",
    "mmf_router",
    "summary_router",
]
