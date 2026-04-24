from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.core.bq_client import get_bq_client
from backend.core.config import settings
from backend.routers import ri_config, ri_entry, ri_masters
from backend.startup import run_startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = get_bq_client()
    run_startup(client)
    yield


app = FastAPI(title="FPA-T2 RI API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(ri_config.router)
app.include_router(ri_entry.router)
app.include_router(ri_masters.router)


@app.get("/health")
async def health():
    try:
        client = get_bq_client()
        return {"status": "ok", "bq_project": client.project}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
