from fastapi import FastAPI
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