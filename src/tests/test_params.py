from src.params import (
    MAX_BATCH_TOKENS,
    MAX_BLOCK,
    BatchParseSuccess,
    ParseError,
    ParseSuccess,
    QuoteParseSuccess,
    is_valid_address,
    parse_batch_params,
    parse_bool_param,
    parse_ignore_pools,
    parse_price_params,
    parse_quote_params,
    parse_timestamp,
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


class TestParseTimestamp:
    """Tests for parse_timestamp function."""

    def test_valid_unix_epoch_integer(self) -> None:
        """Unix epoch as integer string is accepted."""
        result = parse_timestamp("1700000000")
        assert isinstance(result, int)
        assert result == 1700000000

    def test_valid_unix_epoch_float(self) -> None:
        """Unix epoch as float string is accepted (decimal part discarded)."""
        result = parse_timestamp("1700000000.123")
        assert isinstance(result, int)
        assert result == 1700000000

    def test_valid_iso8601_with_z(self) -> None:
        """ISO 8601 with Z suffix is accepted."""
        result = parse_timestamp("2023-11-14T22:13:20Z")
        assert isinstance(result, int)
        # 2023-11-14T22:13:20Z = 1700000000
        assert result == 1700000000

    def test_valid_iso8601_with_plus_offset(self) -> None:
        """ISO 8601 with +00:00 offset is accepted."""
        result = parse_timestamp("2023-11-14T22:13:20+00:00")
        assert isinstance(result, int)
        assert result == 1700000000

    def test_invalid_format(self) -> None:
        """Invalid format returns ParseError."""
        result = parse_timestamp("not-a-timestamp")
        assert isinstance(result, ParseError)
        assert "timestamp" in result.error.lower()

    def test_negative_timestamp(self) -> None:
        """Negative timestamp returns ParseError."""
        result = parse_timestamp("-100")
        assert isinstance(result, ParseError)
        assert "negative" in result.error.lower()

    def test_zero_timestamp(self) -> None:
        """Zero timestamp returns ParseError."""
        result = parse_timestamp("0")
        assert isinstance(result, ParseError)
        assert "zero" in result.error.lower() or "positive" in result.error.lower()

    def test_future_timestamp(self) -> None:
        """Future timestamp (far in the future) returns ParseError."""
        result = parse_timestamp("9999999999")
        assert isinstance(result, ParseError)
        assert "future" in result.error.lower()

    def test_none_returns_none(self) -> None:
        """None input returns None (parameter not provided)."""
        result = parse_timestamp(None)
        assert result is None

    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None (parameter not provided)."""
        result = parse_timestamp("")
        assert result is None

    def test_iso8601_with_timezone_name(self) -> None:
        """ISO 8601 with timezone name (like UTC) is not accepted."""
        result = parse_timestamp("2023-11-14T22:13:20 UTC")
        assert isinstance(result, ParseError)


class TestParsePriceParamsTimestamp:
    """Tests for timestamp parameter in parse_price_params."""

    def test_timestamp_without_block(self) -> None:
        """Timestamp without block is accepted."""
        result = parse_price_params(DAI, None, None, None, None, None, "1700000000")
        assert isinstance(result, ParseSuccess)
        assert result.data.timestamp == 1700000000
        assert result.data.block is None

    def test_timestamp_and_block_mutually_exclusive(self) -> None:
        """Both timestamp and block returns ParseError."""
        result = parse_price_params(DAI, "18000000", None, None, None, None, "1700000000")
        assert isinstance(result, ParseError)
        assert "mutually exclusive" in result.error.lower()

    def test_timestamp_invalid_format(self) -> None:
        """Invalid timestamp format returns ParseError."""
        result = parse_price_params(DAI, None, None, None, None, None, "invalid")
        assert isinstance(result, ParseError)
        assert "timestamp" in result.error.lower()

    def test_timestamp_future(self) -> None:
        """Future timestamp returns ParseError."""
        result = parse_price_params(DAI, None, None, None, None, None, "9999999999")
        assert isinstance(result, ParseError)
        assert "future" in result.error.lower()

    def test_timestamp_with_other_params(self) -> None:
        """Timestamp works with other params like amount, skip_cache, etc."""
        result = parse_price_params(DAI, None, "1000", "true", None, "true", "1700000000")
        assert isinstance(result, ParseSuccess)
        assert result.data.timestamp == 1700000000
        assert result.data.amount == 1000.0
        assert result.data.skip_cache is True
        assert result.data.silent is True

    def test_no_timestamp_no_block(self) -> None:
        """Omitting both timestamp and block is valid (uses latest block)."""
        result = parse_price_params(DAI)
        assert isinstance(result, ParseSuccess)
        assert result.data.timestamp is None
        assert result.data.block is None


class TestParseBatchParams:
    """Tests for parse_batch_params function."""

    def test_single_token(self) -> None:
        """Single token returns tuple of one."""
        result = parse_batch_params(DAI)
        assert isinstance(result, BatchParseSuccess)
        assert result.data.tokens == (DAI,)
        assert result.data.block is None

    def test_multiple_tokens(self) -> None:
        """Multiple tokens return tuple preserving order."""
        result = parse_batch_params(f"{DAI},{USDC},{WETH}")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.tokens == (DAI, USDC, WETH)

    def test_strips_whitespace(self) -> None:
        """Whitespace around tokens is stripped."""
        result = parse_batch_params(f"  {DAI} , {USDC}  ")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.tokens == (DAI, USDC)

    def test_missing_tokens(self) -> None:
        """Missing tokens param returns error."""
        result = parse_batch_params(None)
        assert isinstance(result, ParseError)
        assert "Missing required parameter" in result.error

    def test_empty_tokens(self) -> None:
        """Empty tokens string returns error."""
        result = parse_batch_params("")
        assert isinstance(result, ParseError)
        assert "Missing required parameter" in result.error

    def test_whitespace_only_tokens(self) -> None:
        """Whitespace-only tokens returns error."""
        result = parse_batch_params("   ,  ,  ")
        assert isinstance(result, ParseError)
        assert "No valid token" in result.error

    def test_invalid_address_in_list(self) -> None:
        """Invalid address in list returns error with position."""
        result = parse_batch_params(f"{DAI},INVALID,{USDC}")
        assert isinstance(result, ParseError)
        assert "position 2" in result.error
        assert "INVALID" in result.error

    def test_consecutive_commas_dropped(self) -> None:
        """Empty segments from consecutive commas are dropped."""
        result = parse_batch_params(f"{DAI},,{USDC}")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.tokens == (DAI, USDC)

    def test_trailing_comma_dropped(self) -> None:
        """Trailing comma is dropped."""
        result = parse_batch_params(f"{DAI},")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.tokens == (DAI,)

    def test_block_param(self) -> None:
        """Block param is parsed and applies to all tokens."""
        result = parse_batch_params(f"{DAI},{USDC}", block="18000000")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.block == 18000000

    def test_invalid_block(self) -> None:
        """Invalid block returns error."""
        result = parse_batch_params(DAI, block="abc")
        assert isinstance(result, ParseError)
        assert "Invalid block" in result.error

    def test_too_many_tokens(self) -> None:
        """More than MAX_BATCH_TOKENS returns error."""
        tokens = ",".join([DAI] * (MAX_BATCH_TOKENS + 1))
        result = parse_batch_params(tokens)
        assert isinstance(result, ParseError)
        assert "Too many tokens" in result.error
        assert str(MAX_BATCH_TOKENS + 1) in result.error
        assert str(MAX_BATCH_TOKENS) in result.error

    def test_exactly_max_tokens(self) -> None:
        """Exactly MAX_BATCH_TOKENS is accepted."""
        tokens = ",".join([DAI] * MAX_BATCH_TOKENS)
        result = parse_batch_params(tokens)
        assert isinstance(result, BatchParseSuccess)
        assert len(result.data.tokens) == MAX_BATCH_TOKENS


class TestParseBatchParamsAmounts:
    """Tests for amounts parameter in batch pricing."""

    def test_amounts_matching_count(self) -> None:
        """Amounts with matching count are parsed correctly."""
        result = parse_batch_params(f"{DAI},{USDC}", amounts="1000,500")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.amounts == (1000.0, 500.0)

    def test_amounts_with_decimals(self) -> None:
        """Amounts with decimal values are parsed."""
        result = parse_batch_params(DAI, amounts="0.5")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.amounts == (0.5,)

    def test_amounts_count_mismatch(self) -> None:
        """Amounts count mismatch returns error."""
        result = parse_batch_params(f"{DAI},{USDC}", amounts="1000")
        assert isinstance(result, ParseError)
        assert "Amounts" in result.error or "amounts" in result.error.lower()
        assert "does not match" in result.error.lower()

    def test_amounts_more_than_tokens(self) -> None:
        """More amounts than tokens returns error."""
        result = parse_batch_params(DAI, amounts="1000,500")
        assert isinstance(result, ParseError)
        assert "does not match" in result.error.lower()

    def test_invalid_amount_non_numeric(self) -> None:
        """Non-numeric amount returns error."""
        result = parse_batch_params(DAI, amounts="abc")
        assert isinstance(result, ParseError)
        assert "Invalid amount" in result.error

    def test_invalid_amount_negative(self) -> None:
        """Negative amount returns error."""
        result = parse_batch_params(f"{DAI},{USDC}", amounts="1000,-500")
        assert isinstance(result, ParseError)
        assert "Invalid amount" in result.error

    def test_invalid_amount_zero(self) -> None:
        """Zero amount returns error."""
        result = parse_batch_params(DAI, amounts="0")
        assert isinstance(result, ParseError)
        assert "Invalid amount" in result.error

    def test_no_amounts(self) -> None:
        """No amounts param returns None."""
        result = parse_batch_params(DAI)
        assert isinstance(result, BatchParseSuccess)
        assert result.data.amounts is None

    def test_amounts_strip_whitespace(self) -> None:
        """Whitespace around amounts is stripped."""
        result = parse_batch_params(f"{DAI},{USDC}", amounts=" 1000 , 500 ")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.amounts == (1000.0, 500.0)

    def test_amounts_empty_segments_now_none(self) -> None:
        """Empty segments in amounts are now treated as None (not dropped)."""
        result = parse_batch_params(f"{DAI},{USDC},{WETH}", amounts="1000,,500")
        # Now: 3 amounts for 3 tokens, middle one is None
        assert isinstance(result, BatchParseSuccess)
        assert result.data.amounts == (1000.0, None, 500.0)

    def test_amounts_count_mismatch_with_none(self) -> None:
        """Empty segments count as None, so 2 tokens with 3 amounts fails."""
        result = parse_batch_params(f"{DAI},{USDC}", amounts="1000,,500")
        # 3 amounts for 2 tokens - should fail
        assert isinstance(result, ParseError)
        assert "does not match" in result.error.lower()


class TestParseBatchParamsMixedAmounts:
    """Tests for mixed amounts lists (some None) - documenting intended semantics.

    This documents the behavior where some tokens in a batch have amounts
    specified and others don't (represented as None in the amounts tuple).

    Use cases:
    - Price impact calculation for specific tokens only
    - Different amounts for different tokens in a single batch
    - Skipping price impact for tokens where it's not relevant
    """

    def test_mixed_amounts_some_none(self) -> None:
        """Amounts list can contain None values for tokens without amount."""
        result = parse_batch_params(f"{DAI},{USDC},{WETH}", amounts="1000,,500")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.amounts == (1000.0, None, 500.0)
        assert len(result.data.amounts) == 3

    def test_all_none_amounts(self) -> None:
        """All None amounts is valid (equivalent to no amounts)."""
        result = parse_batch_params(f"{DAI},{USDC}", amounts=",")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.amounts == (None, None)

    def test_single_none_amount(self) -> None:
        """Single token with empty amount results in (None,)."""
        result = parse_batch_params(DAI, amounts="")
        # Empty string returns None from _parse_amounts, but single comma is (None,)
        assert isinstance(result, BatchParseSuccess)
        # amounts="" returns None, not (None,)
        assert result.data.amounts is None

    def test_leading_none_amount(self) -> None:
        """Leading empty segment becomes None."""
        result = parse_batch_params(f"{DAI},{USDC}", amounts=",500")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.amounts == (None, 500.0)

    def test_trailing_none_amount(self) -> None:
        """Trailing empty segment becomes None."""
        result = parse_batch_params(f"{DAI},{USDC}", amounts="1000,")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.amounts == (1000.0, None)

    def test_mixed_amounts_preserves_position(self) -> None:
        """None values preserve positional correspondence with tokens."""
        result = parse_batch_params(
            f"{DAI},{USDC},{WETH}",
            amounts="1000,,500",
        )
        assert isinstance(result, BatchParseSuccess)
        # DAI has amount 1000, USDC has None, WETH has amount 500
        assert result.data.amounts is not None
        assert result.data.amounts[0] == 1000.0  # DAI
        assert result.data.amounts[1] is None  # USDC
        assert result.data.amounts[2] == 500.0  # WETH


class TestParseBatchParamsTimestamp:
    """Tests for timestamp parameter in batch pricing."""

    def test_timestamp_without_block(self) -> None:
        """Timestamp without block is accepted."""
        result = parse_batch_params(DAI, timestamp="1700000000")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.timestamp == 1700000000
        assert result.data.block is None

    def test_timestamp_and_block_mutually_exclusive(self) -> None:
        """Both timestamp and block returns error."""
        result = parse_batch_params(DAI, block="18000000", timestamp="1700000000")
        assert isinstance(result, ParseError)
        assert "mutually exclusive" in result.error.lower()

    def test_timestamp_invalid_format(self) -> None:
        """Invalid timestamp format returns error."""
        result = parse_batch_params(DAI, timestamp="invalid")
        assert isinstance(result, ParseError)
        assert "timestamp" in result.error.lower()

    def test_timestamp_with_amounts(self) -> None:
        """Timestamp works with amounts."""
        result = parse_batch_params(DAI, timestamp="1700000000", amounts="1000")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.timestamp == 1700000000
        assert result.data.amounts == (1000.0,)


class TestParseBatchParamsBooleans:
    """Tests for skip_cache and silent parameters in batch pricing."""

    def test_skip_cache_true(self) -> None:
        result = parse_batch_params(DAI, skip_cache="true")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.skip_cache is True

    def test_skip_cache_default_false(self) -> None:
        result = parse_batch_params(DAI)
        assert isinstance(result, BatchParseSuccess)
        assert result.data.skip_cache is False

    def test_skip_cache_invalid(self) -> None:
        result = parse_batch_params(DAI, skip_cache="maybe")
        assert isinstance(result, ParseError)
        assert "skip_cache" in result.error

    def test_silent_true(self) -> None:
        result = parse_batch_params(DAI, silent="true")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.silent is True

    def test_silent_default_false(self) -> None:
        result = parse_batch_params(DAI)
        assert isinstance(result, BatchParseSuccess)
        assert result.data.silent is False

    def test_silent_invalid(self) -> None:
        result = parse_batch_params(DAI, silent="2")
        assert isinstance(result, ParseError)
        assert "silent" in result.error

    def test_both_booleans_true(self) -> None:
        result = parse_batch_params(DAI, skip_cache="1", silent="1")
        assert isinstance(result, BatchParseSuccess)
        assert result.data.skip_cache is True
        assert result.data.silent is True


class TestParseBatchParamsCombined:
    """Tests for combined parameters in batch pricing."""

    def test_all_params_combined(self) -> None:
        """All params work together."""
        result = parse_batch_params(
            f"{DAI},{USDC}",
            block="18000000",
            amounts="1000,500",
            skip_cache="true",
            silent="true",
        )
        assert isinstance(result, BatchParseSuccess)
        assert result.data.tokens == (DAI, USDC)
        assert result.data.block == 18000000
        assert result.data.amounts == (1000.0, 500.0)
        assert result.data.skip_cache is True
        assert result.data.silent is True

    def test_timestamp_amounts_combined(self) -> None:
        """Timestamp and amounts can be combined."""
        result = parse_batch_params(
            f"{DAI},{USDC}",
            timestamp="1700000000",
            amounts="1000,500",
        )
        assert isinstance(result, BatchParseSuccess)
        assert result.data.timestamp == 1700000000
        assert result.data.amounts == (1000.0, 500.0)
        assert result.data.block is None


class TestParseQuoteParams:
    """Tests for parse_quote_params function."""

    def test_valid_params(self) -> None:
        """All valid params return QuoteParseSuccess."""
        result = parse_quote_params(DAI, USDC, "1000")
        assert isinstance(result, QuoteParseSuccess)
        assert result.data.from_token == DAI
        assert result.data.to_token == USDC
        assert result.data.amount == 1000.0
        assert result.data.block is None
        assert result.data.timestamp is None

    def test_valid_with_block(self) -> None:
        """Block param is parsed correctly."""
        result = parse_quote_params(DAI, USDC, "1000", block="18000000")
        assert isinstance(result, QuoteParseSuccess)
        assert result.data.block == 18000000

    def test_valid_with_timestamp(self) -> None:
        """Timestamp param is parsed correctly."""
        result = parse_quote_params(DAI, USDC, "1000", timestamp="1700000000")
        assert isinstance(result, QuoteParseSuccess)
        assert result.data.timestamp == 1700000000
        assert result.data.block is None

    def test_missing_from_token(self) -> None:
        """Missing from_token returns error."""
        result = parse_quote_params(None, USDC, "1000")
        assert isinstance(result, ParseError)
        assert "from" in result.error.lower()

    def test_empty_from_token(self) -> None:
        """Empty from_token returns error."""
        result = parse_quote_params("", USDC, "1000")
        assert isinstance(result, ParseError)
        assert "from" in result.error.lower()

    def test_missing_to_token(self) -> None:
        """Missing to_token returns error."""
        result = parse_quote_params(DAI, None, "1000")
        assert isinstance(result, ParseError)
        assert "to" in result.error.lower()

    def test_empty_to_token(self) -> None:
        """Empty to_token returns error."""
        result = parse_quote_params(DAI, "", "1000")
        assert isinstance(result, ParseError)
        assert "to" in result.error.lower()

    def test_invalid_from_token_address(self) -> None:
        """Invalid from_token address returns error."""
        result = parse_quote_params("notanaddress", USDC, "1000")
        assert isinstance(result, ParseError)
        assert "from" in result.error.lower()

    def test_invalid_to_token_address(self) -> None:
        """Invalid to_token address returns error."""
        result = parse_quote_params(DAI, "notanaddress", "1000")
        assert isinstance(result, ParseError)
        assert "to" in result.error.lower()

    def test_missing_amount(self) -> None:
        """Missing amount returns error."""
        result = parse_quote_params(DAI, USDC, None)
        assert isinstance(result, ParseError)
        assert "amount" in result.error.lower()

    def test_empty_amount(self) -> None:
        """Empty amount returns error."""
        result = parse_quote_params(DAI, USDC, "")
        assert isinstance(result, ParseError)
        assert "amount" in result.error.lower()

    def test_invalid_amount_non_numeric(self) -> None:
        """Non-numeric amount returns error."""
        result = parse_quote_params(DAI, USDC, "abc")
        assert isinstance(result, ParseError)
        assert "amount" in result.error.lower()

    def test_invalid_amount_negative(self) -> None:
        """Negative amount returns error."""
        result = parse_quote_params(DAI, USDC, "-100")
        assert isinstance(result, ParseError)
        assert "amount" in result.error.lower()

    def test_invalid_amount_zero(self) -> None:
        """Zero amount returns error."""
        result = parse_quote_params(DAI, USDC, "0")
        assert isinstance(result, ParseError)
        assert "amount" in result.error.lower()

    def test_valid_amount_decimal(self) -> None:
        """Decimal amount is parsed correctly."""
        result = parse_quote_params(DAI, USDC, "0.5")
        assert isinstance(result, QuoteParseSuccess)
        assert result.data.amount == 0.5

    def test_timestamp_and_block_mutually_exclusive(self) -> None:
        """Both timestamp and block returns error."""
        result = parse_quote_params(DAI, USDC, "1000", block="18000000", timestamp="1700000000")
        assert isinstance(result, ParseError)
        assert "mutually exclusive" in result.error.lower()

    def test_invalid_block(self) -> None:
        """Invalid block returns error."""
        result = parse_quote_params(DAI, USDC, "1000", block="abc")
        assert isinstance(result, ParseError)
        assert "block" in result.error.lower()

    def test_invalid_timestamp(self) -> None:
        """Invalid timestamp returns error."""
        result = parse_quote_params(DAI, USDC, "1000", timestamp="invalid")
        assert isinstance(result, ParseError)
        assert "timestamp" in result.error.lower()

    def test_future_timestamp(self) -> None:
        """Future timestamp returns error."""
        result = parse_quote_params(DAI, USDC, "1000", timestamp="9999999999")
        assert isinstance(result, ParseError)
        assert "future" in result.error.lower()

    def test_same_from_and_to_token(self) -> None:
        """Same from and to token is valid (handled by endpoint, not parser)."""
        result = parse_quote_params(DAI, DAI, "1000")
        assert isinstance(result, QuoteParseSuccess)
        assert result.data.from_token == DAI
        assert result.data.to_token == DAI

    def test_all_params_combined(self) -> None:
        """All params work together."""
        result = parse_quote_params(DAI, USDC, "1000", block="18000000")
        assert isinstance(result, QuoteParseSuccess)
        assert result.data.from_token == DAI
        assert result.data.to_token == USDC
        assert result.data.amount == 1000.0
        assert result.data.block == 18000000
