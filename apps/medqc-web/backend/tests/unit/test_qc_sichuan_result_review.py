from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.routers import qc_sichuan
from app.services.luxian_0609_result_schema import CUSTOMER_SCHEMA_VERSION


class _WorkspaceReviewStub:
    def __init__(
        self,
        job: dict[str, Any] | None,
        *,
        canonical_items: list[dict[str, Any]] | None = None,
    ) -> None:
        self.job = job
        self.canonical_items = canonical_items
        self.canonical_load_count = 0
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

    def _load_batch_job_canonical_items(
        self,
        *,
        job: dict[str, Any],
        allow_partial: bool = False,
    ) -> list[dict[str, Any]]:
        assert self.job is not None and job["id"] == self.job["id"]
        self.canonical_load_count += 1
        if self.canonical_items is None:
            raise ValueError("canonical envelope missing")
        return [dict(item) for item in self.canonical_items]


class _CanonicalReadStub:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items

    def _load_batch_job_canonical_items(
        self,
        *,
        job: dict[str, Any],
        allow_partial: bool = False,
    ):
        assert job["id"] == "job-canonical"
        return list(self.items)


def _canonical_item(
    *,
    rule_id: str,
    status: str,
    reason_code: str,
    record_ref_suffix: str = "a",
    **extra: Any,
) -> dict[str, Any]:
    return {
        "schema_version": CUSTOMER_SCHEMA_VERSION,
        "record_ref": "rec_" + record_ref_suffix * 24,
        "rule_id": rule_id,
        "rule_version": "2026-06-09",
        "status": status,
        "result_status": status,
        "display_status": status,
        "is_compliant": (
            True
            if status in {"compliant", "not_applicable"}
            else False
            if status == "non_compliant"
            else None
        ),
        "reason_code": reason_code,
        **extra,
    }


def test_luxian_0609_batch_detail_hydrates_validated_canonical_items_before_summary_projection() -> None:
    canonical_item = {
        "schema_version": "lx0609-customer-result-v2",
        "record_ref": "rec_" + "a" * 24,
        "rule_id": "LX0609-001",
        "rule_version": "2026-06-09",
        "status": "compliant",
        "result_status": "compliant",
        "display_status": "compliant",
        "is_compliant": True,
        "reason_code": "requirement_satisfied",
    }
    raw_job = {
        "id": "job-canonical",
        "status": "completed",
        "items": [{"rule_id": "LX0609-001", "status": "technical_error"}],
    }

    hydrated = qc_sichuan._hydrate_luxian_canonical_batch_job_or_409(
        workspace=_CanonicalReadStub([canonical_item]),
        job=raw_job,
    )
    projected = qc_sichuan._workspace_batch_response_item({
        **hydrated,
        "rule_set_key": "luxian_0609_qc_v1",
    })

    assert projected["summary"]["status_counts"] == {"compliant": 1}
    assert projected["summary"]["result_count"] == 1


def test_luxian_0609_batch_detail_ignores_stale_internal_rule_results_after_canonical_hydration() -> None:
    canonical_item = _canonical_item(
        rule_id="LX0609-001",
        status="compliant",
        reason_code="requirement_satisfied",
    )
    raw_job = {
        "id": "job-canonical",
        "status": "completed",
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_results": [{"rule_id": "INTERNAL-001", "items": []}],
        "summary": {
            "total_records": 1,
            "rule_results": [{"rule_id": "INTERNAL-002", "items": []}],
        },
    }

    hydrated = qc_sichuan._hydrate_luxian_canonical_batch_job_or_409(
        workspace=_CanonicalReadStub([canonical_item]),
        job=raw_job,
    )
    projected = qc_sichuan._workspace_batch_response_item(hydrated)

    assert projected["status"] == "completed"
    assert projected["summary"]["status_counts"] == {"compliant": 1}
    assert projected["summary"]["result_count"] == 1
    assert projected["items"][0]["rule_id"] == "LX0609-001"


def test_luxian_0609_partial_failed_detail_uses_available_canonical_records() -> None:
    canonical_item = _canonical_item(
        rule_id="LX0609-001",
        status="non_compliant",
        reason_code="requirement_not_satisfied",
    )
    raw_job = {
        "id": "job-canonical",
        "status": "failed",
        "rule_set_key": "luxian_0609_qc_v1",
        "items": [{"rule_id": "LX0609-001", "status": "technical_error"}],
        "rule_results": [{"rule_id": "LX0609-001", "items": []}],
        "summary": {
            "execution_status": "partial_failed",
            "rule_results": [{"rule_id": "LX0609-001", "items": []}],
        },
    }

    hydrated = qc_sichuan._hydrate_luxian_canonical_batch_job_or_409(
        workspace=_CanonicalReadStub([canonical_item]),
        job=raw_job,
    )

    assert hydrated["items"] == [canonical_item]
    assert hydrated["rule_results"] == []
    assert "rule_results" not in hydrated["summary"]

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
def test_workspace_response_omits_historical_malformed_result_without_leaking_private_text(
    compact: bool,
) -> None:
    private_text = "患者张三原始病历不得出现在响应中"

    response = qc_sichuan._workspace_batch_response_item(
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

    if compact:
        assert response["items"] == []
    else:
        assert [item["status"] for item in response["items"]] == [
            "technical_error"
        ]
    assert private_text not in str(response)


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


@pytest.mark.parametrize("compact", [False, True], ids=["detail", "list"])
def test_workspace_response_filters_excluded_rule_and_rejects_unknown_rule(
    compact: bool,
) -> None:
    base_job = {
        "id": "job-lx-rule-isolation",
        "rule_set_key": "luxian_0609_qc_v1",
        "status": "completed",
        "summary": {"total_records": 1},
        "items": [
            {
                "record_id": "record-1",
                "rule_id": "LX0609-001",
                "status": "compliant",
                "is_compliant": True,
                "reason_code": "within_deadline",
            },
            {
                "record_id": "record-1",
                "rule_id": "LX0609-033",
                "status": "compliant",
                "is_compliant": True,
                "reason_code": "within_deadline",
            },
        ],
    }

    response = qc_sichuan._workspace_batch_response_item(base_job, compact=compact)
    assert [item["rule_id"] for item in response["items"]] == (
        [] if compact else ["LX0609-001"]
    )
    assert response["summary"]["result_count"] == 1

    malformed_job = {
        **base_job,
        "items": [
            *base_job["items"],
            {
                "record_id": "record-1",
                "rule_id": "LX0609-999",
                "status": "compliant",
                "is_compliant": True,
            },
        ],
    }
    with pytest.raises(HTTPException) as exc_info:
        qc_sichuan._workspace_batch_response_item(malformed_job, compact=compact)
    assert exc_info.value.status_code == 409


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
            "items": [_canonical_item(
                rule_id="LX0609-020",
                status="compliant",
                reason_code="requirement_satisfied",
            )],
            "summary": {"rule_count": 1},
        },
        canonical_items=[
            _canonical_item(
                rule_id="LX0609-020",
                status="uncertain",
                reason_code="semantic_low_confidence",
            )
        ],
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
    assert workspace.canonical_load_count == 2
    assert response["data"]["job"]["summary"]["review_report"]["findings"][0]["suggested_status"] == "not_applicable"


@pytest.mark.asyncio
async def test_review_luxian_workspace_batch_job_rejects_missing_canonical_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _WorkspaceReviewStub(
        {
            "id": "job-lx-missing-envelope",
            "draft_id": "sichuan-rule-library",
            "status": "completed",
            "filters": {"rule_set_key": "luxian_0609_qc_v1"},
            "items": [
                {
                    "rule_id": "LX0609-020",
                    "status": "uncertain",
                    "reason_code": "semantic_low_confidence",
                }
            ],
        }
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    with pytest.raises(HTTPException) as exc_info:
        await qc_sichuan.review_workspace_batch_job(
            _request(),
            "job-lx-missing-envelope",
            current_user={"id": "u-1"},
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "批量质控 Canonical 结果不完整，无法安全展示"
    assert workspace.updated_report is None


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
        },
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
        },
        canonical_items=[
            _canonical_item(
                rule_id="LX0609-021",
                status="ai_suggested_non_compliant",
                reason_code="semantic_low_confidence",
                record_ref_suffix="a",
            ),
            _canonical_item(
                rule_id="LX0609-029",
                status="data_gap",
                reason_code="source_unavailable",
                record_ref_suffix="b",
            ),
            _canonical_item(
                rule_id="LX0609-032",
                status="technical_error",
                reason_code="source_query_error",
                record_ref_suffix="c",
            ),
        ],
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
    assert safe_job["summary"]["issue_records"] == 0
    assert [item["status"] for item in safe_job["items"]] == [
        "ai_suggested_non_compliant",
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


def test_debug_snapshot_preserves_structured_evidence_fields_and_aliases_missing_side() -> None:
    evidence = {
        "source_ref": "src_0123456789abcdef01234567",
        "source_document_id": "doc-1",
        "record_time": "2026-08-31 10:20:00",
        "evidence_excerpt": "术前讨论已完成",
    }
    snapshot = qc_sichuan._build_debug_snapshot(
        {
            "id": "job-1",
            "status": "completed",
            "items": [{"rule_job_id": "rule-1", "status": "non_compliant", "evidence_items": [evidence]}],
        }
    )

    item = snapshot["recent_items"][0]
    assert item["evidence_items"][0] == evidence
    assert item["customer_evidence"][0] == evidence


def test_debug_snapshot_collects_parent_child_items_without_changing_status() -> None:
    evidence = {
        "source_ref": "src_abcdefabcdefabcdefabcdef",
        "source_document_id": "doc-2",
        "record_time": "2026-08-30",
        "evidence_excerpt": "病程记录摘录",
    }
    snapshot = qc_sichuan._build_debug_snapshot(
        {
            "id": "parent-1",
            "status": "completed",
            "job_kind": "parent",
            "items": [],
            "children": [
                {
                    "id": "child-1",
                    "items": [{"rule_job_id": "rule-2", "status": "data_gap", "customer_evidence": [evidence]}],
                }
            ],
        }
    )

    item = snapshot["recent_items"][0]
    assert item["status"] == "data_gap"
    assert item["evidence_items"][0]["source_ref"] == evidence["source_ref"]
    assert item["customer_evidence"][0]["evidence_excerpt"] == evidence["evidence_excerpt"]


def test_debug_snapshot_does_not_repeat_heavy_summary_payloads() -> None:
    snapshot = qc_sichuan._build_debug_snapshot(
        {
            "id": "job-heavy-summary",
            "status": "completed",
            "summary": {
                "rule_set_key": "luxian_0609_qc_v1",
                "total_records": 20,
                "wall_clock_time": 79.5,
                "progress": {"processed_records": 20},
                "rule_results": [{"items": [{"raw": "x" * 1000}]}],
                "performance_profile": {"records": [{"raw": "y" * 1000}]},
                "last_retry_performance_profile": {"records": [{"raw": "z" * 1000}]},
            },
            "items": [],
        }
    )

    assert snapshot["summary"] == {
        "rule_set_key": "luxian_0609_qc_v1",
        "progress": {"processed_records": 20},
        "total_records": 20,
        "wall_clock_time": 79.5,
    }
    assert "rule_results" not in snapshot["summary"]
    assert "performance_profile" not in snapshot["summary"]
    assert "last_retry_performance_profile" not in snapshot["summary"]


def test_debug_snapshot_preserves_luxian_0916_semantic_failure_coordinates() -> None:
    failures = [
        {
            "institute_id": "I-1",
            "patient_id": "P-1",
            "visit_id": "V-1",
            "record_id": "R-1",
            "code": "semantic_extraction_invalid",
            "document_count": 3,
            "llm_call_count": 1,
        }
    ]
    snapshot = qc_sichuan._build_debug_snapshot(
        {
            "id": "job-0916",
            "status": "completed",
            "summary": {
                "semantic_llm_call_count": 30,
                "semantic_extraction_invalid_count": 1,
                "semantic_extraction_failures": failures,
            },
            "items": [],
        }
    )

    assert snapshot["summary"] == {
        "semantic_llm_call_count": 30,
        "semantic_extraction_invalid_count": 1,
        "semantic_extraction_failures": failures,
    }
