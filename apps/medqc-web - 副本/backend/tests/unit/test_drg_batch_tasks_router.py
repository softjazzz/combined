from __future__ import annotations

import asyncio
import threading
import time
import uuid

import pytest

from app.services.drg import batch_service, batch_task_service


def _login(client, email: str = "admin@medqc.com", password: str = "admin888") -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _upload_csv(rows: list[dict[str, object]]) -> bytes:
    header = [
        "病案号",
        "性别",
        "年龄",
        "科室代码",
        "科室名称",
        "住院天数",
        "离院方式",
        "诊断列表",
        "手术操作列表",
        "总费用",
        "医保支付",
        "主管医生",
        "药品费",
        "耗材费",
        "检查费",
        "治疗费",
    ]
    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(str(row.get(col, "")) for col in header))
    return "\n".join(lines).encode("utf-8")


class _FakeBatchStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: dict[str, list[dict[str, object]]] = {}
        self._session_seq = 0
        self._batch_seq = 0

    def create_session(self) -> str:
        with self._lock:
            self._session_seq += 1
            session_id = f"session-{self._session_seq:03d}"
            self._sessions[session_id] = []
            return session_id

    def generate_batch_id(self) -> str:
        with self._lock:
            self._batch_seq += 1
            return f"BATCH_FAKE_{self._batch_seq:03d}"

    def save_batch_record(self, session_id: str, data: dict[str, object]) -> int:
        with self._lock:
            self._sessions.setdefault(session_id, []).append(dict(data))
            return len(self._sessions[session_id])

    def get_all_records(self, session_id: str, batch_id: str | None = None):
        return [dict(row) for row in self._sessions.get(session_id, []) if batch_id is None or row.get("batch_id") == batch_id]

    def drill_down(self, session_id: str, dimension: str, value: str, page: int = 1, per_page: int = 20, batch_id: str | None = None):
        records = self.get_all_records(session_id, batch_id=batch_id)
        return records, len(records)

    def get_statistics(self, session_id: str, batch_id: str | None = None, start_date: str | None = None, end_date: str | None = None, department: str | None = None, doctor: str | None = None):
        records = self.get_all_records(session_id, batch_id=batch_id)
        total_cases = len(records)
        success_count = sum(1 for row in records if row.get("status") == "分组成功")
        total_cost = sum(float(row.get("total_cost") or 0) for row in records)
        total_profit = sum(float(row.get("profit_margin") or 0) for row in records)
        avg_los = round(sum(float(row.get("los") or 0) for row in records) / total_cases, 1) if total_cases else 0
        avg_cmi = round(sum(float(row.get("drg_weight") or 0) for row in records) / total_cases, 4) if total_cases else 0
        return {
            "summary": {
                "total_cases": total_cases,
                "success_rate": round((success_count / total_cases) * 100, 2) if total_cases else 0,
                "avg_cmi": avg_cmi,
                "total_cost": round(total_cost, 2),
                "total_insurance": 0,
                "total_baseline": 0,
                "total_profit": round(total_profit, 2),
                "avg_los": avg_los,
            },
            "department_stats": [],
        }

    def get_batch_list(self, session_id: str):
        return []

    def delete_session(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def cleanup_expired_sessions(self) -> int:
        return 0

    def list_active_sessions(self):
        return []


class _SlowGroupingService:
    def __init__(self, delay: float = 0.08):
        self.delay = delay

    async def group_drg(
        self,
        primary_diagnosis: str,
        secondary_diagnoses: list[str],
        procedures: list[str],
        patient_age: int,
        patient_gender: str,
        los: int = 7,
        city_name: str = "四川省",
        total_fee: float = 0,
    ) -> dict[str, object]:
        await asyncio.sleep(self.delay)
        return {
            "success": True,
            "adrg_code": "AD01",
            "drg_code": f"DRG-{primary_diagnosis.replace('.', '')[:4]}",
            "weight": 1.25,
            "baseline_payment": 12345.0,
            "grouping_logic": "mocked",
        }


@pytest.fixture(autouse=True)
def reset_drg_batch_tasks():
    batch_task_service.reset_batch_tasks_for_testing()
    yield
    batch_task_service.reset_batch_tasks_for_testing()


def _submit_batch(client, token: str, rows: list[dict[str, object]]):
    file_bytes = _upload_csv(rows)
    return client.post(
        "/api/v1/drg/batch-upload",
        headers=_headers(token),
        files={"file": ("batch.csv", file_bytes, "text/csv")},
    )


def _wait_for_task(client, token: str, task_id: str, desired_status: str, timeout: float = 5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/v1/drg/batch-tasks/{task_id}", headers=_headers(token))
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        if body["status"] == desired_status:
            return body
        time.sleep(0.05)
    raise AssertionError(f"task {task_id} did not reach {desired_status}")


@pytest.mark.unit
@pytest.mark.api
def test_drg_batch_upload_creates_task_and_returns_final_result(client, monkeypatch):
    fake_store = _FakeBatchStore()
    monkeypatch.setattr("app.routers.drg_operations.drg_batch_store", fake_store)
    monkeypatch.setattr("app.routers.drg.get_drg_grouping_service", lambda: _SlowGroupingService())
    token = _login(client)

    rows = [
        {
            "病案号": f"A00{i}",
            "性别": 1,
            "年龄": 50 + i,
            "科室代码": "1301",
            "科室名称": "内科",
            "住院天数": 7 + i,
            "离院方式": 1,
            "诊断列表": "I10.x05|E11.900",
            "手术操作列表": "36.0600",
            "总费用": 10000 + i * 100,
            "医保支付": 8000,
            "主管医生": "张医生",
            "药品费": 2000,
            "耗材费": 1000,
            "检查费": 500,
            "治疗费": 700,
        }
        for i in range(3)
    ]

    resp = _submit_batch(client, token, rows)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["task_id"]
    assert body["status"] in {"queued", "running"}
    assert body["results"] == []

    detail = _wait_for_task(client, token, body["task_id"], "succeeded")
    assert detail["progress"] == 100
    assert detail["stage"] == "succeeded"
    assert detail["total_records"] == 3
    assert detail["success_count"] == 3
    assert detail["failed_count"] == 0
    assert detail["session_id"]
    assert detail["batch_id"]

    list_resp = client.get("/api/v1/drg/batch-tasks?status=succeeded&sort_by=created_at&order=desc", headers=_headers(token))
    assert list_resp.status_code == 200
    list_body = list_resp.json()["data"]
    assert list_body["total"] >= 1
    assert any(item["task_id"] == body["task_id"] for item in list_body["items"])

    result_resp = client.get(f"/api/v1/drg/batch-tasks/{body['task_id']}/result", headers=_headers(token))
    assert result_resp.status_code == 200, result_resp.text
    result_body = result_resp.json()
    assert result_body["success"] is True
    assert result_body["session_id"] == detail["session_id"]
    assert result_body["batch_id"] == detail["batch_id"]
    assert result_body["total_records"] == 3
    assert len(result_body["results"]) == 3


@pytest.mark.unit
@pytest.mark.api
def test_drg_batch_upload_rejects_same_owner_storm(client, monkeypatch):
    fake_store = _FakeBatchStore()
    monkeypatch.setattr("app.routers.drg_operations.drg_batch_store", fake_store)
    monkeypatch.setattr("app.routers.drg.get_drg_grouping_service", lambda: _SlowGroupingService(delay=0.6))
    token = _login(client)

    rows = [
        {
            "病案号": "A001",
            "性别": 1,
            "年龄": 60,
            "科室代码": "1301",
            "科室名称": "内科",
            "住院天数": 7,
            "离院方式": 1,
            "诊断列表": "I10.x05|E11.900",
            "手术操作列表": "36.0600",
            "总费用": 10000,
            "医保支付": 8000,
            "主管医生": "张医生",
            "药品费": 2000,
            "耗材费": 1000,
            "检查费": 500,
            "治疗费": 700,
        }
    ]

    first = _submit_batch(client, token, rows)
    assert first.status_code == 200, first.text
    second = _submit_batch(client, token, rows)
    assert second.status_code == 200, second.text

    third = _submit_batch(client, token, rows)
    assert third.status_code == 429
    detail = third.json().get("detail") or third.json().get("error")
    assert "待处理的 DRG 批任务过多" in detail


@pytest.mark.unit
@pytest.mark.api
def test_drg_batch_upload_maps_sync_failure_to_task_failed(client, monkeypatch):
    fake_store = _FakeBatchStore()
    monkeypatch.setattr("app.routers.drg_operations.drg_batch_store", fake_store)
    monkeypatch.setattr("app.routers.drg.get_drg_grouping_service", lambda: _SlowGroupingService(delay=0.3))
    monkeypatch.setattr("app.services.drg.batch_service._read_dataframe", lambda contents, filename: (_ for _ in ()).throw(ValueError("broken file")))
    token = _login(client)

    rows = [
        {
            "病案号": "A001",
            "性别": 1,
            "年龄": 60,
            "科室代码": "1301",
            "科室名称": "内科",
            "住院天数": 7,
            "离院方式": 1,
            "诊断列表": "I10.x05|E11.900",
            "手术操作列表": "36.0600",
            "总费用": 10000,
            "医保支付": 8000,
            "主管医生": "张医生",
            "药品费": 2000,
            "耗材费": 1000,
            "检查费": 500,
            "治疗费": 700,
        }
    ]

    resp = _submit_batch(client, token, rows)
    assert resp.status_code == 200, resp.text
    task_id = resp.json()["task_id"]

    detail = _wait_for_task(client, token, task_id, "failed")
    assert detail["stage"] == "failed"
    assert detail["error"]
    assert "broken file" in detail["error"]

    result_resp = client.get(f"/api/v1/drg/batch-tasks/{task_id}/result", headers=_headers(token))
    assert result_resp.status_code == 409
    result_detail = result_resp.json()
    assert result_detail.get("detail") or result_detail.get("error")
