"""Emulator-only. Real mode must already hold the customer's values."""

from __future__ import annotations

from target import T


def main() -> int:
    t = T()
    if not t.seed_secrets_allowed:
        print("seed_secrets skipped — DATABRICKS_TARGET=real uses the customer's scope")
        return 0
    w = t.workspace_client()
    w.secrets.put_secret(scope=t.secret_scope, key="contoso-pos-api-key", string_value="pos-dev-key")
    print(f"seeded {t.secret_scope}/contoso-pos-api-key")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
