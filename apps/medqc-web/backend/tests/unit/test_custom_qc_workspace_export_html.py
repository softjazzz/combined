from app.services.custom_qc_workspace_service import CustomQCWorkspaceService


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
        "filters": {"selected_rule_ids": ["LX0609-001", "LX0609-002"]},
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
    assert "泸县0609质控点验证 v1" in html
    assert "V001" in html
    assert "V002" in html
    assert "入院记录未在入院后24小时内完成" in html
    assert "入院时间" in html
    assert "2026-06-01 08:00" in html
    assert "记录时间" in html
    assert "2026-06-02 10:00" in html
    assert "间隔" in html
    assert "26小时" in html
    assert "首次病程记录时间" in html
    assert "未归因 Token" in html
    assert "31,529" in html
    assert "Token 拆分" in html
    assert "有未归因" in html
    assert "结果复核建议" in html
    assert "建议总数" in html
    assert "首次病程记录时间缺失，建议结合原文确认" in html
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

    assert html.count("V001") >= 2
    assert "LX0609-001" in html
    assert "LX0609-020" in html
    assert "入院记录超时" in html
    assert "会诊执行记录完整" in html
