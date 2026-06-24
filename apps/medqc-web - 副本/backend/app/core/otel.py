from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


def _read_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class OTelConfig:
    enabled: bool
    service_name: str
    endpoint: str
    sampler: str
    sampler_arg: str
    insecure: bool
    export_timeout_ms: int


def load_otel_config() -> OTelConfig:
    return OTelConfig(
        enabled=_read_bool_env("OTEL_ENABLED", default=False),
        service_name=os.getenv("OTEL_SERVICE_NAME", "medqc-backend"),
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip(),
        sampler=os.getenv("OTEL_TRACES_SAMPLER", "parentbased_always_on").strip(),
        sampler_arg=os.getenv("OTEL_TRACES_SAMPLER_ARG", "1.0").strip(),
        insecure=_read_bool_env("OTEL_EXPORTER_OTLP_INSECURE", default=True),
        export_timeout_ms=int(os.getenv("OTEL_EXPORTER_OTLP_TIMEOUT", "3000")),
    )


def _resolve_sampler(config: OTelConfig):
    from opentelemetry.sdk.trace.sampling import ALWAYS_OFF, ALWAYS_ON, ParentBased, TraceIdRatioBased

    sampler_name = config.sampler.lower()
    if sampler_name in {"always_off"}:
        return ALWAYS_OFF
    if sampler_name in {"always_on"}:
        return ALWAYS_ON
    if sampler_name in {"traceidratio", "traceidratio_based"}:
        try:
            ratio = float(config.sampler_arg)
        except ValueError:
            ratio = 1.0
        ratio = min(max(ratio, 0.0), 1.0)
        return ParentBased(TraceIdRatioBased(ratio))
    # default: parent-based always-on
    return ParentBased(ALWAYS_ON)


def _extract_scope_header(scope: dict[str, Any], key: str) -> str | None:
    raw_headers = scope.get("headers") or []
    key_bytes = key.encode("latin-1").lower()
    for k, v in raw_headers:
        if k.lower() == key_bytes:
            try:
                return v.decode("latin-1").strip()
            except Exception:
                return None
    return None


def _extract_traceparent_trace_id(traceparent: str | None) -> str | None:
    if not traceparent:
        return None
    parts = traceparent.strip().split("-")
    if len(parts) < 4:
        return None
    trace_id = parts[1].lower()
    if len(trace_id) != 32:
        return None
    if trace_id == "0" * 32:
        return None
    return trace_id


def _server_request_hook(span, scope: dict[str, Any]) -> None:
    if span is None:
        return
    trace_id = (
        _extract_scope_header(scope, "x-trace-id")
        or _extract_scope_header(scope, "x-request-id")
        or _extract_traceparent_trace_id(_extract_scope_header(scope, "traceparent"))
    )
    if trace_id:
        span.set_attribute("medqc.trace_id", trace_id)


def configure_otel(app) -> bool:
    """
    初始化 OpenTelemetry，默认关闭。
    - 关闭时零侵入返回 False
    - 启用失败时降级，不阻塞应用启动
    """
    config = load_otel_config()
    app.state.otel_enabled = False
    app.state.otel_reason = "disabled"

    if not config.enabled:
        logger.info("OpenTelemetry disabled by OTEL_ENABLED")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception as exc:
        logger.warning("OpenTelemetry dependencies unavailable, skip instrumentation: %s", exc)
        app.state.otel_reason = "deps_unavailable"
        return False

    try:
        resource = Resource.create({"service.name": config.service_name})
        provider = TracerProvider(resource=resource, sampler=_resolve_sampler(config))

        exporter_kwargs: dict[str, Any] = {"timeout": config.export_timeout_ms}
        if config.endpoint:
            exporter_kwargs["endpoint"] = config.endpoint
        if config.insecure:
            exporter_kwargs["insecure"] = True
        exporter = OTLPSpanExporter(**exporter_kwargs)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=provider,
            server_request_hook=_server_request_hook,
        )
        HTTPXClientInstrumentor().instrument(tracer_provider=provider)

        app.state.otel_enabled = True
        app.state.otel_reason = "enabled"
        logger.info(
            "OpenTelemetry enabled: service=%s endpoint=%s sampler=%s",
            config.service_name,
            config.endpoint or "<default>",
            config.sampler,
        )
        return True
    except Exception as exc:
        logger.warning("OpenTelemetry init failed, degrade to no-op: %s", exc, exc_info=True)
        app.state.otel_enabled = False
        app.state.otel_reason = "init_failed"
        return False
