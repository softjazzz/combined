"""QC 批任务引用的 RabbitMQ 传输适配器。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
import importlib
from types import ModuleType
from typing import Any, Literal

from app.services.qc_dispatch.config import RabbitMQSettings
from app.services.qc_dispatch.contracts import BatchDispatchEnvelope


DispatchTarget = Literal["main", "dead"]


class RabbitMQTransportError(RuntimeError):
    """AMQP 操作失败；文本及 code 都不含连接串或消息内容。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class RabbitMQDeliveryError(RuntimeError):
    """消费端 ACK/reject 未能确认写入 channel。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class RabbitMQDelivery:
    """手动确认的安全消费交付。"""

    body: bytes
    _incoming_message: Any = field(repr=False)
    _settled: bool = field(default=False, init=False, repr=False)
    _settlement_lock: asyncio.Lock = field(
        default_factory=asyncio.Lock,
        init=False,
        repr=False,
    )

    @property
    def settled(self) -> bool:
        return self._settled

    async def ack(self) -> None:
        async with self._settlement_lock:
            if self._settled:
                raise RabbitMQDeliveryError(
                    "delivery_already_settled",
                    "RabbitMQ delivery is already settled",
                )
            try:
                await self._incoming_message.ack(multiple=False)
            except Exception:
                raise RabbitMQDeliveryError(
                    "ack_failed",
                    "RabbitMQ delivery acknowledgement failed",
                ) from None
            self._settled = True

    async def reject(self, *, requeue: bool = False) -> None:
        if requeue:
            raise RabbitMQDeliveryError(
                "unsafe_requeue_rejected",
                "RabbitMQ delivery requeue is not allowed",
            )
        async with self._settlement_lock:
            if self._settled:
                raise RabbitMQDeliveryError(
                    "delivery_already_settled",
                    "RabbitMQ delivery is already settled",
                )
            try:
                await self._incoming_message.reject(requeue=False)
            except Exception:
                raise RabbitMQDeliveryError(
                    "reject_failed",
                    "RabbitMQ delivery rejection failed",
                ) from None
            self._settled = True


class RabbitMQTransport:
    """显式 confirm、mandatory routing 和手动 ACK 的 AMQP 适配器。"""

    def __init__(
        self,
        settings: RabbitMQSettings,
        *,
        connector: Callable[..., Awaitable[Any]] | None = None,
        aio_pika_module: ModuleType | Any | None = None,
    ) -> None:
        self.settings = settings
        self._connector = connector
        self._aio_pika = aio_pika_module
        self._connection: Any | None = None
        self._channel: Any | None = None
        self._exchange: Any | None = None
        self._queues: dict[DispatchTarget, Any] = {}
        self._connect_lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return (
            self._connection is not None
            and not _is_closed(self._connection)
            and self._channel is not None
            and not _is_closed(self._channel)
            and self._exchange is not None
            and set(self._queues) == {"main", "dead"}
        )

    async def connect(self) -> None:
        """建立 robust connection，并在每个新 channel 上重建一致拓扑。"""

        async with self._connect_lock:
            if self.connected:
                return
            module = self._load_aio_pika()
            connection = self._connection
            if connection is None or _is_closed(connection):
                connector = self._connector or module.connect_robust
                try:
                    connection = await connector(
                        self.settings.url,
                        timeout=self.settings.connect_timeout_seconds,
                        client_properties={"connection_name": "medqc-qc-dispatch"},
                    )
                except Exception:
                    self._reset_state()
                    raise RabbitMQTransportError(
                        "connection_failed",
                        "RabbitMQ connection failed",
                    ) from None
                self._connection = connection
            try:
                await self._open_channel_and_declare()
            except RabbitMQTransportError:
                await self._close_after_failed_connect()
                raise
            except Exception:
                await self._close_after_failed_connect()
                raise RabbitMQTransportError(
                    "topology_failed",
                    "RabbitMQ topology declaration failed",
                ) from None

    async def close(self) -> None:
        """关闭 channel/connection；关闭失败不伪装成未发生。"""

        async with self._connect_lock:
            channel = self._channel
            connection = self._connection
            self._reset_state()
            close_error = False
            if channel is not None and not _is_closed(channel):
                try:
                    await channel.close()
                except Exception:
                    close_error = True
            if connection is not None and not _is_closed(connection):
                try:
                    await connection.close()
                except Exception:
                    close_error = True
            if close_error:
                raise RabbitMQTransportError(
                    "channel_closed",
                    "RabbitMQ close did not complete cleanly",
                )

    async def declare_topology(self) -> None:
        """在当前 channel 上重建持久 exchange/queues/bindings。"""

        if self._channel is None or _is_closed(self._channel):
            raise RabbitMQTransportError(
                "channel_closed",
                "RabbitMQ channel is not available",
            )
        try:
            exchange = await self._channel.declare_exchange(
                self.settings.exchange,
                type="direct",
                durable=True,
                auto_delete=False,
            )
            main_queue = await self._declare_queue(self.settings.queue)
            dead_queue = await self._declare_queue(self.settings.dead_queue)
            await main_queue.bind(exchange, routing_key=self.settings.queue)
            await dead_queue.bind(exchange, routing_key=self.settings.dead_queue)
        except Exception:
            self._exchange = None
            self._queues.clear()
            raise RabbitMQTransportError(
                "topology_failed",
                "RabbitMQ topology declaration failed",
            ) from None
        self._exchange = exchange
        self._queues = {"main": main_queue, "dead": dead_queue}

    async def publish(
        self,
        envelope: BatchDispatchEnvelope,
        target: DispatchTarget = "main",
    ) -> None:
        """只在 Broker 返回显式 Basic.Ack 后返回成功。"""

        if target not in {"main", "dead"}:
            raise ValueError("unsupported RabbitMQ dispatch target")
        exchange = self._require_ready()
        module = self._load_aio_pika()
        routing_key = self.settings.queue if target == "main" else self.settings.dead_queue
        message = module.Message(
            body=envelope.to_bytes(),
            delivery_mode=module.DeliveryMode.PERSISTENT,
            content_type="application/json",
            content_encoding="utf-8",
            message_id=envelope.message_id,
            type="qc.batch.dispatch.v1",
            headers={"schema_version": 1},
        )
        try:
            confirmation = await exchange.publish(
                message,
                routing_key=routing_key,
                mandatory=True,
                timeout=self.settings.publish_timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise RabbitMQTransportError(
                "publish_timeout",
                "RabbitMQ publish confirmation timed out",
            ) from None
        except Exception as exc:
            error_name = type(exc).__name__.lower()
            if "delivery" in error_name or "return" in error_name or "unrout" in error_name:
                code = "unroutable"
                message_text = "RabbitMQ message was not routable"
            elif _is_closed(self._channel) or _is_closed(self._connection):
                code = "channel_closed"
                message_text = "RabbitMQ channel closed during publish"
            else:
                code = "unexpected_publish_error"
                message_text = "RabbitMQ publish failed"
            raise RabbitMQTransportError(code, message_text) from None

        confirm_name = type(confirmation).__name__.lower()
        if confirm_name == "ack":
            return
        if confirm_name in {"nack", "reject"} or confirmation is False:
            raise RabbitMQTransportError(
                "publish_nack",
                "RabbitMQ rejected the published message",
            )
        raise RabbitMQTransportError(
            "confirm_missing",
            "RabbitMQ did not return an explicit publisher confirmation",
        )

    async def iter_deliveries(
        self,
        target: DispatchTarget = "main",
    ) -> AsyncIterator[RabbitMQDelivery]:
        """迭代手动 ACK 交付；断连时结束本次消费而不误 ACK。"""

        if target not in {"main", "dead"}:
            raise ValueError("unsupported RabbitMQ dispatch target")
        self._require_ready()
        queue = self._queues[target]
        try:
            async with queue.iterator(no_ack=False) as iterator:
                async for incoming in iterator:
                    if _is_closed(self._channel) or _is_closed(self._connection):
                        raise RabbitMQTransportError(
                            "channel_closed",
                            "RabbitMQ consumer channel closed",
                        )
                    yield RabbitMQDelivery(
                        body=bytes(incoming.body),
                        _incoming_message=incoming,
                    )
        except (asyncio.CancelledError, GeneratorExit):
            raise
        except RabbitMQTransportError:
            raise
        except Exception:
            raise RabbitMQTransportError(
                "channel_closed",
                "RabbitMQ consumer stopped after channel failure",
            ) from None

    async def consume(
        self,
        handler: Callable[[RabbitMQDelivery], Awaitable[None]],
        target: DispatchTarget = "main",
    ) -> None:
        """运行不带隐式 ACK 的消费循环。"""

        async for delivery in self.iter_deliveries(target=target):
            await handler(delivery)

    async def _open_channel_and_declare(self) -> None:
        if self._connection is None or _is_closed(self._connection):
            raise RabbitMQTransportError(
                "connection_failed",
                "RabbitMQ connection is not available",
            )
        self._channel = await self._connection.channel(
            publisher_confirms=True,
            on_return_raises=True,
        )
        await self._channel.set_qos(
            prefetch_count=self.settings.prefetch,
            global_=False,
        )
        await self.declare_topology()

    async def _declare_queue(self, name: str) -> Any:
        return await self._channel.declare_queue(
            name,
            durable=True,
            exclusive=False,
            auto_delete=False,
            arguments={"x-queue-type": self.settings.queue_type},
        )

    def _require_ready(self) -> Any:
        if self._connection is None or _is_closed(self._connection):
            raise RabbitMQTransportError(
                "connection_failed",
                "RabbitMQ connection is not available",
            )
        if not self.connected:
            raise RabbitMQTransportError(
                "channel_closed",
                "RabbitMQ channel is not available",
            )
        return self._exchange

    def _load_aio_pika(self) -> Any:
        if self._aio_pika is not None:
            return self._aio_pika
        try:
            self._aio_pika = importlib.import_module("aio_pika")
        except ImportError:
            raise RabbitMQTransportError(
                "dependency_missing",
                "RabbitMQ client dependency is not installed",
            ) from None
        return self._aio_pika

    async def _close_after_failed_connect(self) -> None:
        channel = self._channel
        connection = self._connection
        self._reset_state()
        if channel is not None and not _is_closed(channel):
            try:
                await channel.close()
            except Exception:
                pass
        if connection is not None and not _is_closed(connection):
            try:
                await connection.close()
            except Exception:
                pass

    def _reset_state(self) -> None:
        self._connection = None
        self._channel = None
        self._exchange = None
        self._queues.clear()


def _is_closed(resource: Any | None) -> bool:
    if resource is None:
        return True
    value = getattr(resource, "is_closed", False)
    return bool(value() if callable(value) else value)
