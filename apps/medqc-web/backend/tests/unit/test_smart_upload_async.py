from __future__ import annotations

import time

import pandas as pd
import pytest

from app.services.smart_upload_async_service import reset_smart_upload_async_service_for_testing


def _login(client, email: str = "admin@medqc.com", password: str = "admin888") -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_xlsx(tmp_path, name: str = "smart_upload.xlsx") -> bytes:
    df = pd.DataFrame(
        [
            {"科室": "内科", "总费用": 1000, "DIP支付标准": 1200},
            {"科室": "外科", "总费用": 2000, "DIP支付标准": 2100},
        ]
    )
    file_path = tmp_path / name
    df.to_excel(file_path, index=False)
    return file_path.read_bytes()


def _wait_for_status(client, task_id: str, headers: dict[str, str], target: str, timeout: float = 8.0):
    deadline = time.time() + timeout
    last_payload = None
    while time.time() < deadline:
        resp = client.get(f"/api/v1/drg/smart-upload/tasks/{task_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        last_payload = payload
        if payload["status"] == target:
            return payload
        if payload["status"] in {"failed", "cancelled"} and payload["status"] != target:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"task {task_id} did not reach {target}; last={last_payload}")


@pytest.fixture(autouse=True)
def _reset_service_state():
    reset_smart_upload_async_service_for_testing()


@pytest.mark.unit
def test_smart_upload_creates_task_and_returns_task_id(client, tmp_path):
    token = _login(client)
    headers = _headers(token)
    payload = _make_xlsx(tmp_path)

    resp = client.post(
        "/api/v1/drg/smart-upload",
        headers=headers,
        files={"file": ("smart_upload.xlsx", payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["task_id"]
    assert body["file_id"]
    assert body["status"] in {"pending", "running"}
    assert body["progress"] <= 100

    status_resp = client.get(f"/api/v1/drg/smart-upload/tasks/{body['task_id']}", headers=headers)
    assert status_resp.status_code == 200, status_resp.text
    status = status_resp.json()
    assert status["task_id"] == body["task_id"]
    assert status["file_id"] == body["file_id"]
    assert status["status"] in {"pending", "running", "succeeded"}


@pytest.mark.unit
def test_smart_upload_status_polling_and_result_success(client, monkeypatch, tmp_path):
    token = _login(client)
    headers = _headers(token)

    async def _fake_mapping(columns, samples):
        return {
            "mappings": {col: col for col in columns},
            "confidence": 0.91,
            "unmapped": [],
            "missing_required": [],
            "fallback": False,
        }

    monkeypatch.setattr("app.services.smart_upload_async_service.suggest_field_mapping", _fake_mapping)

    payload = _make_xlsx(tmp_path, "success.xlsx")
    resp = client.post(
        "/api/v1/drg/smart-upload",
        headers=headers,
        files={"file": ("success.xlsx", payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 202, resp.text
    task_id = resp.json()["task_id"]

    status = _wait_for_status(client, task_id, headers, "succeeded")
    assert status["progress"] == 100
    assert status["error_message"] == ""

    result_resp = client.get(f"/api/v1/drg/smart-upload/tasks/{task_id}/result", headers=headers)
    assert result_resp.status_code == 200, result_resp.text
    result = result_resp.json()
    assert result["success"] is True
    assert result["task_id"] == task_id
    assert result["task_status"] == "succeeded"
    assert result["row_count"] == 2
    assert result["file_count"] == 1
    assert result["sample_data"]
    assert result["columns"]


@pytest.mark.unit
def test_smart_upload_sync_mode_returns_original_payload(client, monkeypatch, tmp_path):
    token = _login(client)
    headers = _headers(token)

    async def _fake_mapping(columns, samples):
        return {
            "mappings": {col: col for col in columns},
            "confidence": 0.91,
            "unmapped": [],
            "missing_required": [],
            "fallback": False,
        }

    monkeypatch.setattr("app.services.smart_upload_async_service.suggest_field_mapping", _fake_mapping)

    payload = _make_xlsx(tmp_path, "sync.xlsx")
    resp = client.post(
        "/api/v1/drg/smart-upload?sync=true",
        headers=headers,
        files={"file": ("sync.xlsx", payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["row_count"] == 2
    assert body["file_count"] == 1
    assert "task_id" not in body


@pytest.mark.unit
def test_smart_upload_task_failure_is_reported(client, monkeypatch, tmp_path):
    token = _login(client)
    headers = _headers(token)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.services.smart_upload_async_service.MultiFileProcessor.explore_files", _boom)

    payload = _make_xlsx(tmp_path, "failure.xlsx")
    resp = client.post(
        "/api/v1/drg/smart-upload",
        headers=headers,
        files={"file": ("failure.xlsx", payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 202, resp.text
    task_id = resp.json()["task_id"]

    status = _wait_for_status(client, task_id, headers, "failed")
    assert status["status"] == "failed"
    assert status["finished_at"] is not None
    assert "文件处理失败" in status["error_message"]
    assert "boom" not in status["error_message"]

    result_resp = client.get(f"/api/v1/drg/smart-upload/tasks/{task_id}/result", headers=headers)
    assert result_resp.status_code == 409
    payload = result_resp.json()
    detail = payload.get("error") or payload.get("detail") or payload
    assert detail["status"] == "failed"


@pytest.mark.unit
def test_smart_upload_cancel_running_task_marks_request(client, monkeypatch, tmp_path):
    token = _login(client)
    headers = _headers(token)

    def _slow_build(self, task_id):
        time.sleep(0.4)
        return {
            "success": True,
            "file_id": "unused",
            "filename": "unused.xlsx",
            "row_count": 1,
            "columns": ["科室"],
            "file_count": 1,
            "sample_data": [{"科室": "内科"}],
        }

    monkeypatch.setattr("app.services.smart_upload_async_service.SmartUploadAsyncService._build_result", _slow_build)

    payload = _make_xlsx(tmp_path, "cancel.xlsx")
    resp = client.post(
        "/api/v1/drg/smart-upload",
        headers=headers,
        files={"file": ("cancel.xlsx", payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 202, resp.text
    task_id = resp.json()["task_id"]

    status = _wait_for_status(client, task_id, headers, "running")
    assert status["status"] == "running"

    cancel_resp = client.post(f"/api/v1/drg/smart-upload/tasks/{task_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200, cancel_resp.text
    cancel_body = cancel_resp.json()
    assert cancel_body["cancel_requested"] is True

    final_status = _wait_for_status(client, task_id, headers, "cancelled")
    assert final_status["status"] == "cancelled"
    assert final_status["cancel_requested"] is True
