from __future__ import annotations


def _login(client, email: str = "admin@medqc.com", password: str = "admin888") -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error_message(resp) -> str:
    payload = resp.json()
    return str(payload.get("error") or payload.get("detail") or "")


def test_tools_upload_rejects_disallowed_extension(client):
    token = _login(client)
    resp = client.post(
        "/api/v1/parse-medical-file-public",
        headers=_headers(token),
        files={"file": ("malicious.exe", b"MZ\x90\x00", "application/octet-stream")},
        data={"options": "{}"},
    )
    assert resp.status_code == 400
    assert "扩展名" in _error_message(resp)


def test_records_upload_rejects_eicar_signature(client):
    token = _login(client)
    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    resp = client.post(
        "/api/v1/records/upload",
        headers=_headers(token),
        files={"file": ("record.txt", eicar, "text/plain")},
    )
    assert resp.status_code == 400
    assert "恶意文件" in _error_message(resp)


def test_drg_batch_upload_rejects_invalid_mime_type(client):
    token = _login(client)
    csv_payload = "病案号,性别,年龄,住院天数,诊断列表,总费用\nA001,1,32,3,I10,1000\n".encode("utf-8")
    resp = client.post(
        "/api/v1/drg/batch-upload",
        headers=_headers(token),
        files={"file": ("sample.csv", csv_payload, "image/png")},
    )
    assert resp.status_code == 400
    assert "文件类型" in _error_message(resp)


def test_smart_upload_rejects_file_too_large(client, monkeypatch):
    token = _login(client)
    monkeypatch.setattr("app.routers.smart_upload.MAX_FILE_SIZE", 8)
    payload = b"0123456789"
    resp = client.post(
        "/api/v1/drg/smart-upload",
        headers=_headers(token),
        files={"file": ("sample.csv", payload, "text/csv")},
    )
    assert resp.status_code == 413
    assert "大小不能超过" in _error_message(resp)
