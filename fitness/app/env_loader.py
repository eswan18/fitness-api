"""Load environment variables early for the FastAPI app.

For local dev, loads a .env file based on ENV ("dev" or "prod").
In K8s (ENV="staging" or "prod"), env vars are injected via configmaps
and secrets, so no .env file is loaded.
"""

import os
import sys
from typing import Literal
from dotenv import load_dotenv

EnvironmentName = Literal["dev", "staging", "prod"]

# Required environment variables that must be set for the app to run.
# If any are missing, the app will fail to start with a clear error message.
REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "PUBLIC_API_BASE_URL",
    "IDENTITY_PROVIDER_URL",
    "JWT_AUDIENCE",
    "TRMNL_API_KEY",
]


def validate_required_env_vars() -> None:
    """Validate that all required environment variables are set.

    Raises:
        SystemExit: If any required environment variables are missing.
    """
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        print(
            f"ERROR: Missing required environment variables: {', '.join(missing)}",
            file=sys.stderr,
        )
        print(
            "Please set these variables in your .env file or environment.",
            file=sys.stderr,
        )
        sys.exit(1)


# Load env vars before any app code runs.
# In K8s (staging/prod), env vars are injected via configmaps and secrets.
# For local dev, load from a .env file.
env = os.getenv("ENV", "dev")
if env in ("staging", "prod"):
    print(f"Running in {env} environment (env vars from configmaps/secrets)")
elif env == "dev":
    print("Loading environment variables from .env.dev")
    load_dotenv(".env.dev", verbose=True)
else:
    raise ValueError(f"Invalid ENV value: {env}. Must be 'dev', 'staging', or 'prod'.")

# Validate required env vars after loading.
validate_required_env_vars()


def get_current_environment() -> EnvironmentName:
    """Get the current environment (dev, staging, or prod)."""
    env = os.getenv("ENV", "dev")
    if env in ("dev", "staging", "prod"):
        return env  # type: ignore[return-value]
    raise ValueError(f"Invalid ENV value: {env}. Must be 'dev', 'staging', or 'prod'.")
