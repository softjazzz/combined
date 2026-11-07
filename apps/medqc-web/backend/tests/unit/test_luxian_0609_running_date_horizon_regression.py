"""P1-R1：通过Provider真实在院冻结日期取材，不手工注入终点行。"""

from datetime import datetime

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
        llm_client=client or Reasons(),
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
            "mr_surgery": (
                {
                    "surgery_id": "P75",
                    "record_content": "有创操作已实施。",
                    "surgery_code": "50.9101",
                    "surgery_name": "经皮肝穿刺引流术",
                    "surgery_begin_datetime": datetime(2026, 6, 2, 10),
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
