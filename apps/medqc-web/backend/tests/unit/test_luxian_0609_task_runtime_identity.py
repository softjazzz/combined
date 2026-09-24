"""LX0609 已接纳任务的模型与实现身份只读边界。"""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import rule_decision_settings as identity


def _service(*, model: str = "model-a", adjudicator: str = "model-review") -> SimpleNamespace:
    def client(name: str) -> SimpleNamespace:
        return SimpleNamespace(
            provider_code="alibaba", model=name,
            api_endpoint="https://example.invalid/llm", api_key="private-key",
            temperature=0.2, top_p=0.9, max_tokens=16384,
            enable_thinking=False, thinking_budget=None, reasoning_effort="",
            allow_mock_when_unconfigured=False,
        )

    return SimpleNamespace(client=client(model), adjudicator_client=client(adjudicator))


def test_runtime_identity_excludes_secrets_and_rejects_model_or_parameter_drift(monkeypatch):
    monkeypatch.setattr(identity, "_PROCESS_RUNTIME_BUILD", {"available": False})
    accepted = _service()
    frozen = identity.capture_luxian_0609_task_runtime(accepted)
    assert frozen["implementation"]["kind"] == "process"
    assert "private-key" not in str(frozen)
    assert "https://example.invalid/llm" not in str(frozen)
    identity.assert_luxian_0609_task_runtime_match(frozen, _service())

    for changed in (
        _service(model="model-b"),
        _service(adjudicator="model-review-b"),
        _service(),
    ):
        if changed.client.model == "model-a" and changed.adjudicator_client.model == "model-review":
            changed.client.enable_thinking = True
        with pytest.raises(ValueError, match="模型或实现版本已变化"):
            identity.assert_luxian_0609_task_runtime_match(frozen, changed)


def test_runtime_identity_rejects_redeployment_before_execution(monkeypatch):
    version = {"available": True, "build_id": "medqc-web-customer-20260925-100000", "git_commit": "a" * 40}
    monkeypatch.setattr(identity, "_PROCESS_RUNTIME_BUILD", dict(version))
    frozen = identity.capture_luxian_0609_task_runtime(_service())
    identity.assert_luxian_0609_task_runtime_match(frozen, _service())
    monkeypatch.setattr(identity, "_PROCESS_RUNTIME_BUILD", {
        **version, "build_id": "medqc-web-customer-20260925-110000",
    })
    with pytest.raises(ValueError, match="模型或实现版本已变化"):
        identity.assert_luxian_0609_task_runtime_match(frozen, _service())


def test_runtime_identity_does_not_read_overwritten_build_file(monkeypatch):
    version = {"available": True, "build_id": "medqc-web-customer-20260925-100000", "git_commit": "a" * 40}
    monkeypatch.setattr(identity, "_PROCESS_RUNTIME_BUILD", version)
    frozen = identity.capture_luxian_0609_task_runtime(_service())
    monkeypatch.setattr(
        identity, "load_runtime_build",
        lambda: pytest.fail("旧进程不得重新读取安装目录的发布声明"),
    )
    identity.assert_luxian_0609_task_runtime_match(frozen, _service())


def test_unversioned_development_task_rejects_cross_process_resume(monkeypatch):
    monkeypatch.setattr(identity, "_PROCESS_RUNTIME_BUILD", {"available": False})
    frozen = identity.capture_luxian_0609_task_runtime(_service())
    monkeypatch.setattr(identity, "_UNVERSIONED_PROCESS_ID", "another-process")
    with pytest.raises(ValueError, match="模型或实现版本已变化"):
        identity.assert_luxian_0609_task_runtime_match(frozen, _service())


def test_runtime_identity_rejects_missing_or_corrupt_snapshot(monkeypatch):
    monkeypatch.setattr(identity, "_PROCESS_RUNTIME_BUILD", {"available": False})
    service = _service()
    frozen = identity.capture_luxian_0609_task_runtime(service)
    for damaged in (None, {}, {**frozen, "schema_version": 2}, {**frozen, "schema_version": True}, {**frozen, "first_pass": float("nan")}):
        with pytest.raises(ValueError, match="快照缺失或非法"):
            identity.assert_luxian_0609_task_runtime_match(damaged, service)
    changed = deepcopy(frozen)
    changed["first_pass"]["endpoint_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="模型或实现版本已变化"):
        identity.assert_luxian_0609_task_runtime_match(changed, service)
