"""
Step 19 — Seed import to BQ.
Reads 5 PPR-PCA-* configs from GSheets via gsheets_reader,
upserts each as is_seed=True into Config_FPA_T:
  ri_screen_config   (1 row per config)
  ri_screen_ybfull   (N rows per config, 44 cols)
  ri_screen_xperiod  (M rows per config)

AP §3.2.3 is_seed guard: these rows are protected from PUT/DELETE.
ISP Step 19: seed import cross-referenced with AP §2.2 P01.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery

from backend.core.bq_client import get_bq_client
from backend.migrations.bq_migrate import RI_YBFULL_COLUMNS
from backend.seed.gsheets_reader import SEED_CONFIGS, read_all_seed_configs

DATASET = "Config_FPA_T"
BQ_PROJECT = "fpa-t-494007"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _table(name: str) -> str:
    return f"{BQ_PROJECT}.{DATASET}.{name}"


def _delete_existing_seed(client: bigquery.Client, config_code: str) -> None:
    """
    Delete existing seed rows for this config_code before re-import.
    Safe because we re-insert immediately after.
    AP §3.2.3: seed delete only allowed from this import script (not via API).
    """
    # Fetch config_id for this code
    q = f"""
        SELECT config_id FROM `{_table('ri_screen_config')}`
        WHERE config_code = @code AND is_seed = TRUE LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("code", "STRING", config_code)
    ])
    rows = list(client.query(q, job_config=job_config).result())
    if not rows:
        return

    config_id = rows[0].config_id

    # BQ streaming doesn't support DELETE immediately after insert;
    # use DML for proper deletion of seed rows.
    for table, col in [
        ("ri_screen_ybfull",  "config_id"),
        ("ri_screen_xperiod", "config_id"),
        ("ri_screen_config",  "config_id"),
    ]:
        dml = f"""
            DELETE FROM `{_table(table)}`
            WHERE {col} = @config_id
        """
        params = [bigquery.ScalarQueryParameter("config_id", "STRING", config_id)]
        client.query(dml, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()

    print(f"    Deleted existing seed rows for config_id={config_id}")


def _infer_period_type(xperiod_code: str) -> str:
    """
    Infer period_type from XPeriod code prefix (AP §1.1 #9).
    M2601 → MF, Q2603 → QF, H2606 → HF, Y26 → YF
    """
    code = str(xperiod_code).strip().upper()
    if code.startswith("M"):
        return "MF"
    if code.startswith("Q"):
        return "QF"
    if code.startswith("H"):
        return "HF"
    if code.startswith("Y"):
        return "YF"
    return "MF"


def _infer_ppr_mode(row_dict: dict) -> str:
    """
    Infer ppr_mode from fnf/unit fields (AP §5.8.0).
    KRF / financial amount rows → Spread; others → Same.
    """
    fnf = str(row_dict.get("fnf", "")).strip().upper()
    if fnf == "KRF":
        return "Spread"
    return "Same"


def import_seed_configs(
    credentials_path: str | None = None,
    client: bigquery.Client | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """
    Full seed import: GSheets → BQ.
    Returns {config_code: yb_row_count} for each imported config.

    dry_run=True: reads GSheets but skips BQ writes (for testing).
    """
    if client is None:
        client = get_bq_client()

    print("Reading seed configs from GSheets…")
    all_configs = read_all_seed_configs(credentials_path)
    print(f"  → {len(all_configs)} configs read")

    results: dict[str, int] = {}

    for cfg in all_configs:
        code = cfg["code"]
        name = cfg["name"]
        sheet_id = cfg["sheet_id"]
        xperiod_codes: list[str] = cfg["xperiod_codes"]
        yb_rows: list[dict] = cfg["yb_full_rows"]

        print(f"\nImporting {code} ({len(yb_rows)} YBFull rows, {len(xperiod_codes)} XPeriods)…")

        if dry_run:
            print(f"  [dry_run] Would import {code}")
            results[code] = len(yb_rows)
            continue

        # Delete existing seed rows for this config (idempotent re-import)
        _delete_existing_seed(client, code)

        # Generate stable config_id from code (deterministic for re-runs)
        config_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"seed.{code}"))
        now = _now()

        # 1. Insert ri_screen_config
        config_row = {
            "config_id":    config_id,
            "config_code":  code,
            "config_name":  name,
            "is_seed":      True,
            "yb_full_codes": json.dumps([r.get("fnf", "") for r in yb_rows]),
            "xperiod_codes": json.dumps(xperiod_codes),
            "created_by":   "seed_import",
            "created_at":   now,
            "updated_at":   now,
        }
        errors = client.insert_rows_json(_table("ri_screen_config"), [config_row])
        if errors:
            raise RuntimeError(f"Config insert error for {code}: {errors}")

        # 2. Insert ri_screen_ybfull rows (44 cols + meta)
        yb_bq_rows = []
        for i, row in enumerate(yb_rows):
            ybfull_id = row.get("fnf", f"ROW_{i+1:03d}")
            ppr_mode = _infer_ppr_mode(row)
            bq_row: dict = {
                "config_id":  config_id,
                "ybfull_id":  ybfull_id,
                "name":       ybfull_id,
                "ppr_mode":   ppr_mode,
                "sort_order": i + 1,
            }
            # Map 44 RI columns from the GSheet row dict
            for col in RI_YBFULL_COLUMNS:
                bq_row[col] = str(row.get(col, "") or "")
            yb_bq_rows.append(bq_row)

        # Insert in batches of 500 (BQ streaming limit)
        for batch_start in range(0, len(yb_bq_rows), 500):
            batch = yb_bq_rows[batch_start:batch_start + 500]
            errors = client.insert_rows_json(_table("ri_screen_ybfull"), batch)
            if errors:
                raise RuntimeError(f"YBFull insert error for {code}: {errors}")

        # 3. Insert ri_screen_xperiod rows
        xp_bq_rows = []
        for i, xp_code in enumerate(xperiod_codes):
            xp_code = str(xp_code).strip()
            if not xp_code:
                continue
            period_type = _infer_period_type(xp_code)
            xp_bq_rows.append({
                "config_id":    config_id,
                "xperiod_code": xp_code,
                "period_type":  period_type,
                "label":        xp_code,
                "sort_order":   i + 1,
            })

        if xp_bq_rows:
            errors = client.insert_rows_json(_table("ri_screen_xperiod"), xp_bq_rows)
            if errors:
                raise RuntimeError(f"XPeriod insert error for {code}: {errors}")

        print(f"  ✓ {code}: {len(yb_bq_rows)} YBFull, {len(xp_bq_rows)} XPeriod rows imported")
        results[code] = len(yb_bq_rows)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import PPR-PCA-* seed configs from GSheets to BQ")
    parser.add_argument("--dry-run", action="store_true", help="Read GSheets but skip BQ writes")
    parser.add_argument("--credentials", default=None, help="Path to service account JSON")
    args = parser.parse_args()

    stats = import_seed_configs(
        credentials_path=args.credentials,
        dry_run=args.dry_run,
    )
    print("\nSeed import complete:")
    for code, count in stats.items():
        print(f"  {code}: {count} YBFull rows")
