"""Tests for server._fetch_price behavior."""

from unittest.mock import AsyncMock, patch

import pytest

DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"


class TestTimestampResolution:
    """Tests for timestamp parameter resolution in the price endpoint."""

    @pytest.mark.asyncio
    async def test_timestamp_resolves_to_block(self, mock_y_module: None) -> None:
        """Timestamp is resolved to a block number via get_block_at_timestamp."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_block_at_timestamp = AsyncMock(return_value=18000000)
        mock_get_price = AsyncMock(return_value=1.0)
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_block_at_timestamp", mock_get_block_at_timestamp),
            patch("y.get_price", mock_get_price),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get(
                "/price",
                params={"token": DAI, "timestamp": "1700000000"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["block"] == 18000000
            assert data["price"] == 1.0
            # get_block_at_timestamp should be called with the timestamp
            mock_get_block_at_timestamp.assert_called_once()

    @pytest.mark.asyncio
    async def test_iso8601_timestamp_resolves(self, mock_y_module: None) -> None:
        """ISO 8601 timestamp is resolved to the same block as equivalent Unix epoch."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_block_at_timestamp = AsyncMock(return_value=18000000)
        mock_get_price = AsyncMock(return_value=1.0)
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_block_at_timestamp", mock_get_block_at_timestamp),
            patch("y.get_price", mock_get_price),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get(
                "/price",
                params={"token": DAI, "timestamp": "2023-11-14T22:13:20Z"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["block"] == 18000000

    @pytest.mark.asyncio
    async def test_timestamp_and_block_returns_400(self, mock_y_module: None) -> None:
        """Both timestamp and block parameters returns 400."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_chain = type("MockChain", (), {"height": 19000000})()

        with patch("brownie.chain", mock_chain):
            client = TestClient(app)
            response = client.get(
                "/price",
                params={"token": DAI, "timestamp": "1700000000", "block": "18000000"},
            )

            assert response.status_code == 400
            data = response.json()
            assert "mutually exclusive" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_timestamp_returns_400(self, mock_y_module: None) -> None:
        """Invalid timestamp format returns 400."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_chain = type("MockChain", (), {"height": 19000000})()

        with patch("brownie.chain", mock_chain):
            client = TestClient(app)
            response = client.get(
                "/price",
                params={"token": DAI, "timestamp": "not-a-timestamp"},
            )

            assert response.status_code == 400
            data = response.json()
            assert "timestamp" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_future_timestamp_returns_400(self, mock_y_module: None) -> None:
        """Future timestamp returns 400."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_chain = type("MockChain", (), {"height": 19000000})()

        with patch("brownie.chain", mock_chain):
            client = TestClient(app)
            response = client.get(
                "/price",
                params={"token": DAI, "timestamp": "9999999999"},
            )

            assert response.status_code == 400
            data = response.json()
            assert "future" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_timestamp_without_token_validates_token_first(self, mock_y_module: None) -> None:
        """Missing token with timestamp validates token first."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_chain = type("MockChain", (), {"height": 19000000})()

        with patch("brownie.chain", mock_chain):
            client = TestClient(app)
            response = client.get(
                "/price",
                params={"timestamp": "1700000000"},
            )

            assert response.status_code == 400
            data = response.json()
            assert "token" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_timestamp_resolution_failure_returns_502(self, mock_y_module: None) -> None:
        """When get_block_at_timestamp fails (RPC error), returns 502."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_block_at_timestamp = AsyncMock(side_effect=ConnectionError("RPC failed"))
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_block_at_timestamp", mock_get_block_at_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get(
                "/price",
                params={"token": DAI, "timestamp": "1700000000"},
            )

            assert response.status_code == 502
            data = response.json()
            assert "timestamp" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_response_includes_resolved_block(self, mock_y_module: None) -> None:
        """The response from a timestamp-based query includes the resolved block number."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_block_at_timestamp = AsyncMock(return_value=18000000)
        mock_get_price = AsyncMock(return_value=1.0)
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_block_at_timestamp", mock_get_block_at_timestamp),
            patch("y.get_price", mock_get_price),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get(
                "/price",
                params={"token": DAI, "timestamp": "1700000000"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["block"] == 18000000
            assert "price" in data
            assert data["cached"] is False


class TestFetchPriceNoneReturn:
    """Test that None return from get_price results in None return (no retry, no exception)."""

    @pytest.mark.asyncio
    async def test_none_return_no_retry(self, mock_y_module: None) -> None:
        """When get_price returns None, _fetch_price returns None immediately without retry."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(return_value=None)
        with patch("y.get_price", mock_get_price):
            result = await _fetch_price(DAI, 18000000)
            assert result is None
            # Should only be called once (no retry)
            mock_get_price.assert_called_once_with(DAI, 18000000, fail_to_None=True, sync=False)

    @pytest.mark.asyncio
    async def test_none_return_with_amount(self, mock_y_module: None) -> None:
        """None return with amount parameter also returns None without retry."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(return_value=None)
        with patch("y.get_price", mock_get_price):
            result = await _fetch_price(DAI, 18000000, amount=1000.0)
            assert result is None
            mock_get_price.assert_called_once_with(
                DAI, 18000000, amount=1000.0, fail_to_None=True, sync=False
            )


class TestFetchPriceInvalidValues:
    """Test that NaN, Inf, and negative prices raise ValueError."""

    @pytest.mark.asyncio
    async def test_nan_raises_value_error(self, mock_y_module: None) -> None:
        """NaN price raises ValueError."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(return_value=float("nan"))
        with (
            patch("y.get_price", mock_get_price),
            pytest.raises(ValueError, match="Invalid price value"),
        ):
            await _fetch_price(DAI, 18000000)

    @pytest.mark.asyncio
    async def test_inf_raises_value_error(self, mock_y_module: None) -> None:
        """Infinity price raises ValueError."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(return_value=float("inf"))
        with (
            patch("y.get_price", mock_get_price),
            pytest.raises(ValueError, match="Invalid price value"),
        ):
            await _fetch_price(DAI, 18000000)

    @pytest.mark.asyncio
    async def test_negative_inf_raises_value_error(self, mock_y_module: None) -> None:
        """Negative infinity price raises ValueError."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(return_value=float("-inf"))
        with (
            patch("y.get_price", mock_get_price),
            pytest.raises(ValueError, match="Invalid price value"),
        ):
            await _fetch_price(DAI, 18000000)

    @pytest.mark.asyncio
    async def test_negative_raises_value_error(self, mock_y_module: None) -> None:
        """Negative price raises ValueError."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(return_value=-1.0)
        with (
            patch("y.get_price", mock_get_price),
            pytest.raises(ValueError, match="Negative price"),
        ):
            await _fetch_price(DAI, 18000000)


class TestFetchPriceRetry:
    """Test that transient errors trigger retry."""

    @pytest.mark.asyncio
    async def test_connection_error_retries_and_succeeds(self, mock_y_module: None) -> None:
        """ConnectionError triggers retry, then success on second attempt."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(
            side_effect=[
                ConnectionError("RPC connection failed"),
                1.0,  # Success on retry
            ]
        )
        with patch("y.get_price", mock_get_price):
            result = await _fetch_price(DAI, 18000000)
            assert result == 1.0
            assert mock_get_price.call_count == 2

    @pytest.mark.asyncio
    async def test_timeout_error_retries(self, mock_y_module: None) -> None:
        """TimeoutError triggers retry."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(
            side_effect=[
                TimeoutError("Request timed out"),
                2.0,  # Success on retry
            ]
        )
        with patch("y.get_price", mock_get_price):
            result = await _fetch_price(DAI, 18000000)
            assert result == 2.0
            assert mock_get_price.call_count == 2

    @pytest.mark.asyncio
    async def test_os_error_retries(self, mock_y_module: None) -> None:
        """OSError triggers retry."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(
            side_effect=[
                OSError("Network error"),
                3.0,  # Success on retry
            ]
        )
        with patch("y.get_price", mock_get_price):
            result = await _fetch_price(DAI, 18000000)
            assert result == 3.0
            assert mock_get_price.call_count == 2

    @pytest.mark.asyncio
    async def test_connection_error_exhausts_retries(self, mock_y_module: None) -> None:
        """After 2 attempts, RetryError is raised."""
        from tenacity import RetryError

        from src.server import _fetch_price

        mock_get_price = AsyncMock(side_effect=ConnectionError("RPC connection failed"))
        with patch("y.get_price", mock_get_price), pytest.raises(RetryError):
            await _fetch_price(DAI, 18000000)
        assert mock_get_price.call_count == 2


class TestFetchPriceNoRetryForValueError:
    """Test that ValueError does NOT trigger retry."""

    @pytest.mark.asyncio
    async def test_value_error_no_retry(self, mock_y_module: None) -> None:
        """ValueError (from invalid price) does not trigger retry."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(return_value=float("nan"))
        with patch("y.get_price", mock_get_price), pytest.raises(ValueError):
            await _fetch_price(DAI, 18000000)
        # Should only be called once (no retry for ValueError)
        mock_get_price.assert_called_once()


class TestFetchPriceSuccess:
    """Test successful price fetch."""

    @pytest.mark.asyncio
    async def test_valid_price_returned(self, mock_y_module: None) -> None:
        """Valid price is returned as float."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(return_value=1.0)
        with patch("y.get_price", mock_get_price):
            result = await _fetch_price(DAI, 18000000)
            assert result == 1.0
            assert isinstance(result, float)

    @pytest.mark.asyncio
    async def test_valid_price_with_amount(self, mock_y_module: None) -> None:
        """Valid price with amount parameter."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(return_value=0.99)
        with patch("y.get_price", mock_get_price):
            result = await _fetch_price(DAI, 18000000, amount=1000.0)
            assert result == 0.99
            mock_get_price.assert_called_once_with(
                DAI, 18000000, amount=1000.0, fail_to_None=True, sync=False
            )

    @pytest.mark.asyncio
    async def test_zero_price_is_valid(self, mock_y_module: None) -> None:
        """Zero price is valid (not negative, not NaN, not Inf)."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(return_value=0.0)
        with patch("y.get_price", mock_get_price):
            result = await _fetch_price(DAI, 18000000)
            assert result == 0.0


class TestFetchPriceNewParams:
    """Test that new params (skip_cache, ignore_pools, silent) are forwarded to get_price."""

    @pytest.mark.asyncio
    async def test_skip_cache_forwarded(self, mock_y_module: None) -> None:
        """skip_cache=True is forwarded to get_price."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(return_value=1.0)
        with patch("y.get_price", mock_get_price):
            result = await _fetch_price(DAI, 18000000, skip_cache=True)
            assert result == 1.0
            mock_get_price.assert_called_once_with(
                DAI, 18000000, fail_to_None=True, sync=False, skip_cache=True
            )

    @pytest.mark.asyncio
    async def test_ignore_pools_forwarded(self, mock_y_module: None) -> None:
        """ignore_pools tuple is forwarded to get_price."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(return_value=1.0)
        ignore_pools = (USDC, WETH)
        with patch("y.get_price", mock_get_price):
            result = await _fetch_price(DAI, 18000000, ignore_pools=ignore_pools)
            assert result == 1.0
            mock_get_price.assert_called_once_with(
                DAI, 18000000, fail_to_None=True, sync=False, ignore_pools=ignore_pools
            )

    @pytest.mark.asyncio
    async def test_silent_forwarded(self, mock_y_module: None) -> None:
        """silent=True is forwarded to get_price."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(return_value=1.0)
        with patch("y.get_price", mock_get_price):
            result = await _fetch_price(DAI, 18000000, silent=True)
            assert result == 1.0
            mock_get_price.assert_called_once_with(
                DAI, 18000000, fail_to_None=True, sync=False, silent=True
            )

    @pytest.mark.asyncio
    async def test_all_new_params_combined(self, mock_y_module: None) -> None:
        """All new params are forwarded together."""
        from src.server import _fetch_price

        mock_get_price = AsyncMock(return_value=1.0)
        ignore_pools = (USDC,)
        with patch("y.get_price", mock_get_price):
            result = await _fetch_price(
                DAI,
                18000000,
                amount=1000.0,
                skip_cache=True,
                ignore_pools=ignore_pools,
                silent=True,
            )
            assert result == 1.0
            mock_get_price.assert_called_once_with(
                DAI,
                18000000,
                amount=1000.0,
                fail_to_None=True,
                sync=False,
                skip_cache=True,
                ignore_pools=ignore_pools,
                silent=True,
            )


class TestFetchBlockTimestamp:
    """Tests for _fetch_block_timestamp helper function."""

    @pytest.mark.asyncio
    async def test_returns_timestamp_on_success(self, mock_y_module: None) -> None:
        """On success, returns the Unix epoch timestamp."""
        from src.server import _fetch_block_timestamp

        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        with patch("y.get_block_timestamp_async", mock_get_block_timestamp):
            result = await _fetch_block_timestamp(18000000)
            assert result == 1700000000
            mock_get_block_timestamp.assert_called_once_with(18000000)

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self, mock_y_module: None) -> None:
        """On exception, returns None (error is logged but not raised)."""
        from src.server import _fetch_block_timestamp

        mock_get_block_timestamp = AsyncMock(side_effect=RuntimeError("RPC error"))
        with patch("y.get_block_timestamp_async", mock_get_block_timestamp):
            result = await _fetch_block_timestamp(18000000)
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_connection_error(self, mock_y_module: None) -> None:
        """ConnectionError is caught and returns None."""
        from src.server import _fetch_block_timestamp

        mock_get_block_timestamp = AsyncMock(side_effect=ConnectionError("Network error"))
        with patch("y.get_block_timestamp_async", mock_get_block_timestamp):
            result = await _fetch_block_timestamp(18000000)
            assert result is None


class TestHealthEndpoint:
    """Tests for the enhanced /health endpoint with node sync status."""

    @pytest.mark.asyncio
    async def test_synced_true_when_node_synced(self, mock_y_module: None) -> None:
        """When check_node_async succeeds, health returns synced=True."""
        from src.server import health

        mock_check_node_async = AsyncMock(return_value=None)
        mock_chain = type("MockChain", (), {"height": 18000000})()

        with (
            patch("y.time.check_node_async", mock_check_node_async),
            patch("brownie.chain", mock_chain),
        ):
            result = await health()
            assert result["status"] == "ok"
            assert result["chain"] == "ethereum"
            assert result["block"] == 18000000
            assert result["synced"] is True

    @pytest.mark.asyncio
    async def test_synced_false_when_node_not_synced(self, mock_y_module: None) -> None:
        """When check_node_async raises NodeNotSynced, health returns synced=False."""
        from src.server import health

        # Create a NodeNotSynced exception matching ypricemagic's name
        class NodeNotSynced(Exception):  # noqa: N818
            pass

        mock_check_node_async = AsyncMock(side_effect=NodeNotSynced("Node is behind"))
        mock_chain = type("MockChain", (), {"height": 18000000})()

        with (
            patch("y.time.check_node_async", mock_check_node_async),
            patch("brownie.chain", mock_chain),
        ):
            result = await health()
            assert result["status"] == "ok"
            assert result["synced"] is False

    @pytest.mark.asyncio
    async def test_synced_none_on_other_exception(self, mock_y_module: None) -> None:
        """When check_node_async raises unexpected exception, health returns synced=None."""
        from src.server import health

        mock_check_node_async = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        mock_chain = type("MockChain", (), {"height": 18000000})()

        with (
            patch("y.time.check_node_async", mock_check_node_async),
            patch("brownie.chain", mock_chain),
        ):
            result = await health()
            assert result["status"] == "ok"
            assert result["synced"] is None

    @pytest.mark.asyncio
    async def test_503_on_chain_height_failure(self, mock_y_module: None) -> None:
        """When chain.height fails, health returns 503 (existing behavior preserved)."""
        from fastapi.responses import JSONResponse

        from src.server import health

        mock_chain = type(
            "MockChain",
            (),
            {"height": property(lambda self: (_ for _ in ()).throw(ConnectionError("RPC failed")))},
        )()

        with patch("brownie.chain", mock_chain):
            result = await health()
            assert isinstance(result, JSONResponse)
            assert result.status_code == 503

    @pytest.mark.asyncio
    async def test_existing_fields_preserved(self, mock_y_module: None) -> None:
        """Health response retains status, chain, block fields. synced is additive."""
        from src.server import health

        mock_check_node_async = AsyncMock(return_value=None)
        mock_chain = type("MockChain", (), {"height": 18000000})()

        with (
            patch("y.time.check_node_async", mock_check_node_async),
            patch("brownie.chain", mock_chain),
        ):
            result = await health()
            # All required fields present
            assert "status" in result
            assert "chain" in result
            assert "block" in result
            assert "synced" in result
            # Values correct
            assert result["status"] == "ok"
            assert result["block"] == 18000000
            assert result["synced"] is True

    @pytest.mark.asyncio
    async def test_timeout_protection(self, mock_y_module: None) -> None:
        """check_node_async timeout doesn't hang health endpoint."""
        import asyncio

        from src.server import health

        async def slow_check() -> None:
            await asyncio.sleep(10)  # Would hang without timeout

        mock_check_node_async = AsyncMock(side_effect=slow_check)
        mock_chain = type("MockChain", (), {"height": 18000000})()

        with (
            patch("y.time.check_node_async", mock_check_node_async),
            patch("brownie.chain", mock_chain),
        ):
            # Should complete within reasonable time (timeout is 5s)
            result = await health()
            # Timeout should result in synced=None
            assert result["synced"] is None

    @pytest.mark.asyncio
    async def test_synced_check_only_after_height_success(self, mock_y_module: None) -> None:
        """synced check only runs if we can get block height (503 path unchanged)."""
        from fastapi.responses import JSONResponse

        from src.server import health

        # Simulate chain.height failing
        mock_chain = type(
            "MockChain",
            (),
            {"height": property(lambda self: (_ for _ in ()).throw(ConnectionError("RPC failed")))},
        )()
        mock_check_node_async = AsyncMock(return_value=None)

        with (
            patch("brownie.chain", mock_chain),
            patch("y.time.check_node_async", mock_check_node_async),
        ):
            result = await health()
            # Should return 503, not call check_node_async
            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
            # check_node_async should not have been called
            mock_check_node_async.assert_not_called()
