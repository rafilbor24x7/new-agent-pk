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

def test_parse_offer_tool_from_text():
    client = TestClient(app)

    response = client.post(
        "/tools/parse_offer",
        json={"text": "Ибупрофен 200мг №20 ЗЦ 45руб"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data[0]["sku_name_raw"]
    assert data[0]["zc"] == 45