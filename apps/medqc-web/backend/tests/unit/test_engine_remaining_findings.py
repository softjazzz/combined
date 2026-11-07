"""Claude剩余发现：合成材料与固定应答，经项目禁网入口执行。"""

import pytest


from datetime import datetime


from typing import Any


from app.services.luxian_0609 import native_course_quality_execution as course


from app.services.luxian_0609.course_quality import rules_008_009 as r89


from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)


from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)


from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)


class a_FixedClient:
    def __init__(self, outputs: list[Any]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **kwargs: Any) -> dict:
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        import json

        return {
            "choices": [
                {"message": {"content": json.dumps(output, ensure_ascii=False)}}
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }


def a_session_018(complaint: str):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            [
                {
                    "record_content": "入院记录正文完整。",
                    "record_time": "2026-06-01 09:00:00",
                    "chief_complaint": complaint,
                }
            ]
            if source_key == "admission_record"
            else [
                {
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                    "diagnosis_name": "稳定型心绞痛",
                }
            ]
            if source_key == "diagnosis"
            else []
        )
        return SnapshotSourceRows.create(
            source_key=source_key, rows=rows, truncated=False, limit_rows=50
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-01-01-02",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
    )


async def a_run_018(complaint: str, output: Any):
    session = a_session_018(complaint)
    client = a_FixedClient([output])
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-01-02",),
        decision_rule_ids=("LX0609-01-01-02",),
        wrapper_rules=[
            {"rule_id": "LX0609-01-01-02", "custom_prompt": "x {medical_text}"}
        ],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-01-01-02",),
        snapshot=session.snapshot,
    )
    return reduced[0]


_UNKNOWN_ATOMIC = {
    "chief_signal_kind": "unknown",
    "chief_complaint_signals": [],
    **{
        field: "unknown"
        for field in (
            "anatomic_relation",
            "laterality_relation",
            "symptom_relation",
            "disease_course_relation",
            "disease_direction_relation",
        )
    },
    "medical_analysis": "材料不足",
}


_LONG = "反复胸痛伴胸闷气促乏力出汗心悸头晕三个月余加重一天"  # >20 字


def a_base_009() -> RuleDecision:
    return RuleDecision(
        rule_id="LX0609-02-01-05",
        snapshot_hash="a" * 64,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.SATISFIED,
        reason_code="requirement_satisfied",
        fact_refs=("b" * 64,),
        evaluator_version="x",
        confidence=1.0,
    )


def a_event(ref: str) -> dict:
    return {
        "event_ref": ref,
        "change_category": "exam_lab",
        "is_explicit_change": True,
        "corresponding_course_ref": "",
    }


import json


from typing import Any


from app.services.luxian_0609 import native_tumor_pathology_execution as tumor


from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision


from app.services.luxian_0609.executor_registry import (
    resolve_legacy_executor_material_source_keys,
)


class b_NoModel:
    def __init__(self, outputs: list[Any] | None = None) -> None:
        self.outputs = list(outputs or [])
        self.calls = 0

    async def generate(self, prompt: str, **kwargs: Any) -> dict:
        self.calls += 1
        if not self.outputs:
            raise AssertionError("不应调用模型")
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(self.outputs.pop(0), ensure_ascii=False)
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }


async def b_run(session, client):
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-06-02-03",),
        wrapper_rules=[
            {"rule_id": "LX0609-06-02-03", "custom_prompt": "x {medical_text}"}
        ],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-06-02-03",),
    )
    return result, reduce_luxian_0609_rule_decision(result.decisions[0])


from typing import Any


from app.services.luxian_0609 import prophylactic_antimicrobial_duration as pad


_EVIDENCE = "切口红肿渗液，体温38.9℃，血常规白细胞18.2×10^9/L，考虑切口感染"


class f_Client:
    def __init__(self, state: str) -> None:
        self.state = state
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **kwargs: Any) -> dict:
        self.prompts.append(prompt)
        quote = _EVIDENCE if self.state == "present" else None
        content = {
            "schema_version": pad.SCHEMA_VERSION,
            "documents": [{"id": "D1", "state": self.state, "quote": quote}],
        }
        return {
            "choices": [
                {
                    "message": {"content": json.dumps(content, ensure_ascii=False)},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }


def f_inputs(body: str):
    event = pad.SurgeryEventInput(
        begin=datetime(2026, 3, 1, 8, 0),
        end=datetime(2026, 3, 1, 10, 0),
        incision_class="I",
        cardiac=False,
    )
    order = {
        "order_id": "a1",
        "generic_name": "头孢唑林钠",
        "drug_type": "抗菌药物",
        "drug_apply_method": "静脉滴注",
        "prescribed_datetime": "2026-03-01 07:30:00",
        "start_datetime": "2026-03-01 07:30:00",
        "stop_datetime": "2026-03-03 10:00:00",
    }
    course = (
        "daily_course_record:0",
        {"record_time": "2026-03-02 09:00:00", "record_content": body},
    )
    return event, order, course


async def f_run(body: str, state: str):
    event, order, course = f_inputs(body)
    client = f_Client(state)
    outcome = await pad.evaluate_prophylactic_antimicrobial_duration(
        events=(event,),
        drug_order_rows=(order,),
        course_rows=(course,),
        llm_client=client,
    )
    return outcome, client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "complaint,state", [(_LONG, "non_compliant"), ("胸痛" * 10, "data_gap")]
)
async def test_length_failed_is_independent_of_unknown_semantics(complaint, state):
    item = await a_run_018(complaint, _UNKNOWN_ATOMIC)
    assert item.final_state.value == state
    assert item.criterion_results[1].status.value == "unknown"


@pytest.mark.parametrize("reverse", [False, True])
def test_009_confirmed_defect_survives_unknown_event(reverse):
    events = [a_event("E01"), a_event("E02")]
    decision, facts = r89._rule_009_change_event_decision(
        base_decision=a_base_009(),
        events=events[::-1] if reverse else events,
        event_times={"E01": datetime(2026, 1, 1, 10), "E02": None},
        course_times={},
        evaluation_horizon=datetime(2026, 1, 5),
    )
    assert decision.qc_direction is QcDirection.DEFECT
    assert facts["unmet_events"][0]["event_ref"] == "E01"
    assert facts["unresolved_events"] == [
        {"event_ref": "E02", "reason_code": "authoritative_time_missing"}
    ]


def test_009_unknown_only_does_not_become_defect():
    decision, facts = r89._rule_009_change_event_decision(
        base_decision=a_base_009(),
        events=(a_event("E02"),),
        event_times={},
        course_times={},
        evaluation_horizon=datetime(2026, 1, 5),
    )
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert facts["unresolved_events"][0]["event_ref"] == "E02"


@pytest.mark.asyncio
@pytest.mark.parametrize("padding", [0, 3300])
async def test_028_complete_long_body_infection_evidence(padding):
    outcome, client = await f_run("字" * padding + _EVIDENCE, "present")
    assert outcome.status == "compliant"
    assert _EVIDENCE in client.prompts[0]
    assert outcome.llm_call_count == 1


@pytest.mark.asyncio
async def test_028_complete_negative_and_bounded_overflow():
    outcome, _ = await f_run("术后恢复良好。", "absent")
    assert outcome.status == "non_compliant"
    outcome, client = await f_run(
        "字" * (pad.MAX_DOCUMENT_CHARS * pad.MAX_EVIDENCE_DOCUMENTS + 1) + _EVIDENCE,
        "absent",
    )
    assert (
        outcome.status == "data_gap"
        and outcome.reason_code == "candidate_scope_incomplete"
    )
    assert not client.prompts


@pytest.mark.asyncio
async def test_culture_formal_entry_local_absence_is_not_source_absence():
    from tests.unit import test_luxian_0609_handbook_exam_lab as h

    snapshot, materials = h._session(
        rows={
            **h._CULTURE_ROWS,
            "evaluation_context.horizon": (
                {
                    "horizon_date": "2026-09-08",
                    "basis": "discharge_date",
                    "row_ref": "h1",
                },
            ),
        }
    )
    execution = await h.native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(h.CULTURE_RULE,),
        wrapper_rules=[{"rule_id": h.CULTURE_RULE}],
        evidence_payload={},
        llm_client=h._ForbiddenClient(),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=(h.CULTURE_RULE,),
    )
    item = h.reduce_luxian_0609_rule_decision(execution.decisions[0])
    assert (item.final_state.value, item.reason_code) == (
        "data_gap",
        "target_report_missing",
    )


def remaining_session(rules, rows, end="2026-05-03 12:00:00", conflict=False):
    from tests.unit.test_luxian_0609_frozen_discharge_horizon import FROZEN

    frozen = {
        **FROZEN,
        "admission_datetime": "2026-04-01 08:00:00",
        "discharge_datetime": end,
        "evaluation_horizon": str(end or "")[:10],
    }
    if conflict:
        frozen["resolution_status"] = "time_conflict"

    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50
        )

    executor = (
        "tumor_pathology"
        if "LX0609-06-02-03" in rules
        else "surgery_presence"
        if "LX0609-04-02-02" in rules
        else "surgery_gate"
        if "LX0609-05-01-01" in rules
        else "surgery_document"
    )
    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=rules,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-05-03T12:00:00+08:00",
        row_reader=reader,
        evaluation_horizon_snapshot=frozen,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            (executor,), selected_rule_ids=rules
        ),
    )


def pathology_rows(daily=()):
    return {
        "pathology_exam_master": (
            {
                "pathology_exam_id": "PATH-1",
                "specimen_name": "胃窦组织",
                "request_datetime": "2026-04-26 08:00:00",
            },
        ),
        "pathology_exam_report": (
            {
                "pathology_exam_id": "PATH-1",
                "diagnosis": "（胃窦）中分化腺癌",
                "report_datetime": "2026-05-02 10:00:00",
            },
        ),
        "daily_course_record": daily,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "end,conflict,state,reason",
    [
        ("2026-04-29 10:00:00", False, "data_gap", "evaluation_window_not_mature"),
        ("2026-05-02 10:00:00", False, "non_compliant", "requirement_violated"),
        ("2026-05-03 12:00:00", False, "non_compliant", "requirement_violated"),
        ("", False, "data_gap", "authoritative_time_missing"),
        ("2026-05-03", False, "data_gap", "authoritative_time_missing"),
        ("2026-05-03 12:00:00", True, "data_gap", "authoritative_time_conflict"),
    ],
)
async def test_pathology_frozen_horizon_controls_negative(end, conflict, state, reason):
    session = remaining_session(("LX0609-06-02-03",), pathology_rows(), end, conflict)
    result, item = await b_run(session, b_NoModel())
    assert (item.final_state.value, item.reason_code) == (state, reason)
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_pathology_positive_still_valid_and_canonical_roundtrip():
    session = remaining_session(
        ("LX0609-06-02-03",),
        pathology_rows(
            (
                {
                    "record_time": "2026-05-02 15:00:00",
                    "record_content": "病理回报：（胃窦）中分化腺癌，已告知患者。",
                },
            )
        ),
    )
    result, item = await b_run(
        session,
        b_NoModel(
            [
                {
                    "schema_version": "lx0609-pathology-documentation-facts-v1",
                    "events": [
                        {
                            "event": "P1",
                            "state": "documented",
                            "document": "d1",
                            "quote": "病理回报：（胃窦）中分化腺癌",
                        }
                    ],
                }
            ]
        ),
    )
    assert item.final_state.value == "compliant"
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_reduced_customer_result,
    )
    from test_luxian_0609_death_record_timeliness import saved_roundtrip

    final = finalize_luxian_0609_reduced_customer_result(
        decision=item,
        raw_customer_display_facts=dict(result.customer_display_facts).get(
            item.rule_id
        ),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert final["status"] == "compliant"
    saved = saved_roundtrip(final)
    assert (
        saved["status"] == final["status"]
        and saved["reason_code"] == final["reason_code"]
    )
    assert saved["customer_display_facts"] == final["customer_display_facts"]
    assert saved["evidence"] == final["evidence_items"]


def run_surgery_order(status, *, planned="2026-05-04 08:00:00", performed=False):
    from app.services.luxian_0609 import native_execution as n

    rows = {
        "inpat_nondrug_order": (
            {
                "order_id": "O",
                "order_type": "手术",
                "order_status": status,
                "planned_start_datetime": planned,
                "order_name": "腹腔镜胆囊切除术",
            },
        )
    }
    if performed:
        rows["mr_surgery"] = (
            {
                "surgery_id": "S",
                "surgery_name": "腹腔镜胆囊切除术",
                "surgery_code": "51.2300",
                "surgical_level": "二级",
                "surgery_begin_datetime": datetime(2026, 5, 2, 8),
                "surgery_end_datetime": datetime(2026, 5, 2, 10),
            },
        )
    session = remaining_session(("LX0609-04-02-02",), rows)
    result = n.execute_luxian_0609_native_rules(
        rule_ids=("LX0609-04-02-02",),
        decision_rule_ids=("LX0609-04-02-02",),
        visit_id="V",
        institute_id="I",
        patient_id="P",
        source_schema=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    item = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-02-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    return session, result, item


@pytest.mark.parametrize(
    "status,planned,performed,state,reason",
    [
        (
            "新开",
            "2026-05-04 08:00:00",
            False,
            "not_applicable",
            "evaluation_window_not_mature",
        ),
        ("新开", "2026-05-01 08:00:00", False, "data_gap", "source_readiness_unproven"),
        ("停止", "2026-05-04 08:00:00", False, "data_gap", "source_readiness_unproven"),
        (
            "作废",
            "2026-05-04 08:00:00",
            False,
            "not_applicable",
            "trigger_absent_complete",
        ),
        (
            "已取消",
            "2026-05-04 08:00:00",
            False,
            "not_applicable",
            "trigger_absent_complete",
        ),
        (
            "停止",
            "2026-05-01 08:00:00",
            True,
            "non_compliant",
            "required_document_missing",
        ),
        (
            "新开",
            "2026-05-01 08:00:00",
            True,
            "non_compliant",
            "required_document_missing",
        ),
        ("取消", "2026-05-01 08:00:00", True, "data_gap", "association_failed"),
    ],
)
def test_surgery_plan_stop_execution_and_conflict(
    status, planned, performed, state, reason
):
    session, result, item = run_surgery_order(
        status, planned=planned, performed=performed
    )
    assert (item.final_state.value, item.reason_code) == (state, reason)


@pytest.mark.asyncio
async def test_preop_summary_not_exempted_by_postop_execution_gate():
    from app.services.luxian_0609 import native_surgery_document_execution as s

    rule = "LX0609-04-01-01"
    session = remaining_session(
        (rule,),
        {
            "inpat_nondrug_order": (
                {
                    "order_id": "O",
                    "order_type": "手术",
                    "order_status": "新开",
                    "planned_start_datetime": "2026-05-04 08:00:00",
                },
            )
        },
    )
    result = await s.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=(rule,),
        decision_rule_ids=(rule,),
        wrapper_rules=[{"rule_id": rule}],
        evidence_payload={},
        llm_client=b_NoModel(),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    item = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=(rule,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    assert item.final_state.value == "non_compliant"


@pytest.mark.asyncio
async def test_009_mixed_result_and_unresolved_marker_survive_canonical_storage():
    from tests.unit import test_luxian_0609_native_course_quality_execution as q
    from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
    from test_luxian_0609_death_record_timeliness import saved_roundtrip

    rule = "LX0609-02-01-05"
    session = q._severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-01 08:00:00"}],
        daily_rows=[
            q._row("病危记录。", f"2026-01-0{day} 08:00:00") for day in range(1, 5)
        ],
        external_rows={
            "exam_item_report": [
                {
                    "report_time": "2026-01-02 10:00:00",
                    "exam_impression": "新发异常改变",
                },
                {"exam_impression": "另一项新发异常改变"},
            ]
        },
        evaluation_as_of_date="2026-01-04",
    )
    result, reduced = await q._run_typed_009(
        session,
        q._Client(
            [
                {
                    "events": [
                        {
                            "event_ref": ref,
                            "change_category": "exam_lab",
                            "is_explicit_change": True,
                            "corresponding_course_ref": "",
                        }
                        for ref in ("E01", "E02")
                    ]
                }
            ]
        ),
    )
    final = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )[0]
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["unresolved_events"] == [
        {"event_ref": "E02", "reason_code": "authoritative_time_missing"}
    ]
    saved = saved_roundtrip(final)
    assert (
        saved["status"] == final["status"]
        and saved["reason_code"] == final["reason_code"]
    )
    assert saved["customer_display_facts"] == final["customer_display_facts"]
    assert saved["evidence"] == final["evidence_items"]


@pytest.mark.asyncio
async def test_028_budget_rejection_keeps_timely_surgery_sibling(tmp_path, monkeypatch):
    from app.services.llm_token_budget import BudgetError, BudgetVerdict
    from app.services.luxian_0609 import native_surgery_gate_execution as sg

    rules = ("LX0609-04-02-01", "LX0609-05-01-01")
    event, order, course = f_inputs("术后切口干燥，体温正常。")
    rows = {
        "surgery_record": (
            {
                "document_id": "S",
                "surgery_name": "腹腔镜胆囊切除术",
                "surgery_begin_time": "2026-03-01 08:00:00+08:00",
                "surgery_end_time": "2026-03-01 10:00:00+08:00",
                "record_time": "2026-03-01 12:00:00",
                "surgery_process": "手术顺利。",
            },
        ),
        "mr_surgery": (
            {
                "surgery_begin_datetime": event.begin,
                "surgery_end_datetime": event.end,
                "surgial_incision_level": "Ⅰ",
                "surgery_code": "51.2301",
                "surgery_name": "腹腔镜胆囊切除术",
            },
        ),
        "inpat_drug_order": (order,),
        "daily_course_record": (course[1],),
    }
    session = remaining_session(rules, rows)

    class Rejected:
        calls = 0

        async def generate(self, *args, **kwargs):
            self.calls += 1
            raise BudgetError(
                BudgetVerdict("OVER_BUDGET", "synthetic", "profile", "model")
            )

    client = Rejected()
    monkeypatch.setenv("LUXIAN_0609_FACT_FREEZE_DIR", str(tmp_path))
    result = await sg.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=rules,
        decision_rule_ids=rules,
        wrapper_rules=[{"rule_id": r} for r in rules],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=rules,
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert [(r.final_state.value, r.reason_code) for r in reduced] == [
        ("compliant", "requirement_within_threshold"),
        ("technical_error", "llm_context_over_budget"),
    ]
    assert client.calls == 1 and result.llm_call_count == 0
    assert not list(tmp_path.rglob("*.json"))


@pytest.mark.asyncio
async def test_028_cancellation_propagates_without_retry():
    import asyncio

    class Cancelled:
        async def generate(self, *args, **kwargs):
            raise asyncio.CancelledError()

    event, order, course = f_inputs("术后观察。")
    with pytest.raises(asyncio.CancelledError):
        await pad.evaluate_prophylactic_antimicrobial_duration(
            events=(event,),
            drug_order_rows=(order,),
            course_rows=(course,),
            llm_client=Cancelled(),
        )


@pytest.mark.asyncio
async def test_028_untimed_candidate_cannot_complete_negative():
    event, order, course = f_inputs("术后观察。")
    outcome = await pad.evaluate_prophylactic_antimicrobial_duration(
        events=(event,),
        drug_order_rows=(order,),
        course_rows=(course, ("unknown-time", {"record_content": _EVIDENCE})),
        llm_client=f_Client("absent"),
    )
    assert (outcome.status, outcome.reason_code) == (
        "data_gap",
        "candidate_scope_incomplete",
    )


@pytest.mark.asyncio
async def test_028_partial_positive_does_not_clear_other_unknown_documents():
    class Mixed:
        async def generate(self, *args, **kwargs):
            return {
                "content": json.dumps(
                    {
                        "schema_version": pad.SCHEMA_VERSION,
                        "documents": [
                            {"id": "D1", "state": "present", "quote": _EVIDENCE},
                            {"id": "D2", "state": "unknown", "quote": None},
                        ],
                    }
                )
            }

    state, keys, _ = await pad._infection_evidence(
        (
            ("first", {"record_content": _EVIDENCE}, datetime(2026, 3, 2)),
            (
                "second",
                {"record_content": "待核对的另一台手术病程。"},
                datetime(2026, 3, 4),
            ),
        ),
        Mixed(),
    )
    assert state == "unresolved" and keys == ("first",)
