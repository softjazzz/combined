"""整批 QC 消息的手动 ACK 状态机。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from enum import Enum
import logging
from typing import Any, Protocol

from app.services.qc_dispatch.contracts import BatchDispatchEnvelope


logger = logging.getLogger(__name__)

_TERMINAL_ACK_STATUSES = frozenset({"completed", "canceled"})
_ACKABLE_RECOVERY_KINDS = frozenset({"delivery", "failed_scope", "unstarted"})


class Delivery(Protocol):
    body: bytes

    async def ack(self) -> None: ...

    async def reject(self, *, requeue: bool = False) -> None: ...


class DispatchRepository(Protocol):
    def get_dispatch(self, job_id: str) -> Any | None: ...

    def get_job_status(self, job_id: str) -> str | None: ...

    def record_terminal_failure(
        self,
        job_id: str,
        generation: int,
        *,
        error_code: str,
    ) -> bool: ...


class ConsumerDecision(str, Enum):
    ACK_TERMINAL = "ack_terminal"
    ACK_OLD_GENERATION = "ack_old_generation"
    ACK_RECOVERY_REGISTERED = "ack_recovery_registered"
    ACK_RETRY_SCHEDULED = "ack_retry_scheduled"
    ACK_FAILED_RECORDED = "ack_failed_recorded"
    REJECT_INVALID = "reject_invalid"


class DeliveryDeferred(RuntimeError):
    """消息保持未确认，交由 channel 关闭后的受控重投处理。"""


class DispatchPersistenceError(RuntimeError):
    """ACK 前的持久化条件未满足。"""


class BatchConsumer:
    """prefetch=1 下串行消费整批任务引用。

    ``execute_job`` 必须只在任务自身 CAS 领取成功后执行，并在返回前提交任务状态。
    本类从不缓存 delivery tag；每次 ACK 都调用当前 delivery 对象，因此重连后不会
    把旧 channel 的 tag 用到新 channel。
    """

    def __init__(
        self,
        *,
        repository: DispatchRepository,
        execute_job: Callable[[BatchDispatchEnvelope], Awaitable[None]],
        recover_failed_job: Callable[[str], Any] | None = None,
    ) -> None:
        self._repository = repository
        self._execute_job = execute_job
        self._recover_failed_job = recover_failed_job

    async def run(self, transport: Any) -> None:
        async for delivery in transport.iter_deliveries(target="main"):
            await self.handle_delivery(delivery)

    async def handle_delivery(self, delivery: Delivery) -> ConsumerDecision:
        try:
            envelope = BatchDispatchEnvelope.from_bytes(delivery.body)
        except Exception:
            logger.warning("拒绝无效 QC 调度消息: code=invalid_envelope")
            await delivery.reject(requeue=False)
            return ConsumerDecision.REJECT_INVALID

        dispatch = self._repository.get_dispatch(envelope.job_id)
        if dispatch is None or str(getattr(dispatch, "mode", "")) != "rabbitmq":
            logger.warning("拒绝无效 QC 调度消息: code=dispatch_not_found_or_wrong_mode")
            await delivery.reject(requeue=False)
            return ConsumerDecision.REJECT_INVALID

        persisted_generation = int(getattr(dispatch, "generation", 0) or 0)
        if envelope.generation < persisted_generation:
            await delivery.ack()
            return ConsumerDecision.ACK_OLD_GENERATION
        if envelope.generation != persisted_generation:
            logger.warning("拒绝无效 QC 调度消息: code=future_generation")
            await delivery.reject(requeue=False)
            return ConsumerDecision.REJECT_INVALID

        status = self._normalized_status(envelope.job_id)
        initial = await self._settle_without_execution(
            delivery=delivery,
            envelope=envelope,
            dispatch=dispatch,
            status=status,
        )
        if initial is not None:
            return initial

        await self._execute_job(envelope)
        return await self._settle_after_execution(delivery, envelope)

    async def _settle_without_execution(
        self,
        *,
        delivery: Delivery,
        envelope: BatchDispatchEnvelope,
        dispatch: Any,
        status: str | None,
    ) -> ConsumerDecision | None:
        if status in _TERMINAL_ACK_STATUSES:
            await delivery.ack()
            return ConsumerDecision.ACK_TERMINAL
        if status == "failed":
            return await self._settle_failed_delivery(
                delivery=delivery, envelope=envelope, dispatch=dispatch,
            )
        if status == "running":
            return await self._defer_live_delivery(
                delivery=delivery,
                envelope=envelope,
                dispatch=dispatch,
            )
        if status == "queued":
            return None
        if status is None:
            logger.warning("拒绝无效 QC 调度消息: code=job_not_found")
            await delivery.reject(requeue=False)
            return ConsumerDecision.REJECT_INVALID
        raise DispatchPersistenceError("QC job has an unsupported persisted status")

    async def _settle_after_execution(
        self,
        delivery: Delivery,
        envelope: BatchDispatchEnvelope,
    ) -> ConsumerDecision:
        dispatch = self._repository.get_dispatch(envelope.job_id)
        if dispatch is None or str(getattr(dispatch, "mode", "")) != "rabbitmq":
            raise DispatchPersistenceError("QC dispatch disappeared before ACK")
        current_generation = int(getattr(dispatch, "generation", 0) or 0)
        status = self._normalized_status(envelope.job_id)
        if current_generation > envelope.generation:
            # retry_batch_job 已在同一事务把新 generation 与 Outbox 持久化。
            await delivery.ack()
            return ConsumerDecision.ACK_RETRY_SCHEDULED
        if current_generation != envelope.generation:
            raise DispatchPersistenceError("QC dispatch generation changed unexpectedly")
        if status in _TERMINAL_ACK_STATUSES:
            await delivery.ack()
            return ConsumerDecision.ACK_TERMINAL
        if status == "failed":
            return await self._settle_failed_delivery(
                delivery=delivery, envelope=envelope, dispatch=dispatch,
            )
        if status in {"running", "queued"}:
            return await self._defer_live_delivery(
                delivery=delivery,
                envelope=envelope,
                dispatch=dispatch,
            )
        raise DispatchPersistenceError("QC job did not reach a durable ACK state")

    async def _record_failure_then_ack(
        self,
        delivery: Delivery,
        envelope: BatchDispatchEnvelope,
        *,
        error_code: str,
    ) -> ConsumerDecision:
        persisted = self._repository.record_terminal_failure(
            envelope.job_id,
            envelope.generation,
            error_code=error_code,
        )
        if not persisted:
            raise DispatchPersistenceError(
                "QC terminal failure could not be persisted before ACK"
            )
        await delivery.ack()
        return ConsumerDecision.ACK_FAILED_RECORDED

    async def _settle_classified_failed_delivery(
        self,
        *,
        delivery: Delivery,
        envelope: BatchDispatchEnvelope,
        dispatch: Any,
    ) -> ConsumerDecision | None:
        recovery_kind = str(getattr(dispatch, "recovery_kind", "") or "")
        if recovery_kind == "manual_scope_required":
            return await self._record_failure_then_ack(
                delivery,
                envelope,
                error_code="manual_scope_required",
            )
        if recovery_kind in _ACKABLE_RECOVERY_KINDS:
            await delivery.ack()
            return ConsumerDecision.ACK_RECOVERY_REGISTERED
        if getattr(dispatch, "last_failure_code", None):
            # last_failure_code 与 dead Outbox 由 record_terminal_failure 同事务提交。
            await delivery.ack()
            return ConsumerDecision.ACK_FAILED_RECORDED
        return None

    async def _settle_failed_delivery(
        self,
        *,
        delivery: Delivery,
        envelope: BatchDispatchEnvelope,
        dispatch: Any,
    ) -> ConsumerDecision:
        settled = await self._settle_classified_failed_delivery(
            delivery=delivery,
            envelope=envelope,
            dispatch=dispatch,
        )
        if settled is not None:
            return settled
        if self._recover_failed_job is not None:
            # 常规失败结算前即时执行单任务恢复分类，避免无条件抛 DeliveryDeferred 引发断连风暴。
            await asyncio.to_thread(self._recover_failed_job, envelope.job_id)
            refreshed = await asyncio.to_thread(
                self._repository.get_dispatch,
                envelope.job_id,
            )
            if refreshed is None or str(getattr(refreshed, "mode", "")) != "rabbitmq":
                raise DispatchPersistenceError(
                    "QC dispatch disappeared during failure recovery"
                )
            current_generation = int(getattr(refreshed, "generation", 0) or 0)
            if current_generation > envelope.generation:
                await delivery.ack()
                return ConsumerDecision.ACK_RETRY_SCHEDULED
            if current_generation != envelope.generation:
                raise DispatchPersistenceError(
                    "QC dispatch generation changed unexpectedly"
                )
            settled = await self._settle_classified_failed_delivery(
                delivery=delivery,
                envelope=envelope,
                dispatch=refreshed,
            )
            if settled is not None:
                return settled
        # stale fencing 与恢复分类是两个持久步骤。分类 owner 尚未登记前绝不能
        # 抢先写 worker_failed 并 ACK，否则会让可恢复任务永久离开候选集合。
        raise DeliveryDeferred("failed QC attempt is awaiting durable recovery classification")

    async def _defer_live_delivery(
        self,
        *,
        delivery: Delivery,
        envelope: BatchDispatchEnvelope,
        dispatch: Any,
    ) -> ConsumerDecision:
        if self._has_prior_recovery(dispatch):
            await delivery.ack()
            return ConsumerDecision.ACK_RECOVERY_REGISTERED

        # 消费者不能在未 ACK delivery 上 sleep，也不能现场登记一个恢复标记后把
        # 消息当作可安全 ACK。只做一次复核；仍 live 时退出当前 channel，由进程级
        # 重连退避控制频率，真正的 available_at 延后只归持久 Outbox 恢复 owner。
        refreshed = self._repository.get_dispatch(envelope.job_id)
        status = self._normalized_status(envelope.job_id)
        if refreshed is None:
            raise DispatchPersistenceError("QC dispatch disappeared while deferred")
        generation = int(getattr(refreshed, "generation", 0) or 0)
        if generation > envelope.generation:
            await delivery.ack()
            return ConsumerDecision.ACK_RETRY_SCHEDULED
        if generation != envelope.generation:
            raise DispatchPersistenceError("QC dispatch generation changed unexpectedly")
        if status in _TERMINAL_ACK_STATUSES:
            await delivery.ack()
            return ConsumerDecision.ACK_TERMINAL
        if status == "failed":
            return await self._settle_failed_delivery(
                delivery=delivery,
                envelope=envelope,
                dispatch=refreshed,
            )
        if self._has_prior_recovery(refreshed):
            await delivery.ack()
            return ConsumerDecision.ACK_RECOVERY_REGISTERED
        raise DeliveryDeferred("live QC attempt has no durable recovery registration")

    def _normalized_status(self, job_id: str) -> str | None:
        status = self._repository.get_job_status(job_id)
        if status is None:
            return None
        return str(status).strip().lower()

    @staticmethod
    def _has_prior_recovery(dispatch: Any) -> bool:
        return str(getattr(dispatch, "recovery_kind", "") or "") in (
            _ACKABLE_RECOVERY_KINDS
        )
