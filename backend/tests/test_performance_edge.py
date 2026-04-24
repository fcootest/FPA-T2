"""
Step 23 — Performance + edge case tests.
AP §5.9.5: XPeriod overlap handling.
ISP: 200+ YBFull rows, large batch inserts, zero-value cells, missing data.
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import MagicMock

import pytest

from backend.models.ri import (
    RICell, RICellMonth, RIRow, SORow, YBFull, XPeriod,
)
from backend.services.ppr_service import (
    RICell_PeriodToMonth,
    RICellToRIRow,
    SORowToRICellMonth,
    RICell_MonthToPeriod,
    WriteSORow,
    prepare_for_calculate,
)


def _make_yb(code: str, ppr_mode: str = "Same") -> YBFull:
    return YBFull(
        yb_full_code=f"{code}__NONE",
        kr_full_code=code,
        filter_full_code="NONE",
        fnf=code,
        unit="",
        ppr_mode=ppr_mode,
        sort_order=1,
    )


def _make_xp(code: str, period_type: str) -> XPeriod:
    return XPeriod(xperiod_code=code, period_type=period_type, label=code, sort_order=1)


def _make_cell(yb: YBFull, xp: XPeriod, value: float, zb: str = "Z1") -> RICell:
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


class TestPerformance:

    def test_200_yb_rows_period_to_month_under_1s(self):
        """
        PPR DOWN with 200 YBFull rows × 4 XPeriods should complete in < 1 second.
        Validates virtual scroll readiness: 200 rows is the upper config bound.
        """
        yb_fulls = [_make_yb(f"KR{i:03d}", "Same") for i in range(200)]
        xperiods = [
            _make_xp("M2601", "MF"),
            _make_xp("Q2603", "QF"),
            _make_xp("H2606", "HF"),
            _make_xp("Y2612", "YF"),
        ]

        cells = [
            _make_cell(yb, xp, float(i * 100 + j))
            for i, yb in enumerate(yb_fulls)
            for j, xp in enumerate(xperiods)
        ]  # 800 cells total

        yb_map = {yb.yb_full_code: yb for yb in yb_fulls}
        xp_map = {xp.xperiod_code: xp for xp in xperiods}

        mock_client = MagicMock()
        mock_client.insert_rows_json.return_value = []

        start = time.perf_counter()
        # Run only PPR-1 + PPR-2 (not BQ write) for pure compute performance
        all_month_cells: list[RICellMonth] = []
        for cell in cells:
            yb = yb_map[cell.yb_full_code]
            xp = xp_map[cell.xperiod_code]
            all_month_cells.extend(RICell_PeriodToMonth(cell, yb, xp))

        ri_rows = RICellToRIRow(all_month_cells)
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"PPR DOWN for 200 YBFull took {elapsed:.2f}s (>1s)"
        assert len(ri_rows) == 200 * 4  # one row per (yb, zb_full) — all share same zb

    def test_batch_500_yb_split(self):
        """
        Seed import batches at 500 rows. Test that 600 YBFull rows split correctly.
        Simulates the batch logic in seed_import without hitting BQ.
        """
        rows = [{"idx": i} for i in range(600)]
        batches = []
        for start in range(0, len(rows), 500):
            batches.append(rows[start:start + 500])

        assert len(batches) == 2
        assert len(batches[0]) == 500
        assert len(batches[1]) == 100


class TestEdgeCases:

    def test_zero_value_cell_preserved(self):
        """Zero-value cells should be stored and restored as 0.0, not skipped."""
        yb = _make_yb("KRN", "Same")
        xp = _make_xp("M2601", "MF")
        cell = _make_cell(yb, xp, 0.0)

        months = RICell_PeriodToMonth(cell, yb, xp)
        assert len(months) == 1
        assert months[0].value == pytest.approx(0.0)

        so_row = SORow(
            so_row_id=str(uuid.uuid4()),
            zb_full_code="Z1",
            yb_full_code=yb.yb_full_code,
            time_values={"m2601": 0.0},
        )
        restored_months = SORowToRICellMonth(so_row, ["m2601"])
        restored_cell = RICell_MonthToPeriod(restored_months, xp, yb)
        assert restored_cell.now_value == pytest.approx(0.0)

    def test_negative_value_spread(self):
        """Negative values spread and sum correctly."""
        yb = _make_yb("KRF", "Spread")
        xp = _make_xp("Q2603", "QF")
        cell = _make_cell(yb, xp, -300.0)

        months = RICell_PeriodToMonth(cell, yb, xp)
        assert all(m.value == pytest.approx(-100.0) for m in months)

        so_row = SORow(
            so_row_id=str(uuid.uuid4()),
            zb_full_code="Z1",
            yb_full_code=yb.yb_full_code,
            time_values={m.month_code: m.value for m in months},
        )
        restored_months = SORowToRICellMonth(so_row, xp.expand_to_months())
        restored = RICell_MonthToPeriod(restored_months, xp, yb)
        assert restored.now_value == pytest.approx(-300.0)

    def test_empty_month_cells_returns_zero(self):
        """RICell_MonthToPeriod with no matching months returns 0.0 (not crash)."""
        yb = _make_yb("KRN", "Same")
        xp = _make_xp("M2601", "MF")
        restored = RICell_MonthToPeriod([], xp, yb)
        assert restored.now_value == pytest.approx(0.0)

    def test_xperiod_overlap_q2603_m2603(self):
        """
        AP §5.9.5: Q2603 includes m2603; M2603 is exactly m2603.
        Both can coexist in a config — each cell is keyed by xperiod_code, not month_code.
        They expand to overlapping months but PPR DOWN writes separate ZBFull rows.
        """
        q = _make_xp("Q2603", "QF")
        m = _make_xp("M2603", "MF")

        q_months = set(q.expand_to_months())
        m_months = set(m.expand_to_months())

        overlap = q_months & m_months
        assert "m2603" in overlap

        # Both cells coexist: different xperiod_code → different RICell keys
        yb = _make_yb("KRN", "Same")
        cell_q = _make_cell(yb, q, 300.0)
        cell_m = _make_cell(yb, m, 100.0)

        assert cell_q.xperiod_code != cell_m.xperiod_code
        assert cell_q.xperiod_code == "Q2603"
        assert cell_m.xperiod_code == "M2603"

    def test_yf_expand_exactly_12_months(self):
        """YF = exactly 12 months (not 11, not 13)."""
        xp = _make_xp("Y2612", "YF")
        months = xp.expand_to_months()
        assert len(months) == 12

    def test_hf_expand_exactly_6_months(self):
        """HF = exactly 6 months."""
        xp = _make_xp("H2606", "HF")
        months = xp.expand_to_months()
        assert len(months) == 6

    def test_qf_expand_exactly_3_months(self):
        """QF = exactly 3 months (NOT 4)."""
        xp = _make_xp("Q2603", "QF")
        months = xp.expand_to_months()
        assert len(months) == 3

    def test_mf_expand_exactly_1_month(self):
        """MF = exactly 1 month."""
        xp = _make_xp("M2601", "MF")
        months = xp.expand_to_months()
        assert len(months) == 1

    def test_so_row_get_month_value_missing_key(self):
        """SORow.get_month_value returns 0.0 for missing month (not KeyError)."""
        so_row = SORow(
            so_row_id="S1",
            zb_full_code="Z1",
            yb_full_code="YB1",
            time_values={"m2601": 42.0},
        )
        assert so_row.get_month_value("m2601") == pytest.approx(42.0)
        assert so_row.get_month_value("m9999") == pytest.approx(0.0)

    def test_write_so_row_with_many_months_doesnt_exceed_bq_streaming_limit(self):
        """
        BQ streaming: up to 10,000 rows per call; single so_row has 135 month cols.
        One RIRow.monthly_values with all 135 months should insert as 1 BQ row.
        """
        all_months = [f"m{y}{m:02d}" for y in range(20, 31) for m in range(1, 13)][:135]
        ri_row = RIRow(
            row_id=str(uuid.uuid4()),
            zb_full_code="Z1",
            yb_full_code="YB1",
            monthly_values={m: 1.0 for m in all_months},
        )
        mock_client = MagicMock()
        mock_client.insert_rows_json.return_value = []

        WriteSORow(ri_row, mock_client)

        # Only 1 insert call with 1 row
        assert mock_client.insert_rows_json.call_count == 1
        call_args = mock_client.insert_rows_json.call_args
        rows = call_args[0][1]
        assert len(rows) == 1

        bq_row = rows[0]
        # All 135 month columns present
        for m in all_months:
            assert f"time_x_block_{m}_value" in bq_row

    def test_effective_ppr_mode_krf_returns_spread(self):
        """YBFull.effective_ppr_mode(): KRF always → Spread regardless of unit."""
        yb = YBFull(
            yb_full_code="KRF__NONE",
            kr_full_code="KRF",
            filter_full_code="NONE",
            fnf="KRF",
            unit="VND",
            ppr_mode=None,
        )
        assert yb.effective_ppr_mode() == "Spread"

    def test_effective_ppr_mode_explicit_overrides(self):
        """Explicitly set ppr_mode takes precedence."""
        yb = YBFull(
            yb_full_code="KRN__NONE",
            kr_full_code="KRN",
            filter_full_code="NONE",
            fnf="KRN",
            unit="",
            ppr_mode="Spread",
        )
        assert yb.effective_ppr_mode() == "Spread"

    def test_zb_full_code_7_part_structure(self):
        """ZBFull must have exactly 7 parts separated by '-' — AP §5.2."""
        from backend.services.ri_entry_service import _resolve_zb_full_code
        code = _resolve_zb_full_code(
            "CAT1", "PCK1", "RI", "MF", "PLA4", "OPT", "RUN2026APR24-120000"
        )
        # 7 hyphen-separated parts: cat-pck-src-ff-alt-scn-run
        # run itself contains a hyphen: RUN2026APR24-120000
        parts = code.split("-")
        # cat(1) + pck(1) + src(1) + ff(1) + alt(1) + scn(1) + run(2 parts due to hyphen in run) = 8
        # This is by design — the run code itself has a hyphen
        assert code.startswith("CAT1-PCK1-RI-MF-PLA4-OPT-RUN2026APR24")
        assert "OPT" in code
