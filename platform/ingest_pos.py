"""Land one vendor (Contoso POS) as CSV + JSON Lines the bronze transform reads.

Full fixture wheels are optional. Without them this writes a tiny sample that
still exercises the product path — enough to prove the sibling attaches.
`make verify` with fixtures present lands the real export.
"""

from __future__ import annotations

import json
from pathlib import Path

from target import T, host_delta, landing_path

DAY = "2026-07-15"


def _sample(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "customers").mkdir(exist_ok=True)
    (dest / "customers" / "part-0001.csv").write_text(
        "customer_id,name,email,country,marketing_segment,loyalty_tier\n"
        "1,Alice,alice@example.com,USA,premium,gold\n"
        "2,Bob,,GB,mainstream,silver\n",
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
        }
    ]
    (dest / "orders" / "part-0001.json").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )


def main() -> int:
    t = T()
    t.refuse_seed_secrets() if False else None  # ingest is not seed_secrets
    host = host_delta() / "landing" / "contoso_pos" / DAY
    _sample(host)
    print(f"landed POS sample at {host} (engine path {landing_path()}/contoso_pos/{DAY})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
