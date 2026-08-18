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
    # THE CONTRACTS, ACTUALLY RUN. This step used to invoke `dbt run` alone and
    # then publish a snapshot listing five ODCS contracts by GLOBBING THEIR
    # FILENAMES off disk -- so the snapshot named five guarantees this runtime
    # had never once evaluated, and `compare_products` compared that list of
    # names against a runtime where they had genuinely passed. Two runtimes
    # "agreeing on contracts" while only one ran them is worse than not
    # comparing at all.
    #
    # A failure here stops the snapshot being written, which is the point: a
    # gold table that breaks its own contract is not a result to publish.
    subprocess.check_call(
        ["dbt", "test", "--project-dir", str(work), "--profiles-dir", str(work)],
        env=env,
    )
    w = t.workspace_client()
    # READ MONEY AT MONEY'S OWN GRAIN, and cast in the ENGINE rather than
    # rounding in Python.
    #
    # This engine returns `double` for `sum()` over a `decimal(19,4)` column --
    # measured: `typeof(sum(amount_usd))` on fct_sales answers `double`, while
    # every input column, silver through fct_sales, is decimal. Real Spark
    # widens decimal(19,4) to decimal(29,4); Sail widens it to binary floating
    # point. So the star's aggregate columns land as `double` and the total
    # arrives as 129341157.67000002 -- the right number carrying ~2e-8 of
    # float error, against the Fabric runtime's exact 129341157.6700.
    #
    # The cast recovers the value because money is defined to four decimal
    # places and the error is eight orders of magnitude below that. It does NOT
    # repair the column, and is not meant to: the demotion is an engine defect
    # worth reporting upstream, and this line only stops a serialisation
    # artefact from being mistaken for two runtimes disagreeing about revenue.
    # Cast to STRING in SQL as well, so the exact digits survive a JSON number.
    money = "CAST(CAST(coalesce(sum({}),0) AS DECIMAL(19,4)) AS STRING)"
    data = _query(
        w,
        wh.id,
        f"SELECT {money.format('revenue_usd')}, {money.format('cancelled_revenue_usd')}, "
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
