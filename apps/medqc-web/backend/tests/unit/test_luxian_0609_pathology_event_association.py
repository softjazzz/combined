"""013/019 病理记录：模型抽取每次检查的取材/结果记录与原文引用，程序核验并判定。

关联语义（标本是否对应、是否算记录结果）由模型抽取并在真实模型上验证；本文件
锁定程序职责：送模范围与时间过滤、引用核验、事件级状态映射、证据坐标。
"""

from copy import deepcopy

import pytest

from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.native_tumor_pathology_execution import execute_luxian_0609_native_tumor_pathology_rules

from luxian_0609_pathology_test_facts import PathologyFactsClient, default_pathology_facts


SAMPLING = "LX0609-06-02-02"
RESULT = "LX0609-06-02-03"


def _rows():
    return {
        "pathology_exam_master": [{"document_id": "master-A", "pathology_exam_id": "A", "specimen_name": "胆囊", "request_datetime": "2026-07-01 09:00:00"}],
        "pathology_exam_report": [{"document_id": "report-A", "pathology_exam_id": "A", "specimen_name": "胆囊", "diagnosis": "慢性胆囊炎", "report_datetime": "2026-07-02 10:00:00"}],
        "surgery_record": [{"document_id": "surgery-A", "record_time": "2026-07-01 10:00:00", "surgery_process": "已切除胆囊，标本送病理检查。"}],
        "daily_course_record": [{"document_id": "course-A", "record_time": "2026-07-02 12:00:00", "record_content": "胆囊病理结果：慢性胆囊炎。"}],
    }


async def _run(rows, rule_id, client=None):
    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=key, rows=rows.get(key, []), truncated=False, limit_rows=500)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule_id,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-07-10T00:00:00+08:00", row_reader=reader,
    )
    client = client if client is not None else PathologyFactsClient()
    result = await execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=(rule_id,), wrapper_rules=[], evidence_payload={},
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=(rule_id,),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(rule_id,), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(result.customer_display_facts).get(rule_id),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    final["_llm_call_count"] = result.llm_call_count
    return final


def _documents(final):
    return {row["source_document_id"] for row in final.get("customer_evidence") or []}


def _scripted(*states):
    """按事件顺序返回指定状态；documented 时沿用默认规则找到的引用。"""

    def script(sampling, events, documents):
        found = default_pathology_facts(sampling, events, documents)
        answers = []
        for event, state, default in zip(events, states, found):
            if state == "documented":
                assert default["state"] == "documented"
                answers.append(default)
            else:
                answers.append({"event": event["event"], "state": state, "document": None, "quote": None})
        return answers

    return PathologyFactsClient(script)


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id,cited", [(SAMPLING, "surgery-A"), (RESULT, "course-A")])
async def test_documented_single_event_is_compliant_with_cited_document(rule_id, cited):
    final = await _run(_rows(), rule_id)
    assert (final["status"], final["_llm_call_count"]) == ("compliant", 1)
    assert cited in _documents(final)


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", [SAMPLING, RESULT])
async def test_not_documented_is_non_compliant_with_checked_documents(rule_id):
    final = await _run(_rows(), rule_id, _scripted("not_documented"))
    assert final["status"] == "non_compliant"
    # 019 有手术记录时只核对手术记录；013 核对报告之后的记录。
    expected = {"surgery-A"} if rule_id == SAMPLING else {"course-A"}
    assert _documents(final) >= expected
    if rule_id == SAMPLING:
        assert "course-A" not in _documents(final)


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", [SAMPLING, RESULT])
async def test_unknown_attribution_is_association_gap(rule_id):
    final = await _run(_rows(), rule_id, _scripted("unknown"))
    assert (final["status"], final["reason_code"]) == ("data_gap", "association_failed")


@pytest.mark.asyncio
async def test_paraphrased_result_and_specimen_reach_model_without_verbatim_matching():
    """标本名/诊断不再逐字匹配：病理单“（胃窦）组织”“（胃窦）中分化腺癌”，病程转述也交模型判断。"""
    rows = _rows()
    for key in ("pathology_exam_master", "pathology_exam_report"):
        rows[key][0]["specimen_name"] = "（胃窦）组织"
    rows["pathology_exam_report"][0]["diagnosis"] = "（胃窦）中分化腺癌"
    rows["surgery_record"][0]["surgery_process"] = "行远端胃切除术，切除标本送病理检查。"
    rows["daily_course_record"][0]["record_content"] = "术后病理回报胃窦中分化腺癌，拟下周化疗。"
    for rule_id in (SAMPLING, RESULT):
        assert (await _run(rows, rule_id))["status"] == "compliant"


@pytest.mark.asyncio
async def test_result_rule_only_sends_records_after_report_time():
    rows = _rows()
    client = PathologyFactsClient()
    final = await _run(rows, RESULT, client)
    prompt = client.prompts[0]
    assert "胆囊病理结果" in prompt
    assert "已切除胆囊" not in prompt  # 手术记录早于报告，不能证明记录了本次结果
    assert final["status"] == "compliant"


@pytest.mark.asyncio
async def test_result_with_every_target_before_report_is_not_documented_without_model():
    rows = _rows()
    rows["daily_course_record"][0]["record_time"] = "2026-07-01 12:00:00"
    final = await _run(rows, RESULT)
    assert (final["status"], final["_llm_call_count"]) == ("non_compliant", 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", [SAMPLING, RESULT])
async def test_untimed_record_blocks_result_absence_but_not_sampling_review(rule_id):
    rows = _rows()
    rows["daily_course_record"].append({"document_id": "course-untimed", "record_content": "胆囊标本已送病理。"})
    final = await _run(rows, rule_id, _scripted("not_documented"))
    # 013 无时间文书无法核对先后，不能据此断言未记录；019 取材无时间要求，照常送模。
    assert final["status"] == ("non_compliant" if rule_id == SAMPLING else "data_gap")


@pytest.mark.asyncio
async def test_two_reports_each_need_their_own_record():
    rows = _rows()
    second = deepcopy(rows["pathology_exam_report"][0])
    second.update(document_id="report-B", pathology_exam_id="B", specimen_name="胃", diagnosis="胃腺癌", report_datetime="2026-07-04 10:00:00")
    rows["pathology_exam_report"].append(second)
    rows["pathology_exam_master"].append({"document_id": "master-B", "pathology_exam_id": "B", "specimen_name": "胃", "request_datetime": "2026-07-03 09:00:00"})
    rows["daily_course_record"].append({"document_id": "course-B", "record_time": "2026-07-04 12:00:00", "record_content": "胃病理结果：胃腺癌。"})
    final = await _run(rows, RESULT)
    assert final["status"] == "compliant"
    assert _documents(final) >= {"report-A", "report-B", "course-A", "course-B"}
    partial = await _run(rows, RESULT, _scripted("documented", "not_documented"))
    assert partial["status"] == "non_compliant"


@pytest.mark.asyncio
async def test_citation_before_its_own_report_cannot_prove_that_result():
    """第二份报告晚于被引用的病程时，该引用不能证明第二份结果已记录。"""
    rows = _rows()
    second = deepcopy(rows["pathology_exam_report"][0])
    second.update(document_id="report-B", pathology_exam_id="B", report_datetime="2026-07-05 10:00:00")
    rows["pathology_exam_report"].append(second)
    rows["pathology_exam_master"].append({"document_id": "master-B", "pathology_exam_id": "B", "specimen_name": "胆囊", "request_datetime": "2026-07-04 09:00:00"})
    final = await _run(rows, RESULT)
    assert (final["status"], final["reason_code"]) == ("data_gap", "association_failed")


@pytest.mark.asyncio
async def test_ungrounded_quote_fails_whole_extraction():
    def script(sampling, events, documents):
        return [{"event": events[0]["event"], "state": "documented", "document": documents[0]["document"],
                 "quote": "病程中并不存在的这句话。"}]

    final = await _run(_rows(), SAMPLING, PathologyFactsClient(script))
    assert (final["status"], final["reason_code"]) == ("technical_error", "model_invalid_output")


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", [SAMPLING, RESULT])
async def test_duplicate_master_for_one_report_is_association_gap_without_model(rule_id):
    rows = _rows()
    rows["pathology_exam_master"].append(dict(rows["pathology_exam_master"][0], document_id="master-dup"))
    final = await _run(rows, rule_id)
    assert (final["status"], final["_llm_call_count"]) == ("data_gap", 0)


@pytest.mark.asyncio
async def test_sampling_request_without_report_cannot_be_covered_by_other_event():
    rows = _rows()
    rows["pathology_exam_master"].append({"document_id": "master-B", "pathology_exam_id": "B", "specimen_name": "胃", "request_datetime": "2026-07-03 09:00:00"})
    final = await _run(rows, SAMPLING)
    assert (final["status"], final["_llm_call_count"]) == ("data_gap", 0)


@pytest.mark.asyncio
async def test_sampling_facts_name_only_sources_the_model_cited():
    rows = _rows()
    rows["daily_course_record"][0]["record_content"] = "患者一般情况可。"
    final = await _run(rows, SAMPLING)
    assert final["status"] == "compliant"
    assert final["customer_display_facts"]["documented_sources"] == ["surgery_record"]
    assert "course-A" not in _documents(final)


@pytest.mark.asyncio
async def test_missing_model_client_is_technical_failure_not_a_judgement():
    final = await _run(_rows(), RESULT, client=object())
    assert (final["status"], final["reason_code"]) == ("technical_error", "model_transport_error")


@pytest.mark.asyncio
async def test_019_with_surgery_record_ignores_sampling_written_only_in_course():
    """院方口径：有手术记录时取材须写在手术记录中，病程里写了送检不算。"""
    rows = _rows()
    rows["surgery_record"][0]["surgery_process"] = "已切除胆囊，手术顺利。"
    rows["daily_course_record"][0]["record_content"] = "术中切除胆囊标本已送病理检查。"
    client = PathologyFactsClient()
    final = await _run(rows, SAMPLING, client)
    assert final["status"] == "non_compliant"
    assert "已送病理检查" not in client.prompts[0]
    assert final["customer_display_facts"]["checked_target_sources"] == [
        {"source": "surgery_record", "state": "present"},
    ]
    assert "已核对手术记录，均未找到取材情况记录" in final["findings"]


@pytest.mark.asyncio
@pytest.mark.parametrize("course,expected", [
    ("胃镜下于胃窦取活检组织4块送病理检查。", "compliant"),
    ("胃镜检查顺利，患者无不适。", "non_compliant"),
])
async def test_019_without_surgery_record_checks_daily_course(course, expected):
    """院方口径：本次无手术记录（内镜、穿刺等活检）时核对日常病程。"""
    rows = _rows()
    rows["surgery_record"] = []
    rows["daily_course_record"][0]["record_content"] = course
    rows["daily_course_record"][0]["record_time"] = "2026-07-01 12:00:00"
    final = await _run(rows, SAMPLING)
    assert final["status"] == expected
    assert final["customer_display_facts"]["checked_target_sources"] == [
        {"source": "surgery_record", "state": "empty"},
        {"source": "daily_course_record", "state": "present"},
    ]
