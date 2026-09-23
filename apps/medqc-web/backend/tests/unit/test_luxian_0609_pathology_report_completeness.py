"""2026版病理报告单：业务键完整性和CDM证据边界的独立回归。"""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from app.services.custom_qc_workspace_service import project_customer_safe_result_item
from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from app.services.luxian_0609.decision_model import (
    ApplicabilityState, EvidenceState, QcDirection, RuleDecision,
)
import app.services.luxian_0609.canonical_result_finalizer as finalizer_module
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import resolve_legacy_executor_material_source_keys
from app.services.luxian_0609.pathology_report_completeness import (
    PATHOLOGY_COMPLETENESS_SOURCES,
    PATHOLOGY_REPORT_COMPLETENESS_RULE_ID as RULE_ID,
    evaluate_pathology_report_completeness,
)
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceQueryError, SourceEvidenceUnavailable
from app.services.luxian_0609.tumor_pathology_result_mapping import (
    safe_tumor_pathology_customer_display_facts,
    tumor_pathology_customer_fact_status_is_valid,
)
from app.services.qc_workspace.canonical_result_store import (
    safe_customer_display_facts,
    validated_customer_explanation,
)


OLD_RULES = ("LX0609-06-02-03", "LX0609-06-02-02", "LX0609-05-02-01", "LX0609-08-01-04")
MASTER, REPORT = PATHOLOGY_COMPLETENESS_SOURCES


def _master(key="E1", **values):
    return {"pathology_exam_id": key, "request_datetime": "2026-09-01 09:00:00", **values}


def _report(key="E1", **values):
    return {"pathology_exam_id": key, "report_datetime": "2026-09-02 10:00:00", **values}


def _evaluate(master=(), report=(), *, source_states=None, completeness=None):
    return evaluate_pathology_report_completeness(
        master_rows=master,
        report_rows=report,
        source_states=source_states or {MASTER: "present" if master else "empty", REPORT: "present" if report else "empty"},
        source_completeness=completeness or {MASTER: "complete", REPORT: "complete"},
        document_refs=lambda source, rows: ("a" * 64 if source == MASTER else "b" * 64,) if rows else (),
    )


@pytest.mark.parametrize(
    ("master", "report", "expected", "reason"),
    [
        ([], [], "not_applicable", "pathology_performed_event_absent"),
        ([_master()], [_report(diagnosis="")], "compliant", "pathology_reports_complete"),
        ([_master()], [], "data_gap", "pathology_report_completeness_unproven"),
        ([_master(record_content="已完成病理检查。")], [], "data_gap", "target_report_missing"),
    ],
)
def test_current_cdm_evidence_does_not_invent_a_clinical_defect(master, report, expected, reason):
    outcome = _evaluate(master, report)
    assert (outcome.status, outcome.reason_code) == (expected, reason)
    assert outcome.status != "non_compliant"
    safe = safe_tumor_pathology_customer_display_facts(rule_id=RULE_ID, raw=outcome.display_facts)
    assert safe is not None
    assert tumor_pathology_customer_fact_status_is_valid(rule_id=RULE_ID, status=expected, safe_facts=safe)


@pytest.mark.parametrize("text", ["拟行病理检查。", "计划进行病理检查。", "病理检查已取消。", "已取消病理检查。", "病理检查未执行。"])
def test_planned_or_cancelled_events_do_not_require_reports(text):
    outcome = _evaluate([_master(record_content=text)])
    assert outcome.status == "not_applicable"
    assert outcome.display_facts["excluded_event_count"] == 1


@pytest.mark.parametrize("text", ["病理申请已完成。", "已经取材送病理。", "若已完成病理检查，请核对报告。", "既往已完成病理检查。", "未完成病理检查。"])
def test_request_sampling_or_hypothetical_text_does_not_prove_execution(text):
    outcome = _evaluate([_master(record_content=text)])
    assert outcome.status == "data_gap"
    assert not outcome.display_facts["events"][0]["execution_confirmed"]


@pytest.mark.parametrize("source", PATHOLOGY_COMPLETENESS_SOURCES)
@pytest.mark.parametrize("state", ["unavailable", "error", "truncated"])
def test_failed_or_truncated_source_is_not_an_empty_complete_scope(source, state):
    outcome = _evaluate(source_states={MASTER: "empty", REPORT: "empty", source: state})
    assert outcome.status == "data_gap"


def test_readable_rows_do_not_prove_completeness():
    outcome = _evaluate([_master()], [_report()], completeness={MASTER: "unproven", REPORT: "complete"})
    assert outcome.status == "data_gap"
    assert outcome.display_facts["report_count"] == 1


def test_duplicate_reports_are_counted_by_business_event_and_keep_valid_version():
    master = [_master(), _master()]
    reports = [_report(report_status="待报告"), _report(), _report()]
    for rows in (reports, list(reversed(reports))):
        outcome = _evaluate(master, rows)
        assert outcome.status == "compliant"
        assert outcome.display_facts["event_count"] == 1
        assert outcome.display_facts["report_count"] == 1


def test_report_can_link_by_pathology_id_without_pathology_exam_id():
    outcome = _evaluate([{"pathology_id": "P1"}], [{"pathology_id": "P1", "diagnosis": "未见恶性细胞。"}])
    assert outcome.status == "compliant"
    assert outcome.display_facts["event_count"] == 1


def test_values_from_different_business_key_namespaces_do_not_join():
    outcome = _evaluate([_master("same")], [{"pathology_id": "same", "report_datetime": "2026-09-02"}])
    assert outcome.status == "data_gap"
    assert outcome.display_facts["event_count"] == 2


def test_crossed_business_keys_are_an_ambiguous_event():
    outcome = _evaluate(
        [_master("E1", pathology_id="P1"), _master("E2", pathology_id="P2")],
        [_report("E1", pathology_id="P2")],
    )
    assert outcome.status == "data_gap"
    assert outcome.display_facts["event_count"] == 1
    assert outcome.display_facts["events"][0]["reason_code"] == "pathology_business_key_ambiguous"


def test_unkeyed_report_prevents_a_false_assertion_that_a_known_report_is_missing():
    outcome = _evaluate([_master(record_content="已完成病理检查。")], [{"diagnosis": "良性组织。"}])
    assert outcome.status == "data_gap"
    assert outcome.display_facts["missing_report_count"] == 0
    assert {item["reason_code"] for item in outcome.display_facts["events"]} == {
        "pathology_report_linkage_unresolved", "pathology_business_key_missing",
    }


def test_unkeyed_master_stays_a_separate_gap_even_with_an_orphan_report():
    outcome = _evaluate([{"request_datetime": "2026-09-01"}], [_report()])
    assert outcome.status == "data_gap"
    assert outcome.display_facts["event_count"] == 2


def test_execution_and_cancellation_conflict_is_not_a_defect_or_compliance():
    outcome = _evaluate([_master(record_content="病理检查已取消。")], [_report()])
    assert outcome.status == "data_gap"
    assert outcome.display_facts["events"][0]["reason_code"] == "pathology_execution_conflict"


def test_empty_diagnosis_is_not_a_report_existence_requirement():
    assert _evaluate([_master()], [_report(diagnosis="")]).status == "compliant"
    assert _evaluate([_master()], [_report(report_datetime="", diagnosis="未见恶性细胞")]).status == "compliant"


@pytest.mark.parametrize("values", [
    {"report_status": "待报告"},
    {"report_status": "作废"},
    {"report_datetime": "invalid", "diagnosis": "待报告"},
    {"report_datetime": "2026-13-40", "diagnosis": "--"},
    {"report_datetime": "", "diagnosis": "", "eye_findings": ""},
])
def test_placeholder_or_cancelled_report_does_not_prove_report_existence(values):
    outcome = _evaluate([_master()], [_report(**values)])
    assert outcome.status == "data_gap"
    assert outcome.display_facts["report_count"] == 0


def test_multiple_events_preserve_individual_results_and_missing_report_fact():
    outcome = _evaluate(
        [_master("E1"), _master("E2", record_content="已完成病理检查。"), _master("E3"), _master("E4", record_content="拟行病理检查。")],
        [_report("E1"), _report("E1")],
    )
    assert (outcome.status, outcome.reason_code) == ("data_gap", "target_report_missing")
    facts = outcome.display_facts
    assert (facts["event_count"], facts["report_count"], facts["missing_report_count"], facts["unresolved_event_count"], facts["excluded_event_count"]) == (4, 1, 1, 2, 1)
    assert set(outcome.fact_refs) == {"a" * 64, "b" * 64}


def test_safe_projection_strips_raw_ids_and_rejects_malformed_counts_and_refs():
    raw = dict(_evaluate([_master()], [_report()]).display_facts)
    raw["patient_id"] = "must-not-leak"
    raw["events"][0]["pathology_id"] = "must-not-leak"
    safe = safe_tumor_pathology_customer_display_facts(rule_id=RULE_ID, raw=raw)
    assert safe is not None and "must-not-leak" not in repr(safe)
    assert "fact_refs" not in repr(safe)
    assert not tumor_pathology_customer_fact_status_is_valid(rule_id=RULE_ID, status="non_compliant", safe_facts=safe)
    for mutate in (lambda data: data.update(report_count=2), lambda data: data["events"][0].update(fact_refs=["raw-id"])):
        malformed = deepcopy(raw)
        mutate(malformed)
        assert safe_tumor_pathology_customer_display_facts(rule_id=RULE_ID, raw=malformed) is None


@pytest.mark.parametrize(
    ("masters", "reports", "expected_status"),
    [
        ([_master()], [_report()], "compliant"),
        ([_master(record_content="已完成病理检查。")], [], "data_gap"),
    ],
)
def test_pathology_nonempty_events_survive_safe_fact_save_and_read(
    masters, reports, expected_status
):
    outcome = _evaluate(masters, reports)
    assert outcome.status == expected_status
    safe = safe_tumor_pathology_customer_display_facts(
        rule_id=RULE_ID, raw=outcome.display_facts
    )
    assert safe is not None and safe["events"]
    assert safe_tumor_pathology_customer_display_facts(rule_id=RULE_ID, raw=safe) is None
    item = {"customer_display_facts": safe}
    assert safe_customer_display_facts(item, rule_id=RULE_ID) == safe
    assert validated_customer_explanation(
        item, rule_id=RULE_ID, status=expected_status
    ) == (safe, [])
    projected = project_customer_safe_result_item(
        {"rule_id": RULE_ID, "status": expected_status,
         "result_status": expected_status, "display_status": expected_status,
         "is_compliant": expected_status == "compliant",
         "customer_display_facts": safe},
        hmac_key="unit-test-key",
    )
    assert projected["customer_display_facts"] == safe
    assert "fact_refs" not in repr(safe)

    for extra in ({"fact_refs": ["invalid-ref"]}, {"patient_id": "private"}):
        forged = deepcopy(safe)
        forged["events"][0].update(extra)
        assert safe_tumor_pathology_customer_display_facts(
            rule_id=RULE_ID, raw=forged
        ) is None


def test_pathology_published_facts_reject_internal_shape_and_unknown_fields():
    raw = deepcopy(_evaluate([_master()], [_report()]).display_facts)
    safe = safe_tumor_pathology_customer_display_facts(rule_id=RULE_ID, raw=raw)
    assert safe is not None
    missing_required = deepcopy(safe)
    missing_required.pop("event_count")
    for invalid in (raw, {**safe, "unexpected": "private"}, missing_required):
        with pytest.raises(ValueError):
            safe_customer_display_facts({"customer_display_facts": invalid}, rule_id=RULE_ID)
        with pytest.raises(ValueError):
            project_customer_safe_result_item(
                {"rule_id": RULE_ID, "status": "compliant", "customer_display_facts": invalid},
                hmac_key="unit-test-key",
            )


def test_pathology_reduced_publication_does_not_reproject_published_facts(monkeypatch):
    outcome = _evaluate([_master()], [_report()])
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id=RULE_ID, snapshot_hash="a" * 64,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.SATISFIED,
        reason_code="requirement_satisfied", fact_refs=outcome.fact_refs,
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
        decision=decision, raw_customer_display_facts=outcome.display_facts,
        evidence_snapshot=None, evidence_materials=None,
    )
    assert result["status"] == "compliant"
    assert result["customer_display_facts"] == safe_tumor_pathology_customer_display_facts(
        rule_id=RULE_ID, raw=outcome.display_facts,
    )
    assert calls == [outcome.display_facts]


def _session(master=(), report=(), *, truncated=None, failed=None, extra=None):
    rows = {MASTER: tuple(master), REPORT: tuple(report), **(extra or {})}

    def reader(**kwargs):
        key = kwargs["source_key"]
        if failed == (key, "error"):
            raise SourceEvidenceQueryError("test_source_query_error")
        if failed == (key, "unavailable"):
            raise SourceEvidenceUnavailable("test_source_unavailable")
        source_rows = rows.get(key, ())
        if key == truncated and not source_rows:
            source_rows = ({"pathology_exam_id": "TRUNCATED"},)
        return SnapshotSourceRows.create(source_key=key, rows=source_rows, truncated=key == truncated, limit_rows=500)

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=OLD_RULES,
        institute_id="test-institute", patient_id="test-patient", visit_id="test-visit",
        source_schema=None, created_at="2026-09-22T12:00:00+08:00", row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(("tumor_pathology",), selected_rule_ids=OLD_RULES),
    )


class _ForbiddenClient:
    async def generate(self, *_args, **_kwargs):
        raise AssertionError("病理报告完整性不得调用模型")


async def _execute(session, *, rule_ids=(RULE_ID,), client=None, payload=None, typed=True):
    return await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=rule_ids,
        wrapper_rules=[{"rule_id": rule_id, "custom_prompt": "核对病理和病程。{medical_text}"} for rule_id in rule_ids],
        evidence_payload=payload,
        institute_id="test-institute", patient_id="test-patient", visit_id="test-visit", source_schema=None,
        llm_client=client or _ForbiddenClient(),
        evidence_snapshot=session.snapshot if session else None,
        evidence_materials=session.materials if session else None,
        decision_rule_ids=rule_ids if typed else (),
    )


@pytest.mark.asyncio
async def test_native_branch_uses_all_session_rows_and_skips_malignancy_and_legacy_query(monkeypatch):
    masters = [_master(f"E{i}") for i in range(10)]
    reports = [_report(f"E{i}") for i in range(9)]
    session = _session(masters, reports)

    def forbidden(**_kwargs):
        raise AssertionError("新规则不得回查数据库")

    monkeypatch.setattr(tumor, "read_luxian_0609_native_source_rows", forbidden)
    result = await _execute(session, payload={"programmatic_timeline": {"documents": {REPORT: [_report("E9")]}}})
    assert len(result.decisions) == 1
    assert reduce_luxian_0609_rule_decision(result.decisions[0]).final_state == "data_gap"
    facts = dict(result.customer_display_facts)[RULE_ID]
    assert (facts["event_count"], facts["report_count"], facts["unresolved_event_count"]) == (10, 9, 1)
    assert result.llm_call_count == result.total_tokens == 0
    assert set(result.decisions[0].fact_refs).issubset(session.snapshot.document_refs)
    assert len(result.decisions[0].fact_refs) == 19


@pytest.mark.asyncio
async def test_native_confirmed_execution_missing_local_report_remains_gap():
    result = await _execute(_session([_master(record_content="已完成病理检查。")]))
    decision = result.decisions[0]
    assert decision.reason_code == "target_report_missing"
    assert reduce_luxian_0609_rule_decision(decision).final_state == "data_gap"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["truncated", "unavailable", "error"])
async def test_native_incomplete_source_never_becomes_technical_error_or_not_applicable(state):
    session = _session(truncated=MASTER if state == "truncated" else None, failed=(MASTER, state) if state != "truncated" else None)
    result = await _execute(session)
    assert reduce_luxian_0609_rule_decision(result.decisions[0]).final_state == "data_gap"


@pytest.mark.asyncio
async def test_legacy_payload_without_a_session_cannot_claim_report_scope(monkeypatch):
    monkeypatch.setattr(tumor, "read_luxian_0609_native_source_rows", lambda **kwargs: pytest.fail("不得回查数据库"))
    result = await _execute(None, typed=False, payload={"programmatic_timeline": {"documents": {MASTER: [_master()], REPORT: [_report()]}}})
    assert result.results[0]["status"] == "data_gap"
    assert result.llm_call_count == 0


class _FixedClient:
    def __init__(self):
        self.prompts = []

    async def generate(self, prompt, **_kwargs):
        self.prompts.append(prompt)
        return {"choices": [{"message": {"content": json.dumps({"is_compliant": True})}}], "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}, "_api_time": 0.2}


@pytest.mark.asyncio
async def test_adding_rule_keeps_old_four_decisions_facts_and_model_usage_identical():
    session = _session(
        [_master()], [_report(diagnosis="病理诊断为良性组织。")],
        extra={
            "surgery_record": ({"surgery_process": "术中切取组织标本并送病理检查。"},),
            "daily_course_record": ({"record_content": "病情平稳，治疗后继续观察。"},),
            "diagnosis": ({"diagnosis_code": "J18.9", "diagnosis_name": "肺炎"},),
            "inpat_registration.discharge_horizon": ({"discharge_time": "2026-09-03 10:00:00"},),
        },
    )
    baseline_client, expanded_client = _FixedClient(), _FixedClient()
    baseline = await _execute(session, rule_ids=OLD_RULES, client=baseline_client)
    expanded = await _execute(session, rule_ids=(RULE_ID, *OLD_RULES), client=expanded_client)
    assert expanded.decisions[1:] == baseline.decisions
    assert tuple(item for item in expanded.customer_display_facts if item[0] != RULE_ID) == baseline.customer_display_facts
    assert expanded.llm_call_count == baseline.llm_call_count
    assert expanded.total_tokens == baseline.total_tokens
    assert expanded.prompt_tokens == baseline.prompt_tokens
    assert expanded.completion_tokens == baseline.completion_tokens
    assert expanded.api_time == baseline.api_time
    assert expanded_client.prompts == baseline_client.prompts
