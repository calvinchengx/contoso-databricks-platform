"""Repo-boundary tests. No Docker, no emulator."""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_pins_are_immutable():
    pins = {}
    for line in (ROOT / "versions.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            pins[k.strip()] = v.strip()
    assert "DATABRICKS_EMULATOR_VERSION" in pins
    assert "SAIL_VERSION" in pins
    assert "UC_VERSION" in pins
    mutable = {"latest", "stable", "main", "edge"}
    for k, v in pins.items():
        assert v.lower() not in mutable, f"{k}={v}"


def test_compose_reads_every_pin():
    composed = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "compose").glob("*.yml"))
    for line in (ROOT / "versions.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k = line.split("=", 1)[0].strip()
            assert "${" + k in composed, k


def test_makefile_survives_cmd_exe():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    for bad in (" | ", " && ", " `", " rm "):
        for line in text.splitlines():
            if line.startswith("#") or line.startswith("ifeq") or line.startswith("  SHELL"):
                continue
            if ":" in line and not line.startswith("\t") and not line.startswith(" "):
                continue
            if line.startswith("\t"):
                assert bad not in line, f"cmd.exe-unsafe recipe: {line!r}"


def test_emulator_only_in_target_resolver():
    """localhost / seeded PAT must not appear outside platform/target.py and compose."""
    allowed = {
        ROOT / "platform" / "target.py",
        ROOT / "platform" / "spark_session.py",
        ROOT / "platform" / "gold.py",
        ROOT / "platform" / "govern.py",
        ROOT / "gold" / "profiles.yml",
    }
    hits = []
    for p in (ROOT / "platform").glob("*.py"):
        if p in allowed:
            continue
        text = p.read_text(encoding="utf-8")
        if "localhost:8447" in text or "admin.pat" in text:
            hits.append(p.name)
    assert hits == []


def test_product_is_imported_not_restated():
    bronze = (ROOT / "platform" / "bronze.py").read_text(encoding="utf-8")
    silver = (ROOT / "platform" / "silver.py").read_text(encoding="utf-8")
    assert "from contoso_product import run_bronze" in bronze
    assert "from contoso_product import run_silver" in silver
    assert "decimal(19,4)" not in silver
