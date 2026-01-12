from datetime import date

from fitness.agg.shoes import mileage_by_shoes


def test_mileage_by_shoes(run_factory):
    nikes = "Nike Air Zoom Pegasus 37"
    brooks = "Brooks Ghost 14"
    # Create shoes first to get their IDs
    from fitness.models.shoe import Shoe, generate_shoe_id

    brooks_id = generate_shoe_id(brooks)
    nikes_id = generate_shoe_id(nikes)

    shoes = [
        Shoe(id=brooks_id, name=brooks),
        Shoe(id=nikes_id, name=nikes),
    ]

    runs = [
        run_factory.make(update={"distance": 4.0, "shoe_id": brooks_id}),
        run_factory.make(update={"distance": 5.0, "shoe_id": nikes_id}),
        run_factory.make(update={"distance": 2.0, "shoe_id": None}),
        run_factory.make(update={"distance": 2.0, "shoe_id": None}),
        run_factory.make(update={"distance": 3.0, "shoe_id": nikes_id}),
        run_factory.make(update={"distance": 1.0, "shoe_id": brooks_id}),
    ]

    mileage_results = mileage_by_shoes(runs, shoes=shoes)
    mileage_dict = {result.shoe.name: result.mileage for result in mileage_results}
    assert mileage_dict[brooks] == 5.0
    assert mileage_dict[nikes] == 8.0


def test_mileage_by_shoes_exclude_retired(run_factory):
    """Test that retired shoes are excluded by default."""
    nikes = "Nike Air Zoom Pegasus 37"
    brooks = "Brooks Ghost 14"

    # Create mock shoes with nike retired and brooks active
    from fitness.models.shoe import Shoe, generate_shoe_id

    brooks_id = generate_shoe_id(brooks)
    nikes_id = generate_shoe_id(nikes)

    mock_shoes = [
        Shoe(
            id=nikes_id,
            name=nikes,
            retired_at=date(2024, 12, 15),
            retirement_notes="Worn out",
        ),
        Shoe(id=brooks_id, name=brooks),  # Active shoe
    ]

    runs = [
        run_factory.make(update={"distance": 4.0, "shoe_id": brooks_id}),
        run_factory.make(update={"distance": 5.0, "shoe_id": nikes_id}),
        run_factory.make(update={"distance": 3.0, "shoe_id": nikes_id}),
        run_factory.make(update={"distance": 1.0, "shoe_id": brooks_id}),
    ]

    # Test without including retired (default behavior)
    mileage_results = mileage_by_shoes(runs, shoes=mock_shoes, include_retired=False)
    mileage_dict = {result.shoe.name: result.mileage for result in mileage_results}
    assert brooks in mileage_dict
    assert nikes not in mileage_dict  # Should be excluded
    assert mileage_dict[brooks] == 5.0

    # Test with including retired
    mileage_with_retired_results = mileage_by_shoes(
        runs, shoes=mock_shoes, include_retired=True
    )
    mileage_with_retired_dict = {
        result.shoe.name: result.mileage for result in mileage_with_retired_results
    }
    assert brooks in mileage_with_retired_dict
    assert nikes in mileage_with_retired_dict  # Should be included
    assert mileage_with_retired_dict[brooks] == 5.0
    assert mileage_with_retired_dict[nikes] == 8.0


def test_mileage_by_shoes_include_retired(run_factory):
    """Test mileage calculation including retired shoes."""
    nikes = "Nike Air Zoom Pegasus 37"
    brooks = "Brooks Ghost 14"

    # Create mock shoes with nike retired and brooks active
    from fitness.models.shoe import Shoe, generate_shoe_id

    brooks_id = generate_shoe_id(brooks)
    nikes_id = generate_shoe_id(nikes)

    mock_shoes = [
        Shoe(
            id=nikes_id,
            name=nikes,
            retired_at=date(2024, 12, 15),
            retirement_notes="Worn out",
        ),
        Shoe(id=brooks_id, name=brooks),  # Active shoe
    ]

    runs = [
        run_factory.make(update={"distance": 4.0, "shoe_id": brooks_id}),
        run_factory.make(update={"distance": 5.0, "shoe_id": nikes_id}),
        run_factory.make(update={"distance": 3.0, "shoe_id": nikes_id}),
        run_factory.make(update={"distance": 1.0, "shoe_id": brooks_id}),
    ]

    # Test with include_retired=True to get all shoes including retired ones
    mileage_results = mileage_by_shoes(runs, shoes=mock_shoes, include_retired=True)

    # Convert to dict for easier testing
    results_by_name = {result.shoe.name: result for result in mileage_results}

    # Check Nike shoes (retired) - should be included when include_retired=True
    nike_result = results_by_name[nikes]
    assert nike_result.mileage == 8.0
    assert nike_result.shoe.is_retired is True
    assert nike_result.shoe.retired_at == date(2024, 12, 15)
    assert nike_result.shoe.retirement_notes == "Worn out"

    # Check Brooks shoes (not retired)
    brooks_result = results_by_name[brooks]
    assert brooks_result.mileage == 5.0
    assert brooks_result.shoe.is_retired is False
    assert brooks_result.shoe.retired_at is None
    assert brooks_result.shoe.retirement_notes is None
