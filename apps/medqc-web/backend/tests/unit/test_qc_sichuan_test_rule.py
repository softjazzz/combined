from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.routers.qc_sichuan import (
    TestRuleRequest as RuleTestRequest,
    get_qc_service,
    test_rule as execute_test_rule,
)


@pytest.mark.parametrize("rule_id", ("LX0609-001", "LX0609-003", "LX0609-004", "LX0609-039"))
def test_test_rule_api_rejects_luxian_wrappers_before_any_engine_call(
    rule_id: str,
    app,
    client,
) -> None:
    engine = SimpleNamespace(evaluate=AsyncMock())
    service = SimpleNamespace(rule_engine=engine)
    app.dependency_overrides[get_qc_service] = lambda: service

    try:
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@medqc.com", "password": "admin888"},
        )
        assert login_response.status_code == 200, login_response.text
        response = client.post(
            "/api/v1/qc/sichuan/test-rule",
            json={"rule_id": rule_id, "medical_text": "仅含纯文本的测试输入"},
            headers={
                "Authorization": f"Bearer {login_response.json()['access_token']}"
            },
        )
    finally:
        app.dependency_overrides.pop(get_qc_service, None)

    assert response.status_code == 422
    body = response.json()
    detail = str(body.get("detail") or body.get("message") or body.get("error") or "")
    assert "客户样本验证" in detail
    assert "正式单规则入口" in detail
    engine.evaluate.assert_not_awaited()


@pytest.mark.asyncio
async def test_test_rule_keeps_non_luxian_engine_path_unchanged() -> None:
    target_rule = {
        "rule_id": "SC-001",
        "name": "普通四川规则",
        "category": "admission_record",
    }
    engine = SimpleNamespace(
        evaluate=AsyncMock(
            return_value={
                "rule_id": "SC-001",
                "rule_name": "普通四川规则",
                "is_compliant": True,
                "issues": [],
                "findings": "符合规则要求",
                "evidence": "普通文书证据",
                "suggestion": "",
                "confidence": 0.91,
                "applicability": {"is_applicable": True, "reason": ""},
                "metadata": {"tokens_used": 7},
            }
        )
    )
    service = SimpleNamespace(
        rule_engine=engine,
        get_rule_by_id=Mock(return_value=target_rule),
    )

    result = await execute_test_rule(
        request=SimpleNamespace(state=SimpleNamespace(trace_id="test-trace-id")),
        req=RuleTestRequest(rule_id="SC-001", medical_text="普通规则测试文本"),
        qc_service=service,
    )

    assert result["success"] is True
    assert result["data"]["rule_id"] == "SC-001"
    assert result["data"]["token_usage"] == {"total_tokens": 7}
    engine.evaluate.assert_awaited_once_with(
        rule=target_rule,
        medical_record={
            "id": "SC-001",
            "content": "普通规则测试文本",
            "document_type": "admission_record",
        },
    )


def test_test_rule_source_contains_no_legacy_luxian_decision_path() -> None:
    import inspect
    import app.routers.qc_sichuan as router

    source = inspect.getsource(router)

    for forbidden in (
        "_parse_luxian_datetime",
        "_extract_labeled_luxian_time",
        "_apply_luxian_time_rule",
        "_extract_luxian_section",
        "_apply_luxian_preop_surgeon_rule",
        "_apply_luxian_local_rule",
        "_normalize_luxian_single_test_result",
        "luxian_time_rule",
        "luxian_preop_surgeon_rule",
    ):
        assert forbidden not in source
