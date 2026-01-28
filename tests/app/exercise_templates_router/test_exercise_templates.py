"""Test the /exercise-templates endpoints."""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from tests._factories.lift import ExerciseTemplateFactory


class TestGetExerciseTemplates:
    """Test GET /exercise-templates endpoint."""

    @patch("fitness.app.routers.exercise_templates.get_all_exercise_templates")
    def test_get_exercise_templates(
        self,
        mock_get_templates: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that exercise templates are returned."""
        template_factory = ExerciseTemplateFactory()
        # DB returns prefixed IDs
        template = template_factory.make({"id": "hevy_bp_001", "title": "Bench Press"})

        mock_get_templates.return_value = [template]

        response = viewer_client.get("/exercise-templates")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "hevy_bp_001"
        assert data[0]["title"] == "Bench Press"

    @patch("fitness.app.routers.exercise_templates.get_all_exercise_templates")
    def test_get_exercise_templates_empty(
        self,
        mock_get_templates: MagicMock,
        viewer_client: TestClient,
    ):
        """Test that empty list is returned when no templates."""
        mock_get_templates.return_value = []

        response = viewer_client.get("/exercise-templates")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_get_exercise_templates_requires_auth(self, client: TestClient):
        """Test that exercise templates endpoint requires authentication."""
        response = client.get("/exercise-templates")
        assert response.status_code == 401
