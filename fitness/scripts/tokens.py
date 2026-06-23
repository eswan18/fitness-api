"""CLI to mint, list, and revoke per-service API tokens (``fitapi-token``).

The raw token is shown exactly once, at creation. Only its SHA-256 hash is
stored, so it cannot be recovered later — mint a new one if it's lost.

Usage:
    uv run fitapi-token mint --name health-auto-export [--expires 2027-01-01]
    uv run fitapi-token list [--all]
    uv run fitapi-token revoke --prefix fitapi_AbC123
    uv run fitapi-token revoke --id 4
"""

import argparse
import sys
from datetime import datetime

from fitness.config.env_files import load_dotenv_for_current_env
from fitness.auth.tokens import generate_token, hash_token, token_prefix
from fitness.db.api_tokens import (
    create_api_token,
    list_api_tokens,
    revoke_api_token,
)


def _load_env() -> None:
    """Load ``.env.{ENV}`` the same way the app does (``ENV=prod`` -> ``.env.prod``).

    Uses the app's shared loader, but unlike the app's ``env_loader`` we do not
    require the full app environment — only ``DATABASE_URL``, which the DB layer
    reads when a command runs.
    """
    load_dotenv_for_current_env()


def _cmd_mint(args: argparse.Namespace) -> int:
    expires_at: datetime | None = None
    if args.expires:
        expires_at = datetime.fromisoformat(args.expires)

    raw = generate_token()
    token = create_api_token(
        name=args.name,
        token_hash=hash_token(raw),
        prefix=token_prefix(raw),
        expires_at=expires_at,
    )
    print(f"Token minted for '{token.name}' (id={token.id}, prefix={token.prefix}).")
    print("Raw token (shown once — store it now, it cannot be recovered):")
    print()
    print(f"    {raw}")
    print()
    print("Use it as the request header:")
    print(f"    Authorization: Bearer {raw}")
    return 0


def _cmd_revoke(args: argparse.Namespace) -> int:
    if args.id is not None:
        revoked = revoke_api_token(token_id=args.id)
        target = f"id={args.id}"
    else:
        revoked = revoke_api_token(prefix=args.prefix)
        target = f"prefix={args.prefix}"
    if revoked:
        print(f"Revoked token ({target}).")
        return 0
    print(f"No active token found for {target}.", file=sys.stderr)
    return 1


def _cmd_list(args: argparse.Namespace) -> int:
    rows = list_api_tokens(include_revoked=args.all)
    if not rows:
        print("No tokens.")
        return 0
    header = f"{'id':>4}  {'name':<24}  {'prefix':<16}  {'created':<19}  {'expires':<19}  {'last_used':<19}  {'revoked':<19}"
    print(header)
    print("-" * len(header))
    for t in rows:
        print(
            f"{t.id:>4}  {t.name:<24}  {t.prefix:<16}  "
            f"{_fmt(t.created_at):<19}  {_fmt(t.expires_at):<19}  "
            f"{_fmt(t.last_used_at):<19}  {_fmt(t.revoked_at):<19}"
        )
    return 0


def _fmt(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else "-"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fitapi-token")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_mint = sub.add_parser("mint", help="create a new token")
    p_mint.add_argument("--name", required=True, help="human label for the token")
    p_mint.add_argument(
        "--expires", help="optional ISO date/datetime when the token expires"
    )
    p_mint.set_defaults(func=_cmd_mint)

    p_revoke = sub.add_parser("revoke", help="revoke a token")
    group = p_revoke.add_mutually_exclusive_group(required=True)
    group.add_argument("--id", type=int, help="token id")
    group.add_argument("--prefix", help="token prefix (e.g. fitapi_AbC123)")
    p_revoke.set_defaults(func=_cmd_revoke)

    p_list = sub.add_parser("list", help="list tokens")
    p_list.add_argument("--all", action="store_true", help="include revoked tokens")
    p_list.set_defaults(func=_cmd_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    _load_env()
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
