"""Register silver Delta paths as UC EXTERNAL tables. MANAGED is refused on the emulator."""

from __future__ import annotations

from target import CATALOG, T, tables_path

SILVER_TABLES = (
    "silver_customers",
    "silver_orders",
    "silver_quarantine_orders",
    "silver_product_hierarchy",
    "silver_fx_daily",
    "silver_web_customers",
    "silver_web_order_lines",
    "silver_party",
)


def main() -> int:
    t = T()
    w = t.workspace_client()
    wh = t.warehouse()
    root = tables_path()
    for name in SILVER_TABLES:
        loc = f"{root}/{name}"
        sql = (
            f"CREATE TABLE IF NOT EXISTS {CATALOG}.silver.{name} "
            f"USING delta LOCATION '{loc}'"
        )
        stmt = w.statement_execution.execute_statement(warehouse_id=wh.id, statement=sql)
        state = stmt.status.state.value if stmt.status and stmt.status.state else None
        print(f"  {name}: {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
