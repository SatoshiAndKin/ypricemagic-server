import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

ADDRESS_REGEX = re.compile(r"^0x[a-fA-F0-9]{40}$")

MAX_BLOCK = 2**63

# Buffer for future timestamp validation (allows slight clock skew)
TIMESTAMP_FUTURE_BUFFER_SECONDS = 300  # 5 minutes


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
    timestamp: int | None = None


@dataclass
class BatchParams:
    tokens: tuple[str, ...]
    block: int | None = None
    amounts: tuple[float | None, ...] | None = None
    skip_cache: bool = False
    silent: bool = False
    timestamp: int | None = None


@dataclass
class QuoteParams:
    """Parameters for the quote endpoint.

    from_token: the token to quote from (required)
    to_token: the token to quote to (required)
    amount: the amount of from_token (required, must be positive)
    block: optional block number
    timestamp: optional Unix/ISO timestamp (mutually exclusive with block)
    """

    from_token: str
    to_token: str
    amount: float
    block: int | None = None
    timestamp: int | None = None


# Maximum number of tokens allowed in a batch request
MAX_BATCH_TOKENS = 100


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


def parse_timestamp(value: str | None) -> int | None | ParseError:
    """Parse timestamp parameter.

    Accepts:
    - Unix epoch as integer string (e.g., '1700000000')
    - Unix epoch as float string (e.g., '1700000000.123' - decimal discarded)
    - ISO 8601 with timezone (e.g., '2023-11-14T22:13:20Z' or '2023-11-14T22:13:20+00:00')

    Validates:
    - Not negative
    - Not zero
    - Not in the future (compared to current time + buffer)

    Returns Unix epoch as int on success.
    Returns None for missing/empty values.
    Returns ParseError for invalid values.
    """
    if value is None or value == "":
        return None

    stripped = value.strip()

    # Try parsing as Unix epoch (int or float)
    parsed = _parse_unix_timestamp(stripped)
    if parsed is not None:
        return parsed

    # Try ISO 8601 format
    return _parse_iso8601_timestamp(stripped)


def _parse_unix_timestamp(value: str) -> int | None | ParseError:
    """Parse Unix epoch timestamp string."""
    try:
        parsed_float = float(value)
    except ValueError:
        return None  # Not a number, caller should try other formats

    if parsed_float < 0:
        return ParseError("Timestamp cannot be negative.")
    if parsed_float == 0:
        return ParseError("Timestamp cannot be zero.")

    parsed = int(parsed_float)

    # Validate not in future
    now = datetime.now(UTC)
    max_allowed = now + timedelta(seconds=TIMESTAMP_FUTURE_BUFFER_SECONDS)
    if parsed > max_allowed.timestamp():
        return ParseError("Timestamp cannot be in the future.")

    return parsed


def _parse_iso8601_timestamp(value: str) -> int | ParseError:
    """Parse ISO 8601 timestamp string."""
    iso_patterns = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
    ]

    parsed_dt: datetime | None = None
    for pattern in iso_patterns:
        try:
            parsed_dt = datetime.strptime(value, pattern)
            break
        except ValueError:
            continue

    if parsed_dt is None:
        return ParseError(f"Invalid timestamp format: '{value}'. Expected Unix epoch or ISO 8601.")

    # Ensure timezone-aware (add UTC if naive)
    if parsed_dt.tzinfo is None:
        parsed_dt = parsed_dt.replace(tzinfo=UTC)

    # Validate not in future
    now = datetime.now(UTC)
    max_allowed = now + timedelta(seconds=TIMESTAMP_FUTURE_BUFFER_SECONDS)
    if parsed_dt > max_allowed:
        return ParseError("Timestamp cannot be in the future.")

    epoch = int(parsed_dt.timestamp())
    if epoch <= 0:
        return ParseError("Timestamp cannot be zero or negative.")

    return epoch


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
    timestamp: str | None = None,
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

    parsed_timestamp = parse_timestamp(timestamp)
    if isinstance(parsed_timestamp, ParseError):
        return parsed_timestamp

    # Mutual exclusivity check: timestamp and block cannot both be provided
    if parsed_timestamp is not None and parsed_block is not None:
        return ParseError(
            "Parameters 'timestamp' and 'block' are mutually exclusive. Provide only one."
        )

    return ParseSuccess(
        data=PriceParams(
            token=token,
            block=parsed_block,
            amount=parsed_amount,
            skip_cache=parsed_skip_cache,
            ignore_pools=parsed_ignore_pools,
            silent=parsed_silent,
            timestamp=parsed_timestamp,
        )
    )


@dataclass
class BatchParseSuccess:
    data: "BatchParams"


BatchParseResult = BatchParseSuccess | ParseError


def _parse_amounts(value: str | None) -> tuple[float | None, ...] | None | ParseError:
    """Parse comma-separated amounts.

    Splits on comma, strips whitespace.
    Empty segments (from consecutive commas or explicit empty) are treated as None.
    This allows specifying amounts for some tokens but not others in a batch.

    Non-empty segments must be positive numbers.

    Returns tuple of amounts (float or None for empty segments).
    Returns None for missing/empty values.
    Returns ParseError if any non-empty amount is invalid.
    """
    if value is None or value == "":
        return None

    segments = value.split(",")
    amounts: list[float | None] = []
    for i, segment in enumerate(segments):
        stripped = segment.strip()
        if stripped == "":
            # Empty segment means "no amount for this token"
            amounts.append(None)
        else:
            try:
                parsed = float(stripped)
            except (ValueError, TypeError):
                return ParseError(f"Invalid amount at position {i + 1}: '{stripped}'")
            if parsed <= 0:
                return ParseError(
                    f"Invalid amount at position {i + 1}: '{stripped}' (must be positive)"
                )
            amounts.append(parsed)

    return tuple(amounts) if amounts else None


def _parse_tokens(value: str | None) -> tuple[str, ...] | ParseError:
    """Parse comma-separated token addresses.

    Validates:
    - At least one valid address
    - Each address is valid
    - Max MAX_BATCH_TOKENS addresses

    Returns tuple of addresses on success.
    Returns ParseError on validation failure.
    """
    if value is None or value.strip() == "":
        return ParseError("Missing required parameter: tokens")

    segments = value.split(",")
    tokens: list[str] = []
    for i, segment in enumerate(segments):
        stripped = segment.strip()
        if stripped == "":
            continue  # Drop empty segments
        if not is_valid_address(stripped):
            return ParseError(f"Invalid token address at position {i + 1}: '{stripped}'")
        tokens.append(stripped)

    if len(tokens) == 0:
        return ParseError("No valid token addresses provided.")

    if len(tokens) > MAX_BATCH_TOKENS:
        return ParseError(f"Too many tokens: {len(tokens)}. Maximum allowed is {MAX_BATCH_TOKENS}.")

    return tuple(tokens)


def parse_batch_params(
    tokens: str | None,
    block: str | None = None,
    amounts: str | None = None,
    timestamp: str | None = None,
    skip_cache: str | None = None,
    silent: str | None = None,
) -> BatchParseResult:
    """Parse batch pricing parameters.

    Validates:
    - tokens: comma-separated addresses (required, max 100)
    - block: optional block number
    - amounts: optional comma-separated amounts (must match token count if provided)
    - timestamp: optional Unix/ISO timestamp (mutually exclusive with block)
    - skip_cache, silent: optional booleans

    Returns BatchParseSuccess with BatchParams on success.
    Returns ParseError on validation failure.
    """
    # Parse tokens
    parsed_tokens = _parse_tokens(tokens)
    if isinstance(parsed_tokens, ParseError):
        return parsed_tokens

    # Parse block
    parsed_block = _parse_block(block)
    if isinstance(parsed_block, ParseError):
        return parsed_block

    # Parse amounts
    parsed_amounts = _parse_amounts(amounts)
    if isinstance(parsed_amounts, ParseError):
        return parsed_amounts

    # Validate amounts count matches tokens count
    if parsed_amounts is not None and len(parsed_amounts) != len(parsed_tokens):
        return ParseError(
            f"Amounts count ({len(parsed_amounts)}) does not match tokens count ({len(parsed_tokens)})."
        )

    # Parse timestamp
    parsed_timestamp = parse_timestamp(timestamp)
    if isinstance(parsed_timestamp, ParseError):
        return parsed_timestamp

    # Parse booleans
    parsed_skip_cache = _parse_bool_with_default(skip_cache, "skip_cache")
    if isinstance(parsed_skip_cache, ParseError):
        return parsed_skip_cache

    parsed_silent = _parse_bool_with_default(silent, "silent")
    if isinstance(parsed_silent, ParseError):
        return parsed_silent

    # Mutual exclusivity check: timestamp and block cannot both be provided
    if parsed_timestamp is not None and parsed_block is not None:
        return ParseError(
            "Parameters 'timestamp' and 'block' are mutually exclusive. Provide only one."
        )

    return BatchParseSuccess(
        data=BatchParams(
            tokens=tuple(parsed_tokens),
            block=parsed_block,
            amounts=parsed_amounts,
            skip_cache=parsed_skip_cache,
            silent=parsed_silent,
            timestamp=parsed_timestamp,
        )
    )


@dataclass
class QuoteParseSuccess:
    data: "QuoteParams"


QuoteParseResult = QuoteParseSuccess | ParseError


def _parse_quote_token(token: str | None, name: str) -> str | ParseError:
    """Validate a token address for quote endpoint.

    Returns the token address on success.
    Returns ParseError on validation failure.
    """
    if not token:
        return ParseError(f"Missing required parameter: {name}")
    if not is_valid_address(token):
        return ParseError(f"Invalid {name} token address: {token}")
    return token


def parse_quote_params(
    from_token: str | None,
    to_token: str | None,
    amount: str | None,
    block: str | None = None,
    timestamp: str | None = None,
) -> QuoteParseResult:
    """Parse quote endpoint parameters.

    Validates:
    - from_token: valid address (required)
    - to_token: valid address (required)
    - amount: positive number (required)
    - block: optional block number
    - timestamp: optional Unix/ISO timestamp (mutually exclusive with block)

    Returns QuoteParseSuccess with QuoteParams on success.
    Returns ParseError on validation failure.
    """
    # Validate tokens
    validated_from = _parse_quote_token(from_token, "from")
    if isinstance(validated_from, ParseError):
        return validated_from

    validated_to = _parse_quote_token(to_token, "to")
    if isinstance(validated_to, ParseError):
        return validated_to

    # Validate amount
    if not amount:
        return ParseError("Missing required parameter: amount")
    parsed_amount = _parse_amount(amount)
    if isinstance(parsed_amount, ParseError):
        return parsed_amount
    if parsed_amount is None:
        return ParseError("Missing required parameter: amount")

    # Parse block and timestamp
    parsed_block = _parse_block(block)
    if isinstance(parsed_block, ParseError):
        return parsed_block

    parsed_timestamp = parse_timestamp(timestamp)
    if isinstance(parsed_timestamp, ParseError):
        return parsed_timestamp

    # Mutual exclusivity check
    if parsed_timestamp is not None and parsed_block is not None:
        return ParseError(
            "Parameters 'timestamp' and 'block' are mutually exclusive. Provide only one."
        )

    return QuoteParseSuccess(
        data=QuoteParams(
            from_token=validated_from,
            to_token=validated_to,
            amount=parsed_amount,
            block=parsed_block,
            timestamp=parsed_timestamp,
        )
    )
