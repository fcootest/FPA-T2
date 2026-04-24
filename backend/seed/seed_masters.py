"""
Step 3 — Seed master tables into Config_FPA_T.
Idempotent: uses INSERT OR REPLACE (MERGE in BQ).
AP §2.4 masters endpoints serve this data.
"""

from __future__ import annotations

from google.cloud import bigquery

from backend.migrations.bq_migrate import ensure_dataset
from backend.seed.masters_data import (
    MASTER_CAT, MASTER_PCK, MASTER_SRC, MASTER_FF, MASTER_ALT,
    MASTER_SCN, MASTER_XPERIOD, MASTER_KR_ITEMS, MASTER_FILTER_ITEMS,
)

DATASET = "Config_FPA_T"

MASTER_MAP = {
    "ri_master_cat":         MASTER_CAT,
    "ri_master_pck":         MASTER_PCK,
    "ri_master_src":         MASTER_SRC,
    "ri_master_ff":          MASTER_FF,
    "ri_master_alt":         MASTER_ALT,
    "ri_master_scn":         MASTER_SCN,
    "ri_master_xperiod":     MASTER_XPERIOD,
    "ri_master_kr_item":     MASTER_KR_ITEMS,
    "ri_master_filter_item": MASTER_FILTER_ITEMS,
}


def _upsert_rows(
    client: bigquery.Client,
    table_id: str,
    rows: list[dict],
    dataset_id: str = DATASET,
) -> int:
    """Insert rows, ignoring conflicts (BQ streaming insert, dedup by row identity)."""
    if not rows:
        return 0
    full_table = f"{client.project}.{dataset_id}.{table_id}"
    errors = client.insert_rows_json(full_table, rows)
    if errors:
        raise RuntimeError(f"BQ insert errors for {table_id}: {errors}")
    return len(rows)


def seed_masters(client: bigquery.Client, dataset_id: str = DATASET) -> dict[str, int]:
    """
    Seed all master tables. Returns {table_id: rows_inserted}.
    Run after ensure_tables().
    """
    ensure_dataset(client, dataset_id)
    results: dict[str, int] = {}
    for table_id, rows in MASTER_MAP.items():
        n = _upsert_rows(client, table_id, rows, dataset_id)
        results[table_id] = n
    return results


if __name__ == "__main__":
    from backend.core.bq_client import get_bq_client
    from backend.migrations.bq_migrate import ensure_tables

    client = get_bq_client()
    ensure_tables(client)
    results = seed_masters(client)
    for table_id, n in results.items():
        print(f"  {table_id}: {n} rows")
