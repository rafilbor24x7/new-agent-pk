import os
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.api.tools import router as tools_router
from app.api.tools import get_esklp_lookup

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
    _require_admin_token(x_admin_token)

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


@app.get("/admin/esklp_status")
def esklp_status(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, object]:
    _require_admin_token(x_admin_token)

    esklp_dir_value = os.getenv("ESKLP_DIR")
    files: list[str] = []
    esklp_tn_rows: int | None = None

    if esklp_dir_value:
        esklp_dir = Path(esklp_dir_value)
        if esklp_dir.exists() and esklp_dir.is_dir():
            files = sorted(path.name for path in esklp_dir.glob("*.xlsx") if path.is_file())

        lookup = get_esklp_lookup()
        esklp_tn_rows = int(
            lookup.connection.execute("SELECT count(*) FROM esklp_tn").fetchone()[0]
        )

    return {
        "esklp_dir": esklp_dir_value,
        "files": files,
        "esklp_tn_rows": esklp_tn_rows,
    }


def _require_admin_token(x_admin_token: str | None) -> None:
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN is not configured")
    if x_admin_token != admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")
