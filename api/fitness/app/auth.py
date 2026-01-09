"""OAuth-only authentication."""

from .oauth import verify_oauth_token

# Export for use in routers
__all__ = ["verify_oauth_token"]
