"""Tests for OAuth Authentication."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from fitness.app import app
from fitness.app.dependencies import strava_client


@pytest.fixture(scope="function")
def override_strava_client():
    """Effectively disable the Strava client for the duration of the test, to avoid it trying to refresh the token."""
    app.dependency_overrides[strava_client] = lambda: None
    yield
    app.dependency_overrides = {}


class TestAuthenticationEndpoints:
    """Test OAuth Authentication on endpoints."""

    def test_update_data_requires_auth(self, client: TestClient):
        """POST /update-data should require authentication."""
        response = client.post("/strava/update-data")
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
        assert "Bearer" in response.headers["WWW-Authenticate"]

    def test_update_data_with_valid_credentials(
        self, auth_client: TestClient, monkeypatch, override_strava_client
    ):
        """POST /strava/update-data should succeed with valid OAuth token (editor)."""
        with monkeypatch.context() as m:
            m.setattr("fitness.app.routers.strava.load_strava_runs", lambda client: [])
            m.setattr("fitness.app.routers.strava.get_existing_run_ids", lambda: [])
            response = auth_client.post("/strava/update-data")

        assert response.status_code == 200
        data = response.json()
        assert data["inserted_count"] == 0

    def test_update_data_with_invalid_token(self, client: TestClient):
        """POST /strava/update-data should fail with invalid token."""
        response = client.post(
            "/strava/update-data", headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

    def test_read_runs_requires_viewer_auth(self, client: TestClient):
        """GET /runs should require viewer authentication."""
        response = client.get("/runs")
        assert response.status_code == 401

    def test_read_runs_with_viewer_auth(self, viewer_client: TestClient):
        """GET /runs should succeed with viewer authentication."""
        with patch("fitness.app.dependencies.all_runs") as mock_runs:
            mock_runs.return_value = []
            response = viewer_client.get("/runs")
            assert response.status_code == 200

    def test_health_endpoint_no_auth(self, client: TestClient):
        """GET /health should remain public."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_metrics_requires_viewer_auth(self, client: TestClient):
        """GET /metrics/* endpoints should require viewer authentication."""
        response = client.get("/metrics/mileage/total")
        assert response.status_code == 401

    def test_metrics_with_viewer_auth(self, viewer_client: TestClient):
        """GET /metrics/* endpoints should succeed with viewer authentication."""
        with patch("fitness.app.dependencies.all_runs") as mock_runs:
            mock_runs.return_value = []
            response = viewer_client.get("/metrics/mileage/total")
            assert response.status_code == 200


class TestProtectedMutationEndpoints:
    """Test that all mutation endpoints are properly protected."""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/strava/update-data"),
            ("PATCH", "/runs/test_run_123"),
            ("POST", "/runs/test_run_123/restore/1"),
            ("PATCH", "/shoes/test_shoe_id"),
            ("POST", "/sync/runs/test_run_123"),
            ("DELETE", "/sync/runs/test_run_123"),
        ],
    )
    def test_mutation_endpoints_require_auth(self, method, path, client: TestClient):
        """All mutation endpoints should return 401 without auth."""
        # Prepare request body for endpoints that need it
        body = {}
        if "runs" in path and method == "PATCH":
            body = {"changed_by": "test", "distance": 5.0}
        elif "shoes" in path:
            body = {"retired_at": "2024-01-01"}

        kwargs = {"json": body} if body else {}
        response = client.request(method, path, **kwargs)
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/strava/update-data"),
            ("PATCH", "/runs/test_run_123"),
            ("POST", "/runs/test_run_123/restore/1"),
            ("PATCH", "/shoes/test_shoe_id"),
            ("POST", "/sync/runs/test_run_123"),
            ("DELETE", "/sync/runs/test_run_123"),
        ],
    )
    def test_mutation_endpoints_require_editor_role(
        self, method, path, viewer_client: TestClient
    ):
        """All mutation endpoints should return 403 for viewer role."""
        # Prepare request body for endpoints that need it
        body = {}
        if "runs" in path and method == "PATCH":
            body = {"changed_by": "test", "distance": 5.0}
        elif "shoes" in path:
            body = {"retired_at": "2024-01-01"}

        kwargs = {"json": body} if body else {}
        response = viewer_client.request(method, path, **kwargs)
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "path",
        [
            "/runs",
            "/runs/details",
            "/runs-details",
            "/metrics/mileage/total",
            "/metrics/mileage/by-shoe",
            "/metrics/seconds/total",
            "/shoes",
            "/environment",
        ],
    )
    def test_read_endpoints_require_viewer_auth(self, path, client: TestClient):
        """Read endpoints should require viewer authentication."""
        response = client.get(path)
        assert response.status_code == 401

    @pytest.mark.parametrize(
        "path",
        [
            "/runs",
            "/runs/details",
            "/runs-details",
            "/metrics/mileage/total",
            "/metrics/mileage/by-shoe",
            "/metrics/seconds/total",
            "/shoes",
            "/environment",
        ],
    )
    def test_read_endpoints_work_with_viewer_auth(
        self, path, viewer_client: TestClient
    ):
        """Read endpoints should work with viewer authentication."""
        with patch("fitness.app.dependencies.all_runs") as mock_runs:
            mock_runs.return_value = []
            with patch("fitness.db.shoes.get_shoes") as mock_shoes:
                mock_shoes.return_value = []
                response = viewer_client.get(path)
                # Should succeed (may be 200 or other valid response code)
                assert response.status_code == 200

    def test_health_endpoint_remains_public(self, client: TestClient):
        """GET /health should remain public."""
        response = client.get("/health")
        assert response.status_code == 200
