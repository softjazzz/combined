"""异常分类使用真实异常类型，但不发HTTP请求、不输出原始异常信息。"""

import json
import logging

import httpx
import pytest

from app.services.luxian_0609.model_failure import classify_model_failure, log_model_failure


@pytest.mark.parametrize(("error", "stage", "reason", "retryable"), [
    (httpx.ReadTimeout("SECRET"), "call", "model_timeout", True),
    (httpx.ConnectError("SECRET"), "call", "model_transport_error", True),
    (ConnectionError("SECRET"), "call", "model_transport_error", True),
    (RuntimeError("upstream_http_status=429 SECRET"), "call", "model_rate_limited", True),
    (RuntimeError("upstream_http_status=503 SECRET"), "call", "model_upstream_error", True),
    (RuntimeError("upstream_http_status=401 SECRET"), "call", "model_http_error", False),
    (RuntimeError("missing API key SECRET"), "call", "model_configuration_error", False),
    (json.JSONDecodeError("SECRET", "SECRET", 0), "validate", "model_parse_error", False),
    (ValueError("SECRET"), "validate", "model_invalid_output", False),
    (TypeError("SECRET"), "call", "execution_program_error", False),
    (ValueError("SECRET"), "aggregate", "execution_program_error", False),
])
def test_classifies_failure_by_type_and_boundary_without_messages(caplog, error, stage, reason, retryable):
    assert classify_model_failure(error, stage=stage)[1:] == (reason, retryable)
    logger = logging.getLogger("synthetic-failure")
    with caplog.at_level(logging.WARNING):
        try:
            raise error
        except Exception as caught:
            log_model_failure(logger, rule="LX0609-03-01-04", stage=stage, error=caught)
    assert "SECRET" not in caplog.text
    assert "origin=" in caplog.text and "line=" in caplog.text
