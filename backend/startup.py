"""
Startup orchestration — BUG-007.
Consolidates ensure_dataset + ensure_tables + seed_masters into one call.
Safe to call on every startup (all operations are idempotent).
"""

from __future__ import annotations

import json
from pathlib import Path

from google.cloud import bigquery

from backend.migrations.bq_migrate import ensure_tables

SEED_FILE = Path(__file__).parent / "seed" / "data" / "masters.json"
DATASET = "Config_FPA_T"

_MASTER_TABLES_WITH_CODE_PK = {
    "master_cat", "master_pck", "master_src", "master_ff",
    "master_alt", "master_scn",
}
_MASTER_TABLES_WITH_OTHER_PK = {
    "master_xperiod": "xperiod_code",
    "master_kr_item": "kr_item_code",
    "master_filter_item": "filter_item_code",
}


def _pk_field(table: str) -> str:
    if table in _MASTER_TABLES_WITH_CODE_PK:
        return "code"
    return _MASTER_TABLES_WITH_OTHER_PK.get(table, "code")


def _seed_masters(client: bigquery.Client) -> dict[str, str]:
    """Insert missing seed rows (skip existing PK values). Idempotent."""
    if not SEED_FILE.exists():
        return {}
    seed_data: dict[str, list[dict]] = json.loads(SEED_FILE.read_text())
    results: dict[str, str] = {}

    for table, rows in seed_data.items():
        pk = _pk_field(table)
        full_table = f"{client.project}.{DATASET}.{table}"

        # Load existing PKs
        existing_pks = {
            r[pk]
            for r in client.query(f"SELECT {pk} FROM `{full_table}`").result()
        }

        new_rows = [r for r in rows if r.get(pk) not in existing_pks]
        if new_rows:
            errors = client.insert_rows_json(full_table, new_rows)
            results[table] = f"inserted {len(new_rows)}" if not errors else f"error: {errors}"
        else:
            results[table] = "skipped (all exist)"

    return results


def run_startup(client: bigquery.Client) -> dict:
    """
    Full startup sequence:
    1. ensure_tables (idempotent schema migration)
    2. seed_masters (insert missing reference data)
    """
    table_results = ensure_tables(client)
    seed_results = _seed_masters(client)
    return {"tables": table_results, "seeds": seed_results}
