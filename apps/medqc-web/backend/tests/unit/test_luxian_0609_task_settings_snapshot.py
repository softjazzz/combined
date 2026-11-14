"""LX0609 正式任务创建快照和 Worker 前置配置门禁。"""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.core.settings import Settings
from app.services import sichuan_workspace_batch_worker as worker
from app.services.luxian_0609 import rule_decision_settings as runtime_identity
from app.services.luxian_0609.rule_decision_settings import (
    LX0609_TASK_SETTINGS_FILTER_KEY,
    LX0609_TASK_RUNTIME_FILTER_KEY,
    assert_luxian_0609_task_settings_match,
    capture_luxian_0609_task_settings,
    capture_luxian_0609_task_runtime,
    resolve_mainline_rule_decision_settings,
)
from tests.unit.test_qc_sichuan_batch_throughput import _ServiceStub, _WorkspaceStub


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, JWT_SECRET="synthetic-task-guard", **overrides)


def _snapshot(settings: Settings) -> dict:
    return capture_luxian_0609_task_settings(
        resolve_mainline_rule_decision_settings(settings)
    )


def test_snapshot_contains_only_effective_boolean_contract_and_ignores_capacity():
    base = _settings(LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=False)
    frozen = _snapshot(base)
    assert frozen["schema_version"] == 1
    assert len(frozen["flags"]) == 32
    assert frozen["flags"]["LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED"] is False
    assert frozen["flags"]["LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED"] is False
    assert frozen["flags"]["LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED"] is True
    assert all(type(value) is bool for value in frozen["flags"].values())
    assert not any("CONCURRENCY" in name or "SHADOW" in name or "API_KEY" in name for name in frozen["flags"])
    assert_luxian_0609_task_settings_match(
        frozen, resolve_mainline_rule_decision_settings(
            _settings(LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=False, LUXIAN_0609_FAMILY_MAX_CONCURRENCY=2)
        ),
    )


@pytest.mark.parametrize("damage", ["missing", "version", "field", "string_bool", "extra"])
def test_snapshot_rejects_legacy_or_malformed_without_truthy_string(damage: str):
    settings = _settings()
    frozen = deepcopy(_snapshot(settings))
    if damage == "missing":
        frozen = None
    elif damage == "version":
        frozen["schema_version"] = 2
    elif damage == "field":
        frozen["flags"].pop("LUXIAN_0609_TRIGGER_GATE_ENABLED")
    elif damage == "string_bool":
        frozen["flags"]["LUXIAN_0609_TRIGGER_GATE_ENABLED"] = "false"
    else:
        frozen["flags"]["LUXIAN_0609_UNKNOWN_ENABLED"] = False
    with pytest.raises(ValueError, match="快照缺失或非法"):
        assert_luxian_0609_task_settings_match(
            frozen, resolve_mainline_rule_decision_settings(settings),
        )


def test_snapshot_rejects_effective_medical_drift_but_not_equivalent_overlay():
    frozen = _snapshot(_settings(LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=False))
    equivalent = resolve_mainline_rule_decision_settings(
        _settings(
            LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=False,
            LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED=False,
        )
    )
    assert_luxian_0609_task_settings_match(frozen, equivalent)
    with pytest.raises(ValueError, match="配置已变化"):
        assert_luxian_0609_task_settings_match(
            frozen,
            resolve_mainline_rule_decision_settings(_settings(LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=True)),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["legacy", "invalid", "drift"])
async def test_worker_rejects_bad_snapshot_before_plan_and_source(
    monkeypatch: pytest.MonkeyPatch, damage: str,
):
    workspace = _WorkspaceStub()
    workspace.job["filters"] = {
        "rule_set_key": "luxian_0609_qc_v1", "rule_ids": ["LX0609-01-01-01"],
    }
    settings = _settings()
    failure_kwargs: dict = {}
    def _claim(*, job_id: str) -> str:
        assert job_id == workspace.job["id"]
        workspace.job["status"] = "running"
        return "attempt-1"
    def _fail(**kwargs: object) -> None:
        failure_kwargs.update(kwargs)
        workspace.job["status"] = "failed"
        workspace.job["error_message"] = kwargs["error_message"]
    monkeypatch.setattr(workspace, "mark_batch_job_running", _claim)
    monkeypatch.setattr(workspace, "is_batch_job_canceled_or_missing", lambda **_kwargs: False, raising=False)
    monkeypatch.setattr(workspace, "fail_batch_job", _fail)
    if damage != "legacy":
        frozen = _snapshot(settings)
        if damage == "invalid":
            frozen["flags"]["LUXIAN_0609_TRIGGER_GATE_ENABLED"] = "false"
        else:
            frozen["flags"]["LUXIAN_0609_TRIGGER_GATE_ENABLED"] = False
        workspace.job["filters"][LX0609_TASK_SETTINGS_FILTER_KEY] = frozen

    monkeypatch.setattr(worker, "get_product_activation_service", lambda: SimpleNamespace(enforce=lambda: None))
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(
        worker, "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: pytest.fail("配置校验之前不得构建医学计划"),
    )
    monkeypatch.setattr(
        workspace, "collect_records",
        lambda **_kwargs: pytest.fail("配置校验之前不得读取病例"),
    )

    async def _service_provider() -> object:
        return object()

    await worker.run_sichuan_workspace_batch_job(
        workspace.job["id"], workspace=workspace,
        qc_service_provider=_service_provider,
    )
    assert workspace.job["status"] == "failed"
    assert failure_kwargs["attempt_filters_json"] == "attempt-1"
    assert failure_kwargs["execution_error"]["reason_code"] == ("task_settings_changed" if damage == "drift" else "task_settings_missing")
    assert failure_kwargs["execution_error"]["retryable"] is False
    assert workspace.items == []


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["missing", "first_pass", "adjudicator", "release"])
async def test_worker_rejects_runtime_identity_drift_before_plan_or_record_read(
    monkeypatch: pytest.MonkeyPatch, change: str,
):
    workspace = _WorkspaceStub()
    workspace.job["filters"] = {
        "rule_set_key": "luxian_0609_qc_v1", "rule_ids": ["LX0609-01-01-01"],
    }
    settings = _settings()
    workspace.job["filters"][LX0609_TASK_SETTINGS_FILTER_KEY] = _snapshot(settings)
    version = {"available": True, "build_id": "medqc-web-customer-20260925-100000", "git_commit": "a" * 40}
    monkeypatch.setattr(runtime_identity, "_PROCESS_RUNTIME_BUILD", dict(version))
    qc_service = _ServiceStub()
    accepted = capture_luxian_0609_task_runtime(qc_service)
    if change != "missing":
        workspace.job["filters"][LX0609_TASK_RUNTIME_FILTER_KEY] = accepted
    if change == "first_pass":
        qc_service.client.model = "changed-model"
    elif change == "adjudicator":
        qc_service.adjudicator_client.model = "changed-review-model"
    elif change == "release":
        monkeypatch.setattr(runtime_identity, "_PROCESS_RUNTIME_BUILD", {
            **version, "build_id": "medqc-web-customer-20260925-110000",
        })

    failure_kwargs: dict = {}
    def _claim(*, job_id: str) -> str:
        assert job_id == workspace.job["id"]
        workspace.job["status"] = "running"
        return "attempt-identity"
    def _fail(**kwargs: object) -> None:
        failure_kwargs.update(kwargs)
        workspace.job["status"] = "failed"
        workspace.job["error_message"] = kwargs["error_message"]
    monkeypatch.setattr(workspace, "mark_batch_job_running", _claim)
    monkeypatch.setattr(workspace, "is_batch_job_canceled_or_missing", lambda **_kwargs: False, raising=False)
    monkeypatch.setattr(workspace, "fail_batch_job", _fail)
    monkeypatch.setattr(worker, "get_product_activation_service", lambda: SimpleNamespace(enforce=lambda: None))
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "build_luxian_0609_package_plan_from_settings", lambda **_kwargs: pytest.fail("漂移后不能规划"))
    monkeypatch.setattr(workspace, "collect_records", lambda **_kwargs: pytest.fail("漂移后不能读取病例"))

    async def _service_provider():
        return qc_service

    await worker.run_sichuan_workspace_batch_job(
        workspace.job["id"], workspace=workspace, qc_service_provider=_service_provider,
    )
    assert workspace.job["status"] == "failed"
    assert failure_kwargs["attempt_filters_json"] == "attempt-identity"
    expected_code = "task_runtime_missing" if change == "missing" else "task_runtime_changed"
    assert failure_kwargs["execution_error"]["reason_code"] == expected_code
    assert failure_kwargs["execution_error"]["retryable"] is False
    assert workspace.items == []
