"""OAuth authentication and role-based authorization."""

from .oauth import (
    verify_oauth_token,
    get_current_user,
    require_viewer,
    require_editor,
)

# Export for use in routers
__all__ = [
    "verify_oauth_token",
    "get_current_user",
    "require_viewer",
    "require_editor",
]
