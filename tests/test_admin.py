from fastapi.testclient import TestClient

from app.main import app, get_esklp_lookup


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
