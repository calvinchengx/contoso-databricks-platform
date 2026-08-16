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
    (work / "macros" / "databricks_adapter_stubs.sql").write_text(
        "{% macro databricks__create_schema(relation) -%}\n"
        "  {# Provision owns UC schemas. Unity Catalog OSS returns 400 when the schema exists. #}\n"
        "{%- endmacro %}\n"
        "\n"
        "{%- macro get_create_row_filter_clause(relation) -%}\n"
        "{%- endmacro -%}\n"
        "\n"
        "{%- macro drop_row_filter_if_exists(relation) -%}\n"
        "{%- endmacro -%}\n"
        "\n"
        "{%- macro fetch_row_filters(relation) -%}\n"
        "  {{ return(none) }}\n"
        "{%- endmacro -%}\n"
        "\n"
        "{# UC OSS rejects CREATE OR REPLACE. Models stay the product's; only this DDL. #}\n"
        "{% macro get_create_table_sql(target_relation, columns, compiled_code) %}\n"
        "  {%- set catalog_relation = adapter.build_catalog_relation(config.model) -%}\n"
        "  {%- set contract = config.get('contract') -%}\n"
        "  {%- set contract_enforced = contract and contract.enforced -%}\n"
        "  {%- if contract_enforced -%}\n"
        "    {{ get_assert_columns_equivalent(compiled_code) }}\n"
        "  {%- endif -%}\n"
        "  create table {{ target_relation.render() }}\n"
        "  {{ get_column_and_constraints_sql(target_relation, columns) }}\n"
        "  {{ file_format_clause(catalog_relation) }}\n"
        "  {{ databricks__options_clause(catalog_relation) }}\n"
        "  {{ partition_cols(label=\"partitioned by\") }}\n"
        "  {{ get_create_row_filter_clause(target_relation) }}\n"
        "  {{ liquid_clustered_cols() }}\n"
        "  {{ clustered_cols(label=\"clustered by\") }}\n"
        "  {{ location_clause(catalog_relation) }}\n"
        "  {{ comment_clause() }}\n"
        "  {{ tblproperties_clause() }}\n"
        "{% endmacro %}\n"
        "\n"
        "{% macro databricks__create_table_as(temporary, relation, compiled_code, language='sql') -%}\n"
        "  {%- set catalog_relation = adapter.build_catalog_relation(config.model) -%}\n"
        "  {%- if language == 'sql' -%}\n"
        "    {%- if temporary -%}\n"
        "      {{ create_temporary_view(relation, compiled_code) }}\n"
        "    {%- else -%}\n"
        "      create table {{ relation.render() }}\n"
        "      {%- set contract_config = config.get('contract') -%}\n"
        "      {% if contract_config and contract_config.enforced %}\n"
        "        {{ get_assert_columns_equivalent(compiled_code) }}\n"
        "        {%- set compiled_code = get_select_subquery(compiled_code) %}\n"
        "      {% endif %}\n"
        "      {{ file_format_clause(catalog_relation) }}\n"
        "      {{ databricks__options_clause(catalog_relation) }}\n"
        "      {{ partition_cols(label=\"partitioned by\") }}\n"
        "      {{ get_create_row_filter_clause(relation) }}\n"
        "      {{ liquid_clustered_cols() }}\n"
        "      {{ clustered_cols(label=\"clustered by\") }}\n"
        "      {{ location_clause(catalog_relation) }}\n"
        "      {{ comment_clause() }}\n"
        "      {{ tblproperties_clause() }}\n"
        "      as\n"
        "      {{ compiled_code }}\n"
        "    {%- endif -%}\n"
        "  {%- elif language == 'python' -%}\n"
        "    {{ databricks__py_write_table(compiled_code=compiled_code, target_relation=relation) }}\n"
        "  {%- endif -%}\n"
        "{%- endmacro -%}\n",
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
