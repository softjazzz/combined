from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa

from app.routers.custom_qc import _workspace_rule_payload_from_draft
from app.services import custom_qc_workspace_service as workspace_module
from app.services.custom_qc_service import evaluate_inline_rule_orchestrated
from app.services.qc_rule_orchestrator import QCRuleOrchestrator
from tests.unit.test_custom_qc_draft_basic_info import (
    _basic_payload,
    _visual_condition,
    workspace,  # noqa: F401 - 复用隔离SQLite草稿fixture。
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("documents", "readiness", "expected_status"),
    [
        ([], "complete", "non_compliant"),
        ([{"document_id": "doc-1"}], "complete", "compliant"),
        ([], "partial", "data_gap"),
        ([], "unavailable", "technical_error"),
    ],
)
async def test_published_workspace_retains_visual_definition_and_never_calls_llm(
    workspace, monkeypatch, documents, readiness, expected_status,  # noqa: F811 - pytest按同名注入导入的fixture。
):
    service, sessions, drafts = workspace
    rules = sa.Table(
        "qc_rules", drafts.metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("rule_code", sa.String, unique=True),
        sa.Column("check_logic", sa.JSON),
        sa.Column("status", sa.String),
    )
    rules.create(sessions.kw["bind"])
    monkeypatch.setattr(workspace_module, "_qc_rules_table", lambda: rules)
    draft = service.create_basic_info_draft(created_by="manager-1", payload=_basic_payload())
    service.update_visual_condition_draft(
        draft_id=draft["id"], created_by="manager-1",
        expected_updated_at=draft["updated_at"], visual_condition=_visual_condition(),
    )
    # 发布门禁本身属于68；这里显式建立既有门禁证明，只验证发布搬运和执行路径。
    service.save_last_test_summary(
        draft_id=draft["id"], created_by="manager-1", summary={"success_count": 1},
    )
    service.publish_draft(draft_id=draft["id"], created_by="manager-1")
    published = service.get_draft(draft_id=draft["id"], created_by="manager-1")
    assert published["status"] == "published"
    assert published["check_logic"]["visual_condition"] == _visual_condition()
    with sessions() as session:
        saved = session.execute(sa.select(rules.c.check_logic)).scalar_one()
    assert saved["visual_condition"] == _visual_condition()

    llm = AsyncMock(side_effect=AssertionError("可视化条件不得回退LLM"))
    qc_service = SimpleNamespace(
        client=SimpleNamespace(model="test-no-network"),
        rule_engine=SimpleNamespace(evaluate=llm),
        rule_orchestrator=QCRuleOrchestrator(), execution_cache=None,
    )
    result = await evaluate_inline_rule_orchestrated(
        qc_service=qc_service,
        rule=_workspace_rule_payload_from_draft(published),
        record={
            "record_id": "record-1", "institute_id": "hospital-1",
            "patient_id": "patient-1", "visit_id": "visit-1", "medical_text": "",
            "evidence_payload": {"programmatic_timeline": {
                "documents": {"first_course_record": documents},
                "source_readiness": {"first_course_record": readiness},
            }},
        },
    )
    assert result["status"] == expected_status
    assert result["is_compliant"] is (expected_status == "compliant")
    assert result["performance"]["token_usage"] == 0
    llm.assert_not_awaited()
