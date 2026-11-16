"""合成传输异常：日志保留阶段，不保留异常自由文本。"""

import logging
import socket
import ssl
from uuid import uuid4

import httpx
import pytest

from app.core import http
from app.core.llm_transport_diagnostics import transport_diagnostic_scope
from app.core.llm_http_proxy import LLMHTTPProxyPolicy


@pytest.mark.parametrize("error_type,phase,kind", (
    (httpx.ConnectTimeout, "connect", "connect_timeout"),
    (httpx.ReadTimeout, "read", "read_timeout"),
    (httpx.WriteTimeout, "write", "write_timeout"),
    (httpx.PoolTimeout, "pool", "pool_timeout"),
    (httpx.ConnectError, "connect", "connect_error"),
    (httpx.RemoteProtocolError, "protocol", "remote_protocol_error"),
    (httpx.ProxyError, "proxy", "proxy_error"),
    (httpx.TransportError, "unknown", "transport_error"),
))
def test_real_http_boundary_logs_only_safe_fields(caplog, error_type, phase, kind):
    secret = "SYNTHETIC-SECRET-AND-PATIENT-TEXT"
    event_id = str(uuid4())

    def handler(request):
        raise error_type(secret, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with caplog.at_level(logging.WARNING), transport_diagnostic_scope(event_id):
            with pytest.raises(error_type):
                http._post_json(client, "https://synthetic.test/secret-path", {"Authorization": secret},
                                {"content": secret}, 17, allow_disconnect_retry=False)
    assert f"event_id={event_id}" in caplog.text
    assert f"phase={phase}" in caplog.text
    assert f"error_kind={kind}" in caplog.text
    assert "effective_timeout_seconds=17" in caplog.text
    assert "transport_attempt=1" in caplog.text
    assert secret not in caplog.text
    assert "synthetic.test" not in caplog.text
    assert "secret-path" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_proxy_masking_keeps_original_safe_subtype_in_log(caplog):
    def handler(request):
        raise httpx.ConnectError("SYNTHETIC-SECRET") from ssl.SSLCertVerificationError("SYNTHETIC-CERT")

    transport = httpx.MockTransport(handler)
    resources = http._SharedHttpResources(1,
        proxy_policy=LLMHTTPProxyPolicy.parse("http://192.0.2.10:18090", "synthetic.test"),
        transport=transport, proxy_transport=transport)
    try:
        with caplog.at_level(logging.WARNING), transport_diagnostic_scope(str(uuid4())):
            with pytest.raises(httpx.TransportError, match="llm_http_proxy_transport_error"):
                resources.post_json("https://synthetic.test/v1", {}, {}, 19)
        assert "phase=tls" in caplog.text
        assert "error_kind=tls_certificate_error" in caplog.text
        assert "SYNTHETIC" not in caplog.text
    finally:
        resources.client.close()
        resources.proxy_client.close()
        resources.executor.shutdown()


def test_unknown_cause_and_untrusted_event_id_are_not_echoed(caplog):
    def handler(request):
        raise httpx.ConnectError("secret") from OSError(987654, "secret")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with caplog.at_level(logging.WARNING), transport_diagnostic_scope("secret-case-id"):
            with pytest.raises(httpx.ConnectError):
                http._post_json(client, "https://synthetic.test", {}, {}, 11)
    assert "event_id=unbound" in caplog.text
    assert "os_error=unknown" in caplog.text
    assert "secret" not in caplog.text
    assert "987654" not in caplog.text


def test_existing_disconnect_retry_policy_and_ordinal_are_preserved(caplog):
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.RemoteProtocolError("Server disconnected without sending a response")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with caplog.at_level(logging.WARNING), pytest.raises(httpx.RemoteProtocolError):
            http._post_json(client, "https://synthetic.test", {}, {}, 11)
    assert len(calls) == 2
    assert "transport_attempt=1" in caplog.text and "transport_attempt=2" in caplog.text


def test_dns_cause_is_classified_without_free_text(caplog):
    def handler(request):
        raise httpx.ConnectError("secret") from socket.gaierror(socket.EAI_NONAME, "secret-host")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with caplog.at_level(logging.WARNING), pytest.raises(httpx.ConnectError):
            http._post_json(client, "https://synthetic.test", {}, {}, 11)
    assert "phase=dns" in caplog.text and "os_error=dns_name_not_found" in caplog.text
    assert "secret" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type,reason", ((httpx.ReadTimeout, "model_timeout"),
                                             (httpx.ConnectError, "model_transport_error")))
async def test_client_threaded_transport_keeps_event_binding_and_retry_contract(monkeypatch, caplog, error_type, reason):
    from app.services.llm_observability import LLMObservabilityRecorder
    from app.services.qc_execution_errors import SafeExecutionError
    from app.services.qc_llm_client import SichuanQCLLMClient

    class Store:
        def __init__(self):
            self.started = []
            self.finished = []

        async def start_attempt(self, event):
            self.started.append(dict(event))

        async def finish_attempt(self, event_id, changes):
            self.finished.append({"event_id": event_id, **dict(changes)})

    def handler(request):
        raise error_type("SYNTHETIC-SECRET", request=request)

    resources = http._SharedHttpResources(1, proxy_policy=LLMHTTPProxyPolicy(),
                                         transport=httpx.MockTransport(handler))
    monkeypatch.setattr(http, "_shared_resources", resources)
    monkeypatch.setattr(http, "_is_allowed_host", lambda host: host == "synthetic.test")
    store = Store()
    client = SichuanQCLLMClient(config={"provider_code": "alibaba", "model": "qwen3.8-flash",
        "api_endpoint": "https://synthetic.test/v1", "api_key": "SYNTHETIC-SECRET",
        "timeout_seconds": 23}, observability_recorder=LLMObservabilityRecorder(store=store))
    try:
        with caplog.at_level(logging.WARNING), pytest.raises(SafeExecutionError) as error:
            await client.generate("SYNTHETIC-PATIENT-TEXT")
        assert error.value.reason_code == reason and error.value.retryable is True
        assert len(store.started) == len(store.finished) == 1
        assert f"event_id={store.started[0]['event_id']}" in caplog.text
        assert "effective_timeout_seconds=23" in caplog.text
        assert "SYNTHETIC" not in caplog.text
    finally:
        http.close_shared_http_resources()
