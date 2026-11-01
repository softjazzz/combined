from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.llm_gateway.config import GatewaySettings, ProfileConfig, ResourceConfig
from app.llm_gateway.lifecycle import SENTINEL_FILENAME, SingleInstanceError, SingleInstanceSentinel
from app.llm_gateway.main import GatewayRuntime, _complete_until_disconnect, create_app
from app.llm_gateway.providers import ProviderTimeoutError
from app.services.llm_dispatch.contracts import GatewayCompletionRequest


class ControlledSender:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0
        self.cancelled = False
        self.error: Exception | None = None

    async def send(
        self,
        profile: ProfileConfig,
        payload: dict[str, Any],
        *,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        self.calls += 1
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        if self.error:
            raise self.error
        return {"choices": [{"message": {"content": "ok"}}], "usage": {}}


def _settings(tmp_path: Path, *, grace: float = 0.2) -> GatewaySettings:
    resource = ResourceConfig("gpu", max_inflight=1, max_queue=2)
    profile = ProfileConfig(
        name="strata",
        resource_id="gpu",
        provider_code="strata",
        model="m",
        api_endpoint="https://provider.test/chat/completions",
    )
    return GatewaySettings(
        token="x" * 32,
        resources={"gpu": resource},
        profiles={"strata": profile},
        allowed_hosts=frozenset({"provider.test"}),
        state_dir=tmp_path,
        startup_isolation_seconds=0,
        shutdown_grace_seconds=grace,
    )


def _request(timeout_seconds: float = 10) -> GatewayCompletionRequest:
    return GatewayCompletionRequest(
        request_id=uuid4(),
        profile="strata",
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds),
        timeout_seconds=timeout_seconds,
        payload={
            "model": "m",
            "messages": [{"role": "user", "content": "synthetic"}],
            "stream": False,
        },
    )


async def _wait_for_zero(runtime: GatewayRuntime) -> None:
    for _ in range(100):
        if (await runtime.resource_counts())[0]["inflight"] == 0:
            return
        await asyncio.sleep(0.001)
    raise AssertionError("slot was not released")


async def _wait_for_count(runtime: GatewayRuntime, field: str, expected: int) -> None:
    for _ in range(100):
        if (await runtime.resource_counts())[0][field] == expected:
            return
        await asyncio.sleep(0.001)
    raise AssertionError(f"{field} did not become {expected}")


@pytest.mark.asyncio
async def test_cancelled_pending_request_is_never_sent(tmp_path: Path) -> None:
    sender = ControlledSender()
    runtime = GatewayRuntime(_settings(tmp_path), sender)
    active = asyncio.create_task(runtime.complete(_request()))
    await sender.started.wait()
    pending = asyncio.create_task(runtime.complete(_request()))
    await asyncio.sleep(0)
    assert (await runtime.resource_counts())[0]["queued"] == 1

    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    sender.release.set()
    await active
    assert sender.calls == 1
    assert (await runtime.resource_counts())[0]["queued"] == 0


@pytest.mark.asyncio
async def test_asgi_http_disconnect_withdraws_pending_request_before_send(tmp_path: Path) -> None:
    sender = ControlledSender()
    runtime = GatewayRuntime(_settings(tmp_path), sender)
    active = asyncio.create_task(runtime.complete(_request()))
    await sender.started.wait()
    disconnected = asyncio.Event()

    async def receive() -> dict[str, str]:
        await disconnected.wait()
        return {"type": "http.disconnect"}

    request = Request({"type": "http", "method": "POST", "path": "/v1/llm/completions", "headers": []}, receive)
    pending = asyncio.create_task(_complete_until_disconnect(runtime, _request(), request))
    await asyncio.sleep(0)
    assert (await runtime.resource_counts())[0]["queued"] == 1
    disconnected.set()
    with pytest.raises(asyncio.CancelledError):
        await pending

    sender.release.set()
    await active
    assert sender.calls == 1


@pytest.mark.asyncio
async def test_wrapper_cancellation_without_http_disconnect_cleans_pending_child(tmp_path: Path) -> None:
    sender = ControlledSender()
    runtime = GatewayRuntime(_settings(tmp_path), sender)
    active = asyncio.create_task(runtime.complete(_request()))
    await sender.started.wait()
    never_disconnects = asyncio.Event()

    async def receive() -> dict[str, str]:
        await never_disconnects.wait()
        return {"type": "http.disconnect"}

    request = Request({"type": "http", "method": "POST", "path": "/v1/llm/completions", "headers": []}, receive)
    wrapper = asyncio.create_task(_complete_until_disconnect(runtime, _request(), request))
    await _wait_for_count(runtime, "queued", 1)

    wrapper.cancel()
    with pytest.raises(asyncio.CancelledError):
        await wrapper
    assert (await runtime.resource_counts())[0]["queued"] == 0

    sender.release.set()
    await active
    await asyncio.sleep(0)
    assert sender.calls == 1


@pytest.mark.asyncio
async def test_cancel_after_lease_before_sender_start_never_sends(tmp_path: Path) -> None:
    sender = ControlledSender()
    start_gate = asyncio.Event()
    runtime = GatewayRuntime(_settings(tmp_path), sender, provider_start_gate=start_gate)
    caller = asyncio.create_task(runtime.complete(_request()))
    await _wait_for_count(runtime, "inflight", 1)
    assert sender.calls == 0

    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    start_gate.set()
    await asyncio.sleep(0)

    assert sender.calls == 0
    assert (await runtime.resource_counts())[0]["inflight"] == 0


@pytest.mark.asyncio
async def test_deadline_expiring_after_lease_before_sender_start_never_sends_or_quarantines(
    tmp_path: Path,
) -> None:
    sender = ControlledSender()
    start_gate = asyncio.Event()
    runtime = GatewayRuntime(_settings(tmp_path), sender, provider_start_gate=start_gate)
    caller = asyncio.create_task(runtime.complete(_request(0.02)))
    await _wait_for_count(runtime, "inflight", 1)

    await asyncio.sleep(0.03)
    start_gate.set()
    with pytest.raises(Exception) as captured:
        await caller
    assert getattr(captured.value, "code", None) == "gateway_deadline_exceeded"
    assert sender.calls == 0
    snapshot = (await runtime.resource_counts())[0]
    assert snapshot["inflight"] == 0
    assert snapshot["unknown_inflight"] is False
    assert snapshot["accepting"] is True


@pytest.mark.asyncio
async def test_deadline_expiring_between_outer_check_and_invoke_is_not_transport_failure(
    tmp_path: Path,
) -> None:
    sender = ControlledSender()
    clock_values = iter((0.0, float("inf")))
    runtime = GatewayRuntime(
        _settings(tmp_path),
        sender,
        deadline_clock=lambda: next(clock_values),
    )

    with pytest.raises(Exception) as captured:
        await runtime.complete(_request())
    assert getattr(captured.value, "code", None) == "gateway_deadline_exceeded"
    assert sender.calls == 0
    snapshot = (await runtime.resource_counts())[0]
    assert snapshot["inflight"] == 0
    assert snapshot["unknown_inflight"] is False
    assert snapshot["accepting"] is True


@pytest.mark.asyncio
async def test_cancelled_admitted_caller_does_not_release_slot_early(tmp_path: Path) -> None:
    sender = ControlledSender()
    runtime = GatewayRuntime(_settings(tmp_path), sender)
    caller = asyncio.create_task(runtime.complete(_request()))
    await sender.started.wait()

    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert (await runtime.resource_counts())[0]["inflight"] == 1
    assert not sender.cancelled

    sender.release.set()
    await _wait_for_zero(runtime)
    assert sender.calls == 1


@pytest.mark.asyncio
async def test_sender_exception_releases_slot_and_does_not_leak_text(tmp_path: Path) -> None:
    sender = ControlledSender()
    sender.error = RuntimeError("secret endpoint key prompt")
    sender.release.set()
    runtime = GatewayRuntime(_settings(tmp_path), sender)

    with pytest.raises(Exception) as captured:
        await runtime.complete(_request())
    assert "secret" not in str(captured.value)
    assert (await runtime.resource_counts())[0]["inflight"] == 0


@pytest.mark.asyncio
async def test_provider_timeout_quarantines_resource_and_retains_restart_sentinel(tmp_path: Path) -> None:
    sender = ControlledSender()
    sender.error = ProviderTimeoutError()
    sender.release.set()
    app = create_app(_settings(tmp_path), sender=sender, enforce_single_instance=True)

    async with app.router.lifespan_context(app):
        runtime: GatewayRuntime = app.state.gateway_runtime
        with pytest.raises(ProviderTimeoutError):
            await runtime.complete(_request())
        snapshot = (await runtime.resource_counts())[0]
        assert snapshot["unknown_inflight"] is True
        assert snapshot["accepting"] is False
        with pytest.raises(Exception) as rejected:
            await runtime.complete(_request())
        assert getattr(rejected.value, "code", None) == "gateway_resource_quarantined"
        assert sender.calls == 1

    # HTTP 超时不证明 GPU 已结束，因此退出不删 sentinel。
    assert (tmp_path / SENTINEL_FILENAME).exists()


@pytest.mark.asyncio
async def test_gateway_enforces_wall_clock_sender_budget_and_quarantines_unknown_remote(
    tmp_path: Path,
) -> None:
    sender = ControlledSender()
    runtime = GatewayRuntime(_settings(tmp_path), sender)

    with pytest.raises(ProviderTimeoutError):
        # 外层上限只是测试防挂死；必须由 Gateway 在 20ms 预算处产生 ProviderTimeoutError。
        await asyncio.wait_for(runtime.complete(_request(0.02)), timeout=0.5)

    assert sender.started.is_set()
    assert sender.cancelled is True
    snapshot = (await runtime.resource_counts())[0]
    assert snapshot["inflight"] == 0
    assert snapshot["unknown_inflight"] is True
    assert snapshot["accepting"] is False


@pytest.mark.asyncio
async def test_shutdown_stops_admission_and_unclean_drain_is_reported(tmp_path: Path) -> None:
    sender = ControlledSender()
    runtime = GatewayRuntime(_settings(tmp_path, grace=0.01), sender)
    active = asyncio.create_task(runtime.complete(_request()))
    await sender.started.wait()
    pending = asyncio.create_task(runtime.complete(_request()))
    await asyncio.sleep(0)

    clean = await runtime.shutdown()
    assert clean is False
    assert sender.cancelled is True
    with pytest.raises(Exception) as pending_error:
        await pending
    assert getattr(pending_error.value, "code", None) == "gateway_shutting_down"
    with pytest.raises(asyncio.CancelledError):
        await active
    snapshot = (await runtime.resource_counts())[0]
    assert snapshot["inflight"] == 0
    assert snapshot["queued"] == 0
    assert snapshot["accepting"] is False


def test_single_instance_sentinel_requires_clean_drain_or_operator_action(tmp_path: Path) -> None:
    first = SingleInstanceSentinel(tmp_path)
    first.acquire()
    with pytest.raises(SingleInstanceError):
        SingleInstanceSentinel(tmp_path).acquire()

    # 测试中模拟已人工确认 Provider 无遗留；产品不提供自动删除。
    first.release_after_clean_drain()
    second = SingleInstanceSentinel(tmp_path)
    second.acquire()
    second.release_after_clean_drain()
