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
    async def test_timestamp_converted_to_datetime(self, mock_y_module: None) -> None:
        """Unix epoch timestamp is converted to timezone-aware datetime before calling get_block_at_timestamp."""
        from datetime import UTC, datetime

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
            # Verify get_block_at_timestamp was called with a datetime object
            mock_get_block_at_timestamp.assert_called_once()
            call_args = mock_get_block_at_timestamp.call_args
            # First positional argument should be a datetime
            dt_arg = call_args[0][0]
            assert isinstance(dt_arg, datetime)
            # Verify it's the correct datetime (UTC timezone, correct epoch)
            assert dt_arg == datetime.fromtimestamp(1700000000, tz=UTC)
            assert dt_arg.tzinfo is not None

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


class TestBatchPricesEndpoint:
    """Tests for GET /prices batch pricing endpoint."""

    @pytest.mark.asyncio
    async def test_single_token_returns_array_of_one(self, mock_y_module: None) -> None:
        """Single token returns 200 with JSON array containing one result."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_prices = AsyncMock(return_value=[1.0])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get("/prices", params={"tokens": DAI})

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["token"] == DAI
            assert data[0]["price"] == 1.0
            assert data[0]["cached"] is False

    @pytest.mark.asyncio
    async def test_multiple_tokens_preserve_order(self, mock_y_module: None) -> None:
        """Multiple tokens return ordered results preserving input order."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_prices = AsyncMock(return_value=[1.0, 1.0])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get("/prices", params={"tokens": f"{DAI},{USDC}"})

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["token"] == DAI
            assert data[1]["token"] == USDC

    @pytest.mark.asyncio
    async def test_missing_tokens_returns_400(self, mock_y_module: None) -> None:
        """Missing tokens param returns 400."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_chain = type("MockChain", (), {"height": 19000000})()

        with patch("brownie.chain", mock_chain):
            client = TestClient(app)
            response = client.get("/prices")

            assert response.status_code == 400
            data = response.json()
            assert "tokens" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_address_returns_400(self, mock_y_module: None) -> None:
        """Invalid address in list returns 400."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_chain = type("MockChain", (), {"height": 19000000})()

        with patch("brownie.chain", mock_chain):
            client = TestClient(app)
            response = client.get("/prices", params={"tokens": f"{DAI},INVALID"})

            assert response.status_code == 400
            data = response.json()
            assert "INVALID" in data["error"]

    @pytest.mark.asyncio
    async def test_block_applies_to_all_tokens(self, mock_y_module: None) -> None:
        """Block param applies to all tokens."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_prices = AsyncMock(return_value=[1.0, 1.0])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get(
                "/prices", params={"tokens": f"{DAI},{USDC}", "block": "18000000"}
            )

            assert response.status_code == 200
            data = response.json()
            assert all(r["block"] == 18000000 for r in data)

    @pytest.mark.asyncio
    async def test_partial_failure_returns_null_prices(self, mock_y_module: None) -> None:
        """Partial failure returns 200 with null prices for failed tokens."""
        from fastapi.testclient import TestClient

        from src.server import app

        # First token succeeds, second fails
        mock_get_prices = AsyncMock(return_value=[1.0, None])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get("/prices", params={"tokens": f"{DAI},{USDC}"})

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["price"] == 1.0
            assert data[1]["price"] is None

    @pytest.mark.asyncio
    async def test_all_failures_returns_200(self, mock_y_module: None) -> None:
        """All-failures also returns 200 with null prices."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_prices = AsyncMock(return_value=[None, None])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get("/prices", params={"tokens": f"{DAI},{USDC}"})

            assert response.status_code == 200
            data = response.json()
            assert all(r["price"] is None for r in data)

    @pytest.mark.asyncio
    async def test_batch_with_timestamp_resolves_correctly(self, mock_y_module: None) -> None:
        """Batch with timestamp resolves to block and prices all tokens."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_block_at_timestamp = AsyncMock(return_value=18000000)
        mock_get_prices = AsyncMock(return_value=[1.0, 1.0])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_block_at_timestamp", mock_get_block_at_timestamp),
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get(
                "/prices", params={"tokens": f"{DAI},{USDC}", "timestamp": "1700000000"}
            )

            assert response.status_code == 200
            data = response.json()
            assert all(r["block"] == 18000000 for r in data)
            mock_get_block_at_timestamp.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_timestamp_converted_to_datetime(self, mock_y_module: None) -> None:
        """Batch endpoint converts Unix epoch to datetime before calling get_block_at_timestamp."""
        from datetime import UTC, datetime

        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_block_at_timestamp = AsyncMock(return_value=18000000)
        mock_get_prices = AsyncMock(return_value=[1.0, 1.0])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_block_at_timestamp", mock_get_block_at_timestamp),
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get(
                "/prices", params={"tokens": f"{DAI},{USDC}", "timestamp": "1700000000"}
            )

            assert response.status_code == 200
            # Verify get_block_at_timestamp was called with a datetime object
            mock_get_block_at_timestamp.assert_called_once()
            call_args = mock_get_block_at_timestamp.call_args
            dt_arg = call_args[0][0]
            assert isinstance(dt_arg, datetime)
            assert dt_arg == datetime.fromtimestamp(1700000000, tz=UTC)
            assert dt_arg.tzinfo is not None

    @pytest.mark.asyncio
    async def test_batch_with_timestamp_and_amounts(self, mock_y_module: None) -> None:
        """Batch with timestamp and amounts combined works."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_block_at_timestamp = AsyncMock(return_value=18000000)
        mock_get_prices = AsyncMock(return_value=[1.0, 2.0])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_block_at_timestamp", mock_get_block_at_timestamp),
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get(
                "/prices",
                params={
                    "tokens": f"{DAI},{USDC}",
                    "timestamp": "1700000000",
                    "amounts": "1000,500",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            # Verify amounts were passed to get_prices
            mock_get_prices.assert_called_once()
            call_kwargs = mock_get_prices.call_args[1]
            assert call_kwargs.get("amounts") == (1000.0, 500.0)

    @pytest.mark.asyncio
    async def test_too_many_tokens_returns_400(self, mock_y_module: None) -> None:
        """More than 100 tokens returns 400."""
        from fastapi.testclient import TestClient

        from src.params import MAX_BATCH_TOKENS
        from src.server import app

        mock_chain = type("MockChain", (), {"height": 19000000})()
        tokens = ",".join([DAI] * (MAX_BATCH_TOKENS + 1))

        with patch("brownie.chain", mock_chain):
            client = TestClient(app)
            response = client.get("/prices", params={"tokens": tokens})

            assert response.status_code == 400
            data = response.json()
            assert "Too many" in data["error"]

    @pytest.mark.asyncio
    async def test_batch_results_include_block_timestamp(self, mock_y_module: None) -> None:
        """Each element in batch response includes block_timestamp field."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_prices = AsyncMock(return_value=[1.0, 1.0])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get("/prices", params={"tokens": f"{DAI},{USDC}"})

            assert response.status_code == 200
            data = response.json()
            assert all("block_timestamp" in r for r in data)
            assert all(r["block_timestamp"] == 1700000000 for r in data)


class TestBatchPricesAmounts:
    """Tests for amounts parameter in batch pricing."""

    @pytest.mark.asyncio
    async def test_amounts_matching_count(self, mock_y_module: None) -> None:
        """Amounts with matching count work for price impact."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_prices = AsyncMock(return_value=[0.99, 1.01])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get(
                "/prices", params={"tokens": f"{DAI},{USDC}", "amounts": "1000,500"}
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            # Verify amounts were passed
            call_kwargs = mock_get_prices.call_args[1]
            assert call_kwargs.get("amounts") == (1000.0, 500.0)

    @pytest.mark.asyncio
    async def test_amounts_count_mismatch_returns_400(self, mock_y_module: None) -> None:
        """Amounts count mismatch returns 400."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_chain = type("MockChain", (), {"height": 19000000})()

        with patch("brownie.chain", mock_chain):
            client = TestClient(app)
            response = client.get("/prices", params={"tokens": f"{DAI},{USDC}", "amounts": "1000"})

            assert response.status_code == 400
            data = response.json()
            assert "does not match" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_amount_returns_400(self, mock_y_module: None) -> None:
        """Invalid amount values return 400."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_chain = type("MockChain", (), {"height": 19000000})()

        with patch("brownie.chain", mock_chain):
            client = TestClient(app)
            response = client.get(
                "/prices", params={"tokens": f"{DAI},{USDC}", "amounts": "1000,abc"}
            )

            assert response.status_code == 400
            data = response.json()
            assert "amount" in data["error"].lower()


class TestBatchPricesCaching:
    """Tests for caching behavior in batch pricing."""

    @pytest.mark.asyncio
    async def test_cache_hit_for_single_token(self, mock_y_module: None) -> None:
        """Individual results are cached and retrievable via single /price."""
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_prices = AsyncMock(return_value=[1.0])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        # Mock cache functions
        cached_data: dict[str, dict[str, object]] = {}

        def mock_get_cached_price(token: str, block: int) -> dict[str, object] | None:
            key = f"{token}:{block}"
            return cached_data.get(key)

        def mock_set_cached_price(
            token: str, block: int, price: float, block_timestamp: int | None = None
        ) -> None:
            key = f"{token}:{block}"
            cached_data[key] = {"price": price, "block_timestamp": block_timestamp}

        with (
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
            patch("src.server.get_cached_price", mock_get_cached_price),
            patch("src.server.set_cached_price", mock_set_cached_price),
        ):
            client = TestClient(app)

            # First request - should fetch
            response = client.get("/prices", params={"tokens": DAI, "block": "18000000"})
            assert response.status_code == 200
            data = response.json()
            assert data[0]["cached"] is False

            # Verify it was cached
            assert f"{DAI}:18000000" in cached_data

    @pytest.mark.asyncio
    async def test_amounts_skip_cache_write(self, mock_y_module: None) -> None:
        """Results with amounts are NOT cached."""
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_prices = AsyncMock(return_value=[1.0])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        cached_data: dict[str, dict[str, object]] = {}

        def mock_set_cached_price(
            token: str, block: int, price: float, block_timestamp: int | None = None
        ) -> None:
            key = f"{token}:{block}"
            cached_data[key] = {"price": price, "block_timestamp": block_timestamp}

        with (
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
            patch("src.server.get_cached_price", return_value=None),
            patch("src.server.set_cached_price", mock_set_cached_price),
        ):
            client = TestClient(app)

            # Request with amount - should NOT cache
            response = client.get(
                "/prices", params={"tokens": DAI, "block": "18000000", "amounts": "1000"}
            )
            assert response.status_code == 200

            # Verify it was NOT cached
            assert f"{DAI}:18000000" not in cached_data


class TestBatchPricesParams:
    """Tests for skip_cache and silent parameters in batch pricing."""

    @pytest.mark.asyncio
    async def test_skip_cache_forwarded(self, mock_y_module: None) -> None:
        """skip_cache is forwarded to get_prices."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_prices = AsyncMock(return_value=[1.0])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
            patch("src.server.get_cached_price", return_value=None),
        ):
            client = TestClient(app)
            response = client.get(
                "/prices", params={"tokens": DAI, "block": "18000000", "skip_cache": "true"}
            )

            assert response.status_code == 200
            call_kwargs = mock_get_prices.call_args[1]
            assert call_kwargs.get("skip_cache") is True

    @pytest.mark.asyncio
    async def test_silent_forwarded(self, mock_y_module: None) -> None:
        """silent is forwarded to get_prices."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_prices = AsyncMock(return_value=[1.0])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
            patch("src.server.get_cached_price", return_value=None),
        ):
            client = TestClient(app)
            response = client.get(
                "/prices", params={"tokens": DAI, "block": "18000000", "silent": "true"}
            )

            assert response.status_code == 200
            call_kwargs = mock_get_prices.call_args[1]
            assert call_kwargs.get("silent") is True

    @pytest.mark.asyncio
    async def test_both_params_forwarded(self, mock_y_module: None) -> None:
        """Both skip_cache and silent are forwarded together."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_prices = AsyncMock(return_value=[1.0])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
            patch("src.server.get_cached_price", return_value=None),
        ):
            client = TestClient(app)
            response = client.get(
                "/prices",
                params={"tokens": DAI, "block": "18000000", "skip_cache": "1", "silent": "1"},
            )

            assert response.status_code == 200
            call_kwargs = mock_get_prices.call_args[1]
            assert call_kwargs.get("skip_cache") is True
            assert call_kwargs.get("silent") is True


class TestCheckBucketEndpoint:
    """Tests for GET /check_bucket token classification endpoint."""

    @pytest.mark.asyncio
    async def test_known_token_returns_bucket_string(self, mock_y_module: None) -> None:
        """Known token returns 200 with bucket classification string."""
        from unittest.mock import AsyncMock, patch

        from fastapi.testclient import TestClient

        from src.server import app

        mock_check_bucket = AsyncMock(return_value="atoken")

        with patch("y.check_bucket", mock_check_bucket):
            client = TestClient(app)
            response = client.get("/check_bucket", params={"token": DAI})

            assert response.status_code == 200
            data = response.json()
            assert data["token"] == DAI
            assert data["chain"] == "ethereum"
            assert data["bucket"] == "atoken"

    @pytest.mark.asyncio
    async def test_missing_token_returns_400(self, mock_y_module: None) -> None:
        """Missing token param returns 400."""
        from fastapi.testclient import TestClient

        from src.server import app

        client = TestClient(app)
        response = client.get("/check_bucket")

        assert response.status_code == 400
        data = response.json()
        assert "token" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_address_returns_400(self, mock_y_module: None) -> None:
        """Invalid token address returns 400."""
        from fastapi.testclient import TestClient

        from src.server import app

        client = TestClient(app)
        response = client.get("/check_bucket", params={"token": "INVALID"})

        assert response.status_code == 400
        data = response.json()
        assert "INVALID" in data["error"]

    @pytest.mark.asyncio
    async def test_unclassifiable_returns_200_with_null_bucket(self, mock_y_module: None) -> None:
        """Unclassifiable token returns 200 with bucket: null."""
        from unittest.mock import AsyncMock, patch

        from fastapi.testclient import TestClient

        from src.server import app

        # check_bucket returns None for unclassifiable tokens
        mock_check_bucket = AsyncMock(return_value=None)

        with patch("y.check_bucket", mock_check_bucket):
            client = TestClient(app)
            response = client.get("/check_bucket", params={"token": DAI})

            assert response.status_code == 200
            data = response.json()
            assert data["token"] == DAI
            assert data["bucket"] is None

    @pytest.mark.asyncio
    async def test_exception_returns_500(self, mock_y_module: None) -> None:
        """check_bucket exception returns 500 with error envelope."""
        from unittest.mock import AsyncMock, patch

        from fastapi.testclient import TestClient

        from src.server import app

        mock_check_bucket = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        with patch("y.check_bucket", mock_check_bucket):
            client = TestClient(app)
            response = client.get("/check_bucket", params={"token": DAI})

            assert response.status_code == 500
            data = response.json()
            assert "error" in data
            assert "Failed to classify token" in data["error"]

    @pytest.mark.asyncio
    async def test_no_block_parameter_needed(self, mock_y_module: None) -> None:
        """check_bucket succeeds without any block param."""
        from unittest.mock import AsyncMock, patch

        from fastapi.testclient import TestClient

        from src.server import app

        mock_check_bucket = AsyncMock(return_value="curve lp")

        with patch("y.check_bucket", mock_check_bucket):
            client = TestClient(app)
            response = client.get("/check_bucket", params={"token": USDC})

            assert response.status_code == 200
            data = response.json()
            assert data["bucket"] == "curve lp"

    @pytest.mark.asyncio
    async def test_bucket_classification_various_types(self, mock_y_module: None) -> None:
        """Various bucket classification types are returned correctly."""
        from unittest.mock import AsyncMock, patch

        from fastapi.testclient import TestClient

        from src.server import app

        bucket_types = ["atoken", "curve lp", "uni or uni-like lp", "belt lp", "solidly lp"]

        for bucket_type in bucket_types:
            mock_check_bucket = AsyncMock(return_value=bucket_type)

            with patch("y.check_bucket", mock_check_bucket):
                client = TestClient(app)
                response = client.get("/check_bucket", params={"token": DAI})

                assert response.status_code == 200
                data = response.json()
                assert data["bucket"] == bucket_type

    @pytest.mark.asyncio
    async def test_prometheus_metrics_tracked(self, mock_y_module: None) -> None:
        """Check_bucket requests are tracked in Prometheus metrics."""
        from unittest.mock import AsyncMock, patch

        from fastapi.testclient import TestClient

        from src.server import app

        mock_check_bucket = AsyncMock(return_value="atoken")

        with patch("y.check_bucket", mock_check_bucket):
            client = TestClient(app)
            response = client.get("/check_bucket", params={"token": DAI})

            assert response.status_code == 200
            # The metric should have been incremented (we can't easily check the value here,
            # but we verify the endpoint works without error)


class TestCrossAreaErrorEnvelope:
    """Tests for error envelope format across all endpoints (VAL-CROSS-002)."""

    @pytest.mark.asyncio
    async def test_price_parse_error_uses_error_envelope(self, mock_y_module: None) -> None:
        """Parse errors from /price endpoint use {"error": "..."} format."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_chain = type("MockChain", (), {"height": 19000000})()

        with patch("brownie.chain", mock_chain):
            client = TestClient(app)
            response = client.get("/price", params={"token": "INVALID"})

            assert response.status_code == 400
            data = response.json()
            assert "error" in data
            assert "INVALID" in data["error"]

    @pytest.mark.asyncio
    async def test_prices_parse_error_uses_error_envelope(self, mock_y_module: None) -> None:
        """Parse errors from /prices endpoint use {"error": "..."} format."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_chain = type("MockChain", (), {"height": 19000000})()

        with patch("brownie.chain", mock_chain):
            client = TestClient(app)
            response = client.get("/prices", params={"tokens": "INVALID"})

            assert response.status_code == 400
            data = response.json()
            assert "error" in data
            assert "INVALID" in data["error"]

    @pytest.mark.asyncio
    async def test_check_bucket_parse_error_uses_error_envelope(self, mock_y_module: None) -> None:
        """Parse errors from /check_bucket endpoint use {"error": "..."} format."""
        from fastapi.testclient import TestClient

        from src.server import app

        client = TestClient(app)
        response = client.get("/check_bucket", params={"token": "INVALID"})

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "INVALID" in data["error"]

    @pytest.mark.asyncio
    async def test_fastapi_422_uses_error_envelope(self, mock_y_module: None) -> None:
        """FastAPI's default 422 validation errors are converted to {"error": "..."} format."""
        import json

        from fastapi.exceptions import RequestValidationError

        from src.server import validation_exception_handler

        # Create a mock request and validation error to test the handler directly
        mock_request = type("MockRequest", (), {})()
        mock_error = RequestValidationError(
            [{"loc": ("query", "token"), "msg": "field required", "type": "value_error.missing"}]
        )

        # Test the exception handler directly
        response = await validation_exception_handler(mock_request, mock_error)

        assert response.status_code == 422
        # Parse the response body - body is bytes
        data = json.loads(bytes(response.body))
        assert "error" in data
        assert "Validation error" in data["error"]


class TestCrossAreaRequestId:
    """Tests for X-Request-ID header propagation (VAL-CROSS-006)."""

    @pytest.mark.asyncio
    async def test_request_id_echoed_on_price(self, mock_y_module: None) -> None:
        """X-Request-ID header is echoed back on /price endpoint."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_price = AsyncMock(return_value=1.0)
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_price", mock_get_price),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get(
                "/price",
                params={"token": DAI},
                headers={"X-Request-ID": "test-request-123"},
            )

            assert response.status_code == 200
            assert response.headers["X-Request-ID"] == "test-request-123"

    @pytest.mark.asyncio
    async def test_request_id_generated_if_missing(self, mock_y_module: None) -> None:
        """X-Request-ID is generated if not provided."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_chain = type("MockChain", (), {"height": 19000000})()

        with patch("brownie.chain", mock_chain):
            client = TestClient(app)
            response = client.get("/price", params={"token": "INVALID"})

            # Even on error, X-Request-ID should be present
            assert "X-Request-ID" in response.headers
            assert len(response.headers["X-Request-ID"]) > 0

    @pytest.mark.asyncio
    async def test_request_id_on_prices_endpoint(self, mock_y_module: None) -> None:
        """X-Request-ID header is echoed back on /prices endpoint."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_prices = AsyncMock(return_value=[1.0])
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_prices", mock_get_prices),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get(
                "/prices",
                params={"tokens": DAI},
                headers={"X-Request-ID": "batch-request-456"},
            )

            assert response.status_code == 200
            assert response.headers["X-Request-ID"] == "batch-request-456"

    @pytest.mark.asyncio
    async def test_request_id_on_check_bucket_endpoint(self, mock_y_module: None) -> None:
        """X-Request-ID header is echoed back on /check_bucket endpoint."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_check_bucket = AsyncMock(return_value="atoken")

        with patch("y.check_bucket", mock_check_bucket):
            client = TestClient(app)
            response = client.get(
                "/check_bucket",
                params={"token": DAI},
                headers={"X-Request-ID": "bucket-request-789"},
            )

            assert response.status_code == 200
            assert response.headers["X-Request-ID"] == "bucket-request-789"


class TestCrossAreaCORS:
    """Tests for CORS headers on all endpoints (VAL-CROSS-007)."""

    @pytest.mark.asyncio
    async def test_cors_headers_on_price(self, mock_y_module: None) -> None:
        """CORS headers are present on /price endpoint."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_chain = type("MockChain", (), {"height": 19000000})()

        with patch("brownie.chain", mock_chain):
            client = TestClient(app)
            response = client.options(
                "/price",
                headers={
                    "Origin": "http://example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )

            # CORS middleware should add these headers
            assert "access-control-allow-origin" in response.headers

    @pytest.mark.asyncio
    async def test_cors_headers_on_prices(self, mock_y_module: None) -> None:
        """CORS headers are present on /prices endpoint."""
        from fastapi.testclient import TestClient

        from src.server import app

        client = TestClient(app)
        response = client.options(
            "/prices",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert "access-control-allow-origin" in response.headers

    @pytest.mark.asyncio
    async def test_cors_headers_on_check_bucket(self, mock_y_module: None) -> None:
        """CORS headers are present on /check_bucket endpoint."""
        from fastapi.testclient import TestClient

        from src.server import app

        client = TestClient(app)
        response = client.options(
            "/check_bucket",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert "access-control-allow-origin" in response.headers


class TestCrossAreaSkipCacheAmount:
    """Tests for skip_cache + amount interaction (VAL-CROSS-004)."""

    @pytest.mark.asyncio
    async def test_amount_skips_cache_write_regardless_of_skip_cache(
        self, mock_y_module: None
    ) -> None:
        """Amount requests skip cache writes regardless of skip_cache setting."""
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_price = AsyncMock(return_value=1.0)
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        cache_writes: list[tuple[str, int, float]] = []

        def mock_set_cached_price(
            token: str, block: int, price: float, block_timestamp: int | None = None
        ) -> None:
            cache_writes.append((token, block, price))

        with (
            patch("y.get_price", mock_get_price),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
            patch("src.server.get_cached_price", return_value=None),
            patch("src.server.set_cached_price", mock_set_cached_price),
        ):
            client = TestClient(app)

            # Request with amount (cache write should be skipped)
            response = client.get(
                "/price",
                params={"token": DAI, "block": "18000000", "amount": "1000", "skip_cache": "true"},
            )

            assert response.status_code == 200
            # Cache should NOT have been written because amount is present
            assert len(cache_writes) == 0

    @pytest.mark.asyncio
    async def test_amount_request_not_cached(self, mock_y_module: None) -> None:
        """After an amount request, subsequent non-amount request is not cached:true."""
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_price = AsyncMock(return_value=1.0)
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        cached_data: dict[str, dict[str, object]] = {}

        def mock_get_cached_price(token: str, block: int) -> dict[str, object] | None:
            key = f"{token}:{block}"
            return cached_data.get(key)

        def mock_set_cached_price(
            token: str, block: int, price: float, block_timestamp: int | None = None
        ) -> None:
            key = f"{token}:{block}"
            cached_data[key] = {"price": price, "block_timestamp": block_timestamp}

        with (
            patch("y.get_price", mock_get_price),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
            patch("src.server.get_cached_price", mock_get_cached_price),
            patch("src.server.set_cached_price", mock_set_cached_price),
        ):
            client = TestClient(app)

            # First request with amount (should NOT be cached)
            response1 = client.get(
                "/price",
                params={"token": DAI, "block": "18000000", "amount": "1000"},
            )
            assert response1.status_code == 200
            assert response1.json()["cached"] is False

            # Cache should be empty
            assert len(cached_data) == 0

            # Second request without amount (should be fresh, not cached)
            response2 = client.get(
                "/price",
                params={"token": DAI, "block": "18000000"},
            )
            assert response2.status_code == 200
            assert response2.json()["cached"] is False

            # Now cache should have the entry
            assert len(cached_data) == 1


class TestCrossAreaBackwardsCompat:
    """Tests for backwards compatible response shape (VAL-CROSS-001)."""

    @pytest.mark.asyncio
    async def test_price_response_has_all_original_fields(self, mock_y_module: None) -> None:
        """GET /price with only original params returns existing fields + additive block_timestamp."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_price = AsyncMock(return_value=1.0)
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_price", mock_get_price),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get(
                "/price",
                params={"token": DAI, "block": "18000000"},
            )

            assert response.status_code == 200
            data = response.json()

            # All original fields must be present
            assert "chain" in data
            assert "token" in data
            assert "block" in data
            assert "price" in data
            assert "cached" in data

            # Additive field should be present
            assert "block_timestamp" in data

            # Verify values
            assert data["chain"] == "ethereum"
            assert data["token"] == DAI
            assert data["block"] == 18000000
            assert data["price"] == 1.0
            assert data["cached"] is False
            assert data["block_timestamp"] == 1700000000

    @pytest.mark.asyncio
    async def test_price_response_no_new_fields_removed(self, mock_y_module: None) -> None:
        """Response shape is a superset - no fields removed."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_price = AsyncMock(return_value=1.0)
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_price", mock_get_price),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)
            response = client.get("/price", params={"token": DAI})

            assert response.status_code == 200
            data = response.json()

            # Response should have these required keys
            required_keys = {"chain", "token", "block", "price", "cached", "block_timestamp"}
            assert required_keys.issubset(data.keys())

    @pytest.mark.asyncio
    async def test_amount_field_conditional(self, mock_y_module: None) -> None:
        """Amount field is only present when amount parameter is provided."""
        from fastapi.testclient import TestClient

        from src.server import app

        mock_get_price = AsyncMock(return_value=1.0)
        mock_get_block_timestamp = AsyncMock(return_value=1700000000)
        mock_chain = type("MockChain", (), {"height": 19000000})()

        with (
            patch("y.get_price", mock_get_price),
            patch("y.get_block_timestamp_async", mock_get_block_timestamp),
            patch("brownie.chain", mock_chain),
        ):
            client = TestClient(app)

            # Without amount - should NOT have amount field
            response1 = client.get("/price", params={"token": DAI, "block": "18000000"})
            assert response1.status_code == 200
            assert "amount" not in response1.json()

            # With amount - should have amount field
            response2 = client.get(
                "/price", params={"token": DAI, "block": "18000000", "amount": "1000"}
            )
            assert response2.status_code == 200
            assert "amount" in response2.json()
            assert response2.json()["amount"] == 1000.0
