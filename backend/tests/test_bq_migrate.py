"""Tests for BQ migration — Step 2"""

from unittest.mock import MagicMock, patch, call
from google.cloud.exceptions import NotFound

from backend.migrations.bq_migrate import (
    ensure_tables, ensure_dataset, RI_YBFULL_COLUMNS, SCHEMAS,
)


def _mock_client(tables_exist: bool = False):
    client = MagicMock()
    client.project = "fpa-t-494007"
    if tables_exist:
        client.get_dataset.return_value = MagicMock()
        client.get_table.return_value = MagicMock()
    else:
        client.get_dataset.side_effect = NotFound("dataset")
        client.get_table.side_effect = NotFound("table")
    return client


class TestEnsureDataset:
    def test_creates_dataset_when_missing(self):
        client = _mock_client(tables_exist=False)
        ensure_dataset(client, "Config_FPA_T")
        client.create_dataset.assert_called_once()

    def test_skips_create_when_dataset_exists(self):
        client = MagicMock()
        client.get_dataset.return_value = MagicMock()
        ensure_dataset(client, "Config_FPA_T")
        client.create_dataset.assert_not_called()


class TestEnsureTables:
    def test_creates_all_tables_when_missing(self):
        client = _mock_client(tables_exist=False)
        client.get_dataset.side_effect = None
        client.get_dataset.return_value = MagicMock()

        results = ensure_tables(client, "Config_FPA_T")

        assert client.create_table.call_count == len(SCHEMAS)
        assert all(v == "created" for v in results.values())

    def test_idempotent_when_tables_exist(self):
        client = MagicMock()
        client.get_dataset.return_value = MagicMock()
        client.get_table.return_value = MagicMock()

        results = ensure_tables(client, "Config_FPA_T")

        client.create_table.assert_not_called()
        assert all(v == "existed" for v in results.values())

    def test_ri_screen_config_schema_has_is_seed(self):
        schema = SCHEMAS["ri_screen_config"]
        field_names = [f.name for f in schema]
        assert "is_seed" in field_names
        is_seed_field = next(f for f in schema if f.name == "is_seed")
        assert is_seed_field.field_type == "BOOL"

    def test_ri_screen_ybfull_has_all_44_columns(self):
        schema = SCHEMAS["ri_screen_ybfull"]
        field_names = [f.name for f in schema]
        for col in RI_YBFULL_COLUMNS:
            assert col in field_names, f"Missing column: {col}"
        assert len(RI_YBFULL_COLUMNS) == 44

    def test_ri_screen_xperiod_schema(self):
        schema = SCHEMAS["ri_screen_xperiod"]
        field_names = [f.name for f in schema]
        assert "xperiod_code" in field_names
        assert "period_type" in field_names
        assert "sort_order" in field_names

    def test_all_expected_tables_in_schemas(self):
        expected = {
            "ri_screen_config", "ri_screen_entry",
            "ri_screen_ybfull", "ri_screen_xperiod",
            "master_cat", "master_pck", "master_src", "master_ff",
            "master_alt", "master_scn", "master_xperiod",
            "master_kr_item", "master_filter_item",
        }
        assert expected.issubset(set(SCHEMAS.keys()))
