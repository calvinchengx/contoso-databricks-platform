"""Repo-boundary tests. No Docker, no emulator."""

from __future__ import annotations

import pathlib
import re

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


def test_the_locked_wheel_matches_the_pinned_release():
    """The LOCKFILE is what decides which client actually runs.

    test_the_target_wheel_matches_the_pinned_release checks pyproject.toml,
    and that is the declaration. It is not what gets installed: every make
    target runs `uv run --frozen`, and --frozen resolves from uv.lock without
    reading pyproject.toml at all. So a bump that moves versions.env and
    pyproject.toml but not the lock leaves the pin pointing one way and the
    installed client pointing the other, with nothing between them.

    Measured, not hypothesised: with pyproject at v0.2.5 and uv.lock left at
    v0.2.4, `uv run --frozen` installed databricks_target from the v0.2.4
    wheel, reported success, and named the old URL in its direct_url.json.
    That is the new image running against the old client -- the exact
    mismatch this repository exists to notice, arriving silently.
    """
    pins = {}
    for line in (ROOT / "versions.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            pins[k.strip()] = v.strip()
    version = pins["DATABRICKS_EMULATOR_VERSION"]

    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    stale = [
        line.strip()
        for line in lock.splitlines()
        if "databricks-emulator/releases/download/" in line
        and f"/download/v{version}/" not in line
    ]
    assert not stale, (
        f"uv.lock still installs databricks-target from a release other than "
        f"the pinned v{version}. Run `python scripts/set_release.py {version}` "
        f"AND `uv lock` -- the lockfile is what --frozen installs.\n  "
        + "\n  ".join(stale)
    )


def test_the_acceptance_run_adopts_every_file_the_bump_touches():
    """A half-adopted pin publishes a main that fails its own test.

    The adopt step commits what set_release.py changed. set_release.py changes
    versions.env and pyproject.toml, and `uv lock` then changes uv.lock. Commit
    only the first and main carries a pin the other two contradict --
    test_the_target_wheel_matches_the_pinned_release fails on the very commit
    the acceptance run pushed as verified.
    """
    wf = (ROOT / ".github" / "workflows" / "acceptance.yml").read_text(encoding="utf-8")
    adopt = wf[wf.index("Adopt the version this run just verified") :]
    for name in ("versions.env", "pyproject.toml", "uv.lock"):
        assert adopt.count(name) >= 2, (
            f"the adopt step must both TEST and COMMIT {name}; a file left out "
            f"of either half is a pin that main contradicts"
        )
    assert "uv lock" in wf, (
        "the dispatch must refresh the lockfile after set_release.py, or the "
        "run verifies the new image against the client the lock still names"
    )


def test_acceptance_checks_out_every_repository_the_stack_reads():
    """doctor.py and compose.py hard-require a contoso-sources checkout.

    `sources_dir()` resolves `ROOT.parent / "contoso-sources"` unless SOURCES
    overrides it, and both scripts exit rather than guess. The acceptance job
    checked out three repositories and not that one, so `make doctor` failed at
    the first step with "missing the vendor declaration" -- an emulator release
    could not be verified at all, for a reason that had nothing to do with the
    emulator.

    Measured: run 32193426410, the first acceptance run after the vendor
    declaration became load-bearing, died 12 seconds in.

    The declaration alone is not enough either. compose.py checks for the
    materialised bytes under _data/ and says so ("Run `make sources` in ...
    first"), because mokapi serves the exports from that directory; an
    unmaterialised checkout stands up vendors that answer nothing.
    """
    raw = (ROOT / ".github" / "workflows" / "acceptance.yml").read_text(encoding="utf-8")
    # Comments are stripped before anything is looked up. The prose above the job
    # names the targets it is explaining -- `make verify` appears in a comment far
    # above the step that runs it -- so `raw.index` finds the comment and the
    # ordering below fails on a workflow that is correctly ordered. Presence is
    # checked here too: a commented-out checkout must not satisfy this test.
    wf = "\n".join(ln for ln in raw.splitlines() if not ln.lstrip().startswith("#"))
    assert "repository: calvinchengx/contoso-sources" in wf, (
        "acceptance must check out contoso-sources beside this repository, or "
        "doctor.py exits before the emulator is ever started"
    )
    assert "make sources" in wf, (
        "checking out contoso-sources is half of it -- without `make sources` "
        "the exports under _data/ do not exist and compose.py refuses"
    )
    materialise = wf.index("make sources")
    for target in ("make doctor", "make up", "make verify"):
        assert materialise < wf.index(target), (
            f"`make sources` must run before `{target}`; the vendors have to "
            f"exist before anything reads them"
        )


def test_the_platform_holds_no_product():
    """The platform is compose, pins, vendors and scripts. Nothing Contoso.

    This repository used to contain its own product: eighteen step modules --
    ingest, the medallion runners, the target binding -- sitting in `platform/`
    beside the compose files. That made the cell's name a half-truth, and it
    made "a second product can use this platform unchanged" untestable, because
    there was no second thing to point it at.

    The split line is `00-family.md`'s, not this file's invention: a platform
    holds no Contoso name and no product file. `fabric-platform-airflow3`, the
    cell that already got this right, has no `platform/` directory at all —
    it takes PRODUCT as a path and the product carries its own task code.
    """
    assert not (ROOT / "platform").exists(), (
        "a platform/ directory is back — the product's steps belong in the leaf"
    )

    # The Makefile may name the vendors repo (it consumes one) but never a
    # product: `./product` is a mount point, and a default naming Contoso would
    # put the identifier straight back.
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for line in makefile.splitlines():
        code = line.split("#", 1)[0]
        if "contoso" in code.lower() and "contoso-sources" not in code:
            raise AssertionError(f"the Makefile names a product: {line.strip()!r}")


def test_the_product_is_supplied_as_a_path():
    """PRODUCT is how the platform learns what to run, and it is a PATH.

    A name would mean this platform could only ever run one product, which is
    the property the family is trying to demonstrate is false.
    """
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert re.search(r"^PRODUCT \?= \./product$", makefile, re.M), (
        "PRODUCT must default to the ./product mount point"
    )
    # `cd &&` is not available on cmd.exe, which is why the steps run through
    # `uv run --directory` instead.
    assert "--directory $(PRODUCT)" in makefile
