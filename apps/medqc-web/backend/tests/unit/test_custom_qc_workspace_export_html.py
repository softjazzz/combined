import csv
import json
from io import BytesIO, StringIO
from typing import Any

import pytest

from openpyxl import load_workbook

import app.services.custom_qc_workspace_service as workspace_module
from app.services.custom_qc_workspace_service import (
    CustomQCWorkspaceService,
    customer_safe_projection_key,
    flatten_customer_safe_result_items,
    project_customer_safe_batch_job,
)


def _service() -> CustomQCWorkspaceService:
    service = object.__new__(CustomQCWorkspaceService)
    service._load_batch_job_canonical_items = lambda *, job: flatten_customer_safe_result_items(
        job,
        hmac_key=customer_safe_projection_key(),
    )
    return service


class _Rows:
    def __init__(self, rows: list[dict[str, Any]]):
        self.rows = rows

    def mappings(self) -> "_Rows":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self.rows


class _ReadSession:
    def __init__(self, rows: list[dict[str, Any]]):
        self.rows = rows

    def execute(self, _statement: Any) -> _Rows:
        return _Rows(self.rows)

    def close(self) -> None:
        return None


def test_customer_safe_batch_job_projects_inflight_rule_progress() -> None:
    projected = project_customer_safe_batch_job(
        {
            "id": "job-progress-1",
            "status": "running",
            "rule_code": "LX0609",
            "rule_name": "泸县0609质控",
            "scope": "all",
            "summary": {
                "total_records": 1,
                "rule_count": 49,
                "progress": {
                    "step_key": "run",
                    "rule_index": 18,
                    "rule_count": 49,
                    "processed_records": 0,
                    "total_records": 1,
                    "max_parallel_records": 1,
                    "active_record_count": 1,
                    "queued_record_count": 0,
                },
            },
            "items": [],
        },
        hmac_key="unit-test-key",
    )

    assert projected["summary"]["progress"] == {
        "step_key": "run",
        "processed_rule_count": 18,
        "rule_count": 49,
        "processed_records": 0,
        "total_records": 1,
        "max_parallel_records": 1,
        "active_record_count": 1,
        "queued_record_count": 0,
    }
    assert projected["summary"]["processed_rule_count"] == 18


def test_export_batch_job_html_reads_only_this_jobs_canonical_envelopes(monkeypatch):
    service = object.__new__(CustomQCWorkspaceService)
    service._record_result_envelope_table = workspace_module._record_result_envelopes_table()
    envelope = {
        "schema_version": "lx0609-record-result-envelope-v1",
        "delivery_mode": "canonical_straight_through",
        "job_id": "job-canonical-child",
        "root_job_id": "job-canonical-only",
        "record_ref": "rec_0123456789abcdef01234567",
        "items": [{
            "rule_id": "LX0609-001",
            "rule_version": "1.0",
            "rule_name": "Canonical 质控点",
            "status": "compliant",
            "result_status": "compliant",
            "is_compliant": True,
            "reason_code": "internal_reason_must_not_render",
            "evidence": [{
                "source_type": "daily_course_record",
                "source_ref": "src_1234567890abcdef12345678",
                "record_time": "2026-07-08 08:35:49",
                "evidence_excerpt": "患者术后第1日精神可，切口无渗血。",
                "excerpt_kind": "字段级依据",
            }],
        }],
    }
    session = _ReadSession([{
        "job_id": "job-canonical-child",
        "root_job_id": "job-canonical-only",
        "created_by": "owner-1",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
        "envelope_json": json.dumps(envelope, ensure_ascii=False),
    }])
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    job = {
        "id": "job-canonical-only",
        "created_by": "owner-1",
        "status": "completed",
        "total_records": 1,
        "filters": {
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "2026-06-09",
            "record_refs": [{
                "institute_id": "inst-1",
                "patient_id": "patient-1",
                "visit_id": "visit-1",
            }],
        },
        "items": [{
            "record_id": "legacy-record-must-not-render",
            "rule_id": "LX0609-999",
            "status": "non_compliant",
        }],
    }

    html = service.export_batch_job_html(job=job)

    assert "LX0609-001" in html
    assert "LX0609-999" not in html
    assert "legacy-record-must-not-render" not in html
    assert "internal_reason_must_not_render" not in html
    assert "患者术后第1日精神可，切口无渗血" in html
    assert "src_1234567890abcdef12345678" not in html
    assert "原因码" not in html
    assert html.count("data-record-group") == 1


def test_batch_html_rejects_incomplete_frozen_record_scope():
    service = object.__new__(CustomQCWorkspaceService)

    with pytest.raises(ValueError, match="冻结病历范围"):
        service._load_batch_job_canonical_items(
            job={
                "id": "job-incomplete-scope",
                "created_by": "owner-1",
                "status": "completed",
                "total_records": 2,
                "filters": {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                    "record_refs": [],
                },
            },
            session_factory=lambda: (_ for _ in ()).throw(
                AssertionError("冻结范围无效时不得查询Envelope")
            ),
        )


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
    assert html.count("data-record-group") == 2
    assert "病历数：2" in html
    assert "结果总数：2" in html
    assert "确定问题病历数：0" in html
    assert "AI判断 1" in html
    assert "数据不足 1" in html
    assert "LX0609-001" in html
    assert "LX0609-002" in html
    assert "发现该质控点对应的明确问题" not in html
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
    assert html.count("data-record-group") == 1
    assert "病历数：1" in html
    assert html.count("rec_") >= 2
    assert "V001" not in html
    assert "张某某" not in html
    assert "LX0609-001" in html
    assert "LX0609-020" in html
    assert "入院记录超时" not in html
    assert "会诊执行记录完整" not in html


def test_export_batch_job_html_safely_reports_empty_result_set():
    service = _service()
    job = {
        "id": "empty-job",
        "status": "completed",
        "filters": {"rule_set_key": "luxian_0609_qc_v1"},
        "items": [],
    }

    html = service.export_batch_job_html(job=job)

    assert html.count("data-record-group") == 0
    assert html.count("data-result-row") == 0
    assert "病历数：0" in html
    assert "结果总数：0" in html
    assert "本次任务没有可导出的质控结果" in html
    assert "empty-job" not in html


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
                "AI判断": "uncertain",
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
                "AI判断": "uncertain",
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
    assert summary_rows["确定问题病历数"] == 0

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
