"""End-to-end tests for the api_tokens DB layer against real Postgres."""

from datetime import datetime, timedelta, timezone

import pytest

from fitness.auth.tokens import generate_token, hash_token, token_prefix
from fitness.db.api_tokens import (
    ApiToken,
    create_api_token,
    get_active_token_by_hash,
    list_api_tokens,
    revoke_api_token,
    touch_last_used,
)


def _mint(name: str, expires_at: datetime | None = None) -> tuple[str, ApiToken]:
    """Create a token row; return (raw_token, ApiToken)."""
    raw = generate_token()
    row = create_api_token(
        name=name,
        token_hash=hash_token(raw),
        prefix=token_prefix(raw),
        expires_at=expires_at,
    )
    return raw, row


@pytest.mark.e2e
def test_create_and_lookup_active_token(db_url: str):
    raw, created = _mint("lookup-test")
    assert created.id is not None
    assert created.name == "lookup-test"
    assert created.prefix == token_prefix(raw)
    assert created.revoked_at is None

    found = get_active_token_by_hash(hash_token(raw))
    assert found is not None
    assert found.id == created.id
    assert found.name == "lookup-test"


@pytest.mark.e2e
def test_unknown_hash_returns_none(db_url: str):
    assert get_active_token_by_hash(hash_token("fitapi_does-not-exist")) is None


@pytest.mark.e2e
def test_revoked_token_is_not_active(db_url: str):
    raw, created = _mint("revoke-test")
    assert revoke_api_token(token_id=created.id) is True
    assert get_active_token_by_hash(hash_token(raw)) is None
    # revoking again affects no rows
    assert revoke_api_token(token_id=created.id) is False


@pytest.mark.e2e
def test_revoke_by_prefix(db_url: str):
    raw, created = _mint("revoke-by-prefix")
    assert revoke_api_token(prefix=created.prefix) is True
    assert get_active_token_by_hash(hash_token(raw)) is None


@pytest.mark.e2e
def test_expired_token_is_not_active(db_url: str):
    past = datetime.now(timezone.utc) - timedelta(days=1)
    raw, _ = _mint("expired-test", expires_at=past)
    assert get_active_token_by_hash(hash_token(raw)) is None


@pytest.mark.e2e
def test_future_expiry_token_is_active(db_url: str):
    future = datetime.now(timezone.utc) + timedelta(days=30)
    raw, _ = _mint("future-expiry", expires_at=future)
    assert get_active_token_by_hash(hash_token(raw)) is not None


@pytest.mark.e2e
def test_touch_last_used_sets_timestamp(db_url: str):
    raw, created = _mint("touch-test")
    assert created.last_used_at is None
    touch_last_used(created.id)
    refreshed = get_active_token_by_hash(hash_token(raw))
    assert refreshed is not None
    assert refreshed.last_used_at is not None


@pytest.mark.e2e
def test_list_excludes_revoked_by_default(db_url: str):
    _, active = _mint("list-active")
    _, revoked = _mint("list-revoked")
    revoke_api_token(token_id=revoked.id)

    default_ids = {t.id for t in list_api_tokens()}
    assert active.id in default_ids
    assert revoked.id not in default_ids

    all_ids = {t.id for t in list_api_tokens(include_revoked=True)}
    assert revoked.id in all_ids
