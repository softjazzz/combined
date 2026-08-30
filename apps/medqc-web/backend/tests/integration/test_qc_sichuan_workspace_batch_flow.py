from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO, StringIO
from typing import Any, Dict, List, Optional

import pytest

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
from app.routers import qc_sichuan
from app.services.sichuan_qc_service import RuleSourceGuardError
from app.services.sichuan_workspace_batch_worker import _sanitize_trace_value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class _ListResult:
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


def test_customer_display_facts_keep_96_recommendation_evidence_entries():
    facts = {
        "recommendation_evidence": [{"recommendation_index": index} for index in range(1, 97)],
        "other_list": list(range(60)),
    }

    sanitized = _sanitize_trace_value(
        facts,
        set(),
        max_text=120,
        list_limits={"recommendation_evidence": 96},
    )

    assert len(sanitized["recommendation_evidence"]) == 96
    assert len(sanitized["other_list"]) == 50


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
        record_refs: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        refs = list(record_refs or [])
        if not refs:
            refs = [
                {
                    "institute_id": "inst-1",
                    "patient_id": f"patient-{idx + 1}",
                    "visit_id": str(record_id),
                }
                for idx, record_id in enumerate(record_ids or ["visit-1001", "visit-1002"])
            ]
        return [
            {
                **(ref.as_dict() if hasattr(ref, "as_dict") else ref),
                "record_id": str(ref.visit_id if hasattr(ref, "visit_id") else ref["visit_id"]),
                "patient_name": f"患者-{idx + 1}",
                "department": department or "骨科",
                "doctor": doctor or "王医生",
                "scope": scope,
            }
            for idx, ref in enumerate(refs)
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
        record_refs: Optional[List[Dict[str, str]]] = None,
        draft_ids: Optional[List[str]] = None,
        execution_mode: str = "single",
        run_mode: str = "serial",
        rule_count: int = 1,
        job_kind: str = "leaf",
        parent_job_id: Optional[str] = None,
        child_job_ids: Optional[List[str]] = None,
        child_summary: Optional[Dict[str, Any]] = None,
        family_key: Optional[str] = None,
        family_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        job_id = self._next_job_id()
        now = _now_iso()
        job = {
            "id": job_id,
            "draft_id": str(draft.get("id") or ""),
            "draft_ids": list(draft_ids or [str(draft.get("id") or "")]),
            "rule_code": str(draft.get("rule_code") or ""),
            "rule_name": str(draft.get("name") or ""),
            "scene": str(draft.get("scene") or "final"),
            "scope": str(scope or "final"),
            "status": "queued",
            "filters": {
                **(filters or {}),
                **(
                    {
                        "record_refs": [
                            ref.as_dict() if hasattr(ref, "as_dict") else dict(ref)
                            for ref in record_refs
                        ]
                    }
                    if record_refs
                    else {}
                ),
            },
            "record_ids": list(record_ids or []),
            "record_refs": [
                ref.as_dict() if hasattr(ref, "as_dict") else dict(ref)
                for ref in list(record_refs or [])
            ],
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
            "execution_mode": execution_mode,
            "run_mode": run_mode,
            "rule_count": int(rule_count or 0),
            "job_kind": job_kind,
            "parent_job_id": parent_job_id,
            "child_job_ids": list(child_job_ids or []),
            "child_summary": child_summary or {},
            "family_key": family_key,
            "family_name": family_name,
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

    def get_latest_luxian_0609_record_result(
        self,
        *,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        expected_rule_ids=None,
        rule_set_key: str = "luxian_0609_qc_v1",
        rule_set_version: str = "2026-06-09",
    ) -> Dict[str, Any]:
        candidates = [
            job
            for job in self.jobs.values()
            if str(job.get("status")) == "completed"
            and str(visit_id) in {str(value) for value in list(job.get("record_ids") or [])}
            and str((job.get("filters") or {}).get("rule_set_key") or "") == rule_set_key
            and str((job.get("filters") or {}).get("rule_set_version") or "") == rule_set_version
        ]
        if not candidates:
            return {
                "schema_version": "lx0609-single-record-result-v1",
                "state": "not_found",
                "reason_code": "record_result_not_found",
            "record_ref": "",
                "job_id": "",
                "items": [],
                "expected_rule_count": 49,
                "result_rule_count": 0,
                "is_complete": False,
            }
        current = sorted(candidates, key=lambda item: str(item.get("finished_at") or item.get("created_at") or ""), reverse=True)[0]
        items = [
            item
            for item in list(current.get("items") or [])
            if str(item.get("record_id") or item.get("visit_id") or "") == str(visit_id)
        ]
        return {
            "schema_version": "lx0609-single-record-result-v1",
            "state": "ready",
            "reason_code": "",
            "record_ref": f"rec_{visit_id}",
            "job_id": str(current.get("id") or ""),
            "rule_set_key": rule_set_key,
            "rule_set_version": rule_set_version,
            "items": items,
            "expected_rule_count": 49,
            "result_rule_count": len(items),
            "is_complete": len(items) == 49,
            "missing_rule_ids": [],
            "conflicting_rule_ids": [],
        }

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

    def export_batch_job_html(self, *, job: Dict[str, Any]) -> str:
        return f"<!doctype html><html><body><h1>质控明细</h1><p>{job.get('id')}</p></body></html>"

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

    def _fake_complete(job_id: str) -> None:
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

    async def _fake_run(job_id: str) -> None:
        _fake_complete(job_id)

    monkeypatch.setattr(qc_sichuan, "_run_sichuan_workspace_batch_job", _fake_run)

    def _run_detached_immediately(_task_name: str, task_func, *args, **kwargs):
        if args:
            _fake_complete(str(args[0]))

    monkeypatch.setattr(qc_sichuan, "submit_detached_task", _run_detached_immediately)

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

    html_export_resp = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}/export?format=html")
    assert html_export_resp.status_code == 200
    assert "text/html" in str(html_export_resp.headers.get("content-type") or "")
    assert "sichuan_rules_" in str(html_export_resp.headers.get("content-disposition") or "")
    assert "质控明细" in html_export_resp.text


def test_workspace_batch_create_persists_full_case_coordinates_for_same_visit(
    client,
    sichuan_workspace_stub,
):
    response = client.post(
        "/api/v1/qc/sichuan/workspace/batch-jobs",
        json={
            "rule_ids": ["SC-001"],
            "scope": "final",
            "record_refs": [
                {"institute_id": "H1", "patient_id": "P1", "visit_id": "V-SAME"},
                {"institute_id": "H2", "patient_id": "P2", "visit_id": "V-SAME"},
            ],
        },
    )

    assert response.status_code == 200
    created = _extract_data(response)
    assert created["record_refs"] == [
        {"institute_id": "H1", "patient_id": "P1", "visit_id": "V-SAME"},
        {"institute_id": "H2", "patient_id": "P2", "visit_id": "V-SAME"},
    ]
    assert created["filters"]["record_refs"] == created["record_refs"]


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


def test_latest_luxian_record_result_is_read_by_server_bound_record(client, sichuan_workspace_stub):
    job = sichuan_workspace_stub.create_batch_job(
        draft={"id": "luxian-0609", "rule_code": "LX0609", "name": "泸县0609", "scene": "final"},
        created_by="u-admin",
        scope="final",
        filters={"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"},
        record_ids=["visit-lx-1", "visit-lx-2"],
        total_records=2,
        job_kind="parent",
    )
    sichuan_workspace_stub.complete_batch_job(
        job_id=str(job["id"]),
        summary={"total_records": 2},
        items=[
            {"record_id": "visit-lx-1", "rule_id": "LX0609-018", "status": "non_compliant"},
            {"record_id": "visit-lx-2", "rule_id": "LX0609-018", "status": "compliant"},
        ],
        failed_records=[],
    )
    newer_job = sichuan_workspace_stub.create_batch_job(
        draft={"id": "luxian-0609", "rule_code": "LX0609", "name": "泸县0609", "scene": "final"},
        created_by="u-audit",
        scope="final",
        filters={"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"},
        record_ids=["visit-lx-1"],
        total_records=1,
        job_kind="parent",
    )
    sichuan_workspace_stub.complete_batch_job(
        job_id=str(newer_job["id"]),
        summary={"total_records": 1},
        items=[
            {"record_id": "visit-lx-1", "rule_id": "LX0609-018", "status": "compliant"},
        ],
        failed_records=[],
    )
    sichuan_workspace_stub.jobs[str(newer_job["id"])]["finished_at"] = "2099-08-09T00:00:00+00:00"

    response = client.get(
        "/api/v1/qc/sichuan/workspace/records/visit-lx-1/latest-result",
        params={"institute_id": "inst-1", "patient_id": "patient-1"},
    )

    assert response.status_code == 200
    data = _extract_data(response)
    assert data.get("state") == "ready"
    assert data.get("job_id") == newer_job["id"]
    assert data.get("record_ref") == "rec_visit-lx-1"
    assert [item.get("record_id") for item in data.get("items") or []] == ["visit-lx-1"]

    missing_coordinates = client.get("/api/v1/qc/sichuan/workspace/records/visit-lx-1/latest-result")
    assert missing_coordinates.status_code == 422

    missing_response = client.get(
        "/api/v1/qc/sichuan/workspace/records/visit-not-saved/latest-result",
        params={"institute_id": "inst-1", "patient_id": "patient-1"},
    )
    assert missing_response.status_code == 404


def test_workspace_batch_create_should_block_when_sc_source_not_pg(client, sichuan_workspace_stub):
    class _GuardFailService:
        def assert_sc_rule_source_ready(self, *, context: str, block_batch: bool = False):
            raise RuleSourceGuardError("SC 规则来源异常，当前请求已被阻断。")

    client.app.dependency_overrides[qc_sichuan.get_qc_service] = lambda: _GuardFailService()
    try:
        resp = client.post(
            "/api/v1/qc/sichuan/workspace/batch-jobs",
            json={
                "rule_ids": ["SC-001"],
                "scope": "final",
                "record_ids": ["visit-3001"],
            },
        )
        assert resp.status_code == 503
        body = resp.json()
        assert "阻断" in str(body.get("error") or body.get("detail") or "")
    finally:
        client.app.dependency_overrides.pop(qc_sichuan.get_qc_service, None)
