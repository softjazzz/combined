"""M2 合成验收使用的最小内存 Broker；不创建 socket 或后台进程。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.services.qc_dispatch.rabbitmq_transport import (
    RabbitMQDeliveryError,
    RabbitMQTransportError,
)


@dataclass(slots=True)
class FakeDelivery:
    """记录手动 ACK/reject 的合成交付。"""

    body: bytes
    fail_ack: bool = False
    ack_count: int = field(default=0, init=False)
    reject_count: int = field(default=0, init=False)
    rejected_requeue: bool | None = field(default=None, init=False)

    async def ack(self) -> None:
        if self.fail_ack:
            raise RabbitMQDeliveryError(
                "ack_failed",
                "FakeBroker delivery acknowledgement failed",
            )
        self.ack_count += 1

    async def reject(self, *, requeue: bool = False) -> None:
        self.reject_count += 1
        self.rejected_requeue = requeue


class FakeBroker:
    """只模拟 M2 publisher/consumer 之间的字节交付和 confirm 故障。"""

    def __init__(self) -> None:
        self._messages: dict[str, list[bytes]] = defaultdict(list)
        self.offline = False
        self.lose_next_confirm = False
        self.publish_attempts = 0

    async def publish(self, envelope: Any, target: str = "main") -> None:
        self.publish_attempts += 1
        if self.offline:
            raise RabbitMQTransportError(
                "connection_failed",
                "FakeBroker is offline",
            )
        if target not in {"main", "dead"}:
            raise ValueError("unsupported FakeBroker dispatch target")
        self._messages[target].append(envelope.to_bytes())
        if self.lose_next_confirm:
            self.lose_next_confirm = False
            raise RabbitMQTransportError(
                "confirm_missing",
                "FakeBroker publisher confirmation was lost",
            )

    def deliveries(
        self,
        *,
        target: str = "main",
        fail_ack: bool = False,
    ) -> list[FakeDelivery]:
        return [
            FakeDelivery(body=body, fail_ack=fail_ack)
            for body in self._messages.get(target, ())
        ]

    def bodies(self, *, target: str = "main") -> tuple[bytes, ...]:
        return tuple(self._messages.get(target, ()))

    def clear(self) -> None:
        self._messages.clear()
