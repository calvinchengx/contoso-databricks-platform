"""Land sample bytes for every vendor the product bronze reads.

When the published fixture wheels are installed, a later step can replace
these with the real export. The sample is enough to prove the sibling
attaches the product without restating transform logic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from target import host_delta, landing_path

DAY = "2026-07-15"


def _pos(root: Path) -> None:
    dest = root / "contoso_pos" / DAY
    (dest / "customers").mkdir(parents=True, exist_ok=True)
    (dest / "customers" / "part-0001.csv").write_text(
        "customer_id,name,email,country,marketing_segment,loyalty_tier\n"
        "1,Alice,alice@example.com,USA,premium,gold\n"
        "2,Bob,,GB,mainstream,silver\n"
        "3,Cara,cara@example.com,United Kingdom,new,bronze\n",
        encoding="utf-8",
    )
    (dest / "orders").mkdir(exist_ok=True)
    rows = [
        {
            "order_id": "o1",
            "customer_id": "1",
            "product_id": "sku-1",
            "event_seq": 1,
            "order_date": "2026-07-15",
            "channel": "store",
            "status": "shipped",
            "currency": "USD",
            "quantity": 2,
            "unit_price": 10.0,
        },
        {
            "order_id": "o2",
            "customer_id": "2",
            "product_id": "sku-2",
            "event_seq": 1,
            "order_date": "2026-07-15",
            "channel": "store",
            "status": "shipped",
            "currency": "USD",
            "quantity": 1,
            "unit_price": 5.0,
        },
    ]
    (dest / "orders" / "part-0001.json").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )


def _web(root: Path) -> None:
    dest = root / "contoso_web" / DAY
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "customers").mkdir(exist_ok=True)
    (dest / "customers" / "page.json").write_text(
        json.dumps(
            [
                {"email": "alice@example.com", "country": "United States"},
                {"email": "dana@example.com", "country": "SG"},
            ]
        ),
        encoding="utf-8",
    )
    (dest / "products").mkdir(exist_ok=True)
    (dest / "products" / "page.json").write_text(
        json.dumps([{"product_id": "sku-1", "name": "Mouse"}]),
        encoding="utf-8",
    )
    (dest / "orders").mkdir(exist_ok=True)
    (dest / "orders" / "page.json").write_text(
        json.dumps(
            [
                {
                    "web_order_id": "w1",
                    "email": "alice@example.com",
                    "placed_at": "2026-07-15T12:00:00Z",
                    "status": "paid",
                    "lines": [
                        {
                            "line_no": 1,
                            "product_id": "sku-1",
                            "quantity": "1",
                            "unit_price": "12.00",
                        }
                    ],
                },
                {
                    "web_order_id": "w2",
                    "email": "dana@example.com",
                    "placed_at": "2026-06-30T23:30:00-07:00",
                    "status": "cancelled",
                    "lines": [
                        {
                            "line_no": 1,
                            "product_id": "sku-99",
                            "quantity": "1",
                            "unit_price": "3.00",
                        }
                    ],
                },
            ]
        ),
        encoding="utf-8",
    )


def _reference(root: Path) -> None:
    dest = root / "contoso_reference" / DAY
    dest.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.table(
            {
                "currency": ["USD", "GBP"],
                "rate_date": ["2026-07-15", "2026-07-15"],
                "rate_to_usd": [1.0, 1.27],
            }
        ),
        dest / "fx_rates.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "product_id": ["sku-1", "sku-2"],
                "product_name": ["Mouse", "Pad"],
                "category": ["Peripherals", "Peripherals"],
                "department": ["Accessories", "Accessories"],
                "segment": ["Peripheral", "Peripheral"],
                "list_price_usd": [12.0, 5.0],
            }
        ),
        dest / "product_hierarchy.parquet",
    )


def _erp(root: Path) -> None:
    dest = root / "contoso_erp" / DAY
    dest.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.table({"change_id": [1], "entity": ["order"], "op": ["c"]}),
        dest / "changes.parquet",
    )


def main() -> int:
    root = host_delta() / "landing"
    _pos(root)
    _web(root)
    _reference(root)
    _erp(root)
    print(f"landed sample vendors under {root} (engine {landing_path()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
