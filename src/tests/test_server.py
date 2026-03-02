"""Tests for server._fetch_price behavior."""

from unittest.mock import AsyncMock, patch

import pytest

DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"


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
