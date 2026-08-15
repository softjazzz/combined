from types import SimpleNamespace

from app.services.luxian_0609.shadow_audit_summary import (
    merge_luxian_0609_shadow_summaries,
    project_luxian_0609_shadow_summaries,
)
from app.services.sichuan_qc_service import SichuanQCService


def _shadow_025() -> dict:
    return {
        "shadow_only": True,
        "release_eligible": False,
        "status": "non_compliant",
        "reason_code": "surgery_text_fact_defect",
        "contract_version": "lx0609-025-shadow-v1",
        "operation_count": 2,
        "status_counts": {"non_compliant": 2},
        "missing_field_counts": {"implant_material": 1},
        "llm_calls": 1,
        "prompt_tokens": 11,
        "completion_tokens": 4,
        "total_tokens": 15,
        "elapsed_ms": 21,
        "operations": [{"source_document_id": "PRIVATE-DOC"}],
    }


def _shadow_059() -> dict:
    return {
        "shadow_only": True,
        "release_eligible": False,
        "status": "data_gap",
        "reason_code": "events_source_unavailable",
        "contract_version": "lx0609-059-shadow-v1",
        "event_count": 3,
        "matched_order_count": 1,
        "missing_order_count": 0,
        "conflict_order_count": 0,
        "llm_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "elapsed_ms": 7,
        "event_refs": ["PRIVATE-EVENT"],
    }


def test_project_shadow_summaries_removes_raw_identity_and_operation_details() -> None:
    projected = project_luxian_0609_shadow_summaries(
        {
            "luxian_0609_025_shadow": _shadow_025(),
            "luxian_0609_059_shadow": _shadow_059(),
        }
    )

    assert projected["luxian_0609_025_shadow"] == {
        "shadow_only": True,
        "release_eligible": False,
        "status": "non_compliant",
        "reason_code": "surgery_text_fact_defect",
        "contract_version": "lx0609-025-shadow-v1",
        "operation_count": 2,
        "llm_calls": 1,
        "prompt_tokens": 11,
        "completion_tokens": 4,
        "total_tokens": 15,
        "elapsed_ms": 21,
        "status_counts": {"non_compliant": 2},
        "missing_field_counts": {"implant_material": 1},
    }
    assert "PRIVATE" not in repr(projected)


def test_invalid_shadow_summary_fails_closed_without_preserving_payload() -> None:
    projected = project_luxian_0609_shadow_summaries(
        {
            "luxian_0609_025_shadow": {
                **_shadow_025(),
                "reason_code": "PRIVATE-RAW-REASON",
            }
        }
    )

    assert projected["luxian_0609_025_shadow"] == {
        "shadow_only": True,
        "release_eligible": False,
        "status": "shadow_error",
        "reason_code": "result_contract_invalid",
        "contract_version": "lx0609-025-shadow-v1",
        "llm_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "elapsed_ms": 0,
        "operation_count": 0,
        "missing_field_counts": {},
    }


def test_merge_shadow_summaries_persists_only_batch_aggregate() -> None:
    aggregate: dict[str, dict] = {}
    summaries = project_luxian_0609_shadow_summaries(
        {
            "luxian_0609_025_shadow": _shadow_025(),
            "luxian_0609_059_shadow": _shadow_059(),
        }
    )

    merge_luxian_0609_shadow_summaries(aggregate, summaries)
    merge_luxian_0609_shadow_summaries(aggregate, summaries)

    assert aggregate["luxian_0609_025_shadow"] == {
        "shadow_only": True,
        "release_eligible": False,
        "contract_version": "lx0609-025-shadow-v1",
        "records_evaluated": 2,
        "status_counts": {"non_compliant": 2},
        "reason_counts": {"surgery_text_fact_defect": 2},
        "operation_count": 4,
        "llm_calls": 2,
        "prompt_tokens": 22,
        "completion_tokens": 8,
        "total_tokens": 30,
        "elapsed_ms": 42,
        "missing_field_counts": {"implant_material": 2},
    }
    assert "PRIVATE" not in repr(aggregate)


def test_document_result_keeps_shadow_summary_outside_formal_items_and_tokens() -> None:
    service = object.__new__(SichuanQCService)
    service.client = SimpleNamespace(model="unit-test")
    result = service._build_document_evaluation_result(
        document_id="PRIVATE-DOCUMENT",
        document_type="病程记录",
        rules=[],
        orchestrated={
            "results": [],
            "total_tokens": 7,
            "total_prompt_tokens": 3,
            "total_completion_tokens": 4,
            "luxian_0609_025_shadow": _shadow_025(),
        },
    )

    assert result["token_usage"] == {
        "total_tokens": 7,
        "prompt_tokens": 3,
        "completion_tokens": 4,
    }
    assert result["evaluation_results"] == []
    assert result["luxian_0609_shadow_evaluations"]["luxian_0609_025_shadow"][
        "total_tokens"
    ] == 15
    assert "PRIVATE" not in repr(result["luxian_0609_shadow_evaluations"])
