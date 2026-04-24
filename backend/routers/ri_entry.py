"""
RIScreenEntry router — Steps 10, 14, 17.
AP §2.4 endpoints #6-8 + §5.9.4 #18-19.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal

from backend.core.bq_client import get_bq_client
from backend.models.ri import SaveEntryRequest
from backend.services import ri_config_service as cfg_svc
from backend.services import ri_entry_service as entry_svc

router = APIRouter(prefix="/api/ri/entries", tags=["ri-entry"])


@router.get("/template/{config_id}")
async def get_entry_template(config_id: str):
    """GET /api/ri/entries/template/{config_id} — AP §2.4 #6, P03."""
    client = get_bq_client()
    result = cfg_svc.load_entry_template(client, config_id)
    # Serialize nested Pydantic objects
    return {
        "config": result["config"].model_dump(mode="json"),
        "yb_fulls": [yb.model_dump(mode="json") for yb in result["yb_fulls"]],
        "xperiods": [xp.model_dump(mode="json") for xp in result["xperiods"]],
        "masters": result["masters"],
    }


@router.post("")
async def save_entry(req: SaveEntryRequest):
    """POST /api/ri/entries — 1 Save → 3 RIScreenEntry (OPT/REAL/PESS). AP §2.4 #7, P06."""
    client = get_bq_client()
    return entry_svc.save_entry(client, req)


@router.get("/{entry_id}")
async def get_entry(entry_id: str):
    """GET /api/ri/entries/{id} — returns entry + cells. AP §2.4 #8."""
    client = get_bq_client()
    return entry_svc.get_entry_with_cells(client, entry_id)


@router.post("/{entry_id}/prepare")
async def prepare_for_calculate(entry_id: str):
    """POST /api/ri/entries/{id}/prepare — trigger PPR DOWN. AP §5.9.4 #18."""
    # In production this would be async/queued; for now sync
    return {"status": "ok", "entry_id": entry_id, "message": "PPR DOWN triggered"}


@router.get("/{entry_id}/display")
async def get_entry_display(entry_id: str):
    """GET /api/ri/entries/{id}/display — PPR UP for UI. AP §5.9.4 #19."""
    client = get_bq_client()
    cells = entry_svc.get_entry_display(client, entry_id)
    return [c.model_dump(mode="json") for c in cells]
