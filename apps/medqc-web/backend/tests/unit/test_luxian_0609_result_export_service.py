from io import BytesIO

from openpyxl import load_workbook

from app.services.luxian_0609_result_export_service import (
    export_filtered_record_results_workbook,
    export_single_record_result_html,
)


def _ready_result():
    return {
        "schema_version": "lx0609-single-record-result-v1",
        "state": "ready",
        "record_ref": "rec_safe_001",
        "job_id": "job-001",
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
        "expected_rule_count": 2,
        "result_rule_count": 2,
        "is_complete": True,
        "items": [
            {
                "rule_id": "LX0609-12-01-02",
                "rule_name": "不合理复制病历",
                "source_document": "病程记录",
                "qc_point": "两次以上病程记录高度相似",
                "status": "non_compliant",
                "conclusion": "发现 3 组病程记录达到判定阈值。",
                "actual": "最高相似度 100%",
                "standard": "判定阈值 70%",
                "suggestion": "请逐组核对并完善记录。",
                "evidence": [
                    {
                        "source_type": "daily_course_record",
                        "source_label": "日常病程记录",
                        "source_ref": "doc_safe_001",
                        "record_time": "2026-07-08 08:35:49",
                        "evidence_excerpt": "术后第1日病程：患者神志清楚，切口敷料干燥。",
                        "excerpt_kind": "字段级依据",
                    }
                ],
                "prompt": "SECRET_PROMPT",
                "raw_response": "SECRET_RESPONSE",
            },
            {
                "rule_id": "LX0609-01-01-01",
                "rule_name": "入院记录及时完成",
                "source_document": "入院记录",
                "qc_point": "入院后24小时内完成",
                "status": "compliant",
                "conclusion": "已在规定时限内完成。",
            },
        ],
    }


def _record():
    return {
        "institute_id": "H-1",
        "patient_id": "P-1",
        "visit_id": "V-1",
        "patient_name": "患者甲",
        "department": "重症医学科（ICU）",
        "doctor": "李医生",
        "admission_date": "2026-07-01",
        "discharge_date": "2026-07-12",
    }


def test_single_record_html_uses_customer_fields_and_hides_internal_payload():
    content = export_single_record_result_html(result=_ready_result(), record=_record())

    assert content.startswith("\ufeff<!doctype html>")
    assert "患者甲" in content
    assert "确定问题 1" in content
    assert "病程记录" in content
    assert "发现 3 组病程记录达到判定阈值" in content
    assert "术后第1日病程：患者神志清楚，切口敷料干燥" in content
    assert "doc_safe_001" not in content
    assert "SECRET_PROMPT" not in content
    assert "SECRET_RESPONSE" not in content
    assert "reason_code" not in content


def test_partial_record_export_retains_saved_results_and_failure_notice():
    result = {**_ready_result(), "execution_status": "partial_failed", "is_complete": False,
              "failed_rule_count": 1, "failed_rule_ids": ["LX0609-01-02-02"]}
    content = export_single_record_result_html(result=result, record=_record())
    assert "本次质控未全部完成" in content
    assert "已保留 2 项有效结果" in content
    assert "1 项执行失败" in content
    assert "LX0609-01-02-02" in content
    assert "确定问题 1" in content


def test_filtered_workbook_contains_summary_and_rule_details_without_internal_fields():
    output = export_filtered_record_results_workbook(
        records=[_record()],
        results={("H-1", "P-1", "V-1"): _ready_result()},
        filters={"scope": "final", "department": "重症医学科（ICU）"},
    )

    workbook = load_workbook(BytesIO(output.getvalue()), read_only=True)
    assert workbook.sheetnames == ["导出说明", "病历汇总", "需处理明细", "全部规则结果"]
    summary_rows = list(workbook["病历汇总"].iter_rows(values_only=True))
    issue_rows = list(workbook["需处理明细"].iter_rows(values_only=True))
    all_rows = list(workbook["全部规则结果"].iter_rows(values_only=True))
    assert summary_rows[1][0] == "患者甲"
    assert summary_rows[1][6] == "需优先复核"
    assert summary_rows[1][7] == 1
    assert issue_rows[1][3] == "LX0609-12-01-02"
    assert len(all_rows) == 3
    flattened = "\n".join(str(value) for row in all_rows for value in row if value is not None)
    assert "术后第1日病程：患者神志清楚，切口敷料干燥" in flattened
    assert "doc_safe_001" not in flattened
    assert "SECRET_PROMPT" not in flattened
    assert "SECRET_RESPONSE" not in flattened
    assert "reason_code" not in flattened


def test_filtered_workbook_escapes_formula_like_customer_text():
    record = _record()
    record["patient_name"] = '=HYPERLINK("https://invalid.example", "患者")'
    result = _ready_result()
    result["items"][0]["conclusion"] = "+1+1"

    output = export_filtered_record_results_workbook(
        records=[record],
        results={("H-1", "P-1", "V-1"): result},
        filters={"scope": "final", "keyword": "@危险公式"},
    )

    workbook = load_workbook(BytesIO(output.getvalue()), read_only=True, data_only=False)
    assert workbook["病历汇总"]["A2"].value.startswith("'=")
    assert workbook["需处理明细"]["H2"].value == "'+1+1"
    assert workbook["导出说明"]["B6"].value == "'@危险公式"


def test_selected_workbook_uses_selected_scope_description_without_technical_filter_row():
    output = export_filtered_record_results_workbook(
        records=[_record()],
        results={("H-1", "P-1", "V-1"): _ready_result()},
        filters={"scope": "final", "export_mode": "selected"},
    )

    workbook = load_workbook(BytesIO(output.getvalue()), read_only=True)
    rows = list(workbook["导出说明"].iter_rows(values_only=True))
    assert ("导出口径", "已勾选病历的最新 Canonical 质控结果") in rows
    assert all(row[0] != "筛选-export_mode" for row in rows)


def test_long_evidence_is_lossless_in_both_workbook_entrypoints():
    from app.services.qc_workspace.export_service import render_customer_safe_workbook
    from app.services.luxian_0609_result_export_service import customer_evidence_summary
    from app.services.luxian_0609.ct_order_course_consistency import validate_ct_display_facts
    facts = {"verification_kind": "ct_order_course_review", "subject": "ct_mri",
        "requirement": "order_course_consistency", "review_scope_complete": True,
        "event_count": 32, "event_results": [], "order_results": []}
    evidence = []
    for i in range(32):
        facts["event_results"].append({"event_position": i+1, "event_status": "compliant",
                                       "issue_kind": "order_course_consistent"})
        facts["order_results"].append({"event_position": i+1, "order_position": 1,
            "status": "compliant", "issue_kind": "order_course_consistent",
            "order_reference_positions": [4*i+1], "course_locations": [{
                "reference_position": 4*i+4, "field_path": "record_content", "start": 0,
                "end": 300, "clause_id": f"C{i+1}", "offset_unit": "unicode_codepoint"}]})
        for k, source in enumerate(("inpat_nondrug_order", "exam_master", "exam_item_report", "daily_course_record"), 1):
            evidence.append({"source_type": source, "evidence_excerpt": "核"*299 + "🩺",
                "decision_reference_positions": [4*i+k]})
    assert validate_ct_display_facts(facts) == facts
    text = customer_evidence_summary(evidence, facts=facts)
    assert len(text) > 32767
    summary = {"operation_ref": "test", "result_count": 1, "issue_records": 0, "status_counts": {"compliant": 1}}
    batch = load_workbook(render_customer_safe_workbook(
        items=[{"is_confirmed_issue": False}], rows=[["rec", "LX0609-06-01-01", "CT", "合规", "", "", "", text]], summary=summary))
    result = _ready_result()
    result["items"] = [{"rule_id": "LX0609-06-01-01", "status": "compliant",
                         "evidence": evidence, "customer_display_facts": facts}]
    filtered = load_workbook(export_filtered_record_results_workbook(
        records=[_record()], results={("H-1", "P-1", "V-1"): result}, filters={}))
    for book, sheet, column in ((batch, "全部明细", 8), (filtered, "全部规则结果", 11)):
        assert "完整内容见长文本" in book[sheet].cell(2, column).value
        parts = [row[4] for row in book["长文本"].iter_rows(min_row=2, values_only=True)
                 if row[0] == sheet and row[1] == 2 and row[2] == column]
        assert "".join(parts) == text
        for i in range(32):
            assert f"检查事件{i+1}/医嘱1" in "".join(parts)
        assert all(len(part.encode("utf-16-le"))//2 <= 32767 for part in parts)


def test_overflow_split_does_not_create_formula_and_preserves_non_bmp():
    from openpyxl import Workbook
    from app.services.qc_workspace.export_service import append_complete_workbook_row
    book = Workbook()
    text = "🩺"*16000 + "=1+1" + "核"*18000
    append_complete_workbook_row(book.active, [text])
    output = BytesIO()
    book.save(output)
    output.seek(0)
    reloaded = load_workbook(output, data_only=False)
    cells = [row[4] for row in reloaded["长文本"].iter_rows(min_row=2)]
    assert "".join(cell.value for cell in cells) == text
    assert all(cell.data_type == "s" for cell in cells)
