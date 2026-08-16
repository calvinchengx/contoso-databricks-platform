# Rules for this codebase

This platform runs against **real Databricks**. `databricks-emulator` is one
target it can be pointed at — not the thing it is built for. Every rule below
exists to keep that true.

## 1. Databricks, not the emulator

| | |
|---|---|
| **Rule** | Every difference between the emulator and real Databricks lives in the published `databricks-target` package, selected by `DATABRICKS_TARGET=emulator\|real`. `platform/target.py` adds only this platform's policy (names, landing path). |
| **Why** | A localhost URL or a seeded PAT anywhere else is a workaround that ships to production. |
| **Enforced by** | `test_emulator_only_in_target_resolver` |

| | |
|---|---|
| **Rule** | TLS verification is never hardcoded off on the real target. |
| **Why** | `skip_verify=True` against production is a security defect. The resolver sets `tls_verify=True` on `real`. |
| **Enforced by** | databricks-target unit tests |

| | |
|---|---|
| **Rule** | Credentials come from a named secret scope (AKV-backed locally via keyvault-emulator, the customer's scope or vault in production). Never from the source tree. |
| **Why** | A key in a repository has already leaked. |
| **Enforced by** | `seed_secrets.py` calls `t.refuse_seed_secrets()` — raises on `DATABRICKS_TARGET=real` |

| | |
|---|---|
| **Rule** | Workspace, warehouse, catalog, and schema are addressed **by name**. Ids are resolved per target and never written into product code. |
| **Why** | Ids never match across emulator and real. |
| **Enforced by** | judgement — read `platform/target.py` |

## 2. The product is installed, never restated

| | |
|---|---|
| **Rule** | Bronze, silver, gold SQL, and ODCS contracts come from `contoso-data-product`. This repo wraps them. |
| **Why** | A second `fct_sales.sql` is how "no DE code change" dies. |
| **Enforced by** | `test_product_is_imported_not_restated` |

| | |
|---|---|
| **Rule** | Unity Catalog is the engine catalog (`contoso.silver.*` / `contoso.gold.*`). OpenMetadata is the human catalog. |
| **Why** | Grants and three-part names belong to UC. Glossary, contracts, and the dual-runtime product entity belong to OM. |
| **Enforced by** | judgement |

## 3. Real-target switch

```
DATABRICKS_TARGET=real
DATABRICKS_HOST=https://adb-<id>.azuredatabricks.net
DATABRICKS_TOKEN=...
DATABRICKS_WAREHOUSE=contoso_warehouse
DATABRICKS_CATALOG=contoso
AZURE_KEY_VAULT_URL=https://<vault>.vault.azure.net
OM_URL=https://<openmetadata>/api/v1
```

`make verify` is the same command. Seed-secrets refuse to run. No CI against
real Databricks — the toggle is the contract; the emulator leg is the witness.

## What this platform will not claim

- Power BI / DAX / XMLA
- Photon / DBR compatibility
- UC grants (emulator 501 until they deny)
- Jobs `dbt_task` (gold is warehouse `dbt-databricks`)
- MANAGED UC tables on the emulator (EXTERNAL only)
- Fabric notebooks running unchanged (the *logic* is shared; the item format is not)
