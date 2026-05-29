from fastapi.testclient import TestClient

from app.main import app


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