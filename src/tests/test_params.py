import pytest

from src.params import ParseError, ParseSuccess, is_valid_address, parse_price_params

DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


class TestIsValidAddress:
    def test_accepts_valid_checksummed(self):
        assert is_valid_address(DAI) is True

    def test_accepts_valid_lowercase(self):
        assert is_valid_address(DAI.lower()) is True

    def test_accepts_valid_uppercase(self):
        assert is_valid_address("0x6B175474E89094C44DA98B954EEDEAC495271D0F") is True

    def test_rejects_no_prefix(self):
        assert is_valid_address("6B175474E89094C44Da98b954EedeAC495271d0F") is False

    def test_rejects_short(self):
        assert is_valid_address("0x123") is False

    def test_rejects_long(self):
        assert is_valid_address("0x6B175474E89094C44Da98b954EedeAC495271d0F00") is False

    def test_rejects_invalid_chars(self):
        assert is_valid_address("0x6B175474E89094C44Da98b954EedeAC495271d0G") is False

    def test_rejects_empty(self):
        assert is_valid_address("") is False

    def test_rejects_symbol(self):
        assert is_valid_address("DAI") is False


class TestParsePriceParams:
    def test_valid_token_only(self):
        result = parse_price_params(DAI)
        assert isinstance(result, ParseSuccess)
        assert result.data.token == DAI
        assert result.data.block is None

    def test_valid_token_and_block(self):
        result = parse_price_params(DAI, "18000000")
        assert isinstance(result, ParseSuccess)
        assert result.data.token == DAI
        assert result.data.block == 18000000

    def test_missing_token(self):
        result = parse_price_params(None)
        assert isinstance(result, ParseError)
        assert "Missing required parameter" in result.error

    def test_empty_token(self):
        result = parse_price_params("")
        assert isinstance(result, ParseError)
        assert "Missing required parameter" in result.error

    def test_invalid_token_address(self):
        result = parse_price_params("DAI")
        assert isinstance(result, ParseError)
        assert "Invalid token address" in result.error

    def test_invalid_block_non_numeric(self):
        result = parse_price_params(DAI, "abc")
        assert isinstance(result, ParseError)
        assert "Invalid block number" in result.error

    def test_invalid_block_negative(self):
        result = parse_price_params(DAI, "-100")
        assert isinstance(result, ParseError)
        assert "Invalid block number" in result.error

    def test_invalid_block_zero(self):
        result = parse_price_params(DAI, "0")
        assert isinstance(result, ParseError)
        assert "Invalid block number" in result.error

    def test_valid_block_one(self):
        result = parse_price_params(DAI, "1")
        assert isinstance(result, ParseSuccess)
        assert result.data.block == 1

    def test_no_block_param(self):
        result = parse_price_params(USDC, None)
        assert isinstance(result, ParseSuccess)
        assert result.data.block is None
