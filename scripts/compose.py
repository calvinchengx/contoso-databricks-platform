#!/usr/bin/env python3
"""Assemble compose files. Logic lives here so the Makefile survives cmd.exe."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "compose" / ".generated"
FILES = ["compose/docker-compose.yml"]
if os.environ.get("GOVERNANCE", "1") == "1":
    FILES.append("compose/governance.yml")


def sources_dir() -> Path:
    """The contoso-sources checkout this stack pulls its vendors from.

    A SIBLING PATH, and the one place in this repository where that is right.
    Everything else installs from a published wheel because this platform must
    build on its own -- but the vendors are not a dependency of this platform,
    they are the world outside it, and they are mounted into containers as
    bytes rather than imported as code. Overridable, because pointing this at
    real vendors is exactly what production does.
    """
    return Path(os.environ.get("SOURCES", ROOT.parent / "contoso-sources")).resolve()


def vendor_fragment() -> Path:
    """Generate the vendor compose fragment from the sources declaration.

    Generated rather than checked in, so this repository cannot hold a stale
    copy of another repository's vendor list. If contoso-sources adds a vendor,
    the next `make up` stands it up.
    """
    src = sources_dir()
    decl = src / "sources.yaml"
    if not decl.exists():
        sys.exit(
            f"no vendor declaration at {decl}.\n\n"
            f"This platform pulls from the vendors contoso-sources declares --\n"
            f"the same ones fabric-platform-notebook-pipelines pulls from, which is what\n"
            f"makes the two runtimes' gold numbers comparable. Clone it beside\n"
            f"this repository, or set SOURCES=/path/to/contoso-sources."
        )
    # The bytes, not just the declaration. Without `make sources` over there the
    # vendors still START -- mokapi falls back to generating bodies from the
    # OpenAPI schema -- and every ingest step would land invented data that
    # looks entirely plausible until the numbers are compared. Refusing here is
    # the difference between a clear message and a silent wrong answer.
    data = src / "_data"
    if not data.is_dir() or not any(data.iterdir()):
        sys.exit(
            f"{data} is empty -- the vendors have no bytes to serve.\n\n"
            f"Run `make sources` in {src} first. Without it mokapi does not\n"
            f"fail: it generates bodies from the OpenAPI schema and answers\n"
            f"every request 200, so this pipeline would land invented data."
        )
    BUILD.mkdir(parents=True, exist_ok=True)
    out = BUILD / "sources.json"
    frag = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sources.py"), str(decl), str(src)],
        check=True, capture_output=True, text=True,
    ).stdout
    out.write_text(frag, encoding="utf-8")
    return out


def main() -> int:
    args = sys.argv[1:]
    files = list(FILES)
    files.append(str(vendor_fragment().relative_to(ROOT)))
    cmd = [
        "docker",
        "compose",
        "--env-file",
        "versions.env",
        "--profile",
        "governance",
    ]
    for f in files:
        cmd.extend(["-f", f])
    cmd.extend(args)
    env = os.environ.copy()
    env.setdefault("DELTA_DATA", str(Path("/tmp/contoso-dbx-delta")))
    Path(env["DELTA_DATA"]).mkdir(parents=True, exist_ok=True)
    env.setdefault("DATABRICKS_DATA", str(ROOT / "data"))
    Path(env["DATABRICKS_DATA"]).mkdir(parents=True, exist_ok=True)
    os.chmod(env["DATABRICKS_DATA"], 0o777)
    return subprocess.call(cmd, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
