from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from app.llm_gateway.admission import (
    AdmissionDeadlineError,
    QueueFullError,
    ResourceAdmissionPool,
)
from app.llm_gateway.config import GatewaySettings, ProfileConfig, ResourceConfig
from app.llm_gateway.main import GatewayRuntime
from app.services.llm_dispatch.contracts import GatewayCompletionRequest


class BlockingSender:
    def __init__(self) -> None:
        self.started: asyncio.Queue[str] = asyncio.Queue()
        self.release = asyncio.Event()
        self.active = 0
        self.peak = 0

    async def send(
        self,
        profile: ProfileConfig,
        payload: dict[str, Any],
        *,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        self.active += 1
        self.peak = max(self.peak, self.active)
        await self.started.put(profile.name)
        try:
            await self.release.wait()
            return {"choices": [{"finish_reason": "stop"}], "usage": {"total_tokens": 3}}
        finally:
            self.active -= 1


def _settings(tmp_path: Path, *, max_inflight: int = 2, max_queue: int = 4) -> GatewaySettings:
    resource = ResourceConfig("strata_gpu", max_inflight=max_inflight, max_queue=max_queue)
    profiles = {
        name: ProfileConfig(
            name=name,
            resource_id="strata_gpu",
            provider_code="strata",
            model="Qwen/Qwen3",
            api_endpoint="https://provider.test/v1/chat/completions",
        )
        for name in ("strata_first_pass", "strata_adjudicator")
    }
    return GatewaySettings(
        token="t" * 32,
        resources={resource.resource_id: resource},
        profiles=profiles,
        allowed_hosts=frozenset({"provider.test"}),
        state_dir=tmp_path,
        startup_isolation_seconds=0,
        shutdown_grace_seconds=0.2,
    )


def _request(profile: str = "strata_first_pass", timeout: float = 5) -> GatewayCompletionRequest:
    return GatewayCompletionRequest(
        request_id=uuid4(),
        # 本文件的各请求代表不同合成病例；同病例串行另有专门保护。
        case_key=uuid4().hex * 2,
        profile=profile,
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=timeout),
        timeout_seconds=timeout,
        payload={
            "model": "Qwen/Qwen3",
            "messages": [{"role": "user", "content": "synthetic"}],
            "stream": False,
        },
    )


@pytest.mark.asyncio
async def test_profiles_sharing_resource_never_exceed_two_slots(tmp_path: Path) -> None:
    sender = BlockingSender()
    runtime = GatewayRuntime(_settings(tmp_path), sender)
    tasks = [
        asyncio.create_task(runtime.complete(_request("strata_first_pass"))),
        asyncio.create_task(runtime.complete(_request("strata_adjudicator"))),
        asyncio.create_task(runtime.complete(_request("strata_first_pass"))),
    ]

    assert {await sender.started.get(), await sender.started.get()} == {
        "strata_first_pass",
        "strata_adjudicator",
    }
    await asyncio.sleep(0)
    snapshot = (await runtime.resource_counts())[0]
    assert snapshot["inflight"] == 2
    assert snapshot["queued"] == 1
    assert sender.peak == 2

    sender.release.set()
    results = await asyncio.gather(*tasks)
    assert sender.peak == 2
    assert all(result["choices"][0]["finish_reason"] == "stop" for result in results)
    assert (await runtime.resource_counts())[0]["inflight"] == 0


@pytest.mark.asyncio
async def test_bounded_queue_rejects_without_starting_http(tmp_path: Path) -> None:
    sender = BlockingSender()
    runtime = GatewayRuntime(_settings(tmp_path, max_inflight=1, max_queue=1), sender)
    first = asyncio.create_task(runtime.complete(_request()))
    assert await sender.started.get() == "strata_first_pass"
    second = asyncio.create_task(runtime.complete(_request()))
    await asyncio.sleep(0)

    with pytest.raises(QueueFullError):
        await runtime.complete(_request())
    assert sender.started.empty()

    sender.release.set()
    await asyncio.gather(first, second)


@pytest.mark.asyncio
async def test_fifo_order_and_no_bypass() -> None:
    pool = ResourceAdmissionPool(ResourceConfig("gpu", max_inflight=1, max_queue=3))
    loop = asyncio.get_running_loop()
    first = await pool.acquire(monotonic_deadline=loop.time() + 5)
    order: list[int] = []

    async def queued(number: int) -> None:
        lease = await pool.acquire(monotonic_deadline=loop.time() + 5)
        order.append(number)
        await lease.release()

    tasks = [asyncio.create_task(queued(number)) for number in (1, 2, 3)]
    await asyncio.sleep(0)
    await first.release()
    await asyncio.gather(*tasks)
    assert order == [1, 2, 3]


@pytest.mark.asyncio
async def test_queue_wait_honors_deadline_and_releases_waiter() -> None:
    pool = ResourceAdmissionPool(ResourceConfig("gpu", max_inflight=1, max_queue=1))
    loop = asyncio.get_running_loop()
    lease = await pool.acquire(monotonic_deadline=loop.time() + 5)
    with pytest.raises(AdmissionDeadlineError):
        await pool.acquire(monotonic_deadline=loop.time() + 0.01)
    assert (await pool.snapshot())["queued"] == 0
    await lease.release()


@pytest.mark.asyncio
async def test_expired_request_never_occupies_slot(tmp_path: Path) -> None:
    sender = BlockingSender()
    runtime = GatewayRuntime(_settings(tmp_path), sender)
    request = _request(timeout=1)
    request.deadline_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    with pytest.raises(AdmissionDeadlineError):
        await runtime.complete(request)
    assert sender.started.empty()
    assert (await runtime.resource_counts())[0]["inflight"] == 0
