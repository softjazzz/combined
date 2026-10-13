import asyncio

import pytest

from app.services.luxian_0609.privacy_request_scope import (
    bind_luxian_0609_identity_provider,
    luxian_0609_privacy_scope,
    protect_current_payload,
)
from app.services.luxian_0609.llm_prompt_privacy import (
    PatientPrivacyViolation,
    PrivacyIdentityContextError,
)


@pytest.mark.asyncio
async def test_scope_guards_legacy_payload_and_restores_after_error():
    payload = {"messages": [{"role": "user", "content": "未标注身份的测试甲姓名"}]}

    @luxian_0609_privacy_scope
    async def run(*, rule_set_key):
        bind_luxian_0609_identity_provider(lambda: ("测试甲",))
        return protect_current_payload(payload)

    with pytest.raises(PatientPrivacyViolation):
        await run(rule_set_key="luxian_0609_qc_v1")
    assert protect_current_payload(payload) is payload


@pytest.mark.asyncio
async def test_scope_without_identity_initialization_fails_closed():
    @luxian_0609_privacy_scope
    async def run(*, rule_set_key):
        return protect_current_payload({"messages": []})

    with pytest.raises(PrivacyIdentityContextError):
        await run(rule_set_key="luxian_0609_qc_v1")


@pytest.mark.asyncio
async def test_concurrent_cases_and_nested_legacy_calls_keep_own_identity():
    @luxian_0609_privacy_scope
    async def legacy(*, rule_set_key="", text):
        await asyncio.sleep(0)
        return protect_current_payload({"messages": [{"content": text}]})

    @luxian_0609_privacy_scope
    async def run(*, rule_set_key, own, other):
        bind_luxian_0609_identity_provider(lambda: (own,))
        await legacy(text=other)
        with pytest.raises(PatientPrivacyViolation):
            await legacy(text=own)

    await asyncio.gather(
        run(rule_set_key="luxian_0609_qc_v1", own="测试甲", other="测试乙"),
        run(rule_set_key="luxian_0609_qc_v1", own="测试乙", other="测试甲"),
    )


@pytest.mark.asyncio
async def test_actual_http_boundary_blocks_before_observation_or_transport(monkeypatch):
    from app.services.qc_llm_client import SichuanQCLLMClient

    client = object.__new__(SichuanQCLLMClient)

    @luxian_0609_privacy_scope
    async def run(*, rule_set_key):
        bind_luxian_0609_identity_provider(lambda: ("测试甲",))
        # No recorder/client attributes exist: reaching them is a test failure.
        return await client._perform_observed_attempt(
            logical_call_id="synthetic",
            attempt_no=2,
            headers={},
            payload={"messages": [{"content": "测试甲"}]},
        )

    with pytest.raises(PatientPrivacyViolation):
        await run(rule_set_key="luxian_0609_qc_v1")


@pytest.mark.asyncio
async def test_scope_cancel_and_nested_exception_restore_context():
    payload = {"messages": [{"content": "合成甲"}]}

    @luxian_0609_privacy_scope
    async def inner(*, rule_set_key):
        bind_luxian_0609_identity_provider(lambda: ("合成乙",))
        assert protect_current_payload(payload) == payload
        raise asyncio.CancelledError()

    @luxian_0609_privacy_scope
    async def outer(*, rule_set_key):
        bind_luxian_0609_identity_provider(lambda: ("合成甲",))
        with pytest.raises(asyncio.CancelledError):
            await inner(rule_set_key=rule_set_key)
        with pytest.raises(PatientPrivacyViolation):
            protect_current_payload(payload)

    await outer(rule_set_key="luxian_0609_qc_v1")
    assert protect_current_payload(payload) is payload


@pytest.mark.asyncio
async def test_identity_rechecked_on_each_attempt_without_mutating_input():
    identities = ["合成甲"]
    payload = {"messages": [{"content": "合成乙"}]}

    @luxian_0609_privacy_scope
    async def run(*, rule_set_key):
        bind_luxian_0609_identity_provider(lambda: identities)
        assert protect_current_payload(payload) == payload
        identities.append("合成乙")
        with pytest.raises(PatientPrivacyViolation):
            protect_current_payload(payload)
        assert payload["messages"][0]["content"] == "合成乙"

    await run(rule_set_key="luxian_0609_qc_v1")


@pytest.mark.asyncio
async def test_safe_request_reaches_mock_transport_with_schema_numbers(monkeypatch):
    from unittest.mock import AsyncMock
    from types import SimpleNamespace
    import app.services.qc_llm_client as client_module

    client = object.__new__(client_module.SichuanQCLLMClient)
    client._observability_recorder = SimpleNamespace(
        start_attempt=AsyncMock(return_value=(None, 0)), finish_attempt=AsyncMock()
    )
    client.provider_code = "synthetic"
    client.model = "synthetic"
    client.model_role = "first_pass"
    client.api_endpoint = "https://offline.invalid"
    client.timeout_seconds = 1
    transport = AsyncMock(return_value={"choices": []})
    monkeypatch.setattr(client_module, "safe_post_json", transport)
    monkeypatch.setattr(
        client_module, "begin_diagnostic_attempt", lambda **kwargs: None
    )
    monkeypatch.setattr(
        client_module, "finish_diagnostic_attempt", lambda *args, **kwargs: None
    )
    payload = {
        "messages": [{"content": "合成无身份文本"}],
        "temperature": 1,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"schema": {"type": "array", "minItems": 1}},
        },
    }

    @luxian_0609_privacy_scope
    async def run(*, rule_set_key):
        bind_luxian_0609_identity_provider(lambda: ("1",))
        await client._perform_observed_attempt(
            logical_call_id="synthetic", attempt_no=1, headers={}, payload=payload
        )

    await run(rule_set_key="luxian_0609_qc_v1")
    transport.assert_awaited_once()
    assert transport.call_args.kwargs["payload"] == payload


@pytest.mark.asyncio
async def test_empty_provider_fails_closed():
    @luxian_0609_privacy_scope
    async def run(*, rule_set_key):
        bind_luxian_0609_identity_provider(lambda: ())
        return protect_current_payload({"messages": []})

    with pytest.raises(PrivacyIdentityContextError):
        await run(rule_set_key="luxian_0609_qc_v1")
