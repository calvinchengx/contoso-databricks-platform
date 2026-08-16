"""This platform's policy on top of the published databricks-target contract.

THE CONTRACT IS NOT WRITTEN HERE. It is `databricks-target`, published from
databricks-emulator's release and installed by this repo. This file adds only
the decisions that are this platform's: warehouse name, catalog name, where
landing lives, whether seed_secrets may run.
"""

from __future__ import annotations

import os
from pathlib import Path

import databricks_target

WORKSPACE = "contoso-analytics"
WAREHOUSE = "contoso_warehouse"
CATALOG = "contoso"
LANDING_NAME = "landing"
TABLES_NAME = "tables"


def T():
    return databricks_target.target()


def landing_path() -> str:
    """Engine-visible landing directory. Name-based; the scheme is the target's."""
    root = os.environ.get("CONTOSO_DELTA", "/data/delta")
    return f"{root}/{LANDING_NAME}"


def tables_path() -> str:
    root = os.environ.get("CONTOSO_DELTA", "/data/delta")
    return f"{root}/{TABLES_NAME}"


def host_delta() -> Path:
    """The same volume, as the operator's host sees it."""
    return Path(os.environ.get("DELTA_DATA", "/tmp/contoso-dbx-delta"))
