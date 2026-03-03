"""Tests for static file serving."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


class TestStaticFilesMount:
    """Tests for the /static endpoint serving static files."""

    @pytest.mark.asyncio
    async def test_static_tokenlist_served(self, mock_y_module: None) -> None:
        """GET /static/tokenlists/uniswap-default.json returns 200 with JSON."""
        from src.server import app

        client = TestClient(app)
        response = client.get("/static/tokenlists/uniswap-default.json")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")

        # Verify it's valid JSON with tokens array
        data = response.json()
        assert "tokens" in data
        assert isinstance(data["tokens"], list)
        assert len(data["tokens"]) > 0

    @pytest.mark.asyncio
    async def test_static_tokenlist_token_format(self, mock_y_module: None) -> None:
        """Tokenlist tokens have required fields (address, chainId, symbol, name)."""
        from src.server import app

        client = TestClient(app)
        response = client.get("/static/tokenlists/uniswap-default.json")

        assert response.status_code == 200
        data = response.json()

        # Check first token has required fields
        if data["tokens"]:
            token = data["tokens"][0]
            assert "address" in token
            assert "chainId" in token
            assert "symbol" in token
            assert "name" in token

    @pytest.mark.asyncio
    async def test_static_file_not_found_returns_404(self, mock_y_module: None) -> None:
        """GET /static/nonexistent.file returns 404."""
        from src.server import app

        client = TestClient(app)
        response = client.get("/static/nonexistent.file")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_static_directory_not_listable(self, mock_y_module: None) -> None:
        """GET /static/ returns 404 (directory listing disabled)."""
        from src.server import app

        client = TestClient(app)
        response = client.get("/static/")

        # StaticFiles returns 404 for directory requests (no index.html)
        assert response.status_code == 404


class TestStaticDirectoryStructure:
    """Tests for the static directory structure."""

    def test_static_directory_exists(self) -> None:
        """static/ directory exists."""
        static_dir = Path(__file__).parent.parent.parent / "static"
        assert static_dir.is_dir()

    def test_js_directory_exists(self) -> None:
        """static/js/ directory exists."""
        js_dir = Path(__file__).parent.parent.parent / "static" / "js"
        assert js_dir.is_dir()

    def test_css_directory_exists(self) -> None:
        """static/css/ directory exists."""
        css_dir = Path(__file__).parent.parent.parent / "static" / "css"
        assert css_dir.is_dir()

    def test_tokenlists_directory_exists(self) -> None:
        """static/tokenlists/ directory exists."""
        tokenlists_dir = Path(__file__).parent.parent.parent / "static" / "tokenlists"
        assert tokenlists_dir.is_dir()

    def test_uniswap_tokenlist_exists(self) -> None:
        """Uniswap default tokenlist file exists."""
        tokenlist_path = (
            Path(__file__).parent.parent.parent / "static" / "tokenlists" / "uniswap-default.json"
        )
        assert tokenlist_path.is_file()

    def test_uniswap_tokenlist_valid_json(self) -> None:
        """Uniswap default tokenlist is valid JSON with tokens array."""
        import json

        tokenlist_path = (
            Path(__file__).parent.parent.parent / "static" / "tokenlists" / "uniswap-default.json"
        )
        with open(tokenlist_path) as f:
            data = json.load(f)

        assert "tokens" in data
        assert isinstance(data["tokens"], list)
        assert len(data["tokens"]) > 0
