import csv
import json
from copy import deepcopy
from io import BytesIO, StringIO
from typing import Any

import pytest

from openpyxl import load_workbook

import app.services.custom_qc_workspace_service as workspace_module
from app.services.luxian_0609.consultation_customer_projection import (
    safe_consultation_customer_display_facts,
)
from app.services.custom_qc_workspace_service import (
    CustomQCWorkspaceService,
    customer_safe_projection_key,
    flatten_customer_safe_result_items,
    project_customer_safe_batch_job,
)


def _service() -> CustomQCWorkspaceService:
    service = object.__new__(CustomQCWorkspaceService)
    service._load_batch_job_canonical_items = lambda *, job, allow_partial=False: flatten_customer_safe_result_items(
        job,
        hmac_key=customer_safe_projection_key(),
    )
    return service


def _failed_criterion() -> list[dict[str, str]]:
    return [
        {
            "criterion_id": "requirement_check",
            "kind": "semantic_relation",
            "status": "failed",
            "reason_code": "requirement_violated",
        }
    ]


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
            "schema_version": "lx0609-customer-result-v2",
            "rule_id": "LX0609-03-01-03",
            "rule_version": "1.0",
            "rule_name": "会诊记录单会诊意见是否明确",
            "status": "non_compliant",
            "result_status": "non_compliant",
            "is_compliant": False,
            "reason_code": "requirement_violated",
            "suggestion": "PRIVATE_PATIENT_NAME 任意上游建议不得直接导出",
            "customer_display_facts": {
                "verification_kind": "consultation_opinion_quality_check",
                "episode_count": 2,
                "document_count": 2,
                "semantic_state": "mixed",
                "checked_requirement": "给出针对当前病情的明确诊疗意见",
                "source_document_ids": ["CONSULT-1", "CONSULT-2"],
                "episode_results": [
                    {
                        "episode_index": 1,
                        "semantic_state": "clear",
                        "source_document_id": "CONSULT-1",
                        "record_time": "2026-07-20 01:00:00",
                        "document_title": "会诊记录单",
                    },
                    {
                        "episode_index": 2,
                        "semantic_state": "vague",
                        "source_document_id": "CONSULT-2",
                        "record_time": "2026-07-20 02:00:00",
                        "document_title": "会诊记录单",
                    },
                ],
            },
            "evidence": [{
                "source_type": "daily_course_record",
                "source_ref": "src_1234567890abcdef12345678",
                "record_time": "2026-07-08 08:35:49",
                "evidence_excerpt": "患者术后第1日精神可，切口无渗血。",
                "excerpt_kind": "字段级依据",
            }],
        }, {
            "schema_version": "lx0609-customer-result-v2",
            "rule_id": "LX0609-06-01-04",
            "rule_version": "1.0",
            "rule_name": "CT/MRI 报告后24小时内是否记录病程",
            "status": "data_gap",
            "result_status": "data_gap",
            "is_compliant": None,
            "reason_code": "authoritative_report_time_missing",
            "findings": "PRIVATE_FREE_TEXT 不得直接导出",
            "suggestion": "PRIVATE_FREE_SUGGESTION 不得直接导出",
        }],
    }
    # Envelope 保存的是 Finalizer 已发布的公开形态；原始 source_document_id
    # 只能作为执行器输入，不能伪装成已落库的 Canonical 客户事实。
    consultation_item = envelope["items"][0]
    public_facts = safe_consultation_customer_display_facts(
        rule_id=consultation_item["rule_id"],
        raw=consultation_item["customer_display_facts"],
    )
    assert public_facts is not None
    consultation_item["customer_display_facts"] = public_facts
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
    csv_text = service.export_batch_job_csv(job=job).getvalue()
    workbook = load_workbook(service.export_batch_job_workbook(job=job), read_only=True)
    workbook_text = "\n".join(
        str(value)
        for sheet in workbook.worksheets
        for row in sheet.iter_rows(values_only=True)
        for value in row
        if value is not None
    )

    assert "LX0609-03-01-03" in html
    assert "LX0609-999" not in html
    assert "legacy-record-must-not-render" not in html
    assert "requirement_violated" not in html
    assert "患者术后第1日精神可，切口无渗血" in html
    assert "src_1234567890abcdef12345678" not in html
    assert "原因码" not in html
    assert "病历引用" not in html
    assert "rec_0123456789abcdef01234567" not in html
    # 旧式测试数据不具备正式 Renderer 生成的结论；导出不能借内部文书 ID
    # 重建定位，也不能保留未经过公开合同的自由文本建议。
    assert "CONSULT-1" not in html
    assert "CONSULT-2" not in html
    assert "PRIVATE_PATIENT_NAME" not in html
    assert "任意上游建议不得直接导出" not in html
    assert "CT/MRI 报告缺少权威报告时间" in html
    assert "核对 CT/MRI 报告时间" in html
    assert "PRIVATE_FREE_TEXT" not in html
    assert "PRIVATE_FREE_SUGGESTION" not in html
    assert html.count("data-record-group") == 1
    for exported in (csv_text, workbook_text):
        assert "LX0609-03-01-03" in exported
        assert "LX0609-06-01-04" in exported
        assert "LX0609-999" not in exported
        assert "legacy-record-must-not-render" not in exported
        assert "PRIVATE_PATIENT_NAME" not in exported
        assert "PRIVATE_FREE_SUGGESTION" not in exported

    partial_job = {
        **job,
        "status": "failed",
        "success_count": 1,
        "summary": {"execution_status": "partial_failed"},
    }
    assert "LX0609-03-01-03" in service.export_batch_job_html(job=partial_job)
    assert "LX0609-03-01-03" in service.export_batch_job_csv(job=partial_job).getvalue()
    partial_workbook = load_workbook(service.export_batch_job_workbook(job=partial_job), read_only=True)
    assert any(
        value == "LX0609-03-01-03"
        for sheet in partial_workbook.worksheets
        for row in sheet.iter_rows(values_only=True)
        for value in row
    )

    damaged = deepcopy(envelope)
    damaged["items"][0]["customer_display_facts"]["source_document_ids"] = ["CONSULT-1"]
    session.rows[0]["envelope_json"] = json.dumps(damaged, ensure_ascii=False)
    for export in (
        service.export_batch_job_html,
        service.export_batch_job_csv,
        service.export_batch_job_workbook,
    ):
        with pytest.raises(ValueError, match="解释合同不完整"):
            export(job=job)


def test_batch_html_rejects_incomplete_frozen_record_scope():
    service = object.__new__(CustomQCWorkspaceService)
    job = {
        "id": "job-incomplete-scope",
        "created_by": "owner-1",
        "status": "completed",
        "total_records": 2,
        "filters": {
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "2026-06-09",
            "record_refs": [],
        },
        "items": [{"rule_id": "LX0609-01-01-01", "status": "compliant"}],
    }
    with pytest.raises(ValueError, match="冻结病历范围"):
        service._load_batch_job_canonical_items(
            job=job,
            session_factory=lambda: (_ for _ in ()).throw(
                AssertionError("冻结范围无效时不得查询Envelope")
            ),
        )
    for export in (
        service.export_batch_job_html,
        service.export_batch_job_csv,
        service.export_batch_job_workbook,
    ):
        with pytest.raises(ValueError, match="冻结病历范围"):
            export(job=job)


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
            "selected_rule_ids": ["LX0609-01-01-01", "LX0609-01-02-01"],
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
                        "rule_id": "LX0609-01-02-01",
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
                "rule_code": "LX0609-01-01-01",
                "rule_name": "入院记录：入院后24小时内是否完成",
                "status": "non_compliant",
                "is_compliant": False,
                "criterion_results": _failed_criterion(),
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
                "rule_code": "LX0609-01-02-01",
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
    assert "确定问题病历数：1" in html
    assert "不合规 1" in html
    assert "数据不足 1" in html
    assert 'class="status-pill status-non-compliant"' in html
    assert 'class="status-pill status-data-gap"' in html
    assert "LX0609-01-01-01" in html
    assert "LX0609-01-02-01" in html
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
                        "rule_code": "LX0609-01-01-01",
                        "rule_name": "入院记录：入院后24小时内是否完成",
                        "status": "non_compliant",
                        "criterion_results": _failed_criterion(),
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
                        "rule_code": "LX0609-03-01-01",
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
    assert "病历引用" not in html
    assert "rec_" not in html
    assert "V001" not in html
    assert "张某某" not in html
    assert "LX0609-01-01-01" in html
    assert "LX0609-03-01-01" in html
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
                "rule_id": "LX0609-01-01-01",
                "status": "non_compliant",
                "reason_code": "deadline_exceeded",
                "criterion_results": _failed_criterion(),
                "customer_conclusion": "记录完成时间超过规定时限。",
            },
            {
                "record_id": "R-A",
                "patient_name": "甲患者",
                "rule_id": "LX0609-03-01-02",
                "status": "ai_suggested_non_compliant",
                "reason_code": "semantic_low_confidence",
            },
            {
                "record_id": "R-B",
                "patient_name": "乙患者",
                "rule_id": "LX0609-11-01-01",
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
        "LX0609-01-01-01",
        "LX0609-03-01-02",
    ]
    csv_rows = list(csv.reader(StringIO(csv_text)))
    detail_start = csv_rows.index(["全部明细"])
    assert [row[1] for row in csv_rows[detail_start + 2 :]] == [
        "LX0609-01-01-01",
        "LX0609-03-01-02",
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
    for rule_id in ("LX0609-01-01-01", "LX0609-03-01-02"):
        assert html.find(rule_id) >= 0
        assert csv_text.find(rule_id) >= 0
    assert "LX0609-11-01-01" not in html
    assert "LX0609-11-01-01" not in csv_text

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
            "selected_rule_ids": ["LX0609-01-01-01"],
        },
        "items": [
            {
                "record_id": "R-IDEMPOTENT",
                "rule_id": "LX0609-01-01-01",
                "status": "non_compliant",
                "reason_code": "deadline_exceeded",
                "criterion_results": _failed_criterion(),
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
    assert second["draft_ids"] == ["LX0609-01-01-01"]
    assert second["items"] == first["items"]
    assert "病历引用" not in service.export_batch_job_html(job=second)
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


def _lx0609_export_job(*items: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "job-lx-rule-isolation",
        "status": "completed",
        "filters": {"rule_set_key": "luxian_0609_qc_v1"},
        "summary": {"total_records": 1},
        "items": list(items),
    }


def _lx0609_compliant_item(rule_id: str) -> dict[str, Any]:
    return {
        "record_id": "record-1",
        "rule_id": rule_id,
        "status": "compliant",
        "is_compliant": True,
        "reason_code": "within_deadline",
    }


def test_luxian_customer_projection_filters_excluded_rule_but_rejects_unknown_rule() -> None:
    visible = project_customer_safe_batch_job(
        _lx0609_export_job(
            _lx0609_compliant_item("LX0609-01-01-01"),
            _lx0609_compliant_item("LX0609-11-01-01"),
        ),
        hmac_key=customer_safe_projection_key(),
    )

    assert [item["rule_id"] for item in visible["items"]] == ["LX0609-01-01-01"]
    assert visible["summary"]["result_count"] == 1
    assert visible["summary"]["status_counts"] == {"compliant": 1}

    with pytest.raises(ValueError, match="LX0609 客户结果解释合同不完整"):
        project_customer_safe_batch_job(
            _lx0609_export_job(
                _lx0609_compliant_item("LX0609-01-01-01"),
                _lx0609_compliant_item("LX0609-999"),
            ),
            hmac_key=customer_safe_projection_key(),
        )

    missing_rule_id = _lx0609_compliant_item("LX0609-01-01-01")
    missing_rule_id.pop("rule_id")
    with pytest.raises(ValueError, match="LX0609 客户结果解释合同不完整"):
        project_customer_safe_batch_job(
            _lx0609_export_job(missing_rule_id),
            hmac_key=customer_safe_projection_key(),
        )


def test_luxian_customer_exports_share_rule_isolation_for_csv_xlsx_and_html() -> None:
    service = _service()
    visible_job = _lx0609_export_job(
        _lx0609_compliant_item("LX0609-01-01-01"),
        _lx0609_compliant_item("LX0609-11-01-01"),
    )

    csv_text = service.export_batch_job_csv(job=visible_job).getvalue()
    workbook = load_workbook(
        BytesIO(service.export_batch_job_workbook(job=visible_job).getvalue())
    )
    html = service.export_batch_job_html(job=visible_job)
    for exported in (csv_text, html):
        assert "LX0609-01-01-01" in exported
        assert "LX0609-11-01-01" not in exported
    workbook_text = "\n".join(
        str(cell)
        for sheet in workbook.worksheets
        for row in sheet.iter_rows(values_only=True)
        for cell in row
        if cell is not None
    )
    assert "LX0609-01-01-01" in workbook_text
    assert "LX0609-11-01-01" not in workbook_text

    malformed_job = _lx0609_export_job(
        _lx0609_compliant_item("LX0609-01-01-01"),
        _lx0609_compliant_item("LX0609-999"),
    )
    with pytest.raises(ValueError, match="LX0609 客户结果解释合同不完整"):
        service.export_batch_job_csv(job=malformed_job)
    with pytest.raises(ValueError, match="LX0609 客户结果解释合同不完整"):
        service.export_batch_job_workbook(job=malformed_job)
    with pytest.raises(ValueError, match="LX0609 客户结果解释合同不完整"):
        service.export_batch_job_html(job=malformed_job)


def test_luxian_customer_projection_preserves_case_counts_and_filters_nested_results() -> None:
    allowed_item = _lx0609_compliant_item("LX0609-01-01-01")
    excluded_item = _lx0609_compliant_item("LX0609-11-01-01")
    child = {
        "id": "child-rule-isolation",
        "status": "completed",
        "filters": {"rule_set_key": "luxian_0609_qc_v1"},
        "summary": {"total_records": 9, "success_count": 8, "failed_count": 1},
        "items": [allowed_item, excluded_item],
        "rule_results": [
            {
                "rule_code": "LX0609-01-01-01",
                "total_records": 9,
                "success_count": 8,
                "failed_count": 1,
                "items": [allowed_item],
            },
            {
                "rule_code": "LX0609-11-01-01",
                "total_records": 9,
                "success_count": 8,
                "failed_count": 1,
                "items": [excluded_item],
            },
        ],
    }
    projected = project_customer_safe_batch_job(
        {
            "id": "parent-rule-isolation",
            "status": "completed",
            "filters": {"rule_set_key": "luxian_0609_qc_v1"},
            "summary": {"total_records": 9, "success_count": 8, "failed_count": 1},
            "child_jobs": [child],
        },
        hmac_key=customer_safe_projection_key(),
    )

    # total/success/failed 是病例处理范围计数，不因客户隐藏规则而改写。
    assert projected["summary"]["total_records"] == 9
    assert projected["summary"]["success_count"] == 8
    assert projected["summary"]["failed_count"] == 1
    child_projection = projected["child_jobs"][0]
    assert child_projection["summary"]["total_records"] == 9
    assert child_projection["summary"]["success_count"] == 8
    assert child_projection["summary"]["failed_count"] == 1
    assert [item["rule_id"] for item in child_projection["items"]] == ["LX0609-01-01-01"]
    assert child_projection["rule_results"][0]["total_records"] == 9
    assert child_projection["rule_results"][0]["success_count"] == 8
    assert child_projection["rule_results"][0]["failed_count"] == 1
    assert child_projection["rule_results"][0]["issue_records"] == 0
    assert len(child_projection["rule_results"]) == 1


@pytest.mark.parametrize(
    "malformed_rule",
    [
        {"rule_code": "LX0609-999", "items": []},
        {"items": []},
    ],
    ids=["unknown", "missing"],
)
def test_luxian_customer_projection_rejects_unknown_or_missing_rule_result_identity(
    malformed_rule: dict[str, Any],
) -> None:
    job = _lx0609_export_job(_lx0609_compliant_item("LX0609-01-01-01"))
    job["rule_results"] = [malformed_rule]

    with pytest.raises(ValueError, match="LX0609 客户结果解释合同不完整"):
        project_customer_safe_batch_job(
            job,
            hmac_key=customer_safe_projection_key(),
        )


def test_luxian_customer_projection_rejects_missing_review_finding_identity() -> None:
    job = _lx0609_export_job(_lx0609_compliant_item("LX0609-01-01-01"))
    job["summary"]["review_report"] = {
        "findings": [{"severity": "P1", "suggested_status": "uncertain"}]
    }

    with pytest.raises(ValueError, match="LX0609 客户结果解释合同不完整"):
        project_customer_safe_batch_job(
            job,
            hmac_key=customer_safe_projection_key(),
        )
