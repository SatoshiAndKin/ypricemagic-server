import re
from dataclasses import dataclass

ADDRESS_REGEX = re.compile(r"^0x[a-fA-F0-9]{40}$")

MAX_BLOCK = 2**63


def is_valid_address(address: str) -> bool:
    return bool(ADDRESS_REGEX.match(address))


@dataclass
class PriceParams:
    token: str
    block: int | None = None
    amount: float | None = None
    skip_cache: bool = False
    ignore_pools: tuple[str, ...] = ()
    silent: bool = False


@dataclass
class ParseSuccess:
    data: PriceParams


@dataclass
class ParseError:
    error: str


ParseResult = ParseSuccess | ParseError


def parse_bool_param(value: str | None, name: str) -> bool | None | ParseError:
    """Parse a boolean query parameter.

    Accepts: true, false, 1, 0 (case-insensitive).
    Returns True/False for valid values.
    Returns None for missing/empty values.
    Returns ParseError for invalid values.
    """
    if value is None or value == "":
        return None

    normalized = value.lower().strip()
    if normalized in ("true", "1"):
        return True
    elif normalized in ("false", "0"):
        return False
    else:
        return ParseError(f"Invalid {name} value: '{value}'. Must be true, false, 1, or 0.")


def parse_ignore_pools(value: str | None) -> tuple[str, ...] | ParseError:
    """Parse comma-separated pool addresses.

    Splits on comma, strips whitespace, drops empty segments.
    Validates each segment as a valid address.
    Returns tuple of addresses.
    Returns empty tuple for missing/empty values.
    Returns ParseError if any address is invalid.
    """
    if value is None or value == "":
        return ()

    segments = value.split(",")
    addresses: list[str] = []
    for segment in segments:
        stripped = segment.strip()
        if stripped == "":
            continue  # Drop empty segments
        if not is_valid_address(stripped):
            return ParseError(f"Invalid ignore_pools address: '{stripped}'")
        addresses.append(stripped)

    return tuple(addresses)


def _parse_block(block: str | None) -> int | None | ParseError:
    """Parse block parameter."""
    if block is None:
        return None
    try:
        parsed = int(block)
    except (ValueError, TypeError):
        return ParseError(f"Invalid block number: {block}")
    if parsed <= 0 or parsed > MAX_BLOCK:
        return ParseError(f"Invalid block number: {block}")
    return parsed


def _parse_amount(amount: str | None) -> float | None | ParseError:
    """Parse amount parameter."""
    if amount is None:
        return None
    try:
        parsed = float(amount)
    except (ValueError, TypeError):
        return ParseError(f"Invalid amount: {amount}")
    if parsed <= 0:
        return ParseError(f"Invalid amount: {amount}")
    return parsed


def _parse_bool_with_default(value: str | None, name: str) -> bool | ParseError:
    """Parse boolean parameter with default False."""
    result = parse_bool_param(value, name)
    if isinstance(result, ParseError):
        return result
    return result if result is not None else False


def parse_price_params(
    token: str | None,
    block: str | None = None,
    amount: str | None = None,
    skip_cache: str | None = None,
    ignore_pools: str | None = None,
    silent: str | None = None,
) -> ParseResult:
    if not token:
        return ParseError("Missing required parameter: token")

    if not is_valid_address(token):
        return ParseError(f"Invalid token address: {token}")

    parsed_block = _parse_block(block)
    if isinstance(parsed_block, ParseError):
        return parsed_block

    parsed_amount = _parse_amount(amount)
    if isinstance(parsed_amount, ParseError):
        return parsed_amount

    parsed_skip_cache = _parse_bool_with_default(skip_cache, "skip_cache")
    if isinstance(parsed_skip_cache, ParseError):
        return parsed_skip_cache

    parsed_silent = _parse_bool_with_default(silent, "silent")
    if isinstance(parsed_silent, ParseError):
        return parsed_silent

    parsed_ignore_pools = parse_ignore_pools(ignore_pools)
    if isinstance(parsed_ignore_pools, ParseError):
        return parsed_ignore_pools

    return ParseSuccess(
        data=PriceParams(
            token=token,
            block=parsed_block,
            amount=parsed_amount,
            skip_cache=parsed_skip_cache,
            ignore_pools=parsed_ignore_pools,
            silent=parsed_silent,
        )
    )
