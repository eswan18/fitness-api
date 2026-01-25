import pytest
from fitness.app import env_loader  # noqa: F401

from ._factories import RunFactory, StravaActivityWithGearFactory, MmfActivityFactory


class AccidentalDatabaseAccessError(Exception):
    """Raised when a unit test accidentally tries to access the database."""

    pass


def _raise_db_access_error(*args, **kwargs):
    """Raise an error when DB access is attempted in unit tests."""
    raise AccidentalDatabaseAccessError(
        "Unit test attempted to connect to the database! "
        "Either mock the database call with @patch('fitness.db.connection.get_db_cursor') "
        "or similar, or mark this test as @pytest.mark.e2e if it requires real DB access."
    )


@pytest.fixture(autouse=True)
def prevent_db_access_in_unit_tests(request, monkeypatch):
    """Prevent accidental database access in unit tests.

    This fixture automatically applies to all tests. For e2e tests (marked with
    @pytest.mark.e2e), it does nothing. For all other tests, it patches psycopg.connect
    to raise a clear error if any code path tries to access the database without
    proper mocking.

    This catches issues early when someone forgets to mock a DB call in a unit test.
    """
    # Skip this protection for e2e and integration tests - they need real DB access
    markers = [marker.name for marker in request.node.iter_markers()]
    if "e2e" in markers or "integration" in markers:
        yield
        return

    # For unit tests, patch psycopg.connect to fail fast with a clear error
    monkeypatch.setattr("psycopg.connect", _raise_db_access_error)
    yield


@pytest.fixture(scope="session")
def run_factory() -> RunFactory:
    return RunFactory()


@pytest.fixture(scope="session")
def strava_activity_with_gear_factory() -> StravaActivityWithGearFactory:
    return StravaActivityWithGearFactory()


@pytest.fixture(scope="session")
def mmf_activity_factory() -> MmfActivityFactory:
    return MmfActivityFactory()
