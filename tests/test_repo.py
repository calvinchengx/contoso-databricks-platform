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
        if "127.0.0.1:18470" in text or "admin.pat" in text:
            hits.append(p.name)
    assert hits == []


def test_product_is_imported_not_restated():
    bronze = (ROOT / "platform" / "bronze.py").read_text(encoding="utf-8")
    silver = (ROOT / "platform" / "silver.py").read_text(encoding="utf-8")
    assert "from contoso_product import run_bronze" in bronze
    assert "from contoso_product import run_silver" in silver
    assert "decimal(19,4)" not in silver


def test_the_target_wheel_matches_the_pinned_release():
    """The client wheel and the image come from the SAME release.

    `databricks-target` is installed from a published wheel rather than from
    the emulator's source tree, which is what makes this repository a consumer:
    it builds from what a release ships, so anything that works here works for
    anyone with the same release.

    That puts the version in two files, and a copied version with nothing
    checking it is a second source of truth that drifts. This is the check.
    A workspace binary and a client that disagree about the contract is the one
    mismatch this repository exists to notice.
    """
    pins = {}
    for line in (ROOT / "versions.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            pins[k.strip()] = v.strip()
    version = pins["DATABRICKS_EMULATOR_VERSION"]

    proj = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "databricks-target = { url =" in proj, (
        "databricks-target must come from the published wheel, not a path: a "
        "consumer that reads the emulator's source tree proves nothing"
    )
    expected = f"databricks-emulator/releases/download/v{version}/"
    assert expected in proj, (
        f"the databricks-target wheel does not come from the pinned release "
        f"v{version}. Run `python scripts/set_release.py {version}`."
    )


def test_no_dependency_comes_from_a_sibling_checkout():
    """This repository must clone and build on its own.

    Both `databricks-target` and `contoso-data-product` install from wheels
    their releases publish. A `path = "../…"` source is invisible to everyone
    who already has the siblings on disk, and fails for everyone who does not,
    which is the whole population this repository claims to serve.

    CI asserts the same thing by checking out one repository and nothing else.
    This test is the fast version, and it names the rule.
    """
    proj = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in proj.splitlines()
        if "path = " in line and "../" in line and not line.lstrip().startswith("#")
    ]
    assert not offenders, (
        "a dependency resolves from a sibling checkout, so a lone clone cannot "
        "build: " + str(offenders)
    )


def test_set_release_moves_only_the_emulator_pin(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "set_release", ROOT / "scripts" / "set_release.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = (ROOT / "versions.env").read_text(encoding="utf-8")
    new, moved = mod.set_version(text, "0.2.0")
    assert "DATABRICKS_EMULATOR_VERSION" in moved
    assert "DATABRICKS_EMULATOR_VERSION=0.2.0" in new
    assert "SAIL_VERSION=" in new
    sail = [ln for ln in text.splitlines() if ln.startswith("SAIL_VERSION=")][0]
    assert sail in new


def test_ingest_pulls_from_vendors_rather_than_writing_fixtures():
    """No ingest step may author the data it claims to have ingested.

    This platform used to write a handful of literal rows here -- three
    customers, two orders -- and every number it published downstream was then
    true about a fixture it had invented. Worse, it looked identical to a real
    run: green pipeline, populated star, a gold snapshot with numbers in it.
    The defect was only visible by comparing against the Fabric runtime, which
    is precisely the comparison the invented fixture made meaningless.

    So the rule is structural: an ingest step fetches, it does not compose. A
    literal row written to the landing directory is the failure this catches.
    """
    import re

    root = ROOT / "platform"
    offenders = []
    for p in sorted(root.glob("ingest*.py")):
        text = p.read_text(encoding="utf-8")
        # A docstring may describe the old behaviour; code may not perform it.
        body = re.sub(r'"""(?:.|\n)*?"""', "", text)
        for marker in ("customer_id,name,email", "write_text("):
            if marker in body:
                offenders.append(f"{p.name}: {marker}")
    assert not offenders, (
        "an ingest step is composing bytes rather than fetching them: "
        + str(offenders)
    )


def test_no_vendor_credential_is_written_in_this_repository():
    """Keys come from the vendor or the environment, never from the tree.

    `seed_secrets.py` used to carry `string_value="pos-dev-key"` -- a
    credential in the source tree, and the WRONG one: the vendor issues
    `pos-key-8843-dev`, so anything reading that scope entry would have been
    refused 401 by the very vendor it was seeded for. Both halves of that are
    worth failing on.
    """
    suspicious = []
    for p in sorted((ROOT / "platform").glob("*.py")):
        text = p.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.lstrip().startswith("#"):
                continue
            if "string_value=" in line and '"' in line.split("string_value=", 1)[1]:
                suspicious.append(f"{p.name}: {line.strip()}")
    assert not suspicious, (
        "a literal credential is being written into the secret scope: "
        + str(suspicious)
    )


def test_the_vendor_stack_is_generated_from_the_sources_declaration():
    """The vendors are contoso-sources', not this repository's.

    Two platforms' gold numbers are comparable only if the bytes were
    identical, and identical bytes means the same declaration, the same
    fixtures and the same pinned simulator. A vendor block hand-written here
    would be this platform's own data wearing the family's name.
    """
    assert not (ROOT / "compose" / "sources.yml").exists(), (
        "compose/sources.yml is back — vendors belong to contoso-sources, and "
        "a local copy is how the two runtimes quietly stop comparing"
    )
    compose = (ROOT / "scripts" / "compose.py").read_text(encoding="utf-8")
    assert "sources.yaml" in compose and "_data" in compose, (
        "compose.py must generate the vendor fragment from the sources "
        "declaration, and must refuse to start when the fixtures are absent"
    )


def test_the_generator_refuses_a_vendor_kind_it_cannot_run(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "vendor_sources", ROOT / "scripts" / "sources.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    decl = {"vendors": [{"name": "nope", "kind": "telepathy"}]}
    try:
        mod.fragment(decl, str(tmp_path), {"MOKAPI_VERSION": "0.50.0"})
    except SystemExit as exc:
        assert "telepathy" in str(exc)
    else:  # pragma: no cover - the assertion IS the test
        raise AssertionError("an unknown vendor kind was quietly accepted")


def test_vendor_host_ports_do_not_collide_with_the_fabric_platform():
    """Both stacks run on one developer machine, often at the same time.

    A collision does not report itself as a collision: compose fails to bind
    and the message names a port, not the two platforms fighting over it. The
    Fabric platform owns 180xx / 19092 / 55432; this one owns 181xx / 19094 /
    55434.
    """
    text = (ROOT / "scripts" / "sources.py").read_text(encoding="utf-8")
    ns: dict = {}
    for line in text.splitlines():
        if line.startswith(("HOST_BASE", "ERP_DB_HOST_PORT", "ERP_BROKER_HOST_PORT",
                            "ERP_CONNECT_HOST_PORT")):
            k, v = line.split("=", 1)
            ns[k.strip()] = int(v.split("#")[0].strip())
    fabric = {18090, 18091, 18092, 18081, 18082, 18084, 18083, 19092, 55432}
    ours = {ns["HOST_BASE"] + i for i in range(3)} | {
        ns["ERP_DB_HOST_PORT"], ns["ERP_BROKER_HOST_PORT"], ns["ERP_CONNECT_HOST_PORT"]}
    assert not (ours & fabric), f"host ports collide with fabric-platform-notebook-pipelines: {ours & fabric}"


def test_gold_records_the_measurement_and_still_fails():
    """A failing contract must not erase the numbers, or hide behind them.

    Recording a measurement and asserting a pass are two things. This step used
    to do both at once: a failing contract stopped the snapshot being written,
    so the failure took the evidence with it — and this runtime's gold is
    correct, its aggregates identical to Fabric's, with the two failing
    contracts failing on an emulator defect rather than a product one. Refusing
    to publish removed the cell from the comparison the family exists to make.

    Both halves are load-bearing, so both are checked: the snapshot is written
    BEFORE the exit, and the exit still happens.
    """
    gold = (ROOT / "platform" / "gold.py").read_text(encoding="utf-8")
    write = gold.index('Path("product_snapshot.json").write_text')
    raise_after = gold.index("gold's numbers were recorded, and this run FAILED")
    assert write < raise_after, (
        "the snapshot must be written before the run fails, or a failing "
        "contract erases the evidence along with the pass"
    )
    assert "contract_failures" in gold, (
        "the failures must travel with the numbers; a snapshot recorded "
        "without them is the stale-snapshot failure again"
    )


def test_contract_results_come_from_the_test_invocation():
    """dbt overwrites run_results.json, and `dbt run` shares the target dir.

    Read without checking which command wrote it, the file reports a `dbt run`:
    nine model rows, zero failures. Believed, that publishes a snapshot
    asserting NO contract failures on a run where two failed — the precise
    false green this design exists to prevent. Measured, not hypothesised: it
    is what the artefact said when inspected after a later `dbt run`.
    """
    gold = (ROOT / "platform" / "gold.py").read_text(encoding="utf-8")
    assert 'which != "test"' in gold, (
        "gold.py must refuse a run_results.json written by anything other than "
        "`dbt test` before reporting contract results from it"
    )
