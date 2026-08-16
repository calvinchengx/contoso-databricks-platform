"""dbt-databricks over the product gold project. Adapter only; SQL is the product's."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from contoso_product import gold_dir
from target import CATALOG, T, WAREHOUSE


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
    (work / "macros" / "databricks_create_schema.sql").write_text(
        "{% macro databricks__create_schema(relation) -%}\n"
        "  {# Provision owns UC schemas. Unity Catalog OSS returns 400 when the schema exists. #}\n"
        "{%- endmacro %}\n",
        encoding="utf-8",
    )
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
    stmt = w.statement_execution.execute_statement(
        warehouse_id=wh.id,
        statement=(
            f"SELECT coalesce(sum(revenue_usd),0), coalesce(sum(cancelled_revenue_usd),0), "
            f"coalesce(sum(sale_lines),0) FROM {CATALOG}.gold.fct_revenue_summary"
        ),
    )
    data = []
    if stmt.result and getattr(stmt.result, "data_array", None):
        data = stmt.result.data_array
    snapshot = {
        "revenue_usd": str(data[0][0]) if data else "0",
        "cancelled_revenue_usd": str(data[0][1]) if data else "0",
        "sale_lines": str(data[0][2]) if data else "0",
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
