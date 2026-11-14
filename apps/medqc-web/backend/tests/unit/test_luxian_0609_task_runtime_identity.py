"""LX0609 已接纳任务的模型与实现身份只读边界。"""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.core.settings import get_settings
from app.services import sichuan_workspace_batch_worker as worker
from app.services.luxian_0609 import rule_decision_settings as identity
from app.services.luxian_0609.rule_decision_settings import (
    LX0609_TASK_RUNTIME_FILTER_KEY,
    LX0609_TASK_SETTINGS_FILTER_KEY,
    capture_luxian_0609_task_settings,
    resolve_mainline_rule_decision_settings,
)
from app.services.sichuan_qc_service import SichuanQCService
from tests.unit.test_qc_sichuan_batch_throughput import _WorkspaceStub


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
    for damaged in (None, {}, {**frozen, "schema_version": 3}, {**frozen, "schema_version": True}, {**frozen, "first_pass": float("nan")}):
        with pytest.raises(ValueError, match="快照缺失或非法"):
            identity.assert_luxian_0609_task_runtime_match(damaged, service)
    changed = deepcopy(frozen)
    changed["first_pass"]["endpoint_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="模型或实现版本已变化"):
        identity.assert_luxian_0609_task_runtime_match(changed, service)


def test_running_luxian_job_keeps_accepted_clients_after_global_config_reload():
    """领取后的服务须与可热重载的全局服务分离，一审和二审均不能串版本。"""

    config = {
        "provider_code": "alibaba",
        "api_endpoint": "https://example.invalid/llm-a",
        "api_key": "test-secret-a",
        "model": "model-a",
        "timeout_seconds": 30,
        "source": "test",
        "custom_parameters": {
            "temperature": 0.1, "top_p": 0.8, "max_tokens": 2048,
            "execution_concurrency": {
                "max_parallel_records": 16,
                "family_max_concurrency": 4,
                "http_max_concurrency": 40,
            },
        },
    }
    shared = SichuanQCService(config)
    accepted = identity.capture_luxian_0609_task_runtime(shared)
    running = shared.isolated_luxian_0609_runtime()
    identity.assert_luxian_0609_task_runtime_match(accepted, running)
    assert running is not shared
    assert running.client is not shared.client
    assert running.adjudicator_client is not shared.adjudicator_client
    assert running.rule_engine._llm_generate.__self__ is running

    # 重载接口原地修改全局客户端；固定的运行实例必须保留接纳时的密钥、模型和参数。
    shared.client.api_endpoint = "https://example.invalid/llm-b"
    shared.client.api_key = "test-secret-b"
    shared.client.model = "model-b"
    shared.client.temperature = 0.9
    shared.adjudicator_client.model = "model-review-b"
    with pytest.raises(ValueError, match="模型或实现版本已变化"):
        identity.assert_luxian_0609_task_runtime_match(accepted, shared)
    identity.assert_luxian_0609_task_runtime_match(accepted, running)
    assert running.client.api_key == "test-secret-a"
    assert running.client.temperature == 0.1
    assert running.adjudicator_client.model != "model-review-b"


@pytest.mark.asyncio
@pytest.mark.parametrize(("record_count", "sample_pool", "child", "expected_limit"), [
    (0, False, False, 4),
    (1, True, False, 4),
    (2, True, False, 4),
    (1, True, True, 4),
    (1, False, False, 4),
])
async def test_formal_worker_isolates_real_service_before_reading_records(
    monkeypatch, record_count, sample_pool, child, expected_limit,
):
    workspace = _WorkspaceStub()
    workspace.job["filters"] = {
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_ids": ["LX0609-01-01-01"],
        "record_refs": [
            {"institute_id": "inst", "patient_id": f"case-{i}", "visit_id": f"visit-{i}"}
            for i in range(record_count)
        ],
    }
    if sample_pool:
        workspace.job["filters"]["sample_pool_id"] = "pool-test"
    if child:
        workspace.job["parent_job_id"] = "parent-test"
    shared = SichuanQCService({
        "provider_code": "alibaba", "api_endpoint": "https://example.invalid/llm",
        "api_key": "test-secret", "model": "model-a", "source": "test",
    })
    isolated: list[SichuanQCService] = []
    original = SichuanQCService.isolated_luxian_0609_runtime

    def record_isolation(self, **kwargs):
        result = original(self, **kwargs)
        isolated.append(result)
        return result

    class Activation:
        def enforce(self):
            return None

    monkeypatch.setattr(SichuanQCService, "isolated_luxian_0609_runtime", record_isolation)
    monkeypatch.setattr(worker, "get_product_activation_service", lambda: Activation())
    monkeypatch.setattr(
        workspace, "fail_batch_job",
        lambda **_kwargs: workspace.job.update(status="failed"),
    )

    async def provide():
        return shared

    # 故意不附任务设置快照：Worker 必须在读取任何病例前拒绝，且已隔离客户端。
    await worker.run_sichuan_workspace_batch_job(
        workspace.job["id"], workspace=workspace, qc_service_provider=provide,
    )
    assert len(isolated) == 1
    assert isolated[0].client is not shared.client
    assert isolated[0].client.family_max_concurrency == expected_limit
    assert isolated[0].adjudicator_client.family_max_concurrency == expected_limit
    assert (
        isolated[0].luxian_0609_execution_concurrency.family_max_concurrency
        == expected_limit
    )
    assert shared.client.family_max_concurrency == 4
    assert workspace.job["status"] == "failed"


@pytest.mark.parametrize(("single_limit", "expected_limit"), [(1, 1), (6, 4), (8, 4)])
def test_single_record_family_budget_only_tightens_accepted_policy(
    monkeypatch, single_limit, expected_limit,
):
    from app.core.settings import Settings
    from app.services import sichuan_qc_service as service_module

    settings = Settings(_env_file=None, JWT_SECRET="test-only-budget",
                        LUXIAN_0609_SINGLE_RECORD_FAMILY_MAX_CONCURRENCY=single_limit)
    monkeypatch.setattr(service_module, "get_settings", lambda: settings)
    shared = SichuanQCService({
        "provider_code": "alibaba", "api_endpoint": "https://example.invalid/llm",
        "api_key": "test-secret", "model": "model-a", "source": "test",
        "custom_parameters": {"execution_concurrency": {
            "max_parallel_records": 16, "family_max_concurrency": 4, "http_max_concurrency": 40,
        }},
    })
    single = shared.isolated_luxian_0609_runtime(single_record=True)
    batch = shared.isolated_luxian_0609_runtime(single_record=False)
    assert single.client.family_max_concurrency == expected_limit
    assert single.adjudicator_client.family_max_concurrency == expected_limit
    assert single.luxian_0609_execution_concurrency.family_max_concurrency == expected_limit
    assert batch.client.family_max_concurrency == shared.client.family_max_concurrency == 4
    assert batch.adjudicator_client.family_max_concurrency == 4
    assert single.client.http_max_concurrency == batch.client.http_max_concurrency == 40
    assert single.client.max_parallel_records == batch.client.max_parallel_records == 16
    assert single.rule_engine._llm_generate.__self__ is single


def test_isolated_runtime_keeps_non_sensitive_gateway_routing(monkeypatch):
    """隔离任务复制模式/profile，不复制 Gateway URL 或 token。"""

    from app.services import qc_llm_client as client_module

    monkeypatch.setattr(
        client_module,
        "get_settings",
        lambda: SimpleNamespace(
            LLM_DISPATCH_MODE="gateway",
            LLM_GATEWAY_PROFILE="alibaba-qc",
            LLM_GATEWAY_URL="https://gateway.example.invalid",
        ),
    )

    shared = SichuanQCService({
        "provider_code": "alibaba", "api_endpoint": "https://example.invalid/llm",
        "api_key": "test-secret", "model": "model-a", "source": "test",
    })
    for client in (shared.client, shared.adjudicator_client):
        client.dispatch_mode = "gateway"
        client.gateway_profile = "alibaba-qc"
        client.refresh_dispatch_identity()
        client.gateway_url = "https://gateway.example.invalid/private"
        client.gateway_token = "gateway-private-token"

    running = shared.isolated_luxian_0609_runtime()

    for client in (running.client, running.adjudicator_client):
        runtime_config = SichuanQCService._client_runtime_config(client)
        assert client.dispatch_mode == runtime_config["dispatch_mode"] == "gateway"
        assert client.gateway_profile == runtime_config["gateway_profile"] == "alibaba-qc"
        assert "gateway_url" not in runtime_config
        assert "gateway_token" not in runtime_config
        assert not hasattr(client, "gateway_url")
        assert not hasattr(client, "gateway_token")


@pytest.mark.asyncio
async def test_isolated_client_usage_remains_in_process_statistics(monkeypatch):
    shared = SichuanQCService({
        "provider_code": "alibaba", "api_endpoint": "https://example.invalid/llm",
        "api_key": "test-secret", "model": "model-a", "source": "test",
    })
    running = shared.isolated_luxian_0609_runtime()

    async def fake_attempt(**_kwargs):
        return (
            {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]},
            {"input_tokens": 7, "output_tokens": 5, "total_tokens": 12},
        )

    monkeypatch.setattr(running.client, "_perform_observed_attempt", fake_attempt)
    await running.client.generate("合成输入")
    assert running.client.stats()["total_tokens"] == 12
    assert shared.client.stats()["total_calls"] == 1
    assert shared.client.stats()["total_tokens"] == 12
    assert shared.client.stats()["success_calls"] == 1

    async def failed_attempt(**_kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(running.client, "_perform_observed_attempt", failed_attempt)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        await running.client.generate("合成输入")
    assert running.client.stats()["total_calls"] == 2
    assert shared.client.stats()["total_calls"] == 2
    assert shared.client.stats()["error_calls"] == 1
    assert shared.client.stats()["total_tokens"] == 12


@pytest.mark.asyncio
@pytest.mark.parametrize("same_release", [True, False])
async def test_formal_worker_checks_release_identity_before_record_read(
    monkeypatch, same_release,
):
    original_release = {
        "available": True,
        "build_id": "medqc-web-customer-20260925-100000",
        "git_commit": "a" * 40,
    }
    monkeypatch.setattr(identity, "_PROCESS_RUNTIME_BUILD", original_release)
    config = {
        "provider_code": "alibaba", "api_endpoint": "https://example.invalid/llm",
        "api_key": "test-secret", "model": "model-a", "source": "test",
    }
    accepted = SichuanQCService(config)
    workspace = _WorkspaceStub()
    workspace.job["filters"] = {
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_ids": ["LX0609-01-01-01"],
        LX0609_TASK_SETTINGS_FILTER_KEY: capture_luxian_0609_task_settings(
            resolve_mainline_rule_decision_settings(get_settings())
        ),
        LX0609_TASK_RUNTIME_FILTER_KEY: identity.capture_luxian_0609_task_runtime(accepted),
    }
    resumed_release = dict(original_release)
    if not same_release:
        resumed_release["build_id"] = "medqc-web-customer-20260925-110000"
    monkeypatch.setattr(identity, "_PROCESS_RUNTIME_BUILD", resumed_release)
    resumed = SichuanQCService(config)
    errors: list[str] = []
    gate_reached = []
    failures = []

    class Activation:
        def enforce(self):
            return None

    def fail_batch_job(**kwargs):
        errors.append(kwargs["error_message"])
        failures.append(kwargs["execution_error"])
        workspace.job["status"] = "failed"

    def stop_after_runtime_gate(*_args, **_kwargs):
        gate_reached.append(True)
        raise RuntimeError("passed-runtime-gate")

    monkeypatch.setattr(worker, "get_product_activation_service", lambda: Activation())
    monkeypatch.setattr(workspace, "fail_batch_job", fail_batch_job)
    monkeypatch.setattr(
        worker, "assert_luxian_0609_customer_native_delivery_ready",
        stop_after_runtime_gate,
    )
    monkeypatch.setattr(
        workspace, "collect_records",
        lambda **_kwargs: pytest.fail("运行身份检查前不得读取病例"),
    )

    async def provide():
        return resumed

    await worker.run_sichuan_workspace_batch_job(
        workspace.job["id"], workspace=workspace, qc_service_provider=provide,
    )
    assert len(errors) == 1
    if same_release:
        assert gate_reached == [True]
        assert failures[0]["reason_code"] == "execution_program_error"
        assert "passed-runtime-gate" not in errors[0]
    else:
        assert gate_reached == []
        assert failures[0]["reason_code"] == "task_runtime_changed"
        assert failures[0]["retryable"] is False
        assert "模型或实现版本已变化" in errors[0]
