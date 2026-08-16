#!/usr/bin/env python3
"""Assemble compose files. Logic lives here so the Makefile survives cmd.exe."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["compose/docker-compose.yml", "compose/sources.yml"]
if os.environ.get("GOVERNANCE", "1") == "1":
    FILES.append("compose/governance.yml")


def main() -> int:
    args = sys.argv[1:]
    cmd = [
        "docker",
        "compose",
        "--env-file",
        "versions.env",
        "--profile",
        "governance",
    ]
    for f in FILES:
        cmd.extend(["-f", f])
    cmd.extend(args)
    env = os.environ.copy()
    env.setdefault("DELTA_DATA", str(Path("/tmp/contoso-dbx-delta")))
    Path(env["DELTA_DATA"]).mkdir(parents=True, exist_ok=True)
    return subprocess.call(cmd, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
