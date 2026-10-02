"""Smoke validation must not hide API failures behind reference availability."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from scripts import validate_prices as validation

TOKEN = validation.TOKENS[0]


@pytest.mark.parametrize("function", [validation._compare_one, validation._compare_latest])
def test_api_failure_is_a_failed_comparison(monkeypatch: pytest.MonkeyPatch, function: Any) -> None:
    monkeypatch.setattr(
        validation, "fetch_ypm_price", lambda *args, **kwargs: (None, "HTTP 504: timed out")
    )
    args = (
        ("http://test", TOKEN, 1700000000, 1.0)
        if function == validation._compare_one
        else ("http://test", TOKEN, 1.0)
    )
    result = function(*args)
    assert result.passed is False
    assert result.ypm_error == "HTTP 504: timed out"
    assert result.ypm_seconds >= 0


def test_current_check_runs_after_historical_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    lookup = Mock(return_value=(1.0, None))
    monkeypatch.setattr(validation, "fetch_ypm_price", lookup)
    monkeypatch.setattr(
        validation, "fetch_defillama_current_prices", lambda tokens: {TOKEN.address: 1.0}
    )
    failed = validation.ComparisonResult(TOKEN, 1700000000, None, 1.0, "HTTP 504", None, False)
    result = validation._compare_latest_prices("http://test", [TOKEN], ["ethereum"], [failed])
    assert result[0].passed is True
    lookup.assert_called_once_with("http://test", TOKEN, timestamp=None)
    assert failed.passed is False


def test_missing_required_chain_fails_and_writes_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(validation, "discover_live_chains", lambda url: ["ethereum"])
    report = tmp_path / "report.json"
    assert validation.run("http://test", report=report) == 1
    assert json.loads(report.read_text()) == {
        "passed": False,
        "missing_chains": ["base"],
        "results": [],
    }


def test_base_and_real_xpremia_are_permanent_cases() -> None:
    assert {token.name for token in validation.TOKENS if token.chain == "base"} == {"USDC", "WETH"}
    xpremia = next(token for token in validation.TOKENS if token.name == "xPREMIA")
    assert xpremia.address == "0x16f9D564Df80376C61AC914205D3fDfF7057d610"


def test_expected_unavailable_requires_http_404(monkeypatch: pytest.MonkeyPatch) -> None:
    for error, expected in [
        ("HTTP 404: No price", True),
        ("HTTP 404: 404 page not found", False),
        ("HTTP 504: timeout", False),
        ("network error", False),
    ]:
        monkeypatch.setattr(validation, "fetch_ypm_price", lambda *args, value=error: (None, value))
        assert validation._check_unavailable("http://test").passed is expected


def test_base_history_starts_after_native_token_deployment(monkeypatch: pytest.MonkeyPatch) -> None:
    tokens = [token for token in validation.TOKENS if token.chain == "base"]
    monkeypatch.setattr(
        validation,
        "fetch_defillama_first_timestamps",
        lambda tokens: {token.address: 1538667082 for token in tokens},
    )
    chart = Mock(return_value={})
    monkeypatch.setattr(validation, "fetch_defillama_chart", chart)
    monkeypatch.setattr(validation, "_ypm_only", lambda *args: Mock())
    validation._compare_historical("http://test", tokens)
    assert chart.call_args.args[1] == 1692383789
