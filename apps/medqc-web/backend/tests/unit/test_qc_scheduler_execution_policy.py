"""QC 调度接纳后的不可变执行策略回归。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from app.services.luxian_0609 import execution
from app.services.luxian_0609.engine import FamilyExecutionContext
from app.services.luxian_0609.executor_registry import (
    ExecutorRegistration,
    Luxian0609ExecutorRegistry,
)
from app.services.luxian_0609.native_package import Luxian0609PackagePlan
from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client
from app.services.llm_dispatch.client import GatewayDispatchError
from app.services.llm_dispatch.contracts import GatewayErrorCode
from app.services.sichuan_qc_service import SichuanQCService
from test_luxian_0609_engine import _envelope
from test_luxian_0609_mainline_services import (
    _all_native_settings,
    _safe_evidence_session,
)


@dataclass
class _BlockingExecutor:
    callback: Any

    async def evaluate(self, context: FamilyExecutionContext) -> Any:
        return await self.callback(context)


@pytest.mark.asyncio
async def test_formal_adjudicator_privacy_chain_starts_only_configured_families(
    monkeypatch,
) -> None:
    """二审客户端经隐私包装后，Engine 仍只并发启动策略指定的两个族。"""

    selected = (
        "LX0609-01-01-01",
        "LX0609-06-01-02",
        "LX0609-12-01-01",
        "LX0609-04-02-01",
    )
    batches = (
        ("basic_timeliness", (selected[0],)),
        ("exam_lab", (selected[1],)),
        ("course_quality", (selected[2],)),
        ("surgery_gate", (selected[3],)),
    )
    plan = Luxian0609PackagePlan(
        selected_rule_ids=selected,
        native_sync_rule_ids=selected,
        native_async_rule_ids=(),
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=batches,
    )
    service = SichuanQCService(
        {
            "provider_code": "alibaba",
            "api_endpoint": "https://example.invalid/llm",
            "api_key": "synthetic-only",
            "model": "qwen3.8-flash",
            "source": "test",
            "custom_parameters": {
                "enable_thinking": True,
                "execution_concurrency": {
                    "max_parallel_records": 4,
                    "family_max_concurrency": 2,
                    "http_max_concurrency": 4,
                },
            },
        }
    ).isolated_luxian_0609_runtime(single_record=True)
    accepted_policy = service.luxian_0609_execution_concurrency
    assert accepted_policy.family_max_concurrency == 2
    assert service.adjudicator_client.model == "qwen3.8-flash"
    assert service.adjudicator_client.enable_thinking is True

    active = 0
    peak = 0
    started: list[str] = []
    first_wave_started = asyncio.Event()
    release = asyncio.Event()

    async def block_family(context: FamilyExecutionContext):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        started.append(context.selected_rule_ids[0])
        if len(started) == 2:
            # 让所有已获准的族都有一次确定性的启动机会，再通知断言协程。
            await asyncio.sleep(0)
            first_wave_started.set()
        try:
            await release.wait()
            return _envelope(context)
        finally:
            active -= 1

    registry = Luxian0609ExecutorRegistry(
        tuple(
            ExecutorRegistration(
                executor_key=executor_key,
                executor=_BlockingExecutor(block_family),
            )
            for executor_key, _rule_ids in batches
        )
    )

    def build_registry(*, resources, **_kwargs):
        # 正式链确实已经进入隐私包装；并发策略不能靠给包装对象临时补属性传递。
        assert resources.llm_client is not service.adjudicator_client
        assert resources.llm_client.delegate is service.adjudicator_client
        assert not hasattr(resources.llm_client, "family_max_concurrency")
        return registry

    monkeypatch.setattr(
        execution,
        "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: plan,
    )
    monkeypatch.setattr(
        execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: _safe_evidence_session(),
    )
    monkeypatch.setattr(
        execution,
        "build_luxian_0609_legacy_executor_registry",
        build_registry,
    )

    task = asyncio.create_task(
        execution.prepare_luxian_0609_execution(
            rule_set_key="luxian_0609_qc_v1",
            prepared_rules=[],
            visit_id="synthetic-visit",
            medical_text="",
            evidence_payload={},
            llm_client=service.adjudicator_client,
            execution_concurrency=accepted_policy,
            settings=_all_native_settings(
                LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
                LUXIAN_0609_FAMILY_MAX_CONCURRENCY=4,
            ),
            institute_id="synthetic-institute",
            patient_id="synthetic-patient",
            source_schema="cdm",
            selected_customer_rule_ids=selected,
        )
    )
    try:
        await asyncio.wait_for(first_wave_started.wait(), timeout=2)
        assert active == peak == 2
        assert len(started) == 2
    finally:
        release.set()
    await task
    assert peak == 2
    assert set(started) == set(selected)


@pytest.mark.asyncio
async def test_gateway_managed_transport_error_is_not_retried_by_privacy_wrapper() -> None:
    class Delegate:
        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, _prompt: str, **_kwargs):
            self.calls += 1
            raise GatewayDispatchError(
                GatewayErrorCode.PROVIDER_UNAVAILABLE.value,
                retryable=True,
            )

    delegate = Delegate()
    client = wrap_luxian_0609_llm_client(delegate)

    with pytest.raises(
        GatewayDispatchError,
        match=GatewayErrorCode.PROVIDER_UNAVAILABLE.value,
    ):
        await client.generate("synthetic prompt")
    assert delegate.calls == 1

