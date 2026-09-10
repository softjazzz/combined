"""LX0609-069 会诊业务时间缺口的受控事实与客户展示。"""

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_canonical_result,
)
from app.services.luxian_0609.continuity_result_mapping import (
    safe_continuity_customer_display_facts,
)
from app.services.luxian_0609.customer_renderer import (
    render_luxian_0609_customer_result,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.decision_reducer import (
    reduce_luxian_0609_rule_decision,
)
from app.services.luxian_0609.extended_document.consultation_timeliness import (
    evaluate_consultation_timeliness,
)


def _gap_decision():
    return reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-069",
            snapshot_hash="a" * 64,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="authoritative_time_missing",
            fact_refs=("b" * 64,),
            evaluator_version="native-extended-document-v1",
        )
    )


def test_empty_request_time_branch_reports_request_business_time_only() -> None:
    row = {"document_id": "DOC", "consult_apply_time": None}

    outcome = evaluate_consultation_timeliness(
        consultation_rows=(row,), consultation_error=""
    )

    assert outcome.final_state == "data_gap"
    assert outcome.reason_code == "authoritative_time_missing"
    assert outcome.display_facts == {
        "failure_kind": "consultation_business_time_missing",
        "missing_time_roles": ["request"],
    }
    assert outcome.consumed_document_rows == (row,)


@pytest.mark.parametrize(
    ("rows", "expected_roles"),
    (
        (
            ({"document_id": "DOC", "request_time": "invalid", "completion_time": "2026-08-20 10:00:00"},),
            ["request"],
        ),
        (
            ({"document_id": "DOC", "request_time": "2026-08-20 08:00:00", "completion_time": None},),
            ["completion"],
        ),
        (
            (
                {"document_id": "ONE", "request_time": "invalid", "completion_time": "2026-08-20 10:00:00"},
                {"document_id": "TWO", "request_time": "2026-08-20 08:00:00", "completion_time": None},
            ),
            ["request", "completion"],
        ),
    ),
)
def test_event_time_gap_reports_actual_missing_roles(rows, expected_roles) -> None:
    outcome = evaluate_consultation_timeliness(
        consultation_rows=rows, consultation_error=""
    )

    assert outcome.final_state == "data_gap"
    assert outcome.reason_code == "authoritative_time_missing"
    assert outcome.display_facts == {
        "failure_kind": "consultation_business_time_missing",
        "missing_time_roles": expected_roles,
    }


def test_consultation_business_time_gap_mapping_accepts_exact_shape() -> None:
    raw = {
        "failure_kind": "consultation_business_time_missing",
        "missing_time_roles": ["request", "completion"],
    }

    assert safe_continuity_customer_display_facts(
        rule_id="LX0609-069", raw=raw
    ) == raw


@pytest.mark.parametrize(
    "raw",
    (
        {"failure_kind": "consultation_business_time_missing", "missing_time_roles": []},
        {"failure_kind": "consultation_business_time_missing", "missing_time_roles": "request"},
        {"failure_kind": "consultation_business_time_missing", "missing_time_roles": ["request", "request"]},
        {"failure_kind": "consultation_business_time_missing", "missing_time_roles": ["submit"]},
        {"failure_kind": "consultation_business_time_missing", "missing_time_roles": [{}]},
        {"failure_kind": "consultation_business_time_missing", "missing_time_roles": [[]]},
        {"failure_kind": "consultation_business_time_missing", "missing_time_roles": ["request"], "extra": 1},
    ),
)
def test_consultation_business_time_gap_mapping_rejects_invalid_shapes(raw) -> None:
    assert safe_continuity_customer_display_facts(
        rule_id="LX0609-069", raw=raw
    ) is None


@pytest.mark.parametrize(
    ("roles", "expected_fields"),
    (
        (["request"], ["会诊申请业务时间"]),
        (["completion"], ["会诊完成业务时间"]),
        (["request", "completion"], ["会诊申请业务时间", "会诊完成业务时间"]),
    ),
)
def test_renderer_and_finalizer_name_exact_missing_business_times(
    roles, expected_fields
) -> None:
    facts = {
        "failure_kind": "consultation_business_time_missing",
        "missing_time_roles": roles,
    }
    rendered = render_luxian_0609_customer_result(
        decision=_gap_decision(), safe_customer_display_facts=facts
    )

    joined = "、".join(expected_fields)
    assert joined in rendered["findings"]
    assert joined in rendered["evidence"]
    assert joined in rendered["suggestion"]
    assert "提交时间" not in str(rendered)

    finalized = finalize_luxian_0609_canonical_result(
        {**rendered, "customer_display_facts": facts}
    )
    assert finalized["status"] == "data_gap"
    assert finalized["reason_code"] == "authoritative_time_missing"
    assert finalized["missing_sources"] == []
    assert finalized["missing_fields"] == expected_fields
    assert finalized["data_gap_details"]["reason_label"] == "会诊业务时间缺失"
    assert joined in finalized["customer_message"]
