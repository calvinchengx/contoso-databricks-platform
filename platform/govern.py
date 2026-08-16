"""Publish the same product entities to OpenMetadata. UC remains the engine catalog."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import requests
from contoso_product.contracts import DOMAIN, METRICS, PRODUCT_NAME, contract_id

OM = os.environ.get("OM_URL", "http://localhost:18585/api/v1").rstrip("/")
OM_USER = os.environ.get("OM_USER", "admin@open-metadata.org")
OM_PASSWORD = os.environ.get("OM_PASSWORD", "admin")

S = requests.Session()


def login() -> None:
    r = S.post(
        f"{OM}/users/login",
        json={
            "email": OM_USER,
            "password": base64.b64encode(OM_PASSWORD.encode()).decode(),
        },
        timeout=60,
    )
    r.raise_for_status()
    S.headers["Authorization"] = f"Bearer {r.json()['accessToken']}"


def put(path: str, body: dict) -> dict:
    r = S.put(f"{OM}/{path}", json=body, timeout=60)
    r.raise_for_status()
    return r.json() if r.content else {}


def main() -> int:
    login()
    put(
        "domains",
        {
            "name": DOMAIN,
            "displayName": "Contoso Commerce",
            "description": "One product, two runtimes (Fabric and Databricks).",
        },
    )
    put(
        "services/databaseServices",
        {
            "name": "contoso-databricks",
            "serviceType": "Databricks",
            "connection": {
                "config": {
                    "type": "Databricks",
                    "hostPort": os.environ.get("DATABRICKS_HOST", "http://localhost:18470"),
                    "httpPath": "/sql/1.0/endpoints/wh-1",
                    "token": "not-stored",
                }
            },
        },
    )
    contracts = [contract_id("fct_revenue_summary")]
    for metric in METRICS:
        put(
            "metrics",
            {
                "name": metric,
                "displayName": metric,
                "description": f"Product metric {metric} on {PRODUCT_NAME}",
            },
        )
    catalogued = {
        "product": PRODUCT_NAME,
        "domain": DOMAIN,
        "service": "contoso-databricks",
        "fqn": "contoso-databricks.contoso.gold.fct_revenue_summary",
        "contracts": contracts,
        "metrics": list(METRICS),
    }
    Path("catalog.json").write_text(json.dumps(catalogued, indent=2) + "\n", encoding="utf-8")
    print(f"catalogued {PRODUCT_NAME} as {catalogued['fqn']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
