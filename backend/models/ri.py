"""
RI module — canonical Pydantic v2 data models.
Cross-referenced with AP_FPA-T2_RI_V10_20260424.md §1, §5.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Master entities (AP §2.4 /masters/*)
# ---------------------------------------------------------------------------

class MasterBase(BaseModel):
    code: str
    name: str
    description: str = ""


class CAT(MasterBase):
    pass


class PCK(MasterBase):
    pass


class SRC(MasterBase):
    pass


class FF(MasterBase):
    """Frequency Filter — MF/QF/HF/YF"""
    pass


class ALT(MasterBase):
    """Alternative scenario type (PLA4, …)"""
    pass


class SCN(MasterBase):
    """Scenario — OPT / REAL / PESS"""
    scn_type: Literal["OPT", "REAL", "PESS"]


class RUN(BaseModel):
    run_code: str  # e.g. RUN2026APR24-142233
    run_ts: datetime


# ---------------------------------------------------------------------------
# KRItem / FilterItem → KRFull / FilterFull → YBFull
# AP §5.1 compose logic
# ---------------------------------------------------------------------------

class KRItem(BaseModel):
    kr_item_code: str
    level_code: str  # L1 / L2 / … / L8
    name: str = ""


class FilterItem(BaseModel):
    filter_item_code: str
    level_code: str
    name: str = ""


class KRFull(BaseModel):
    """Derived from KRItem set. kr_full_code = join(kr1..kr8, '-')"""
    kr_full_code: str
    items: list[KRItem] = []


class FilterFull(BaseModel):
    """Derived from FilterItem set. filter_full_code = join(cdt..td_bu, '-')"""
    filter_full_code: str
    items: list[FilterItem] = []


class YBFull(BaseModel):
    """
    1 row of the entry grid.  yb_full_code = f"{kr_full_code}__{filter_full_code}"
    (double underscore separator — AP §5.1)
    ppr_mode: explicit or auto-derived from fnf (KRN→Same, KRF→Spread).
    """
    yb_full_code: str
    kr_full_code: str
    filter_full_code: str
    fnf: Literal["KRN", "KRF"] = "KRN"
    unit: str = ""  # bVND / mVND / mUSD / % / pers / hrs / #
    ppr_mode: Literal["Same", "Spread"] | None = None
    sort_order: int = 0

    def effective_ppr_mode(self) -> Literal["Same", "Spread"]:
        if self.ppr_mode:
            return self.ppr_mode
        return "Same" if self.fnf == "KRN" else "Spread"


# ---------------------------------------------------------------------------
# XPeriod — grid column  (AP §5.8.1)
# ---------------------------------------------------------------------------

class XPeriod(BaseModel):
    """
    xperiod_code convention: {type}{YY}{end_month_MM}
      MF → M2603 (monthly Mar 2026)
      QF → Q2603 (quarter ending Mar 2026 = Jan/Feb/Mar)
      HF → H2606 (half ending Jun 2026)
      YF → Y26   (year 2026, all 12 months)
    """
    xperiod_code: str
    period_type: Literal["MF", "QF", "HF", "YF"]
    label: str = ""
    sort_order: int = 0

    def expand_to_months(self) -> list[str]:
        """
        Expand XPeriod → ordered list of month codes (lowercase, e.g. 'm2601').
        MF→1M  QF→3M  HF→6M  YF→12M  (AP §5.8.1 table).
        """
        code = self.xperiod_code

        if self.period_type == "MF":
            # M2603 → ["m2603"]
            return [f"m{code[1:]}"]

        elif self.period_type == "YF":
            # Y26 → ["m2601".."m2612"]
            yy = code[1:]  # "26"
            return [f"m{yy}{mm:02d}" for mm in range(1, 13)]

        elif self.period_type in ("QF", "HF"):
            n_months = 3 if self.period_type == "QF" else 6
            yy = int(code[1:3])   # 26
            end_mm = int(code[3:5])  # 03
            months = []
            for i in range(n_months - 1, -1, -1):
                mm = end_mm - i
                y = yy
                if mm <= 0:
                    mm += 12
                    y -= 1
                months.append(f"m{y:02d}{mm:02d}")
            return months

        raise ValueError(f"Unknown period_type: {self.period_type}")


# ---------------------------------------------------------------------------
# ZBFull — 7-master composite  (AP §5.2)
# ---------------------------------------------------------------------------

class ZBFull(BaseModel):
    """
    ZBFull = CAT + PCK + SRC + FF + ALT + SCN + RUN (7 masters).
    zb_full_code = f"{cat}-{pck}-{src}-{ff}-{alt}-{scn}-{run_code}"
    """
    zb_full_code: str
    cat_code: str
    pck_code: str
    src_code: str
    ff_code: str
    alt_code: str
    scn_code: str
    run_code: str

    @classmethod
    def build_code(cls, cat: str, pck: str, src: str, ff: str, alt: str, scn: str, run: str) -> str:
        return f"{cat}-{pck}-{src}-{ff}-{alt}-{scn}-{run}"

    def to_key(self) -> str:
        return self.build_code(
            self.cat_code, self.pck_code, self.src_code, self.ff_code,
            self.alt_code, self.scn_code, self.run_code,
        )


# ---------------------------------------------------------------------------
# RIScreenConfig  (AP §1.2)
# ---------------------------------------------------------------------------

class RIScreenConfig(BaseModel):
    """
    Template layout for the entry grid.
    is_seed=True → 5 PPR-PCA-* system seeds (PUT/DELETE blocked, Clone allowed).
    yb_full_codes: list of ybfull codes (soft warn > 30).
    xperiod_codes: list of xperiod codes (soft warn > 10).
    """
    config_id: str
    config_code: str  # PPR-PCA-GH / PPR-PCA-COH / … or user-defined
    config_name: str
    is_seed: bool = False
    yb_full_codes: list[str] = Field(default_factory=list)
    xperiod_codes: list[str] = Field(default_factory=list)
    created_by: str = ""
    created_at: datetime
    updated_at: datetime

    @property
    def yb_full_count_warning(self) -> bool:
        return len(self.yb_full_codes) > 30

    @property
    def xperiod_count_warning(self) -> bool:
        return len(self.xperiod_codes) > 10


# ---------------------------------------------------------------------------
# RIScreenEntry  (AP §1.1 — new entity)
# ---------------------------------------------------------------------------

class RIScreenEntry(BaseModel):
    """
    Instance of an entry session. 1 Save → 3 entries (OPT/REAL/PESS).
    zb_full_code is UNIQUE (1:1 with ZBFull).
    """
    entry_id: str
    config_id: str
    zb_full_code: str  # UNIQUE FK → ZBFull
    scn_type: Literal["OPT", "REAL", "PESS"]
    run_code: str
    created_by: str = ""
    created_at: datetime
    status: Literal["DRAFT", "SAVED"] = "DRAFT"


# ---------------------------------------------------------------------------
# UICell — FE-only, NEVER persisted to BQ  (AP §1.1 #3)
# ---------------------------------------------------------------------------

class UICell(BaseModel):
    """
    Transient FE state only. No entry_id, no cell_id.
    Discarded on page reload — becomes RICell only after Save.
    """
    yb_full_code: str
    xperiod_code: str
    scn_type: Literal["OPT", "REAL", "PESS"]
    value: float | None = None
    is_dirty: bool = False


# ---------------------------------------------------------------------------
# RICell — persisted cell  (AP §1.1 #4, mirrors so_cell_v1)
# ---------------------------------------------------------------------------

class RICell(BaseModel):
    """
    Persisted after Save. Mirrors fpa-t-494007.so_cell.so_cell_v1 schema.
    Key fields from AP §1.1: entry_id FK (replaces upload_batch_id), plus
    z_block_* and now_y_block_* metadata.
    """
    cell_id: str
    entry_id: str
    yb_full_code: str
    xperiod_code: str
    zb_full_code: str
    # Z-block metadata (from ZBFull decomposition)
    z_block_zblock1_category: str = ""
    z_block_zblock1_scenario: str = ""
    z_block_zblock1_source: str = ""
    z_block_zblock1_frequency: str = ""
    z_block_zblock1_run: str = ""
    now_zblock2_alt: str = ""
    # Y-block metadata
    now_y_block_fnf_fnf: str = ""  # KRN / KRF
    # Values
    now_value: float = 0.0
    prev_value: float = 0.0
    # Meta
    time_col_name: str = ""   # e.g. "m2601"
    now_np: str = ""
    prev_np: str = ""
    so_row_id: str = ""


# ---------------------------------------------------------------------------
# RICellMonth — PPR intermediate  (AP §5.8.1)
# ---------------------------------------------------------------------------

class RICellMonth(BaseModel):
    """
    Intermediate after PeriodToMonth expansion.
    month_code uses lowercase format matching so_rows_pca columns: 'm2601'.
    """
    ri_row_id: str = ""
    yb_full_code: str
    zb_full_code: str
    month_code: str   # e.g. "m2601"  (lowercase, matching time_x_block_m2601_value)
    value: float


# ---------------------------------------------------------------------------
# RIRow — persisted row  (AP §1.1 #5, mirrors so_rows_pca)
# ---------------------------------------------------------------------------

class RIRow(BaseModel):
    """
    Groups RICellMonth by (ZBFull, YBFull).
    monthly_values: sparse dict { "m2601": value, … }
    Mirrors fpa-t-494007.so_rows.so_rows_pca time_x_block_* schema.
    """
    row_id: str
    so_row_id: str = ""    # PK join vs so_rows_pca
    zb_full_code: str
    yb_full_code: str
    # Z-block decomposed (for WriteSORow)
    cat_code: str = ""
    pck_code: str = ""
    src_code: str = ""
    ff_code: str = ""
    alt_code: str = ""
    scn_code: str = ""
    run_code: str = ""
    fnf: str = ""          # KRN / KRF  (from YBFull.fnf)
    # Sparse month vector — keys are lowercase month codes e.g. "m2601"
    monthly_values: dict[str, float] = Field(default_factory=dict)
    upload_batch_id: str = ""
    uploaded_at: datetime | None = None


# ---------------------------------------------------------------------------
# SORow — BigQuery so_rows_pca row representation  (AP §5.8.3)
# ---------------------------------------------------------------------------

class SORow(BaseModel):
    """
    In-memory representation of a so_rows_pca row.
    Time columns stored as dict to avoid 203-field explosion in Pydantic.
    Key: time_x_block_{period_code}_value (e.g. time_x_block_m2601_value)
    """
    so_row_id: str
    zb_full_code: str
    yb_full_code: str
    upload_batch_id: str = ""
    uploaded_at: datetime | None = None
    z_block_zblock1_category: str = ""
    z_block_zblock1_pack: str = ""
    z_block_zblock1_scenario: str = ""
    z_block_zblock1_source: str = ""
    z_block_zblock1_frequency: str = ""
    z_block_zblock1_run: str = ""
    now_zblock2_alt: str = ""
    now_y_block_fnf_fnf: str = ""
    # Time values stored as sparse dict: {"m2601": 100.0, …}
    # Column name pattern in BQ: time_x_block_{code}_value
    time_values: dict[str, float] = Field(default_factory=dict)

    def get_month_value(self, month_code: str) -> float:
        """Read time_x_block_{month_code}_value — e.g. month_code='m2601'"""
        return self.time_values.get(month_code, 0.0)

    def set_month_value(self, month_code: str, value: float) -> None:
        self.time_values[month_code] = value


# ---------------------------------------------------------------------------
# Request/Response schemas for API  (AP §2.4)
# ---------------------------------------------------------------------------

class SaveConfigRequest(BaseModel):
    config_code: str | None = None
    config_name: str
    rows: list[dict]       # [{kr_items: [...], filter_items: [...], ppr_mode?, unit?}]
    xperiod_codes: list[str]
    created_by: str = ""


class SaveEntryRequest(BaseModel):
    """
    POST /api/ri/entries payload.
    SCN is NOT at top level — each cell carries its scn_type.
    AP §3.3.3: 1 Save → 3 RIScreenEntry (OPT/REAL/PESS).
    """
    config_id: str
    cat: str
    pck: str
    src: str
    ff: str
    alt: str
    cells: list[dict]   # [{yb_full_code, xperiod_code, scn_type, value}]
    created_by: str = ""


class EntryTemplateResponse(BaseModel):
    """GET /api/ri/entries/template/{config_id} response (AP P03)"""
    config: RIScreenConfig
    yb_fulls: list[YBFull]
    xperiods: list[XPeriod]
    masters: dict  # {CAT_OPTIONS, PCK_OPTIONS, …}


class ConfigListItem(BaseModel):
    config_id: str
    config_code: str
    config_name: str
    is_seed: bool
    yb_full_count: int
    xperiod_count: int
    created_at: datetime
