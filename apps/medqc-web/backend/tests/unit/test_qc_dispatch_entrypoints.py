"""M2 HTTP 入口按持久调度身份分流，且 Web 恢复不接管 MQ 任务。"""

from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.settings import Settings
from app.core.security import get_current_user
from app.routers import qc_sample_pools, qc_sichuan
from app.services.llm_dispatch.provider_profiles import ProviderConfigurationError
from app.services.qc_dispatch.dispatcher import (
    QCDispatchEntrypointError,
    assert_new_qc_task_dispatch_ready,
    persisted_qc_dispatch_mode,
    should_submit_detached_qc_task,
)
from app.services.qc_dispatch.repository import QCDispatchSchemaUnavailable
from app.services.product_activation import require_product_activation
from tests.unit.test_qc_sample_pools_router import (
    _SamplePoolServiceStub,
    _WorkspaceServiceStub as _SampleWorkspaceStub,
    _build_request,
    _run_record_ref,
)
from tests.unit.test_qc_sichuan_batch_throughput import (
    _ServiceStub,
    _WorkspaceStub,
)


def _main_settings(
    *,
    qc_mode: str = "legacy",
    llm_mode: str = "direct",
) -> Settings:
    gateway = (
        {
            "LLM_GATEWAY_URL": "http://127.0.0.1:8765/gateway",
            "LLM_GATEWAY_TOKEN": "entrypoint-test-token-0123456789abcdef",
            "LLM_GATEWAY_PROFILE": "alibaba_first_pass",
        }
        if llm_mode == "gateway"
        else {}
    )
    return Settings(
        _env_file=None,
        JWT_SECRET="entrypoint-test-secret",
        QC_TASK_DISPATCH_MODE=qc_mode,
        LLM_DISPATCH_MODE=llm_mode,
        **gateway,
    )


def _gateway_service() -> _ServiceStub:
    service = _ServiceStub()
    for client in (service.client, service.adjudicator_client):
        client.dispatch_mode = "gateway"
        client.gateway_profile = "alibaba_first_pass"
        client.gateway_endpoint_sha256 = "a" * 64
    return service


def _gateway_runtime_snapshot() -> dict[str, Any]:
    identity = {
        "dispatch_mode": "gateway",
        "gateway_profile": "alibaba_first_pass",
        "gateway_endpoint_sha256": "a" * 64,
    }
    return {"first_pass": dict(identity), "adjudicator": dict(identity)}


class _PersistingWorkspace(_WorkspaceStub):
    def __init__(self, *, persisted_mode: str) -> None:
        super().__init__()
        self.persisted_mode = persisted_mode

    def create_batch_job(self, **kwargs: Any) -> dict[str, Any]:
        job = super().create_batch_job(**kwargs)
        if (job.get("filters") or {}).get(
            "rule_set_key"
        ) == qc_sichuan.LUXIAN_0609_RULE_SET_KEY:
            if self.persisted_mode == "rabbitmq":
                job["filters"]["qc_dispatch"] = {
                    "schema_version": 1,
                    "mode": "rabbitmq",
                }
            self.created_job = dict(job)
        return job


class _PersistingSampleWorkspace(_SampleWorkspaceStub):
    def __init__(self, *, persisted_mode: str) -> None:
        super().__init__()
        self.persisted_mode = persisted_mode

    def create_batch_job(self, **kwargs: Any) -> dict[str, Any]:
        job = super().create_batch_job(**kwargs)
        if (
            (job.get("filters") or {}).get("rule_set_key")
            == qc_sample_pools.LUXIAN_0609_QC_RULE_SET_KEY
            and self.persisted_mode == "rabbitmq"
        ):
            job["filters"]["qc_dispatch"] = {
                "schema_version": 1,
                "mode": "rabbitmq",
            }
            self.create_batch_job_calls[-1]["filters"] = job["filters"]
        return job


def test_main_settings_default_to_legacy_and_reject_unknown_mode() -> None:
    assert _main_settings().QC_TASK_DISPATCH_MODE == "legacy"
    with pytest.raises(ValidationError):
        _main_settings(qc_mode="unknown")


def test_dispatch_changes_keep_auth_and_activation_dependencies() -> None:
    sample_parameters = inspect.signature(
        qc_sample_pools.run_sample_pool_intrinsic_validation
    ).parameters
    create_parameters = inspect.signature(
        qc_sichuan.create_workspace_batch_job
    ).parameters
    retry_parameters = inspect.signature(
        qc_sichuan.retry_workspace_batch_job
    ).parameters

    assert sample_parameters["current_user"].default.dependency is get_current_user
    assert sample_parameters["_"].default.dependency is require_product_activation
    assert (
        create_parameters["current_user"].default.dependency
        is require_product_activation
    )
    assert (
        retry_parameters["current_user"].default.dependency
        is require_product_activation
    )


def test_new_task_mode_requires_gateway_only_for_eligible_luxian_leaf() -> None:
    rabbit_without_gateway = _main_settings(qc_mode="rabbitmq")
    assert (
        assert_new_qc_task_dispatch_ready(
            eligible_for_rabbitmq=False,
            settings=rabbit_without_gateway,
        )
        == "legacy"
    )
    with pytest.raises(QCDispatchEntrypointError, match="LLM Gateway"):
        assert_new_qc_task_dispatch_ready(
            eligible_for_rabbitmq=True,
            settings=rabbit_without_gateway,
        )
    assert (
        assert_new_qc_task_dispatch_ready(
            eligible_for_rabbitmq=True,
            task_runtime_snapshot=_gateway_runtime_snapshot(),
            settings=_main_settings(qc_mode="rabbitmq", llm_mode="gateway"),
        )
        == "rabbitmq"
    )


def test_persisted_mode_not_hot_setting_controls_detached_submission() -> None:
    legacy = {"filters": {}}
    rabbitmq = {
        "filters": {
            "qc_dispatch": {"schema_version": 1, "mode": "rabbitmq"},
        }
    }
    assert persisted_qc_dispatch_mode(legacy) == "legacy"
    assert should_submit_detached_qc_task(legacy) is True
    assert persisted_qc_dispatch_mode(rabbitmq) == "rabbitmq"
    assert should_submit_detached_qc_task(rabbitmq) is False
    with pytest.raises(ValueError):
        persisted_qc_dispatch_mode(
            {"filters": {"qc_dispatch": {"schema_version": 1, "mode": "invalid"}}}
        )
    with pytest.raises(ValueError):
        persisted_qc_dispatch_mode({"filters": []})


@pytest.mark.asyncio
async def test_workspace_mq_create_returns_queued_without_detached_submit(
    monkeypatch,
) -> None:
    workspace = _PersistingWorkspace(persisted_mode="rabbitmq")
    settings = _main_settings(qc_mode="rabbitmq", llm_mode="gateway")
    submitted: list[tuple[Any, ...]] = []
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "get_settings", lambda: settings)
    monkeypatch.setattr(
        qc_sichuan,
        "submit_detached_task",
        lambda *args, **_kwargs: submitted.append(args),
    )

    response = await qc_sichuan.create_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
        payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
            rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
            scope="final",
            record_refs=[_run_record_ref()],
            rule_ids=["LX0609-01-01-01"],
        ),
        current_user={"id": "tester"},
        qc_service=_gateway_service(),  # type: ignore[arg-type]
    )

    assert response["data"]["status"] == "queued"
    assert response["data"]["filters"]["qc_dispatch"]["mode"] == "rabbitmq"
    assert submitted == []


@pytest.mark.asyncio
async def test_workspace_mq_configuration_failure_precedes_job_insert(
    monkeypatch,
) -> None:
    workspace = _PersistingWorkspace(persisted_mode="rabbitmq")
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        qc_sichuan,
        "get_settings",
        lambda: _main_settings(qc_mode="rabbitmq", llm_mode="direct"),
    )

    with pytest.raises(HTTPException) as rejected:
        await qc_sichuan.create_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
                scope="final",
                record_refs=[_run_record_ref()],
                rule_ids=["LX0609-01-01-01"],
            ),
            current_user={"id": "tester"},
            qc_service=_ServiceStub(),  # type: ignore[arg-type]
        )

    assert rejected.value.status_code == 503
    assert workspace.created_job is None


@pytest.mark.asyncio
async def test_workspace_mq_rejects_direct_actual_service_identity(monkeypatch) -> None:
    workspace = _PersistingWorkspace(persisted_mode="rabbitmq")
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        qc_sichuan,
        "get_settings",
        lambda: _main_settings(qc_mode="rabbitmq", llm_mode="gateway"),
    )

    with pytest.raises(HTTPException) as rejected:
        await qc_sichuan.create_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
                scope="final",
                record_refs=[_run_record_ref()],
                rule_ids=["LX0609-01-01-01"],
            ),
            current_user={"id": "tester"},
            qc_service=_ServiceStub(),  # type: ignore[arg-type]
        )

    assert rejected.value.status_code == 503
    assert workspace.created_job is None


@pytest.mark.asyncio
async def test_workspace_mq_schema_failure_is_controlled_and_not_submitted(
    monkeypatch,
) -> None:
    class _MissingSchemaWorkspace(_PersistingWorkspace):
        def create_batch_job(self, **_kwargs: Any) -> dict[str, Any]:
            raise QCDispatchSchemaUnavailable("qc dispatch schema is unavailable")

    workspace = _MissingSchemaWorkspace(persisted_mode="rabbitmq")
    submitted: list[tuple[Any, ...]] = []
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        qc_sichuan,
        "get_settings",
        lambda: _main_settings(qc_mode="rabbitmq", llm_mode="gateway"),
    )
    monkeypatch.setattr(
        qc_sichuan,
        "submit_detached_task",
        lambda *args, **_kwargs: submitted.append(args),
    )

    with pytest.raises(HTTPException) as rejected:
        await qc_sichuan.create_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
                scope="final",
                record_refs=[_run_record_ref()],
                rule_ids=["LX0609-01-01-01"],
            ),
            current_user={"id": "tester"},
            qc_service=_gateway_service(),  # type: ignore[arg-type]
        )

    assert rejected.value.status_code == 503
    assert submitted == []


@pytest.fixture
def retry_account_store(monkeypatch):
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.database import connection
    from app.database.models.v36_reports import SysUser

    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SysUser.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(connection, "SessionLocal", sessions)
    with sessions.begin() as session:
        session.add(SysUser(id="tester", username="tester", display_name="合成入口账号",
                            role="qc_manager", institute_id="synthetic-institute", is_active=True))
    yield
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("persisted_mode", "expected_submit_count"),
    [("legacy", 1), ("rabbitmq", 0)],
)
async def test_retry_uses_persisted_task_mode(
    monkeypatch, retry_account_store,
    persisted_mode: str,
    expected_submit_count: int,
) -> None:
    filters = {"rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
               "record_refs": [{"institute_id": "synthetic-institute",
                                "patient_id": "synthetic-patient", "visit_id": "synthetic-visit"}]}
    if persisted_mode == "rabbitmq":
        filters["qc_dispatch"] = {"schema_version": 1, "mode": "rabbitmq"}
    job = {
        "id": "retry-successor",
        "draft_id": "sichuan-rule-library",
        "status": "queued",
        "job_kind": "leaf",
        "filters": filters,
    }

    qc_service = _gateway_service()
    accepted_runtime = qc_sichuan.capture_luxian_0609_task_runtime(qc_service)

    class _RetryWorkspace:
        def get_batch_job(self, *, job_id: str, created_by: str) -> dict[str, Any]:
            assert (job_id, created_by) == ("retry-job", "tester")
            return {**job, "id": "retry-job", "status": "failed"}

        def retry_batch_job(self, **kwargs: Any) -> dict[str, Any]:
            assert kwargs["job_id"] == "retry-job"
            assert kwargs["task_runtime_snapshot"] == accepted_runtime
            return job

    async def provider():
        return qc_service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", provider)

    submitted: list[tuple[Any, ...]] = []
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", _RetryWorkspace)
    monkeypatch.setattr(
        qc_sichuan,
        "submit_detached_task",
        lambda *args, **_kwargs: submitted.append(args),
    )

    response = await qc_sichuan.retry_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
        job_id="retry-job",
        current_user={"id": "tester"},
    )

    assert response["data"]["status"] == "queued"
    assert len(submitted) == expected_submit_count
    assert response["data"]["id"] == "retry-successor"
    if submitted:
        assert submitted[0][2] == "retry-successor"


def test_web_startup_resume_uses_repository_legacy_filter(monkeypatch) -> None:
    calls: list[tuple[str, Any]] = []

    class _RecoveryWorkspace:
        def list_queued_luxian_0609_batch_job_ids(
            self,
            *,
            dispatch_mode: str = "legacy",
        ) -> tuple[str, ...]:
            calls.append(("list", dispatch_mode))
            return ("legacy-job",) if dispatch_mode == "legacy" else ("mq-job",)

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", _RecoveryWorkspace)
    monkeypatch.setattr(
        qc_sichuan,
        "submit_detached_task",
        lambda _name, _func, job_id: calls.append(("submit", job_id)),
    )

    assert qc_sichuan.resume_queued_luxian_0609_workspace_jobs() == 1
    assert calls == [("list", "legacy"), ("submit", "legacy-job")]


@pytest.mark.asyncio
async def test_web_lease_monitor_only_fails_legacy_attempts(monkeypatch) -> None:
    observed: list[str] = []

    class _RecoveryWorkspace:
        def fail_stale_luxian_0609_running_jobs(
            self,
            *,
            stale_before: Any,
            dispatch_mode: str = "legacy",
        ) -> tuple[str, ...]:
            del stale_before
            observed.append(dispatch_mode)
            return ()

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", _RecoveryWorkspace)
    monkeypatch.setattr(qc_sichuan, "_LX0609_RECOVERY_SCAN_SECONDS", 0.001)
    qc_sichuan.start_luxian_0609_task_recovery_monitor()
    try:
        for _ in range(50):
            if observed:
                break
            await asyncio.sleep(0.002)
        assert observed == ["legacy"]
    finally:
        await qc_sichuan.stop_luxian_0609_task_recovery_monitor()


@pytest.mark.asyncio
async def test_sample_mq_leaf_does_not_submit_but_0916_keeps_legacy(
    monkeypatch,
) -> None:
    settings = _main_settings(qc_mode="rabbitmq", llm_mode="gateway")
    service = _gateway_service()

    async def _get_qc_service() -> _ServiceStub:
        return service

    async def _load_config(**_kwargs: Any) -> dict[str, Any]:
        return {"custom_parameters": {}}

    monkeypatch.setattr(qc_sample_pools, "get_settings", lambda: settings)
    monkeypatch.setattr(qc_sample_pools, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(qc_sample_pools.LLMConfigLoader, "load_config", _load_config)

    submitted: list[str] = []
    monkeypatch.setattr(
        qc_sample_pools,
        "submit_detached_task",
        lambda _name, _func, job_id: submitted.append(job_id),
    )

    sample_service = _SamplePoolServiceStub()
    mq_workspace = _PersistingSampleWorkspace(persisted_mode="rabbitmq")
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: mq_workspace)
    mq_response = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolRunRequest(
            record_refs=[_run_record_ref()],
            sample_item_ids=["item-1"],
            rule_set_key=qc_sample_pools.LUXIAN_0609_QC_RULE_SET_KEY,
            selected_rule_ids=["LX0609-01-01-01"],
        ),
        current_user={"id": "tester"},
    )
    assert mq_response["data"]["job_id"]
    assert submitted == []

    legacy_workspace = _PersistingSampleWorkspace(persisted_mode="legacy")
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: legacy_workspace)
    legacy_response = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolRunRequest(
            record_refs=[_run_record_ref()],
            sample_item_ids=["item-1"],
            rule_set_key=qc_sample_pools.LUXIAN_0916_QC_RULE_SET_KEY,
        ),
        current_user={"id": "tester"},
    )
    assert legacy_response["data"]["job_id"]
    assert submitted == [legacy_workspace.create_batch_job_calls[0]["id"]]


@pytest.mark.asyncio
async def test_sample_mq_family_rejected_before_parent_insert(monkeypatch) -> None:
    settings = _main_settings(qc_mode="rabbitmq", llm_mode="gateway")
    workspace = _PersistingSampleWorkspace(persisted_mode="rabbitmq")

    async def _get_qc_service() -> _ServiceStub:
        return _gateway_service()

    async def _load_config(**_kwargs: Any) -> dict[str, Any]:
        return {"custom_parameters": {}}

    monkeypatch.setattr(qc_sample_pools, "_service", _SamplePoolServiceStub)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "get_settings", lambda: settings)
    monkeypatch.setattr(qc_sample_pools, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(qc_sample_pools.LLMConfigLoader, "load_config", _load_config)

    with pytest.raises(HTTPException) as rejected:
        await qc_sample_pools.run_sample_pool_intrinsic_validation(
            request=_build_request(),
            pool_id="pool-1",
            payload=qc_sample_pools.SamplePoolRunRequest(
                record_refs=[_run_record_ref()],
                sample_item_ids=["item-1"],
                rule_set_key=qc_sample_pools.LUXIAN_0609_QC_RULE_SET_KEY,
                selected_rule_ids=["LX0609-01-01-01", "LX0609-03-01-04"],
                group_by_luxian_family=True,
            ),
            current_user={"id": "tester"},
        )

    assert rejected.value.status_code == 503
    assert workspace.create_batch_job_calls == []


@pytest.mark.asyncio
async def test_http_qc_service_does_not_fallback_on_provider_identity_error(
    monkeypatch,
) -> None:
    qc_sichuan.service = None
    constructions: list[Any] = []

    async def _load_config(**_kwargs: Any) -> dict[str, Any]:
        raise ProviderConfigurationError("database LLM provider identity is missing")

    monkeypatch.setattr(qc_sichuan.LLMConfigLoader, "load_config", _load_config)
    monkeypatch.setattr(
        qc_sichuan,
        "SichuanQCService",
        lambda config=None: constructions.append(config),
    )

    with pytest.raises(ProviderConfigurationError, match="identity is missing"):
        await qc_sichuan.init_qc_service()
    assert constructions == []
    assert qc_sichuan.service is None
