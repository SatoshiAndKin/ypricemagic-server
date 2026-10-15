"""Verify the resolved private proxy contract with native Compose."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("filename", ["docker-compose.yml", "docker-compose.prod.yml"])
def test_proxy_is_private_and_digest_override_preserves_application_contract(
    tmp_path: Path, filename: str
) -> None:
    image = "ghcr.io/satoshiandkin/web3-proxy@sha256:" + "a" * 64
    override = tmp_path / "compose.image.json"
    override.write_text(json.dumps({"services": {"rpc-ethereum": {"image": image}}}))
    environment = tmp_path / "env"
    environment.write_text("ETHERSCAN_TOKEN=synthetic\n")
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(environment),
            "-f",
            str(ROOT / filename),
            "-f",
            str(override),
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        env=dict(os.environ, ETHERSCAN_TOKEN="synthetic"),
        text=True,
        capture_output=True,
        check=True,
    )
    services: dict[str, Any] = json.loads(result.stdout)["services"]
    assert set(services) == {"rpc-ethereum", "ypm-ethereum", "frontend"}
    proxy = services["rpc-ethereum"]
    assert proxy["image"] == image
    assert not proxy.get("ports")
    assert set(proxy["networks"]) == {"rpc-ethereum"}
    assert proxy["labels"]["traefik.enable"] == "false"
    app = services["ypm-ethereum"]
    assert "RPC_URL" not in app["environment"]
    assert int(app["mem_limit"]) == int(app["memswap_limit"]) == 8 * 1024**3
    assert app["depends_on"]["rpc-ethereum"]["condition"] == "service_healthy"
    assert set(app["networks"]) == {"rpc-ethereum", "traefik-proxy"}
    source = yaml.safe_load((ROOT / filename).read_text())
    # Compose omits unused volumes from config output. Retain their declarations
    # for later Base reactivation; deployments never remove volumes.
    assert {"cache-base", "brownie-base", "ypricemagic-base", "appcache-base"} <= set(
        source["volumes"]
    )
