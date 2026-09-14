"""跨事件模型失败必须与资料缺失分离，首答和恢复使用同一合同。"""

from copy import deepcopy

import pytest

from app.services.luxian_0609 import native_exam_lab_execution as native
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from test_luxian_0609_native_exam_lab_execution import _Client, _typed_session, _wrapper


def _answer():
    return {
        "schema_version": "lx0609-exam-lab-text-facts-v4",
        "facts": [
            {
                "rule_id": rule_id,
                "event_position": position,
                "applicability": "applicable",
                "semantic_state": "present",
                "positive_state": "positive" if rule_id.endswith("012") else "not_relevant",
                "course_doc_positions": [position],
            }
            for rule_id in ("LX0609-011", "LX0609-012")
            for position in (1, 2)
        ],
    }


def _single_event_answer(rule_id: str):
    return {
        "schema_version": "lx0609-exam-lab-text-facts-v3",
        "facts": [
            {
                "rule_id": rule_id,
                "applicability": "applicable",
                "semantic_state": "present",
                "positive_state": "positive" if rule_id.endswith("012") else "not_relevant",
                "course_doc_positions": [1],
            }
        ],
    }


async def _execute(
    monkeypatch,
    answers,
    *,
    report_text="阳性：异常信号。",
    report_texts: tuple[str, str] | None = None,
):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=tuple(
            {
                "exam_id": f"EXAM-{position}",
                "exam_type": "CT",
                "exam_name": name,
                "report_time": f"2026-04-{25 + position} 12:00:00",
                "exam_conclusion": (
                    report_texts[position - 1] if report_texts else report_text
                ),
            }
            for position, name in ((1, "胸部CT"), (2, "头颅CT"))
        ),
        exam_report_rows=tuple(
            {
                "exam_id": f"EXAM-{position}",
                "report_time": f"2026-04-{25 + position} 12:00:00",
                "exam_item_name": "CT报告",
                "exam_result": (
                    report_texts[position - 1] if report_texts else report_text
                ),
            }
            for position in (1, 2)
        ),
        course_rows=tuple(
            {
                "record_time": f"2026-04-{25 + position} 13:00:00",
                "record_content": "结果已记录并完成临床判断与处置。",
            }
            for position in (1, 2)
        ),
        evaluation_horizon_rows=({"horizon_date": "2026-04-30"},),
    )
    rule_ids = ("LX0609-011", "LX0609-012")
    client = _Client(answers)
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=rule_ids,
        wrapper_rules=[_wrapper(rule) for rule in rule_ids],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=rule_ids,
    )
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule} for rule in rule_ids],
        execution_results=list(result.results),
        reduced_decisions=bind_and_reduce_luxian_0609_rule_decisions(
            decisions=result.decisions, expected_rule_ids=rule_ids,
            snapshot=snapshot, evidence_materials=materials,
        ),
        customer_display_facts=result.customer_display_facts,
        audit_context={"evidence_snapshot": snapshot, "evidence_materials": materials},
    )
    return result, {row["rule_id"]: row for row in canonical}, client


@pytest.mark.asyncio
async def test_cross_event_citation_recovers_with_event_isolated_context(monkeypatch):
    bad = _answer()
    bad["facts"][1]["course_doc_positions"] = [1]

    result, rows, client = await _execute(
        monkeypatch,
        [bad, _single_event_answer("LX0609-011"), _single_event_answer("LX0609-011")],
        report_texts=(
            "阳性：第一事件异常。\nONLY_EVENT_ONE",
            "阳性：第二事件异常。\nONLY_EVENT_TWO",
        ),
    )

    assert result.llm_call_count == 3
    assert rows["LX0609-011"]["status"] == "compliant"
    assert rows["LX0609-012"]["status"] == "compliant"
    assert "EVENT_DOC=E01-01" in client.prompts[1]
    assert "EVENT_DOC=E01-02" not in client.prompts[1]
    assert "EVENT_DOC=E01-02" in client.prompts[2]
    assert "EVENT_DOC=E01-01" not in client.prompts[2]
    assert "ONLY_EVENT_TWO" not in client.prompts[1]
    assert "ONLY_EVENT_ONE" not in client.prompts[2]


@pytest.mark.asyncio
async def test_persistent_cross_event_citation_is_failure_not_missing_field(monkeypatch):
    bad = _answer()
    bad["facts"][1]["course_doc_positions"] = [1]
    result, rows, _ = await _execute(
        monkeypatch,
        [
            bad,
            _single_event_answer("LX0609-011"),
            {"schema_version": "wrong", "facts": []},
        ],
    )
    assert result.llm_call_count == 3
    assert result.parse_failure_kinds == ("evidence_ref",)
    assert rows["LX0609-011"]["status"] == "technical_error"
    assert rows["LX0609-011"]["reason_code"] != "required_field_missing"
    assert rows["LX0609-012"]["status"] == "compliant"
    assert result.model_execution_stats == {
        "requested_rule_count": 2,
        "first_success_rule_count": 1,
        "retried_rule_count": 1,
        "recovered_rule_count": 0,
        "failed_rule_count": 1,
        "first_answer_success_rate": 0.5,
        "recovery_success_rate": 0.0,
        "model_failure_rate": 0.5,
    }


@pytest.mark.asyncio
async def test_repaired_citation_preserves_other_rules_first_answer(monkeypatch):
    bad = _answer()
    bad["facts"][1]["course_doc_positions"] = [1]
    result, rows, _ = await _execute(
        monkeypatch,
        [bad, _single_event_answer("LX0609-011"), _single_event_answer("LX0609-011")],
    )
    assert result.llm_call_count == 3
    assert {rule: row["status"] for rule, row in rows.items()} == {
        "LX0609-011": "compliant", "LX0609-012": "compliant",
    }
    assert result.model_execution_stats["first_answer_success_rate"] == 0.5
    assert result.model_execution_stats["recovery_success_rate"] == 1.0
    assert result.model_execution_stats["model_failure_rate"] == 0.0


@pytest.mark.asyncio
async def test_outer_schema_failure_cannot_bypass_citation_check_on_retry(monkeypatch):
    bad = _answer()
    bad["facts"][1]["course_doc_positions"] = [1]
    result, rows, _ = await _execute(monkeypatch, [{"schema_version": "wrong", "facts": []}, bad])
    assert result.llm_call_count == 2
    assert rows["LX0609-011"]["status"] == "technical_error"
    assert rows["LX0609-012"]["status"] == "compliant"
    assert result.model_execution_stats["first_answer_success_rate"] == 0.0
    assert result.model_execution_stats["recovery_success_rate"] == 0.5
    assert result.model_execution_stats["model_failure_rate"] == 0.5


@pytest.mark.asyncio
@pytest.mark.parametrize("unknown_field", ["semantic_state", "positive_state", "applicability"])
async def test_complete_material_model_unknown_is_not_required_field_missing(monkeypatch, unknown_field):
    unknown = _answer()
    unknown["facts"][3][unknown_field] = "unknown"
    if unknown_field != "positive_state":
        unknown["facts"][3]["course_doc_positions"] = []
    result, rows, _ = await _execute(
        monkeypatch, [unknown, deepcopy(unknown)], report_text="待排急性脑梗死。"
    )
    assert result.llm_call_count == 2
    assert rows["LX0609-011"]["status"] == "compliant"
    assert rows["LX0609-012"]["status"] == "technical_error"
    assert rows["LX0609-012"]["reason_code"] != "required_field_missing"


@pytest.mark.asyncio
async def test_authoritative_positive_hint_resolves_model_classification_unknown(monkeypatch):
    answer = _answer()
    answer["facts"][3]["positive_state"] = "unknown"
    result, rows, _ = await _execute(monkeypatch, [answer])
    assert result.llm_call_count == 1
    assert rows["LX0609-012"]["status"] == "compliant"


@pytest.mark.asyncio
async def test_success_without_recovery_has_no_recovery_denominator(monkeypatch):
    result, rows, _ = await _execute(monkeypatch, [_answer()])
    assert all(row["status"] == "compliant" for row in rows.values())
    assert result.llm_call_count == 1
    assert result.model_execution_stats["first_answer_success_rate"] == 1.0
    assert result.model_execution_stats["recovery_success_rate"] is None
    assert result.model_execution_stats["model_failure_rate"] == 0.0
