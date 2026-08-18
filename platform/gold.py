"""dbt-databricks over the product gold project. Adapter only; SQL is the product's."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from contoso_product import gold_dir
from target import CATALOG, T, WAREHOUSE


def _query(w, warehouse_id: str, statement: str) -> list:
    """Run one statement and return its rows, whatever shape they arrive in.

    NOT `statement_execution.execute_statement`. That returns a typed
    `ResultData`, and the SDK's model carries `data_array` and no `text` --
    so when this warehouse answers with `result.text` (the payload as a nested
    JSON string) the SDK drops it on the floor and every read looks like an
    empty table. Measured: the statement reported SUCCEEDED, `data_array` was
    None, and the star held four rows summing to 37 the whole time.

    `api_client.do` is the same transport and the same auth, minus the model
    that discards the field. Both shapes are then accepted rather than one
    being declared correct: real Databricks returns `data_array`, and a fix
    that only understood the emulator would break against the thing this
    platform exists to rehearse.
    """
    payload = w.api_client.do(
        "POST",
        "/api/2.0/sql/statements",
        body={"warehouse_id": warehouse_id, "statement": statement,
              "wait_timeout": "30s"},
    )
    state = (payload.get("status") or {}).get("state")
    if state != "SUCCEEDED":
        message = ((payload.get("status") or {}).get("error") or {}).get("message", "")
        raise SystemExit(f"statement did not succeed ({state}): {message[:200]}")
    result = payload.get("result") or {}
    if "data_array" in result:
        return result["data_array"] or []
    if "text" in result:
        return json.loads(result["text"]).get("data") or []
    return []


def main() -> int:
    t = T()
    wh = t.warehouse(WAREHOUSE)
    product = gold_dir()
    work = Path("gold")
    for name in ("models", "macros", "tests"):
        dest = work / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(product / name, dest)

    host = t.host
    dbt_host = host.replace("https://", "").replace("http://", "")
    path = wh.http_path
    uri = f"{host}{path}"
    env = os.environ.copy()
    env.update(
        {
            "DATABRICKS_HOST": dbt_host,
            "DATABRICKS_TOKEN": t.token,
            "DATABRICKS_HTTP_PATH": path,
            "DATABRICKS_CONNECTION_URI": uri,
            "DATABRICKS_CATALOG": CATALOG,
            "CONTOSO_SILVER_DATABASE": CATALOG,
            "CONTOSO_SILVER_SCHEMA": "silver",
            "LAKEHOUSE_ID": CATALOG,
            "DBT_PROFILES_DIR": str(work.resolve()),
            "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
        }
    )
    subprocess.check_call(
        ["dbt", "run", "--project-dir", str(work), "--profiles-dir", str(work)],
        env=env,
    )
    w = t.workspace_client()
    data = _query(
        w,
        wh.id,
        f"SELECT coalesce(sum(revenue_usd),0), coalesce(sum(cancelled_revenue_usd),0), "
        f"coalesce(sum(sale_lines),0) FROM {CATALOG}.gold.fct_revenue_summary",
    )
    if not data:
        # "COULD NOT READ" IS NOT "ZERO", and defaulting to 0 here published a
        # snapshot claiming this runtime built nothing while dbt had just
        # reported nine models built. compare_products then refused it as an
        # empty runtime -- the right call on the evidence, and the wrong
        # diagnosis. Measured: the star held 4 rows and revenue 37 the whole
        # time; the read was blind, not the warehouse.
        raise SystemExit(
            "gold built, but its aggregates came back with no rows -- refusing "
            "to publish a snapshot of zeros."
        )
    snapshot = {
        "revenue_usd": str(data[0][0]),
        "cancelled_revenue_usd": str(data[0][1]),
        "sale_lines": str(data[0][2]),
        "contracts": sorted(
            p.stem for p in (product / "tests").glob("*.sql")
        ),
        "runtime": "databricks",
        "catalog": CATALOG,
    }
    Path("product_snapshot.json").write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"gold snapshot {snapshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
