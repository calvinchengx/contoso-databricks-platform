# Contoso Databricks Platform

A consumer of [`databricks-emulator`](https://github.com/calvinchengx/databricks-emulator)
and of the portable [`contoso-data-product`](https://github.com/calvinchengx/contoso-data-product).

The Fabric sibling is [`contoso-data-platform`](https://github.com/calvinchengx/contoso-data-platform).
A data engineer writes bronze/silver Spark and gold dbt SQL once. This repo
wraps that product in Databricks Jobs / warehouse dbt / Unity Catalog.
OpenMetadata is the shared human catalog.

```sh
make doctor
make up
make verify
```

Switch emulator vs real with one setting. Code holds **names**.

```sh
DATABRICKS_TARGET=emulator make verify
DATABRICKS_TARGET=real DATABRICKS_HOST=https://adb-….azuredatabricks.net \
  DATABRICKS_TOKEN=… DATABRICKS_WAREHOUSE=contoso_warehouse make verify
```

See [RULES.md](RULES.md). Compare runtimes with
`contoso-data-product/scripts/compare_products.py`.

Apache-2.0.
