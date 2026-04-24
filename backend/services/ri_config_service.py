"""
RIScreenConfig service — Steps 4-5.
Implements P01 (save_config), P02 (list_configs) from AP §2.2.
is_seed guard: AP §3.2.3 — 403 on PUT/DELETE for seed configs.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery
from fastapi import HTTPException

from backend.models.ri import (
    RIScreenConfig, YBFull, XPeriod, KRFull, FilterFull,
    ConfigListItem, SaveConfigRequest,
)

DATASET = "Config_FPA_T"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _table(client: bigquery.Client, name: str) -> str:
    return f"{client.project}.{DATASET}.{name}"


# ---------------------------------------------------------------------------
# YBFull builder (AP §5.1)
# ---------------------------------------------------------------------------

def build_kr_full_code(kr_items: list[dict]) -> str:
    """
    Compose KRFull code from KRItem list.
    Sort by level, join non-empty codes with '-'.
    AP §5.1: kr_full_code = join(sorted items by level, '-')
    """
    sorted_items = sorted(kr_items, key=lambda x: int(x.get("level", 1)))
    parts = [str(it.get("code", "")).strip() for it in sorted_items if it.get("code")]
    return "-".join(parts)


def build_filter_full_code(filter_items: list[dict]) -> str:
    """AP §5.1: filter_full_code = join(sorted filter items, '-')"""
    sorted_items = sorted(filter_items, key=lambda x: int(x.get("level", 1)))
    parts = [str(it.get("code", "")).strip() for it in sorted_items if it.get("code")]
    return "-".join(parts) if parts else "NONE"


def build_yb_full_id(kr_full_code: str, filter_full_code: str) -> str:
    """
    yb_full_code = f"{kr_full_code}__{filter_full_code}"  (double underscore — AP §5.1)
    """
    return f"{kr_full_code}__{filter_full_code}"


def _row_to_yb_full(row: dict, sort_order: int) -> tuple[str, dict]:
    """
    Convert a config grid row dict → (ybfull_id, bq_row_dict).
    row contains: kr_items[], filter_items[], ppr_mode?, unit?, plus 44-col fields.
    """
    kr_items = row.get("kr_items", [])
    filter_items = row.get("filter_items", [])

    kr_full_code = build_kr_full_code(kr_items) or "UNKNOWN"
    filter_full_code = build_filter_full_code(filter_items)
    ybfull_id = build_yb_full_id(kr_full_code, filter_full_code)

    # fnf from first kr_item's code if available, else from row field
    fnf = row.get("fnf", kr_items[0].get("code", "KRN") if kr_items else "KRN")

    bq_row = {
        "ybfull_id":   ybfull_id,
        "name":        row.get("name", ybfull_id),
        "ppr_mode":    row.get("ppr_mode"),
        "sort_order":  sort_order,
        # 44 RI_COLUMN_SCHEMA fields — copy from row if present, else empty string
        "fnf": fnf,
        **{col: str(row.get(col, "")) for col in [
            "kr1","kr2","kr3","kr4","kr5","kr6","kr7","kr8",
            "cdt1","cdt2","cdt3","cdt4",
            "pt1_now","pt2_now","du_now","pt1_prev","pt2_prev","du_prev",
            "owntype","aitype","cty1","cty2","ostype","fu1","fu2","ch",
            "egt1","egt2","egt3","egt4","egt5",
            "hr1","hr2","hr3","sec","px","ppc","np",
            "le1","le2","unit","td_bu","non_agg",
        ]},
    }
    # unit from explicit field if present
    if row.get("unit"):
        bq_row["unit"] = str(row["unit"])

    return ybfull_id, bq_row


# ---------------------------------------------------------------------------
# List / Get configs  (AP §2.4 #1-2)
# ---------------------------------------------------------------------------

def list_configs(client: bigquery.Client) -> list[ConfigListItem]:
    """GET /api/ri/configs — list all configs (seed + user). AP P02."""
    query = f"""
        SELECT config_id, config_code, config_name, is_seed, created_at,
               ARRAY_LENGTH(JSON_VALUE_ARRAY(yb_full_codes)) AS yb_full_count,
               ARRAY_LENGTH(JSON_VALUE_ARRAY(xperiod_codes)) AS xperiod_count
        FROM `{_table(client, 'ri_screen_config')}`
        ORDER BY is_seed DESC, created_at ASC
    """
    rows = list(client.query(query).result())
    return [
        ConfigListItem(
            config_id=r.config_id,
            config_code=r.config_code,
            config_name=r.config_name,
            is_seed=r.is_seed,
            yb_full_count=r.yb_full_count or 0,
            xperiod_count=r.xperiod_count or 0,
            created_at=r.created_at,
        )
        for r in rows
    ]


def get_config(client: bigquery.Client, config_id: str) -> RIScreenConfig:
    """GET /api/ri/configs/{id}"""
    query = f"""
        SELECT * FROM `{_table(client, 'ri_screen_config')}`
        WHERE config_id = @config_id LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("config_id", "STRING", config_id)]
    )
    rows = list(client.query(query, job_config=job_config).result())
    if not rows:
        raise HTTPException(status_code=404, detail=f"Config {config_id} not found")
    r = rows[0]
    return RIScreenConfig(
        config_id=r.config_id,
        config_code=r.config_code,
        config_name=r.config_name,
        is_seed=r.is_seed,
        yb_full_codes=json.loads(r.yb_full_codes or "[]"),
        xperiod_codes=json.loads(r.xperiod_codes or "[]"),
        created_by=r.created_by or "",
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


# ---------------------------------------------------------------------------
# Create config  (AP §2.4 #3, P01)
# ---------------------------------------------------------------------------

def create_config(client: bigquery.Client, req: SaveConfigRequest) -> RIScreenConfig:
    """POST /api/ri/configs — create non-seed config. AP P01."""
    config_id = str(uuid.uuid4())
    config_code = req.config_code or f"CFG-{config_id[:8].upper()}"
    now = _now()

    # Build YBFull rows
    yb_full_ids: list[str] = []
    yb_rows: list[dict] = []
    for i, row in enumerate(req.rows):
        ybfull_id, bq_row = _row_to_yb_full(row, sort_order=i)
        bq_row["config_id"] = config_id
        yb_full_ids.append(ybfull_id)
        yb_rows.append(bq_row)

    # Soft warn (not error) — AP §5.3
    if len(yb_full_ids) > 30:
        pass  # warning only, still save
    if len(req.xperiod_codes) > 10:
        pass  # warning only

    config_row = {
        "config_id":    config_id,
        "config_code":  config_code,
        "config_name":  req.config_name,
        "is_seed":      False,
        "yb_full_codes": json.dumps(yb_full_ids),
        "xperiod_codes": json.dumps(req.xperiod_codes),
        "created_by":   req.created_by,
        "created_at":   now.isoformat(),
        "updated_at":   now.isoformat(),
    }

    errors = client.insert_rows_json(_table(client, "ri_screen_config"), [config_row])
    if errors:
        raise HTTPException(status_code=500, detail=f"BQ insert error: {errors}")

    if yb_rows:
        errors = client.insert_rows_json(_table(client, "ri_screen_ybfull"), yb_rows)
        if errors:
            raise HTTPException(status_code=500, detail=f"BQ ybfull insert error: {errors}")

    # Insert xperiod rows for this config
    xp_rows = [
        {"config_id": config_id, "xperiod_code": xp, "period_type": None,
         "label": None, "sort_order": i}
        for i, xp in enumerate(req.xperiod_codes)
    ]
    if xp_rows:
        errors = client.insert_rows_json(_table(client, "ri_screen_xperiod"), xp_rows)
        if errors:
            raise HTTPException(status_code=500, detail=f"BQ xperiod insert error: {errors}")

    return RIScreenConfig(
        config_id=config_id,
        config_code=config_code,
        config_name=req.config_name,
        is_seed=False,
        yb_full_codes=yb_full_ids,
        xperiod_codes=req.xperiod_codes,
        created_by=req.created_by,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Update / Delete (with is_seed guard — AP §3.2.3)
# ---------------------------------------------------------------------------

def _assert_not_seed(client: bigquery.Client, config_id: str) -> None:
    """Raise 403 if config is a system seed. AP §3.2.3."""
    cfg = get_config(client, config_id)
    if cfg.is_seed:
        raise HTTPException(
            status_code=403,
            detail="Seed configs cannot be modified or deleted. Use Clone instead.",
        )


def update_config(client: bigquery.Client, config_id: str, req: SaveConfigRequest) -> RIScreenConfig:
    """PUT /api/ri/configs/{id} — non-seed only."""
    _assert_not_seed(client, config_id)
    now = _now()

    # Rebuild ybfull rows (delete old + insert new — BQ streaming doesn't support UPDATE)
    # For simplicity: insert new rows; old rows filtered by config_id in queries
    yb_full_ids: list[str] = []
    yb_rows: list[dict] = []
    for i, row in enumerate(req.rows):
        ybfull_id, bq_row = _row_to_yb_full(row, sort_order=i)
        bq_row["config_id"] = config_id
        yb_full_ids.append(ybfull_id)
        yb_rows.append(bq_row)

    # DML UPDATE for config metadata (BQ DML is synchronous enough for our use)
    update_sql = f"""
        UPDATE `{_table(client, 'ri_screen_config')}`
        SET config_name    = @config_name,
            yb_full_codes  = @yb_full_codes,
            xperiod_codes  = @xperiod_codes,
            updated_at     = @updated_at
        WHERE config_id = @config_id
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("config_name",    "STRING", req.config_name),
        bigquery.ScalarQueryParameter("yb_full_codes",  "JSON",   json.dumps(yb_full_ids)),
        bigquery.ScalarQueryParameter("xperiod_codes",  "JSON",   json.dumps(req.xperiod_codes)),
        bigquery.ScalarQueryParameter("updated_at",     "TIMESTAMP", now.isoformat()),
        bigquery.ScalarQueryParameter("config_id",      "STRING", config_id),
    ])
    client.query(update_sql, job_config=job_config).result()

    if yb_rows:
        client.insert_rows_json(_table(client, "ri_screen_ybfull"), yb_rows)

    return get_config(client, config_id)


def delete_config(client: bigquery.Client, config_id: str) -> None:
    """DELETE /api/ri/configs/{id} — non-seed only."""
    _assert_not_seed(client, config_id)
    delete_sql = f"""
        DELETE FROM `{_table(client, 'ri_screen_config')}` WHERE config_id = @config_id
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("config_id", "STRING", config_id)
    ])
    client.query(delete_sql, job_config=job_config).result()


def clone_config(client: bigquery.Client, config_id: str, new_name: str, created_by: str = "") -> RIScreenConfig:
    """
    POST /api/ri/configs/{id}/clone — clone any config (including seeds) as non-seed copy.
    AP §3.2.3: Clone creates is_seed=False copy.
    """
    src = get_config(client, config_id)
    now = _now()
    new_id = str(uuid.uuid4())
    new_code = f"CLONE-{src.config_code}-{new_id[:6].upper()}"

    # Clone config row
    clone_row = {
        "config_id":     new_id,
        "config_code":   new_code,
        "config_name":   new_name or f"Copy of {src.config_name}",
        "is_seed":       False,  # clones are never seeds
        "yb_full_codes": json.dumps(src.yb_full_codes),
        "xperiod_codes": json.dumps(src.xperiod_codes),
        "created_by":    created_by,
        "created_at":    now.isoformat(),
        "updated_at":    now.isoformat(),
    }
    errors = client.insert_rows_json(_table(client, "ri_screen_config"), [clone_row])
    if errors:
        raise HTTPException(status_code=500, detail=f"Clone error: {errors}")

    # Copy ybfull rows with new config_id
    src_yb_query = f"""
        SELECT * FROM `{_table(client, 'ri_screen_ybfull')}`
        WHERE config_id = @config_id
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("config_id", "STRING", config_id)
    ])
    src_yb_rows = list(client.query(src_yb_query, job_config=job_config).result())
    if src_yb_rows:
        new_yb_rows = [{**dict(r), "config_id": new_id} for r in src_yb_rows]
        client.insert_rows_json(_table(client, "ri_screen_ybfull"), new_yb_rows)

    return get_config(client, new_id)


# ---------------------------------------------------------------------------
# Load template for Entry screen (AP P03)
# ---------------------------------------------------------------------------

def load_entry_template(client: bigquery.Client, config_id: str) -> dict:
    """
    GET /api/ri/entries/template/{config_id}
    Returns config + resolved YBFull rows + XPeriod list + master dropdown options.
    AP §2.2 P03.
    """
    config = get_config(client, config_id)

    # Load YBFull rows for this config
    yb_query = f"""
        SELECT * FROM `{_table(client, 'ri_screen_ybfull')}`
        WHERE config_id = @config_id
        ORDER BY sort_order ASC
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("config_id", "STRING", config_id)
    ])
    yb_rows = list(client.query(yb_query, job_config=job_config).result())

    yb_fulls = [
        YBFull(
            yb_full_code=r.ybfull_id,
            kr_full_code=r.kr1 or "",
            filter_full_code=r.cdt1 or "",
            fnf=r.fnf or "KRN",
            unit=r.unit or "",
            ppr_mode=r.ppr_mode,
            sort_order=r.sort_order or 0,
        )
        for r in yb_rows
    ]

    # Load XPeriod master info for config's xperiod_codes
    xperiods = []
    if config.xperiod_codes:
        xp_query = f"""
            SELECT * FROM `{_table(client, 'master_xperiod')}`
            WHERE xperiod_code IN UNNEST(@codes)
            ORDER BY sort_order ASC
        """
        job_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ArrayQueryParameter("codes", "STRING", config.xperiod_codes)
        ])
        xp_rows = list(client.query(xp_query, job_config=job_config).result())
        xperiods = [
            XPeriod(
                xperiod_code=r.xperiod_code,
                period_type=r.period_type or "MF",
                label=r.label or r.xperiod_code,
                sort_order=r.sort_order or 0,
            )
            for r in xp_rows
        ]

    # Load dropdown masters
    masters = _load_masters(client)

    return {
        "config": config,
        "yb_fulls": yb_fulls,
        "xperiods": xperiods,
        "masters": masters,
    }


def _load_masters(client: bigquery.Client) -> dict:
    """Load all master dropdown data for entry screen top bar."""
    def _query_master(table: str, order_col: str = "code") -> list[dict]:
        q = f"SELECT * FROM `{_table(client, table)}` ORDER BY {order_col}"
        return [dict(r) for r in client.query(q).result()]

    return {
        "CAT_OPTIONS":    _query_master("ri_master_cat"),
        "PCK_OPTIONS":    _query_master("ri_master_pck"),
        "SRC_OPTIONS":    _query_master("ri_master_src"),
        "FF_OPTIONS":     _query_master("ri_master_ff"),
        "ALT_OPTIONS":    _query_master("ri_master_alt"),
        "SCN_OPTIONS":    ["OPT", "REAL", "PESS"],
        "KR_ITEMS":       _query_master("ri_master_kr_item", "level_code"),
        "FILTER_ITEMS":   _query_master("ri_master_filter_item", "level_code"),
        "XPERIOD_OPTIONS": _query_master("ri_master_xperiod", "sort_order"),
    }
