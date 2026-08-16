from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.routers import qc_sichuan


class _WorkspaceReviewStub:
    def __init__(self, job: dict[str, Any] | None) -> None:
        self.job = job
        self.updated_report: dict[str, Any] | None = None

    def get_batch_job(self, *, job_id: str, created_by: str) -> dict[str, Any] | None:
        if self.job is None or self.job.get("id") != job_id or created_by != "u-1":
            return None
        return dict(self.job)

    def update_batch_job_review_report(
        self,
        *,
        job_id: str,
        created_by: str,
        review_report: dict[str, Any],
    ) -> dict[str, Any] | None:
        if self.job is None or self.job.get("id") != job_id or created_by != "u-1":
            return None
        self.updated_report = review_report
        summary = {**dict(self.job.get("summary") or {}), "review_report": review_report}
        self.job = {**self.job, "summary": summary}
        return dict(self.job)


def test_projected_luxian_job_still_uses_safe_workspace_response() -> None:
    response = qc_sichuan._workspace_batch_response_item(
        {
            "schema_version": "customer-qc-job-v1",
            "id": "job-projected",
            "rule_set_key": "luxian_0609_qc_v1",
            "status": "completed",
            "items": [
                {
                    "schema_version": "customer-qc-result-v1",
                    "record_ref": "rec_" + "a" * 24,
                    "rule_id": "LX0609-001",
                    "status": "compliant",
                    "reason_code": "within_deadline",
                }
            ],
        }
    )

    assert response["schema_version"] == "customer-qc-job-v1"
    assert response["rule_set_key"] == "luxian_0609_qc_v1"
    assert response["items"][0]["record_ref"] == "rec_" + "a" * 24


@pytest.mark.parametrize("compact", [False, True], ids=["detail", "list"])
def test_workspace_response_rejects_historical_malformed_result_with_safe_409(
    compact: bool,
) -> None:
    private_text = "患者张三原始病历不得出现在响应中"

    with pytest.raises(HTTPException) as exc_info:
        qc_sichuan._workspace_batch_response_item(
            {
                "id": "job-malformed",
                "rule_set_key": "luxian_0609_qc_v1",
                "status": "completed",
                "items": [
                    {
                        "record_id": "private-record-id",
                        "rule_id": "LX0609-001",
                        "status": "non_compliant",
                        "customer_conclusion": private_text,
                    }
                ],
            },
            compact=compact,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "历史质控结果交付合同不完整，无法安全展示"
    assert private_text not in str(exc_info.value.detail)


def test_workspace_response_does_not_swallow_unrelated_projection_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        qc_sichuan,
        "project_customer_safe_batch_job",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("unrelated-error")),
    )

    with pytest.raises(ValueError, match="^unrelated-error$"):
        qc_sichuan._workspace_batch_response_item(
            {
                "id": "job-other-error",
                "rule_set_key": "luxian_0609_qc_v1",
            }
        )


def _request() -> Any:
    return SimpleNamespace(headers={}, state=SimpleNamespace(trace_id="test-trace-id"))


@pytest.mark.asyncio
async def test_review_luxian_workspace_batch_job_persists_report(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _WorkspaceReviewStub(
        {
            "id": "job-lx-review",
            "draft_id": "sichuan-rule-library",
            "status": "completed",
            "filters": {"rule_set_key": "luxian_0609_qc_v1"},
            "items": [
                {
                    "rule_id": "LX0609-020",
                    "rule_name": "会诊记录：有会诊记录单无请会诊执行记录",
                    "status": "uncertain",
                    "record_id": "visit-001",
                    "evidence": "未见会诊申请单或会诊记录单。",
                }
            ],
            "summary": {"rule_count": 1},
        }
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    response = await qc_sichuan.review_workspace_batch_job(
        _request(),
        "job-lx-review",
        current_user={"id": "u-1"},
    )

    assert response["success"] is True
    assert response["data"]["review_report"]["scope"] == "luxian_0609_qc_v1"
    assert response["data"]["review_report"]["summary"]["p1"] == 1
    assert workspace.updated_report is not None
    assert response["data"]["job"]["summary"]["review_report"]["findings"][0]["suggested_status"] == "not_applicable"


@pytest.mark.asyncio
async def test_review_non_luxian_workspace_batch_job_returns_422(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _WorkspaceReviewStub(
        {
            "id": "job-sc-review",
            "draft_id": "sichuan-rule-library",
            "status": "completed",
            "filters": {"rule_set_key": "sc_content_v1"},
            "items": [{"rule_id": "SC-001", "status": "non_compliant"}],
            "summary": {"rule_count": 1},
        }
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    with pytest.raises(HTTPException) as exc_info:
        await qc_sichuan.review_workspace_batch_job(
            _request(),
            "job-sc-review",
            current_user={"id": "u-1"},
        )

    assert exc_info.value.status_code == 422
    assert workspace.updated_report is None


@pytest.mark.asyncio
async def test_review_response_uses_customer_safe_projection_and_recomputes_issue_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _WorkspaceReviewStub(
        {
            "id": "job-lx-safe",
            "draft_id": "sichuan-rule-library",
            "status": "completed",
            "filters": {
                "rule_set_key": "luxian_0609_qc_v1",
                "execution_scope_hash": "a" * 64,
                "deduplicated": True,
            },
            "items": [
                {
                    "record_id": "R-101",
                    "visit_id": "V-101",
                    "patient_name": "王某某",
                    "rule_id": "LX0609-021",
                    "status": "ai_suggested_non_compliant",
                    "reason_code": "semantic_low_confidence",
                    "findings": "原始正文不得回传",
                },
                {
                    "record_id": "R-102",
                    "patient_name": "赵某某",
                    "rule_id": "LX0609-033",
                    "status": "non_compliant",
                    "reason_code": "signature_missing",
                    "customer_conclusion": "手术知情同意书签署要素不完整。",
                    "criterion_results": [
                        {
                            "criterion_id": "signature_explanation",
                            "kind": "semantic_relation",
                            "status": "failed",
                            "reason_code": "signature_missing",
                        }
                    ],
                },
                {
                    "record_id": "R-103",
                    "rule_id": "LX0609-029",
                    "result_status": "data_gap",
                    "status": "non_compliant",
                    "is_compliant": False,
                    "reason_code": "source_unavailable",
                },
                {
                    "record_id": "R-104",
                    "rule_id": "LX0609-032",
                    "status": "technical_error",
                    "is_compliant": False,
                    "reason_code": "source_query_error",
                },
            ],
            "summary": {
                "rule_count": 4,
                "issue_records": 4,
                "performance_profile": {
                    "tokens_total": 321,
                    "prompt_tokens": 250,
                    "completion_tokens": 71,
                    "unattributed_tokens": 0,
                    "llm_call_count": 2,
                    "retry_count": 1,
                    "latency_p95_ms": 88.5,
                    "raw_debug": {"patient_name": "指标泄漏"},
                },
            },
        }
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    response = await qc_sichuan.review_workspace_batch_job(
        _request(),
        "job-lx-safe",
        current_user={"id": "u-1"},
    )

    safe_job = response["data"]["job"]
    assert safe_job["id"] == "job-lx-safe"
    assert safe_job["job_id"] == "job-lx-safe"
    assert safe_job["execution_scope_hash"] == "a" * 64
    assert safe_job["deduplicated"] is True
    assert "filters" not in safe_job
    assert safe_job["total_tokens"] == 321
    assert safe_job["prompt_tokens"] == 250
    assert safe_job["completion_tokens"] == 71
    assert safe_job["llm_call_count"] == 2
    assert safe_job["retry_count"] == 1
    assert safe_job["summary"]["performance_profile"]["latency_p95_ms"] == 88.5
    assert "raw_debug" not in safe_job["summary"]["performance_profile"]
    assert safe_job["summary"]["issue_records"] == 1
    assert [item["status"] for item in safe_job["items"]] == [
        "ai_suggested_non_compliant",
        "non_compliant",
        "data_gap",
        "technical_error",
    ]
    assert safe_job["items"][0]["is_confirmed_issue"] is False
    dumped = str(response)
    assert "R-101" not in dumped
    assert "V-101" not in dumped
    assert "王某某" not in dumped
    assert "指标泄漏" not in dumped
    assert "原始正文不得回传" not in dumped
