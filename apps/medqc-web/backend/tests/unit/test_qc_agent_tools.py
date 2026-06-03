from __future__ import annotations

import pytest

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
from app.routers.qc_agent import get_qc_agent_registry
from app.services.qc_agent.schemas import (
    GetRecordContextInput,
    RunDocumentQCInput,
    RunFrontpageQCInput,
    SearchRecordsInput,
    SelectRecordDocumentsInput,
)
from app.services.qc_agent.tool_registry import AgentToolRegistry
from app.services.qc_agent.tools import (
    get_record_context,
    register_default_tools,
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
    assert public_data["qc_summary"]["issue_count"] == public_data["qc_summary"]["failed"]
    assert all(issue["passed"] is False for issue in public_data["issues"])
    assert observation.internal_data is not None
    assert observation.internal_data["selected_documents"][0]["text"]
    _assert_no_raw_context(public_data)


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


def _registry_with_fake_workspace() -> AgentToolRegistry:
    registry = AgentToolRegistry()
    workspace = FakeWorkspace()

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
    return registry


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
