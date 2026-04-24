"""Tests for RI Pydantic models — Step 1 (AP §1, §5)"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from backend.models.ri import (
    ZBFull, YBFull, XPeriod, RIScreenConfig, RIScreenEntry,
    UICell, RICell, RICellMonth, RIRow, SORow, KRFull, FilterFull,
)

NOW = datetime(2026, 4, 24, 10, 0, 0, tzinfo=timezone.utc)


class TestZBFull:
    def test_to_key_format(self):
        zb = ZBFull(
            zb_full_code="PLN-PK1-GH-MF-PLA4-OPT-RUN2026APR24-142233",
            cat_code="PLN", pck_code="PK1", src_code="GH",
            ff_code="MF", alt_code="PLA4", scn_code="OPT",
            run_code="RUN2026APR24-142233",
        )
        assert zb.to_key() == "PLN-PK1-GH-MF-PLA4-OPT-RUN2026APR24-142233"

    def test_build_code_classmethod(self):
        code = ZBFull.build_code("PLN", "PK1", "GH", "MF", "PLA4", "REAL", "RUN001")
        assert code == "PLN-PK1-GH-MF-PLA4-REAL-RUN001"


class TestYBFull:
    def test_effective_ppr_mode_explicit(self):
        yb = YBFull(yb_full_code="a__b", kr_full_code="a", filter_full_code="b",
                    fnf="KRF", ppr_mode="Same")
        assert yb.effective_ppr_mode() == "Same"

    def test_effective_ppr_mode_krf_default(self):
        yb = YBFull(yb_full_code="a__b", kr_full_code="a", filter_full_code="b", fnf="KRF")
        assert yb.effective_ppr_mode() == "Spread"

    def test_effective_ppr_mode_krn_default(self):
        yb = YBFull(yb_full_code="a__b", kr_full_code="a", filter_full_code="b", fnf="KRN")
        assert yb.effective_ppr_mode() == "Same"


class TestXPeriod:
    def test_expand_mf(self):
        xp = XPeriod(xperiod_code="M2603", period_type="MF")
        assert xp.expand_to_months() == ["m2603"]

    def test_expand_qf_q1_2026(self):
        # Q2603 = Q1 2026 = [Jan, Feb, Mar]
        xp = XPeriod(xperiod_code="Q2603", period_type="QF")
        assert xp.expand_to_months() == ["m2601", "m2602", "m2603"]

    def test_expand_qf_q4_2026(self):
        # Q2612 = Q4 2026 = [Oct, Nov, Dec]
        xp = XPeriod(xperiod_code="Q2612", period_type="QF")
        assert xp.expand_to_months() == ["m2610", "m2611", "m2612"]

    def test_expand_hf_h1_2026(self):
        # H2606 = H1 2026 = Jan-Jun
        xp = XPeriod(xperiod_code="H2606", period_type="HF")
        months = xp.expand_to_months()
        assert months == ["m2601", "m2602", "m2603", "m2604", "m2605", "m2606"]

    def test_expand_yf_y26(self):
        # Y26 = full year 2026, 12 months
        xp = XPeriod(xperiod_code="Y26", period_type="YF")
        months = xp.expand_to_months()
        assert len(months) == 12
        assert months[0] == "m2601"
        assert months[-1] == "m2612"

    def test_expand_qf_cross_year(self):
        # Q2603 ends March — months don't cross year here
        # Q2601 ends Jan 2026 = [Nov 2025, Dec 2025, Jan 2026]
        xp = XPeriod(xperiod_code="Q2601", period_type="QF")
        months = xp.expand_to_months()
        assert months == ["m2511", "m2512", "m2601"]


class TestRIScreenConfig:
    def _make_config(self, **kwargs):
        defaults = dict(
            config_id="cfg-001", config_code="PPR-PCA-GH",
            config_name="GH Template", created_at=NOW, updated_at=NOW,
        )
        return RIScreenConfig(**{**defaults, **kwargs})

    def test_is_seed_default_false(self):
        cfg = self._make_config()
        assert cfg.is_seed is False

    def test_yb_full_count_warning(self):
        cfg = self._make_config(yb_full_codes=[f"yb{i}" for i in range(31)])
        assert cfg.yb_full_count_warning is True

    def test_xperiod_count_warning(self):
        cfg = self._make_config(xperiod_codes=[f"xp{i}" for i in range(11)])
        assert cfg.xperiod_count_warning is True

    def test_no_warning_at_limits(self):
        cfg = self._make_config(
            yb_full_codes=[f"yb{i}" for i in range(30)],
            xperiod_codes=[f"xp{i}" for i in range(10)],
        )
        assert cfg.yb_full_count_warning is False
        assert cfg.xperiod_count_warning is False


class TestRIScreenEntry:
    def test_valid_scn_types(self):
        for scn in ("OPT", "REAL", "PESS"):
            entry = RIScreenEntry(
                entry_id="e-001", config_id="cfg-001",
                zb_full_code=f"A-B-C-D-E-{scn}-RUN001",
                scn_type=scn, run_code="RUN001", created_at=NOW,
            )
            assert entry.scn_type == scn

    def test_invalid_scn_type_raises(self):
        with pytest.raises(ValidationError):
            RIScreenEntry(
                entry_id="e-001", config_id="cfg-001",
                zb_full_code="A-B-C-D-E-INVALID-RUN001",
                scn_type="INVALID", run_code="RUN001", created_at=NOW,
            )

    def test_status_default_draft(self):
        entry = RIScreenEntry(
            entry_id="e-001", config_id="cfg-001",
            zb_full_code="A-B-C-D-E-OPT-RUN001",
            scn_type="OPT", run_code="RUN001", created_at=NOW,
        )
        assert entry.status == "DRAFT"


class TestUICell:
    def test_no_entry_id_field(self):
        """UICell must NOT have entry_id — it is FE-only, not persisted."""
        cell = UICell(yb_full_code="yb1", xperiod_code="M2601", scn_type="OPT")
        assert not hasattr(cell, "entry_id")
        assert not hasattr(cell, "cell_id")

    def test_value_nullable(self):
        cell = UICell(yb_full_code="yb1", xperiod_code="M2601", scn_type="OPT")
        assert cell.value is None

    def test_is_dirty_default_false(self):
        cell = UICell(yb_full_code="yb1", xperiod_code="M2601", scn_type="OPT", value=100.0)
        assert cell.is_dirty is False


class TestRICellMonth:
    def test_json_round_trip(self):
        obj = RICellMonth(
            yb_full_code="RATE-PRM-BHR__SMI-MAR",
            zb_full_code="PLN-PK1-GH-MF-PLA4-OPT-RUN001",
            month_code="m2601",
            value=1000.0,
        )
        data = obj.model_dump()
        restored = RICellMonth(**data)
        assert restored.month_code == "m2601"
        assert restored.value == 1000.0

    def test_month_code_lowercase(self):
        """month_code must be lowercase to match so_rows_pca column naming."""
        obj = RICellMonth(yb_full_code="yb1", zb_full_code="zb1",
                          month_code="m2601", value=0.0)
        assert obj.month_code == obj.month_code.lower()


class TestSORow:
    def test_get_set_month_value(self):
        row = SORow(so_row_id="sr-001", zb_full_code="zb1", yb_full_code="yb1")
        row.set_month_value("m2601", 500.0)
        assert row.get_month_value("m2601") == 500.0

    def test_missing_month_returns_zero(self):
        row = SORow(so_row_id="sr-001", zb_full_code="zb1", yb_full_code="yb1")
        assert row.get_month_value("m9999") == 0.0
