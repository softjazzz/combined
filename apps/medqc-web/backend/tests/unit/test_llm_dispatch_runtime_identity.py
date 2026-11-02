from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import rule_decision_settings as runtime_settings


def _client(
    *,
    dispatch_mode: str = "direct",
    gateway_profile: str | None = None,
    gateway_hash: str | None = None,
):
    return SimpleNamespace(
        provider_code="alibaba",
        model="qwen3.8-flash",
        api_endpoint="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=0.2,
        top_p=0.9,
        max_tokens=16384,
        enable_thinking=True,
        thinking_budget=256,
        reasoning_effort="",
        allow_mock_when_unconfigured=False,
        dispatch_mode=dispatch_mode,
        gateway_profile=gateway_profile,
        gateway_endpoint_sha256=gateway_hash,
    )


def _service(**client_kwargs):
    return SimpleNamespace(
        client=_client(**client_kwargs),
        adjudicator_client=_client(**client_kwargs),
    )


def _as_v1(snapshot: dict) -> dict:
    legacy = deepcopy(snapshot)
    legacy["schema_version"] = 1
    for role in ("first_pass", "adjudicator"):
        for key in (
            "dispatch_mode", "gateway_profile", "gateway_endpoint_sha256"
        ):
            legacy[role].pop(key)
    return legacy


def test_legacy_v1_direct_snapshot_remains_compatible():
    service = _service()
    frozen = _as_v1(runtime_settings.capture_luxian_0609_task_runtime(service))
    runtime_settings.assert_luxian_0609_task_runtime_match(frozen, service)


def test_gateway_snapshot_freezes_profile_and_endpoint_hash():
    service = _service(
        dispatch_mode="gateway",
        gateway_profile="alibaba_first_pass",
        gateway_hash="a" * 64,
    )
    frozen = runtime_settings.capture_luxian_0609_task_runtime(service)
    assert frozen["schema_version"] == 2
    assert frozen["first_pass"]["dispatch_mode"] == "gateway"
    assert frozen["first_pass"]["gateway_profile"] == "alibaba_first_pass"
    assert frozen["first_pass"]["gateway_endpoint_sha256"] == "a" * 64

    service.client.gateway_profile = "alibaba_other"
    with pytest.raises(ValueError, match="已变化"):
        runtime_settings.assert_luxian_0609_task_runtime_match(frozen, service)


def test_legacy_v1_snapshot_cannot_silently_switch_to_gateway():
    direct = _service()
    frozen = _as_v1(runtime_settings.capture_luxian_0609_task_runtime(direct))
    gateway = _service(
        dispatch_mode="gateway",
        gateway_profile="alibaba_first_pass",
        gateway_hash="b" * 64,
    )
    with pytest.raises(ValueError, match="旧任务缺少Gateway运行身份"):
        runtime_settings.assert_luxian_0609_task_runtime_match(frozen, gateway)
