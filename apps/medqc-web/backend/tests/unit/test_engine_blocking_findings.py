"""B-01至B-05：只用合成材料、固定应答和内存保存，不连接服务。"""

import json
from datetime import date, datetime

import pytest

from tests.unit import test_luxian_0609_native_extended_document_execution as fixtures


@pytest.fixture(autouse=True)
def isolated_freeze(monkeypatch, tmp_path):
    monkeypatch.setenv("LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR", str(tmp_path))


class Reasons:
    def __init__(self):
        self.calls = 0

    async def generate(self, prompt, **kwargs):
        self.calls += 1
        payload = json.loads(prompt.rsplit("INPUT_JSON=", 1)[1])
        texts = {d["doc_ref"]: d["text"] for d in payload["documents"]}
        events = []
        for e in payload["events"]:
            item = dict(event_id=e["event_id"], documented_use="no", quote_doc_refs={})
            for ref in e["doc_refs"]:
                for kind, quote in [
                    ("infection_judgment", "考虑肺部感染"),
                    ("selection_reason", "经验性抗感染"),
                ]:
                    if quote in texts[ref]:
                        item[kind + "_quote"] = quote
                        item["quote_doc_refs"][kind] = ref
                        item["documented_use"] = "yes"
            events.append(item)
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(
                            dict(
                                schema_version="lx0609_antimicrobial_order_reason_v1",
                                events=events,
                            )
                        )
                    },
                }
            ],
            "usage": {"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4},
        }


def drug(name="头孢曲松", **extra):
    return dict(
        generic_name=name,
        order_id=name,
        planned_start_datetime="2026-06-01 10:00:00",
        **extra,
    )


def horizon(value):
    return (
        {
            "horizon_date": value[:10],
            **({"horizon_datetime": value} if ":" in value else {}),
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", ["05-01-02", "05-01-05", "05-01-06"])
@pytest.mark.parametrize(
    "end,state", [("2026-06-01 11:00:00", "not_applicable"), ("2026-06-01", "data_gap")]
)
async def test_immature_or_date_only_antimicrobial_horizon(rule, end, state):
    snapshot, materials, native, reduceds = await fixtures._evaluate_selected(
        ("LX0609-" + rule,),
        {
            "inpat_drug_order": (drug("美罗培南"),),
            "evaluation_context.horizon": horizon(end),
        },
        llm_client=Reasons(),
    )
    reduced = reduceds[0]
    assert reduced.final_state.value == state
    assert reduced.reason_code == (
        "evaluation_window_not_mature"
        if state == "not_applicable"
        else "authoritative_time_missing"
    )
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_reduced_customer_result,
    )

    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced,
        raw_customer_display_facts=dict(native.customer_display_facts).get(
            reduced.rule_id
        ),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
    )
    assert final["status"] == state


@pytest.mark.asyncio
async def test_single_and_combined_reason_rule_use_same_frozen_horizon():
    rows = {
        "inpat_drug_order": (drug(),),
        "evaluation_context.horizon": horizon("2026-06-01 12:00:00"),
    }
    _, single = await fixtures._evaluate("LX0609-05-01-02", rows, llm_client=Reasons())
    _, _, _, combined = await fixtures._evaluate_selected(
        ("LX0609-05-01-02", "LX0609-05-01-03"), rows, llm_client=Reasons()
    )
    assert (single.final_state, single.reason_code) == (
        combined[0].final_state,
        combined[0].reason_code,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("padding", [0, 8100])
async def test_reason_in_long_document_is_visible_and_grounded(padding):
    client = Reasons()
    _, reduced = await fixtures._evaluate(
        "LX0609-05-01-05",
        {
            "inpat_drug_order": (drug(),),
            "evaluation_context.horizon": horizon("2026-06-03 12:00:00"),
            "daily_course_record": (
                {
                    "document_id": "D",
                    "record_time": "2026-06-01 11:00:00",
                    "record_content": "合成正文。" * padding
                    + "考虑肺部感染，经验性抗感染。",
                },
            ),
        },
        llm_client=client,
    )
    assert reduced.final_state.value == "compliant"
    assert client.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["未执行", "已作废"])
async def test_unperformed_drug_does_not_create_additional_expert_requirement(status):
    from special_antimicrobial_test_support import FrozenSpecialApprovalClient

    _, reduced = await fixtures._evaluate(
        "LX0609-05-01-06",
        {
            "inpat_drug_order": (
                drug("美罗培南"),
                drug("万古霉素", order_status=status),
            ),
            "evaluation_context.horizon": horizon("2026-06-03 12:00:00"),
            "consultation_record": (
                {
                    "document_id": "C",
                    "record_time": "2026-06-01 09:00:00",
                    "record_content": "感染科副主任医师会诊：同意使用美罗培南抗感染。",
                },
            ),
        },
        llm_client=FrozenSpecialApprovalClient(),
    )
    assert reduced.final_state.value == "compliant"


@pytest.mark.asyncio
async def test_culture_without_sampling_time_cannot_be_confirmed_late():
    _, reduced = await fixtures._evaluate(
        "LX0609-05-01-04",
        {
            "inpat_drug_order": (drug("美罗培南"), drug("万古霉素")),
            "labtest_master": (
                {
                    "test_id": "T",
                    "labtest_subject": "血培养",
                    "request_datetime": "2026-06-01 09:00:00",
                },
            ),
        },
    )
    assert (reduced.final_state.value, reduced.reason_code) == (
        "data_gap",
        "authoritative_time_missing",
    )


@pytest.mark.asyncio
async def test_request_and_sample_straddling_use_is_pending_clinical_definition():
    _, reduced = await fixtures._evaluate(
        "LX0609-05-01-04",
        {
            "inpat_drug_order": (drug("美罗培南"), drug("万古霉素")),
            "labtest_master": (
                {
                    "test_id": "T",
                    "labtest_subject": "血培养",
                    "request_datetime": "2026-06-01 09:00:00",
                    "sample_datetime": "2026-06-01 11:00:00",
                },
            ),
        },
    )
    assert (reduced.final_state.value, reduced.reason_code) == (
        "data_gap",
        "authoritative_time_conflict",
    )


@pytest.mark.asyncio
async def test_unperformed_second_drug_does_not_spoil_empiric_reason():
    _, reduced = await fixtures._evaluate(
        "LX0609-05-01-05",
        {
            "inpat_drug_order": (drug(), drug("左氧氟沙星", order_status="未执行")),
            "evaluation_context.horizon": horizon("2026-06-03 12:00:00"),
            "daily_course_record": (
                {
                    "document_id": "D",
                    "record_time": "2026-06-01 11:00:00",
                    "record_content": "头孢曲松：考虑肺部感染，经验性抗感染。",
                },
            ),
        },
        llm_client=Reasons(),
    )
    assert reduced.final_state.value == "compliant"


@pytest.mark.asyncio
async def test_death_unavailable_keeps_sibling_success_and_roundtrip():
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_reduced_customer_result,
    )
    from test_luxian_0609_death_record_timeliness import saved_roundtrip

    rules = ("LX0609-04-02-06", "LX0609-05-01-04")
    snapshot, materials, result, reduced = await fixtures._evaluate_selected(
        rules,
        {
            "inpat_registration": (
                {"death_datetime": "2026-06-01 10:00:00", "discharge_mode": "死亡"},
            )
        },
        unavailable_sources=frozenset({"death_record"}),
    )
    assert reduced[0].final_state.value == "data_gap"
    assert reduced[1].final_state.value == "not_applicable"
    for d in reduced:
        final = finalize_luxian_0609_reduced_customer_result(
            decision=d,
            raw_customer_display_facts=dict(result.customer_display_facts).get(
                d.rule_id
            ),
            evidence_snapshot=snapshot,
            evidence_materials=materials,
        )
        assert final["status"] == d.final_state.value
        assert saved_roundtrip(final)["status"] == final["status"]


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["discharge_date", "discharge_datetime"])
async def test_discharge_date_is_not_midnight_for_hourly_deadline(field):
    _, reduced = await fixtures._evaluate(
        "LX0609-08-01-01",
        {
            "inpat_registration": ({"discharge_datetime": "2026-06-01"},)
            if field == "discharge_datetime"
            else (),
            "discharge_record": (
                {
                    "document_id": "D",
                    field: "2026-06-01",
                    "record_time": "2026-06-02 10:00:00",
                },
            ),
        },
    )
    assert (reduced.final_state.value, reduced.reason_code) == (
        "data_gap",
        "authoritative_time_missing",
    )


def test_overdue_critical_event_is_not_hidden_by_immature_sibling():
    from app.services.luxian_0609.extended_document_critical_value import (
        CriticalValueInput,
        CriticalValueItem,
        CriticalValueDisposition,
        evaluate_critical_value_rules,
    )
    from app.services.luxian_0609.critical_value_result_mapping import (
        critical_value_customer_fact_status_is_valid,
    )

    inputs = CriticalValueInput(
        None,
        None,
        2,
        2,
        (
            CriticalValueItem("血钾", ("PH",), "", "PH", datetime(2026, 6, 1, 1), "A"),
            CriticalValueItem("血钠", ("PL",), "", "PL", datetime(2026, 6, 1, 10), "B"),
        ),
        (CriticalValueDisposition(datetime(2026, 6, 1, 8), "A"),),
        evaluation_horizon_datetime=datetime(2026, 6, 1, 11),
    )
    out = evaluate_critical_value_rules(rule_ids=("LX0609-06-04-01",), inputs=inputs)[0]
    assert out.final_state == "non_compliant"
    assert critical_value_customer_fact_status_is_valid(
        rule_id="LX0609-06-04-01", status=out.final_state, safe_facts=out.display_facts
    )


@pytest.mark.parametrize("with_clear", [False, True])
def test_uncertain_consultation_episode_cannot_be_all_clear(with_clear):
    from app.services.luxian_0609 import native_consultation_episode_execution as m

    rec = m._Recommendation("r1", "medication", "予奥美拉唑护胃", "奥美拉唑护胃", "d1")
    clear = m._Episode("d1", ("d1",), (), ("d1",), "absent", "clear", "high", (rec,))
    unknown = m._Episode("d2", ("d2",), (), ("d2",), "absent", "unknown", "low", ())
    completed = m._CompletedRecommendation(
        "d1", rec, m._ObservedTime(datetime(2026, 6, 1, 10), True)
    )
    assessment = m._ExecutionAssessment(
        "r1", "linked_specific", ("inpat_drug_order-1",), "high", ()
    )
    outcome = m._execution_outcome(
        "LX0609-03-01-04",
        episodes=(clear, unknown) if with_clear else (unknown,),
        completed_recommendations=(completed,) if with_clear else (),
        assessments=(assessment,) if with_clear else None,
    )
    assert outcome == ("evaluation_unknown", "semantic_low_confidence")
    from app.services.luxian_0609.consultation_measure_check import MeasureCheckOutcome

    refined, _ = m._apply_order_measure_check(
        outcome,
        MeasureCheckOutcome("ready", {}),
        completed=(completed,) if with_clear else (),
        assessments=(assessment,) if with_clear else None,
        already_excluded=frozenset(),
        source_incomplete_keys=frozenset(),
    )
    assert refined == outcome


@pytest.mark.asyncio
async def test_long_invasive_record_is_not_truncated():
    from app.services.luxian_0609.extended_document import (
        invasive_procedure_record as inv,
    )

    trigger = inv.ProcedureTrigger(
        inv.load_invasive_procedure_catalog()[0], date(2026, 6, 1), ("合成操作",)
    )

    class Fixed:
        async def generate(self, prompt, **kwargs):
            data = json.loads(prompt.split("INPUT_JSON=", 1)[1])
            assert "本次操作已实施" in data["records"][0]["text"]
            return {
                "content": json.dumps(
                    {
                        "schema_version": inv.RECORD_SCHEMA_VERSION,
                        "items": [
                            {
                                "id": "P01",
                                "state": "documented",
                                "record": "R01",
                                "quote": "本次操作已实施",
                            }
                        ],
                    }
                )
            }

    out = await inv.check_invasive_procedure_records(
        (trigger,),
        (
            {
                "document_id": "D",
                "record_time": "2026-06-01 11:00:00",
                "record_content": "合成正文" * 400 + "本次操作已实施。",
            },
        ),
        Fixed(),
    )
    assert out.state == "ready" and out.states[0][1] == "documented"


@pytest.mark.parametrize(
    "end,state",
    [
        (datetime(2026, 6, 1, 11), "not_applicable"),
        (datetime(2026, 6, 2, 12), "non_compliant"),
        (None, "data_gap"),
    ],
)
def test_handover_missing_requires_complete_window(end, state):
    from app.services.luxian_0609.extended_document.physician_handoff import (
        evaluate_physician_handoff,
    )

    out = evaluate_physician_handoff(
        physician_change_rows=(
            {
                "change_datetime": "2026-06-01 10:00:00",
                "old_physician_name": "甲",
                "new_physician_name": "乙",
            },
        ),
        physician_change_error="",
        nondrug_order_rows=(),
        nondrug_order_error="",
        daily_course_rows=(),
        daily_course_error="",
        handoff_rows=(
            {
                "document_id": "H",
                "record_time": "2026-06-01 09:00:00",
                "shift_time": "2026-06-01 10:00:00",
                "handoff_doctor": "甲",
                "record_content": "交班",
            },
        ),
        handoff_error="",
        handover_rows=(),
        handover_error="",
        evaluation_horizon_datetime=end,
    )
    assert out.final_state == state


@pytest.mark.asyncio
@pytest.mark.parametrize("positive", [False, True])
async def test_diagnosis_fourth_candidate_cannot_be_denied_by_first_three(positive):
    rows = {
        "admission_record_diagnosis": (
            {"diagnosis_type": "修正诊断", "diagnosis_name": "肺炎"},
        ),
        "daily_course_record": tuple(
            {
                "document_id": f"D{i}",
                "record_time": f"2026-06-01 {10 + i}:00:00",
                "record_content": "肺炎病情观察。"
                + ("理由为发热，依据为CT。" if i == 3 else "继续诊疗。"),
            }
            for i in range(4)
        ),
    }
    client = fixtures._DiagnosisChangeStateClient(
        ("present", "present") if positive else ("missing", "missing")
    )
    _, reduced = await fixtures._evaluate("LX0609-12-02-01", rows, llm_client=client)
    assert reduced.final_state.value == ("compliant" if positive else "data_gap")
    if not positive:
        assert reduced.reason_code == "candidate_scope_incomplete"
    assert len(client.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "end,state",
    [
        ("2026-06-02 12:00:00", "not_applicable"),
        ("2026-06-05 00:00:00", "non_compliant"),
    ],
)
async def test_invasive_missing_is_gated_at_formal_executor(end, state):
    _, reduced = await fixtures._evaluate(
        "LX0609-10-03-01",
        {
            "evaluation_context.horizon": horizon(end),
            "mr_surgery": (
                {
                    "surgery_code": "50.9101",
                    "surgery_name": "经皮肝穿刺引流术",
                    "surgery_begin_datetime": "2026-06-02 10:00:00",
                },
            ),
        },
    )
    assert reduced.final_state.value == state


@pytest.mark.parametrize(
    "status,excluded", [("作废", True), ("执行", False), ("停止", False)]
)
def test_canceled_consultation_order_is_removed_from_actual_projection(
    monkeypatch, status, excluded
):
    from app.services.luxian_0609 import native_consultation_episode_execution as m

    row = {
        "order_id": "O",
        "order_status": status,
        "generic_name": "奥美拉唑",
        "prescribed_datetime": "2026-06-01 10:00:00",
    }
    monkeypatch.setattr(
        m,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: [row] if source_key == "inpat_drug_order" else [],
    )
    out = m._candidate_documents(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        evidence_materials=None,
        evidence_snapshot=None,
        stay_window=m._StayWindow(date(2026, 6, 1), date(2026, 6, 3)),
    )
    assert (
        bool([item for item in out.candidates if item.source_key == "inpat_drug_order"])
        is not excluded
    )
    assert (
        bool(m._candidate_text(row=row, source_key="inpat_drug_order")) is not excluded
    )


@pytest.mark.asyncio
async def test_budget_failure_keeps_other_rule_success_without_freezing(tmp_path):
    from app.services.llm_token_budget import BudgetError, BudgetVerdict

    class Rejected:
        async def generate(self, *args, **kwargs):
            raise BudgetError(
                BudgetVerdict("OVER_BUDGET", "synthetic", "profile", "model")
            )

    snapshot, materials, result, reduced = await fixtures._evaluate_selected(
        ("LX0609-05-01-05", "LX0609-05-01-04"),
        {
            "evaluation_context.horizon": horizon("2026-06-03 12:00:00"),
            "inpat_drug_order": (drug("美罗培南"), drug("万古霉素")),
            "labtest_master": (
                {
                    "test_id": "T",
                    "labtest_subject": "血培养",
                    "sample_datetime": "2026-06-01 09:00:00",
                },
            ),
            "daily_course_record": (
                {
                    "document_id": "D",
                    "record_time": "2026-06-01 11:00:00",
                    "record_content": "合成病程",
                },
            ),
        },
        llm_client=Rejected(),
    )
    by_rule = {d.rule_id: d for d in reduced}
    assert by_rule["LX0609-05-01-05"].final_state.value == "technical_error"
    assert by_rule["LX0609-05-01-05"].reason_code == "llm_context_over_budget"
    assert by_rule["LX0609-05-01-04"].final_state.value == "compliant"
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_reduced_customer_result,
    )
    from test_luxian_0609_death_record_timeliness import saved_roundtrip

    successful = finalize_luxian_0609_reduced_customer_result(
        decision=by_rule["LX0609-05-01-04"],
        raw_customer_display_facts=dict(result.customer_display_facts)[
            "LX0609-05-01-04"
        ],
        evidence_snapshot=snapshot,
        evidence_materials=materials,
    )
    saved = saved_roundtrip(successful)
    assert saved["status"] == "compliant"
    assert saved["customer_display_facts"] == successful["customer_display_facts"]
    assert saved["rule_id"] == successful["rule_id"]
    # Canonical的evidence承载证据集合；Finalizer同名字段是展示文案。
    assert saved["evidence"] == successful["evidence_items"]
    assert result.llm_call_count == 0
    assert not list(tmp_path.rglob("*.json"))


def test_date_precision_is_frozen_and_cannot_masquerade_as_precise_midnight():
    from tests.unit.test_luxian_0609_frozen_discharge_horizon import FROZEN, _kwargs
    from app.services.luxian_0609.evaluation_horizon import (
        resolve_record_evaluation_horizon,
    )
    from app.services.luxian_0609.evidence_snapshot_provider import (
        build_luxian_0609_evidence_read_session,
    )
    from app.services.luxian_0609.native_extended_document_execution import (
        _critical_value_evaluation_horizon,
    )

    frozen = {
        **FROZEN,
        **resolve_record_evaluation_horizon(
            record_id="V",
            record_scene="final",
            admission_datetime="2026-06-01 08:00:00",
            discharge_datetime="2026-06-10",
            task_frozen_date="2026-07-01",
        ).to_dict(),
    }
    assert frozen["discharge_time_precision"] == "date"
    session = build_luxian_0609_evidence_read_session(**_kwargs(snapshot=frozen))
    row = session.materials.rows("evaluation_context.horizon")[0]
    assert row["time_precision"] == "date"
    assert _critical_value_evaluation_horizon((row,), "")[1] is None
    precise = build_luxian_0609_evidence_read_session(
        **_kwargs(
            snapshot={
                **frozen,
                "discharge_datetime": "2026-06-10 00:00:00",
                "discharge_time_precision": "datetime",
            }
        )
    )
    other = precise.materials.rows("evaluation_context.horizon")[0]
    assert (
        row["row_ref"] != other["row_ref"]
        and session.snapshot.snapshot_hash != precise.snapshot.snapshot_hash
    )


def test_single_rule_source_plan_always_includes_horizon():
    from app.services.luxian_0609.source_registry import (
        resolve_luxian_0609_decision_support_source_keys,
    )

    for rule in ("05-01-02", "05-01-05", "05-01-06", "10-01-01", "10-03-01"):
        assert (
            "evaluation_context.horizon"
            in resolve_luxian_0609_decision_support_source_keys(("LX0609-" + rule,))
        )


@pytest.mark.asyncio
async def test_canceled_status_does_not_erase_explicitly_performed_drug():
    from special_antimicrobial_test_support import FrozenSpecialApprovalClient

    _, reduced = await fixtures._evaluate(
        "LX0609-05-01-06",
        {
            "inpat_drug_order": (
                drug(
                    "美罗培南",
                    order_status="已作废",
                    record_content="已给予美罗培南静脉滴注。",
                ),
            ),
            "evaluation_context.horizon": horizon("2026-06-03 12:00:00"),
            "consultation_record": (
                {
                    "document_id": "C",
                    "record_time": "2026-06-01 09:00:00",
                    "record_content": "感染科副主任医师会诊：同意使用美罗培南抗感染。",
                },
            ),
        },
        llm_client=FrozenSpecialApprovalClient(),
    )
    assert reduced.final_state.value == "compliant"


@pytest.mark.asyncio
async def test_different_054_and_057_exclusion_contracts_do_not_share_empty_facts():
    client = Reasons()
    _, _, native, reduced = await fixtures._evaluate_selected(
        ("LX0609-05-01-02", "LX0609-05-01-05"),
        {
            "inpat_drug_order": (
                drug(order_status="已作废", record_content="已给予头孢曲松。"),
            ),
            "evaluation_context.horizon": horizon("2026-06-03 12:00:00"),
            "daily_course_record": (
                {
                    "document_id": "D",
                    "record_time": "2026-06-01 11:00:00",
                    "record_content": "头孢曲松：考虑肺部感染，经验性抗感染。",
                },
            ),
        },
        llm_client=client,
    )
    assert reduced[0].final_state.value == "not_applicable"
    assert reduced[1].final_state.value == "compliant"
    assert native.llm_call_count == client.calls == 1


def test_confirmed_consultation_defect_survives_another_unknown_episode():
    from app.services.luxian_0609 import native_consultation_episode_execution as m

    rec = m._Recommendation("r", "medication", "予奥美拉唑", "奥美拉唑", "d")
    clear = m._Episode("d", ("d",), (), ("d",), "absent", "clear", "high", (rec,))
    unknown = m._Episode("u", ("u",), (), ("u",), "absent", "unknown", "low", ())
    completed = m._CompletedRecommendation(
        "d", rec, m._ObservedTime(datetime(2026, 6, 1, 10), True)
    )
    missing = m._ExecutionAssessment(
        "r", "absent", (), "high", (), execution_record_state="no_trace"
    )
    assert (
        m._execution_outcome(
            "LX0609-03-01-04",
            episodes=(clear, unknown),
            completed_recommendations=(completed,),
            assessments=(missing,),
        )[0]
        == "non_compliant"
    )


@pytest.mark.asyncio
async def test_new_reason_protocol_does_not_overwrite_or_reuse_legacy_freeze(tmp_path):
    from app.services.luxian_0609.extended_document import (
        antimicrobial_order_reason as r,
    )
    from app.services.luxian_0609 import antimicrobial_freeze as store

    events = r.derive_antimicrobial_use_events(
        (drug(),), lambda _: ("头孢曲松",)
    ).events
    text = "考虑肺部感染，经验性抗感染。"
    docs = (
        r.WindowDocument(
            "D1", "daily_course_record", {}, datetime(2026, 6, 1, 11), text
        ),
    )
    refs = {events[0].event_id: ("D1",)}
    prompt = r._prompt(events, docs, refs)
    key = store.freeze_key(prompt)
    legacy = {
        "facts": [
            {"event_id": events[0].event_id, "documented_use": "no", "quotes": {}}
        ]
    }
    store.save_payload("order_reason", key, legacy)
    old = next(tmp_path.rglob("*.json"))
    before = old.read_bytes()
    client = Reasons()
    out = await r.extract_antimicrobial_reasons(events, docs, refs, client)
    assert (
        out.state == "ready"
        and out.facts[0].documented_use == "yes"
        and client.calls == 1
    )
    assert (
        store.load_payload("order_reason", key) == legacy and old.read_bytes() == before
    )
