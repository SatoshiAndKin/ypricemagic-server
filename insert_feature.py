import json

path = "/Users/bryan/.factory/missions/a35e4400-3487-4006-9ae9-a8427a21c985/features.json"
with open(path) as f:
    data = json.load(f)

new_feature = {
    "id": "fix-quote-token-scrutiny-findings",
    "description": 'Fix issues found during quote-token scrutiny validation.\n\n**BLOCKING BUG:** y/prices/dex/uniswap/v2.py ~line 598: V2 deepest_pool fallback always returns `UsdPrice(...)` regardless of `is_usd_price`. Fix: change `if paired_with_price:` to `if paired_with_price and is_usd_price: return UsdPrice(...)`. This ensures non-USD quote tokens don\'t get silently wrong USD-denominated prices.\n\n**NON-BLOCKING FIX 1:** Run `.venv/bin/python -m black tests/prices/test_quote_token_routing.py`.\n\n**NON-BLOCKING FIX 2:** y/prices/magic.py ~line 265: Prevent potential ZeroDivisionError if `quote_usd_price` is 0 in `get_price_in`. Add `if not quote_usd_price: return None` before the division.\n\n**NON-BLOCKING FIX 3:** y/prices/dex/uniswap/v2.py ~line 502: Change return type annotation `-> UsdPrice | float | None` to `-> UsdPrice | Price | None` because the method can return `Price(result)`. Make sure to import `Price` from `y.datatypes` if needed.\n\n**NON-BLOCKING FIX 4:** y/prices/magic.py: Change bare `except Exception: pass` in `_get_price_on_chain` to log the exception at DEBUG level (e.g. `logger.debug("Error in on-chain routing", exc_info=True)`) instead of silently swallowing it.',
    "skillName": "python-lib-worker",
    "preconditions": ["router-quote-token-generalization is complete"],
    "expectedBehavior": [
        "V2 deepest_pool fallback skips UsdPrice return for non-USD quotes",
        "test_quote_token_routing.py is black-formatted",
        "get_price_in handles quote_usd_price == 0 safely",
        "V2 get_price return type is accurately annotated",
        "Exceptions in _get_price_on_chain are logged at debug level",
    ],
    "verificationSteps": [
        "black --check tests/prices/test_quote_token_routing.py",
        "mypy y/prices/magic.py y/prices/dex/uniswap/v2.py",
        "pytest tests/prices/test_quote_token_routing.py -v passes",
    ],
    "fulfills": [],
    "milestone": "quote-token",
    "status": "pending",
}

data["features"].insert(0, new_feature)

with open(path, "w") as f:
    json.dump(data, f, indent=2)

print("Inserted new feature successfully.")  # noqa: T201
