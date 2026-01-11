"""
Tests for user database operations.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from uuid import UUID

from fitness.db.users import (
    get_user_by_idp_id,
    create_user,
    update_user_profile,
    get_or_create_user,
)
from fitness.models.user import User


# Test UUIDs
TEST_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
TEST_IDP_USER_ID = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def sample_user_row():
    """Create a sample database row for a user."""
    return (
        TEST_USER_ID,
        TEST_IDP_USER_ID,
        "test@example.com",
        "testuser",
        "viewer",
        datetime(2024, 1, 15, 10, 0, 0),
        datetime(2024, 1, 15, 10, 0, 0),
    )


@pytest.fixture
def sample_user():
    """Create a sample User object."""
    return User(
        id=TEST_USER_ID,
        idp_user_id=TEST_IDP_USER_ID,
        email="test@example.com",
        username="testuser",
        role="viewer",
        created_at=datetime(2024, 1, 15, 10, 0, 0),
        updated_at=datetime(2024, 1, 15, 10, 0, 0),
    )


class TestGetUserByIdpId:
    """Test get_user_by_idp_id function."""

    @patch("fitness.db.users.get_db_cursor")
    def test_user_found(self, mock_get_cursor, sample_user_row):
        """Test successful user retrieval."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = sample_user_row
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        user = get_user_by_idp_id(TEST_IDP_USER_ID)

        assert user is not None
        assert isinstance(user, User)
        assert user.id == TEST_USER_ID
        assert user.idp_user_id == TEST_IDP_USER_ID
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.role == "viewer"
        mock_cursor.execute.assert_called_once()

    @patch("fitness.db.users.get_db_cursor")
    def test_user_not_found(self, mock_get_cursor):
        """Test handling of non-existent user."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        user = get_user_by_idp_id(TEST_IDP_USER_ID)

        assert user is None


class TestCreateUser:
    """Test create_user function."""

    @patch("fitness.db.users.get_db_cursor")
    def test_create_user_success(self, mock_get_cursor, sample_user_row):
        """Test successful user creation."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = sample_user_row
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        user = create_user(
            idp_user_id=TEST_IDP_USER_ID,
            email="test@example.com",
            username="testuser",
            role="viewer",
        )

        assert user is not None
        assert isinstance(user, User)
        assert user.idp_user_id == TEST_IDP_USER_ID
        assert user.email == "test@example.com"
        assert user.role == "viewer"

        # Verify INSERT was called
        call_args = mock_cursor.execute.call_args[0]
        assert "INSERT INTO users" in call_args[0]

    @patch("fitness.db.users.get_db_cursor")
    def test_create_user_with_editor_role(self, mock_get_cursor):
        """Test user creation with editor role."""
        editor_row = (
            TEST_USER_ID,
            TEST_IDP_USER_ID,
            "editor@example.com",
            "editor",
            "editor",
            datetime(2024, 1, 15, 10, 0, 0),
            datetime(2024, 1, 15, 10, 0, 0),
        )
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = editor_row
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        user = create_user(
            idp_user_id=TEST_IDP_USER_ID,
            email="editor@example.com",
            username="editor",
            role="editor",
        )

        assert user.role == "editor"

    @patch("fitness.db.users.get_db_cursor")
    def test_create_user_with_null_email_username(self, mock_get_cursor):
        """Test user creation with null email and username."""
        null_fields_row = (
            TEST_USER_ID,
            TEST_IDP_USER_ID,
            None,
            None,
            "viewer",
            datetime(2024, 1, 15, 10, 0, 0),
            datetime(2024, 1, 15, 10, 0, 0),
        )
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = null_fields_row
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        user = create_user(
            idp_user_id=TEST_IDP_USER_ID,
            email=None,
            username=None,
        )

        assert user.email is None
        assert user.username is None


class TestUpdateUserProfile:
    """Test update_user_profile function."""

    @patch("fitness.db.users.get_db_cursor")
    def test_update_success(self, mock_get_cursor):
        """Test successful profile update."""
        updated_row = (
            TEST_USER_ID,
            TEST_IDP_USER_ID,
            "new@example.com",
            "newusername",
            "viewer",
            datetime(2024, 1, 15, 10, 0, 0),
            datetime(2024, 1, 16, 10, 0, 0),
        )
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = updated_row
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        user = update_user_profile(
            idp_user_id=TEST_IDP_USER_ID,
            email="new@example.com",
            username="newusername",
        )

        assert user is not None
        assert user.email == "new@example.com"
        assert user.username == "newusername"

        # Verify UPDATE was called
        call_args = mock_cursor.execute.call_args[0]
        assert "UPDATE users" in call_args[0]

    @patch("fitness.db.users.get_db_cursor")
    def test_update_user_not_found(self, mock_get_cursor):
        """Test update of non-existent user."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        user = update_user_profile(
            idp_user_id=TEST_IDP_USER_ID,
            email="new@example.com",
            username="newusername",
        )

        assert user is None


class TestGetOrCreateUser:
    """Test get_or_create_user function."""

    @patch("fitness.db.users.get_user_by_idp_id")
    def test_returns_existing_user(self, mock_get_user, sample_user):
        """Test that existing user is returned without creating new one."""
        mock_get_user.return_value = sample_user

        user = get_or_create_user(
            idp_user_id=TEST_IDP_USER_ID,
            email="test@example.com",
            username="testuser",
        )

        assert user == sample_user
        mock_get_user.assert_called_once_with(TEST_IDP_USER_ID)

    @patch("fitness.db.users.create_user")
    @patch("fitness.db.users.get_user_by_idp_id")
    def test_creates_new_user_when_not_found(
        self, mock_get_user, mock_create_user, sample_user
    ):
        """Test that new user is created when not found."""
        mock_get_user.return_value = None
        mock_create_user.return_value = sample_user

        user = get_or_create_user(
            idp_user_id=TEST_IDP_USER_ID,
            email="test@example.com",
            username="testuser",
        )

        assert user == sample_user
        mock_create_user.assert_called_once_with(
            TEST_IDP_USER_ID, "test@example.com", "testuser", role="viewer"
        )

    @patch("fitness.db.users.update_user_profile")
    @patch("fitness.db.users.get_user_by_idp_id")
    def test_updates_profile_when_changed(
        self, mock_get_user, mock_update_profile, sample_user
    ):
        """Test that profile is updated when email or username changed."""
        # Existing user with different email
        mock_get_user.return_value = sample_user

        updated_user = User(
            id=TEST_USER_ID,
            idp_user_id=TEST_IDP_USER_ID,
            email="new@example.com",
            username="testuser",
            role="viewer",
            created_at=datetime(2024, 1, 15, 10, 0, 0),
            updated_at=datetime(2024, 1, 16, 10, 0, 0),
        )
        mock_update_profile.return_value = updated_user

        user = get_or_create_user(
            idp_user_id=TEST_IDP_USER_ID,
            email="new@example.com",  # Changed email
            username="testuser",
        )

        assert user.email == "new@example.com"
        mock_update_profile.assert_called_once_with(
            TEST_IDP_USER_ID, "new@example.com", "testuser"
        )

    @patch("fitness.db.users.update_user_profile")
    @patch("fitness.db.users.get_user_by_idp_id")
    def test_no_update_when_profile_unchanged(
        self, mock_get_user, mock_update_profile, sample_user
    ):
        """Test that profile is not updated when unchanged."""
        mock_get_user.return_value = sample_user

        user = get_or_create_user(
            idp_user_id=TEST_IDP_USER_ID,
            email="test@example.com",  # Same as existing
            username="testuser",  # Same as existing
        )

        assert user == sample_user
        mock_update_profile.assert_not_called()
