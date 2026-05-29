import time

from fastapi.testclient import TestClient

from app.main import app, get_esklp_lookup, _reload_esklp_for_tests


def test_upload_esklp_requires_admin_token(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setenv("ESKLP_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/admin/upload_esklp",
        files={"file": ("tn_smnn_test.xlsx", b"content", "application/octet-stream")},
    )

    assert response.status_code == 401


def test_upload_esklp_saves_file(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setenv("ESKLP_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/admin/upload_esklp",
        headers={"X-Admin-Token": "secret"},
        files={"file": ("../esklp_smnn_test.xlsx", b"xlsx-bytes", "application/octet-stream")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["saved"] == "esklp_smnn_test.xlsx"
    saved_path = tmp_path / "esklp_smnn_test.xlsx"
    assert data["path"] == str(saved_path)
    assert saved_path.read_bytes() == b"xlsx-bytes"


def test_upload_esklp_rejects_non_xlsx(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setenv("ESKLP_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/admin/upload_esklp",
        headers={"X-Admin-Token": "secret"},
        files={"file": ("tn_smnn_test.xls", b"content", "application/vnd.ms-excel")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only .xlsx files are supported"


def test_upload_esklp_requires_esklp_dir(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.delenv("ESKLP_DIR", raising=False)
    client = TestClient(app)

    response = client.post(
        "/admin/upload_esklp",
        headers={"X-Admin-Token": "secret"},
        files={"file": ("tn_smnn_test.xlsx", b"content", "application/octet-stream")},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "ESKLP_DIR is not configured"


def test_esklp_status_requires_admin_token(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setenv("ESKLP_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.get("/admin/esklp_status")

    assert response.status_code == 401


def test_esklp_status_returns_dir_files_and_rows(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setenv("ESKLP_DIR", "data/esklp_test")
    get_esklp_lookup.cache_clear()
    _reload_esklp_for_tests()
    client = TestClient(app)

    response = client.get(
        "/admin/esklp_status",
        headers={"X-Admin-Token": "secret"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["esklp_dir"] == "data/esklp_test"
    assert data["files"] == ["esklp_smnn_test.xlsx", "tn_smnn_test.xlsx"]
    assert data["esklp_tn_rows"] == 5
    assert data["columns"] == [
        "trade_name",
        "mnn",
        "form",
        "dosage",
        "smnn_code",
        "smnn_join_key",
    ]
    assert data["status"] == "ready"
    assert data["error"] is None
    assert len(data["sample"]) == 3
    assert data["sample"][0]["trade_name"] == "Ибупрофен"


def test_reload_esklp_requires_admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setenv("ESKLP_DIR", "data/esklp_test")
    client = TestClient(app)

    response = client.post("/admin/reload_esklp")

    assert response.status_code == 401


def test_esklp_debug_returns_raw_rows_like_and_scores(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setenv("ESKLP_DIR", "data/esklp_test")
    get_esklp_lookup.cache_clear()
    _reload_esklp_for_tests()
    client = TestClient(app)

    response = client.post(
        "/admin/esklp_debug",
        headers={"X-Admin-Token": "secret"},
        json={"trade_name": "Ibuprofen"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["trade_name"] == "Ibuprofen"
    assert data["like_pattern"] == "%Ibu%"
    assert len(data["first_rows"]) == 3
    assert set(data["first_rows"][0]) == {
        "trade_name",
        "mnn",
        "form",
        "dosage",
        "smnn_code",
        "smnn_join_key",
    }
    assert isinstance(data["like_matches"], list)
    assert len(data["rapidfuzz_scores"]) == 5
    assert set(data["rapidfuzz_scores"][0]) == {"trade_name", "token_sort_ratio"}


def test_reload_esklp_clears_cached_empty_lookup(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setenv("ESKLP_DIR", str(tmp_path))
    get_esklp_lookup.cache_clear()
    assert get_esklp_lookup().connection.execute("SELECT count(*) FROM esklp_tn").fetchone()[0] == 0

    monkeypatch.setenv("ESKLP_DIR", "data/esklp_test")
    client = TestClient(app)

    response = client.post(
        "/admin/reload_esklp",
        headers={"X-Admin-Token": "secret"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "loading"}

    status = None
    for _ in range(20):
        status_response = client.get(
            "/admin/esklp_status",
            headers={"X-Admin-Token": "secret"},
        )
        status = status_response.json()
        if status["status"] == "ready":
            break
        time.sleep(0.1)

    assert status is not None
    assert status["status"] == "ready"
    assert status["esklp_tn_rows"] == 5
    assert status["error"] is None

    search_response = client.post("/tools/search_esklp", json={"trade_name": "Ибупрофен"})
    assert search_response.status_code == 200
    assert search_response.json()
