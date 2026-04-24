"""
BQ table migration — Step 2.
Idempotent: create tables if not exist. Safe to run at startup.
Dataset: Config_FPA_T in project fpa-t-494007.
Cross-referenced with AP §1.2 and ISP Step 2.
"""

from __future__ import annotations

from google.cloud import bigquery
from google.cloud.exceptions import NotFound

# 44-column schema for ri_screen_ybfull (mirrors sheet RI cols I:BA, AP §3.2.0)
RI_YBFULL_COLUMNS = [
    "fnf", "kr1", "kr2", "kr3", "kr4", "kr5", "kr6", "kr7", "kr8",
    "cdt1", "cdt2", "cdt3", "cdt4",
    "pt1_now", "pt2_now", "du_now",
    "pt1_prev", "pt2_prev", "du_prev",
    "owntype", "aitype",
    "cty1", "cty2", "ostype",
    "fu1", "fu2", "ch",
    "egt1", "egt2", "egt3", "egt4", "egt5",
    "hr1", "hr2", "hr3", "sec",
    "px", "ppc", "np",
    "le1", "le2", "unit", "td_bu", "non_agg",
]

_SF = bigquery.SchemaField

SCHEMAS: dict[str, list[bigquery.SchemaField]] = {
    # RIScreenConfig — AP §1.2
    "ri_screen_config": [
        _SF("config_id",    "STRING", mode="REQUIRED"),
        _SF("config_code",  "STRING", mode="REQUIRED"),   # PPR-PCA-GH / user-defined
        _SF("config_name",  "STRING", mode="REQUIRED"),
        _SF("is_seed",      "BOOL",   mode="REQUIRED"),
        _SF("yb_full_codes","JSON"),                       # array of ybfull codes
        _SF("xperiod_codes","JSON"),                       # array of xperiod codes
        _SF("created_by",   "STRING"),
        _SF("created_at",   "TIMESTAMP"),
        _SF("updated_at",   "TIMESTAMP"),
    ],
    # RIScreenEntry — AP §1.1 new entity
    "ri_screen_entry": [
        _SF("entry_id",         "STRING", mode="REQUIRED"),
        _SF("config_id",        "STRING", mode="REQUIRED"),
        _SF("zb_full_code",     "STRING", mode="REQUIRED"),  # UNIQUE — 1:1 ZBFull
        _SF("scn_type",         "STRING"),                   # OPT / REAL / PESS
        _SF("run_code",         "STRING"),
        _SF("created_by",       "STRING"),
        _SF("created_at",       "TIMESTAMP"),
        _SF("status",           "STRING"),                   # DRAFT / SAVED
    ],
    # YBFull rows per config — 44-col mirror of sheet RI I:BA (AP §3.2.0)
    "ri_screen_ybfull": [
        _SF("config_id",    "STRING", mode="REQUIRED"),
        _SF("ybfull_id",    "STRING", mode="REQUIRED"),
        _SF("name",         "STRING"),
        _SF("ppr_mode",     "STRING"),   # Same / Spread (AP §5.8.0)
        _SF("sort_order",   "INT64"),
        *[_SF(col, "STRING") for col in RI_YBFULL_COLUMNS],
    ],
    # XPeriod per config — AP §1.1 #9
    "ri_screen_xperiod": [
        _SF("config_id",    "STRING", mode="REQUIRED"),
        _SF("xperiod_code", "STRING", mode="REQUIRED"),  # M2603 / Q2603 / H2606 / Y26
        _SF("period_type",  "STRING"),                   # MF / QF / HF / YF
        _SF("label",        "STRING"),
        _SF("sort_order",   "INT64"),
    ],
    # Master tables (shared across configs)
    "ri_master_cat": [
        _SF("code",        "STRING", mode="REQUIRED"),
        _SF("name",        "STRING"),
        _SF("description", "STRING"),
        _SF("is_active",   "BOOL"),
    ],
    "ri_master_pck": [
        _SF("code",        "STRING", mode="REQUIRED"),
        _SF("name",        "STRING"),
        _SF("description", "STRING"),
        _SF("is_active",   "BOOL"),
    ],
    "ri_master_src": [
        _SF("code",        "STRING", mode="REQUIRED"),
        _SF("name",        "STRING"),
        _SF("description", "STRING"),
        _SF("is_active",   "BOOL"),
    ],
    "ri_master_ff": [
        _SF("code",        "STRING", mode="REQUIRED"),  # MF / QF / HF / YF
        _SF("name",        "STRING"),
        _SF("description", "STRING"),
        _SF("is_active",   "BOOL"),
    ],
    "ri_master_alt": [
        _SF("code",        "STRING", mode="REQUIRED"),  # PLA4 / ...
        _SF("name",        "STRING"),
        _SF("description", "STRING"),
        _SF("is_active",   "BOOL"),
    ],
    "ri_master_scn": [
        _SF("code",      "STRING", mode="REQUIRED"),  # OPT / REAL / PESS
        _SF("name",      "STRING"),
        _SF("scn_type",  "STRING"),
        _SF("is_active", "BOOL"),
    ],
    "ri_master_xperiod": [
        _SF("xperiod_code", "STRING", mode="REQUIRED"),
        _SF("period_type",  "STRING"),
        _SF("label",        "STRING"),
        _SF("sort_order",   "INT64"),
        _SF("is_active",    "BOOL"),
    ],
    "ri_master_kr_item": [
        _SF("kr_item_code", "STRING", mode="REQUIRED"),
        _SF("level_code",   "STRING"),
        _SF("name",         "STRING"),
        _SF("is_active",    "BOOL"),
    ],
    "ri_master_filter_item": [
        _SF("filter_item_code", "STRING", mode="REQUIRED"),
        _SF("level_code",       "STRING"),
        _SF("name",             "STRING"),
        _SF("is_active",        "BOOL"),
    ],
    "ri_master_run": [
        _SF("run_code",   "STRING", mode="REQUIRED"),
        _SF("run_ts",     "TIMESTAMP"),
        _SF("created_by", "STRING"),
    ],
}


def ensure_dataset(client: bigquery.Client, dataset_id: str = "Config_FPA_T") -> None:
    """Create dataset if not exists (AP Step 3 / BLOCK resolution)."""
    dataset_ref = client.dataset(dataset_id)
    try:
        client.get_dataset(dataset_ref)
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset)


def ensure_tables(
    client: bigquery.Client,
    dataset_id: str = "Config_FPA_T",
) -> dict[str, str]:
    """
    Idempotent table creation. Returns {table_id: 'created'|'existed'} for each table.
    """
    ensure_dataset(client, dataset_id)
    results: dict[str, str] = {}

    for table_id, schema in SCHEMAS.items():
        table_ref = f"{client.project}.{dataset_id}.{table_id}"
        try:
            client.get_table(table_ref)
            results[table_id] = "existed"
        except NotFound:
            table = bigquery.Table(table_ref, schema=schema)
            client.create_table(table)
            results[table_id] = "created"

    return results


if __name__ == "__main__":
    from backend.core.bq_client import get_bq_client
    client = get_bq_client()
    results = ensure_tables(client)
    for table_id, status in results.items():
        print(f"  {table_id}: {status}")
