#!/usr/bin/env python3
"""
Strip extended depends_on conditions from docker-stack.yml for Swarm compatibility.

Docker Swarm doesn't support extended depends_on format with condition: service_healthy.
This script converts the extended format to a simple list format.

Before:
  depends_on:
    ypm-ethereum:
      condition: service_healthy
      required: true

After:
  depends_on:
  - ypm-ethereum
"""

import sys

try:
    import yaml
except ImportError:
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "pyyaml"])
    import yaml


def strip_depends_on(input_file: str, output_file: str | None = None) -> None:
    """Strip extended depends_on conditions from a compose file."""
    if output_file is None:
        output_file = input_file

    with open(input_file) as f:
        config = yaml.safe_load(f)

    for service in config.get("services", {}).values():
        if "depends_on" in service:
            deps = service["depends_on"]
            if isinstance(deps, dict):
                # Convert extended format to simple list format
                service["depends_on"] = list(deps.keys())

    with open(output_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "docker-stack.yml"
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    strip_depends_on(input_file, output_file)
