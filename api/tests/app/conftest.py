import pytest
from fastapi.testclient import TestClient

from fitness.app.app import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="function")
def auth_client() -> TestClient:
    """Test client with mocked OAuth authentication.

    Mocks the verify_oauth_token dependency to validate test tokens.
    """
    # Create a mock that checks the token value
    async def mock_validate(token: str):
        if token == "test_token":
            return {
                'username': 'test_user',
                'email': 'test@example.com',
                'sub': 'test-user-id'
            }
        # Invalid token
        return None

    # Override the validate function
    from fitness.app import oauth
    original_validate = oauth.validate_access_token
    oauth.validate_access_token = mock_validate

    try:
        client = TestClient(app)
        # Set a fake Bearer token
        client.headers = {"Authorization": "Bearer test_token"}
        yield client
    finally:
        # Restore original
        oauth.validate_access_token = original_validate
