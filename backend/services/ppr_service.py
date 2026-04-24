"""
PPR (Plan Prepare) service — Steps 12-17.
4 core functions implementing the 2-way Period↔Month pipeline.
AP §5.8, §5.9.

PPR DOWN (write path):
  RICell_PeriodToMonth() → RICellToRIRow() → WriteSORow()

PPR UP (read path):
  SORowToRICellMonth() [NEW converter] → RICell_MonthToPeriod()
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from google.cloud import bigquery

from backend.models.ri import (
    RICell, RICellMonth, RIRow, SORow, YBFull, XPeriod,
)

BQ_PROJECT = "fpa-t-494007"
SO_ROWS_TABLE = f"{BQ_PROJECT}.so_rows.so_rows_pca"
SO_CELL_TABLE = f"{BQ_PROJECT}.so_cell.so_cell_v1"

# Monthly column range in so_rows_pca (AP §1.1 #5)
# m2007 → m3012 (135 months); we write only the ones in ri_row.monthly_values
# Column name pattern: time_x_block_{month_code}_value (all lowercase)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# PPR-1: RICell_PeriodToMonth()  (AP §5.8.1)
# ---------------------------------------------------------------------------

def RICell_PeriodToMonth(ri_cell: RICell, yb_full: YBFull, xperiod: XPeriod) -> list[RICellMonth]:
    """
    Expand 1 RICell (XPeriod-level) → N RICellMonth (month-level).
    N = 1 (MF) / 3 (QF) / 6 (HF) / 12 (YF).

    ppr_mode logic (AP §5.8.0):
      Same  → copy value to each month (RATE / NOEM / KRN rows)
      Spread → divide value by N months (financial amount / KRF rows)
    """
    months = xperiod.expand_to_months()
    n = len(months)
    ppr_mode = yb_full.effective_ppr_mode()

    if ppr_mode == "Same":
        factor = 1.0
    elif ppr_mode == "Spread":
        factor = 1.0 / n if n > 0 else 1.0
    else:
        raise ValueError(f"Unknown ppr_mode: {ppr_mode}")

    return [
        RICellMonth(
            ri_row_id=ri_cell.so_row_id,
            yb_full_code=ri_cell.yb_full_code,
            zb_full_code=ri_cell.zb_full_code,
            month_code=m,
            value=ri_cell.now_value * factor,
        )
        for m in months
    ]


# ---------------------------------------------------------------------------
# PPR-2: RICellToRIRow()  (AP §5.8.2)
# ---------------------------------------------------------------------------

def _decompose_zb_full_code(zb_full_code: str) -> dict[str, str]:
    """Split ZBFull code into 7 master components. AP §5.2.
    Format: {cat}-{pck}-{src}-{ff}-{alt}-{scn}-{run} where run may contain '-'.
    """
    parts = zb_full_code.split('-', 6)  # maxsplit=6 keeps run_code intact
    if len(parts) < 7:
        return {}
    return {
        "cat_code": parts[0],
        "pck_code": parts[1],
        "src_code": parts[2],
        "ff_code":  parts[3],
        "alt_code": parts[4],
        "scn_code": parts[5],
        "run_code": parts[6],
    }


def RICellToRIRow(ri_cells_month: list[RICellMonth]) -> list[RIRow]:
    """
    Group RICellMonth by (zb_full_code, yb_full_code) → 1 RIRow per group.
    Builds sparse monthly_values dict: {"m2601": value, …}.
    """
    rows_map: dict[tuple[str, str], RIRow] = {}

    for c in ri_cells_month:
        key = (c.zb_full_code, c.yb_full_code)
        if key not in rows_map:
            decomposed = _decompose_zb_full_code(c.zb_full_code)
            rows_map[key] = RIRow(
                row_id=str(uuid.uuid4()),
                zb_full_code=c.zb_full_code,
                yb_full_code=c.yb_full_code,
                monthly_values={},
                uploaded_at=_now(),
                **decomposed,
            )
        rows_map[key].monthly_values[c.month_code] = c.value

    return list(rows_map.values())


# ---------------------------------------------------------------------------
# PPR-3: WriteSORow()  (AP §5.8.3)
# ---------------------------------------------------------------------------

def WriteSORow(ri_row: RIRow, client: bigquery.Client) -> SORow:
    """
    Write RIRow → fpa-t-494007.so_rows.so_rows_pca.
    Month column pattern: time_x_block_{month_code}_value (e.g. time_x_block_m2601_value).
    Meta (z_block_* / now_y_block_*) from RIRow decomposition.

    AP §5.8.3: RIRow only writes monthly columns (m2601..m2712);
    quarterly/half/yearly filled by Calculate Engine.
    """
    so_row_id = ri_row.so_row_id or str(uuid.uuid4())

    # Build BQ row — only non-null fields to save on streaming quota
    bq_row: dict = {
        "so_row_id":                  so_row_id,
        "upload_batch_id":            ri_row.upload_batch_id or "",
        "uploaded_at":                _now().isoformat(),
        "z_block_zblock1_category":   ri_row.cat_code,
        "z_block_zblock1_pack":       ri_row.pck_code,   # ID-01 fix
        "z_block_zblock1_scenario":   ri_row.scn_code,
        "z_block_zblock1_source":     ri_row.src_code,
        "z_block_zblock1_frequency":  ri_row.ff_code,
        "z_block_zblock1_run":        ri_row.run_code,
        "now_zblock2_alt":            ri_row.alt_code,
        "now_y_block_fnf_fnf":        ri_row.fnf,
    }

    # Fan out monthly values → time_x_block_{month_code}_value columns
    for month_code, value in ri_row.monthly_values.items():
        col_name = f"time_x_block_{month_code}_value"  # e.g. time_x_block_m2601_value
        bq_row[col_name] = value

    errors = client.insert_rows_json(SO_ROWS_TABLE, [bq_row])
    if errors:
        raise RuntimeError(f"WriteSORow BQ error: {errors}")

    # Build SORow model (in-memory)
    so_row = SORow(
        so_row_id=so_row_id,
        zb_full_code=ri_row.zb_full_code,
        yb_full_code=ri_row.yb_full_code,
        upload_batch_id=ri_row.upload_batch_id or "",
        uploaded_at=_now(),
        z_block_zblock1_category=ri_row.cat_code,
        z_block_zblock1_pack=ri_row.pck_code,
        z_block_zblock1_scenario=ri_row.scn_code,
        z_block_zblock1_source=ri_row.src_code,
        z_block_zblock1_frequency=ri_row.ff_code,
        z_block_zblock1_run=ri_row.run_code,
        now_zblock2_alt=ri_row.alt_code,
        now_y_block_fnf_fnf=ri_row.fnf,
        time_values=dict(ri_row.monthly_values),
    )
    return so_row


# ---------------------------------------------------------------------------
# PPR-4a: SORowToRICellMonth()  — NEW converter (AP BLOCK Step 21 resolution)
# ---------------------------------------------------------------------------

def SORowToRICellMonth(
    so_row: SORow,
    month_codes: list[str],
) -> list[RICellMonth]:
    """
    Bridge SORow (BQ column format: time_x_block_m2601_value)
    → List[RICellMonth] (month_code='m2601', value=float).

    This converter resolves the field name mismatch in the original AP §5.8.4
    where MonthToPeriod read `value_{m}` instead of `time_x_block_{m}_value`.

    Column format in so_rows_pca: time_x_block_{lowercase_month_code}_value
    month_codes: list of lowercase codes e.g. ['m2601', 'm2602', 'm2603']
    """
    return [
        RICellMonth(
            ri_row_id=so_row.so_row_id,
            yb_full_code=so_row.yb_full_code,
            zb_full_code=so_row.zb_full_code,
            month_code=m,
            value=so_row.get_month_value(m),  # reads time_values dict
        )
        for m in month_codes
    ]


# ---------------------------------------------------------------------------
# PPR-4b: RICell_MonthToPeriod()  (AP §5.8.4)
# ---------------------------------------------------------------------------

def RICell_MonthToPeriod(
    month_values: list[RICellMonth],
    target_xperiod: XPeriod,
    yb_full: YBFull,
) -> RICell:
    """
    Aggregate List[RICellMonth] → 1 RICell for UI display at target XPeriod.

    ppr_mode (AP §5.8.4):
      Same  (KRN/RATE/NOEM): take first month value (all months equal in period)
      Spread (KRF/amount):   SUM all months in period to restore period value
    """
    months_needed = set(target_xperiod.expand_to_months())
    relevant = [c for c in month_values if c.month_code in months_needed]

    ppr_mode = yb_full.effective_ppr_mode()

    if ppr_mode == "Same":
        value = relevant[0].value if relevant else 0.0
    else:  # Spread
        value = sum(c.value for c in relevant)

    # Determine zb_full_code from first cell (all cells in group share same zb)
    zb_full_code = relevant[0].zb_full_code if relevant else ""

    return RICell(
        cell_id=str(uuid.uuid4()),
        entry_id="",  # filled by caller
        yb_full_code=yb_full.yb_full_code,
        xperiod_code=target_xperiod.xperiod_code,
        zb_full_code=zb_full_code,
        now_y_block_fnf_fnf=yb_full.fnf,
        now_value=value,
        time_col_name=target_xperiod.xperiod_code,
    )


# ---------------------------------------------------------------------------
# Orchestration: prepare_for_calculate (DOWN)  (AP §5.9.2)
# ---------------------------------------------------------------------------

def prepare_for_calculate(
    ri_cells: list[RICell],
    yb_fulls: dict[str, YBFull],
    xperiods: dict[str, XPeriod],
    client: bigquery.Client,
) -> list[SORow]:
    """
    Full PPR DOWN: RICell list → SORow list written to so_rows_pca.
    yb_fulls: {yb_full_code: YBFull}
    xperiods: {xperiod_code: XPeriod}
    AP §5.9.2 orchestration pseudocode.
    """
    ri_cells_month: list[RICellMonth] = []
    for cell in ri_cells:
        yb = yb_fulls.get(cell.yb_full_code)
        xp = xperiods.get(cell.xperiod_code)
        if not yb or not xp:
            continue
        ri_cells_month.extend(RICell_PeriodToMonth(cell, yb, xp))  # PPR-1

    ri_rows = RICellToRIRow(ri_cells_month)  # PPR-2

    so_rows = []
    for rr in ri_rows:
        so_row = WriteSORow(rr, client)  # PPR-3
        so_rows.append(so_row)

    return so_rows


# ---------------------------------------------------------------------------
# Orchestration: load_for_ui (UP)  (AP §5.9.2)
# ---------------------------------------------------------------------------

def load_for_ui(
    zb_full_code: str,
    yb_fulls: list[YBFull],
    xperiods: list[XPeriod],
    client: bigquery.Client,
) -> list[RICell]:
    """
    Full PPR UP: query so_rows_pca → reconstruct RICell per (yb, xperiod) for UI.
    AP §5.9.2 load_for_ui pseudocode.
    """
    if not yb_fulls or not xperiods:
        return []

    yb_codes = [yb.yb_full_code for yb in yb_fulls]
    xp_month_codes = list({m for xp in xperiods for m in xp.expand_to_months()})

    # Build SELECT for only the month columns we need
    month_col_selects = ", ".join(
        f"time_x_block_{m}_value" for m in xp_month_codes
    )

    query = f"""
        SELECT so_row_id, z_block_zblock1_category, z_block_zblock1_scenario,
               z_block_zblock1_source, z_block_zblock1_frequency, z_block_zblock1_run,
               now_zblock2_alt, now_y_block_fnf_fnf,
               {month_col_selects}
        FROM `{SO_ROWS_TABLE}`
        WHERE CONCAT(z_block_zblock1_category, '-', z_block_zblock1_pack, '-',
                     z_block_zblock1_source, '-', z_block_zblock1_frequency, '-',
                     now_zblock2_alt, '-', z_block_zblock1_scenario, '-',
                     z_block_zblock1_run) = @zb_full_code
        AND now_y_block_fnf_fnf IN UNNEST(@yb_codes)
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("zb_full_code", "STRING", zb_full_code),
        bigquery.ArrayQueryParameter("yb_codes", "STRING", yb_codes),
    ])

    bq_rows = list(client.query(query, job_config=job_config).result())
    yb_map = {yb.yb_full_code: yb for yb in yb_fulls}
    xp_map = {xp.xperiod_code: xp for xp in xperiods}

    result: list[RICell] = []
    for bq_row in bq_rows:
        # Build SORow from BQ row
        so_row = SORow(
            so_row_id=bq_row.so_row_id,
            zb_full_code=zb_full_code,
            yb_full_code=bq_row.now_y_block_fnf_fnf,  # using fnf as yb proxy; real impl maps via so_row_id
            time_values={m: getattr(bq_row, f"time_x_block_{m}_value", 0.0) or 0.0
                         for m in xp_month_codes},
        )

        yb = yb_map.get(so_row.yb_full_code)
        if not yb:
            continue

        # PPR UP: SORowToRICellMonth → RICell_MonthToPeriod per XPeriod
        month_cells = SORowToRICellMonth(so_row, xp_month_codes)  # PPR-4a

        for xp in xperiods:
            ri_cell = RICell_MonthToPeriod(month_cells, xp, yb)  # PPR-4b
            result.append(ri_cell)

    return result
