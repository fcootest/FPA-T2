"""
Masters router — Step 5.
AP §2.4 endpoints #9-17: CAT/PCK/SRC/FF/ALT/SCN/KRItem/FilterItem/XPeriod.
"""

from fastapi import APIRouter
from backend.core.bq_client import get_bq_client

router = APIRouter(prefix="/api/ri/masters", tags=["ri-masters"])

DATASET = "Config_FPA_T"


def _query(client, table: str, order: str = "code", active_only: bool = True) -> list[dict]:
    full = f"{client.project}.{DATASET}.{table}"
    where = "WHERE is_active = TRUE" if active_only else ""
    rows = client.query(f"SELECT * FROM `{full}` {where} ORDER BY {order}").result()
    return [dict(r) for r in rows]


@router.get("/cat")
async def get_cat():
    return _query(get_bq_client(), "master_cat")


@router.get("/pck")
async def get_pck():
    return _query(get_bq_client(), "master_pck")


@router.get("/src")
async def get_src():
    return _query(get_bq_client(), "master_src")


@router.get("/ff")
async def get_ff():
    return _query(get_bq_client(), "master_ff")


@router.get("/alt")
async def get_alt():
    return _query(get_bq_client(), "master_alt")


@router.get("/scn")
async def get_scn():
    return _query(get_bq_client(), "master_scn")


@router.get("/kr-items")
async def get_kr_items():
    return _query(get_bq_client(), "master_kr_item", order="level_code")


@router.get("/filter-items")
async def get_filter_items():
    return _query(get_bq_client(), "master_filter_item", order="level_code")


@router.get("/xperiods")
async def get_xperiods():
    return _query(get_bq_client(), "master_xperiod", order="sort_order")


@router.get("/run")
async def get_run():
    return _query(get_bq_client(), "master_run", order="run_ts DESC", active_only=False)
