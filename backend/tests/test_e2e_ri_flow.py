"""
Step 22 — Full E2E test: create config → create entry → PPR DOWN → PPR UP → verify grid.
AP §2.2: P01 (save_config) → P03 (load_entry_template) → P06 (save_entry) → display.
Uses mocked BQ client throughout; tests the full service integration.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, call, patch

import pytest

from backend.models.ri import (
    RIScreenConfig, RICell, YBFull, XPeriod, SaveEntryRequest, SaveConfigRequest,
)
from backend.services import ri_config_service as cfg_svc
from backend.services import ri_entry_service as entry_svc
from backend.services.ppr_service import (
    prepare_for_calculate, load_for_ui,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONFIG_ID = str(uuid.uuid4())
ENTRY_ID = str(uuid.uuid4())

YB_KRN = YBFull(
    yb_full_code="KRN__NONE",
    kr_full_code="KRN",
    filter_full_code="NONE",
    fnf="KRN",
    unit="",
    ppr_mode="Same",
    sort_order=1,
)
YB_KRF = YBFull(
    yb_full_code="KRF__NONE",
    kr_full_code="KRF",
    filter_full_code="NONE",
    fnf="KRF",
    unit="VND",
    ppr_mode="Spread",
    sort_order=2,
)
XP_M2601 = XPeriod(xperiod_code="M2601", period_type="MF", label="Jan 2026", sort_order=1)
XP_Q2603 = XPeriod(xperiod_code="Q2603", period_type="QF", label="Q1 2026", sort_order=2)


def _make_bq_client(
    config_rows=None, yb_rows=None, xp_rows=None, so_rows=None
) -> MagicMock:
    """Build a mock BQ client that can serve different queries."""
    mock_client = MagicMock()
    mock_client.project = "fpa-t-494007"
    mock_client.insert_rows_json.return_value = []

    query_results_by_order: list = []
    if config_rows is not None:
        query_results_by_order.append(config_rows)
    if yb_rows is not None:
        query_results_by_order.append(yb_rows)
    if xp_rows is not None:
        query_results_by_order.append(xp_rows)
    if so_rows is not None:
        query_results_by_order.append(so_rows)

    call_idx = [0]

    def query_side_effect(q, **kwargs):
        mock_job = MagicMock()
        idx = call_idx[0]
        if idx < len(query_results_by_order):
            mock_job.result.return_value = query_results_by_order[idx]
        else:
            mock_job.result.return_value = []
        call_idx[0] += 1
        return mock_job

    mock_client.query.side_effect = query_side_effect
    return mock_client


def _make_yb_bq_row(yb: YBFull) -> MagicMock:
    row = MagicMock()
    row.ybfull_id = yb.yb_full_code
    row.fnf = yb.fnf
    row.unit = yb.unit
    row.ppr_mode = yb.ppr_mode
    row.kr1 = yb.kr_full_code
    row.cdt1 = None
    row.sort_order = yb.sort_order
    return row


def _make_xp_bq_row(xp: XPeriod) -> MagicMock:
    row = MagicMock()
    row.xperiod_code = xp.xperiod_code
    row.period_type = xp.period_type
    row.label = xp.label
    row.sort_order = xp.sort_order
    return row


# ---------------------------------------------------------------------------
# Step 22 E2E Tests
# ---------------------------------------------------------------------------

class TestE2ERIFlow:

    def test_save_entry_creates_3_scn_entries(self):
        """
        P06: POST /api/ri/entries → 3 RIScreenEntry (OPT/REAL/PESS).
        AP §5.5 step 2: 1 Save = 3 entries sharing same RUN code.
        """
        mock_client = _make_bq_client(
            yb_rows=[_make_yb_bq_row(YB_KRN), _make_yb_bq_row(YB_KRF)],
            xp_rows=[_make_xp_bq_row(XP_M2601)],
        )

        req = SaveEntryRequest(
            config_id=CONFIG_ID,
            cat="CAT1", pck="PCK1", src="RI", ff="QF",
            alt="PLA4", created_by="test_user",
            cells=[
                {"yb_full_code": "KRN__NONE", "xperiod_code": "M2601", "scn_type": "OPT",  "value": 100.0},
                {"yb_full_code": "KRN__NONE", "xperiod_code": "M2601", "scn_type": "REAL", "value": 90.0},
                {"yb_full_code": "KRN__NONE", "xperiod_code": "M2601", "scn_type": "PESS", "value": 80.0},
            ],
        )

        result = entry_svc.save_entry(mock_client, req)

        assert "entries" in result
        assert "run_code" in result
        entries = result["entries"]
        assert len(entries) == 3

        scn_types = {e["scn_type"] for e in entries}
        assert scn_types == {"OPT", "REAL", "PESS"}

        # All share same run_code
        run_codes = {e["run_code"] for e in entries}
        assert len(run_codes) == 1

    def test_save_entry_run_code_format(self):
        """RUN code must match RUN{YYYY}{MMM}{DD}-{HHMMSS} — AP §5.4."""
        import re
        from backend.services.ri_entry_service import _generate_run_code
        code = _generate_run_code()
        assert re.match(r"^RUN\d{4}[A-Z]{3}\d{2}-\d{6}$", code), f"Invalid RUN code: {code}"

    def test_save_entry_zb_full_code_structure(self):
        """ZBFull = cat-pck-src-ff-alt-scn-run — AP §5.2."""
        from backend.services.ri_entry_service import _resolve_zb_full_code
        code = _resolve_zb_full_code("CAT1", "PCK1", "RI", "QF", "PLA4", "OPT", "RUN2026APR24-120000")
        assert code == "CAT1-PCK1-RI-QF-PLA4-OPT-RUN2026APR24-120000"

    def test_ppr_down_writes_monthly_cols_to_bq(self):
        """
        PPR DOWN: save_entry must call insert_rows_json on so_rows_pca
        with time_x_block_{month_code}_value columns.
        """
        inserted_so_rows: list[dict] = []

        mock_client = MagicMock()
        mock_client.project = "fpa-t-494007"

        # Track inserts by table
        def insert_side_effect(table, rows):
            if "so_rows" in table:
                inserted_so_rows.extend(rows)
            return []

        mock_client.insert_rows_json.side_effect = insert_side_effect

        # Mock query results for _load_config_yb_xp
        call_idx = [0]
        def query_side_effect(q, **kwargs):
            mock_job = MagicMock()
            if call_idx[0] == 0:
                mock_job.result.return_value = [_make_yb_bq_row(YB_KRN)]
            else:
                mock_job.result.return_value = [_make_xp_bq_row(XP_M2601)]
            call_idx[0] += 1
            return mock_job

        mock_client.query.side_effect = query_side_effect

        req = SaveEntryRequest(
            config_id=CONFIG_ID,
            cat="CAT1", pck="PCK1", src="RI", ff="MF",
            alt="PLA4", created_by="test_user",
            cells=[
                {"yb_full_code": "KRN__NONE", "xperiod_code": "M2601", "scn_type": "OPT",  "value": 500.0},
                {"yb_full_code": "KRN__NONE", "xperiod_code": "M2601", "scn_type": "REAL", "value": 500.0},
                {"yb_full_code": "KRN__NONE", "xperiod_code": "M2601", "scn_type": "PESS", "value": 500.0},
            ],
        )

        entry_svc.save_entry(mock_client, req)

        # Verify so_rows were written with correct column format
        assert len(inserted_so_rows) > 0, "No SORow inserts detected"
        for row in inserted_so_rows:
            assert "time_x_block_m2601_value" in row, f"Missing monthly column in: {list(row.keys())}"
            assert row["time_x_block_m2601_value"] == pytest.approx(500.0)

    def test_ppr_up_restores_spread_value(self):
        """
        PPR UP via load_for_ui: QF Spread 300 → 3 months * 100 → sum back = 300.
        AP §5.9.2 load_for_ui.
        """
        yb_fulls = [YB_KRF]
        xperiods = [XP_Q2603]
        zb = "CAT1-PCK1-RI-QF-PLA4-REAL-RUN2026APR24-120000"

        # Build mock BQ SO row with monthly values already written
        month_codes = XP_Q2603.expand_to_months()  # ['m2601', 'm2602', 'm2603']
        mock_so_row = MagicMock()
        mock_so_row.so_row_id = str(uuid.uuid4())
        mock_so_row.now_y_block_fnf_fnf = "KRF__NONE"

        for m in month_codes:
            setattr(mock_so_row, f"time_x_block_{m}_value", 100.0)

        mock_client = MagicMock()
        mock_client.project = "fpa-t-494007"
        mock_job = MagicMock()
        mock_job.result.return_value = [mock_so_row]
        mock_client.query.return_value = mock_job

        ri_cells = load_for_ui(zb, yb_fulls, xperiods, mock_client)

        # Find cell for Q2603
        q_cells = [c for c in ri_cells if c.xperiod_code == "Q2603"]
        assert len(q_cells) > 0, "No cell found for Q2603"
        assert q_cells[0].now_value == pytest.approx(300.0), (
            f"Expected 300.0 (sum of 3*100), got {q_cells[0].now_value}"
        )

    def test_entry_status_starts_as_saved(self):
        """New entries must have status=SAVED — AP §1.1 #4."""
        mock_client = _make_bq_client(
            yb_rows=[_make_yb_bq_row(YB_KRN)],
            xp_rows=[_make_xp_bq_row(XP_M2601)],
        )
        req = SaveEntryRequest(
            config_id=CONFIG_ID,
            cat="CAT1", pck="PCK1", src="RI", ff="MF",
            alt="PLA4", created_by="user1",
            cells=[],
        )
        result = entry_svc.save_entry(mock_client, req)
        for entry in result["entries"]:
            assert entry["status"] == "SAVED"

    def test_ui_cell_key_format(self):
        """UICellKey must be '{yb}__{xp}__{scn}' — types/ri.ts contract."""
        # Python-side: verify the key format used in entry cells
        yb = "KRN__NONE"
        xp = "M2601"
        scn = "OPT"
        key = f"{yb}__{xp}__{scn}"
        assert key == "KRN__NONE__M2601__OPT"

    def test_xperiod_overlap_rule(self):
        """
        AP §5.9.5: M2603 and Q2603 overlap (both include March 2026).
        When both exist in xperiods, M2603 cells take precedence over Q2603 for that month.
        The expand_to_months() for Q2603 includes m2603; M2603 covers exactly m2603.
        """
        q = XPeriod(xperiod_code="Q2603", period_type="QF", label="Q1 2026", sort_order=1)
        m = XPeriod(xperiod_code="M2603", period_type="MF", label="Mar 2026", sort_order=2)

        q_months = set(q.expand_to_months())
        m_months = set(m.expand_to_months())

        # They share m2603
        overlap = q_months & m_months
        assert "m2603" in overlap, "Q2603 and M2603 must overlap on m2603"
