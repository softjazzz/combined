"""根因C：多次同类事件不能合并，也不能互相借用证据（串账）。"""

import json
from datetime import datetime

import pytest

from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import (
    resolve_legacy_executor_material_source_keys,
)
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows


@pytest.fixture(autouse=True)
def isolated_freeze(monkeypatch, tmp_path):
    for key in (
        "LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR", "LUXIAN_0609_OPINION_FREEZE_DIR",
        "LUXIAN_0609_CONSULTATION_RESPONSE_FREEZE_DIR", "LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR",
    ):
        monkeypatch.setenv(key, str(tmp_path))


def _session(rule, rows, executor, *, final=False):
    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50
        )

    frozen = {
        "institute_id": "I", "patient_id": "P", "visit_id": "V", "record_scene": "running",
        "evaluation_horizon": "2026-06-10", "evaluation_basis": "task_frozen_date",
        "resolution_status": "resolved",
    }
    if final:
        frozen.update(
            record_scene="final", evaluation_basis="discharge_datetime",
            admission_datetime="2026-05-01 08:00:00", discharge_datetime="2026-06-10 12:00:00",
        )
    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-06-10T23:00:00+08:00", row_reader=reader,
        evaluation_as_of_date="2026-06-10",
        evaluation_horizon_policy="authoritative_discharge" if final else "frozen_task_date",
        evaluation_horizon_snapshot=frozen,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            (executor,), selected_rule_ids=(rule,)
        ),
    )


def _reply(obj):
    return {"choices": [{"finish_reason": "stop",
                         "message": {"content": json.dumps(obj, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


async def _extended(rule, rows, client, *, final=False):
    from app.services.luxian_0609.native_extended_document_execution import (
        execute_luxian_0609_native_extended_document_rules,
    )

    session = _session(rule, rows, "extended_document", final=final)
    native = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=session.snapshot,
        evidence_materials=session.materials, llm_client=client,
    )
    return bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions, expected_rule_ids=(rule,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]


# ---------- 10-03-01：同一操作不同日期各做一次 ----------
INVASIVE_NAME = "经皮肝穿刺引流术"
INVASIVE_CODE = "50.9101"
DONE_TEXT = "已行经皮肝穿刺引流术"


class _LenientInvasiveModel:
    """只要记录不早于操作日就引用（不看3天上界），用于验证程序侧逐次绑定。"""

    def __init__(self):
        self.procedure_counts = []

    async def generate(self, prompt, **kwargs):
        payload = json.loads(prompt.rsplit("INPUT_JSON=", 1)[1])
        if "catalog" in payload:
            catalog_id = next(c["id"] for c in payload["catalog"] if c["name"] == INVASIVE_NAME)
            return _reply({"schema_version": "lx0609-invasive-order-mapping-v2", "matches": [
                {"id": order["id"], "catalog": catalog_id}
                for order in payload["orders"] if "肝穿刺引流" in order["name"]
            ]})
        self.procedure_counts.append(len(payload["procedures"]))
        items = []
        for procedure in payload["procedures"]:
            hit = next((record for record in payload["records"]
                        if DONE_TEXT in record["text"]
                        and record["time"][:10] >= procedure["operation_date"]), None)
            items.append({"id": procedure["id"], "state": "documented" if hit else "not_documented",
                          "record": hit["id"] if hit else None,
                          "quote": DONE_TEXT if hit else None})
        return _reply({"schema_version": "lx0609-invasive-procedure-record-v1", "items": items})


def _invasive_rows(op_days, documented_day, source):
    rows = {"daily_course_record": ({
        "document_id": "D", "record_time": f"2026-06-{documented_day:02d} 15:00:00",
        "record_content": f"今日{DONE_TEXT}，过程顺利。",
    },)}
    if source == "front":
        rows["mr_surgery"] = tuple(
            {"surgery_id": f"S{day}", "surgery_code": INVASIVE_CODE, "surgery_name": INVASIVE_NAME,
             "surgery_begin_datetime": datetime(2026, 6, day, 10)}
            for day in op_days
        )
    else:
        rows["inpat_nondrug_order"] = tuple(
            {"order_id": f"O{day}", "order_name": INVASIVE_NAME, "order_type": "治疗",
             "order_status": "已执行", "planned_start_datetime": f"2026-06-{day:02d} 10:00:00"}
            for day in op_days
        )
    return rows


@pytest.mark.asyncio
@pytest.mark.parametrize("source,final", [("orders", False), ("front", True)])
@pytest.mark.parametrize("documented_day", [1, 6])
async def test_075_same_code_on_two_dates_is_checked_per_occurrence(source, final, documented_day):
    model = _LenientInvasiveModel()
    item = await _extended(
        "LX0609-10-03-01", _invasive_rows((1, 6), documented_day, source), model, final=final,
    )
    assert model.procedure_counts == [2]
    assert (item.final_state.value, item.reason_code) == ("non_compliant", "required_document_missing")


@pytest.mark.asyncio
async def test_075_record_of_later_occurrence_does_not_prove_earlier_one():
    item = await _extended(
        "LX0609-10-03-01", _invasive_rows((1, 3), 3, "front"), _LenientInvasiveModel(), final=True,
    )
    assert item.final_state.value != "compliant"


@pytest.mark.asyncio
async def test_075_pending_second_occurrence_is_not_compliant():
    item = await _extended(
        "LX0609-10-03-01", _invasive_rows((1, 9), 1, "orders"), _LenientInvasiveModel(),
    )
    assert (item.final_state.value, item.reason_code) == ("not_applicable", "evaluation_window_not_mature")


@pytest.mark.asyncio
async def test_075_each_occurrence_documented_is_compliant():
    rows = _invasive_rows((1, 6), 1, "orders")
    rows["daily_course_record"] = (
        *rows["daily_course_record"],
        {"document_id": "D6", "record_time": "2026-06-06 15:00:00",
         "record_content": f"今日再次{DONE_TEXT}。"},
    )
    item = await _extended("LX0609-10-03-01", rows, _LenientInvasiveModel())
    assert item.final_state.value == "compliant"


# ---------- 04-02-02：同日多台手术只有一份手术记录 ----------
SURGERY_NAME = "腹腔镜下阑尾切除术"


def _surgery_master(day, hour=8, *, surgeon="甲", name=SURGERY_NAME, code="47.0101"):
    return {"surgery_name": name, "surgery_code": code, "surgeon": surgeon, "main_surgery_sign": "",
            "surgery_begin_datetime": datetime(2026, 6, day, hour),
            "surgery_end_datetime": datetime(2026, 6, day, hour + 2),
            "surgical_level": "二级", "surgical_incision_level": "II", "surgial_incision_level": "II"}


def _surgery_record(day, hour=8):
    return {"document_id": f"R{day}{hour}", "surgery_name": SURGERY_NAME, "surgeon": "甲",
            "surgeon_sign": "甲",
            "surgery_begin_time": f"2026-06-{day:02d} {hour:02d}:00:00+08:00",
            "surgery_end_time": f"2026-06-{day:02d} {hour + 2:02d}:00:00+08:00",
            "record_time": f"2026-06-{day:02d} {hour + 3:02d}:00:00",
            "surgery_process": "手术经过：顺利。", "record_content": "手术经过：顺利。"}


def _surgery_presence_final(rows):
    from app.services.luxian_0609 import native_execution
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_reduced_customer_result,
    )

    rule = "LX0609-04-02-02"
    session = _session(rule, rows, "surgery_presence", final=True)
    native = native_execution.execute_luxian_0609_native_rules(
        rule_ids=(rule,), visit_id="V", institute_id="I", patient_id="P", source_schema=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=(rule,),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions, expected_rule_ids=(rule,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    return finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(native.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_030_same_day_two_surgeries_one_record_is_not_compliant(reverse):
    from tests.unit.test_luxian_0609_death_record_timeliness import saved_roundtrip

    masters = [_surgery_master(2, 8), _surgery_master(2, 20, surgeon="乙")]
    final = _surgery_presence_final({
        "mr_surgery": masters[::-1] if reverse else masters,
        "surgery_record": [_surgery_record(2, 8)],
    })
    assert (final["status"], final["reason_code"]) == ("data_gap", "association_failed")
    saved = saved_roundtrip(final)
    assert (saved["status"], saved["reason_code"]) == ("data_gap", "association_failed")


def test_030_split_rows_of_one_surgery_share_one_record():
    final = _surgery_presence_final({
        "mr_surgery": [_surgery_master(2), _surgery_master(2, name="腹腔镜下肠粘连松解术", code="54.5101")],
        "surgery_record": [_surgery_record(2, 8)],
    })
    assert final["status"] == "compliant"


def test_030_same_day_two_surgeries_two_records_is_compliant():
    final = _surgery_presence_final({
        "mr_surgery": [_surgery_master(2, 8), _surgery_master(2, 20, surgeon="乙")],
        "surgery_record": [_surgery_record(2, 8), _surgery_record(2, 20)],
    })
    assert final["status"] == "compliant"
