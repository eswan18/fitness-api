import pytest
from uuid import UUID
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from fitness.app.app import app
from fitness.models.user import User


# Shared test user data
TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
TEST_IDP_USER_ID = UUID("00000000-0000-0000-0000-000000000002")


def _create_test_user(role: str = "viewer") -> User:
    """Create a test user with specified role."""
    return User(
        id=TEST_USER_ID,
        idp_user_id=TEST_IDP_USER_ID,
        email="test@example.com",
        username="test_user",
        role=role,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="function")
def auth_client() -> TestClient:
    """Test client with mocked OAuth authentication (editor role).

    Mocks the verify_oauth_token dependency to validate test tokens.
    Returns a user with 'editor' role for backwards compatibility.
    """

    # Create a mock that checks the token value
    def mock_validate(token: str):
        if token == "test_token":
            return {
                "username": "test_user",
                "email": "test@example.com",
                "sub": str(TEST_IDP_USER_ID),
            }
        # Invalid token
        return None

    def mock_get_or_create_user(idp_user_id, email, username):
        return _create_test_user(role="editor")

    # Override the validate function and user creation
    # Important: mock at the location where it's imported, not where it's defined
    from fitness.app import oauth

    original_validate = oauth.validate_jwt_token
    original_get_or_create = oauth.get_or_create_user
    oauth.validate_jwt_token = mock_validate
    oauth.get_or_create_user = mock_get_or_create_user

    try:
        client = TestClient(app)
        # Set a fake Bearer token
        client.headers = {"Authorization": "Bearer test_token"}
        yield client
    finally:
        # Restore original
        oauth.validate_jwt_token = original_validate
        oauth.get_or_create_user = original_get_or_create


@pytest.fixture(scope="function")
def viewer_client() -> TestClient:
    """Test client with mocked OAuth authentication (viewer role)."""

    def mock_validate(token: str):
        if token == "viewer_token":
            return {
                "username": "viewer_user",
                "email": "viewer@example.com",
                "sub": str(TEST_IDP_USER_ID),
            }
        return None

    def mock_get_or_create_user(idp_user_id, email, username):
        return _create_test_user(role="viewer")

    from fitness.app import oauth

    original_validate = oauth.validate_jwt_token
    original_get_or_create = oauth.get_or_create_user
    oauth.validate_jwt_token = mock_validate
    oauth.get_or_create_user = mock_get_or_create_user

    try:
        client = TestClient(app)
        client.headers = {"Authorization": "Bearer viewer_token"}
        yield client
    finally:
        oauth.validate_jwt_token = original_validate
        oauth.get_or_create_user = original_get_or_create


@pytest.fixture(scope="function")
def editor_client() -> TestClient:
    """Test client with mocked OAuth authentication (editor role)."""

    def mock_validate(token: str):
        if token == "editor_token":
            return {
                "username": "editor_user",
                "email": "editor@example.com",
                "sub": str(TEST_IDP_USER_ID),
            }
        return None

    def mock_get_or_create_user(idp_user_id, email, username):
        return _create_test_user(role="editor")

    from fitness.app import oauth

    original_validate = oauth.validate_jwt_token
    original_get_or_create = oauth.get_or_create_user
    oauth.validate_jwt_token = mock_validate
    oauth.get_or_create_user = mock_get_or_create_user

    try:
        client = TestClient(app)
        client.headers = {"Authorization": "Bearer editor_token"}
        yield client
    finally:
        oauth.validate_jwt_token = original_validate
        oauth.get_or_create_user = original_get_or_create
