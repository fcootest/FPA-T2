"""
RIScreenConfig router — Steps 4-5.
AP §2.4 endpoints #1-6, #18-19.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.core.bq_client import get_bq_client
from backend.models.ri import RIScreenConfig, ConfigListItem, SaveConfigRequest
from backend.services import ri_config_service as svc

router = APIRouter(prefix="/api/ri/configs", tags=["ri-config"])


@router.get("", response_model=list[ConfigListItem])
async def list_configs():
    """GET /api/ri/configs — list all configs. AP §2.4 #1."""
    client = get_bq_client()
    return svc.list_configs(client)


@router.get("/{config_id}", response_model=RIScreenConfig)
async def get_config(config_id: str):
    """GET /api/ri/configs/{id}. AP §2.4 #2."""
    client = get_bq_client()
    return svc.get_config(client, config_id)


@router.post("", response_model=RIScreenConfig, status_code=201)
async def create_config(req: SaveConfigRequest):
    """POST /api/ri/configs — create non-seed config. AP §2.4 #3, P01."""
    client = get_bq_client()
    return svc.create_config(client, req)


@router.put("/{config_id}", response_model=RIScreenConfig)
async def update_config(config_id: str, req: SaveConfigRequest):
    """PUT /api/ri/configs/{id} — non-seed only. AP §2.4 #4."""
    client = get_bq_client()
    return svc.update_config(client, config_id, req)


@router.delete("/{config_id}", status_code=204)
async def delete_config(config_id: str):
    """DELETE /api/ri/configs/{id} — non-seed only. AP §2.4 #5."""
    client = get_bq_client()
    svc.delete_config(client, config_id)


class CloneRequest(BaseModel):
    new_name: str = ""
    created_by: str = ""


@router.post("/{config_id}/clone", response_model=RIScreenConfig, status_code=201)
async def clone_config(config_id: str, req: CloneRequest):
    """POST /api/ri/configs/{id}/clone — clone (including seeds → is_seed=False). AP §2.4 #18."""
    client = get_bq_client()
    return svc.clone_config(client, config_id, req.new_name, req.created_by)


class PasteValidateRequest(BaseModel):
    tsv: str    # tab-separated clipboard text from GSheet


class PasteValidateResponse(BaseModel):
    valid: bool
    rows: list[dict] = []
    errors: list[str] = []


@router.post("/paste-validate", response_model=PasteValidateResponse)
async def paste_validate(req: PasteValidateRequest):
    """
    POST /api/ri/configs/paste-validate — validate TSV from clipboard.
    Parses GSheet tab RI cols I:BA (44 cols). AP §2.4 #19, §3.2.2.
    """
    from backend.migrations.bq_migrate import RI_YBFULL_COLUMNS
    lines = req.tsv.strip().split("\n")
    errors = []
    rows = []

    for i, line in enumerate(lines):
        cols = line.split("\t")
        if len(cols) < 44:
            errors.append(f"Row {i+1}: expected 44 cols, got {len(cols)}")
            continue
        row = dict(zip(RI_YBFULL_COLUMNS, cols[:44]))
        rows.append(row)

    return PasteValidateResponse(valid=len(errors) == 0, rows=rows, errors=errors)
