# Contoso Databricks Platform

[![CI](https://github.com/calvinchengx/databricks-platform-jobs/actions/workflows/ci.yml/badge.svg)](https://github.com/calvinchengx/databricks-platform-jobs/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A Databricks analytics platform built on
[`databricks-emulator`](https://github.com/calvinchengx/databricks-emulator),
running the portable
[`contoso-data-product`](https://github.com/calvinchengx/contoso-data-product)
end to end: landing, bronze, silver in Spark, gold in dbt, catalogued in Unity
Catalog and OpenMetadata.

Its sibling is
[fabric-platform-notebook-pipelines](https://github.com/calvinchengx/fabric-platform-notebook-pipelines),
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
# The vendors this platform pulls from. NOT a dependency of this repository --
# they are the world outside it, mounted into containers as bytes rather than
# imported as code, and they are the same vendors fabric-platform-notebook-pipelines
# pulls from, which is the only reason the two runtimes' numbers can be
# compared at all.
git clone https://github.com/calvinchengx/contoso-sources
make -C contoso-sources sources

git clone https://github.com/calvinchengx/databricks-platform-jobs
cd databricks-platform-jobs
make doctor     # what is ready, and what is not
make up         # start the stack, vendors included
make verify     # run the platform end to end
```

## What `make verify` runs

Eight steps, in order, each a real call against the emulator:

| step | |
|---|---|
| `provision` | create the named warehouse, UC catalog and schemas |
| `seed_secrets` | put the source credentials in the secret scope |
| `ingest` | pull four vendors over their own transports and land the bytes verbatim |
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

## The vendors

Four source systems, four transports, and none of them is Databricks:

| vendor | transport | what makes it awkward |
|---|---|---|
| Contoso POS | paged CSV + JSON Lines over HTTP | 95 MB export, paged; the parts are landed as parts |
| Contoso Web | paged JSON arrays over HTTP | orders arrive **nested**, and accounts are keyed on email — no customer id |
| Contoso Reference | binary Parquet over HTTP | corrupts *quietly*, so the ingest verifies the vendor's published sha256 |
| Contoso ERP | Postgres → Debezium → Kafka | a **change stream**, not a table read |

They are declared by [contoso-sources](https://github.com/calvinchengx/contoso-sources),
not here. `scripts/sources.py` reads that declaration and emits a compose
fragment, so adding a vendor there stands one up here — and both this platform
and fabric-platform-notebook-pipelines pull the *same bytes from the same pinned
simulator*. That is load-bearing: gold agreeing across two engines means
something only if the inputs were identical, and a vendor block hand-written in
this repository would make this platform's data its own.

**The failure this guards against is silent.** Without `make sources` in that
repository, mokapi does not fail — it generates bodies from the OpenAPI schema
and answers every request `200`, wrong API key included. The pipeline would go
green over invented data. `make doctor` refuses to start, `scripts/compose.py`
refuses to compose, and every ingest step sends a deliberately wrong key first
and stops unless the vendor answers `401`.

## The stack

`make up` starts **14 services**: the emulator, Sail as the Spark engine, a
Spark agent, the Unity Catalog OSS sidecar, OpenMetadata with its own Postgres,
OpenSearch and a one-shot migration — and the six that are the vendors (three
mokapi instances, a Postgres, Redpanda, and Debezium with its seeder).

One more profile exists and is off by default, because `make verify` does not
need it: `identity` adds
[entra-emulator](https://github.com/calvinchengx/entra-emulator) and
[azure-keyvault-emulator](https://github.com/calvinchengx/azure-keyvault-emulator)
for the AKV-backed secret scope.

Host ports are `181xx`, `19094` and `55434`, chosen clear of
fabric-platform-notebook-pipelines's `180xx` / `19092` / `55432` so both stacks can run at
once. `test_vendor_host_ports_do_not_collide_with_the_fabric_platform` holds
that line.

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
[`fabric-platform-notebook-pipelines`](https://github.com/calvinchengx/fabric-platform-notebook-pipelines),
this repo, and
[`snowflake-platform-tasks`](https://github.com/calvinchengx/snowflake-platform-tasks).
The transforms they share live in
[`contoso-data-product`](https://github.com/calvinchengx/contoso-data-product).

The emulators underneath are the [**azure-emulators**](https://github.com/calvinchengx/azure-emulators) family — entra, Key
Vault, ARM, Fabric, API Management and
[`databricks-emulator`](https://github.com/calvinchengx/databricks-emulator).
