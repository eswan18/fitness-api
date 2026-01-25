"""Shared shoe configuration for normalizing shoe names across data sources."""

# Mapping of raw shoe names to normalized names.
# Used by both Strava and MMF data loaders to ensure consistent shoe naming.
SHOE_RENAME_MAP: dict[str, str] = {
    # Adidas
    "Adizero SL": "Adidas Adizero SL",
    "Adidas Boston 13": "Boston 13",
    # Brooks
    "Ghost 15": "Brooks Ghost 15",
    "Ghost 16": "Brooks Ghost 16",
    # Karhu (normalize spacing variations)
    "Karhu Fusion 2021  2": "Karhu Fusion 2021 - 2",
    "Karhu Fusion 2021 2": "Karhu Fusion 2021 - 2",
    # New Balance (normalize model number formats)
    "M1080K10": "New Balance M1080K10",
    "M1080R10": "New Balance M1080R10",
    "New Balance 1080K10": "New Balance M1080K10",
    # Nike
    "Pegasus 38": "Nike Air Zoom Pegasus 38",
}


def normalize_shoe_name(name: str | None) -> str | None:
    """Normalize a shoe name using the rename map.

    Args:
        name: Raw shoe name from data source

    Returns:
        Normalized shoe name, or original name if no mapping exists,
        or None if input is None
    """
    if name is None:
        return None
    return SHOE_RENAME_MAP.get(name, name)
