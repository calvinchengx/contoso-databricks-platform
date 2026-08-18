#!/usr/bin/env python3
"""Prerequisites, including the one this platform cannot install for you."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    missing = [n for n in ("docker", "uv", "make") if shutil.which(n) is None]
    if missing:
        print("missing:", ", ".join(missing), file=sys.stderr)
        return 1

    # THE VENDORS ARE NOT OPTIONAL, and their absence does not announce itself.
    # Without contoso-sources materialised, mokapi still starts and still
    # answers 200 -- it generates bodies from the OpenAPI schema instead of
    # serving the fixture. This pipeline would then land invented data, build a
    # green medallion on it, and publish numbers that agree with nothing.
    src = Path(os.environ.get("SOURCES", ROOT.parent / "contoso-sources"))
    if not (src / "sources.yaml").exists():
        print(
            f"missing the vendor declaration at {src / 'sources.yaml'}.\n"
            f"Clone calvinchengx/contoso-sources beside this repository, or set "
            f"SOURCES=/path/to/contoso-sources.",
            file=sys.stderr,
        )
        return 1
    data = src / "_data"
    if not data.is_dir() or not any(data.iterdir()):
        print(
            f"{data} is empty — run `make sources` in {src} first.\n"
            f"Without it the vendors serve schema-generated bodies rather than "
            f"their fixtures, and every number downstream is invented.",
            file=sys.stderr,
        )
        return 1

    print("doctor: docker, uv, make on PATH; vendors materialised at", src)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
