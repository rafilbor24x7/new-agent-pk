from fastapi.testclient import TestClient

from app.main import app


class FakeLLMClient:
    def __init__(self, result):
        self.result = result
        self.last_sku = None

    def can_match_pk(self):
        return True

    def match_pk(self, sku, pk_list, candidates):
        self.last_sku = sku
        return self.result


def test_search_esklp_tool_finds_mnn_with_atx(monkeypatch):
    monkeypatch.setenv("ESKLP_DIR", "data/esklp_test")
    from app.api.tools import get_esklp_lookup

    get_esklp_lookup.cache_clear()
    client = TestClient(app)

    response = client.post("/tools/search_esklp", json={"trade_name": "Ибупрофен"})

    assert response.status_code == 200
    data = response.json()
    assert data
    assert data[0]["mnn"] == "Ибупрофен"
    assert data[0]["atx_code"] == "M01AE"
    assert data[0]["ftg_name"] == "Нестероидные противовоспалительные препараты"


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


def test_match_pk(monkeypatch):
    from app.api import tools

    fake_pk = [
        {"tg": "Лекарственные препараты", "tk": "Анальгетики", "pk": "Ибупрофен таблетки"},
        {"tg": "БАД", "tk": "Витамины", "pk": "Витамин Д (жидкие формы)"},
        {"tg": "Медицинские изделия", "tk": "Перевязочные материалы", "pk": "Медицинский клеевой материал"},
    ]
    monkeypatch.setattr(tools, "load_pk_list", lambda: fake_pk)
    tools.get_llm_client.cache_clear()
    client = TestClient(app)

    response = client.post(
        "/tools/match_pk",
        json={"trade_name": "Ибупрофен 200 мг таблетки", "mnn": "Ибупрофен", "form": "таблетки"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "auto_matched"
    assert data["pk"] == "Ибупрофен таблетки"

    bad_llm = FakeLLMClient(
        {
            "pk": "Витамин Д (жидкие формы)",
            "tg": "БАД",
            "tk": "Витамины",
            "confidence": 0.93,
            "reason": "bad_without_mnn",
        }
    )
    monkeypatch.setattr(tools, "get_llm_client", lambda: bad_llm)
    response = client.post(
        "/tools/match_pk",
        json={
            "trade_name": "Аквадетрим капли",
            "atx_code": "A11CC",
            "atx_name": "Витамин D и аналоги",
            "ftg_name": "кальциево-фосфорного обмена регулятор",
        },
    )
    assert response.status_code == 200
    assert response.json()["pk"] == "Витамин Д (жидкие формы)"
    assert bad_llm.last_sku["atx_code"] == "A11CC"
    assert bad_llm.last_sku["ftg_name"] == "кальциево-фосфорного обмена регулятор"

    med_llm = FakeLLMClient(
        {
            "pk": "Медицинский клеевой материал",
            "tg": "Медицинские изделия",
            "tk": "Перевязочные материалы",
            "confidence": 0.94,
            "reason": "medical_device",
        }
    )
    monkeypatch.setattr(tools, "get_llm_client", lambda: med_llm)
    response = client.post("/tools/match_pk", json={"trade_name": "лейкопластырь медицинский"})
    assert response.status_code == 200
    assert response.json()["pk"] == "Медицинский клеевой материал"

def test_upload_base_tool():
    client = TestClient(app)

    with open("tests/fixtures/base_sample.xlsx", "rb") as file:
        response = client.post(
            "/tools/upload_base",
            files={"file": ("base_sample.xlsx", file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["file_id"]
    assert data["columns_ok"] is True
    assert data["rows"] > 0

def test_build_excel():
    client = TestClient(app)

    with open("tests/fixtures/base_sample.xlsx", "rb") as file:
        upload_response = client.post(
            "/tools/upload_base",
            files={"file": ("base_sample.xlsx", file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    base_file_id = upload_response.json()["file_id"]

    response = client.post(
        "/tools/build_excel",
        json={
            "base_file_id": base_file_id,
            "matched_skus": [
                {
                    "sku": {
                        "sku_name_raw": "Ибупрофен 200 мг таблетки №20",
                        "mnn": "Ибупрофен",
                        "form": "таблетки",
                        "dosage": "200 мг",
                        "zc": 45,
                        "rc": 60,
                    },
                    "match": {
                        "pk": "Терапия и профилактика пероральные формы для взрослых",
                        "tg": "Аптечные препараты и нутрицевтики",
                        "tk": "Средства при ОРВИ и простудных состояниях",
                        "confidence": 0.93,
                        "status": "auto_matched",
                        "reason": "test",
                    },
                }
            ],
        },
    )

    assert response.status_code == 200
    download_url = response.json()["download_url"]
    assert download_url.startswith("/tools/download/")

    download_response = client.get(download_url)
    assert download_response.status_code == 200
    assert download_response.content.startswith(b"PK")