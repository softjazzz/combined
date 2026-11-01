"""RabbitMQ 传输的独立、失败关闭配置。"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Mapping
from urllib.parse import unquote, urlsplit


_AMQP_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class RabbitMQConfigurationError(RuntimeError):
    """配置不完整或不安全。

    异常文本只使用固定描述，不带连接串、凭据或队列消息。
    """


@dataclass(frozen=True, slots=True)
class RabbitMQSettings:
    """QC Worker/Publisher 共用的 AMQP 设置。"""

    url: str = field(repr=False)
    exchange: str
    queue: str
    dead_queue: str
    prefetch: int = 1
    connect_timeout_seconds: float = 10.0
    publish_timeout_seconds: float = 10.0
    queue_type: str = field(default="classic", init=False)

    def __post_init__(self) -> None:
        _validate_url(self.url)
        for name, value in (
            ("exchange", self.exchange),
            ("queue", self.queue),
            ("dead queue", self.dead_queue),
        ):
            if not isinstance(value, str) or not _AMQP_NAME_RE.fullmatch(value):
                raise RabbitMQConfigurationError(f"RabbitMQ {name} is invalid")
        if self.queue == self.dead_queue:
            raise RabbitMQConfigurationError("RabbitMQ queues must be distinct")
        if isinstance(self.prefetch, bool) or self.prefetch != 1:
            raise RabbitMQConfigurationError("RabbitMQ prefetch must be 1")
        _validate_timeout(self.connect_timeout_seconds, "connect timeout")
        _validate_timeout(self.publish_timeout_seconds, "publish timeout")

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "RabbitMQSettings":
        env = os.environ if environ is None else environ
        url = _required(env, "QC_RABBITMQ_URL")
        exchange = _required(env, "QC_RABBITMQ_EXCHANGE")
        queue = _required(env, "QC_RABBITMQ_QUEUE")
        dead_queue = _required(env, "QC_RABBITMQ_DEAD_QUEUE")
        prefetch = _parse_prefetch(env.get("QC_RABBITMQ_PREFETCH", "1"))
        return cls(
            url=url,
            exchange=exchange,
            queue=queue,
            dead_queue=dead_queue,
            prefetch=prefetch,
        )


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if not isinstance(value, str) or not value or value.strip() != value:
        raise RabbitMQConfigurationError(f"{name} is required")
    return value


def _validate_url(value: object) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or any(ord(character) < 33 or ord(character) == 127 for character in value)
    ):
        raise RabbitMQConfigurationError("RabbitMQ URL is required")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError):
        raise RabbitMQConfigurationError("RabbitMQ URL is invalid") from None
    if parsed.scheme.lower() not in {"amqp", "amqps"} or not parsed.hostname:
        raise RabbitMQConfigurationError("RabbitMQ URL is invalid")
    if parsed.query or parsed.fragment or port == 0:
        raise RabbitMQConfigurationError("RabbitMQ URL is invalid")

    # RabbitMQ URI 中 vhost 是唯一 path segment；要求显式写在 URL 内。
    encoded_vhost = parsed.path[1:] if parsed.path.startswith("/") else ""
    if (
        not encoded_vhost
        or "/" in encoded_vhost
        or re.search(r"%(?![0-9A-Fa-f]{2})", encoded_vhost)
        or not unquote(encoded_vhost)
    ):
        raise RabbitMQConfigurationError("RabbitMQ URL must include an explicit vhost")


def _parse_prefetch(value: object) -> int:
    if not isinstance(value, str) or value.strip() != "1":
        raise RabbitMQConfigurationError("QC_RABBITMQ_PREFETCH must be 1")
    return 1


def _validate_timeout(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RabbitMQConfigurationError(f"RabbitMQ {name} is invalid")
    if value <= 0 or value > 300:
        raise RabbitMQConfigurationError(f"RabbitMQ {name} is invalid")
