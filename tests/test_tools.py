from fastapi.testclient import TestClient

from app.main import app


def test_search_esklp_tool_finds_mnn(monkeypatch):
    monkeypatch.setenv("ESKLP_DIR", "data/esklp_test")
    from app.api.tools import get_esklp_lookup

    get_esklp_lookup.cache_clear()
    client = TestClient(app)

    response = client.post("/tools/search_esklp", json={"trade_name": "Ибупрофен"})

    assert response.status_code == 200
    data = response.json()
    assert data
    assert data[0]["mnn"] == "Ибупрофен"