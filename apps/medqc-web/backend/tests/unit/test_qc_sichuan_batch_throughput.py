from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from app.routers import qc_sichuan


class _WorkspaceStub:
    def __init__(self) -> None:
        self.job: Dict[str, Any] = {
            "id": "job-throughput-001",
            "status": "queued",
            "scope": "final",
            "filters": {
                "rule_ids": ["SC-001", "SC-002", "SC-003"],
                "date_field": "discharge",
            },
            "record_ids": ["visit-001", "visit-002"],
        }
        self.summary: Optional[Dict[str, Any]] = None
        self.items: List[Dict[str, Any]] = []
        self.failed_records: List[Dict[str, Any]] = []

    def get_batch_job_for_processing(self, *, job_id: str) -> Optional[Dict[str, Any]]:
        if job_id != self.job["id"]:
            return None
        return dict(self.job)

    def mark_batch_job_running(self, *, job_id: str) -> None:
        if job_id == self.job["id"]:
            self.job["status"] = "running"

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
        ids = list(record_ids or [])
        return [
            {
                "record_id": rid,
                "visit_id": rid,
                "patient_name": f"患者{idx + 1}",
                "department": "骨科",
                "scope": scope,
            }
            for idx, rid in enumerate(ids)
        ]

    def hydrate_records_with_medical_text(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{**item, "medical_text": f"病历文本-{item.get('record_id')}"} for item in records]

    def complete_batch_job(
        self,
        *,
        job_id: str,
        summary: Dict[str, Any],
        items: List[Dict[str, Any]],
        failed_records: List[Dict[str, Any]],
    ) -> None:
        self.job["status"] = "completed"
        self.summary = dict(summary)
        self.items = list(items)
        self.failed_records = list(failed_records)

    def fail_batch_job(self, *, job_id: str, error_message: str) -> None:
        self.job["status"] = "failed"
        self.job["error_message"] = error_message


class _ServiceStub:
    def __init__(self) -> None:
        self.evaluate_calls = 0

    def assert_sc_rule_source_ready(self, *, context: str, block_batch: bool = False) -> Dict[str, Any]:
        return {"sc_source": "pg_governance"}

    def get_rule_by_id(self, rule_id: str) -> Dict[str, Any]:
        return {
            "rule_id": rule_id,
            "rule_code": rule_id,
            "name": f"规则-{rule_id}",
            "defect_level": "一般缺陷",
        }

    async def evaluate_document(
        self,
        document_id: str,
        content: str,
        document_type: str = "病程记录",
        rule_ids: Optional[List[str]] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        self.evaluate_calls += 1
        evals: List[Dict[str, Any]] = []
        for rid in list(rule_ids or []):
            evals.append(
                {
                    "rule_id": rid,
                    "rule_name": f"规则-{rid}",
                    "status": "compliant",
                    "is_compliant": True,
                    "findings": "",
                    "evidence": "",
                    "suggestion": "",
                    "confidence": 0.9,
                    "metadata": {
                        "executor_type": "program",
                        "tokens_used": 0,
                        "api_time": 0.001,
                        "cache_hit": False,
                        "rule_version": "v1",
                        "prompt_version": "default-v1",
                        "model_version": "test-model",
                        "evidence_source": "medical_text",
                        "trace_id": "trace-1",
                        "cache_key": "",
                        "execution_domain": "general",
                        "doc_scope": "primary",
                        "cost_class": "low",
                        "llm_fallback": False,
                    },
                }
            )
        return {"evaluation_results": evals}


@pytest.mark.asyncio
async def test_workspace_batch_should_call_evaluate_once_per_record(monkeypatch):
    workspace = _WorkspaceStub()
    service = _ServiceStub()

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _fake_get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert service.evaluate_calls == 2
    assert workspace.job["status"] == "completed"
    assert workspace.summary is not None
    assert int(workspace.summary.get("total_records") or 0) == 2
    assert int(workspace.summary.get("rule_count") or 0) == 3
    assert int(workspace.summary.get("processed_rule_count") or 0) == 3
