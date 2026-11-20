"""Rewrite or verify the exact ypricemagic Git pin without changing any other input."""

import argparse
import re
import sys
import tomllib
from pathlib import Path

SOURCE = "https://github.com/SatoshiAndKin/ypricemagic.git"
PIN = re.compile(rf"ypricemagic @ git\+{re.escape(SOURCE)}@([0-9a-f]{{40}})")
MANIFEST = Path("pyproject.toml")
LOCK = Path("uv.lock")


def pin() -> str:
    deps = tomllib.loads(MANIFEST.read_text())["project"]["dependencies"]
    matches = [match for dep in deps if (match := PIN.fullmatch(dep))]
    if len(matches) != 1:
        raise SystemExit("Expected exactly one immutable SatoshiAndKin/ypricemagic Git pin")
    return matches[0][1]


def update(new: str) -> None:
    old = pin()
    text = MANIFEST.read_text()
    text, count = re.subn(
        re.escape(f'ypricemagic @ git+{SOURCE}@{old}"'),
        f'ypricemagic @ git+{SOURCE}@{new}"',
        text,
    )
    if count != 1:
        raise SystemExit("Unexpected ypricemagic pin spelling in pyproject.toml")
    MANIFEST.write_text(text)
    if pin() != new:
        raise SystemExit("Failed to set the manifest pin")


def check_lock(expected: str) -> None:
    packages = tomllib.loads(LOCK.read_text())["package"]
    sources = [package["source"] for package in packages if package["name"] == "ypricemagic"]
    if pin() != expected or sources != [{"git": f"{SOURCE}?rev={expected}#{expected}"}]:
        raise SystemExit("ypricemagic manifest and uv.lock did not resolve to the expected Git SHA")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["read", "update", "check-lock"])
    parser.add_argument("sha", nargs="?")
    args = parser.parse_args()
    if args.operation == "read":
        sys.stdout.write(f"{pin()}\n")
        return
    if not args.sha or not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        parser.error("expected a full lowercase Git SHA")
    if args.operation == "update":
        update(args.sha)
    else:
        check_lock(args.sha)


if __name__ == "__main__":
    main()
