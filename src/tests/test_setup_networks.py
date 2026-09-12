"""Run the real entrypoint with synthetic Brownie and server commands."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class NetworkRegistrationTests(unittest.TestCase):
    def test_registration_preserves_arguments_and_never_prints_credentials(self) -> None:
        script = Path(__file__).resolve().parents[2] / "setup-networks.sh"
        for outcome in ("added", "updated", "add-failed", "update-failed"):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                rpc = "https://rpc.example/v2/private-key?first=1&second=2"
                brownie = root / "brownie"
                brownie.write_text(
                    f"#!{sys.executable}\n"
                    "import json, os, pathlib, sys\n"
                    "with open(os.environ['CALLS'], 'a') as stream:\n"
                    "    stream.write(json.dumps(sys.argv[1:]) + '\\n')\n"
                    "action = sys.argv[2]\n"
                    "mode = os.environ['OUTCOME']\n"
                    "print(os.environ['RPC_URL'])\n"
                    "if action == 'add' and mode != 'added':\n"
                    "    print('already exists' if mode != 'add-failed' else 'failed')\n"
                    "    raise SystemExit(1)\n"
                    "if action == 'modify' and mode == 'update-failed':\n"
                    "    raise SystemExit(1)\n"
                    "if action == 'list': print('base-custom')\n"
                )
                brownie.chmod(0o755)
                server = root / "uvicorn"
                server.write_text(f"#!{sys.executable}\nprint('server started')\n")
                server.chmod(0o755)
                result = subprocess.run(
                    ["bash", str(script)],
                    env=dict(
                        os.environ,
                        PATH=f"{root}:{os.environ['PATH']}",
                        CHAIN_NAME="base",
                        CHAIN_ID="8453",
                        RPC_URL=rpc,
                        CALLS=str(root / "calls"),
                        OUTCOME=outcome,
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                output = result.stdout + result.stderr
                self.assertNotIn(rpc, output)
                self.assertNotIn("private-key", output)
                succeeded = outcome in ("added", "updated")
                self.assertEqual(result.returncode, 0 if succeeded else 1, output)
                self.assertEqual("server started" in output, succeeded)
                calls = [json.loads(line) for line in (root / "calls").read_text().splitlines()]
                self.assertIn(f"host={rpc}", calls[0])
                if outcome in ("updated", "update-failed"):
                    self.assertIn(f"host={rpc}", calls[1])


if __name__ == "__main__":
    unittest.main()
