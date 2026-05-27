from fastapi import FastAPI

app = FastAPI(title="new-agent-pk")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
