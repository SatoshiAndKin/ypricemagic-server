import re
from dataclasses import dataclass
from typing import Optional, Union

ADDRESS_REGEX = re.compile(r"^0x[a-fA-F0-9]{40}$")

MAX_BLOCK = 2**63


def is_valid_address(address: str) -> bool:
    return bool(ADDRESS_REGEX.match(address))


@dataclass
class PriceParams:
    token: str
    block: Optional[int] = None


@dataclass
class ParseSuccess:
    data: PriceParams


@dataclass
class ParseError:
    error: str


ParseResult = Union[ParseSuccess, ParseError]


def parse_price_params(
    token: Optional[str],
    block: Optional[str] = None,
) -> ParseResult:
    if not token:
        return ParseError("Missing required parameter: token")

    if not is_valid_address(token):
        return ParseError(f"Invalid token address: {token}")

    parsed_block: Optional[int] = None
    if block is not None:
        try:
            parsed_block = int(block)
        except (ValueError, TypeError):
            return ParseError(f"Invalid block number: {block}")
        if parsed_block <= 0 or parsed_block > MAX_BLOCK:
            return ParseError(f"Invalid block number: {block}")

    return ParseSuccess(data=PriceParams(token=token, block=parsed_block))
