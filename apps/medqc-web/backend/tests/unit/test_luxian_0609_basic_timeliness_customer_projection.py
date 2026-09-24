from __future__ import annotations

from copy import deepcopy

import pytest

from app.services.luxian_0609.basic_timeliness_customer_projection import (
    BASIC_TIMELINESS_CUSTOMER_RULE_IDS,
    basic_timeliness_customer_fact_status_is_valid,
    safe_basic_timeliness_customer_display_facts,
    validate_published_rescue_content_facts,
)
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
    finalizer_owns_executor_customer_display_facts,
    finalizer_requires_public_fact_ref_evidence,
    validate_luxian_0609_published_customer_display_facts,
)
import app.services.luxian_0609.canonical_result_finalizer as finalizer_module
import app.services.luxian_0609.basic_timeliness_customer_projection as projection_module
from app.services.luxian_0609.decision_model import (
    ApplicabilityState, EvidenceState, QcDirection, RuleDecision,
)
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from app.services.qc_workspace.canonical_result_store import (
    safe_customer_display_facts,
    validated_customer_explanation,
)
from app.services.custom_qc_workspace_service import project_customer_safe_result_item
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results


_WITHIN_FACTS_BY_RULE = {
    "LX0609-01-01-01": {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "admission_record",
        "timeliness_state": "within",
        "threshold_hours": 24,
        "source_label": "入院记录",
    },
    "LX0609-01-02-01": {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "first_course_record",
        "timeliness_state": "within",
        "threshold_hours": 8,
        "source_label": "首次病程记录",
    },
    "LX0609-09-01-01": {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "rescue_record",
        "timeliness_state": "within",
        "threshold_hours": 6,
        "source_label": "抢救记录",
    },
    "LX0609-09-01-02": {
        "target_document": "rescue_record",
        "source_label": "抢救记录",
        "content_state": "compliant",
        "required_fields": [
            "condition_change",
            "rescue_time",
            "rescue_measures",
            "rescue_outcome",
            "participant_names",
            "participant_titles",
        ],
        "missing_fields": [],
        "unknown_fields": [],
        "rescue_content_events": [
            {
                "event_index": 1,
                "document_ref": "a" * 64,
                "source_document_id": "RESCUE-1",
                "record_time": "2026-09-01T10:00:00+08:00",
                "body_scope": "complete",
                "field_facts": {
                    field: {
                        "state": "present",
                        "start": 0,
                        "end": 1,
                        "quote": "抢",
                    }
                    for field in (
                        "condition_change",
                        "rescue_time",
                        "rescue_measures",
                        "rescue_outcome",
                        "participant_names",
                        "participant_titles",
                    )
                },
                "missing_fields": [],
                "unknown_fields": [],
            }
        ],
        "failure_kind": "",
    },
    "LX0609-02-01-01": {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "attending_course_record",
        "timeliness_state": "within",
        "threshold_hours": 48,
        "source_label": "主治医师首次查房记录",
    },
    "LX0609-02-01-02": {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "senior_course_record",
        "timeliness_state": "within",
        "threshold_hours": 72,
        "source_label": "最高级别医师首次查房记录",
    },
}


def _executor_result(rule_id: str, status: str) -> dict[str, str]:
    return {
        "rule_id": rule_id,
        "status": status,
        "reason_code": "executor_reason",
        "findings": "执行器结论",
        "customer_evidence": [{"source_type": "forbidden-on-contract-failure"}],
    }


@pytest.mark.parametrize("rule_id", sorted(BASIC_TIMELINESS_CUSTOMER_RULE_IDS))
def test_basic_family_published_read_baseline(rule_id: str):
    safe = safe_basic_timeliness_customer_display_facts(
        rule_id=rule_id, raw=deepcopy(_WITHIN_FACTS_BY_RULE[rule_id]),
    )
    assert safe is not None
    assert validate_luxian_0609_published_customer_display_facts(
        rule_id=f" {rule_id.lower()} ", raw=safe,
    ) == safe
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=rule_id, raw={**safe, "unexpected_field": "invalid"},
        )
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw=None)


def test_unknown_rule_is_not_claimed_by_basic_family():
    assert validate_luxian_0609_published_customer_display_facts(
        rule_id="LX0609-99-99-99", raw=None,
    ) is None
    assert validate_luxian_0609_published_customer_display_facts(
        rule_id="LX0609-99-99-99", raw={},
    ) is NotImplemented


@pytest.mark.parametrize("rule_id", sorted(BASIC_TIMELINESS_CUSTOMER_RULE_IDS))
def test_all_basic_timeliness_rules_have_safe_compliant_fact_shape(rule_id: str):
    raw_facts = _WITHIN_FACTS_BY_RULE[rule_id]

    safe_facts = safe_basic_timeliness_customer_display_facts(
        rule_id=rule_id,
        raw=raw_facts,
    )

    if rule_id == "LX0609-09-01-02":
        assert safe_facts is not None
        assert safe_facts["content_state"] == "compliant"
        assert safe_facts["missing_fields"] == []
        assert safe_facts["unknown_fields"] == []
        assert safe_facts["rescue_content_events"][0]["field_facts"] == {
            field: {"state": "present"}
            for field in raw_facts["required_fields"]
        }
        serialized = repr(safe_facts)
        assert "document_ref" not in serialized
        assert "source_document_id" not in serialized
        assert "quote" not in serialized
        assert "start" not in serialized
        assert "end" not in serialized
    else:
        assert safe_facts == raw_facts
    assert basic_timeliness_customer_fact_status_is_valid(
        rule_id=rule_id,
        status="compliant",
        safe_facts=safe_facts,
    )


def test_rescue_missing_participant_title_survives_safe_fact_save_and_read():
    rule_id = "LX0609-09-01-02"
    raw = deepcopy(_WITHIN_FACTS_BY_RULE[rule_id])
    raw["content_state"] = "non_compliant"
    raw["missing_fields"] = ["participant_titles"]
    raw["rescue_content_events"][0]["missing_fields"] = ["participant_titles"]
    raw["rescue_content_events"][0]["field_facts"]["participant_titles"] = {
        "state": "absent", "start": None, "end": None, "quote": "",
    }

    safe = safe_basic_timeliness_customer_display_facts(rule_id=rule_id, raw=raw)
    assert safe is not None
    assert safe_basic_timeliness_customer_display_facts(rule_id=rule_id, raw=safe) is None
    item = {"customer_display_facts": safe}
    assert safe_customer_display_facts(item, rule_id=rule_id) == safe
    assert validated_customer_explanation(
        item, rule_id=rule_id, status="non_compliant"
    ) == (safe, [])
    projected = project_customer_safe_result_item(
        {"rule_id": rule_id, "status": "non_compliant", "result_status": "non_compliant",
         "display_status": "non_compliant", "is_compliant": False,
         "customer_display_facts": safe},
        hmac_key="unit-test-key",
    )
    assert projected["customer_display_facts"] == safe
    assert "document_ref" not in repr(safe)
    assert "source_document_id" not in repr(safe)
    assert "quote" not in repr(safe)

    for extra in (
        {"source_document_id": "RESCUE-1"},
        {"document_ref": "a" * 64},
    ):
        forged = deepcopy(safe)
        forged["rescue_content_events"][0].update(extra)
        assert safe_basic_timeliness_customer_display_facts(rule_id=rule_id, raw=forged) is None
    forged = deepcopy(safe)
    forged["rescue_content_events"][0]["field_facts"]["participant_titles"]["quote"] = "伪造原文"
    assert safe_basic_timeliness_customer_display_facts(rule_id=rule_id, raw=forged) is None


def test_rescue_published_facts_reject_internal_shape_and_unknown_fields():
    rule_id = "LX0609-09-01-02"
    raw = deepcopy(_WITHIN_FACTS_BY_RULE[rule_id])
    safe = safe_basic_timeliness_customer_display_facts(rule_id=rule_id, raw=raw)
    assert safe is not None
    assert safe_customer_display_facts({"customer_display_facts": safe}, rule_id=rule_id) == safe
    missing_required = deepcopy(safe)
    missing_required.pop("content_state")
    for invalid in (raw, {**safe, "unexpected": "private"}, missing_required):
        with pytest.raises(ValueError):
            safe_customer_display_facts({"customer_display_facts": invalid}, rule_id=rule_id)
        with pytest.raises(ValueError):
            project_customer_safe_result_item(
                {"rule_id": rule_id, "status": "compliant", "customer_display_facts": invalid},
                hmac_key="unit-test-key",
            )


@pytest.mark.parametrize(
    ("path", "invalid"),
    [
        (("content_state",), []),
        (("failure_kind",), {}),
        (("missing_fields",), [{}]),
        (("unknown_fields",), [[]]),
        (("rescue_content_events", 0, "body_scope"), {}),
        (("rescue_content_events", 0, "missing_fields"), [{}]),
        (("rescue_content_events", 0, "unknown_fields"), [[]]),
        (("rescue_content_events", 0, "field_facts", "participant_titles", "state"), []),
    ],
)
def test_rescue_published_facts_reject_json_field_type_errors(path, invalid):
    raw = deepcopy(_WITHIN_FACTS_BY_RULE["LX0609-09-01-02"])
    safe = safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-09-01-02", raw=raw,
    )
    assert safe is not None and safe["rescue_content_events"]
    target = safe
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = invalid
    assert validate_published_rescue_content_facts(safe) is None
    with pytest.raises(ValueError):
        safe_customer_display_facts(
            {"customer_display_facts": safe}, rule_id="LX0609-09-01-02",
        )


def test_rescue_reduced_publication_does_not_reproject_published_facts(monkeypatch):
    raw = deepcopy(_WITHIN_FACTS_BY_RULE["LX0609-09-01-02"])
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id="LX0609-09-01-02", snapshot_hash="a" * 64,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.SATISFIED,
        reason_code="requirement_satisfied", fact_refs=("b" * 64,),
        evaluator_version="test-v1", confidence=1.0,
    ))

    original = finalizer_module.validate_luxian_0609_executor_customer_display_facts
    calls = []
    def tracked_internal_projection(**kwargs):
        calls.append(kwargs["raw"])
        return original(**kwargs)
    monkeypatch.setattr(
        finalizer_module, "validate_luxian_0609_executor_customer_display_facts",
        tracked_internal_projection,
    )
    result = finalizer_module.finalize_luxian_0609_reduced_customer_result(
        decision=decision, raw_customer_display_facts=raw,
        evidence_snapshot=None, evidence_materials=None,
    )
    assert result["status"] == "compliant"
    assert result["customer_display_facts"] == (
        safe_basic_timeliness_customer_display_facts(
            rule_id="LX0609-09-01-02", raw=raw,
        )
    )
    assert calls == [raw]


@pytest.mark.parametrize("rule_id", sorted(BASIC_TIMELINESS_CUSTOMER_RULE_IDS))
def test_all_basic_timeliness_rules_are_finalizer_facts_and_public_evidence_owners(
    rule_id: str,
):
    assert finalizer_owns_executor_customer_display_facts(rule_id)
    assert finalizer_requires_public_fact_ref_evidence(rule_id)


def test_lx004_data_gap_fact_shape_is_accepted_without_reinterpreting_rescue_logic():
    raw_facts = {
        "failure_kind": "rescue_record_missing_after_trigger",
        "target_document": "rescue_record",
        "source_label": "抢救记录",
    }

    safe_facts = safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-09-01-01",
        raw=raw_facts,
    )

    assert safe_facts == raw_facts
    assert basic_timeliness_customer_fact_status_is_valid(
        rule_id="LX0609-09-01-01",
        status="data_gap",
        safe_facts=safe_facts,
    )


def test_lx004_published_late_facts_are_read_without_recalculation():
    raw = {
        "failure_kind": "timeliness_requirement_not_met",
        "target_document": "rescue_record",
        "source_label": "抢救记录",
        "timeliness_state": "late",
        "threshold_hours": 6,
        "elapsed_hours": 7,
    }
    published = safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-09-01-01", raw=raw,
    )
    assert published is not None
    assert validate_luxian_0609_published_customer_display_facts(
        rule_id="LX0609-09-01-01", raw=published,
    ) == published

    corrupted = {**published, "overdue_hours": 999}
    with pytest.raises(ValueError, match="解释合同不完整"):
        safe_customer_display_facts(
            {"customer_display_facts": corrupted},
            rule_id="LX0609-09-01-01",
        )


def test_lx001_published_facts_are_read_without_recalculation():
    raw = {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "admission_record", "source_label": "入院记录",
        "timeliness_state": "within", "threshold_hours": 24,
        "elapsed_hours": 1.0,
    }
    published = safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-01-01-01", raw=raw,
    )
    assert published is not None
    assert validate_luxian_0609_published_customer_display_facts(
        rule_id="LX0609-01-01-01", raw=published,
    ) == published

    corrupted = {**published, "remaining_hours": 999.0}
    with pytest.raises(ValueError, match="解释合同不完整"):
        safe_customer_display_facts(
            {"customer_display_facts": corrupted}, rule_id="LX0609-01-01-01",
        )


@pytest.mark.parametrize(
    "raw",
    [
        {
            "failure_kind": "timeliness_requirement_not_met",
            "target_document": "admission_record", "source_label": "入院记录",
            "timeliness_state": "missing", "threshold_hours": 24,
            "document_content_state": "blank_or_placeholder",
        },
        {
            "failure_kind": "timeliness_requirement_not_met",
            "target_document": "admission_record", "source_label": "入院记录",
            "timeliness_state": "late", "threshold_hours": 24,
            "anchor_time": "2026-06-01 09:00:00",
            "observed_time": "2026-06-02 10:00:00", "elapsed_hours": 25.0,
        },
        {
            "failure_kind": "timeliness_requirement_satisfied",
            "target_document": "admission_record", "source_label": "入院记录",
            "timeliness_state": "within", "threshold_hours": 24,
            "anchor_date": "2026-06-01", "observed_time": "2026-06-01 10:00:00",
        },
        {
            "failure_kind": "evidence_time_conflict",
            "target_document": "admission_record", "source_label": "入院记录",
            "timeliness_state": "before", "threshold_hours": 24,
            "anchor_time": "2026-06-01 09:00:00",
            "observed_time": "2026-06-01 08:00:00",
            "time_conflict_seconds": 3600,
        },
    ],
    ids=["blank", "late", "date_anchor", "conflict"],
)
def test_lx001_published_fact_branches_keep_exact_projected_values(raw):
    published = safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-01-01-01", raw=raw,
    )
    assert published is not None
    assert validate_luxian_0609_published_customer_display_facts(
        rule_id="LX0609-01-01-01", raw=published,
    ) == published


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("threshold_hours", True), ("elapsed_hours", True),
        ("elapsed_hours", float("nan")), ("elapsed_hours", -1),
        ("remaining_hours", float("inf")), ("remaining_hours", -1),
        ("remaining_hours", []), ("source_label", {}),
        ("anchor_time", []), ("failure_kind", []),
        ("timeliness_state", {}),
    ],
)
def test_lx001_invalid_published_field_types_fail_closed(field, invalid):
    published = safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-01-01-01",
        raw={
            "failure_kind": "timeliness_requirement_satisfied",
            "target_document": "admission_record", "source_label": "入院记录",
            "timeliness_state": "within", "threshold_hours": 24,
            "elapsed_hours": 1.0, "anchor_time": "2026-06-01 09:00:00",
        },
    )
    assert published is not None
    forged = {**published, field: invalid}
    with pytest.raises(ValueError, match="解释合同不完整"):
        safe_customer_display_facts(
            {"customer_display_facts": forged}, rule_id="LX0609-01-01-01",
        )

    with pytest.raises(ValueError, match="解释合同不完整"):
        safe_customer_display_facts(
            {"customer_display_facts": {**published, 1: "unexpected"}},
            rule_id="LX0609-01-01-01",
        )


def test_lx001_published_rounding_accepts_previous_two_step_projection():
    # 内部投影从未舍入间隔计算剩余时间，再分别保留两位小数。
    raw = {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "admission_record", "source_label": "入院记录",
        "timeliness_state": "within", "threshold_hours": 24,
        "elapsed_hours": 1.004, "anchor_time": "2026-06-01 09:00:00",
        "observed_time": "2026-06-01 10:00:14",
    }
    published = safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-01-01-01", raw=raw,
    )
    assert published is not None
    assert published["elapsed_hours"] == 1.0
    assert published["remaining_hours"] == 23.0
    assert validate_luxian_0609_published_customer_display_facts(
        rule_id="LX0609-01-01-01", raw=published,
    ) == published


@pytest.mark.parametrize(
    ("rule_id", "target", "threshold", "elapsed", "expected_elapsed", "derived_key", "expected_derived"),
    [
        ("LX0609-01-01-01", "admission_record", 24, 0.055, 0.06, "remaining_hours", 23.94),
        ("LX0609-01-02-01", "first_course_record", 8, 0.005, 0.01, "remaining_hours", 7.99),
        ("LX0609-02-01-01", "attending_course_record", 48, 5.995, 6.0, "remaining_hours", 42.0),
        ("LX0609-02-01-02", "senior_course_record", 72, 72.005, 72.0, None, None),
    ],
)
def test_original_timeliness_finalizer_keeps_existing_final_numbers_without_reprojection(
    monkeypatch, rule_id, target, threshold, elapsed, expected_elapsed, derived_key, expected_derived,
):
    """原生执行器只投影一次；最终交付数值与旧双投影结果保持一致。"""

    late = elapsed > threshold
    raw = {
        "failure_kind": "timeliness_requirement_not_met" if late else "timeliness_requirement_satisfied",
        "target_document": target,
        "source_label": "测试记录",
        "timeliness_state": "late" if late else "within",
        "threshold_hours": threshold,
        "elapsed_hours": elapsed,
    }
    published = projection_module.safe_basic_timeliness_customer_display_facts(
        rule_id=rule_id, raw=raw, formal_publication=True,
    )
    assert published is not None

    def forbidden_projection(*args, **kwargs):
        raise AssertionError("已发布事实不得在 Finalizer 再次投影")

    monkeypatch.setattr(
        projection_module, "safe_basic_timeliness_customer_display_facts",
        forbidden_projection,
    )
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id=rule_id, snapshot_hash="a" * 64,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.DEFECT if late else QcDirection.SATISFIED,
        reason_code="threshold_exceeded" if late else "requirement_satisfied",
        fact_refs=("b" * 64,), evaluator_version="test-v1", confidence=1.0,
    ))
    result = finalizer_module.finalize_luxian_0609_reduced_customer_result(
        decision=decision, raw_customer_display_facts=published,
        evidence_snapshot=None, evidence_materials=None,
    )
    facts = result["customer_display_facts"]
    assert result["status"] == ("non_compliant" if late else "compliant")
    assert facts["elapsed_hours"] == expected_elapsed
    if derived_key is None:
        assert "overdue_hours" not in facts
    else:
        assert facts[derived_key] == expected_derived


@pytest.mark.parametrize(
    ("rule_id", "target", "threshold"),
    [
        ("LX0609-01-01-01", "admission_record", 24),
        ("LX0609-01-02-01", "first_course_record", 8),
        ("LX0609-02-01-01", "attending_course_record", 48),
        ("LX0609-02-01-02", "senior_course_record", 72),
    ],
)
def test_original_timeliness_single_formal_projection_matches_previous_delivery(
    rule_id, target, threshold,
):
    """固定临界输入，对照旧执行器加 Finalizer 的两次投影交付值。"""

    for elapsed in (0.005, 0.055, 5.995, 6.001, 6.005, 6.995,
                    threshold - 0.005, threshold, threshold + 0.005):
        late = elapsed > threshold
        raw = {
            "failure_kind": "timeliness_requirement_not_met" if late else "timeliness_requirement_satisfied",
            "target_document": target,
            "source_label": "测试记录",
            "timeliness_state": "late" if late else "within",
            "threshold_hours": threshold,
            "elapsed_hours": elapsed,
        }
        legacy_first = safe_basic_timeliness_customer_display_facts(
            rule_id=rule_id, raw=raw,
        )
        assert legacy_first is not None
        legacy_final = safe_basic_timeliness_customer_display_facts(
            rule_id=rule_id, raw=legacy_first,
        )
        formal = safe_basic_timeliness_customer_display_facts(
            rule_id=rule_id, raw=raw, formal_publication=True,
        )
        assert formal == legacy_final


def test_original_timeliness_legacy_entry_still_rejects_private_fact_identifier():
    with pytest.raises(ValueError, match="invalid customer display facts"):
        aggregate_luxian_0609_results(
            wrapper_rules=[{"rule_id": "LX0609-01-01-01", "name": "入院记录时限"}],
            execution_results=[{
                "rule_id": "LX0609-01-01-01", "status": "non_compliant",
                "metadata": {
                    "execution_source": "lx0609_native",
                    "customer_display_facts": {
                        "failure_kind": "timeliness_requirement_not_met",
                        "target_document": "admission_record",
                        "source_label": "入院记录",
                        "timeliness_state": "late", "threshold_hours": 24,
                        "elapsed_hours": 25,
                        "source_document_id": "private-document-id",
                    },
                },
            }],
        )


@pytest.mark.parametrize(
    "raw",
    [
        {
            "failure_kind": "timeliness_requirement_satisfied",
            "target_document": "rescue_record",
            "source_label": "抢救记录",
            "timeliness_state": "within",
            "threshold_hours": 6,
            "elapsed_hours": 5,
        },
        {
            "failure_kind": "timeliness_requirement_not_met",
            "target_document": "rescue_record",
            "source_label": "抢救记录",
            "timeliness_state": "late",
            "threshold_hours": 6,
            "elapsed_hours": 7,
            "rescue_events": [
                {
                    "event_index": 1,
                    "event_state": "within",
                    "rescue_end_time": "2026-09-01T00:00:00+08:00",
                    "document_completion_time": "2026-09-01T05:00:00+08:00",
                    "elapsed_hours": 5,
                },
                {
                    "event_index": 2,
                    "event_state": "late",
                    "rescue_end_time": "2026-09-02T00:00:00+08:00",
                    "document_completion_time": "2026-09-02T07:00:00+08:00",
                    "elapsed_hours": 7,
                },
            ],
        },
        {
            "failure_kind": "timeliness_requirement_not_met",
            "target_document": "rescue_record",
            "source_label": "抢救记录",
            "timeliness_state": "missing",
            "threshold_hours": 6,
        },
        {
            "failure_kind": "rescue_end_time_missing",
            "target_document": "rescue_record",
            "source_label": "抢救记录",
            "timeliness_state": "missing_time",
            "threshold_hours": 6,
            "observed_time": "2026-09-01T05:00:00+08:00",
        },
        {
            "failure_kind": "document_completion_time_missing",
            "target_document": "rescue_record",
            "source_label": "抢救记录",
            "timeliness_state": "missing_time",
            "threshold_hours": 6,
            "anchor_time": "2026-09-01T00:00:00+08:00",
        },
        {
            "failure_kind": "authoritative_time_conflict",
            "target_document": "rescue_record",
            "source_label": "抢救记录",
            "timeliness_state": "conflict",
            "threshold_hours": 6,
            "anchor_time": "2026-09-01T07:00:00+08:00",
            "observed_time": "2026-09-01T05:00:00+08:00",
        },
        {
            "failure_kind": "rescue_record_missing_after_trigger",
            "target_document": "rescue_record",
            "source_label": "抢救记录",
        },
    ],
)
def test_lx004_published_fact_branches_are_read_without_internal_projection(
    raw: dict[str, object], monkeypatch: pytest.MonkeyPatch,
):
    published = projection_module.safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-09-01-01", raw=raw,
    )
    assert published is not None

    def forbidden_projection(*args: object, **kwargs: object) -> None:
        raise AssertionError("读取公开事实时不应调用内部发布投影")

    monkeypatch.setattr(
        projection_module, "safe_basic_timeliness_customer_display_facts",
        forbidden_projection,
    )
    monkeypatch.setattr(
        finalizer_module, "validate_luxian_0609_executor_customer_display_facts",
        forbidden_projection,
    )
    assert safe_customer_display_facts(
        {"customer_display_facts": published}, rule_id="LX0609-09-01-01",
    ) == published


@pytest.mark.parametrize(
    "changed",
    [
        {"remaining_hours": 999},
        {"elapsed_hours": 5, "remaining_hours": 0},
        {"trigger_source": "inpat_nondrug_order.rescue_order"},
        {"source_document_id": "private-id"},
    ],
)
def test_lx004_published_facts_reject_added_or_inconsistent_fields(
    changed: dict[str, object],
):
    published = deepcopy(_WITHIN_FACTS_BY_RULE["LX0609-09-01-01"])
    published.update(changed)
    with pytest.raises(ValueError, match="解释合同不完整"):
        safe_customer_display_facts(
            {"customer_display_facts": published}, rule_id="LX0609-09-01-01",
        )


def test_lx004_published_multi_event_rejects_private_id_and_changed_elapsed():
    raw = {
        "failure_kind": "timeliness_requirement_not_met",
        "target_document": "rescue_record",
        "source_label": "抢救记录",
        "timeliness_state": "late",
        "threshold_hours": 6,
        "elapsed_hours": 7,
        "rescue_events": [
            {
                "event_index": index,
                "event_state": "late",
                "rescue_end_time": f"2026-09-0{index}T00:00:00+08:00",
                "document_completion_time": f"2026-09-0{index}T07:00:00+08:00",
                "elapsed_hours": 7,
            }
            for index in (1, 2)
        ],
    }
    published = projection_module.safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-09-01-01", raw=raw,
    )
    assert published is not None
    for changed_key, changed_value in (
        ("source_document_id", "private-id"),
        ("elapsed_hours", 999),
    ):
        corrupted = deepcopy(published)
        corrupted["rescue_events"][0][changed_key] = changed_value
        with pytest.raises(ValueError, match="解释合同不完整"):
            safe_customer_display_facts(
                {"customer_display_facts": corrupted}, rule_id="LX0609-09-01-01",
            )


@pytest.mark.parametrize("elapsed", [0.005, 0.055, 5.995, 6.001, 6.005, 6.995, 7.005])
@pytest.mark.parametrize(
    ("kind", "state"),
    [
        ("timeliness_requirement_satisfied", "within"),
        ("timeliness_requirement_not_met", "late"),
    ],
)
def test_lx004_published_rounding_keeps_existing_two_step_values(
    elapsed: float, kind: str, state: str,
):
    published = projection_module.safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-09-01-01",
        raw={
            "failure_kind": kind,
            "target_document": "rescue_record",
            "source_label": "抢救记录",
            "timeliness_state": state,
            "threshold_hours": 6,
            "elapsed_hours": elapsed,
        },
    )
    assert published is not None
    assert safe_customer_display_facts(
        {"customer_display_facts": published}, rule_id="LX0609-09-01-01",
    ) == published


@pytest.mark.parametrize(
    "changed",
    [
        {"failure_kind": []},
        {"timeliness_state": []},
        {"threshold_hours": True},
        {"elapsed_hours": 10 ** 400},
        {"rescue_events": [{"event_index": 1, "event_state": []}]},
    ],
)
def test_lx004_malformed_published_facts_fail_closed_without_type_error(
    changed: dict[str, object],
):
    published = deepcopy(_WITHIN_FACTS_BY_RULE["LX0609-09-01-01"])
    published.update(changed)
    with pytest.raises(ValueError, match="解释合同不完整"):
        safe_customer_display_facts(
            {"customer_display_facts": published}, rule_id="LX0609-09-01-01",
        )


@pytest.mark.parametrize("invalid_overdue", [-0.01, 0.005])
def test_lx004_rounding_tolerance_does_not_accept_invalid_published_precision(
    invalid_overdue: float,
):
    published = projection_module.safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-09-01-01",
        raw={
            "failure_kind": "timeliness_requirement_not_met",
            "target_document": "rescue_record",
            "source_label": "抢救记录",
            "timeliness_state": "late",
            "threshold_hours": 6,
            "elapsed_hours": 6.001,
        },
    )
    assert published is not None and published["overdue_hours"] == 0.0
    changed = {**published, "overdue_hours": invalid_overdue}
    with pytest.raises(ValueError, match="解释合同不完整"):
        safe_customer_display_facts(
            {"customer_display_facts": changed}, rule_id="LX0609-09-01-01",
        )


def test_lx001_uncertain_conflict_fact_shape_is_accepted():
    raw_facts = {
        "failure_kind": "evidence_time_conflict",
        "target_document": "admission_record",
        "source_label": "入院记录",
        "timeliness_state": "before",
        "threshold_hours": 24,
        "anchor_time": "2026-06-01T09:00:00",
        "observed_time": "2026-06-01T08:00:00",
        "time_conflict_seconds": 3600,
    }

    safe_facts = safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-01-01-01",
        raw=raw_facts,
    )

    assert basic_timeliness_customer_fact_status_is_valid(
        rule_id="LX0609-01-01-01",
        status="uncertain",
        safe_facts=safe_facts,
    )


@pytest.mark.parametrize(
    ("status", "raw_facts"),
    [
        ("compliant", None),
        ("non_compliant", _WITHIN_FACTS_BY_RULE["LX0609-01-01-01"]),
        (
            "compliant",
            {
                **_WITHIN_FACTS_BY_RULE["LX0609-01-01-01"],
                "source_document_refs": ["forged-internal-ref"],
            },
        ),
    ],
    ids=["missing_facts", "contradictory_status", "private_fact_ref"],
)
def test_basic_timeliness_contract_failure_safely_downgrades_to_technical_error(
    status: str,
    raw_facts: object,
):
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result=_executor_result("LX0609-01-01-01", status),
        raw_facts=raw_facts,
    )

    assert handled is True
    assert finalized["status"] == "technical_error"
    assert finalized["result_status"] == "technical_error"
    assert finalized["reason_code"] == "model_invalid_output"
    assert finalized["is_compliant"] is None
    assert "customer_display_facts" not in finalized
    assert "customer_evidence" not in finalized
    assert "findings" not in finalized
