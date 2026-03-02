from src.params import (
    MAX_BLOCK,
    ParseError,
    ParseSuccess,
    is_valid_address,
    parse_bool_param,
    parse_ignore_pools,
    parse_price_params,
)

DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"


class TestIsValidAddress:
    def test_accepts_valid_checksummed(self) -> None:
        assert is_valid_address(DAI) is True

    def test_accepts_valid_lowercase(self) -> None:
        assert is_valid_address(DAI.lower()) is True

    def test_accepts_valid_uppercase(self) -> None:
        assert is_valid_address("0x6B175474E89094C44DA98B954EEDEAC495271D0F") is True

    def test_rejects_no_prefix(self) -> None:
        assert is_valid_address("6B175474E89094C44Da98b954EedeAC495271d0F") is False

    def test_rejects_short(self) -> None:
        assert is_valid_address("0x123") is False

    def test_rejects_long(self) -> None:
        assert is_valid_address("0x6B175474E89094C44Da98b954EedeAC495271d0F00") is False

    def test_rejects_invalid_chars(self) -> None:
        assert is_valid_address("0x6B175474E89094C44Da98b954EedeAC495271d0G") is False

    def test_rejects_empty(self) -> None:
        assert is_valid_address("") is False

    def test_rejects_symbol(self) -> None:
        assert is_valid_address("DAI") is False


class TestParsePriceParams:
    def test_valid_token_only(self) -> None:
        result = parse_price_params(DAI)
        assert isinstance(result, ParseSuccess)
        assert result.data.token == DAI
        assert result.data.block is None

    def test_valid_token_and_block(self) -> None:
        result = parse_price_params(DAI, "18000000")
        assert isinstance(result, ParseSuccess)
        assert result.data.token == DAI
        assert result.data.block == 18000000

    def test_missing_token(self) -> None:
        result = parse_price_params(None)
        assert isinstance(result, ParseError)
        assert "Missing required parameter" in result.error

    def test_empty_token(self) -> None:
        result = parse_price_params("")
        assert isinstance(result, ParseError)
        assert "Missing required parameter" in result.error

    def test_invalid_token_address(self) -> None:
        result = parse_price_params("DAI")
        assert isinstance(result, ParseError)
        assert "Invalid token address" in result.error

    def test_invalid_block_non_numeric(self) -> None:
        result = parse_price_params(DAI, "abc")
        assert isinstance(result, ParseError)
        assert "Invalid block number" in result.error

    def test_invalid_block_negative(self) -> None:
        result = parse_price_params(DAI, "-100")
        assert isinstance(result, ParseError)
        assert "Invalid block number" in result.error

    def test_invalid_block_zero(self) -> None:
        result = parse_price_params(DAI, "0")
        assert isinstance(result, ParseError)
        assert "Invalid block number" in result.error

    def test_valid_block_one(self) -> None:
        result = parse_price_params(DAI, "1")
        assert isinstance(result, ParseSuccess)
        assert result.data.block == 1

    def test_no_block_param(self) -> None:
        result = parse_price_params(USDC, None)
        assert isinstance(result, ParseSuccess)
        assert result.data.block is None

    def test_block_at_max(self) -> None:
        result = parse_price_params(DAI, str(MAX_BLOCK))
        assert isinstance(result, ParseSuccess)
        assert result.data.block == MAX_BLOCK

    def test_block_exceeds_max(self) -> None:
        result = parse_price_params(DAI, str(MAX_BLOCK + 1))
        assert isinstance(result, ParseError)
        assert "Invalid block number" in result.error

    def test_block_overflow(self) -> None:
        result = parse_price_params(DAI, "99999999999999999999999999999")
        assert isinstance(result, ParseError)
        assert "Invalid block number" in result.error


class TestParsePriceParamsAmount:
    def test_valid_amount(self) -> None:
        result = parse_price_params(DAI, "18000000", "1000")
        assert isinstance(result, ParseSuccess)
        assert result.data.amount == 1000.0

    def test_valid_amount_decimal(self) -> None:
        result = parse_price_params(DAI, "18000000", "0.5")
        assert isinstance(result, ParseSuccess)
        assert result.data.amount == 0.5

    def test_no_amount(self) -> None:
        result = parse_price_params(DAI, "18000000")
        assert isinstance(result, ParseSuccess)
        assert result.data.amount is None

    def test_none_amount(self) -> None:
        result = parse_price_params(DAI, "18000000", None)
        assert isinstance(result, ParseSuccess)
        assert result.data.amount is None

    def test_invalid_amount_non_numeric(self) -> None:
        result = parse_price_params(DAI, "18000000", "abc")
        assert isinstance(result, ParseError)
        assert "Invalid amount" in result.error

    def test_invalid_amount_zero(self) -> None:
        result = parse_price_params(DAI, "18000000", "0")
        assert isinstance(result, ParseError)
        assert "Invalid amount" in result.error

    def test_invalid_amount_negative(self) -> None:
        result = parse_price_params(DAI, "18000000", "-100")
        assert isinstance(result, ParseError)
        assert "Invalid amount" in result.error


class TestParseBoolParam:
    def test_accepts_true_lowercase(self) -> None:
        result = parse_bool_param("true", "skip_cache")
        assert result is True

    def test_accepts_true_uppercase(self) -> None:
        result = parse_bool_param("TRUE", "skip_cache")
        assert result is True

    def test_accepts_false_lowercase(self) -> None:
        result = parse_bool_param("false", "silent")
        assert result is False

    def test_accepts_false_uppercase(self) -> None:
        result = parse_bool_param("FALSE", "silent")
        assert result is False

    def test_accepts_1(self) -> None:
        result = parse_bool_param("1", "skip_cache")
        assert result is True

    def test_accepts_0(self) -> None:
        result = parse_bool_param("0", "silent")
        assert result is False

    def test_none_returns_none(self) -> None:
        """When param is not provided (None), returns None to indicate absent."""
        result = parse_bool_param(None, "skip_cache")
        assert result is None

    def test_empty_string_returns_none(self) -> None:
        """Empty string is treated as not provided."""
        result = parse_bool_param("", "skip_cache")
        assert result is None

    def test_rejects_maybe(self) -> None:
        result = parse_bool_param("maybe", "skip_cache")
        assert isinstance(result, ParseError)
        assert "skip_cache" in result.error
        assert "true" in result.error.lower() or "false" in result.error.lower()

    def test_rejects_2(self) -> None:
        result = parse_bool_param("2", "silent")
        assert isinstance(result, ParseError)
        assert "silent" in result.error

    def test_rejects_yes(self) -> None:
        result = parse_bool_param("yes", "skip_cache")
        assert isinstance(result, ParseError)

    def test_rejects_no(self) -> None:
        result = parse_bool_param("no", "silent")
        assert isinstance(result, ParseError)


class TestParseIgnorePools:
    def test_single_valid_address(self) -> None:
        result = parse_ignore_pools(DAI)
        assert result == (DAI,)

    def test_multiple_valid_addresses(self) -> None:
        result = parse_ignore_pools(f"{DAI},{USDC}")
        assert result == (DAI, USDC)

    def test_strips_whitespace(self) -> None:
        result = parse_ignore_pools(f"  {DAI} , {USDC}  ")
        assert result == (DAI, USDC)

    def test_empty_returns_empty_tuple(self) -> None:
        result = parse_ignore_pools("")
        assert result == ()

    def test_none_returns_empty_tuple(self) -> None:
        result = parse_ignore_pools(None)
        assert result == ()

    def test_consecutive_commas_dropped(self) -> None:
        """Empty segments from consecutive commas are silently dropped."""
        result = parse_ignore_pools(f"{DAI},,{USDC}")
        assert result == (DAI, USDC)

    def test_trailing_comma_dropped(self) -> None:
        result = parse_ignore_pools(f"{DAI},")
        assert result == (DAI,)

    def test_leading_comma_dropped(self) -> None:
        result = parse_ignore_pools(f",{DAI}")
        assert result == (DAI,)

    def test_whitespace_only_segments_dropped(self) -> None:
        result = parse_ignore_pools(f"{DAI},   ,{USDC}")
        assert result == (DAI, USDC)

    def test_invalid_address_returns_error(self) -> None:
        result = parse_ignore_pools("notanaddress")
        assert isinstance(result, ParseError)
        assert "notanaddress" in result.error

    def test_invalid_address_in_list_returns_error(self) -> None:
        result = parse_ignore_pools(f"{DAI},invalid,{USDC}")
        assert isinstance(result, ParseError)
        assert "invalid" in result.error

    def test_three_addresses(self) -> None:
        result = parse_ignore_pools(f"{DAI},{USDC},{WETH}")
        assert result == (DAI, USDC, WETH)


class TestParsePriceParamsNewFields:
    def test_skip_cache_true(self) -> None:
        result = parse_price_params(DAI, "18000000", None, skip_cache="true")
        assert isinstance(result, ParseSuccess)
        assert result.data.skip_cache is True

    def test_skip_cache_false(self) -> None:
        result = parse_price_params(DAI, "18000000", None, skip_cache="false")
        assert isinstance(result, ParseSuccess)
        assert result.data.skip_cache is False

    def test_skip_cache_default_false(self) -> None:
        result = parse_price_params(DAI, "18000000")
        assert isinstance(result, ParseSuccess)
        assert result.data.skip_cache is False

    def test_skip_cache_invalid(self) -> None:
        result = parse_price_params(DAI, "18000000", None, skip_cache="maybe")
        assert isinstance(result, ParseError)
        assert "skip_cache" in result.error

    def test_silent_true(self) -> None:
        result = parse_price_params(DAI, "18000000", None, silent="true")
        assert isinstance(result, ParseSuccess)
        assert result.data.silent is True

    def test_silent_default_false(self) -> None:
        result = parse_price_params(DAI, "18000000")
        assert isinstance(result, ParseSuccess)
        assert result.data.silent is False

    def test_silent_invalid(self) -> None:
        result = parse_price_params(DAI, "18000000", None, silent="2")
        assert isinstance(result, ParseError)
        assert "silent" in result.error

    def test_ignore_pools_single(self) -> None:
        result = parse_price_params(DAI, "18000000", None, ignore_pools=USDC)
        assert isinstance(result, ParseSuccess)
        assert result.data.ignore_pools == (USDC,)

    def test_ignore_pools_multiple(self) -> None:
        result = parse_price_params(DAI, "18000000", None, ignore_pools=f"{USDC},{WETH}")
        assert isinstance(result, ParseSuccess)
        assert result.data.ignore_pools == (USDC, WETH)

    def test_ignore_pools_default_empty(self) -> None:
        result = parse_price_params(DAI, "18000000")
        assert isinstance(result, ParseSuccess)
        assert result.data.ignore_pools == ()

    def test_ignore_pools_invalid_address(self) -> None:
        result = parse_price_params(DAI, "18000000", None, ignore_pools="notanaddress")
        assert isinstance(result, ParseError)
        assert "notanaddress" in result.error

    def test_ignore_pools_empty_string(self) -> None:
        result = parse_price_params(DAI, "18000000", None, ignore_pools="")
        assert isinstance(result, ParseSuccess)
        assert result.data.ignore_pools == ()

    def test_all_new_params_combined(self) -> None:
        result = parse_price_params(
            DAI, "18000000", "1000", skip_cache="true", silent="1", ignore_pools=f"{USDC},{WETH}"
        )
        assert isinstance(result, ParseSuccess)
        assert result.data.token == DAI
        assert result.data.block == 18000000
        assert result.data.amount == 1000.0
        assert result.data.skip_cache is True
        assert result.data.silent is True
        assert result.data.ignore_pools == (USDC, WETH)

    def test_backwards_compat_no_new_params(self) -> None:
        """Omitting new params preserves existing behavior exactly."""
        result = parse_price_params(DAI, "18000000", "1000")
        assert isinstance(result, ParseSuccess)
        assert result.data.token == DAI
        assert result.data.block == 18000000
        assert result.data.amount == 1000.0
        # New fields have defaults
        assert result.data.skip_cache is False
        assert result.data.silent is False
        assert result.data.ignore_pools == ()
