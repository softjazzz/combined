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


# ---------- 08-01-03：多版本出院记录的诊断不合并比对 ----------
class _NoCallModel:
    async def generate(self, *args, **kwargs):
        raise AssertionError("本用例不应调用模型")


def _diagnoses(doc, names):
    return tuple({"document_id": doc, "diagnosis_type": "出院诊断", "diagnosis_name": name,
                  "diagnosis_no": index} for index, name in enumerate(names, 1))


def _discharge_rows(first_names, second_names, *, second_time="2026-06-11 09:00:00"):
    names = ("社区获得性肺炎", "2型糖尿病")
    return {
        "discharge_record": (
            {"document_id": "D1", "record_time": "2026-06-10 15:00:00", "record_content": "出院记录"},
            {"document_id": "D2", "record_time": second_time, "record_content": "出院记录（修订）"},
        ),
        "discharge_record_diagnosis": _diagnoses("D1", first_names) + _diagnoses("D2", second_names),
        "mr_diagnosis": tuple({"diagnosis_type": "出院诊断", "diagnosis_name": name, "diagnosis_no": index}
                              for index, name in enumerate(names, 1)),
        "inpat_registration": ({"admission_datetime": "2026-06-01 08:00:00",
                                "discharge_datetime": "2026-06-10 12:00:00", "status": "出院"},),
    }


async def _063_final(rows):
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_reduced_customer_result,
    )
    from app.services.luxian_0609.native_extended_document_execution import (
        execute_luxian_0609_native_extended_document_rules,
    )

    rule = "LX0609-08-01-03"
    session = _session(rule, rows, "extended_document", final=True)
    native = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=session.snapshot,
        evidence_materials=session.materials, llm_client=_NoCallModel(),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions, expected_rule_ids=(rule,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    return finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(native.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )


NAMES = ("社区获得性肺炎", "2型糖尿病")


@pytest.mark.asyncio
async def test_063_identical_versions_are_compared_once():
    final = await _063_final(_discharge_rows(NAMES, NAMES))
    assert final["status"] == "compliant"


@pytest.mark.asyncio
async def test_063_latest_version_is_used():
    # 初写版漏了糖尿病，修订版完整：以修订版为准。
    final = await _063_final(_discharge_rows(NAMES[:1], NAMES))
    assert final["status"] == "compliant"
    # 反过来：修订版漏写，初写完整，以修订版为准判不合规。
    final = await _063_final(_discharge_rows(NAMES, NAMES[:1]))
    assert final["status"] == "non_compliant"


@pytest.mark.asyncio
async def test_063_conflicting_versions_without_unique_latest_is_data_gap():
    final = await _063_final(_discharge_rows(NAMES[:1], NAMES, second_time="2026-06-10 15:00:00"))
    assert final["status"] == "data_gap"
    assert final["customer_display_facts"]["written_gap"] == "version_conflict"


# ---------- 复核补充：同类事件证据归属与版本边界 ----------
class _ScriptedInvasiveModel:
    """plan: 操作日 -> (记录选择函数, 摘录)；未列出的操作日回答 not_documented。"""

    def __init__(self, plan):
        self.plan = plan
        self.record_payloads = []

    async def generate(self, prompt, **kwargs):
        payload = json.loads(prompt.rsplit("INPUT_JSON=", 1)[1])
        if "catalog" in payload:
            catalog_id = next(c["id"] for c in payload["catalog"] if c["name"] == INVASIVE_NAME)
            return _reply({"schema_version": "lx0609-invasive-order-mapping-v2", "matches": [
                {"id": order["id"], "catalog": catalog_id} for order in payload["orders"]
            ]})
        self.record_payloads.append(payload["records"])
        items = []
        for procedure in payload["procedures"]:
            choice = self.plan.get(procedure["operation_date"])
            record = next((r for r in payload["records"] if choice and choice[0](r)), None)
            items.append({"id": procedure["id"], "state": "documented" if record else "not_documented",
                          "record": record["id"] if record else None,
                          "quote": choice[1] if record else None})
        return _reply({"schema_version": "lx0609-invasive-procedure-record-v1", "items": items})


def _two_day_rows(*records):
    rows = _invasive_rows((1, 2), 2, "front")
    rows["daily_course_record"] = tuple(records)
    return rows


def _course(doc, day, hour, text):
    return {"document_id": doc, "record_time": f"2026-06-{day:02d} {hour:02d}:00:00", "record_content": text}


@pytest.mark.asyncio
async def test_075_same_document_from_two_sources_is_one_record():
    rows = _invasive_rows((1, 2), 2, "front")
    rows["senior_course_record"] = rows["daily_course_record"]
    model = _ScriptedInvasiveModel({
        "2026-06-01": (lambda r: True, DONE_TEXT), "2026-06-02": (lambda r: True, DONE_TEXT),
    })
    item = await _extended("LX0609-10-03-01", rows, model, final=True)
    assert [len(records) for records in model.record_payloads] == [1]
    assert item.final_state.value == "data_gap"


@pytest.mark.asyncio
async def test_075_two_documents_both_stating_second_day_do_not_prove_first():
    rows = _two_day_rows(
        _course("D2A", 2, 15, f"2026年6月2日，今日{DONE_TEXT}，操作顺利。"),
        _course("D2B", 2, 16, f"补充今日操作经过：2026年6月2日{DONE_TEXT}，状态平稳。"),
    )
    model = _ScriptedInvasiveModel({
        "2026-06-01": (lambda r: r["time"].endswith("15:00"), DONE_TEXT),
        "2026-06-02": (lambda r: r["time"].endswith("16:00"), DONE_TEXT),
    })
    item = await _extended("LX0609-10-03-01", rows, model, final=True)
    assert item.final_state.value == "data_gap"


@pytest.mark.asyncio
async def test_075_consecutive_days_each_with_own_record_is_compliant():
    rows = _two_day_rows(
        _course("D1", 1, 15, f"今日{DONE_TEXT}，过程顺利。"),
        _course("D2", 2, 15, f"今日再次{DONE_TEXT}，过程顺利。"),
    )
    model = _ScriptedInvasiveModel({
        "2026-06-01": (lambda r: r["time"].startswith("2026-06-01"), DONE_TEXT),
        "2026-06-02": (lambda r: r["time"].startswith("2026-06-02"), DONE_TEXT),
    })
    item = await _extended("LX0609-10-03-01", rows, model, final=True)
    assert item.final_state.value == "compliant"


@pytest.mark.asyncio
async def test_075_one_document_recording_each_dated_occurrence_is_compliant():
    text = f"6月1日{DONE_TEXT}；6月2日再次{DONE_TEXT}，过程顺利。"
    rows = _two_day_rows(_course("D", 2, 15, text))
    model = _ScriptedInvasiveModel({
        "2026-06-01": (lambda r: True, f"6月1日{DONE_TEXT}"),
        "2026-06-02": (lambda r: True, f"6月2日再次{DONE_TEXT}"),
    })
    item = await _extended("LX0609-10-03-01", rows, model, final=True)
    assert item.final_state.value == "compliant"


def test_030_versions_of_first_surgery_do_not_cover_second():
    first = _surgery_record(2, 8)
    revised = {**first, "document_id": "R28-revised", "record_time": "2026-06-02 12:00:00"}
    final = _surgery_presence_final({
        "mr_surgery": [_surgery_master(2, 8), _surgery_master(2, 20, surgeon="乙")],
        "surgery_record": [first, revised],
    })
    assert (final["status"], final["reason_code"]) == ("data_gap", "association_failed")


@pytest.mark.asyncio
async def test_063_latest_version_without_diagnoses_does_not_borrow_older():
    final = await _063_final(_discharge_rows(NAMES, ()))
    assert final["status"] == "data_gap"
    assert final["customer_display_facts"]["written_gap"] == "diagnoses_missing"


@pytest.mark.asyncio
async def test_063_latest_main_flag_change_is_used():
    rows = _discharge_rows(NAMES, NAMES)
    diagnoses = []
    for doc, main in (("D1", NAMES[0]), ("D2", NAMES[1])):
        for row in _diagnoses(doc, NAMES):
            diagnoses.append({**{k: v for k, v in row.items() if k != "diagnosis_no"},
                              "diagnosis_main": "是" if row["diagnosis_name"] == main else "否"})
    rows["discharge_record_diagnosis"] = tuple(diagnoses)
    final = await _063_final(rows)
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["written_main"] == NAMES[1]


# ---------- 第二轮复核：明示日期优先、缺时刻记录与父子身份 ----------
def test_quote_date_requires_matching_year():
    from datetime import date

    from app.services.luxian_0609.extended_document.invasive_procedure_record import (
        _quote_states_date,
    )

    assert _quote_states_date(f"2026年6月1日{DONE_TEXT}", date(2026, 6, 1))
    assert _quote_states_date(f"6月1日{DONE_TEXT}", date(2026, 6, 1))
    assert not _quote_states_date(f"2025年6月1日{DONE_TEXT}", date(2026, 6, 1))
    assert not _quote_states_date(f"6月1日、6月2日{DONE_TEXT}", date(2026, 6, 1))


@pytest.mark.asyncio
@pytest.mark.parametrize("supplement", [
    "补记昨日操作经过：2026年6月1日" + DONE_TEXT,
    "补记昨日操作经过：" + DONE_TEXT,
])
async def test_075_same_day_supplement_of_previous_operation_is_not_current(supplement):
    first = f"2026年6月1日{DONE_TEXT}"
    rows = _two_day_rows(_course("D1", 1, 15, first + "。"), _course("S", 2, 15, supplement + "。"))
    model = _ScriptedInvasiveModel({
        "2026-06-01": (lambda r: r["time"].startswith("2026-06-01"), first),
        "2026-06-02": (lambda r: r["time"].startswith("2026-06-02"), supplement),
    })
    item = await _extended("LX0609-10-03-01", rows, model, final=True)
    assert item.final_state.value == "data_gap"


@pytest.mark.asyncio
async def test_075_previous_year_history_does_not_prove_this_year():
    history = f"2025年6月1日{DONE_TEXT}"
    current = f"2026年6月2日再次{DONE_TEXT}"
    rows = _two_day_rows(_course("H", 2, 15, "既往史：" + history + "。"), _course("D2", 2, 16, current + "。"))
    model = _ScriptedInvasiveModel({
        "2026-06-01": (lambda r: r["time"].endswith("15:00"), history),
        "2026-06-02": (lambda r: r["time"].endswith("16:00"), current),
    })
    item = await _extended("LX0609-10-03-01", rows, model, final=True)
    assert item.final_state.value == "data_gap"


@pytest.mark.parametrize("revision", [
    {"surgery_begin_time": None},
    {"surgery_begin_time": "2026-06-02 09:00:00+08:00"},
], ids=["undated", "inexact_begin_before_second"])
def test_030_revision_of_first_surgery_cannot_cover_second(revision):
    first = {**_surgery_record(2, 8), "surgery_begin_time": "2026-06-02 08:30:00+08:00"}
    revised = {**first, "document_id": "R28-revised", "record_time": "2026-06-02 12:00:00", **revision}
    final = _surgery_presence_final({
        "mr_surgery": [_surgery_master(2, 8), _surgery_master(2, 20, surgeon="乙")],
        "surgery_record": [first, revised],
    })
    assert (final["status"], final["reason_code"]) == ("data_gap", "association_failed")


def test_030_each_surgery_with_own_inexact_record_is_not_association_gap():
    records = [
        {**_surgery_record(2, 8), "surgery_begin_time": "2026-06-02 08:20:00+08:00"},
        {**_surgery_record(2, 20), "surgery_begin_time": "2026-06-02 20:15:00+08:00"},
    ]
    final = _surgery_presence_final({
        "mr_surgery": [_surgery_master(2, 8), _surgery_master(2, 20, surgeon="乙")],
        "surgery_record": records,
    })
    assert final["reason_code"] != "association_failed"


@pytest.mark.asyncio
async def test_063_diagnoses_not_linked_to_any_discharge_version_is_gap():
    rows = _discharge_rows(NAMES, ())
    rows["discharge_record_diagnosis"] = _diagnoses("OTHER", NAMES)
    final = await _063_final(rows)
    assert final["status"] == "data_gap"
    assert final["customer_display_facts"]["written_gap"] == "version_conflict"


@pytest.mark.asyncio
async def test_063_later_discharge_record_without_id_cannot_borrow_older():
    rows = _discharge_rows(NAMES, ())
    rows["discharge_record"] = (
        rows["discharge_record"][0],
        {k: v for k, v in rows["discharge_record"][1].items() if k != "document_id"},
    )
    final = await _063_final(rows)
    assert final["status"] == "data_gap"
    assert final["customer_display_facts"]["written_gap"] == "version_conflict"
