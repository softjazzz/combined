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
