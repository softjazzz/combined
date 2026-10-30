from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.qc_dispatch.config import (
    RabbitMQConfigurationError,
    RabbitMQSettings,
)
from app.services.qc_dispatch.contracts import BatchDispatchEnvelope
from app.services.qc_dispatch.rabbitmq_transport import (
    RabbitMQDelivery,
    RabbitMQDeliveryError,
    RabbitMQTransport,
    RabbitMQTransportError,
)


class Ack:
    pass


class Nack:
    pass


class DeliveryError(Exception):
    pass


class PublishError(DeliveryError):
    pass


class FakeMessage:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeIncoming:
    def __init__(self, body: bytes, *, ack_fails: bool = False):
        self.body = body
        self.ack_fails = ack_fails
        self.acks: list[bool] = []
        self.rejects: list[bool] = []

    async def ack(self, *, multiple: bool):
        if self.ack_fails:
            raise RuntimeError("socket contained a secret")
        self.acks.append(multiple)

    async def reject(self, *, requeue: bool):
        self.rejects.append(requeue)


class FakeIterator:
    def __init__(self, messages):
        self._messages = iter(messages)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._messages)
        except StopIteration:
            raise StopAsyncIteration from None


class FakeQueue:
    def __init__(self, name: str):
        self.name = name
        self.binds: list[tuple[object, str]] = []
        self.messages: list[FakeIncoming] = []
        self.iterator_calls: list[bool] = []

    async def bind(self, exchange, *, routing_key: str):
        self.binds.append((exchange, routing_key))

    def iterator(self, *, no_ack: bool):
        self.iterator_calls.append(no_ack)
        return FakeIterator(self.messages)


class FakeExchange:
    def __init__(self):
        self.confirmation = Ack()
        self.error: Exception | None = None
        self.publishes: list[tuple[FakeMessage, dict[str, object]]] = []

    async def publish(self, message, **kwargs):
        self.publishes.append((message, kwargs))
        if self.error is not None:
            raise self.error
        return self.confirmation


class FakeChannel:
    def __init__(self):
        self.is_closed = False
        self.close_calls = 0
        self.qos_calls: list[dict[str, object]] = []
        self.exchange = FakeExchange()
        self.exchange_calls: list[tuple[str, dict[str, object]]] = []
        self.queue_calls: list[tuple[str, dict[str, object]]] = []
        self.queues: dict[str, FakeQueue] = {}

    async def set_qos(self, **kwargs):
        self.qos_calls.append(kwargs)

    async def declare_exchange(self, name: str, **kwargs):
        self.exchange_calls.append((name, kwargs))
        return self.exchange

    async def declare_queue(self, name: str, **kwargs):
        self.queue_calls.append((name, kwargs))
        queue = FakeQueue(name)
        self.queues[name] = queue
        return queue

    async def close(self):
        self.close_calls += 1
        self.is_closed = True


class FakeConnection:
    def __init__(self, channels: list[FakeChannel] | None = None):
        self.is_closed = False
        self.close_calls = 0
        self.channel_calls: list[dict[str, object]] = []
        self.channels = channels or [FakeChannel()]

    async def channel(self, **kwargs):
        self.channel_calls.append(kwargs)
        return self.channels[len(self.channel_calls) - 1]

    async def close(self):
        self.close_calls += 1
        self.is_closed = True


def _settings() -> RabbitMQSettings:
    return RabbitMQSettings(
        url="amqp://publisher:top-secret@rabbit.internal/%2Fmedqc",
        exchange="medqc.qc.dispatch",
        queue="medqc.qc.main",
        dead_queue="medqc.qc.dead",
    )


def _module():
    return SimpleNamespace(
        Message=FakeMessage,
        DeliveryMode=SimpleNamespace(PERSISTENT=2),
    )


async def _connected_transport(channels: list[FakeChannel] | None = None):
    connection = FakeConnection(channels)
    calls = []

    async def connector(url, **kwargs):
        calls.append((url, kwargs))
        return connection

    transport = RabbitMQTransport(
        _settings(),
        connector=connector,
        aio_pika_module=_module(),
    )
    await transport.connect()
    return transport, connection, calls


def test_settings_require_explicit_safe_url_and_hide_credentials():
    settings = RabbitMQSettings.from_env(
        {
            "QC_RABBITMQ_URL": "amqps://user:password@mq.internal/%2Fmedqc",
            "QC_RABBITMQ_EXCHANGE": "qc.dispatch",
            "QC_RABBITMQ_QUEUE": "qc.main",
            "QC_RABBITMQ_DEAD_QUEUE": "qc.dead",
        }
    )

    assert settings.prefetch == 1
    assert "password" not in repr(settings)
    with pytest.raises(RabbitMQConfigurationError, match="required"):
        RabbitMQSettings.from_env({})
    with pytest.raises(RabbitMQConfigurationError, match="invalid"):
        RabbitMQSettings(
            url="https://mq.internal/%2Fmedqc",
            exchange="qc.dispatch",
            queue="qc.main",
            dead_queue="qc.dead",
        )
    with pytest.raises(RabbitMQConfigurationError, match="explicit vhost"):
        RabbitMQSettings(
            url="amqp://mq.internal",
            exchange="qc.dispatch",
            queue="qc.main",
            dead_queue="qc.dead",
        )
    with pytest.raises(RabbitMQConfigurationError) as exc_info:
        RabbitMQSettings(
            url="amqp://user:secret@mq.internal:invalid/%2Fmedqc",
            exchange="qc.dispatch",
            queue="qc.main",
            dead_queue="qc.dead",
        )
    assert exc_info.value.__cause__ is None
    assert "secret" not in repr(exc_info.value)


@pytest.mark.asyncio
async def test_connect_declares_durable_topology_and_rebuilds_closed_channel():
    first = FakeChannel()
    second = FakeChannel()
    transport, connection, calls = await _connected_transport([first, second])

    assert connection.channel_calls == [
        {"publisher_confirms": True, "on_return_raises": True}
    ]
    assert first.qos_calls == [{"prefetch_count": 1, "global_": False}]
    assert first.exchange_calls == [
        (
            "medqc.qc.dispatch",
            {"type": "direct", "durable": True, "auto_delete": False},
        )
    ]
    assert first.queue_calls == [
        (
            "medqc.qc.main",
            {
                "durable": True,
                "exclusive": False,
                "auto_delete": False,
                "arguments": {"x-queue-type": "classic"},
            },
        ),
        (
            "medqc.qc.dead",
            {
                "durable": True,
                "exclusive": False,
                "auto_delete": False,
                "arguments": {"x-queue-type": "classic"},
            },
        ),
    ]
    assert first.queues["medqc.qc.main"].binds[0][1] == "medqc.qc.main"
    assert first.queues["medqc.qc.dead"].binds[0][1] == "medqc.qc.dead"
    assert calls[0][1]["client_properties"] == {
        "connection_name": "medqc-qc-dispatch"
    }

    first.is_closed = True
    await transport.connect()

    assert len(calls) == 1
    assert len(connection.channel_calls) == 2
    assert second.exchange_calls
    assert len(second.queue_calls) == 2


@pytest.mark.asyncio
async def test_publish_uses_persistent_message_mandatory_routing_and_real_serialization():
    transport, _, _ = await _connected_transport()
    envelope = BatchDispatchEnvelope.new(
        job_id="36effbd6-ace9-4ed9-ac4a-f41f98db5c47",
        generation=2,
        message_id="096df71b-5d99-4d28-a40f-5cb46b09debb",
    )

    await transport.publish(envelope, target="main")
    await transport.publish(envelope, target="dead")

    exchange = transport._exchange
    first_message, first_kwargs = exchange.publishes[0]
    assert BatchDispatchEnvelope.from_bytes(first_message.body) == envelope
    assert first_message.delivery_mode == 2
    assert first_message.message_id == envelope.message_id
    assert first_message.headers == {"schema_version": 1}
    assert first_kwargs == {
        "routing_key": "medqc.qc.main",
        "mandatory": True,
        "timeout": 10.0,
    }
    assert exchange.publishes[1][1]["routing_key"] == "medqc.qc.dead"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("confirmation", "expected_code"),
    [(None, "confirm_missing"), (True, "confirm_missing"), (Nack(), "publish_nack")],
)
async def test_publish_requires_explicit_basic_ack(confirmation, expected_code):
    transport, _, _ = await _connected_transport()
    transport._exchange.confirmation = confirmation
    envelope = BatchDispatchEnvelope.new(
        job_id="36effbd6-ace9-4ed9-ac4a-f41f98db5c47",
        generation=1,
    )

    with pytest.raises(RabbitMQTransportError) as exc_info:
        await transport.publish(envelope)

    assert exc_info.value.code == expected_code


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", (DeliveryError, PublishError))
async def test_publish_maps_mandatory_return_without_leaking_original_error(error_type):
    transport, _, _ = await _connected_transport()
    transport._exchange.error = error_type("amqp://user:secret@mq/ leaked")

    with pytest.raises(RabbitMQTransportError) as exc_info:
        await transport.publish(
            BatchDispatchEnvelope.new(
                job_id="36effbd6-ace9-4ed9-ac4a-f41f98db5c47",
                generation=1,
            )
        )

    assert exc_info.value.code == "unroutable"
    assert "secret" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_typed_delivery_rejection_is_nack_and_return_subclass_is_unroutable():
    transport, _, _ = await _connected_transport()
    transport._aio_pika.exceptions = SimpleNamespace(DeliveryError=DeliveryError, PublishError=PublishError)
    envelope = BatchDispatchEnvelope.new(job_id="36effbd6-ace9-4ed9-ac4a-f41f98db5c47", generation=1)
    for error, code in ((DeliveryError("synthetic"), "publish_nack"), (PublishError("synthetic"), "unroutable")):
        transport._exchange.error = error
        with pytest.raises(RabbitMQTransportError) as raised:
            await transport.publish(envelope)
        assert raised.value.code == code


@pytest.mark.asyncio
async def test_delivery_manual_ack_reject_and_no_requeue():
    incoming = FakeIncoming(b"{}")
    delivery = RabbitMQDelivery(b"{}", incoming)

    await delivery.ack()

    assert incoming.acks == [False]
    assert delivery.settled is True
    with pytest.raises(RabbitMQDeliveryError) as exc_info:
        await delivery.ack()
    assert exc_info.value.code == "delivery_already_settled"

    rejected_incoming = FakeIncoming(b"{}")
    rejected = RabbitMQDelivery(b"{}", rejected_incoming)
    with pytest.raises(RabbitMQDeliveryError, match="not allowed"):
        await rejected.reject(requeue=True)
    await rejected.reject()
    assert rejected_incoming.rejects == [False]


@pytest.mark.asyncio
async def test_delivery_does_not_mark_settled_when_ack_channel_fails():
    delivery = RabbitMQDelivery(b"{}", FakeIncoming(b"{}", ack_fails=True))

    with pytest.raises(RabbitMQDeliveryError) as exc_info:
        await delivery.ack()

    assert exc_info.value.code == "ack_failed"
    assert delivery.settled is False
    assert "secret" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_iter_deliveries_uses_manual_ack_and_stops_before_new_work_on_disconnect():
    channel = FakeChannel()
    transport, connection, _ = await _connected_transport([channel])
    incoming = FakeIncoming(b"safe-reference")
    channel.queues["medqc.qc.main"].messages.append(incoming)

    deliveries = transport.iter_deliveries()
    delivery = await anext(deliveries)
    assert delivery.body == b"safe-reference"
    assert incoming.acks == []
    await deliveries.aclose()
    assert channel.queues["medqc.qc.main"].iterator_calls == [False]

    channel.queues["medqc.qc.main"].messages.append(incoming)
    connection.is_closed = True
    with pytest.raises(RabbitMQTransportError) as exc_info:
        await anext(transport.iter_deliveries())
    assert exc_info.value.code == "connection_failed"
    assert incoming.acks == []


@pytest.mark.asyncio
async def test_close_clears_state_and_closes_channel_and_connection():
    transport, connection, _ = await _connected_transport()
    channel = transport._channel

    await transport.close()

    assert channel.close_calls == 1
    assert connection.close_calls == 1
    assert transport.connected is False


@pytest.mark.asyncio
async def test_missing_dependency_fails_startup_without_url_in_error(monkeypatch):
    def missing(_name: str):
        raise ImportError("aio-pika absent")

    monkeypatch.setattr(
        "app.services.qc_dispatch.rabbitmq_transport.importlib.import_module",
        missing,
    )
    transport = RabbitMQTransport(_settings())

    with pytest.raises(RabbitMQTransportError) as exc_info:
        await transport.connect()

    assert exc_info.value.code == "dependency_missing"
    assert "top-secret" not in repr(exc_info.value)
