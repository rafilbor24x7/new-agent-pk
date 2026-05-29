import os
from pathlib import Path
from threading import Lock, Thread

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.api.tools import router as tools_router
from app.api.tools import get_esklp_lookup, has_esklp_lookup, reload_esklp_lookup

_ESKLP_LOAD_LOCK = Lock()
_ESKLP_LOAD_STATUS: dict[str, object] = {
    "status": "ready",
    "rows": None,
    "error": None,
}

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
    sample: list[dict[str, object]] = []
    load_status = _get_esklp_load_status()
    esklp_tn_rows = load_status["rows"]

    if esklp_dir_value:
        esklp_dir = Path(esklp_dir_value)
        if esklp_dir.exists() and esklp_dir.is_dir():
            files = sorted(path.name for path in esklp_dir.glob("*.xlsx") if path.is_file())

        if has_esklp_lookup():
            lookup = get_esklp_lookup()
            if esklp_tn_rows is None:
                esklp_tn_rows = _count_esklp_tn_rows(lookup)
            sample = _sample_esklp_tn(lookup)

    return {
        "esklp_dir": esklp_dir_value,
        "files": files,
        "esklp_tn_rows": esklp_tn_rows,
        "status": load_status["status"],
        "error": load_status["error"],
        "sample": sample,
    }


@app.post("/admin/reload_esklp")
def reload_esklp(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, object]:
    _require_admin_token(x_admin_token)

    if not os.getenv("ESKLP_DIR"):
        raise HTTPException(status_code=503, detail="ESKLP_DIR is not configured")

    _set_esklp_load_status(status="loading", rows=None, error=None)
    Thread(target=_reload_esklp_in_background, daemon=True).start()
    return {"status": "loading"}


def _reload_esklp_in_background() -> None:
    try:
        lookup = reload_esklp_lookup()
        rows = _count_esklp_tn_rows(lookup)
    except Exception as exc:  # pragma: no cover - defensive production diagnostics
        _set_esklp_load_status(status="error", rows=None, error=str(exc))
        return

    _set_esklp_load_status(status="ready", rows=rows, error=None)


def _count_esklp_tn_rows(lookup: object) -> int:
    return int(lookup.connection.execute("SELECT count(*) FROM esklp_tn").fetchone()[0])


def _sample_esklp_tn(lookup: object) -> list[dict[str, object]]:
    rows = lookup.connection.execute(
        """
        SELECT trade_name, mnn, form, dosage, smnn_code
        FROM esklp_tn
        LIMIT 3
        """
    ).fetch_df()
    return rows.where(rows.notna(), None).to_dict("records")


def _get_esklp_load_status() -> dict[str, object]:
    with _ESKLP_LOAD_LOCK:
        return dict(_ESKLP_LOAD_STATUS)


def _set_esklp_load_status(
    *,
    status: str,
    rows: int | None,
    error: str | None,
) -> None:
    with _ESKLP_LOAD_LOCK:
        _ESKLP_LOAD_STATUS.update({"status": status, "rows": rows, "error": error})


def _reload_esklp_for_tests() -> dict[str, object]:
    lookup = reload_esklp_lookup()
    rows = _count_esklp_tn_rows(lookup)
    _set_esklp_load_status(status="ready", rows=rows, error=None)
    return {"status": "ready", "rows": rows}


def _require_admin_token(x_admin_token: str | None) -> None:
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN is not configured")
    if x_admin_token != admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")
