"""Tests for API documentation endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestDocEndpoints:
    """Tests for FastAPI built-in docs endpoints."""

    @pytest.mark.asyncio
    async def test_docs_returns_200(self, mock_y_module: None) -> None:
        """GET /docs returns 200 with Swagger UI HTML."""
        from src.server import app

        client = TestClient(app)
        response = client.get("/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "openapi.json" in response.text
        assert '"/openapi.json"' not in response.text

    @pytest.mark.asyncio
    async def test_redoc_returns_200(self, mock_y_module: None) -> None:
        """GET /redoc returns 200 with ReDoc HTML."""
        from src.server import app

        client = TestClient(app)
        response = client.get("/redoc")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_openapi_json_returns_200(self, mock_y_module: None) -> None:
        """GET /openapi.json returns 200 with valid JSON."""
        from src.server import app

        client = TestClient(app)
        response = client.get("/openapi.json")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data

    @pytest.mark.asyncio
    async def test_root_returns_404(self, mock_y_module: None) -> None:
        """GET / returns 404 (static file serving removed)."""
        from src.server import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_static_js_returns_404(self, mock_y_module: None) -> None:
        """GET /static/js/app.js returns 404 (static file serving removed)."""
        from src.server import app

        client = TestClient(app)
        response = client.get("/static/js/app.js")

        assert response.status_code == 404
