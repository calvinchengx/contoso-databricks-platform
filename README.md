# Contoso Databricks Platform

[![CI](https://github.com/calvinchengx/contoso-databricks-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/calvinchengx/contoso-databricks-platform/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A Databricks analytics platform built on
[`databricks-emulator`](https://github.com/calvinchengx/databricks-emulator),
running the portable
[`contoso-data-product`](https://github.com/calvinchengx/contoso-data-product)
end to end: landing, bronze, silver in Spark, gold in dbt, catalogued in Unity
Catalog and OpenMetadata.

Its sibling is
[contoso-fabric-platform](https://github.com/calvinchengx/contoso-fabric-platform),
which runs **the same data product** on Microsoft Fabric. That pairing is the
point of both repositories: a data engineer writes bronze/silver Spark and gold
dbt SQL once, and the platform it lands on is a wrapper, not a rewrite.

It runs against a **published release**. `databricks-target`, the client that
resolves the emulator/real toggle, is installed from the wheel a
`databricks-emulator` release ships, not from that repository's source tree, so
anything that works here works for anyone holding the same release. The image
tag and the wheel come from the same release, and
`test_the_target_wheel_matches_the_pinned_release` fails if they drift.

[`contoso-data-product`](https://github.com/calvinchengx/contoso-data-product),
the transforms and gold SQL themselves, comes from its own release wheel on the
same terms. **So this repository clones and builds on its own**, with no sibling
checkouts, and its CI checks out one repository and nothing else. That absence is
the proof: reach for a source tree again and `uv sync` fails there.

```sh
git clone https://github.com/calvinchengx/contoso-databricks-platform
cd contoso-databricks-platform
make doctor     # what is ready, and what is not
make up         # start the stack
make verify     # run the platform end to end
```

## What `make verify` runs

Eight steps, in order, each a real call against the emulator:

| step | |
|---|---|
| `provision` | create the named warehouse, UC catalog and schemas |
| `seed_secrets` | put the source credentials in the secret scope |
| `ingest` | land the vendor bytes |
| `bronze` | landing to bronze Delta, **the product's** `run_bronze` |
| `silver` | bronze to silver, **the product's** `run_silver` |
| `register` | silver Delta paths as UC **EXTERNAL** tables |
| `gold` | `dbt-databricks` over the product's gold project |
| `govern` | publish the same entities to OpenMetadata |

Only `provision`, `register` and the two catalog steps are this repository's
code. `bronze`, `silver` and every line of gold SQL come from the product
package, which is what makes the Fabric comparison meaningful.

**Two catalogs, deliberately.** Unity Catalog is the *engine* catalog: grants
and three-part names (`contoso.silver.*`, `contoso.gold.*`) belong to it.
OpenMetadata is the *human* catalog: glossary, ODCS contracts and the
dual-runtime product entity belong there. Neither is a copy of the other.

## The stack

`make up` starts **8 services**: the emulator, Sail as the Spark engine, a
Spark agent, the Unity Catalog OSS sidecar, and OpenMetadata with its own
Postgres, OpenSearch and a one-shot migration.

Two more profiles exist and are off by default, because `make verify` does not
need either: `identity` adds
[entra-emulator](https://github.com/calvinchengx/entra-emulator) and
[azure-keyvault-emulator](https://github.com/calvinchengx/azure-keyvault-emulator)
for the AKV-backed secret scope, and `sources` adds a mokapi vendor API and a
Postgres ERP. `ingest` lands sample bytes itself, so a first run needs nothing
outside the default set.

## Emulator or real Databricks, one setting

The code holds **names**. Ids never match across a local emulator and a real
workspace, so they are resolved per target and never written into product code.

```sh
DATABRICKS_TARGET=emulator make verify

DATABRICKS_TARGET=real DATABRICKS_HOST=https://adb-....azuredatabricks.net \
  DATABRICKS_TOKEN=... DATABRICKS_WAREHOUSE=contoso_warehouse make verify
```

`make verify` is the same command either way. The contract behind the toggle is
the `databricks-target` package, not restated here;
[`platform/target.py`](platform/target.py) adds only this platform's own policy
(warehouse name, catalog name, where landing lives). On the real target
`seed_secrets` **refuses to run** rather than writing test credentials into a
customer's scope.

There is no CI leg against real Databricks. The toggle is the contract and the
emulator leg is the witness, which is stated plainly rather than implied by a
green tick.

## How it is pinned

[`versions.env`](versions.env) pins every image and is read directly by
`docker compose --env-file`, so the pins are stated once. Never `latest`: a
green run must say **which** release it verified.

## Rules

[RULES.md](RULES.md) holds the rules this codebase is built on, and each one
names the test that enforces it or says `judgement` where nothing does.

```sh
make test    # repo-boundary tests, no Docker
make lint
```

`test_product_is_imported_not_restated` is the load-bearing one: it fails if
this repository ever grows its own copy of a transform or a gold model.

## Comparing the two runtimes

Two green pipelines do not prove two runtimes agree. `compare_products.py` in
the product repository fails unless Fabric and Databricks report the same
`fct_revenue_summary` aggregates and the same contract names.

Apache-2.0.

## Related projects

The same Contoso data, on three engines:
[`contoso-fabric-platform`](https://github.com/calvinchengx/contoso-fabric-platform),
this repo, and
[`contoso-snowflake-platform`](https://github.com/calvinchengx/contoso-snowflake-platform).
The transforms they share live in
[`contoso-data-product`](https://github.com/calvinchengx/contoso-data-product).

The emulators underneath are the [**azure-emulators**](https://github.com/calvinchengx/azure-emulators) family — entra, Key
Vault, ARM, Fabric, API Management and
[`databricks-emulator`](https://github.com/calvinchengx/databricks-emulator).
