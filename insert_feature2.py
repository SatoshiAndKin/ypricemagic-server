import json

path = "/Users/bryan/.factory/missions/a35e4400-3487-4006-9ae9-a8427a21c985/features.json"
with open(path) as f:
    data = json.load(f)

new_feature = {
    "id": "fix-v2-deepest-pool-usd-fallback",
    "description": "Fix blocking bug from scrutiny round 2: V2 deepest_pool fallback still returns USD-denominated value for non-USD quote targets. In y/prices/dex/uniswap/v2.py ~line 596-601, `result = amount_out * Decimal(paired_with_price) / _amount` is ALWAYS a USD value. The previous fix returned Price(result) for non-USD branches but the numerical value is still USD-denominated. Fix: change the fallback to simply: `if paired_with_price and is_usd_price: return UsdPrice(amount_out * Decimal(paired_with_price) / _amount)`. Remove the `return Price(result)` branch entirely so non-USD cases fall through to get_price_in's cross-rate fallback.",
    "skillName": "python-lib-worker",
    "preconditions": ["fix-quote-token-scrutiny-findings is complete"],
    "expectedBehavior": [
        "V2 deepest_pool fallback only returns for USD quote targets",
        "Non-USD quote targets fall through and return None, letting get_price_in handle cross-rate fallback",
    ],
    "verificationSteps": [
        "pytest tests/prices/test_quote_token_routing.py -v passes",
        "mypy y/prices/dex/uniswap/v2.py",
    ],
    "fulfills": [],
    "milestone": "quote-token",
    "status": "pending",
}

data["features"].insert(0, new_feature)

with open(path, "w") as f:
    json.dump(data, f, indent=2)

print("Inserted new feature 2 successfully.")  # noqa: T201
