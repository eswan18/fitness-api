"""Load the ``.env.{ENV}`` file for the current environment.

This module is deliberately side-effect free: importing it does not load or
validate anything. That lets it be shared by the app's bootstrap
(``env_loader``, which additionally validates the full app environment) and by
standalone CLI scripts that only need ``DATABASE_URL`` — not the whole app env.
"""

import os

from dotenv import load_dotenv

VALID_ENVIRONMENTS = ("dev", "staging", "prod")


def load_dotenv_for_current_env() -> str:
    """Load ``.env.{ENV}`` (e.g. ``.env.prod`` when ``ENV=prod``).

    Returns the resolved environment name. Loading a missing file is a no-op
    (in K8s the vars come from configmaps/secrets), and pre-existing process
    env vars win over the file (``load_dotenv`` default ``override=False``).
    """
    env = os.getenv("ENV", "dev")
    if env not in VALID_ENVIRONMENTS:
        raise ValueError(
            f"Invalid ENV value: {env}. Must be one of {VALID_ENVIRONMENTS}."
        )
    load_dotenv(f".env.{env}", verbose=True)
    return env
