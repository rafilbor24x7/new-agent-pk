import os
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.api.tools import router as tools_router

app = FastAPI(title="new-agent-pk")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(tools_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/admin/upload_esklp")
async def upload_esklp(
    file: UploadFile = File(...),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, str]:
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN is not configured")
    if x_admin_token != admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")

    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    esklp_dir_value = os.getenv("ESKLP_DIR")
    if not esklp_dir_value:
        raise HTTPException(status_code=503, detail="ESKLP_DIR is not configured")

    esklp_dir = Path(esklp_dir_value)
    esklp_dir.mkdir(parents=True, exist_ok=True)
    destination = esklp_dir / filename
    destination.write_bytes(await file.read())

    return {"saved": filename, "path": str(destination)}