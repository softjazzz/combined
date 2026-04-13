from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO, StringIO
from typing import Any, Dict, List, Optional

import pytest

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
from app.routers import qc_sichuan


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class _ListResult:
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class _InMemorySichuanWorkspaceService:
    def __init__(self) -> None:
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self._counter = 0

    def _next_job_id(self) -> str:
        self._counter += 1
        return f"job-{self._counter:04d}"

    def collect_records(
        self,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        record_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        ids = [str(x) for x in (record_ids or ["visit-1001", "visit-1002"])]
        return [
            {
                "record_id": rid,
                "visit_id": rid,
                "patient_name": f"患者-{idx + 1}",
                "department": department or "骨科",
                "doctor": doctor or "王医生",
                "scope": scope,
            }
            for idx, rid in enumerate(ids)
        ]

    def hydrate_records_with_medical_text(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                **item,
                "medical_text": f"病历正文-{item.get('record_id')}",
            }
            for item in records
        ]

    def create_batch_job(
        self,
        *,
        draft: Dict[str, Any],
        created_by: str,
        scope: str,
        filters: Dict[str, Any],
        record_ids: List[str],
        total_records: int,
    ) -> Dict[str, Any]:
        job_id = self._next_job_id()
        now = _now_iso()
        job = {
            "id": job_id,
            "draft_id": str(draft.get("id") or ""),
            "rule_code": str(draft.get("rule_code") or ""),
            "rule_name": str(draft.get("name") or ""),
            "scene": str(draft.get("scene") or "final"),
            "scope": str(scope or "final"),
            "status": "queued",
            "filters": filters or {},
            "record_ids": list(record_ids or []),
            "summary": None,
            "items": [],
            "failed_records": [],
            "rule_results": [],
            "error_message": "",
            "created_by": created_by,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "updated_at": now,
            "total_records": int(total_records or 0),
            "success_count": 0,
            "failed_count": 0,
            "issue_records": 0,
            "compliant_records": 0,
            "total_tokens": 0,
            "total_processing_time": 0.0,
        }
        self.jobs[job_id] = job
        return dict(job)

    def get_batch_job(self, *, job_id: str, created_by: str) -> Optional[Dict[str, Any]]:
        job = self.jobs.get(job_id)
        if not job or str(job.get("created_by")) != str(created_by):
            return None
        return dict(job)

    def get_batch_job_for_processing(self, *, job_id: str) -> Optional[Dict[str, Any]]:
        job = self.jobs.get(job_id)
        return dict(job) if job else None

    def mark_batch_job_running(self, *, job_id: str) -> None:
        if job_id not in self.jobs:
            return
        self.jobs[job_id]["status"] = "running"
        self.jobs[job_id]["started_at"] = _now_iso()
        self.jobs[job_id]["updated_at"] = _now_iso()

    def complete_batch_job(
        self,
        *,
        job_id: str,
        summary: Dict[str, Any],
        items: List[Dict[str, Any]],
        failed_records: List[Dict[str, Any]],
    ) -> None:
        if job_id not in self.jobs:
            return
        now = _now_iso()
        job = self.jobs[job_id]
        job["status"] = "completed"
        job["summary"] = dict(summary)
        job["items"] = list(items)
        job["failed_records"] = list(failed_records)
        job["rule_results"] = list(summary.get("rule_results") or [])
        job["finished_at"] = now
        job["updated_at"] = now
        job["total_records"] = int(summary.get("total_records") or 0)
        job["success_count"] = int(summary.get("success_count") or 0)
        job["failed_count"] = int(summary.get("failed_count") or 0)
        job["issue_records"] = int(summary.get("issue_records") or 0)
        job["compliant_records"] = int(summary.get("compliant_records") or 0)
        job["total_tokens"] = int(summary.get("total_tokens") or 0)
        job["total_processing_time"] = float(summary.get("total_processing_time") or 0.0)

    def fail_batch_job(self, *, job_id: str, error_message: str) -> None:
        if job_id not in self.jobs:
            return
        self.jobs[job_id]["status"] = "failed"
        self.jobs[job_id]["error_message"] = str(error_message)
        self.jobs[job_id]["updated_at"] = _now_iso()

    def list_batch_jobs(
        self,
        *,
        created_by: str,
        draft_id: Optional[str] = None,
        status: Optional[str] = None,
        scope: Optional[str] = None,
        query: Optional[str] = None,
        executor_type: Optional[str] = None,
        cache_hit: Optional[bool] = None,
        created_start_date: Optional[str] = None,
        created_end_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> _ListResult:
        items = [dict(v) for v in self.jobs.values() if str(v.get("created_by")) == str(created_by)]
        if draft_id:
            items = [x for x in items if str(x.get("draft_id")) == str(draft_id)]
        if status:
            items = [x for x in items if str(x.get("status")) == str(status)]
        if scope:
            items = [x for x in items if str(x.get("scope")) == str(scope)]
        if query:
            q = str(query)
            items = [x for x in items if q in str(x.get("rule_code")) or q in str(x.get("rule_name"))]
        if executor_type in {"program", "llm"}:
            items = [
                x
                for x in items
                if int((((x.get("summary") or {}).get("executor_breakdown") or {}).get(executor_type) or 0)) > 0
            ]
        if cache_hit is not None:
            items = [
                x
                for x in items
                if (int((((x.get("summary") or {}).get("cache_breakdown") or {}).get("hit") or 0)) > 0) == bool(cache_hit)
            ]
        items = sorted(items, key=lambda x: str(x.get("created_at") or ""), reverse=True)
        total = len(items)
        offset = max(0, int(page - 1)) * int(page_size)
        page_items = items[offset : offset + int(page_size)]
        return _ListResult(items=page_items, total=total, page=page, page_size=page_size)

    def cancel_batch_job(self, *, job_id: str, created_by: str) -> Optional[Dict[str, Any]]:
        job = self.jobs.get(job_id)
        if not job or str(job.get("created_by")) != str(created_by):
            return None
        if job.get("status") not in {"completed", "failed", "canceled"}:
            job["status"] = "canceled"
            job["error_message"] = "任务已取消"
            job["finished_at"] = _now_iso()
            job["updated_at"] = _now_iso()
        return dict(job)

    def retry_batch_job(self, *, job_id: str, created_by: str) -> Optional[Dict[str, Any]]:
        job = self.jobs.get(job_id)
        if not job or str(job.get("created_by")) != str(created_by):
            return None
        job["status"] = "queued"
        job["summary"] = None
        job["items"] = []
        job["failed_records"] = []
        job["rule_results"] = []
        job["error_message"] = ""
        job["started_at"] = None
        job["finished_at"] = None
        job["updated_at"] = _now_iso()
        return dict(job)

    def export_batch_job_csv(self, *, job: Dict[str, Any]) -> StringIO:
        out = StringIO()
        out.write("任务ID,状态\n")
        out.write(f"{job.get('id')},{job.get('status')}\n")
        return out

    def export_batch_job_workbook(self, *, job: Dict[str, Any]) -> BytesIO:
        return BytesIO(b"PK\x03\x04fake-xlsx")


@pytest.fixture
def sichuan_workspace_stub(client, monkeypatch):
    workspace = _InMemorySichuanWorkspaceService()
    user = {"id": "u-admin", "email": "admin@medqc.com", "roles": ["admin"], "role": "admin"}

    async def _noop_auth_gate():
        return None

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    client.app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _fake_run(job_id: str) -> None:
        current = workspace.get_batch_job_for_processing(job_id=job_id)
        if not current:
            return
        workspace.mark_batch_job_running(job_id=job_id)
        record_ids = list(current.get("record_ids") or ["visit-1001"])
        items = [
            {
                "rule_job_id": "rule-job-1",
                "rule_id": "SC-001",
                "rule_code": "SC-001",
                "rule_name": "测试规则",
                "record_id": rid,
                "visit_id": rid,
                "patient_name": "患者A",
                "department": "骨科",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "命中",
                "evidence": "证据片段",
                "suggestion": "请修正",
                "confidence": 0.92,
                "executor_type": "program",
                "cache_hit": False,
                "document_type": "出院记录",
                "defect_level": "严重缺陷",
            }
            for rid in record_ids
        ]
        summary = {
            "total_records": len(record_ids),
            "success_count": len(record_ids),
            "failed_count": 0,
            "failed_record_count": 0,
            "issue_records": len(record_ids),
            "compliant_records": 0,
            "total_tokens": 0,
            "total_processing_time": 0.01,
            "rule_count": 1,
            "processed_rule_count": 1,
            "executor_breakdown": {"program": len(record_ids), "llm": 0},
            "cache_breakdown": {"hit": 0, "miss": len(record_ids)},
            "result_aggregation": {"cluster_count": 1, "duplicate_hits": 0, "clusters": []},
            "rule_results": [
                {
                    "id": "rule-job-1",
                    "rule_code": "SC-001",
                    "rule_name": "测试规则",
                    "status": "completed",
                    "progress": {"rule_index": 1, "rule_count": 1, "processed_records": len(record_ids)},
                    "debug": {"executor_breakdown": {"program": len(record_ids), "llm": 0}},
                }
            ],
            "updated_at": _now_iso(),
        }
        workspace.complete_batch_job(job_id=job_id, summary=summary, items=items, failed_records=[])

    monkeypatch.setattr(qc_sichuan, "_run_sichuan_workspace_batch_job", _fake_run)

    yield workspace
    client.app.dependency_overrides.pop(get_current_user, None)
    client.app.dependency_overrides.pop(enforce_default_auth, None)


def _extract_data(resp) -> Dict[str, Any]:
    body = resp.json()
    assert body.get("success") is True
    return body.get("data") or {}


def test_sichuan_workspace_batch_create_poll_debug_export_flow(client, sichuan_workspace_stub):
    create_resp = client.post(
        "/api/v1/qc/sichuan/workspace/batch-jobs",
        json={
            "rule_ids": ["SC-001"],
            "scope": "final",
            "record_ids": ["visit-2001", "visit-2002"],
        },
    )
    assert create_resp.status_code == 200
    created = _extract_data(create_resp)
    job_id = str(created.get("id") or "")
    assert job_id
    assert created.get("execution_mode") == "batch"

    # poll/detail
    detail_resp = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}")
    assert detail_resp.status_code == 200
    detail = _extract_data(detail_resp)
    assert detail.get("status") == "completed"
    assert int((detail.get("summary") or {}).get("rule_count") or 0) == 1

    debug_resp = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}/debug")
    assert debug_resp.status_code == 200
    debug_data = _extract_data(debug_resp)
    assert debug_data.get("job_id") == job_id
    assert debug_data.get("status") == "completed"
    assert int(debug_data.get("rule_count") or 0) == 1

    export_resp = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}/export?format=csv")
    assert export_resp.status_code == 200
    assert "text/csv" in str(export_resp.headers.get("content-type") or "")
    assert "任务ID" in export_resp.text


def test_sichuan_workspace_batch_cancel_and_retry_flow(client, sichuan_workspace_stub):
    draft = {
        "id": "sichuan-rule-library",
        "rule_code": "SC-BATCH",
        "name": "四川规则库批量任务",
        "scene": "final",
    }
    created_by = "u-admin"
    queued_job = sichuan_workspace_stub.create_batch_job(
        draft=draft,
        created_by=created_by,
        scope="final",
        filters={"rule_ids": ["SC-002"]},
        record_ids=["visit-cancel-1"],
        total_records=1,
    )
    job_id = str(queued_job["id"])

    cancel_resp = client.post(f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}/cancel")
    assert cancel_resp.status_code == 200
    canceled = _extract_data(cancel_resp)
    assert canceled.get("status") == "canceled"

    retry_resp = client.post(f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}/retry")
    assert retry_resp.status_code == 200
    retried = _extract_data(retry_resp)
    assert retried.get("status") in {"queued", "running", "completed"}

    # 背景任务在 TestClient 内会执行，最终应可取到详情
    detail_resp = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}")
    assert detail_resp.status_code == 200
    detail = _extract_data(detail_resp)
    assert detail.get("status") in {"queued", "running", "completed"}
