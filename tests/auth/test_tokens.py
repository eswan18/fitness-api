import re

from fitness.auth.tokens import (
    TOKEN_PREFIX,
    generate_token,
    hash_token,
    token_prefix,
)


def test_generate_token_has_prefix_and_entropy():
    token = generate_token()
    assert token.startswith(TOKEN_PREFIX)
    # token_urlsafe(32) -> 43 url-safe base64 chars after the prefix
    body = token[len(TOKEN_PREFIX) :]
    assert len(body) >= 43
    assert re.fullmatch(r"[A-Za-z0-9_-]+", body)


def test_generate_token_is_unique():
    assert generate_token() != generate_token()


def test_hash_token_is_deterministic_sha256_hex():
    token = "fitapi_abc123"
    digest = hash_token(token)
    # sha256 hex digest is 64 lowercase hex chars
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert hash_token(token) == digest  # deterministic


def test_hash_token_differs_per_token():
    assert hash_token("fitapi_aaa") != hash_token("fitapi_bbb")


def test_token_prefix_is_identifying_slice():
    token = "fitapi_AbCdEfGhIjKlMnOp"
    prefix = token_prefix(token)
    assert token.startswith(prefix)
    assert prefix.startswith(TOKEN_PREFIX)
    # short enough to be non-secret, long enough to identify
    assert 8 <= len(prefix) <= 20
