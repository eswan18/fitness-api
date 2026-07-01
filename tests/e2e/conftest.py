import os
from pathlib import Path
from uuid import UUID
from datetime import date, datetime, timezone
from typing import Iterable, Iterator
import pytest
from testcontainers.postgres import PostgresContainer
from alembic.config import Config
from alembic import command
from fastapi.testclient import TestClient

from fitness.models.shoe import Shoe
from fitness.models.user import User, Role

# Ensure allowed environment for env_loader
os.environ.setdefault("ENV", "dev")


def make_shoe(
    brand: str,
    model: str,
    *,
    size: float = 10.0,
    purchased_date: date = date(2024, 1, 1),
    **kwargs,
) -> Shoe:
    """Create a shoe for tests; returns the created Shoe (with opaque id).

    Imports no longer create or assign shoes, so tests that need a shoe to exist
    must create it explicitly. The display ``name`` is ``f"{brand} {model}"``.
    """
    # Imported lazily so DATABASE_URL is set (by the db_url fixture) before the
    # db/connection module resolves it.
    from fitness.db.shoes import create_shoe as _create_shoe

    return _create_shoe(
        brand=brand, model=model, size=size, purchased_date=purchased_date, **kwargs
    )


def assign_shoe_to_runs(shoe_id: str, run_ids: Iterable[str]) -> None:
    """Attribute already-inserted runs to a shoe (imports no longer do this)."""
    from fitness.db.connection import get_db_connection

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE runs SET shoe_id = %s WHERE id = ANY(%s)",
                (shoe_id, list(run_ids)),
            )
        conn.commit()


# Shared test user data
TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
TEST_IDP_USER_ID = UUID("00000000-0000-0000-0000-000000000002")


def _create_test_user(role: Role = "viewer") -> User:
    """Create a test user with specified role."""
    return User(
        id=TEST_USER_ID,
        idp_user_id=TEST_IDP_USER_ID,
        email="e2e_test@example.com",
        username="e2e_test_user",
        role=role,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture(scope="session")
def db_url() -> Iterator[str]:
    """Start a Postgres container, run migrations, and return the DB URL."""
    with PostgresContainer("postgres:16") as pg:
        raw_url = pg.get_connection_url()
        # Normalize to psycopg3-compatible URL if needed
        url = raw_url.replace("postgresql+psycopg2://", "postgresql://")
        os.environ["DATABASE_URL"] = url

        # Run Alembic migrations against this database
        api_dir = Path(__file__).resolve().parents[2]
        alembic_cfg = Config(str(api_dir / "alembic.ini"))
        command.upgrade(alembic_cfg, "head")

        yield url


@pytest.fixture(scope="session")
def _mock_oauth(db_url: str) -> Iterator[None]:
    """Session-scoped OAuth mocking for E2E tests.

    Sets up mocks that accept both viewer and editor tokens.
    Must depend on db_url to ensure DB is ready before app imports.
    """
    # Import oauth module after db_url fixture sets DATABASE_URL
    from fitness.app import oauth

    original_validate = oauth.validate_jwt_token
    original_get_or_create = oauth.get_or_create_user

    def mock_validate(token: str) -> dict[str, str] | None:
        if token == "viewer_token":
            return {
                "username": "e2e_viewer",
                "email": "viewer@example.com",
                "sub": str(TEST_IDP_USER_ID),
            }
        if token == "editor_token":
            return {
                "username": "e2e_editor",
                "email": "editor@example.com",
                "sub": str(TEST_IDP_USER_ID),
            }
        return None

    def mock_get_or_create_user(
        idp_user_id: UUID, email: str | None, username: str | None
    ) -> User:
        # Determine role based on username from the token
        if username == "e2e_editor":
            return _create_test_user(role="editor")
        return _create_test_user(role="viewer")

    oauth.validate_jwt_token = mock_validate  # ty: ignore[invalid-assignment]
    oauth.get_or_create_user = mock_get_or_create_user  # ty: ignore[invalid-assignment]

    yield

    oauth.validate_jwt_token = original_validate
    oauth.get_or_create_user = original_get_or_create


@pytest.fixture(scope="session")
def client(db_url: str, _mock_oauth: None) -> TestClient:
    """Unauthenticated test client (for testing auth requirements)."""
    from fitness.app.app import app

    return TestClient(app)


@pytest.fixture(scope="session")
def viewer_client(db_url: str, _mock_oauth: None) -> TestClient:
    """Test client with viewer role authentication."""
    from fitness.app.app import app

    client = TestClient(app)
    client.headers = {"Authorization": "Bearer viewer_token"}
    return client


@pytest.fixture(scope="session")
def editor_client(db_url: str, _mock_oauth: None) -> TestClient:
    """Test client with editor role authentication."""
    from fitness.app.app import app

    client = TestClient(app)
    client.headers = {"Authorization": "Bearer editor_token"}
    return client


# Backwards compatibility alias
@pytest.fixture(scope="session")
def auth_client(editor_client: TestClient) -> TestClient:
    """Alias for editor_client for backwards compatibility."""
    return editor_client
