"""
Tests for GET /api/ri/masters/* endpoints (BUG-010).
9 endpoints: cat, pck, src, ff, alt, scn, kr-items, filter-items, xperiods.
Uses mock BQ client — no real BQ calls.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, patch

from backend.main import app
from backend.core import bq_client as bq_module


def _make_mock_client(rows: list[dict]):
    """Return a mock BQ client whose .query().result() yields row-like objects."""
    mock_row_list = [MagicMock(**{k: v for k, v in r.items()}) for r in rows]
    for mock_row, r in zip(mock_row_list, rows):
        mock_row.__iter__ = lambda self: iter(r.items())
        mock_row.keys = lambda: list(r.keys())

    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter(mock_row_list))
    mock_query = MagicMock()
    mock_query.result.return_value = mock_result

    client = MagicMock()
    client.project = "fpa-t-494007"
    client.query.return_value = mock_query
    client.insert_rows_json.return_value = []
    return client


def _patch_client(rows: list[dict]):
    return patch.object(bq_module, "get_bq_client", return_value=_make_mock_client(rows))


@pytest.mark.asyncio
async def test_get_cat_returns_list():
    rows = [{"code": "PCA", "name": "PCA", "description": "", "is_active": True}]
    with _patch_client(rows):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/ri/masters/cat")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_get_pck_returns_list():
    rows = [{"code": "GH", "name": "GH", "description": "", "is_active": True}]
    with _patch_client(rows):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/ri/masters/pck")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_get_src_returns_list():
    rows = [{"code": "INT", "name": "Internal", "description": "", "is_active": True}]
    with _patch_client(rows):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/ri/masters/src")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_get_ff_returns_list():
    rows = [{"code": "MF", "name": "Monthly", "description": "", "is_active": True}]
    with _patch_client(rows):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/ri/masters/ff")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_get_alt_returns_list():
    rows = [{"code": "PLA4", "name": "PLA4", "description": "", "is_active": True}]
    with _patch_client(rows):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/ri/masters/alt")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_get_scn_returns_list():
    rows = [{"code": "OPT", "name": "Optimistic", "scn_type": "OPT", "is_active": True}]
    with _patch_client(rows):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/ri/masters/scn")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_get_kr_items_returns_list():
    rows = [{"kr_item_code": "VOL", "level_code": "L1", "name": "Volume", "is_active": True}]
    with _patch_client(rows):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/ri/masters/kr-items")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_get_filter_items_returns_list():
    rows = [{"filter_item_code": "ALL", "level_code": "L0", "name": "All", "is_active": True}]
    with _patch_client(rows):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/ri/masters/filter-items")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_get_xperiods_returns_list():
    rows = [{"xperiod_code": "M2601", "period_type": "MF", "label": "Jan-26", "sort_order": 1, "is_active": True}]
    with _patch_client(rows):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/ri/masters/xperiods")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
