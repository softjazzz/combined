"""第二轮审计最小反例：正式快照、执行器、归约与Finalizer，不调用模型。"""
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace

import pytest
from luxian_0609_anesthesia_test_facts import ExplicitAnesthesiaFactClient
from luxian_0609_course_body_test_facts import FrozenCourseBodyClient, LEGACY_MANUAL_COURSE_BODY_FACTS
from test_luxian_0609_native_extended_document_execution import _session as extended_session

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_extended_document_execution import (
    execute_luxian_0609_native_extended_document_rules,
)
from app.services.luxian_0609.native_surgery_document_execution import (
    execute_luxian_0609_native_surgery_document_rules,
)
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows


class NoModel:
    async def generate(self, *args, **kwargs):
        raise AssertionError("本组规则禁止模型调用")


async def _final(rule, rows, *, anesthesia_facts=None, course_body_facts=None, course_body_calls=1):
    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key, rows=tuple(rows.get(key, ())),
            truncated=False, limit_rows=50,
        )

    if rule == "LX0609-04-04-02":
        session = build_luxian_0609_evidence_read_session(
            selected_rule_ids=(rule,), institute_id="audit-institute",
            patient_id="audit-patient", visit_id="audit-visit", source_schema=None,
            created_at="2026-07-10T12:00:00", row_reader=reader,
        )
    else:
        # 复用正式typed快照夹具，显式保留065评价时点，避免测试依赖运行当天。
        snapshot, materials = extended_session(rows)
        session = SimpleNamespace(snapshot=snapshot, materials=materials)
    assert anesthesia_facts is None or rule == "LX0609-04-04-02"
    client = NoModel() if anesthesia_facts is None else ExplicitAnesthesiaFactClient(anesthesia_facts)
    if course_body_facts is not None:
        assert rule in {"LX0609-04-05-02", "LX0609-08-02-01"} and anesthesia_facts is None
        client = FrozenCourseBodyClient(course_body_facts)
    kwargs = dict(
        rule_ids=(rule,), decision_rule_ids=(rule,),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        llm_client=client,
    )
    if rule == "LX0609-04-04-02":
        result = await execute_luxian_0609_native_surgery_document_rules(
            **kwargs, wrapper_rules=[], evidence_payload=None,
        )
    else:
        result = await execute_luxian_0609_native_extended_document_rules(**kwargs)
    if course_body_facts is not None:
        assert client.fixture_error is None
        assert result.llm_call_count == len(client.calls) == course_body_calls
        assert result.total_tokens == 15 * course_body_calls
    elif anesthesia_facts is None:
        assert result.llm_call_count == result.total_tokens == 0
    else:
        assert result.llm_call_count == len(client.calls) == 1
        assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (10, 5, 15)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(rule,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced[0],
        raw_customer_display_facts=dict(result.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert final["status"] == reduced[0].final_state.value
    return final


def _visits():
    return {
        "anesthesia_record": [{"document_id": "ane-A", "application_id": "A",
            "anesthesia_method": "全身麻醉",
            "record_content": "麻醉诱导完成，气管插管顺利，术毕苏醒拔管。"}],
        "preane_surveil_record": [{"document_id": "pre-A", "application_id": "A",
            "record_time": "2026-07-01 07:00:00", "anesthetist_sign": "测试医师",
            "record_content": "ASA II级；气道评估正常；禁食禁饮已核对；否认麻醉史；已完成麻醉风险告知。"}],
        "postane_surveil_record": [{"document_id": "post-A", "application_id": "A",
            "record_time": "2026-07-02 08:00:00", "anesthetist_sign": "测试医师",
            "record_content": "神志清醒；呼吸平稳；循环稳定；无麻醉并发症。"}],
    }


@pytest.mark.asyncio
async def test_037_complete_visits_and_valid_negatives_stay_compliant():
    assert (await _final("LX0609-04-04-02", _visits(), anesthesia_facts="round2_complete"))["status"] == "compliant"


@pytest.mark.asyncio
async def test_037_empty_template_labels_are_not_complete():
    rows = _visits()
    rows["preane_surveil_record"][0]["record_content"] = (
        "ASA：；气道评估：；禁食禁饮：；麻醉史：；麻醉风险告知：；"
    )
    rows["postane_surveil_record"][0]["record_content"] = "神志：；呼吸：；循环：；并发症：；"
    final = await _final("LX0609-04-04-02", rows, anesthesia_facts="round2_empty_labels")
    assert final["status"] == "non_compliant"
    assert "已核对" not in final["findings"]


@pytest.mark.asyncio
async def test_037_invalid_record_time_is_not_complete():
    rows = _visits()
    for key in ("preane_surveil_record", "postane_surveil_record"):
        rows[key][0]["record_time"] = "2026-99-99 88:88"
    assert (await _final("LX0609-04-04-02", rows, anesthesia_facts="round2_invalid_time"))["status"] == "non_compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["application_id", "anesthesia_id", "surgery_id"])
async def test_037_different_event_postvisit_cannot_complete_anesthesia(field):
    rows = _visits()
    for row_list in rows.values():
        row = row_list[0]
        row.pop("application_id")
        row[field] = "A"
    rows["postane_surveil_record"][0].update({field: "B", "document_id": "post-B"})
    final = await _final("LX0609-04-04-02", rows)
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "association_failed"


@pytest.mark.asyncio
async def test_037_different_document_ids_without_event_keys_keep_single_event_control():
    rows = _visits()
    for row_list in rows.values():
        row_list[0].pop("application_id")
    assert (await _final("LX0609-04-04-02", rows, anesthesia_facts="round2_without_event_keys"))["status"] == "compliant"


def _surgery():
    return {
        "mr_surgery": [{"document_id": "surgery-A", "surgery_code": "01.2400X013",
            "surgery_name": "硬脑膜外血肿清除术",
            "surgery_begin_datetime": datetime(2026, 7, 1, 8),
            "surgery_end_datetime": datetime(2026, 7, 1, 10)}],
        "evaluation_context.horizon": [{"horizon_date": "2026-07-10", "basis": "evaluation_as_of"}],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("time,expected", [
    (None, "data_gap"), ("not-a-date", "data_gap"),
    ("2026-07-02 09:00:00", "compliant"),
    ("2026-07-06 09:00:00", "non_compliant"),
])
async def test_065_undated_existing_round_is_not_missing(time, expected):
    rows = _surgery()
    rows["senior_course_record"] = [{"document_id": "round-A",
        "document_title": "主任医师查房记录", "record_time": time,
        "record_content": "主任医师查房，伤口愈合良好，继续观察。"}]
    final = await _final("LX0609-04-05-02", rows, course_body_facts={"主任医师查房，伤口愈合良好，继续观察。": ("present", "伤口愈合良好")}, course_body_calls=int(time == "2026-07-02 09:00:00"))
    assert final["status"] == expected
    if expected == "data_gap":
        assert final["reason_code"] == "authoritative_time_missing"
        assert "未查到" not in final["findings"]


@pytest.mark.asyncio
async def test_065_dated_valid_round_is_not_blocked_by_another_undated_record():
    rows = _surgery()
    rows["senior_course_record"] = [
        {"document_id": "round-A", "record_time": "2026-07-02 09:00:00", "record_content": "查房，病情稳定。"},
        {"document_id": "round-B", "record_content": "查房，病情稳定。"},
    ]
    assert (await _final("LX0609-04-05-02", rows, course_body_facts={"查房，病情稳定。": ("present", "病情稳定")}))["status"] == "compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("body,expected", [
    ("医生签名：张医生", "data_gap"),
    ("医师签名：李某 主治医师", "data_gap"),
    ("医生签名：", "data_gap"),
    ("医生签名：张三\n医师签名：李四", "data_gap"),
    ("患者病情稳定，明日出院。", "compliant"),
    ("患者病情稳定，明日出院。\n医生签名：张医生", "compliant"),
])
async def test_067_signature_only_is_not_clinical_course(body, expected):
    rows = {
        "inpat_registration": [{"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"}],
        "discharge_record": [{"document_id": "discharge-A", "discharge_date": "2026-07-03"}],
        "daily_course_record": [{"document_id": "course-A", "record_time": "2026-07-02 09:00:00", "record_content": body}],
    }
    final = await _final("LX0609-08-02-01", deepcopy(rows), course_body_facts={body: LEGACY_MANUAL_COURSE_BODY_FACTS[body]} if isinstance(body, str) and body.strip() else {}, course_body_calls=int(isinstance(body, str) and bool(body.strip())))
    assert final["status"] == expected
    if expected == "data_gap":
        assert final["reason_code"] == "required_field_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("body,expected", [
    ("医生签名：", "data_gap"),
    ("医生签名：张医生", "data_gap"),
    ("医师签名：李某 主治医师", "data_gap"),
    ("", "data_gap"),
    (None, "data_gap"),
    ("病情稳定。", "compliant"),
    ("医生签名:继续观察。", "compliant"),
    ("主任医师查房，病情稳定。\n医生签名：张医生", "compliant"),
])
async def test_065_dated_signature_only_is_not_a_clinical_round(body, expected):
    rows = _surgery()
    rows["senior_course_record"] = [{
        "document_id": "round-body-A", "record_time": "2026-07-02 09:00:00",
        "document_title": "主任医师查房记录", "record_content": body,
    }]
    if body is None:
        rows["senior_course_record"][0].pop("record_content")
    final = await _final("LX0609-04-05-02", rows, course_body_facts={body: LEGACY_MANUAL_COURSE_BODY_FACTS[body]} if isinstance(body, str) and body.strip() else {}, course_body_calls=int(isinstance(body, str) and bool(body.strip())))
    assert final["status"] == expected
    if expected == "data_gap":
        assert final["reason_code"] == "required_field_missing"
        assert "未查到" not in final["findings"]
        assert any(item.get("source_document_id") == "round-body-A"
                   for item in final["customer_evidence"])


@pytest.mark.asyncio
async def test_065_valid_round_is_not_blocked_by_signature_only_row():
    rows = _surgery()
    rows["senior_course_record"] = [
        {"document_id": "round-body-A", "record_time": "2026-07-02 09:00:00",
         "record_content": "医生签名：张医生"},
        {"document_id": "round-body-B", "record_time": "2026-07-02 10:00:00",
         "record_content": "病情稳定。"},
    ]
    assert (await _final("LX0609-04-05-02", rows, course_body_facts={"医生签名：张医生": ("absent", None), "病情稳定。": ("present", "病情稳定")}))["status"] == "compliant"
