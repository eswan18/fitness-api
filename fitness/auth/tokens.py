"""Helpers for the per-service API token system used by ingestion endpoints.

These tokens are independent of the human OAuth/JWT auth: a leaked credential
can be revoked in isolation and attributed to its source.

A token looks like ``fitapi_<token_urlsafe(32)>``. Only a SHA-256 hash of the
token is ever stored, so a database leak does not expose live credentials.

Why plain SHA-256 (not bcrypt/argon2)? The token already carries 256 bits of
CSPRNG entropy from ``secrets.token_urlsafe(32)``, so an attacker who steals the
hash cannot brute-force it regardless of hash speed. A fast, deterministic digest
also lets us look a token up with a single indexed ``WHERE token_hash = %s`` —
a per-row salt would force a full-table scan plus a verify on every request.
"""

import hashlib
import secrets

TOKEN_PREFIX = "fitapi_"

# Number of leading characters of the raw token kept for identification (e.g. in
# `list`/`revoke`). This is not a secret — it never reveals the token body.
PREFIX_DISPLAY_LEN = 14


def generate_token() -> str:
    """Generate a new raw API token. Shown to the user exactly once."""
    return f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def hash_token(raw: str) -> str:
    """Return the SHA-256 hex digest of a raw token (what we persist/look up)."""
    return hashlib.sha256(raw.encode()).hexdigest()


def token_prefix(raw: str) -> str:
    """Return the non-secret identifying prefix of a raw token."""
    return raw[:PREFIX_DISPLAY_LEN]
