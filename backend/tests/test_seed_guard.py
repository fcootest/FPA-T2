"""
Step 20 — Seed integrity guard tests.
AP §3.2.3: PUT/DELETE on seed configs → 403.
Clone creates is_seed=False copy.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.bq_client import reset_bq_client

client = TestClient(app)

SEED_CONFIG_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "seed.PPR-PCA-GH"))
SEED_ROW = {
    "config_id":    SEED_CONFIG_ID,
    "config_code":  "PPR-PCA-GH",
    "config_name":  "PPR template cho Group Head",
    "is_seed":      True,
    "yb_full_codes": json.dumps(["KRN__NONE"]),
    "xperiod_codes": json.dumps(["M2601"]),
    "created_by":   "seed_import",
    "created_at":   "2026-01-01T00:00:00+00:00",
    "updated_at":   "2026-01-01T00:00:00+00:00",
}


def _make_mock_client(row_data: dict):
    """Build a mock BQ client that returns row_data for a single row query."""
    mock_row = MagicMock()
    for k, v in row_data.items():
        setattr(mock_row, k, v)
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = [mock_row]
    mock_client = MagicMock()
    mock_client.project = "fpa-t-494007"
    mock_client.query.return_value = mock_query_job
    return mock_client


class TestSeedGuard:
    """AP §3.2.3 — is_seed = True blocks PUT and DELETE via API."""

    def setup_method(self):
        reset_bq_client()

    def test_put_seed_config_returns_403(self):
        mock_client = _make_mock_client(SEED_ROW)
        with patch("backend.core.bq_client._bq_client", mock_client):
            resp = client.put(
                f"/api/ri/configs/{SEED_CONFIG_ID}",
                json={"config_name": "hacked", "grid_rows": []},
            )
        assert resp.status_code == 403
        assert "seed" in resp.json()["detail"].lower()

    def test_delete_seed_config_returns_403(self):
        mock_client = _make_mock_client(SEED_ROW)
        with patch("backend.core.bq_client._bq_client", mock_client):
            resp = client.delete(f"/api/ri/configs/{SEED_CONFIG_ID}")
        assert resp.status_code == 403
        assert "seed" in resp.json()["detail"].lower()

    def test_get_seed_config_allowed(self):
        """GET should work for seed configs."""
        mock_client = _make_mock_client(SEED_ROW)
        # Also mock ybfull + xperiod queries
        yb_row = MagicMock()
        yb_row.ybfull_id = "KRN__NONE"
        yb_row.fnf = "KRN"
        yb_row.unit = ""
        yb_row.ppr_mode = "Same"
        yb_row.kr1 = "KRN"
        yb_row.cdt1 = None
        yb_row.sort_order = 1

        xp_row = MagicMock()
        xp_row.xperiod_code = "M2601"
        xp_row.period_type = "MF"
        xp_row.label = "M2601"
        xp_row.sort_order = 1

        call_count = 0
        def query_side_effect(q, **kwargs):
            nonlocal call_count
            mock_job = MagicMock()
            if call_count == 0:
                mock_job.result.return_value = [MagicMock(**SEED_ROW)]
            elif call_count == 1:
                mock_job.result.return_value = [yb_row]
            else:
                mock_job.result.return_value = [xp_row]
            call_count += 1
            return mock_job

        mock_client = MagicMock()
        mock_client.project = "fpa-t-494007"
        mock_client.query.side_effect = query_side_effect

        with patch("backend.core.bq_client._bq_client", mock_client):
            resp = client.get(f"/api/ri/configs/{SEED_CONFIG_ID}")
        assert resp.status_code == 200


class TestCloneConfig:
    """Clone creates is_seed=False copy — AP §3.2.3."""

    def setup_method(self):
        reset_bq_client()

    def test_clone_creates_non_seed_copy(self):
        """Cloned config must have is_seed=False."""
        mock_client = _make_mock_client(SEED_ROW)

        inserted_rows: list[dict] = []

        def insert_side_effect(table, rows):
            inserted_rows.extend(rows)
            return []

        mock_client.insert_rows_json.side_effect = insert_side_effect

        # Also mock YBFull and XPeriod queries for clone operation
        yb_row = MagicMock()
        yb_row.ybfull_id = "KRN__NONE"
        yb_row.fnf = "KRN"
        yb_row.unit = ""
        yb_row.ppr_mode = "Same"
        yb_row.kr1 = "KRN"
        yb_row.cdt1 = None
        yb_row.sort_order = 1

        xp_row = MagicMock()
        xp_row.xperiod_code = "M2601"
        xp_row.period_type = "MF"
        xp_row.label = "M2601"
        xp_row.sort_order = 1

        call_count = 0
        def query_side_effect(q, **kwargs):
            nonlocal call_count
            mock_job = MagicMock()
            seed_mock = MagicMock()
            for k, v in SEED_ROW.items():
                setattr(seed_mock, k, v)
            if call_count == 0:
                mock_job.result.return_value = [seed_mock]
            elif call_count == 1:
                mock_job.result.return_value = [yb_row]
            else:
                mock_job.result.return_value = [xp_row]
            call_count += 1
            return mock_job

        mock_client.query.side_effect = query_side_effect

        with patch("backend.core.bq_client._bq_client", mock_client):
            resp = client.post(
                f"/api/ri/configs/{SEED_CONFIG_ID}/clone",
                json={"new_name": "My Copy of PPR-PCA-GH"},
            )

        assert resp.status_code == 200
        result = resp.json()
        assert result.get("is_seed") is False or result.get("config", {}).get("is_seed") is False

        # Verify at least one inserted row has is_seed=False
        if inserted_rows:
            config_rows = [r for r in inserted_rows if r.get("config_code", "").startswith("COPY-")]
            assert all(r.get("is_seed") is False for r in config_rows if "is_seed" in r)

    def test_non_seed_config_can_be_updated(self):
        """Non-seed configs allow PUT — AP §3.2.3 (only seed is protected)."""
        non_seed_row = {**SEED_ROW, "is_seed": False, "config_id": str(uuid.uuid4())}
        mock_client = _make_mock_client(non_seed_row)
        mock_client.insert_rows_json.return_value = []

        with patch("backend.core.bq_client._bq_client", mock_client):
            resp = client.put(
                f"/api/ri/configs/{non_seed_row['config_id']}",
                json={"config_name": "Updated Name", "grid_rows": []},
            )
        # Should NOT return 403
        assert resp.status_code != 403


class TestSeedImport:
    """Unit tests for seed_import.py logic."""

    def test_infer_period_type(self):
        from backend.seed.seed_import import _infer_period_type
        assert _infer_period_type("M2601") == "MF"
        assert _infer_period_type("Q2603") == "QF"
        assert _infer_period_type("H2606") == "HF"
        assert _infer_period_type("Y26") == "YF"
        assert _infer_period_type("m2601") == "MF"  # case insensitive

    def test_infer_ppr_mode(self):
        from backend.seed.seed_import import _infer_ppr_mode
        assert _infer_ppr_mode({"fnf": "KRF"}) == "Spread"
        assert _infer_ppr_mode({"fnf": "KRN"}) == "Same"
        assert _infer_ppr_mode({"fnf": "RATE"}) == "Same"
        assert _infer_ppr_mode({}) == "Same"

    def test_dry_run_skips_bq(self):
        """dry_run=True should not call BQ insert."""
        mock_client = MagicMock()
        mock_client.project = "fpa-t-494007"

        fake_configs = [{
            "code": "PPR-PCA-GH",
            "name": "Test",
            "sheet_id": "fake_id",
            "xperiod_codes": ["M2601", "M2602"],
            "yb_full_rows": [{"fnf": "KRN", **{col: "" for col in __import__(
                "backend.migrations.bq_migrate", fromlist=["RI_YBFULL_COLUMNS"]
            ).RI_YBFULL_COLUMNS}}],
        }]

        from backend.seed.seed_import import import_seed_configs
        with patch("backend.seed.seed_import.read_all_seed_configs", return_value=fake_configs):
            result = import_seed_configs(client=mock_client, dry_run=True)

        mock_client.insert_rows_json.assert_not_called()
        assert "PPR-PCA-GH" in result
