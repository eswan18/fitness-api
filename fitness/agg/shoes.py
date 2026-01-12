from fitness.models import Run
from fitness.models.shoe import Shoe, ShoeMileage


def mileage_by_shoes(
    runs: list[Run],
    shoes: list[Shoe],
    include_retired: bool = False,
) -> list[ShoeMileage]:
    """
    Calculate the total mileage for each pair of shoes used in the runs.

    Args:
        runs: List of runs to calculate mileage from
        shoes: List of all shoes to check retirement status against
        include_retired: Whether to include retired shoes in the calculation

    Returns:
        List of ShoeMileage objects containing shoe and mileage data
    """
    # Create lookup dict for shoes by ID
    shoe_id_lookup = {shoe.id: shoe for shoe in shoes}

    # Track mileage by shoe ID
    mileage_by_id: dict[str, float] = {}

    for run in runs:
        if run.shoe_id is None:
            continue

        shoe = shoe_id_lookup.get(run.shoe_id)
        if not shoe:
            continue

        # Skip retired shoes if not including them
        if not include_retired and shoe.is_retired:
            continue

        mileage_by_id[run.shoe_id] = mileage_by_id.get(run.shoe_id, 0.0) + run.distance

    # Convert to list of ShoeMileage objects
    results = [
        ShoeMileage(shoe=shoe_id_lookup[shoe_id], mileage=mileage)
        for shoe_id, mileage in mileage_by_id.items()
    ]

    # Sort by shoe name for consistent ordering
    results.sort(key=lambda x: x.shoe.name)

    return results
