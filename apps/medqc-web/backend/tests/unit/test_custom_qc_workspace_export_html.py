import csv
from io import BytesIO, StringIO

from openpyxl import load_workbook

from app.services.custom_qc_workspace_service import (
    CustomQCWorkspaceService,
    customer_safe_projection_key,
    project_customer_safe_batch_job,
)


def _service() -> CustomQCWorkspaceService:
    return object.__new__(CustomQCWorkspaceService)


def test_export_batch_job_html_groups_records_and_sanitizes_internal_fields():
    service = _service()
    job = {
        "id": "job-html-1",
        "status": "completed",
        "rule_name": "泸县0609质控点验证 v1",
        "customer_rule_count": 2,
        "execution_rule_count": 3,
        "filters": {
            "rule_set_key": "luxian_0609_qc_v1",
            "selected_rule_ids": ["LX0609-001", "LX0609-002"],
        },
        "summary": {
            "total_records": 2,
            "display_status_counts": {"non_compliant": 1, "data_gap": 1},
            "performance_profile": {
                "tokens_total": 80560,
                "prompt_tokens": 42184,
                "completion_tokens": 6847,
                "unattributed_tokens": 31529,
                "token_breakdown_complete": False,
            },
            "review_report": {
                "review_status": "completed",
                "summary": {"total_findings": 1, "p0": 0, "p1": 1, "p2": 0},
                "findings": [
                    {
                        "severity": "P1",
                        "record_id": "V002",
                        "rule_id": "LX0609-002",
                        "reason": "证据模板：内部调试原因",
                        "customer_message": "首次病程记录时间缺失，建议人工复核。",
                        "suggested_status": "data_gap",
                    }
                ],
            },
        },
        "items": [
            {
                "record_id": "V001",
                "patient_name": "张某某",
                "department": "神经内科",
                "rule_code": "LX0609-001",
                "rule_name": "入院记录：入院后24小时内是否完成",
                "status": "non_compliant",
                "is_compliant": False,
                "document_type": "入院记录",
                "defect_level": "严重缺陷",
                "findings": "入院记录未在入院后24小时内完成。",
                "evidence": "证据模板：时限类；映射执行规则：SC-002；执行证据：入院时间：2026-06-01 08:00；记录时间：2026-06-02 10:00；间隔：26小时",
                "suggestion": "请核对入院记录完成时间。",
                "raw_response": "should-not-export",
                "prompt": "should-not-export",
            },
            {
                "record_id": "V002",
                "patient_name": "李某某",
                "department": "普外科",
                "rule_code": "LX0609-002",
                "rule_name": "首次病程：入院后8小时内无首次病程记录",
                "status": "data_gap",
                "is_compliant": False,
                "findings": "缺少首次病程记录时间，无法自动判定。",
                "missing_sources": ["首次病程记录时间"],
            },
        ],
    }

    html = service.export_batch_job_html(job=job)

    assert html.startswith("\ufeff<!doctype html>")
    assert html.count("data-result-row") == 2
    assert "LX0609-001" in html
    assert "LX0609-002" in html
    assert "发现该质控点对应的明确问题" in html
    assert "当前受控数据不足以形成确定结论" in html
    assert "V001" not in html
    assert "V002" not in html
    assert "张某某" not in html
    assert "李某某" not in html
    assert "2026-06-01 08:00" not in html
    assert "2026-06-02 10:00" not in html
    assert "人工复核" not in html
    assert "人工核对" not in html
    assert "数据不足" in html
    assert "证据模板" not in html
    assert "映射执行规则" not in html
    assert "raw_response" not in html
    assert "prompt" not in html
    assert "should-not-export" not in html
    assert "medical_text" not in html
    assert "record_content" not in html
    assert "embedding" not in html


def test_export_batch_job_html_flattens_parent_child_jobs():
    service = _service()
    job = {
        "id": "parent-job",
        "status": "completed",
        "job_kind": "parent",
        "rule_name": "泸县0609总任务",
        "filters": {"rule_set_key": "luxian_0609_qc_v1"},
        "summary": {"total_records": 1},
        "child_jobs": [
            {
                "id": "child-1",
                "items": [
                    {
                        "record_id": "V001",
                        "patient_name": "张某某",
                        "department": "神经内科",
                        "rule_code": "LX0609-001",
                        "rule_name": "入院记录：入院后24小时内是否完成",
                        "status": "non_compliant",
                        "findings": "入院记录超时。",
                    }
                ],
            },
            {
                "id": "child-2",
                "items": [
                    {
                        "record_id": "V001",
                        "patient_name": "张某某",
                        "department": "神经内科",
                        "rule_code": "LX0609-020",
                        "rule_name": "会诊记录：会诊记录单无请会诊执行记录",
                        "status": "compliant",
                        "findings": "会诊执行记录完整。",
                    }
                ],
            },
        ],
    }

    html = service.export_batch_job_html(job=job)

    assert html.count("data-result-row") == 2
    assert html.count("rec_") >= 2
    assert "V001" not in html
    assert "张某某" not in html
    assert "LX0609-001" in html
    assert "LX0609-020" in html
    assert "入院记录超时" not in html
    assert "会诊执行记录完整" not in html


def test_html_csv_xlsx_share_customer_safe_rows_and_confirmed_issue_semantics():
    service = _service()
    job = {
        "id": "job-safe-export",
        "status": "completed",
        "rule_name": "泸县0609质控点验证",
        "filters": {"rule_set_key": "luxian_0609_qc_v1", "patient_name": "泄漏姓名"},
        "summary": {"issue_records": 3, "filters_raw": {"visit_id": "V-RAW"}},
        "items": [
            {
                "record_id": "R-A",
                "visit_id": "V-A",
                "patient_name": "甲患者",
                "rule_id": "LX0609-001",
                "status": "non_compliant",
                "reason_code": "deadline_exceeded",
                "customer_conclusion": "记录完成时间超过规定时限。",
            },
            {
                "record_id": "R-A",
                "patient_name": "甲患者",
                "rule_id": "LX0609-021",
                "status": "ai_suggested_non_compliant",
                "reason_code": "semantic_low_confidence",
            },
            {
                "record_id": "R-B",
                "patient_name": "乙患者",
                "rule_id": "LX0609-033",
                "status": "data_gap",
                "reason_code": "source_unavailable",
                "findings": "原始发现不得回退",
                "evidence_items": [{"source_type": "consent_form", "source_ref": "raw-row", "quote": "原文"}],
            },
        ],
    }

    html = service.export_batch_job_html(job=job)
    csv_text = service.export_batch_job_csv(job=job).getvalue()
    workbook = load_workbook(BytesIO(service.export_batch_job_workbook(job=job).getvalue()))
    projected_job = project_customer_safe_batch_job(
        job,
        hmac_key=customer_safe_projection_key(),
    )

    assert "技术信息" not in workbook.sheetnames
    all_rows = list(workbook["全部明细"].iter_rows(values_only=True))
    assert [row[1] for row in all_rows[1:]] == [
        "LX0609-001",
        "LX0609-021",
        "LX0609-033",
    ]
    csv_rows = list(csv.reader(StringIO(csv_text)))
    detail_start = csv_rows.index(["全部明细"])
    assert [row[1] for row in csv_rows[detail_start + 2 :]] == [
        "LX0609-001",
        "LX0609-021",
        "LX0609-033",
    ]
    expected_status_reasons = [
        (item["status"], item["reason_code"])
        for item in projected_job["items"]
    ]
    assert [
        (
            {
                "不合规": "non_compliant",
                "AI判断：疑似问题": "ai_suggested_non_compliant",
                "数据不足": "data_gap",
            }[row[3]],
            row[4],
        )
        for row in all_rows[1:]
    ] == expected_status_reasons
    assert [
        (
            {
                "不合规": "non_compliant",
                "AI判断：疑似问题": "ai_suggested_non_compliant",
                "数据不足": "data_gap",
            }[row[3]],
            row[4],
        )
        for row in csv_rows[detail_start + 2 :]
    ] == expected_status_reasons
    assert [row[0] for row in all_rows[1:]] == [
        item["record_ref"] for item in projected_job["items"]
    ]
    assert [row[0] for row in csv_rows[detail_start + 2 :]] == [
        item["record_ref"] for item in projected_job["items"]
    ]
    for rule_id in ("LX0609-001", "LX0609-021", "LX0609-033"):
        assert html.find(rule_id) >= 0
        assert csv_text.find(rule_id) >= 0

    summary_rows = dict(workbook["管理摘要"].iter_rows(min_row=2, values_only=True))
    assert summary_rows["确定问题病历数"] == 1

    combined = html + csv_text
    for sheet in workbook.worksheets:
        combined += "\n".join(
            str(cell)
            for row in sheet.iter_rows(values_only=True)
            for cell in row
            if cell is not None
        )
    for forbidden in (
        "R-A",
        "V-A",
        "甲患者",
        "乙患者",
        "泄漏姓名",
        "V-RAW",
        "原始发现不得回退",
        "原文",
        "filters_raw",
    ):
        assert forbidden not in combined


def test_customer_safe_batch_projection_is_idempotent_and_remains_safe_export():
    service = _service()
    job = {
        "id": "job-safe-idempotent",
        "status": "completed",
        "filters": {
            "rule_set_key": "luxian_0609_qc_v1",
            "selected_rule_ids": ["LX0609-001"],
        },
        "items": [
            {
                "record_id": "R-IDEMPOTENT",
                "rule_id": "LX0609-001",
                "status": "non_compliant",
                "reason_code": "deadline_exceeded",
            }
        ],
    }

    first = project_customer_safe_batch_job(
        job,
        hmac_key=customer_safe_projection_key(),
    )
    second = project_customer_safe_batch_job(
        first,
        hmac_key=customer_safe_projection_key(),
    )

    assert second["rule_set_key"] == "luxian_0609_qc_v1"
    assert second["draft_ids"] == ["LX0609-001"]
    assert second["items"] == first["items"]
    assert "病历引用" in service.export_batch_job_html(job=second)
    assert "R-IDEMPOTENT" not in service.export_batch_job_html(job=second)


def test_non_luxian_export_keeps_legacy_business_columns() -> None:
    service = _service()
    job = {
        "id": "job-sc-legacy",
        "status": "completed",
        "rule_name": "四川通用规则",
        "filters": {"rule_set_key": "sc_content_v1"},
        "summary": {"total_records": 1},
        "items": [
            {
                "record_id": "SC-RECORD-1",
                "patient_name": "通用导出患者",
                "department": "内科",
                "rule_code": "SC-001",
                "rule_name": "通用规则",
                "status": "non_compliant",
                "findings": "通用导出原结论",
            }
        ],
    }

    html = service.export_batch_job_html(job=job)
    csv_text = service.export_batch_job_csv(job=job).getvalue()
    workbook = load_workbook(BytesIO(service.export_batch_job_workbook(job=job).getvalue()))

    assert "SC-RECORD-1" in html
    assert "通用导出患者" in html
    assert "通用导出原结论" in html
    assert "病历号" in csv_text
    assert "患者姓名" in csv_text
    assert "技术信息" in workbook.sheetnames
