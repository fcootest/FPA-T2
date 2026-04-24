"""
Step 18 — GSheets seed reader.
Reads 5 PPR-PCA-* config templates from Google Sheets.
Tab: RI, Row 29 = XPeriod codes, Rows 30-250 = YBFull rows (cols I:BA = 44 cols).
AP BLOCK Step 22 resolution + VOI.md §9.
"""

from __future__ import annotations

import os
from typing import Any

from backend.migrations.bq_migrate import RI_YBFULL_COLUMNS

# ---------------------------------------------------------------------------
# 5 seed config spreadsheet IDs (from VOI.md §9)
# ---------------------------------------------------------------------------

SEED_CONFIGS = [
    {
        "code":     "PPR-PCA-GH",
        "name":     "PPR template cho Group Head",
        "sheet_id": "1x56144Vrrl-a8nz-yzGGTu5uygM4iRUcY1d_XWqC15k",
        "row_count": 173,
    },
    {
        "code":     "PPR-PCA-HQ",
        "name":     "PPR template cho HQ",
        "sheet_id": "1TpZ-kq0AOYijYd91NecivbFRTABPDk0reaeaISRCkoA",
        "row_count": 345,
    },
    {
        "code":     "PPR-PCA-TH",
        "name":     "PPR template cho Tech Head",
        "sheet_id": "1tAiLio9vgCEf8JcevHAhf7cWq_gnE5tMiecKyuk36f4",
        "row_count": 92,
    },
    {
        "code":     "PPR-PCA-COH",
        "name":     "PPR template cho CEO Venture",
        "sheet_id": "1-v5-GzmtAzEvXG2coR7TNjc03fJXMPvllEHsvjrpaSA",
        "row_count": 96,
    },
    {
        "code":     "PPR-PCA-CEH",
        "name":     "PPR template cho Center Head",
        "sheet_id": None,  # ID from GIT-DB_Vault/00_Index
        "row_count": 73,
    },
]

# GSheets range: tab RI, row 29 = XPeriod header, rows 30-250 = YBFull data
# Cols I:BA = columns 9-53 (1-indexed) = 44 cols (RI_YBFULL_COLUMNS)
GSHEET_TAB = "RI"
GSHEET_RANGE = "RI!I29:BA250"   # row 29 = XPeriod codes; rows 30-250 = YBFull
XPERIOD_ROW_INDEX = 0           # first row in range = row 29 = XPeriod
DATA_START_ROW_INDEX = 1        # rows 30-250 = YBFull data


def _build_sheets_service(credentials_path: str | None = None):
    """Build Google Sheets API v4 service using service account."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_path = credentials_path or os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS",
        r"G:\My Drive\FPA-T2\Documents\GIT-DB_Vault\FPA-T DB key.json",
    )
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scopes)
    return build("sheets", "v4", credentials=creds)


def read_seed_config(
    sheet_id: str,
    service=None,
    credentials_path: str | None = None,
) -> dict[str, Any]:
    """
    Read one seed config from GSheets.
    Returns: {
        "xperiod_codes": list[str],   # from row 29 cols I:BA
        "yb_full_rows": list[dict],   # rows 30-250 mapped to RI_YBFULL_COLUMNS
    }
    """
    if service is None:
        service = _build_sheets_service(credentials_path)

    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=GSHEET_RANGE,
    ).execute()

    all_rows = result.get("values", [])
    if not all_rows:
        return {"xperiod_codes": [], "yb_full_rows": []}

    # Row 29 (index 0 in range) = XPeriod codes
    xperiod_row = all_rows[XPERIOD_ROW_INDEX] if all_rows else []
    xperiod_codes = [str(v).strip() for v in xperiod_row if str(v).strip()]

    # Rows 30-250 = YBFull data (up to 220 rows)
    yb_full_rows: list[dict] = []
    for row in all_rows[DATA_START_ROW_INDEX:]:
        if not any(str(v).strip() for v in row):
            continue  # skip empty rows
        # Pad row to 44 cols
        padded = list(row) + [""] * (44 - len(row))
        row_dict = dict(zip(RI_YBFULL_COLUMNS, padded[:44]))
        # Skip rows where fnf is empty (not valid YBFull)
        if not row_dict.get("fnf", "").strip():
            continue
        yb_full_rows.append(row_dict)

    return {"xperiod_codes": xperiod_codes, "yb_full_rows": yb_full_rows}


def read_all_seed_configs(credentials_path: str | None = None) -> list[dict]:
    """
    Read all 5 seed configs from GSheets.
    Returns list of {code, name, sheet_id, xperiod_codes, yb_full_rows}.
    Skips configs with sheet_id=None (PPR-PCA-CEH — needs manual ID).
    """
    service = _build_sheets_service(credentials_path)
    results = []
    for cfg in SEED_CONFIGS:
        if not cfg["sheet_id"]:
            print(f"  SKIP {cfg['code']} — no sheet_id configured")
            continue
        print(f"  Reading {cfg['code']} from GSheets…")
        data = read_seed_config(cfg["sheet_id"], service=service)
        results.append({
            "code":          cfg["code"],
            "name":          cfg["name"],
            "sheet_id":      cfg["sheet_id"],
            "xperiod_codes": data["xperiod_codes"],
            "yb_full_rows":  data["yb_full_rows"],
        })
        print(f"    → {len(data['yb_full_rows'])} YBFull rows, {len(data['xperiod_codes'])} XPeriods")
    return results
