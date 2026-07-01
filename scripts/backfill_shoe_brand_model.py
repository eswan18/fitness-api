"""One-off: backfill shoes.brand / shoes.model from the legacy `name`.

Splits each shoe's ``name`` into a known brand prefix + model, mirroring the
dashboard's allowlist logic (fitness-dashboard/src/lib/shoeName.ts). Shoes whose
name has no recognized brand prefix (unlisted brands, or brand-less names like
"Ghost 16") are printed for MANUAL cleanup and left untouched — you must fill
those in before the migration that makes brand/model NOT NULL.

Usage (dry-run by default; requires DATABASE_URL):
    uv run python scripts/backfill_shoe_brand_model.py           # preview only
    uv run python scripts/backfill_shoe_brand_model.py --apply   # write changes
"""

import argparse

from fitness.db.connection import get_db_connection

# Kept in sync with fitness-dashboard/src/lib/shoeName.ts. Longest-first so
# multi-word brands ("Hoka One One", "New Balance") match before their prefixes.
SHOE_BRANDS = sorted(
    [
        "Nike",
        "Adidas",
        "Brooks",
        "Hoka",
        "Hoka One One",
        "Asics",
        "Saucony",
        "New Balance",
        "Under Armour",
        "Mizuno",
        "Karhu",
        "On",
        "On Running",
        "Puma",
        "Altra",
        "Reebok",
        "Topo",
        "Topo Athletic",
        "Salomon",
        "Merrell",
        "La Sportiva",
        "Inov-8",
        "Inov8",
        "Newton",
        "Skechers",
        "Fila",
        "Diadora",
    ],
    key=len,
    reverse=True,
)


def split_name(name: str) -> tuple[str, str] | None:
    """Return (brand, model) if a known brand prefix is found, else None.

    Brand match is case-insensitive and must be followed by whitespace; the
    returned brand uses the canonical casing from SHOE_BRANDS.
    """
    trimmed = name.strip()
    for brand in SHOE_BRANDS:
        if len(trimmed) <= len(brand):
            continue
        if trimmed[: len(brand)].lower() == brand.lower() and trimmed[len(brand)].isspace():
            model = trimmed[len(brand) :].lstrip()
            if model:
                return brand, model
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="write changes (default: dry-run)"
    )
    args = parser.parse_args()

    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT id, name FROM shoes WHERE brand IS NULL ORDER BY name"
        ).fetchall()

        matched: list[tuple[str, str, str]] = []  # (id, brand, model)
        unmatched: list[tuple[str, str]] = []  # (id, name)
        for shoe_id, name in rows:
            split = split_name(name)
            if split:
                matched.append((shoe_id, split[0], split[1]))
            else:
                unmatched.append((shoe_id, name))

        print(f"{len(rows)} shoe(s) with NULL brand.")
        print(f"  {len(matched)} can be split by a known brand prefix.")
        for _id, brand, model in matched:
            print(f"    [{brand}] + [{model}]   (id={_id})")

        if unmatched:
            print(f"\n  {len(unmatched)} need MANUAL cleanup (no known brand prefix):")
            for _id, name in unmatched:
                print(f"    {name!r}   (id={_id})")

        if not args.apply:
            print("\nDry run — no changes written. Re-run with --apply to persist.")
            return

        if matched:
            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE shoes SET brand = %s, model = %s, "
                    "updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    [(brand, model, _id) for _id, brand, model in matched],
                )
            conn.commit()
        print(f"\nApplied: set brand/model on {len(matched)} shoe(s).")
        if unmatched:
            print(f"{len(unmatched)} still need manual brand/model before the NOT NULL migration.")


if __name__ == "__main__":
    main()
