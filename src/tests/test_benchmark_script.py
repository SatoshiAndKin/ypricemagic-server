"""Pinned exact amount results must reject even a one-ULP difference."""

import json
import math
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import benchmark_prices as benchmark


@pytest.mark.parametrize("chain", ["ethereum", "base"])
def test_golden_mismatch_fails_and_remains_in_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, chain: str
) -> None:
    token, _, block, expected = benchmark.CHAINS[chain]
    changed = math.nextafter(expected, math.inf)
    assert changed != expected
    phases: list[str] = []

    def response(
        self: benchmark.Benchmark,
        phase: str,
        requested_chain: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        assert requested_chain == chain
        phases.append(phase)
        if endpoint == "health":
            return {"block": block + 100}
        result = {"token": token, "price": changed, "cached": False}
        return [result] * 3 if endpoint == "prices" else result

    report = tmp_path / "timings.json"
    monkeypatch.setattr(benchmark.Benchmark, "request", response)
    monkeypatch.setattr(sys, "argv", ["benchmark", "--chains", chain, "--report", str(report)])
    with pytest.raises(SystemExit) as caught:
        benchmark.main()
    assert caught.value.code == 1
    assert phases == ["historical-first"]
    records = json.loads(report.read_text())
    assert len(records) == 1
    assert records[0]["chain"] == chain
    assert records[0]["phase"] == "acceptance"
    assert records[0]["passed"] is False
    assert str(changed) in records[0]["error"]
