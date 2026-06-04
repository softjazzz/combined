from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
from app.routers.qc_agent import get_qc_agent_registry
from app.services.qc_agent.schemas import (
    GetRecordContextInput,
    ListQCRulesInput,
    ResolveRuleScopeInput,
    RunDocumentQCInput,
    RunFrontpageQCInput,
    SearchRecordsInput,
    SelectRecordDocumentsInput,
)
from app.services.qc_agent.tool_registry import AgentToolRegistry
from app.services.qc_agent.tools import (
    get_record_context,
    list_qc_rules,
    register_default_tools,
    resolve_rule_scope,
    run_document_qc,
    run_frontpage_qc,
    select_record_documents,
    search_records,
)


class FakeWorkspace:
    def __init__(self) -> None:
        self.calls = []
        self.hydrate_calls = []
        self.persist_called = False

    def collect_records(
        self,
        *,
        scope,
        department,
        doctor,
        date_field,
        start_date,
        end_date,
        keyword,
        record_ids=None,
    ):
        self.calls.append(
            {
                "scope": scope,
                "department": department,
                "doctor": doctor,
                "date_field": date_field,
                "start_date": start_date,
                "end_date": end_date,
                "keyword": keyword,
                "record_ids": record_ids,
            }
        )
        records = [
            {
                "visit_id": "V001",
                "patient_id": "P001",
                "patient_name": "张三",
                "department": "神经内科",
                "doctor": "李医生",
                "admission_date": "2026-05-01",
                "discharge_date": "2026-05-08",
                "medical_text": "完整病历正文不允许返回",
                "record_content": "原始文书不允许返回",
                "documents": [{"content": "文书不允许返回"}],
                "bundle": {"text": "bundle 不允许返回"},
            },
            {
                "visit_id": "V002",
                "patient_id": "P002",
                "patient_name": "李四",
                "department": "心内科",
                "doctor": "王医生",
                "admission_date": "2026-05-02",
                "discharge_date": "2026-05-09",
            },
            {
                "visit_id": "V003",
                "patient_id": "P003",
                "patient_name": "王五",
                "department": "消化内科",
                "doctor": "赵医生",
                "admission_date": "2026-05-10",
                "discharge_date": "2026-05-11",
                "medical_text": "",
            },
        ]
        if record_ids:
            return [record for record in records if record.get("visit_id") in record_ids]
        return records

    def hydrate_records_with_medical_text(self, records):
        self.hydrate_calls.append(records)
        hydrated = []
        for record in records:
            if record.get("visit_id") == "V003":
                hydrated.append({**record, "mr_no": "MR003", "documents": []})
                continue
            if record.get("visit_id") == "V002":
                hydrated.append(
                    {
                        **record,
                        "mr_no": "MR002",
                        "medical_text": "姓名：李四\n出院记录：患者好转出院，无查房相关内容。",
                        "documents": [
                            {
                                "document_ref": "DOC-DIS-1",
                                "document_type": "出院记录",
                                "title": "出院记录",
                                "content": "2026-05-09 出院记录：患者好转出院。",
                                "record_time": "2026-05-09 10:00:00",
                            }
                        ],
                    }
                )
                continue
            hydrated.append(
                {
                    **record,
                    "mr_no": "MR001",
                    "medical_text": (
                        "姓名：张三\n性别：男\n年龄：46岁\n身份证号：110101198001011234\n"
                        "入院时间：2026-05-01 09:00:00\n出院时间：2026-05-08 10:00:00\n"
                        "入院科别：神经内科\n出院科别：神经内科\n入院途径：2\n离院方式：1\n"
                        "实际住院天数：7天\n主治医师：李医生\n"
                        "出院主要诊断：脑梗死\n主要诊断编码：I63.900\n"
                        "其他诊断：高血压 I10\n总费用：12345.67\n"
                        "手机号13812345678，现住址：北京市朝阳区示例路99号。"
                        + "入院记录显示患者头痛头晕，诊断考虑脑梗死。" * 80
                    ),
                    "documents": [
                        {
                            "document_type": "入院记录",
                            "content": "入院记录原文不允许直接返回",
                            "record_time": "2026-05-01 09:00:00",
                        },
                        {
                            "document_ref": "DOC-WR-1",
                            "document_type": "日常病程记录",
                            "title": "上级医师查房记录",
                            "content": (
                                "2026-05-03 主任医师查房：患者头痛较前改善，病情变化平稳。"
                                "处理意见：继续抗血小板治疗，完善头颅影像复查。"
                                "医师签名：李医生。身份证号110101198001011234，手机号13812345678。"
                            ),
                            "record_time": "2026-05-03 08:30:00",
                        },
                        {
                            "document_type": "出院记录",
                            "content": "出院记录原文不允许直接返回",
                            "updated_at": "2026-05-08 10:00:00",
                        },
                    ],
                    "bundle": {"full": "bundle 全量不允许返回"},
                    "structured_context": {"full": "structured_context 全量不允许返回"},
                }
            )
        return hydrated

    def load_or_assemble_scene_bundle(self, *args, **kwargs):
        self.persist_called = True
        raise AssertionError("不允许调用会写 scene bundle 的函数")

    def upsert_scene_bundle(self, *args, **kwargs):
        self.persist_called = True
        raise AssertionError("不允许调用持久化函数")


class SearchResultWorkspace(FakeWorkspace):
    def __init__(self, search_records):
        super().__init__()
        self._search_records = search_records

    def collect_records(
        self,
        *,
        scope,
        department,
        doctor,
        date_field,
        start_date,
        end_date,
        keyword,
        record_ids=None,
    ):
        if record_ids:
            return super().collect_records(
                scope=scope,
                department=department,
                doctor=doctor,
                date_field=date_field,
                start_date=start_date,
                end_date=end_date,
                keyword=keyword,
                record_ids=record_ids,
            )
        self.calls.append(
            {
                "scope": scope,
                "department": department,
                "doctor": doctor,
                "date_field": date_field,
                "start_date": start_date,
                "end_date": end_date,
                "keyword": keyword,
                "record_ids": record_ids,
            }
        )
        return self._search_records


def _assert_no_sensitive_keys(value):
    if isinstance(value, dict):
        assert "medical_text" not in value
        assert "record_content" not in value
        assert "documents" not in value
        assert "bundle" not in value
        assert "structured_context" not in value
        assert "text_preview" not in value
        assert "frontpage_draft" not in value
        assert "raw_draft" not in value
        assert "draft_json" not in value
        for item in value.values():
            _assert_no_sensitive_keys(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_sensitive_keys(item)


def _assert_no_raw_context(value):
    raw_text = str(value)
    assert "完整病历正文不允许返回" not in raw_text
    assert "入院记录原文不允许直接返回" not in raw_text
    assert "出院记录原文不允许直接返回" not in raw_text
    assert "bundle 全量不允许返回" not in raw_text
    assert "structured_context 全量不允许返回" not in raw_text
    assert "110101198001011234" not in raw_text
    assert "13812345678" not in raw_text
    assert "medical_text" not in raw_text
    assert "record_content" not in raw_text
    assert "internal_data" not in raw_text
    assert "raw_llm_output" not in raw_text
    assert "rule_prompt" not in raw_text
    assert "custom_prompt" not in raw_text
    assert "positive_example" not in raw_text
    assert "negative_example" not in raw_text
    assert "few_shot_examples" not in raw_text


def test_search_records_returns_public_record_summaries_only():
    workspace = FakeWorkspace()
    observation = search_records(
        SearchRecordsInput(
            scope="final",
            department="神经内科",
            doctor="李医生",
            date_field="discharge",
            start_date="2026-05-01",
            end_date="2026-05-31",
            keyword="张三",
        ),
        workspace=workspace,  # type: ignore[arg-type]
    )

    assert observation.status == "success"
    assert workspace.calls == [
        {
            "scope": "final",
            "department": "神经内科",
            "doctor": "李医生",
            "date_field": "discharge",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "keyword": "张三",
            "record_ids": None,
        }
    ]
    assert observation.public_data["total"] == 3
    assert observation.public_data["page_size"] == 20
    assert observation.public_data["records"][0] == {
        "visit_id": "V001",
        "patient_id": "P001",
        "patient_name": "张三",
        "department": "神经内科",
        "doctor": "李医生",
        "admission_date": "2026-05-01",
        "discharge_date": "2026-05-08",
    }
    _assert_no_sensitive_keys(observation.public_data)
    _assert_no_sensitive_keys(observation.internal_data)


def test_search_records_applies_page_and_page_size():
    workspace = FakeWorkspace()
    observation = search_records(
        SearchRecordsInput(page=2, page_size=1),
        workspace=workspace,  # type: ignore[arg-type]
    )

    assert observation.public_data["total"] == 3
    assert observation.public_data["page"] == 2
    assert observation.public_data["page_size"] == 1
    assert observation.public_data["records"][0]["visit_id"] == "V002"


def test_search_records_rejects_page_size_overflow():
    with pytest.raises(Exception):
        SearchRecordsInput(page_size=51)


def test_get_record_context_returns_public_summary_and_internal_context():
    workspace = FakeWorkspace()
    observation = get_record_context(
        {
            "visit_id": "V001",
            "patient_id": "P001",
            "scene": "final",
            "include_preview": True,
        },
        workspace=workspace,  # type: ignore[arg-type]
    )

    assert observation.status == "success"
    assert workspace.calls[0]["record_ids"] == ["V001"]
    assert len(workspace.hydrate_calls) == 1
    assert workspace.persist_called is False
    public_data = observation.public_data
    assert public_data["record_summary"]["visit_id"] == "V001"
    assert public_data["record_summary"]["patient_id"] == "P001"
    assert public_data["record_summary"]["mr_no"] == "MR001"
    assert public_data["context_status"]["text_available"] is True
    assert public_data["context_status"]["bundle_available"] is True
    assert public_data["context_status"]["source"] == "hydrate_records_with_medical_text"
    assert public_data["context_status"]["scene"] == "final"
    assert public_data["document_summary"][0]["document_type"] == "入院记录"
    assert len(public_data["preview"]) <= 500
    assert "110101198001011234" not in public_data["preview"]
    assert "13812345678" not in public_data["preview"]
    assert "北京市朝阳区示例路99号" not in public_data["preview"]
    assert observation.internal_data is not None
    assert observation.internal_data["medical_text"]
    _assert_no_sensitive_keys(public_data)


def test_get_record_context_rejects_patient_id_mismatch():
    workspace = FakeWorkspace()

    with pytest.raises(Exception) as exc_info:
        get_record_context(
            {"visit_id": "V001", "patient_id": "P999"},
            workspace=workspace,  # type: ignore[arg-type]
        )

    assert getattr(exc_info.value, "status_code", None) == 409
    assert workspace.persist_called is False


def test_get_record_context_rejects_missing_record():
    workspace = FakeWorkspace()

    with pytest.raises(Exception) as exc_info:
        get_record_context(
            {"visit_id": "V404"},
            workspace=workspace,  # type: ignore[arg-type]
        )

    assert getattr(exc_info.value, "status_code", None) == 404
    assert workspace.persist_called is False


def test_run_frontpage_qc_returns_summary_and_issues():
    workspace = FakeWorkspace()
    observation = run_frontpage_qc(
        RunFrontpageQCInput(visit_id="V001", patient_id="P001"),
        workspace=workspace,  # type: ignore[arg-type]
    )

    assert observation.status == "success"
    assert workspace.persist_called is False
    public_data = observation.public_data
    assert public_data["record_summary"]["visit_id"] == "V001"
    assert public_data["generation_status"]["draft_generated"] is True
    assert public_data["generation_status"]["text_length"] > 0
    assert public_data["qc_summary"]["total_rules"] > 0
    assert public_data["qc_summary"]["issue_count"] == public_data["qc_summary"]["failed"]
    assert all(issue["message"] for issue in public_data["issues"])
    assert all(issue["rule_id"] for issue in public_data["issues"])
    assert observation.internal_data is not None
    assert observation.internal_data["frontpage_draft"]
    _assert_no_sensitive_keys(public_data)


def test_run_frontpage_qc_rejects_patient_id_mismatch():
    workspace = FakeWorkspace()

    with pytest.raises(Exception) as exc_info:
        run_frontpage_qc(
            {"visit_id": "V001", "patient_id": "P999"},
            workspace=workspace,  # type: ignore[arg-type]
        )

    assert getattr(exc_info.value, "status_code", None) == 409
    assert workspace.persist_called is False


def test_run_frontpage_qc_rejects_batch_visit_ids():
    workspace = FakeWorkspace()

    with pytest.raises(Exception) as exc_info:
        run_frontpage_qc(
            {"visit_id": "V001,V002"},
            workspace=workspace,  # type: ignore[arg-type]
        )

    assert getattr(exc_info.value, "status_code", None) == 422
    assert workspace.calls == []
    assert workspace.persist_called is False


def test_run_frontpage_qc_rejects_missing_or_empty_context():
    workspace = FakeWorkspace()

    with pytest.raises(Exception) as exc_info:
        run_frontpage_qc(
            {"visit_id": "V003", "patient_id": "P003"},
            workspace=workspace,  # type: ignore[arg-type]
        )

    assert getattr(exc_info.value, "status_code", None) == 422
    assert "medical_text" in str(exc_info.value.detail)
    assert workspace.persist_called is False


def test_run_frontpage_qc_include_passed_flag_controls_results():
    workspace = FakeWorkspace()
    failed_only = run_frontpage_qc(
        {"visit_id": "V001", "patient_id": "P001", "include_passed": False},
        workspace=workspace,  # type: ignore[arg-type]
    )
    with_passed = run_frontpage_qc(
        {"visit_id": "V001", "patient_id": "P001", "include_passed": True},
        workspace=workspace,  # type: ignore[arg-type]
    )

    assert len(failed_only.public_data["issues"]) == failed_only.public_data["qc_summary"]["failed"]
    assert len(with_passed.public_data["issues"]) == with_passed.public_data["qc_summary"]["total_rules"]
    assert any(issue["message"] == "" for issue in with_passed.public_data["issues"])
    _assert_no_sensitive_keys(with_passed.public_data)


def test_run_frontpage_qc_does_not_call_persistence_paths(monkeypatch):
    workspace = FakeWorkspace()

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("不允许调用持久化路径")

    monkeypatch.setattr(
        "app.services.medical_records.maintenance_service.save_ai_frontpage_draft",
        _forbidden,
    )
    monkeypatch.setattr(
        "app.services.qc_persistence_service.default_qc_persistence_service.persist_analysis",
        _forbidden,
    )
    monkeypatch.setattr(
        "app.services.workflow_queue_state_service.default_workflow_queue_state_service.start_run",
        _forbidden,
    )
    monkeypatch.setattr(
        "app.services.workflow_queue_state_service.default_workflow_queue_state_service.finish_success",
        _forbidden,
    )
    monkeypatch.setattr(
        "app.services.workflow_queue_state_service.default_workflow_queue_state_service.finish_failed",
        _forbidden,
    )
    monkeypatch.setattr(
        "app.services.workflow_queue_state_service.default_workflow_queue_state_service.backfill_frontpage_generate",
        _forbidden,
    )

    observation = run_frontpage_qc(
        {"visit_id": "V001", "patient_id": "P001"},
        workspace=workspace,  # type: ignore[arg-type]
    )

    assert observation.status == "success"
    assert workspace.persist_called is False


def test_select_record_documents_matches_ward_round_from_course_document():
    workspace = FakeWorkspace()
    observation = select_record_documents(
        SelectRecordDocumentsInput(
            visit_id="V001",
            patient_id="P001",
            document_scope={"alias": "ward_round"},
        ),
        workspace=workspace,  # type: ignore[arg-type]
    )

    assert observation.status == "success"
    assert workspace.persist_called is False
    public_data = observation.public_data
    assert public_data["record_summary"]["visit_id"] == "V001"
    assert public_data["selection_summary"]["matched_document_count"] == 1
    assert public_data["documents"][0]["document_ref"] == "DOC-WR-1"
    assert public_data["documents"][0]["document_type"] == "日常病程记录"
    assert len(public_data["documents"][0]["preview"]) <= 300
    assert "110101198001011234" not in public_data["documents"][0]["preview"]
    assert "13812345678" not in public_data["documents"][0]["preview"]
    assert observation.internal_data is not None
    assert observation.internal_data["selected_documents"][0]["text"]
    _assert_no_raw_context(public_data)


def test_select_record_documents_rejects_patient_id_mismatch():
    workspace = FakeWorkspace()

    with pytest.raises(Exception) as exc_info:
        select_record_documents(
            {"visit_id": "V001", "patient_id": "P999", "document_scope": {"alias": "ward_round"}},
            workspace=workspace,  # type: ignore[arg-type]
        )

    assert getattr(exc_info.value, "status_code", None) == 409
    assert workspace.persist_called is False


def test_select_record_documents_rejects_missing_or_empty_context():
    workspace = FakeWorkspace()

    with pytest.raises(Exception) as exc_info:
        select_record_documents(
            {"visit_id": "V003", "patient_id": "P003", "document_scope": {"alias": "ward_round"}},
            workspace=workspace,  # type: ignore[arg-type]
        )

    assert getattr(exc_info.value, "status_code", None) == 422
    assert "文书文本" in str(exc_info.value.detail)
    assert workspace.persist_called is False


def test_select_record_documents_no_match_returns_success_with_warning():
    workspace = FakeWorkspace()
    observation = select_record_documents(
        {"visit_id": "V002", "patient_id": "P002", "document_scope": {"alias": "ward_round"}},
        workspace=workspace,  # type: ignore[arg-type]
    )

    assert observation.status == "success"
    assert observation.public_data["selection_summary"]["matched_document_count"] == 0
    assert "未命中文书" in observation.public_data["warnings"]
    _assert_no_raw_context(observation.public_data)


def test_run_document_qc_ward_round_returns_summary_and_failures_only():
    workspace = FakeWorkspace()
    observation = run_document_qc(
        RunDocumentQCInput(
            visit_id="V001",
            patient_id="P001",
            document_scope={"alias": "ward_round"},
            qc_scope={"rule_family": "ward_round", "include_passed": False},
        ),
        workspace=workspace,  # type: ignore[arg-type]
    )

    assert observation.status == "success"
    assert workspace.persist_called is False
    public_data = observation.public_data
    assert public_data["document_selection_summary"]["matched_document_count"] == 1
    assert public_data["qc_summary"]["total_rules"] == 4
    assert public_data["qc_summary"]["rule_count"] == 4
    assert public_data["qc_summary"]["issue_count"] == public_data["qc_summary"]["failed"]
    assert "未传入 rule_ids 或可解析规则范围，已使用默认文书规则集" in public_data["warnings"]
    assert all(issue["passed"] is False for issue in public_data["issues"])
    assert observation.internal_data is not None
    assert observation.internal_data["selected_documents"][0]["text"]
    _assert_no_raw_context(public_data)


def test_run_document_qc_executes_selected_agent_builtin_rule_ids():
    workspace = FakeWorkspace()
    observation = run_document_qc(
        {
            "visit_id": "V001",
            "patient_id": "P001",
            "document_alias": "ward_round",
            "rule_ids": ["WR-001", "WR-004"],
            "include_passed": True,
        },
        workspace=workspace,  # type: ignore[arg-type]
    )

    public_data = observation.public_data
    assert {rule["rule_id"] for rule in public_data["selected_rules"]} == {"WR-001", "WR-004"}
    assert {rule["rule_id"] for rule in public_data["executed_rules"]} == {"WR-001", "WR-004"}
    assert public_data["skipped_rules"] == []
    assert public_data["qc_summary"]["rule_count"] == 2
    assert public_data["qc_summary"]["total_rules"] == 2
    assert len(public_data["issues"]) == 2
    _assert_no_raw_context(public_data)


def test_run_document_qc_resolves_scope_and_skips_non_executable_rules():
    workspace = FakeWorkspace()
    observation = run_document_qc(
        {
            "visit_id": "V001",
            "patient_id": "P001",
            "document_alias": "ward_round",
            "qc_point_type": "timeliness",
            "include_passed": True,
            "max_rules": 5,
        },
        workspace=workspace,  # type: ignore[arg-type]
    )

    public_data = observation.public_data
    assert public_data["selected_rules"]
    assert all(rule["qc_point_type"] == "timeliness" for rule in public_data["selected_rules"])
    assert public_data["qc_summary"]["skipped_count"] > 0
    assert any(
        item["reason"] in {"requires_llm", "unsupported_execution_mode"}
        for item in public_data["skipped_rules"]
    )
    _assert_no_raw_context(public_data)


def test_run_document_qc_skips_requires_llm_and_unknown_rule_ids():
    workspace = FakeWorkspace()
    observation = run_document_qc(
        {
            "visit_id": "V001",
            "patient_id": "P001",
            "document_alias": "ward_round",
            "rule_ids": ["CL-001", "UNKNOWN-RULE"],
            "include_passed": True,
        },
        workspace=workspace,  # type: ignore[arg-type]
    )

    skipped = observation.public_data["skipped_rules"]
    assert any(item["rule_id"] == "CL-001" and item["reason"] == "requires_llm" for item in skipped)
    assert any(item["rule_id"] == "UNKNOWN-RULE" and item["reason"] == "unknown_rule" for item in skipped)
    assert observation.public_data["executed_rules"] == []
    assert observation.public_data["qc_summary"]["skipped_count"] == 2
    _assert_no_raw_context(observation.public_data)


def test_run_document_qc_skips_not_applicable_document_rule():
    workspace = FakeWorkspace()
    observation = run_document_qc(
        {
            "visit_id": "V001",
            "patient_id": "P001",
            "document_alias": "ward_round",
            "rule_ids": ["DG-001"],
            "include_passed": True,
        },
        workspace=workspace,  # type: ignore[arg-type]
    )

    assert observation.public_data["executed_rules"] == []
    assert observation.public_data["skipped_rules"][0]["reason"] == "not_applicable_document"


def test_run_document_qc_include_passed_returns_all_rules():
    workspace = FakeWorkspace()
    observation = run_document_qc(
        {
            "visit_id": "V001",
            "patient_id": "P001",
            "document_scope": {"alias": "ward_round"},
            "qc_scope": {"rule_family": "ward_round", "include_passed": True},
        },
        workspace=workspace,  # type: ignore[arg-type]
    )

    assert len(observation.public_data["issues"]) == 4
    assert any(issue["passed"] is True for issue in observation.public_data["issues"])
    _assert_no_raw_context(observation.public_data)


def test_run_document_qc_rejects_max_rules_overflow():
    with pytest.raises(Exception):
        RunDocumentQCInput(visit_id="V001", max_rules=51)


def test_run_document_qc_no_ward_round_document_returns_warning_and_errors():
    workspace = FakeWorkspace()
    observation = run_document_qc(
        {
            "visit_id": "V002",
            "patient_id": "P002",
            "document_scope": {"alias": "ward_round"},
            "qc_scope": {"rule_family": "ward_round", "include_passed": False},
        },
        workspace=workspace,  # type: ignore[arg-type]
    )

    assert observation.status == "success"
    assert observation.public_data["document_selection_summary"]["matched_document_count"] == 0
    assert "未命中可质控文书" in observation.public_data["warnings"]
    assert observation.public_data["qc_summary"]["failed"] == 4
    assert all(issue["passed"] is False for issue in observation.public_data["issues"])


def test_run_document_qc_rejects_patient_id_mismatch():
    workspace = FakeWorkspace()

    with pytest.raises(Exception) as exc_info:
        run_document_qc(
            {"visit_id": "V001", "patient_id": "P999", "document_scope": {"alias": "ward_round"}},
            workspace=workspace,  # type: ignore[arg-type]
        )

    assert getattr(exc_info.value, "status_code", None) == 409
    assert workspace.persist_called is False


def test_run_document_qc_rejects_batch_visit_ids():
    workspace = FakeWorkspace()

    with pytest.raises(Exception) as exc_info:
        run_document_qc(
            {"visit_id": "V001,V002", "document_scope": {"alias": "ward_round"}},
            workspace=workspace,  # type: ignore[arg-type]
        )

    assert getattr(exc_info.value, "status_code", None) == 422
    assert workspace.calls == []
    assert workspace.persist_called is False


def test_run_document_qc_does_not_call_persistence_paths(monkeypatch):
    workspace = FakeWorkspace()

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("不允许调用持久化路径")

    monkeypatch.setattr(
        "app.services.medical_records.maintenance_service.save_ai_frontpage_draft",
        _forbidden,
    )
    monkeypatch.setattr(
        "app.services.qc_persistence_service.default_qc_persistence_service.persist_analysis",
        _forbidden,
    )
    monkeypatch.setattr(
        "app.services.workflow_queue_state_service.default_workflow_queue_state_service.start_run",
        _forbidden,
    )
    monkeypatch.setattr(
        "app.services.workflow_queue_state_service.default_workflow_queue_state_service.finish_success",
        _forbidden,
    )
    monkeypatch.setattr(
        "app.services.workflow_queue_state_service.default_workflow_queue_state_service.finish_failed",
        _forbidden,
    )
    monkeypatch.setattr(
        "app.services.workflow_queue_state_service.default_workflow_queue_state_service.backfill_frontpage_generate",
        _forbidden,
    )

    observation = run_document_qc(
        {"visit_id": "V001", "patient_id": "P001", "document_scope": {"alias": "ward_round"}},
        workspace=workspace,  # type: ignore[arg-type]
    )

    assert observation.status == "success"
    assert workspace.persist_called is False


def _assert_rule_public_summary(rule):
    assert rule["rule_id"]
    assert rule["rule_name"]
    assert rule["source"] in {
        "sc146",
        "custom33",
        "customer_luxian",
        "frontpage_formal",
        "agent_builtin",
    }
    assert "custom_prompt" not in rule
    assert "positive_example" not in rule
    assert "negative_example" not in rule
    assert "prompt" not in rule
    assert "examples" not in rule


def test_list_qc_rules_returns_catalog_without_sensitive_rule_fields():
    observation = list_qc_rules(ListQCRulesInput(limit=20))

    assert observation.status == "success"
    public_data = observation.public_data
    assert public_data["total"] > 0
    assert public_data["returned"] <= 20
    assert public_data["rules"]
    for rule in public_data["rules"]:
        _assert_rule_public_summary(rule)
    _assert_no_raw_context(public_data)


def test_list_qc_rules_filters_ward_round_and_discharge_aliases():
    ward_round = list_qc_rules({"document_alias": "ward_round", "limit": 100})
    discharge = list_qc_rules({"document_alias": "discharge", "limit": 100})

    ward_round_ids = {rule["rule_id"] for rule in ward_round.public_data["rules"]}
    assert "WR-001" in ward_round_ids
    assert all("ward_round" in rule["document_aliases"] for rule in ward_round.public_data["rules"])
    assert discharge.public_data["returned"] > 0
    assert all("discharge" in rule["document_aliases"] for rule in discharge.public_data["rules"])


def test_list_qc_rules_filters_qc_point_types():
    for qc_point_type in ("timeliness", "completeness", "consistency"):
        observation = list_qc_rules({"qc_point_type": qc_point_type, "limit": 50})

        assert observation.public_data["returned"] > 0
        assert all(rule["qc_point_type"] == qc_point_type for rule in observation.public_data["rules"])


def test_list_qc_rules_covers_rule_sources():
    for source in ("sc146", "custom33", "customer_luxian", "frontpage_formal", "agent_builtin"):
        observation = list_qc_rules({"source": source, "limit": 5})

        assert observation.public_data["returned"] > 0
        assert all(rule["source"] == source for rule in observation.public_data["rules"])


def test_resolve_rule_scope_returns_stable_rule_ids_and_warnings():
    observation = resolve_rule_scope(
        ResolveRuleScopeInput(
            document_alias="ward_round",
            qc_point_type="completeness",
            source="agent_builtin",
            limit=10,
        )
    )

    assert observation.status == "success"
    assert "WR-001" in observation.public_data["rule_ids"]
    assert observation.public_data["warnings"] == []
    assert observation.internal_data == {"rule_ids": observation.public_data["rule_ids"]}

    unknown = resolve_rule_scope({"document_alias": "unknown_doc", "qc_point_type": "unknown_qc"})
    assert unknown.status == "success"
    assert unknown.public_data["rule_count"] == 0
    assert any("未知文书" in item for item in unknown.public_data["warnings"])
    assert any("未知质控点" in item for item in unknown.public_data["warnings"])


def test_list_qc_rules_limit_upper_bound():
    with pytest.raises(Exception):
        ListQCRulesInput(limit=201)


@pytest.fixture
def qc_agent_auth(client):
    async def _noop_auth_gate():
        return None

    def _user():
        return {"id": "u-qc-agent", "roles": ["admin", "qc_manager"]}

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    client.app.dependency_overrides[get_current_user] = _user
    yield
    client.app.dependency_overrides.pop(enforce_default_auth, None)
    client.app.dependency_overrides.pop(get_current_user, None)
    client.app.dependency_overrides.pop(get_qc_agent_registry, None)


def _registry_with_workspace(workspace) -> AgentToolRegistry:
    registry = AgentToolRegistry()

    def _handler(payload):
        return search_records(payload, workspace=workspace)

    registry.register(
        name="search_records",
        description="按安全筛选条件检索病历索引摘要；不返回病历全文。",
        input_model=SearchRecordsInput,
        handler=_handler,
        risk_level="low",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=5000,
        max_records=50,
    )
    registry.register(
        name="get_record_context",
        description="按 visit_id 只读获取单份病历上下文；API 仅返回摘要和脱敏预览。",
        input_model=GetRecordContextInput,
        handler=lambda payload: get_record_context(payload, workspace=workspace),
        risk_level="medium",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=5000,
        max_records=1,
    )
    registry.register(
        name="run_frontpage_qc",
        description="对单份病历生成瞬态首页草稿并执行首页形式质控；不保存草稿或质控结果。",
        input_model=RunFrontpageQCInput,
        handler=lambda payload: run_frontpage_qc(payload, workspace=workspace),
        risk_level="medium",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=30000,
        max_records=1,
    )
    registry.register(
        name="select_record_documents",
        description="按 visit_id 只读选择单份病历的目标文书；API 仅返回摘要和脱敏预览。",
        input_model=SelectRecordDocumentsInput,
        handler=lambda payload: select_record_documents(payload, workspace=workspace),
        risk_level="medium",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=5000,
        max_records=1,
    )
    registry.register(
        name="run_document_qc",
        description="对单份病历目标文书执行内置只读文书质控；不保存质控结果。",
        input_model=RunDocumentQCInput,
        handler=lambda payload: run_document_qc(payload, workspace=workspace),
        risk_level="medium",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=30000,
        max_records=1,
    )
    registry.register(
        name="list_qc_rules",
        description="只读查询可用于 Agent 的质控规则目录；仅返回规则摘要，不返回 prompt 或示例。",
        input_model=ListQCRulesInput,
        handler=list_qc_rules,
        risk_level="low",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=5000,
        max_records=1,
    )
    registry.register(
        name="resolve_rule_scope",
        description="按结构化条件解析可选 rule_ids，供后续单病历质控工具消费。",
        input_model=ResolveRuleScopeInput,
        handler=resolve_rule_scope,
        risk_level="low",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=5000,
        max_records=1,
    )
    return registry


def _registry_with_fake_workspace() -> AgentToolRegistry:
    return _registry_with_workspace(FakeWorkspace())


def test_api_list_tools_returns_search_records_schema(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.get("/api/v1/qc-agent/tools")

    assert response.status_code == 200
    body = response.json()
    by_name = {item["name"]: item for item in body}
    assert by_name["search_records"]["risk_level"] == "low"
    assert by_name["search_records"]["writes_db"] is False
    assert by_name["search_records"]["requires_confirmation"] is False
    assert by_name["search_records"]["max_records"] == 50
    assert "input_schema" in by_name["search_records"]
    assert by_name["get_record_context"]["risk_level"] == "medium"
    assert by_name["get_record_context"]["writes_db"] is False
    assert by_name["get_record_context"]["requires_confirmation"] is False
    assert by_name["get_record_context"]["max_records"] == 1
    assert "input_schema" in by_name["get_record_context"]
    assert by_name["run_frontpage_qc"]["risk_level"] == "medium"
    assert by_name["run_frontpage_qc"]["writes_db"] is False
    assert by_name["run_frontpage_qc"]["requires_confirmation"] is False
    assert by_name["run_frontpage_qc"]["max_records"] == 1
    assert "input_schema" in by_name["run_frontpage_qc"]
    assert by_name["select_record_documents"]["risk_level"] == "medium"
    assert by_name["select_record_documents"]["writes_db"] is False
    assert by_name["select_record_documents"]["requires_confirmation"] is False
    assert by_name["select_record_documents"]["max_records"] == 1
    assert "input_schema" in by_name["select_record_documents"]
    assert by_name["run_document_qc"]["risk_level"] == "medium"
    assert by_name["run_document_qc"]["writes_db"] is False
    assert by_name["run_document_qc"]["requires_confirmation"] is False
    assert by_name["run_document_qc"]["max_records"] == 1
    assert "input_schema" in by_name["run_document_qc"]
    assert by_name["list_qc_rules"]["risk_level"] == "low"
    assert by_name["list_qc_rules"]["writes_db"] is False
    assert by_name["list_qc_rules"]["requires_confirmation"] is False
    assert by_name["list_qc_rules"]["max_records"] == 1
    assert "input_schema" in by_name["list_qc_rules"]
    assert by_name["resolve_rule_scope"]["risk_level"] == "low"
    assert by_name["resolve_rule_scope"]["writes_db"] is False
    assert by_name["resolve_rule_scope"]["requires_confirmation"] is False
    assert by_name["resolve_rule_scope"]["max_records"] == 1
    assert "input_schema" in by_name["resolve_rule_scope"]


def test_api_requires_login(client):
    response = client.get("/api/v1/qc-agent/tools")

    assert response.status_code == 401


def test_api_rejects_unknown_tool(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.post("/api/v1/qc-agent/tools/unknown/run", json={})

    assert response.status_code == 404


def test_api_search_records_returns_sanitized_output(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.post(
        "/api/v1/qc-agent/tools/search_records/run",
        json={"scope": "final", "keyword": "张三", "page_size": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tool_call"]["tool_name"] == "search_records"
    public_data = body["observation"]["public_data"]
    assert public_data["records"][0]["visit_id"] == "V001"
    assert public_data["records"][0]["patient_name"] == "张三"
    assert "internal_data" not in body["observation"]
    _assert_no_sensitive_keys(body)


def test_api_get_record_context_strips_internal_data_and_raw_context(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.post(
        "/api/v1/qc-agent/tools/get_record_context/run",
        json={"visit_id": "V001", "patient_id": "P001", "include_preview": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tool_call"]["tool_name"] == "get_record_context"
    assert "internal_data" not in body["observation"]
    public_data = body["observation"]["public_data"]
    assert public_data["record_summary"]["visit_id"] == "V001"
    assert len(public_data["preview"]) <= 500
    assert "完整病历正文不允许返回" not in str(body)
    assert "入院记录原文不允许直接返回" not in str(body)
    assert "bundle 全量不允许返回" not in str(body)
    assert "structured_context 全量不允许返回" not in str(body)
    assert "110101198001011234" not in str(body)
    assert "13812345678" not in str(body)
    _assert_no_sensitive_keys(body)


def test_api_run_frontpage_qc_strips_internal_data_and_raw_draft(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.post(
        "/api/v1/qc-agent/tools/run_frontpage_qc/run",
        json={"visit_id": "V001", "patient_id": "P001", "include_passed": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tool_call"]["tool_name"] == "run_frontpage_qc"
    assert "internal_data" not in body["observation"]
    public_data = body["observation"]["public_data"]
    assert public_data["qc_summary"]["total_rules"] > 0
    assert public_data["generation_status"]["draft_generated"] is True
    assert "完整病历正文不允许返回" not in str(body)
    assert "入院记录原文不允许直接返回" not in str(body)
    assert "bundle 全量不允许返回" not in str(body)
    assert "frontpage_draft" not in str(body)
    assert "raw_draft" not in str(body)
    _assert_no_sensitive_keys(body)


def test_api_select_record_documents_strips_internal_data_and_raw_documents(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.post(
        "/api/v1/qc-agent/tools/select_record_documents/run",
        json={"visit_id": "V001", "patient_id": "P001", "document_scope": {"alias": "ward_round"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tool_call"]["tool_name"] == "select_record_documents"
    assert "internal_data" not in body["observation"]
    public_data = body["observation"]["public_data"]
    assert public_data["selection_summary"]["matched_document_count"] == 1
    assert public_data["documents"][0]["document_ref"] == "DOC-WR-1"
    assert len(public_data["documents"][0]["preview"]) <= 300
    _assert_no_raw_context(body)


def test_api_run_document_qc_strips_internal_data_and_raw_documents(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.post(
        "/api/v1/qc-agent/tools/run_document_qc/run",
        json={
            "visit_id": "V001",
            "patient_id": "P001",
            "document_scope": {"alias": "ward_round"},
            "qc_scope": {"rule_family": "ward_round", "include_passed": True},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tool_call"]["tool_name"] == "run_document_qc"
    assert "internal_data" not in body["observation"]
    public_data = body["observation"]["public_data"]
    assert public_data["qc_summary"]["total_rules"] == 4
    assert len(public_data["issues"]) == 4
    _assert_no_raw_context(body)


def test_api_list_qc_rules_returns_public_catalog(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.post(
        "/api/v1/qc-agent/tools/list_qc_rules/run",
        json={"document_alias": "ward_round", "limit": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tool_call"]["tool_name"] == "list_qc_rules"
    assert "internal_data" not in body["observation"]
    public_data = body["observation"]["public_data"]
    assert public_data["returned"] > 0
    assert "WR-001" in {rule["rule_id"] for rule in public_data["rules"]}
    _assert_no_raw_context(body)


def test_api_resolve_rule_scope_returns_rule_ids_and_unknown_warnings(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.post(
        "/api/v1/qc-agent/tools/resolve_rule_scope/run",
        json={"document_alias": "ward_round", "qc_point_type": "completeness", "source": "agent_builtin"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tool_call"]["tool_name"] == "resolve_rule_scope"
    assert "internal_data" not in body["observation"]
    assert "WR-001" in body["observation"]["public_data"]["rule_ids"]
    _assert_no_raw_context(body)

    unknown_response = client.post(
        "/api/v1/qc-agent/tools/resolve_rule_scope/run",
        json={"document_alias": "unknown_doc", "qc_point_type": "unknown_qc"},
    )

    assert unknown_response.status_code == 200
    warnings = unknown_response.json()["observation"]["public_data"]["warnings"]
    assert any("未知文书" in item for item in warnings)
    assert any("未知质控点" in item for item in warnings)


def test_api_chat_direct_visit_id_completes_document_qc(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.post(
        "/api/v1/qc-agent/chat",
        json={"message": "对 visit_id=V001 的查房记录做完整性质控"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["parsed_intent"]["visit_id"] == "V001"
    assert body["parsed_intent"]["document_alias"] == "ward_round"
    assert body["parsed_intent"]["qc_point_type"] == "completeness"
    assert [item["tool_name"] for item in body["plan"]] == [
        "get_record_context",
        "select_record_documents",
        "resolve_rule_scope",
        "run_document_qc",
    ]
    assert body["result"]["record_summary"]["visit_id"] == "V001"
    assert "WR-001" in {rule["rule_id"] for rule in body["result"]["selected_rules"]}
    _assert_no_raw_context(body)


def test_api_chat_explicit_rule_ids_take_priority(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.post(
        "/api/v1/qc-agent/chat",
        json={"message": "对 visit_id=V001 的查房记录按 WR-001 和 DG-001 做质控"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["parsed_intent"]["rule_ids"] == ["WR-001", "DG-001"]
    assert body["plan"][2]["tool_name"] == "resolve_rule_scope"
    assert body["plan"][2]["status"] == "skipped"
    result = body["result"]
    assert "WR-001" in {rule["rule_id"] for rule in result["executed_rules"]}
    assert any(item["rule_id"] == "DG-001" for item in result["skipped_rules"])
    _assert_no_raw_context(body)


def test_api_chat_empty_record_context_needs_clarification(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.post(
        "/api/v1/qc-agent/chat",
        json={"message": "对 visit_id=V003 的查房记录做质控"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_clarification"
    assert body["parsed_intent"]["visit_id"] == "V003"
    assert [item["tool_name"] for item in body["plan"]] == ["get_record_context"]
    assert any("缺少可用文书文本" in item for item in body["warnings"])
    _assert_no_raw_context(body)


def test_api_chat_missing_target_document_needs_clarification(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.post(
        "/api/v1/qc-agent/chat",
        json={"message": "对 visit_id=V001 的会诊记录做质控"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_clarification"
    assert body["parsed_intent"]["document_alias"] == "consultation"
    assert [item["tool_name"] for item in body["plan"]] == [
        "get_record_context",
        "select_record_documents",
    ]
    assert any("未找到目标文书" in item for item in body["warnings"])
    _assert_no_raw_context(body)


def test_qc_agent_pi_harness_summarizes_http_error_envelope():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "run_qc_agent_pi_smoke_test.py"
    spec = importlib.util.spec_from_file_location("run_qc_agent_pi_smoke_test", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    case = module.RegressionCase(
        case_id="direct_ward_round_qc",
        message="对 visit_id=V003 的查房记录做质控",
        expected_statuses={"completed", "needs_clarification"},
    )
    response_data = {
        "success": False,
        "detail": "病历上下文缺少可用文书文本: visit_id=V003",
        "trace_id": "trace-001",
        "code": "CONTEXT_TEXT_MISSING",
        "_http_status": 422,
    }

    result = module.evaluate_case(case, response_data)

    assert result["passed"] is False
    assert result["response_summary"]["http_status"] == 422
    assert result["response_summary"]["code"] == "CONTEXT_TEXT_MISSING"
    assert result["response_summary"]["trace_id"] == "trace-001"
    assert "缺少可用文书文本" in result["response_summary"]["message"]
    assert "http_status=422" in result["error"]
    assert result["sensitive_leak_found"] is False


def test_api_chat_search_no_candidate_needs_clarification(client, qc_agent_auth):
    workspace = SearchResultWorkspace([])
    client.app.dependency_overrides[get_qc_agent_registry] = lambda: _registry_with_workspace(workspace)

    response = client.post(
        "/api/v1/qc-agent/chat",
        json={"message": "查一下患者赵六的病程记录有没有时效性问题"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_clarification"
    assert body["plan"][0]["tool_name"] == "search_records"
    assert body["candidates"] == []
    _assert_no_raw_context(body)


def test_api_chat_search_multi_candidate_needs_confirmation(client, qc_agent_auth):
    workspace = SearchResultWorkspace(
        [
            {
                "visit_id": "V001",
                "patient_id": "P001",
                "patient_name": "张三",
                "department": "神经内科",
                "doctor": "李医生",
                "admission_date": "2026-05-01",
                "discharge_date": "2026-05-08",
            },
            {
                "visit_id": "V002",
                "patient_id": "P002",
                "patient_name": "张三",
                "department": "中医科",
                "doctor": "王医生",
                "admission_date": "2026-05-02",
                "discharge_date": "2026-05-09",
            },
        ]
    )
    client.app.dependency_overrides[get_qc_agent_registry] = lambda: _registry_with_workspace(workspace)

    response = client.post(
        "/api/v1/qc-agent/chat",
        json={"message": "对中医科张三的查房记录做完整性和时效性质控"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_confirmation"
    assert len(body["candidates"]) == 2
    assert all("medical_text" not in str(item) for item in body["candidates"])
    assert [item["tool_name"] for item in body["plan"]] == ["search_records"]
    _assert_no_raw_context(body)


def test_api_chat_search_single_candidate_continues(client, qc_agent_auth):
    workspace = SearchResultWorkspace(
        [
            {
                "visit_id": "V001",
                "patient_id": "P001",
                "patient_name": "张三",
                "department": "神经内科",
                "doctor": "李医生",
                "admission_date": "2026-05-01",
                "discharge_date": "2026-05-08",
            }
        ]
    )
    client.app.dependency_overrides[get_qc_agent_registry] = lambda: _registry_with_workspace(workspace)

    response = client.post(
        "/api/v1/qc-agent/chat",
        json={"message": "查一下患者张三的病程记录有没有时效性问题"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["parsed_intent"]["visit_id"] == "V001"
    assert body["parsed_intent"]["document_alias"] == "course"
    assert body["parsed_intent"]["qc_point_type"] == "timeliness"
    assert [item["tool_name"] for item in body["plan"]][0] == "search_records"
    _assert_no_raw_context(body)


def test_api_chat_document_alias_mapping_and_ambiguous_message(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    discharge = client.post(
        "/api/v1/qc-agent/chat",
        json={"message": "质控 visit_id=V001 的出院记录"},
    )
    consultation = client.post(
        "/api/v1/qc-agent/chat",
        json={"message": "质控 visit_id=V001 的会诊记录"},
    )
    ambiguous = client.post(
        "/api/v1/qc-agent/chat",
        json={"message": "对 visit_id=V001 做质控"},
    )

    assert discharge.status_code == 200
    assert discharge.json()["parsed_intent"]["document_alias"] == "discharge"
    assert consultation.status_code == 200
    assert consultation.json()["parsed_intent"]["document_alias"] == "consultation"
    assert ambiguous.status_code == 200
    assert ambiguous.json()["status"] == "needs_clarification"


def test_api_chat_unsupported_write_intent(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.post(
        "/api/v1/qc-agent/chat",
        json={"message": "删除 visit_id=V001 的质控结果并写入正式表"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unsupported"
    assert body["plan"] == []
    assert any("不支持写入" in item for item in body["warnings"])


def test_api_rejects_page_size_overflow(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.post(
        "/api/v1/qc-agent/tools/search_records/run",
        json={"page_size": 51},
    )

    assert response.status_code == 422


def test_default_registry_contains_only_safe_search_tool():
    registry = register_default_tools(AgentToolRegistry())
    specs = registry.list_specs()

    by_name = {spec.name: spec for spec in specs}
    assert set(by_name) == {
        "search_records",
        "get_record_context",
        "run_frontpage_qc",
        "select_record_documents",
        "run_document_qc",
        "list_qc_rules",
        "resolve_rule_scope",
    }
    assert by_name["search_records"].writes_db is False
    assert by_name["search_records"].requires_confirmation is False
    assert by_name["get_record_context"].writes_db is False
    assert by_name["get_record_context"].requires_confirmation is False
    assert by_name["run_frontpage_qc"].writes_db is False
    assert by_name["run_frontpage_qc"].requires_confirmation is False
    assert by_name["select_record_documents"].writes_db is False
    assert by_name["select_record_documents"].requires_confirmation is False
    assert by_name["run_document_qc"].writes_db is False
    assert by_name["run_document_qc"].requires_confirmation is False
    assert by_name["list_qc_rules"].writes_db is False
    assert by_name["list_qc_rules"].requires_confirmation is False
    assert by_name["list_qc_rules"].max_records == 1
    assert by_name["resolve_rule_scope"].writes_db is False
    assert by_name["resolve_rule_scope"].requires_confirmation is False
    assert by_name["resolve_rule_scope"].max_records == 1
