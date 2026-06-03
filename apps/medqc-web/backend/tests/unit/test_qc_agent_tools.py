from __future__ import annotations

import pytest

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
from app.routers.qc_agent import get_qc_agent_registry
from app.services.qc_agent.schemas import SearchRecordsInput
from app.services.qc_agent.tool_registry import AgentToolRegistry
from app.services.qc_agent.tools import register_default_tools, search_records


class FakeWorkspace:
    def __init__(self) -> None:
        self.calls = []

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
        return [
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
        ]


def _assert_no_sensitive_keys(value):
    if isinstance(value, dict):
        assert "medical_text" not in value
        assert "record_content" not in value
        assert "documents" not in value
        assert "bundle" not in value
        for item in value.values():
            _assert_no_sensitive_keys(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_sensitive_keys(item)


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
    assert observation.public_data["total"] == 2
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

    assert observation.public_data["total"] == 2
    assert observation.public_data["page"] == 2
    assert observation.public_data["page_size"] == 1
    assert observation.public_data["records"][0]["visit_id"] == "V002"


def test_search_records_rejects_page_size_overflow():
    with pytest.raises(Exception):
        SearchRecordsInput(page_size=51)


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
    return registry


def test_api_list_tools_returns_search_records_schema(client, qc_agent_auth):
    client.app.dependency_overrides[get_qc_agent_registry] = _registry_with_fake_workspace

    response = client.get("/api/v1/qc-agent/tools")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["name"] == "search_records"
    assert body[0]["risk_level"] == "low"
    assert body[0]["writes_db"] is False
    assert body[0]["requires_confirmation"] is False
    assert body[0]["max_records"] == 50
    assert "input_schema" in body[0]


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
    _assert_no_sensitive_keys(body)


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

    assert [spec.name for spec in specs] == ["search_records"]
    assert specs[0].writes_db is False
    assert specs[0].requires_confirmation is False
