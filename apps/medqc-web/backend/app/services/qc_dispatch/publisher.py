"""Transactional Outbox 到 RabbitMQ 的短事务 publisher。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re
from typing import Any

from app.services.qc_dispatch.contracts import (
    BatchDispatchEnvelope,
    PUBLISH_FAILURE_CODES,
)
from app.services.qc_dispatch.rabbitmq_transport import (
    RabbitMQTransport,
    RabbitMQTransportError,
)


_OWNER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_UNKNOWN_CONFIRM_CODES = frozenset(
    {
        "channel_closed",
        "confirm_missing",
        "publish_timeout",
        "unexpected_publish_error",
    }
)


@dataclass(frozen=True, slots=True)
class OutboxPublisherSettings:
    owner: str
    lease_seconds: int = 30
    claim_limit: int = 1
    retry_base_seconds: float = 1.0
    retry_max_seconds: float = 60.0
    idle_poll_seconds: float = 0.5
    reconnect_base_seconds: float = 1.0
    reconnect_max_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not isinstance(self.owner, str) or not _OWNER_RE.fullmatch(self.owner):
            raise ValueError("publisher owner is invalid")
        if (
            isinstance(self.lease_seconds, bool)
            or not isinstance(self.lease_seconds, int)
            or not 5 <= self.lease_seconds <= 3600
        ):
            raise ValueError("publisher lease_seconds is invalid")
        if (
            isinstance(self.claim_limit, bool)
            or not isinstance(self.claim_limit, int)
            or not 1 <= self.claim_limit <= 100
        ):
            raise ValueError("publisher claim_limit is invalid")
        for value, name, minimum, maximum in (
            (self.retry_base_seconds, "retry_base_seconds", 0.1, 3600.0),
            (self.retry_max_seconds, "retry_max_seconds", 0.1, 86400.0),
            (self.idle_poll_seconds, "idle_poll_seconds", 0.05, 60.0),
            (self.reconnect_base_seconds, "reconnect_base_seconds", 0.1, 300.0),
            (self.reconnect_max_seconds, "reconnect_max_seconds", 0.1, 3600.0),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"publisher {name} is invalid")
            if not minimum <= value <= maximum:
                raise ValueError(f"publisher {name} is invalid")
        if self.retry_max_seconds < self.retry_base_seconds:
            raise ValueError("publisher retry bounds are invalid")
        if self.reconnect_max_seconds < self.reconnect_base_seconds:
            raise ValueError("publisher reconnect bounds are invalid")


@dataclass(frozen=True, slots=True)
class PublisherRunResult:
    claimed: int = 0
    published: int = 0
    retry_scheduled: int = 0
    confirmation_unknown: int = 0
    stale_claim: int = 0


class OutboxPublisher:
    """先短事务 claim，释放 DB 后再等 Broker confirm。"""

    def __init__(
        self,
        repository: Any,
        transport: RabbitMQTransport,
        settings: OutboxPublisherSettings,
    ) -> None:
        self._repository = repository
        self._transport = transport
        self.settings = settings

    async def run_once(self) -> PublisherRunResult:
        records = self._repository.claim_outbox(
            self.settings.owner,
            lease_seconds=self.settings.lease_seconds,
            limit=self.settings.claim_limit,
        )
        published = 0
        retry_scheduled = 0
        confirmation_unknown = 0
        stale_claim = 0

        for record in records:
            envelope, error_code = _validated_record(record)
            if error_code is not None:
                if self._mark_failed(record, error_code):
                    retry_scheduled += 1
                else:
                    stale_claim += 1
                continue

            try:
                await self._transport.publish(envelope, target=record.target)
            except RabbitMQTransportError as exc:
                code = exc.code if exc.code in PUBLISH_FAILURE_CODES else "unexpected_publish_error"
                if code in _UNKNOWN_CONFIRM_CODES:
                    # 可能已到 Broker，保留 claimed 到 lease 过期后重领。
                    confirmation_unknown += 1
                elif self._mark_failed(record, code):
                    retry_scheduled += 1
                else:
                    stale_claim += 1
                continue
            except Exception:
                # 不确定 publish 是否已离开客户端，不立即改回 pending。
                confirmation_unknown += 1
                continue

            confirmed = self._repository.mark_confirmed(
                str(record.message_id),
                str(record.publication_token),
            )
            if confirmed:
                published += 1
            else:
                # confirm 已到，但 claim token 已失效；消费端必须以 message_id 幂等。
                stale_claim += 1

        return PublisherRunResult(
            claimed=len(records),
            published=published,
            retry_scheduled=retry_scheduled,
            confirmation_unknown=confirmation_unknown,
            stale_claim=stale_claim,
        )

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        """持续发布；只在 outbox 为空时短暂等待。"""

        reconnect_attempts = 0
        while not stop_event.is_set():
            if getattr(self._transport, "connected", True) is False:
                connector = getattr(self._transport, "connect", None)
                if not callable(connector):
                    raise RuntimeError("publisher transport cannot reconnect")
                try:
                    await connector()
                except RabbitMQTransportError:
                    reconnect_attempts += 1
                    await _wait_or_stop(
                        stop_event,
                        min(
                            self.settings.reconnect_max_seconds,
                            self.settings.reconnect_base_seconds
                            * (2 ** min(reconnect_attempts - 1, 30)),
                        ),
                    )
                    continue
                reconnect_attempts = 0
                if stop_event.is_set():
                    break
            result = await self.run_once()
            if result.claimed:
                continue
            await _wait_or_stop(stop_event, self.settings.idle_poll_seconds)

    def _mark_failed(self, record: Any, error_code: str) -> bool:
        if error_code not in PUBLISH_FAILURE_CODES:
            error_code = "unexpected_publish_error"
        token = getattr(record, "publication_token", None)
        if not isinstance(token, str) or not token:
            return False
        return bool(
            self._repository.mark_publish_failed(
                str(record.message_id),
                token,
                error_code,
                retry_delay_seconds=self._retry_delay(record),
            )
        )

    def _retry_delay(self, record: Any) -> float:
        attempts = getattr(record, "publish_attempts", 1)
        if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
            attempts = 1
        exponent = min(attempts - 1, 30)
        return min(
            self.settings.retry_max_seconds,
            self.settings.retry_base_seconds * (2**exponent),
        )


def _validated_record(record: Any) -> tuple[BatchDispatchEnvelope | None, str | None]:
    payload = getattr(record, "payload", None)
    if not isinstance(payload, bytes):
        return None, "invalid_envelope"
    try:
        envelope = BatchDispatchEnvelope.from_bytes(payload)
    except (TypeError, ValueError):
        return None, "invalid_envelope"

    target = getattr(record, "target", None)
    if target not in {"main", "dead"}:
        return None, "record_mismatch"
    expected = (
        str(getattr(record, "message_id", "")),
        str(getattr(record, "job_id", "")),
        getattr(record, "generation", None),
    )
    actual = (envelope.message_id, envelope.job_id, envelope.generation)
    if expected != actual:
        return None, "record_mismatch"
    return envelope, None


async def _wait_or_stop(stop_event: asyncio.Event, delay_seconds: float) -> None:
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=delay_seconds)
    except asyncio.TimeoutError:
        pass
