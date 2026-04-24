"""
Step 21 — PPR DOWN/UP round-trip integration tests.
Tests: save → load restores original values for Same and Spread ppr_mode.
AP §5.8: RICell_PeriodToMonth → RICellToRIRow → WriteSORow → SORowToRICellMonth → RICell_MonthToPeriod.
ISP Step 21 + AP BLOCK resolution: SORowToRICellMonth bridges the field name mismatch.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from backend.models.ri import (
    RICell, RICellMonth, RIRow, SORow, YBFull, XPeriod,
)
from backend.services.ppr_service import (
    RICell_PeriodToMonth,
    RICellToRIRow,
    WriteSORow,
    SORowToRICellMonth,
    RICell_MonthToPeriod,
    prepare_for_calculate,
    load_for_ui,
)


def _make_yb(fnf: str = "KRN", ppr_mode: str = "Same") -> YBFull:
    return YBFull(
        yb_full_code=f"{fnf}__NONE",
        kr_full_code=fnf,
        filter_full_code="NONE",
        fnf=fnf,
        unit="",
        ppr_mode=ppr_mode,
        sort_order=1,
    )


def _make_xperiod(code: str, period_type: str) -> XPeriod:
    return XPeriod(
        xperiod_code=code,
        period_type=period_type,
        label=code,
        sort_order=1,
    )


def _make_ri_cell(yb: YBFull, xp: XPeriod, value: float, zb: str = "Z1") -> RICell:
    return RICell(
        cell_id=str(uuid.uuid4()),
        entry_id=str(uuid.uuid4()),
        yb_full_code=yb.yb_full_code,
        xperiod_code=xp.xperiod_code,
        zb_full_code=zb,
        now_y_block_fnf_fnf=yb.fnf,
        now_value=value,
        time_col_name=xp.xperiod_code,
    )


# ---------------------------------------------------------------------------
# PPR-1: RICell_PeriodToMonth
# ---------------------------------------------------------------------------

class TestRICellPeriodToMonth:

    def test_mf_same_produces_1_month(self):
        yb = _make_yb("KRN", "Same")
        xp = _make_xperiod("M2601", "MF")
        cell = _make_ri_cell(yb, xp, 100.0)
        months = RICell_PeriodToMonth(cell, yb, xp)
        assert len(months) == 1
        assert months[0].month_code == "m2601"
        assert months[0].value == pytest.approx(100.0)

    def test_qf_same_produces_3_months_equal(self):
        """Same mode: each month gets the FULL value (not divided)."""
        yb = _make_yb("KRN", "Same")
        xp = _make_xperiod("Q2603", "QF")  # Jan-Feb-Mar 2026
        cell = _make_ri_cell(yb, xp, 300.0)
        months = RICell_PeriodToMonth(cell, yb, xp)
        assert len(months) == 3
        for m in months:
            assert m.value == pytest.approx(300.0)

    def test_qf_spread_produces_3_months_divided(self):
        """Spread mode: value divided equally across 3 months."""
        yb = _make_yb("KRF", "Spread")
        xp = _make_xperiod("Q2603", "QF")
        cell = _make_ri_cell(yb, xp, 300.0)
        months = RICell_PeriodToMonth(cell, yb, xp)
        assert len(months) == 3
        for m in months:
            assert m.value == pytest.approx(100.0)

    def test_hf_spread_produces_6_months(self):
        """HF = 6 months."""
        yb = _make_yb("KRF", "Spread")
        xp = _make_xperiod("H2606", "HF")
        cell = _make_ri_cell(yb, xp, 600.0)
        months = RICell_PeriodToMonth(cell, yb, xp)
        assert len(months) == 6
        for m in months:
            assert m.value == pytest.approx(100.0)

    def test_yf_spread_produces_12_months(self):
        """YF = 12 months."""
        yb = _make_yb("KRF", "Spread")
        xp = _make_xperiod("Y2612", "YF")
        cell = _make_ri_cell(yb, xp, 1200.0)
        months = RICell_PeriodToMonth(cell, yb, xp)
        assert len(months) == 12
        for m in months:
            assert m.value == pytest.approx(100.0)

    def test_cross_year_quarter(self):
        """Q2601 (Quarter ending Jan 2026) = [m2511, m2512, m2601] — AP cross-year logic."""
        xp = _make_xperiod("Q2601", "QF")
        months_expanded = xp.expand_to_months()
        assert "m2511" in months_expanded
        assert "m2512" in months_expanded
        assert "m2601" in months_expanded
        assert len(months_expanded) == 3


# ---------------------------------------------------------------------------
# PPR-2: RICellToRIRow
# ---------------------------------------------------------------------------

class TestRICellToRIRow:

    def test_groups_by_zb_and_yb(self):
        """Two cells with same (zb, yb) → 1 RIRow with 2 month values."""
        cells = [
            RICellMonth(ri_row_id="", yb_full_code="YB1", zb_full_code="Z1", month_code="m2601", value=100.0),
            RICellMonth(ri_row_id="", yb_full_code="YB1", zb_full_code="Z1", month_code="m2602", value=200.0),
        ]
        rows = RICellToRIRow(cells)
        assert len(rows) == 1
        assert rows[0].monthly_values == {"m2601": 100.0, "m2602": 200.0}

    def test_different_yb_creates_separate_rows(self):
        cells = [
            RICellMonth(ri_row_id="", yb_full_code="YB1", zb_full_code="Z1", month_code="m2601", value=100.0),
            RICellMonth(ri_row_id="", yb_full_code="YB2", zb_full_code="Z1", month_code="m2601", value=200.0),
        ]
        rows = RICellToRIRow(cells)
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# PPR-4a: SORowToRICellMonth
# ---------------------------------------------------------------------------

class TestSORowToRICellMonth:

    def test_reads_time_values_by_month_code(self):
        """SORow.time_values uses month_code keys (e.g. 'm2601') — AP BLOCK resolution."""
        so_row = SORow(
            so_row_id="SO1",
            zb_full_code="Z1",
            yb_full_code="YB1",
            time_values={"m2601": 100.0, "m2602": 200.0, "m2603": 300.0},
        )
        month_codes = ["m2601", "m2602", "m2603"]
        cells = SORowToRICellMonth(so_row, month_codes)
        assert len(cells) == 3
        vals = {c.month_code: c.value for c in cells}
        assert vals["m2601"] == pytest.approx(100.0)
        assert vals["m2602"] == pytest.approx(200.0)
        assert vals["m2603"] == pytest.approx(300.0)

    def test_missing_month_returns_zero(self):
        so_row = SORow(
            so_row_id="SO1",
            zb_full_code="Z1",
            yb_full_code="YB1",
            time_values={"m2601": 50.0},
        )
        cells = SORowToRICellMonth(so_row, ["m2601", "m2602"])
        vals = {c.month_code: c.value for c in cells}
        assert vals["m2601"] == pytest.approx(50.0)
        assert vals["m2602"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# PPR-4b: RICell_MonthToPeriod
# ---------------------------------------------------------------------------

class TestRICellMonthToPeriod:

    def test_same_mode_takes_first_month_value(self):
        yb = _make_yb("KRN", "Same")
        xp = _make_xperiod("Q2603", "QF")
        months = [
            RICellMonth(ri_row_id="", yb_full_code="YB1", zb_full_code="Z1", month_code="m2601", value=300.0),
            RICellMonth(ri_row_id="", yb_full_code="YB1", zb_full_code="Z1", month_code="m2602", value=300.0),
            RICellMonth(ri_row_id="", yb_full_code="YB1", zb_full_code="Z1", month_code="m2603", value=300.0),
        ]
        ri_cell = RICell_MonthToPeriod(months, xp, yb)
        assert ri_cell.now_value == pytest.approx(300.0)

    def test_spread_mode_sums_months(self):
        """Spread: period value = SUM of monthly values (restores original)."""
        yb = _make_yb("KRF", "Spread")
        xp = _make_xperiod("Q2603", "QF")
        months = [
            RICellMonth(ri_row_id="", yb_full_code="YB1", zb_full_code="Z1", month_code="m2601", value=100.0),
            RICellMonth(ri_row_id="", yb_full_code="YB1", zb_full_code="Z1", month_code="m2602", value=100.0),
            RICellMonth(ri_row_id="", yb_full_code="YB1", zb_full_code="Z1", month_code="m2603", value=100.0),
        ]
        ri_cell = RICell_MonthToPeriod(months, xp, yb)
        assert ri_cell.now_value == pytest.approx(300.0)


# ---------------------------------------------------------------------------
# Full round-trip: DOWN then UP
# ---------------------------------------------------------------------------

class TestPPRRoundTrip:

    def test_same_mode_round_trip_mf(self):
        """MF Same: write 100 → read back 100."""
        yb = _make_yb("KRN", "Same")
        xp = _make_xperiod("M2601", "MF")
        original_value = 100.0

        # DOWN: PeriodToMonth → RICellToRIRow
        cell = _make_ri_cell(yb, xp, original_value)
        month_cells = RICell_PeriodToMonth(cell, yb, xp)
        ri_rows = RICellToRIRow(month_cells)

        # Simulate SORow (as if WriteSORow then read back)
        ri_row = ri_rows[0]
        so_row = SORow(
            so_row_id=str(uuid.uuid4()),
            zb_full_code=ri_row.zb_full_code,
            yb_full_code=ri_row.yb_full_code,
            time_values=dict(ri_row.monthly_values),
        )

        # UP: SORowToRICellMonth → MonthToPeriod
        month_codes = xp.expand_to_months()
        month_cells_up = SORowToRICellMonth(so_row, month_codes)
        restored_cell = RICell_MonthToPeriod(month_cells_up, xp, yb)

        assert restored_cell.now_value == pytest.approx(original_value)

    def test_spread_mode_round_trip_qf(self):
        """QF Spread: write 300 → divide by 3 → sum back = 300."""
        yb = _make_yb("KRF", "Spread")
        xp = _make_xperiod("Q2603", "QF")
        original_value = 300.0

        cell = _make_ri_cell(yb, xp, original_value)
        month_cells = RICell_PeriodToMonth(cell, yb, xp)
        ri_rows = RICellToRIRow(month_cells)
        ri_row = ri_rows[0]

        so_row = SORow(
            so_row_id=str(uuid.uuid4()),
            zb_full_code=ri_row.zb_full_code,
            yb_full_code=ri_row.yb_full_code,
            time_values=dict(ri_row.monthly_values),
        )

        month_codes = xp.expand_to_months()
        month_cells_up = SORowToRICellMonth(so_row, month_codes)
        restored_cell = RICell_MonthToPeriod(month_cells_up, xp, yb)

        assert restored_cell.now_value == pytest.approx(original_value)

    def test_spread_mode_round_trip_hf(self):
        """HF Spread: write 600 → divide by 6 → sum back = 600."""
        yb = _make_yb("KRF", "Spread")
        xp = _make_xperiod("H2606", "HF")
        original_value = 600.0

        cell = _make_ri_cell(yb, xp, original_value)
        month_cells = RICell_PeriodToMonth(cell, yb, xp)
        ri_rows = RICellToRIRow(month_cells)
        ri_row = ri_rows[0]

        so_row = SORow(
            so_row_id=str(uuid.uuid4()),
            zb_full_code=ri_row.zb_full_code,
            yb_full_code=ri_row.yb_full_code,
            time_values=dict(ri_row.monthly_values),
        )

        month_codes = xp.expand_to_months()
        month_cells_up = SORowToRICellMonth(so_row, month_codes)
        restored_cell = RICell_MonthToPeriod(month_cells_up, xp, yb)

        assert restored_cell.now_value == pytest.approx(original_value)

    def test_multiple_yb_round_trip(self):
        """Multiple YBFull rows: each restores independently."""
        yb_same = _make_yb("KRN", "Same")
        yb_spread = _make_yb("KRF", "Spread")
        xp = _make_xperiod("Q2603", "QF")
        zb = "CAT-PCK-SRC-QF-ALT-REAL-RUN2026APR24-142233"

        cells = [
            _make_ri_cell(yb_same, xp, 200.0, zb),
            _make_ri_cell(yb_spread, xp, 300.0, zb),
        ]

        # DOWN
        all_month_cells: list[RICellMonth] = []
        for c, yb in zip(cells, [yb_same, yb_spread]):
            all_month_cells.extend(RICell_PeriodToMonth(c, yb, xp))

        ri_rows = RICellToRIRow(all_month_cells)
        assert len(ri_rows) == 2

        # UP — per YBFull
        month_codes = xp.expand_to_months()
        for ri_row, (original_cell, yb) in zip(
            sorted(ri_rows, key=lambda r: r.yb_full_code),
            sorted(zip(cells, [yb_same, yb_spread]), key=lambda x: x[0].yb_full_code),
        ):
            so_row = SORow(
                so_row_id=str(uuid.uuid4()),
                zb_full_code=ri_row.zb_full_code,
                yb_full_code=ri_row.yb_full_code,
                time_values=dict(ri_row.monthly_values),
            )
            month_cells_up = SORowToRICellMonth(so_row, month_codes)
            restored = RICell_MonthToPeriod(month_cells_up, xp, yb)
            assert restored.now_value == pytest.approx(original_cell.now_value)


# ---------------------------------------------------------------------------
# WriteSORow: column format test
# ---------------------------------------------------------------------------

class TestWriteSORow:

    def test_writes_time_x_block_columns(self):
        """WriteSORow must write time_x_block_{month_code}_value (not value_{m})."""
        ri_row = RIRow(
            row_id=str(uuid.uuid4()),
            zb_full_code="Z1",
            yb_full_code="YB1",
            monthly_values={"m2601": 100.0, "m2602": 200.0},
        )
        mock_client = MagicMock()
        mock_client.insert_rows_json.return_value = []

        WriteSORow(ri_row, mock_client)

        call_args = mock_client.insert_rows_json.call_args
        bq_row = call_args[0][1][0]  # first arg = table, second = rows list, [0] = first row

        assert "time_x_block_m2601_value" in bq_row
        assert bq_row["time_x_block_m2601_value"] == pytest.approx(100.0)
        assert "time_x_block_m2602_value" in bq_row
        assert bq_row["time_x_block_m2602_value"] == pytest.approx(200.0)

        # Must NOT use old field name format
        assert "value_m2601" not in bq_row
        assert "value_M2601" not in bq_row
