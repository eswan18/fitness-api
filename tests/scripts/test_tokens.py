from datetime import datetime

from fitness.auth.tokens import hash_token
from fitness.db.api_tokens import ApiToken
from fitness.scripts import tokens


def test_mint_prints_raw_token_once_and_stores_hash(capsys, monkeypatch):
    monkeypatch.setattr(tokens, "generate_token", lambda: "fitapi_RAWTOKENVALUE")
    captured = {}

    def fake_create(name, token_hash, prefix, expires_at):
        captured.update(
            name=name, token_hash=token_hash, prefix=prefix, expires_at=expires_at
        )
        return ApiToken(id=7, name=name, prefix=prefix, created_at=datetime(2026, 6, 1))

    monkeypatch.setattr(tokens, "create_api_token", fake_create)

    rc = tokens.main(["mint", "--name", "health-auto-export"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "fitapi_RAWTOKENVALUE" in out  # raw token shown once
    assert "health-auto-export" in out
    # the hash (not the raw token) is what gets persisted
    assert captured["token_hash"] == hash_token("fitapi_RAWTOKENVALUE")
    assert captured["name"] == "health-auto-export"
    assert captured["expires_at"] is None


def test_revoke_by_prefix_reports_success(capsys, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        tokens, "revoke_api_token", lambda **kw: seen.update(kw) or True
    )
    rc = tokens.main(["revoke", "--prefix", "fitapi_abc123"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "revoked" in out.lower()
    assert seen == {"prefix": "fitapi_abc123"}


def test_revoke_no_match_returns_nonzero(capsys, monkeypatch):
    monkeypatch.setattr(tokens, "revoke_api_token", lambda **kw: False)
    rc = tokens.main(["revoke", "--id", "999"])
    assert rc != 0


def test_list_outputs_tokens(capsys, monkeypatch):
    monkeypatch.setattr(
        tokens,
        "list_api_tokens",
        lambda include_revoked=False: [
            ApiToken(
                id=1, name="hae", prefix="fitapi_x", created_at=datetime(2026, 6, 1)
            )
        ],
    )
    rc = tokens.main(["list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "hae" in out
    assert "fitapi_x" in out
