import json

path = "/Users/bryan/.factory/missions/a35e4400-3487-4006-9ae9-a8427a21c985/features.json"
with open(path) as f:
    data = json.load(f)

new_feature = {
    "id": "fix-quote-token-routing-test-failures",
    "description": "Fix two failing integration tests in tests/prices/test_quote_token_routing.py that were introduced during the quote-token milestone.\n\n**BUG 1:** `test_routing_tokens_used_for_non_usd_quote` fails. WBTC/DAI routing returns 16102 instead of expected ~26048. This indicates a math or routing logic error when routing to a non-USD quote token via intermediaries.\n\n**BUG 2:** `test_usd_cache_not_polluted_by_get_price_in` fails. Calling `get_price` returns a `Decimal` instead of `UsdPrice`. Investigate how `get_price_in` or the new `Price` type is contaminating the cache. Note that `get_price_in` might be calling `get_price` internally in a way that caches a Decimal, or the memoization cache is mixing up the types. Ensure that standard `get_price` calls still return `UsdPrice`.\n\nFix both bugs and ensure `pytest tests/prices/test_quote_token_routing.py -v` passes completely.",
    "skillName": "python-lib-worker",
    "preconditions": ["fix-v2-deepest-pool-usd-fallback is complete"],
    "expectedBehavior": [
        "WBTC/DAI cross-routing calculates the correct price",
        "get_price strictly returns UsdPrice and does not return Decimal after a get_price_in call",
        "All tests in test_quote_token_routing.py pass",
    ],
    "verificationSteps": ["pytest tests/prices/test_quote_token_routing.py -v passes"],
    "fulfills": [],
    "milestone": "quote-token",
    "status": "pending",
}

data["features"].insert(0, new_feature)

with open(path, "w") as f:
    json.dump(data, f, indent=2)

print("Inserted new feature 3 successfully.")  # noqa: T201
