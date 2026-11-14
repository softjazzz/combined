"""P1-R1：通过Provider真实在院冻结日期取材，不手工注入终点行。"""

from datetime import datetime
from luxian_0609_invasive_procedure_test_client import FrozenInvasiveProcedureClient

import pytest

from app.services.luxian_0609.evidence_snapshot_provider import (
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.executor_registry import (
    resolve_legacy_executor_material_source_keys,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from tests.unit.test_engine_blocking_findings import Reasons, drug
from tests.unit.test_engine_remaining_findings import b_run, b_NoModel, pathology_rows


@pytest.fixture(autouse=True)
def isolated_freeze(monkeypatch, tmp_path):
    monkeypatch.setenv("LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR", str(tmp_path))


def running_session(rules, rows, executor, day="2026-06-10", *, final_date_only=False):
    def reader(**kwargs):
        key = kwargs["source_key"]
        assert key != "evaluation_context.horizon"
        return SnapshotSourceRows.create(
            source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50
        )

    frozen = {
        "institute_id": "I",
        "patient_id": "P",
        "visit_id": "V",
        "record_scene": "running",
        "evaluation_horizon": day,
        "evaluation_basis": "task_frozen_date",
        "resolution_status": "resolved",
    }
    if final_date_only:
        frozen.update(
            record_scene="final",
            evaluation_basis="discharge_datetime",
            admission_datetime="2026-05-01 08:00:00",
            discharge_datetime=day,
        )
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=rules,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=day + "T12:00:00+08:00",
        row_reader=reader,
        evaluation_as_of_date=day,
        evaluation_horizon_policy="authoritative_discharge"
        if final_date_only
        else "frozen_task_date",
        evaluation_horizon_snapshot=frozen,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            (executor,), selected_rule_ids=rules
        ),
    )
    horizon = session.materials.rows("evaluation_context.horizon")[0]
    assert horizon["horizon_date"] == day
    if final_date_only:
        assert horizon["time_precision"] == "date"
    else:
        assert "horizon_datetime" not in horizon
    return session


async def extended(rule, rows, *, day="2026-06-10", client=None, final_date_only=False):
    from app.services.luxian_0609.native_extended_document_execution import (
        execute_luxian_0609_native_extended_document_rules,
    )

    session = running_session(
        (rule,), rows, "extended_document", day, final_date_only=final_date_only
    )
    native = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule,),
        decision_rule_ids=(rule,),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        llm_client=client or (FrozenInvasiveProcedureClient(mapping={
            "经皮肝穿刺引流术": "经皮肝穿刺引流术", "脊神经根阻滞术": "脊神经根阻滞术",
        }) if rule == "LX0609-10-03-01" else Reasons()),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions,
        expected_rule_ids=(rule,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    return session, native, reduced


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", ["LX0609-05-01-02", "LX0609-05-01-05"])
@pytest.mark.parametrize("day", ["2026-06-01", "2026-06-10"])
async def test_documented_reason_stays_compliant_with_running_date(rule, day):
    _, _, item = await extended(
        rule,
        {
            "inpat_drug_order": (drug(),),
            "daily_course_record": (
                {
                    "document_id": "D",
                    "record_time": "2026-06-01 11:00:00",
                    "record_content": "考虑肺部感染，予经验性抗感染。",
                },
            ),
        },
        day=day,
    )
    assert item.final_state.value == "compliant"


MISSING_CASES = [
    ("LX0609-05-01-02", {"inpat_drug_order": (drug(),)}),
    ("LX0609-05-01-05", {"inpat_drug_order": (drug(),)}),
    ("LX0609-05-01-06", {"inpat_drug_order": (drug("美罗培南"),)}),
    (
        "LX0609-10-01-01",
        {
            "physician_change_event": (
                {
                    "change_datetime": "2026-06-01 10:00:00",
                    "old_physician_name": "甲",
                    "new_physician_name": "乙",
                },
            ),
            "handoff_record": (
                {
                    "document_id": "H",
                    "shift_time": "2026-06-01 10:00:00",
                    "handoff_doctor": "甲",
                    "record_time": "2026-06-01 09:00:00",
                    "record_content": "交班。",
                },
            ),
        },
    ),
    (
        "LX0609-10-03-01",
        {
            "inpat_nondrug_order": (
                {
                    "order_id": "P75",
                    "record_content": "有创操作已实施。",
                    "surgery_code": "50.9101",
                    "order_name": "经皮肝穿刺引流术",
                    "planned_start_datetime": datetime(2026, 6, 2, 10),
                },
            )
        },
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("rule,rows", MISSING_CASES)
async def test_mature_missing_record_is_not_lost_with_running_date(rule, rows):
    session, native, item = await extended(rule, rows)
    assert item.final_state.value == "non_compliant"
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_reduced_customer_result,
    )
    from test_luxian_0609_death_record_timeliness import saved_roundtrip

    final = finalize_luxian_0609_reduced_customer_result(
        decision=item,
        raw_customer_display_facts=dict(native.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert final["status"] == "non_compliant"
    saved = saved_roundtrip(final)
    assert (saved["status"], saved["reason_code"]) == (
        final["status"],
        final["reason_code"],
    )
    assert saved["customer_display_facts"] == final["customer_display_facts"]
    # 保存合同将逐文书原ID转换为source_ref，保留证据内容、时间及字段定位。
    from app.services.qc_workspace.canonical_result_store import keyed_ref

    original = [*final.get("customer_evidence", []), *final.get("evidence_items", [])]
    if rule == "LX0609-10-03-01":
        # 075现有公开投影没有逐文书片段；验证原空集合未丢失，不冒充可定位证据验收。
        assert not original and saved["evidence"] == []
        assert item.fact_refs and final["customer_display_facts"]["missing_procedures"]
    else:
        assert original and len(saved["evidence"]) == len(original)
    for source, actual in zip(original, saved["evidence"]):
        raw_ref = (
            source.get("source_ref")
            or source.get("document_ref")
            or source.get("fact_ref")
            or source.get("source_document_id")
        )
        expected_ref = (
            raw_ref
            if str(raw_ref).startswith("src_")
            else keyed_ref("src", raw_ref, hmac_key="synthetic-death-test-key")
        )
        assert actual["source_ref"] == expected_ref
        assert {key: value for key, value in actual.items() if key != "source_ref"} == {
            key: value
            for key, value in source.items()
            if key
            not in {
                "source_ref",
                "source_document_id",
                "document_id",
                "fact_ref",
                "document_ref",
            }
        }


def test_running_future_surgery_plan_reaches_not_mature():
    from app.services.luxian_0609.native_execution import (
        execute_luxian_0609_native_rules,
    )

    rule = "LX0609-04-02-02"
    session = running_session(
        (rule,),
        {
            "inpat_nondrug_order": (
                {
                    "order_id": "O",
                    "order_type": "手术",
                    "order_status": "新开",
                    "order_name": "腹腔镜胆囊切除术",
                    "planned_start_datetime": "2026-06-11 08:00:00",
                },
            )
        },
        "surgery_presence",
    )
    native = execute_luxian_0609_native_rules(
        rule_ids=(rule,),
        decision_rule_ids=(rule,),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    item = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions,
        expected_rule_ids=(rule,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    assert (item.final_state.value, item.reason_code) == (
        "not_applicable",
        "evaluation_window_not_mature",
    )


@pytest.mark.asyncio
async def test_running_pathology_has_valid_date_but_no_approved_deadline(monkeypatch):
    from app.services.luxian_0609 import native_tumor_pathology_execution as tumor

    original = tumor._typed_pathology_documentation
    reasons = []

    async def capture(**kwargs):
        result = await original(**kwargs)
        reasons.append(result.reason_code)
        return result

    monkeypatch.setattr(tumor, "_typed_pathology_documentation", capture)
    session = running_session(("LX0609-06-02-03",), pathology_rows(), "tumor_pathology")
    _, item = await b_run(session, b_NoModel())
    assert (item.final_state.value, item.reason_code) == (
        "data_gap",
        "source_readiness_unproven",
    )
    assert reasons == ["pathology_recording_deadline_unconfirmed"]


@pytest.mark.asyncio
@pytest.mark.parametrize("rule,rows", MISSING_CASES)
@pytest.mark.parametrize("offset", [-1, 0])
async def test_running_date_before_or_on_deadline_is_not_definite_defect(
    rule, rows, offset
):
    from datetime import date, timedelta

    deadline = date(2026, 6, 5) if rule == "LX0609-10-03-01" else date(2026, 6, 2)
    _, _, item = await extended(
        rule, rows, day=(deadline + timedelta(days=offset)).isoformat()
    )
    assert (item.final_state.value, item.reason_code) == (
        "not_applicable",
        "evaluation_window_not_mature",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", ["LX0609-05-01-02", "LX0609-05-01-05"])
async def test_date_only_discharge_does_not_override_documented_reason(rule):
    _, _, item = await extended(
        rule,
        {
            "inpat_drug_order": (drug(),),
            "daily_course_record": (
                {
                    "document_id": "D",
                    "record_time": "2026-06-01 11:00:00",
                    "record_content": "考虑肺部感染，予经验性抗感染。",
                },
            ),
        },
        final_date_only=True,
    )
    assert item.final_state.value == "compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_mature_missing_reason_does_not_accuse_other_pending_event(reverse):
    orders = [
        drug(),
        {**drug("左氧氟沙星"), "planned_start_datetime": "2026-06-10 10:00:00"},
    ]
    if reverse:
        orders.reverse()
    _, native, item = await extended(
        "LX0609-05-01-02", {"inpat_drug_order": tuple(orders)}
    )
    assert item.final_state.value == "non_compliant"
    facts = dict(native.customer_display_facts)[item.rule_id]
    assert facts["unmatched_antimicrobials"] == ["头孢曲松"]
    assert facts["action_count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "report_day,expected", [("2026-06-09", "non_compliant"), ("2026-06-10", "data_gap")]
)
async def test_pathology_date_only_discharge_does_not_invent_same_day_order(
    report_day, expected
):
    rows = pathology_rows()
    rows["pathology_exam_report"] = (
        {
            **rows["pathology_exam_report"][0],
            "report_datetime": report_day + " 10:00:00",
        },
    )
    session = running_session(
        ("LX0609-06-02-03",), rows, "tumor_pathology", final_date_only=True
    )
    _, item = await b_run(session, b_NoModel())
    assert item.final_state.value == expected
    assert item.reason_code == (
        "requirement_violated"
        if expected == "non_compliant"
        else "evaluation_window_not_mature"
    )


@pytest.mark.parametrize(
    "clock,error",
    [
        ("2026-06-01 00:00:00", "authoritative_time_conflict"),
        ("not-a-time", "authoritative_time_missing"),
    ],
)
def test_date_precision_cannot_hide_corrupt_clock(clock, error):
    from tests.unit.test_luxian_0609_native_extended_document_execution import _session
    from app.services.luxian_0609.evaluation_horizon import (
        read_frozen_evaluation_horizon,
    )
    from app.services.luxian_0609.native_extended_document_execution import (
        _critical_value_evaluation_horizon,
    )

    rows = (
        {
            "horizon_date": "2026-06-10",
            "horizon_datetime": clock,
            "time_precision": "date",
            "basis": "evaluation_as_of",
        },
    )
    snapshot, materials = _session({"evaluation_context.horizon": rows})
    assert (
        read_frozen_evaluation_horizon(snapshot=snapshot, materials=materials)[2]
        == error
    )
    assert _critical_value_evaluation_horizon(rows, "")[2] == error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rule", ["LX0609-05-01-06", "LX0609-10-03-01", "LX0609-10-01-01"]
)
@pytest.mark.parametrize("reverse", [False, True])
async def test_mixed_pending_event_is_not_published_as_missing(rule, reverse):
    if rule == "LX0609-05-01-06":
        source = "inpat_drug_order"
        events = [
            drug("美罗培南"),
            {**drug("万古霉素"), "planned_start_datetime": "2026-06-09 20:00:00"},
        ]
        key, expected = "unmatched_special_antimicrobials", ["美罗培南"]
    elif rule == "LX0609-10-03-01":
        source = "inpat_nondrug_order"
        events = [
            {
                "order_id": "P1",
                "surgery_code": "50.9101",
                "order_name": "经皮肝穿刺引流术",
                "planned_start_datetime": datetime(2026, 6, 2, 10),
            },
            {
                "order_id": "P2",
                "surgery_code": "03.9102",
                "order_name": "脊神经根阻滞术",
                "planned_start_datetime": datetime(2026, 6, 9, 10),
            },
        ]
        key, expected = "missing_procedures", ["经皮肝穿刺引流术"]
    else:
        source = "physician_change_event"
        events = [
            {
                "change_datetime": "2026-06-01 10:00:00",
                "old_physician_name": "甲",
                "new_physician_name": "乙",
            },
            {
                "change_datetime": "2026-06-09 20:00:00",
                "old_physician_name": "乙",
                "new_physician_name": "丙",
            },
        ]
    if reverse:
        events.reverse()
    rows = {source: tuple(events)}
    if rule == "LX0609-10-01-01":
        rows["handoff_record"] = (
            {
                "document_id": "H1",
                "shift_time": "2026-06-01 10:00:00",
                "handoff_doctor": "甲",
                "record_time": "2026-06-01 09:00:00",
            },
            {
                "document_id": "H2",
                "shift_time": "2026-06-09 20:00:00",
                "handoff_doctor": "乙",
                "record_time": "2026-06-09 19:00:00",
            },
        )
    session, native, item = await extended(rule, rows)
    assert item.final_state.value == "non_compliant"
    facts = dict(native.customer_display_facts)[rule]
    if rule == "LX0609-10-01-01":
        assert [
            (event["change_time"], event["outcome"]) for event in facts["events"]
        ] == [
            ("2026-06-01 10:00:00", "handover_missing"),
            ("2026-06-09 20:00:00", "handover_window_not_mature"),
        ]
    else:
        assert facts[key] == expected
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_reduced_customer_result,
    )
    from test_luxian_0609_death_record_timeliness import saved_roundtrip

    final = finalize_luxian_0609_reduced_customer_result(
        decision=item,
        raw_customer_display_facts=facts,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]
    if rule == "LX0609-10-01-01":
        assert (
            final["customer_display_facts"]["events"][-1]["outcome"]
            == "handover_window_not_mature"
        )
        assert "尚未到期" in final["findings"]
        assert "缺少" not in final["findings"].split("第2次变更", 1)[-1]
    else:
        assert final["customer_display_facts"][key] == expected
        if rule == "LX0609-05-01-06":
            assert "万古霉素" not in final["findings"].split("其中", 1)[-1]
        else:
            assert (
                "脊神经根阻滞术"
                not in final["findings"].split("未找到对应操作记录：", 1)[-1]
            )
    saved = saved_roundtrip(final)
    assert saved["customer_display_facts"] == final["customer_display_facts"]
    assert (saved["status"], saved["reason_code"]) == (
        final["status"],
        final["reason_code"],
    )
    assert saved["findings"] == final["findings"]


def test_handoff_unknown_window_is_not_a_confirmed_missing_event():
    from app.services.luxian_0609.extended_document.physician_handoff import (
        _mature_handoff_outcome,
    )
    from app.services.luxian_0609.continuity_result_mapping import (
        safe_continuity_customer_display_facts,
        continuity_customer_fact_status_is_valid,
    )

    event = dict(
        event_position=1,
        change_time="2026-06-01 10:00:00",
        handoff_time=None,
        handover_time=None,
        handover_interval_seconds=None,
        outcome="handoff_missing",
    )
    facts = dict(
        verification_kind="physician_handoff_multi_event_check",
        change_event_count=2,
        handover_threshold_hours=24,
        events=[
            event,
            {
                **event,
                "event_position": 2,
                "change_time": "2026-06-09 20:00:00",
                "handoff_time": "2026-06-09 19:00:00",
                "outcome": "handover_missing",
            },
        ],
    )
    state, _, updated = _mature_handoff_outcome(
        "non_compliant",
        "requirement_violated",
        facts,
        None,
        "authoritative_time_missing",
    )
    assert (
        state == "non_compliant"
        and updated["events"][1]["outcome"] == "handover_window_unresolved"
    )
    assert facts["events"][1]["outcome"] == "handover_missing"  # 不修改调用方事实。
    safe = safe_continuity_customer_display_facts(
        rule_id="LX0609-10-01-01", raw=updated
    )
    assert safe is not None
    assert continuity_customer_fact_status_is_valid(
        rule_id="LX0609-10-01-01", status=state, safe_facts=safe
    )
    only_pending = {
        **safe,
        "events": [
            {
                **e,
                "handoff_time": e["change_time"],
                "outcome": "handover_window_not_mature",
            }
            for e in safe["events"]
        ],
    }
    assert not continuity_customer_fact_status_is_valid(
        rule_id="LX0609-10-01-01", status="non_compliant", safe_facts=only_pending
    )



# ---- 10-01-01（2026-11-08）：缺变更时间的事件保持未决，不抹掉另一可靠事件的确定缺失 ----
_HANDOFF_E1 = {"event_id": "CHG-1", "change_datetime": "2026-06-01 10:00:00",
               "old_physician_name": "甲", "new_physician_name": "乙"}
_HANDOFF_E2_UNTIMED = {"event_id": "CHG-2", "old_physician_name": "乙", "new_physician_name": "丙"}
_HANDOFF_E3 = {"event_id": "CHG-3", "change_datetime": "2026-06-05 08:00:00",
               "old_physician_name": "丁", "new_physician_name": "戊"}
_HANDOFF_E3_RECORDS = {
    "handoff_record": ({"document_id": "HANDOFF-3", "shift_time": "2026-06-05 08:00:00",
                        "handoff_doctor": "丁", "record_time": "2026-06-05 07:50:00"},),
    "handover_record": ({"document_id": "HANDOVER-3", "shift_time": "2026-06-05 08:00:00",
                         "handover_doctor": "戊", "record_time": "2026-06-05 14:00:00"},),
}


async def _handoff_saved(changes, extra=None):
    import copy
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_reduced_customer_result,
    )
    from test_luxian_0609_death_record_timeliness import saved_roundtrip

    rows = {"physician_change_event": tuple(changes), **(extra or {})}
    before = copy.deepcopy(rows)
    session, native, item = await extended("LX0609-10-01-01", rows)
    assert rows == before  # 不就地修改调用方事实
    final = finalize_luxian_0609_reduced_customer_result(
        decision=item,
        raw_customer_display_facts=dict(native.customer_display_facts).get("LX0609-10-01-01"),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    saved = saved_roundtrip(final)
    assert (saved["status"], saved["reason_code"]) == (final["status"], final["reason_code"]) == (
        item.final_state.value, item.reason_code)
    assert saved["customer_display_facts"] == final["customer_display_facts"]
    return saved


@pytest.mark.asyncio
@pytest.mark.parametrize("order", ["E1_first", "E2_first"])
async def test_handoff_untimed_change_cannot_hide_mature_missing_event(order):
    changes = [_HANDOFF_E1, _HANDOFF_E2_UNTIMED]
    if order == "E2_first":
        changes.reverse()
    saved = await _handoff_saved(changes)
    assert (saved["status"], saved["reason_code"]) == ("non_compliant", "requirement_violated")
    facts = saved["customer_display_facts"]
    # 缺失清单只指向可靠事件 E1，未决的 E2 不被列为缺失、超时或已完成。
    assert facts["change_time"] == "2026-06-01 10:00:00"
    assert "2026-06-01 10:00:00" in saved["findings"]


@pytest.mark.asyncio
async def test_handoff_reliable_missing_event_alone_stays_defect():
    saved = await _handoff_saved([_HANDOFF_E1])
    assert saved["status"] == "non_compliant"


@pytest.mark.asyncio
async def test_handoff_only_untimed_change_stays_data_gap():
    saved = await _handoff_saved([_HANDOFF_E2_UNTIMED])
    assert (saved["status"], saved["reason_code"]) == ("data_gap", "authoritative_time_missing")


@pytest.mark.asyncio
async def test_handoff_completed_event_plus_untimed_change_is_not_upgraded():
    # 唯一可靠事件已按时完成：没有确定缺陷，未决事件不能被写成合规，保持整体资料不足。
    saved = await _handoff_saved([_HANDOFF_E3, _HANDOFF_E2_UNTIMED], _HANDOFF_E3_RECORDS)
    assert (saved["status"], saved["reason_code"]) == ("data_gap", "authoritative_time_missing")


@pytest.mark.asyncio
async def test_handoff_defect_keeps_completed_sibling_and_ignores_untimed():
    saved = await _handoff_saved([_HANDOFF_E1, _HANDOFF_E3, _HANDOFF_E2_UNTIMED], _HANDOFF_E3_RECORDS)
    assert saved["status"] == "non_compliant"
    outcomes = {event["change_time"]: event["outcome"] for event in saved["customer_display_facts"]["events"]}
    assert outcomes["2026-06-05 08:00:00"] == "completed_within_threshold"
    assert outcomes["2026-06-01 10:00:00"] in {"handoff_missing", "handover_missing"}
    assert len(outcomes) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "shift,doctor,expected",
    [
        ("2026-06-05 08:00:00", "戊", "non_compliant"),
        ("2026-06-01 10:00:00", "乙", "data_gap"),
        (None, "戊", "data_gap"),
        ("2026-06-05 08:00:00", "乙", "data_gap"),
        ("2026-06-05 08:00:00", None, "data_gap"),
    ],
)
async def test_handoff_bad_record_isolated_only_with_disjoint_shift_and_identity(
    shift, doctor, expected
):
    saved = await _handoff_saved(
        [
            _HANDOFF_E1,
            {"event_id": "E2", "old_physician_name": "丁", "new_physician_name": "戊"},
        ],
        {
            "handoff_record": (
                {
                    "document_id": "H1",
                    "shift_time": "2026-06-01 10:00:00",
                    "handoff_doctor": "甲",
                    "record_time": "2026-06-01 09:00:00",
                },
            ),
            "handover_record": (
                {
                    "document_id": "HV2",
                    "shift_time": shift,
                    "handover_doctor": doctor,
                    "record_time": None,
                },
            ),
        },
    )
    assert saved["status"] == expected
    facts = saved["customer_display_facts"]
    if expected == "non_compliant":
        assert saved["reason_code"] == "requirement_violated"
        assert facts["change_time"] == "2026-06-01 10:00:00"
        assert facts["handoff_times"] == ["2026-06-01 09:00:00"]
        assert facts["handover_times"] == []
        assert "HV2" not in str(facts)
        assert "2026-06-01 10:00:00" in saved["findings"]
    else:
        assert saved["reason_code"] == "authoritative_time_missing"
