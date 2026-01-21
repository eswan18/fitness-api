"""Tests for OAuth Authentication."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from tests.app.conftest import TEST_API_KEY


class TestAuthenticationEndpoints:
    """Test OAuth Authentication on endpoints."""

    def test_update_data_requires_auth(self, client: TestClient):
        """POST /update-data should require authentication."""
        response = client.post("/strava/update-data")
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
        assert "Bearer" in response.headers["WWW-Authenticate"]

    def test_update_data_with_valid_credentials(
        self, auth_client: TestClient, monkeypatch
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
        with patch("fitness.app.dependencies.all_runs") as mock_runs:
            mock_runs.return_value = []
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
        with patch("fitness.app.dependencies.all_runs") as mock_runs:
            mock_runs.return_value = []
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
        response = client.request(method, path, **kwargs)  # type: ignore[arg-type]
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
        response = viewer_client.request(method, path, **kwargs)  # type: ignore[arg-type]
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
        with patch("fitness.app.dependencies.all_runs") as mock_runs:
            mock_runs.return_value = []
            with patch("fitness.db.shoes.get_shoes") as mock_shoes:
                mock_shoes.return_value = []
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


class TestDualAuthentication:
    """Test endpoints that accept either OAuth or API key authentication."""

    def test_trmnl_endpoint_requires_auth(self, client: TestClient):
        """GET /summary/trmnl should require authentication."""
        with patch("fitness.app.dependencies.all_runs") as mock_runs:
            mock_runs.return_value = []
            response = client.get("/summary/trmnl")
            assert response.status_code == 401
            assert "WWW-Authenticate" in response.headers

    def test_trmnl_endpoint_with_oauth(self, viewer_client: TestClient):
        """GET /summary/trmnl should succeed with OAuth authentication."""
        with patch("fitness.app.dependencies.all_runs") as mock_runs:
            mock_runs.return_value = []
            response = viewer_client.get("/summary/trmnl")
            assert response.status_code == 200

    def test_trmnl_endpoint_with_api_key(self, api_key_client: TestClient):
        """GET /summary/trmnl should succeed with API key authentication."""
        with patch("fitness.app.dependencies.all_runs") as mock_runs:
            mock_runs.return_value = []
            response = api_key_client.get("/summary/trmnl")
            assert response.status_code == 200

    def test_trmnl_endpoint_with_invalid_api_key(self, client: TestClient, monkeypatch):
        """GET /summary/trmnl should fail with invalid API key."""
        monkeypatch.setenv("TRMNL_API_KEY", TEST_API_KEY)
        with patch("fitness.app.dependencies.all_runs") as mock_runs:
            mock_runs.return_value = []
            response = client.get(
                "/summary/trmnl", headers={"X-API-Key": "wrong_key"}
            )
            assert response.status_code == 401
