"""OAuth authentication and role-based authorization."""

from .oauth import (
    verify_oauth_token,
    get_current_user,
    require_viewer,
    require_editor,
    require_viewer_or_api_key,
)

# Export for use in routers
__all__ = [
    "verify_oauth_token",
    "get_current_user",
    "require_viewer",
    "require_editor",
    "require_viewer_or_api_key",
]
