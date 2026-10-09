"""病理记录须属于每次检查，跨事件证据不能互相替代。"""

from copy import deepcopy

import pytest

from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.native_tumor_pathology_execution import execute_luxian_0609_native_tumor_pathology_rules


SAMPLING = "LX0609-06-02-02"
RESULT = "LX0609-06-02-03"


def _rows():
    return {
        "pathology_exam_master": [{"document_id": "master-A", "pathology_exam_id": "A", "specimen_name": "胆囊", "request_datetime": "2026-07-01 09:00:00"}],
        "pathology_exam_report": [{"document_id": "report-A", "pathology_exam_id": "A", "specimen_name": "胆囊", "diagnosis": "慢性胆囊炎", "report_datetime": "2026-07-02 10:00:00"}],
        "surgery_record": [{"document_id": "surgery-A", "record_time": "2026-07-01 10:00:00", "surgery_process": "已切除胆囊，标本送病理检查。"}],
        "daily_course_record": [{"document_id": "course-A", "record_time": "2026-07-02 12:00:00", "record_content": "胆囊病理结果：慢性胆囊炎。"}],
    }


async def _run(rows, rule_id):
    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=key, rows=rows.get(key, []), truncated=False, limit_rows=500)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule_id,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-07-10T00:00:00+08:00", row_reader=reader,
    )
    result = await execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=(rule_id,), wrapper_rules=[], evidence_payload={},
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=None, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
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
    assert result.llm_call_count == result.total_tokens == 0
    return final


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", [SAMPLING, RESULT])
async def test_matching_single_event_remains_compliant(rule_id):
    assert (await _run(_rows(), rule_id))["status"] == "compliant"


@pytest.mark.asyncio
async def test_first_report_record_does_not_cover_second_report():
    rows = _rows()
    rows["pathology_exam_master"].append({"document_id": "master-B", "pathology_exam_id": "B", "specimen_name": "胃", "request_datetime": "2026-07-03 09:00:00"})
    rows["pathology_exam_report"].append({"document_id": "report-B", "pathology_exam_id": "B", "specimen_name": "胃", "diagnosis": "胃腺癌", "report_datetime": "2026-07-04 10:00:00"})
    result = await _run(rows, RESULT)
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "association_failed"


@pytest.mark.asyncio
async def test_record_before_report_cannot_prove_current_result():
    rows = _rows()
    rows["daily_course_record"][0]["record_time"] = "2026-06-01 12:00:00"
    result = await _run(rows, RESULT)
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "association_failed"


@pytest.mark.asyncio
async def test_other_specimen_sampling_cannot_cover_current_event():
    rows = _rows()
    rows["surgery_record"][0]["surgery_process"] = "已切除胃息肉，标本送病理检查。"
    rows["daily_course_record"] = []
    result = await _run(rows, SAMPLING)
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "association_failed"


@pytest.mark.asyncio
async def test_two_reports_with_their_own_records_remain_compliant():
    rows = _rows()
    second = deepcopy(rows["pathology_exam_report"][0])
    second.update(document_id="report-B", pathology_exam_id="B", specimen_name="胃", diagnosis="胃腺癌", report_datetime="2026-07-04 10:00:00")
    rows["pathology_exam_report"].append(second)
    rows["daily_course_record"].append({"document_id": "course-B", "record_time": "2026-07-04 12:00:00", "record_content": "胃病理结果：胃腺癌。"})
    result = await _run(rows, RESULT)
    assert result["status"] == "compliant"
    assert {row["source_document_id"] for row in result["customer_evidence"]} == {"report-A", "report-B", "course-A", "course-B"}


@pytest.mark.asyncio
async def test_repeated_same_specimen_diagnosis_needs_event_identity():
    rows = _rows()
    second = deepcopy(rows["pathology_exam_report"][0])
    second.update(document_id="report-B", pathology_exam_id="B", report_datetime="2026-07-04 10:00:00")
    rows["pathology_exam_report"].append(second)
    rows["daily_course_record"][0]["record_time"] = "2026-07-04 12:00:00"
    result = await _run(rows, RESULT)
    assert result["status"] == "data_gap"


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", [SAMPLING, RESULT])
async def test_submission_time_does_not_replace_missing_record_time(rule_id):
    rows = _rows()
    for source in ("surgery_record", "daily_course_record"):
        for row in rows[source]:
            row.pop("record_time")
            row["submit_datetime"] = "2026-07-05 12:00:00"
    assert (await _run(rows, rule_id))["status"] == "data_gap"


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", [SAMPLING, RESULT])
async def test_conflicting_master_report_specimen_is_not_compliant(rule_id):
    rows = _rows()
    rows["pathology_exam_master"][0]["specimen_name"] = "胃"
    assert (await _run(rows, rule_id))["status"] == "data_gap"


@pytest.mark.asyncio
async def test_specimen_mention_in_other_sentence_does_not_bind_sampling():
    rows = _rows()
    rows["surgery_record"][0]["surgery_process"] = "胆囊检查未见明显异常。已切除胃息肉，标本送病理检查。"
    rows["daily_course_record"] = []
    assert (await _run(rows, SAMPLING))["status"] == "data_gap"


@pytest.mark.asyncio
async def test_sampling_facts_only_name_sources_with_linked_sampling():
    rows = _rows()
    rows["daily_course_record"][0]["record_content"] = "已切除胃息肉，标本送病理检查。"
    result = await _run(rows, SAMPLING)
    assert result["status"] == "compliant"
    assert result["customer_display_facts"]["documented_sources"] == ["surgery_record"]
    assert "course-A" not in {row["source_document_id"] for row in result["customer_evidence"]}


@pytest.mark.asyncio
async def test_explicit_report_numbers_disambiguate_repeated_diagnoses():
    rows = _rows()
    second = deepcopy(rows["pathology_exam_report"][0])
    second.update(document_id="report-B", pathology_exam_id="B", report_datetime="2026-07-04 10:00:00")
    rows["pathology_exam_report"].append(second)
    rows["daily_course_record"][0]["record_content"] = "病理号A。胆囊病理结果：慢性胆囊炎。"
    rows["daily_course_record"].append({"document_id": "course-B", "record_time": "2026-07-04 12:00:00", "record_content": "病理号B。胆囊病理结果：慢性胆囊炎。"})
    assert (await _run(rows, RESULT))["status"] == "compliant"


# 唯一病理事件：资料齐全可核对时，“没有任何取材/结果记录”必须能判为未记录，
# 不能因关联不到文书而一律降为资料不足；任何无法归属的病理表述仍保守处理。
NO_MENTION = ("手术顺利，术后安返病房。", "生命体征平稳，继续观察。")


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", [SAMPLING, RESULT])
async def test_single_event_without_any_record_is_not_documented(rule_id):
    rows = _rows()
    rows["surgery_record"][0]["surgery_process"], rows["daily_course_record"][0]["record_content"] = NO_MENTION
    result = await _run(rows, rule_id)
    assert result["status"] == "non_compliant"
    assert {row["source_document_id"] for row in result["customer_evidence"]} >= {"surgery-A", "course-A"}


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", [SAMPLING, RESULT])
async def test_untimed_target_record_cannot_prove_not_documented(rule_id):
    rows = _rows()
    rows["surgery_record"][0]["surgery_process"], rows["daily_course_record"][0]["record_content"] = NO_MENTION
    rows["daily_course_record"].append({"document_id": "course-untimed", "record_content": "胆囊标本已送病理。"})
    assert (await _run(rows, rule_id))["status"] == "data_gap"


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["拟于明日取材送病理检查。", "追踪病检结果。"])
async def test_unbound_pathology_wording_is_not_treated_as_absence(text):
    rows = _rows()
    rows["surgery_record"][0]["surgery_process"] = text
    rows["daily_course_record"] = []
    assert (await _run(rows, SAMPLING))["status"] == "data_gap"


@pytest.mark.asyncio
async def test_single_event_with_generic_specimen_binds_timed_sampling_record():
    rows = _rows()
    for key in ("pathology_exam_master", "pathology_exam_report"):
        rows[key][0]["specimen_name"] = "组织"
    rows["surgery_record"][0]["surgery_process"] = "术中切取组织标本，已送病理检查。"
    assert (await _run(rows, SAMPLING))["status"] == "compliant"


@pytest.mark.asyncio
async def test_two_events_without_records_stay_unresolved():
    rows = _rows()
    second = deepcopy(rows["pathology_exam_report"][0])
    second.update(document_id="report-B", pathology_exam_id="B", specimen_name="胃", diagnosis="胃腺癌",
                  report_datetime="2026-07-04 10:00:00")
    rows["pathology_exam_report"].append(second)
    rows["surgery_record"][0]["surgery_process"], rows["daily_course_record"][0]["record_content"] = NO_MENTION
    assert (await _run(rows, RESULT))["status"] == "data_gap"