"""模型调用边界的受控异常分类；不输出异常文字、响应、URL 或凭据。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re

import httpx


def classify_model_failure(error: Exception, *, stage: str = "call") -> tuple[str, str, bool]:
    """返回诊断类别、失败原因码和是否属于瞬时上游错误。"""
    if isinstance(error, (httpx.TimeoutException, TimeoutError)):
        return "timeout", "model_timeout", True
    response = getattr(error, "response", None)
    code = getattr(response, "status_code", None)
    if type(code) is not int:
        # 现有客户端把非2xx收敛为带固定数字标记的RuntimeError。
        match = re.search(r"\bupstream_http_status=(\d{3})\b", str(error))
        code = int(match.group(1)) if match else None
    if code == 429:
        return "upstream_429", "model_rate_limited", True
    if code is not None and 500 <= code <= 599:
        return "upstream_5xx", "model_upstream_error", True
    if code is not None and 400 <= code <= 499:
        return "upstream_4xx", "model_http_error", False
    if isinstance(error, (httpx.TransportError, ConnectionError)):
        return "http_transport", "model_transport_error", True
    if isinstance(error, json.JSONDecodeError):
        return "response_json", "model_parse_error", False
    if stage == "validate" and isinstance(error, (ValueError, TypeError, KeyError)):
        return "response_protocol", "model_invalid_output", False
    if stage == "call" and isinstance(error, RuntimeError) and any(
        marker in str(error).lower() for marker in (
            "not configured", "configuration", "missing api key", "missing endpoint",
        )
    ):
        return "configuration", "model_configuration_error", False
    return "program_error", "execution_program_error", False


def log_model_failure(logger: logging.Logger, *, rule: str, stage: str, error: Exception) -> None:
    kind, _, _ = classify_model_failure(error, stage=stage)
    trace = error.__traceback__
    while trace is not None and trace.tb_next is not None:
        trace = trace.tb_next
    origin = "unknown"
    line = 0
    if trace is not None:
        basename = Path(trace.tb_frame.f_code.co_filename).stem
        function = trace.tb_frame.f_code.co_name
        if all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,100}", item) for item in (basename, function)):
            origin = f"{basename}:{function}"
            line = trace.tb_lineno
    exception_type = type(error).__name__
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,80}", exception_type):
        exception_type = "Exception"
    logger.warning("LX0609_MODEL_FAILURE rule=%s stage=%s kind=%s exception_type=%s origin=%s line=%s",
                   rule, stage, kind, exception_type, origin, line)
