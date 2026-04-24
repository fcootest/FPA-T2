"""
RIScreenEntry service — Steps 10, 14, 17.
Implements P06 (save_entry) from AP §2.2, §5.5.
1 Save → 3 RIScreenEntry (OPT/REAL/PESS) with same RUN code.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, HTTPException
from google.cloud import bigquery

from backend.models.ri import (
    RIScreenEntry, RICell, YBFull, XPeriod, SaveEntryRequest,
)
from backend.services.ppr_service import prepare_for_calculate, load_for_ui

DATASET = "Config_FPA_T"
BQ_PROJECT = "fpa-t-494007"
SO_CELL_TABLE = f"{BQ_PROJECT}.so_cell.so_cell_v1"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _table(client: bigquery.Client, name: str) -> str:
    return f"{client.project}.{DATASET}.{name}"


def _generate_run_code(client: bigquery.Client, created_by: str = "") -> str:
    """
    RUN code format: RUN{YYYY}{MMM}{DD}-{HHMMSS} (AP §5.4).
    Persists to master_run registry after generation.
    """
    now = datetime.utcnow()
    run_code = f"RUN{now.year}{now.strftime('%b').upper()}{now.day:02d}-{now:%H%M%S}"
    client.insert_rows_json(
        _table(client, "master_run"),
        [{"run_code": run_code, "run_ts": now.isoformat(), "created_by": created_by}],
    )
    return run_code


def _resolve_zb_full_code(cat: str, pck: str, src: str, ff: str, alt: str, scn: str, run: str) -> str:
    """AP §5.2: ZBFull = f'{cat}-{pck}-{src}-{ff}-{alt}-{scn}-{run}'"""
    return f"{cat}-{pck}-{src}-{ff}-{alt}-{scn}-{run}"


# ---------------------------------------------------------------------------
# Save Entry  (AP §5.5, P06)
# ---------------------------------------------------------------------------

def _update_entries_status(client: bigquery.Client, entry_ids: list[str], status: str) -> None:
    """Update status column for a list of entries via DML UPDATE. AP §5.5 step 5."""
    if not entry_ids:
        return
    ids_literal = ", ".join(f"'{eid}'" for eid in entry_ids)
    query = f"""
        UPDATE `{_table(client, 'ri_screen_entry')}`
        SET status = '{status}'
        WHERE entry_id IN ({ids_literal})
    """
    client.query(query).result()


def save_entry(client: bigquery.Client, req: SaveEntryRequest, background_tasks: BackgroundTasks | None = None) -> dict:
    """
    POST /api/ri/entries
    1. Generate RUN code (shared for all 3 SCN)
    2. Create 3 ZBFull + 3 RIScreenEntry (OPT/REAL/PESS) with status=DRAFT — AP §5.5 step 2
    3. Group cells by SCN → persist RICell per entry — AP §5.5 step 4
    4. Update entry status DRAFT→SAVED after cells persisted — AP §5.5 step 5
    5. Trigger PPR DOWN (prepare_for_calculate) as background task — AP §5.9.3
    """
    run_code = _generate_run_code(client, req.created_by)
    now = _now()

    scn_types = ["OPT", "REAL", "PESS"]
    entries: dict[str, RIScreenEntry] = {}
    entry_rows: list[dict] = []

    for scn in scn_types:
        zb_full_code = _resolve_zb_full_code(
            req.cat, req.pck, req.src, req.ff, req.alt, scn, run_code
        )
        entry_id = str(uuid.uuid4())
        entry = RIScreenEntry(
            entry_id=entry_id,
            config_id=req.config_id,
            zb_full_code=zb_full_code,
            scn_type=scn,
            run_code=run_code,
            created_by=req.created_by,
            created_at=now,
            status="DRAFT",
        )
        entries[scn] = entry
        entry_rows.append({
            "entry_id":     entry_id,
            "config_id":    req.config_id,
            "zb_full_code": zb_full_code,
            "scn_type":     scn,
            "run_code":     run_code,
            "created_by":   req.created_by,
            "created_at":   now.isoformat(),
            "status":       "DRAFT",
        })

    # Persist entries to BQ (DRAFT)
    errors = client.insert_rows_json(_table(client, "ri_screen_entry"), entry_rows)
    if errors:
        raise HTTPException(status_code=500, detail=f"Entry insert error: {errors}")

    # Group cells by SCN → build RICell list per entry (AP §5.5 step 4)
    cells_by_scn: dict[str, list[dict]] = {scn: [] for scn in scn_types}
    for cell in req.cells:
        scn = cell.get("scn_type", "OPT")
        if scn in cells_by_scn:
            cells_by_scn[scn].append(cell)

    # Load YBFull + XPeriod for PPR DOWN
    yb_fulls, xperiods = _load_config_yb_xp(client, req.config_id)
    yb_map = {yb.yb_full_code: yb for yb in yb_fulls}
    xp_map = {xp.xperiod_code: xp for xp in xperiods}

    all_ri_cells: list[RICell] = []
    ri_cell_rows: list[dict] = []

    for scn, cell_dicts in cells_by_scn.items():
        entry = entries[scn]
        for cd in cell_dicts:
            if cd.get("value") is None:
                continue
            cell_id = str(uuid.uuid4())
            yb_full_code = cd.get("yb_full_code", "")
            ri_cell = RICell(
                cell_id=cell_id,
                entry_id=entry.entry_id,
                yb_full_code=yb_full_code,
                xperiod_code=cd.get("xperiod_code", ""),
                zb_full_code=entry.zb_full_code,
                z_block_zblock1_category=req.cat,
                z_block_zblock1_pack=req.pck,
                z_block_zblock1_source=req.src,
                z_block_zblock1_frequency=req.ff,
                z_block_zblock1_scenario=scn,
                z_block_zblock1_run=run_code,
                now_zblock2_alt=req.alt,
                now_y_block_fnf_fnf=yb_map.get(yb_full_code, YBFull(
                    yb_full_code="", kr_full_code="", filter_full_code=""
                )).fnf,
                now_value=float(cd.get("value", 0)),
                time_col_name=cd.get("xperiod_code", ""),
            )
            all_ri_cells.append(ri_cell)
            ri_cell_rows.append({
                "cell_id":                    cell_id,
                "entry_id":                   entry.entry_id,
                "yb_full_code":               ri_cell.yb_full_code,
                "xperiod_code":               ri_cell.xperiod_code,
                "zb_full_code":               ri_cell.zb_full_code,
                "z_block_zblock1_category":   ri_cell.z_block_zblock1_category,
                "z_block_zblock1_pack":       ri_cell.z_block_zblock1_pack,
                "z_block_zblock1_source":     ri_cell.z_block_zblock1_source,
                "z_block_zblock1_frequency":  ri_cell.z_block_zblock1_frequency,
                "z_block_zblock1_scenario":   ri_cell.z_block_zblock1_scenario,
                "z_block_zblock1_run":        ri_cell.z_block_zblock1_run,
                "now_zblock2_alt":            ri_cell.now_zblock2_alt,
                "now_value":                  ri_cell.now_value,
                "now_y_block_fnf_fnf":        ri_cell.now_y_block_fnf_fnf,
                "time_col_name":              ri_cell.time_col_name,
                "uploaded_at":                now.isoformat(),
            })

    # Persist RICell to so_cell_v1
    if ri_cell_rows:
        errors = client.insert_rows_json(SO_CELL_TABLE, ri_cell_rows)
        if errors:
            raise HTTPException(status_code=500, detail=f"RICell insert error: {errors}")

    # Update entry status DRAFT → SAVED (AP §5.5 step 5)
    _update_entries_status(client, [e.entry_id for e in entries.values()], "SAVED")
    for entry in entries.values():
        entry.status = "SAVED"

    # PPR DOWN: run as background task to avoid blocking HTTP response (AP §5.9.3)
    if all_ri_cells:
        if background_tasks is not None:
            background_tasks.add_task(prepare_for_calculate, all_ri_cells, yb_map, xp_map, client)
        else:
            prepare_for_calculate(all_ri_cells, yb_map, xp_map, client)

    return {
        "entries": [e.model_dump(mode="json") for e in entries.values()],
        "run_code": run_code,
    }


# ---------------------------------------------------------------------------
# Load entry display (PPR UP)  (AP §5.9.3)
# ---------------------------------------------------------------------------

def get_entry_display(client: bigquery.Client, entry_id: str) -> list[RICell]:
    """
    GET /api/ri/entries/{id}/display
    Load SORow from BQ → PPR UP → return RICell list for UI grid.
    """
    # Load entry
    entry = _get_entry(client, entry_id)
    yb_fulls, xperiods = _load_config_yb_xp(client, entry.config_id)

    return load_for_ui(entry.zb_full_code, yb_fulls, xperiods, client)


def _get_entry(client: bigquery.Client, entry_id: str) -> RIScreenEntry:
    query = f"""
        SELECT * FROM `{_table(client, 'ri_screen_entry')}`
        WHERE entry_id = @entry_id LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("entry_id", "STRING", entry_id)
    ])
    rows = list(client.query(query, job_config=job_config).result())
    if not rows:
        raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found")
    r = rows[0]
    return RIScreenEntry(
        entry_id=r.entry_id,
        config_id=r.config_id,
        zb_full_code=r.zb_full_code,
        scn_type=r.scn_type,
        run_code=r.run_code,
        created_by=r.created_by or "",
        created_at=r.created_at,
        status=r.status,
    )


def _get_entry_cells(client: bigquery.Client, entry_id: str) -> list[RICell]:
    """Load persisted RICell rows for an entry from so_cell_v1. AP §2.4 #8."""
    query = f"""
        SELECT * FROM `{SO_CELL_TABLE}`
        WHERE entry_id = @entry_id
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("entry_id", "STRING", entry_id)
    ])
    rows = list(client.query(query, job_config=job_config).result())
    return [
        RICell(
            cell_id=r.cell_id,
            entry_id=r.entry_id,
            yb_full_code=r.yb_full_code,
            xperiod_code=r.xperiod_code,
            zb_full_code=r.zb_full_code,
            now_value=float(r.now_value or 0),
            now_y_block_fnf_fnf=r.now_y_block_fnf_fnf or "",
            time_col_name=r.time_col_name or "",
        )
        for r in rows
    ]


def get_entry_with_cells(client: bigquery.Client, entry_id: str) -> dict:
    """GET /api/ri/entries/{id} — returns entry + cells. AP §2.4 #8."""
    entry = _get_entry(client, entry_id)
    cells = _get_entry_cells(client, entry_id)
    return {
        "entry": entry.model_dump(mode="json"),
        "cells": [c.model_dump(mode="json") for c in cells],
    }


def _load_config_yb_xp(client: bigquery.Client, config_id: str) -> tuple[list[YBFull], list[XPeriod]]:
    """Load YBFull + XPeriod rows for a config."""
    yb_query = f"""
        SELECT ybfull_id, fnf, unit, ppr_mode, kr1, cdt1, sort_order
        FROM `{_table(client, 'ri_screen_ybfull')}`
        WHERE config_id = @config_id ORDER BY sort_order
    """
    xp_query = f"""
        SELECT xperiod_code, period_type, label, sort_order
        FROM `{_table(client, 'ri_screen_xperiod')}`
        WHERE config_id = @config_id ORDER BY sort_order
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("config_id", "STRING", config_id)
    ])
    yb_rows = list(client.query(yb_query, job_config=job_config).result())
    xp_rows = list(client.query(xp_query, job_config=job_config).result())

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
    xperiods = [
        XPeriod(
            xperiod_code=r.xperiod_code,
            period_type=r.period_type or "MF",
            label=r.label or r.xperiod_code,
            sort_order=r.sort_order or 0,
        )
        for r in xp_rows
    ]
    return yb_fulls, xperiods
