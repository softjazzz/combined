"""执行错误的安全合同：只输出受控类别，未知错误不自动重试。"""

from __future__ import annotations

from collections.abc import Mapping
import json
import re
from typing import Any

import httpx

from .llm_context_contract import CONTEXT_FAILURE_REASON_CODES


_ERRORS = {
    "model_timeout": ("model_timeout", True, "模型服务响应超时，可稍后重试。"),
    "model_transport_error": ("model_connection", True, "模型服务连接暂时失败，可稍后重试。"),
    "model_rate_limited": ("model_rate_limit", True, "模型服务暂时限流，可稍后重试。"),
    "model_upstream_error": ("model_unavailable", True, "模型服务暂时不可用，可稍后重试。"),
    "model_retry_stopped": ("model_unavailable", False, "模型调用未完成，本次错误不再自动重试。"),
    "model_http_error": ("model_request", False, "模型服务拒绝请求，请检查模型配置和访问权限。"),
    "model_configuration_error": ("model_configuration", False, "模型服务配置不可用，请检查配置后重试。"),
    "model_invalid_output": ("model_output", False, "模型返回内容未满足结果格式要求。"),
    "model_parse_error": ("model_output", False, "模型返回内容无法解析。"),
    "privacy_guard_blocked": ("privacy_guard", False, "模型请求未通过隐私保护检查。"),
    "execution_program_error": ("execution", False, "规则执行异常，请联系管理员检查。"),
    "execution_failed": ("unknown", False, "规则执行未完成，请检查后重试。"),
    "executor_timeout": ("execution_timeout", True, "规则执行超时，可稍后重试。"),
}
_TASK_CONTRACT_MESSAGES = {
    "task_settings_missing": "LX0609任务缺少冻结执行配置，请重新创建任务。",
    "task_settings_changed": "LX0609任务执行配置已变化，请重新创建任务。",
    "task_runtime_missing": "LX0609任务缺少冻结运行身份，请重新创建任务。",
    "task_runtime_changed": "LX0609任务模型或实现版本已变化，请重新创建任务。",
    "task_scope_invalid": "LX0609任务病例规则范围不完整，请重新创建任务。",
}
for _code, _message in _TASK_CONTRACT_MESSAGES.items():
    _ERRORS[_code] = ("execution_contract", False, _message)
for _code in CONTEXT_FAILURE_REASON_CODES:
    _ERRORS[_code] = ("model_context", False, "模型执行上下文不满足要求，请检查配置或材料范围。")
for _code in (
    "customer_result_contract_violation", "family_result_invalid", "family_result_missing",
    "family_result_duplicate", "family_result_extra", "family_result_order_mismatch",
    "family_result_scope_mismatch", "executor_exception", "semantic_output_unknown",
):
    _ERRORS[_code] = ("execution", False, "规则执行未形成符合交付要求的结果。")
_ERRORS["candidate_scope_incomplete"] = ("material", False, "当前候选材料范围不满足执行要求。")

_GATEWAY_REASONS = {
    "gateway_request_timeout": "model_timeout",
    "gateway_provider_timeout": "model_timeout",
    "gateway_transport_error": "model_transport_error",
    "gateway_queue_full": "model_rate_limited",
    "gateway_shutting_down": "model_upstream_error",
    "gateway_provider_unavailable": "model_upstream_error",
    "gateway_invalid_auth": "model_configuration_error",
    "gateway_invalid_profile": "model_configuration_error",
    "gateway_proxy_configuration_invalid": "model_configuration_error",
    "gateway_invalid_request": "model_http_error",
    "gateway_invalid_provider_payload": "model_http_error",
    "gateway_provider_rejected": "model_http_error",
    "gateway_invalid_response": "model_invalid_output",
    "gateway_invalid_provider_response": "model_invalid_output",
    "strata_structured_output_failed": "model_invalid_output",
}


def safe_failure_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    """纯投影，不接受上游自由文本；retryable 只能收紧既有受控类别。"""
    reason = value.get("reason_code")
    from .material_admission import MESSAGES as material_messages
    if isinstance(reason, str) and reason in material_messages:
        return {"reason_code": reason, "error_category": "material", "retryable": False,
                "error": material_messages[reason]}
    if not isinstance(reason, str) or reason not in _ERRORS:
        reason = "execution_failed"
    category, retryable, message = _ERRORS[reason]
    if value.get("retryable") is False and retryable:
        # 部分旧执行器只传 reason_code；终止语义也进入原因码，避免后层重新开启重试。
        reason = "model_retry_stopped"
        category, retryable, message = _ERRORS[reason]
    return {"reason_code": reason, "error_category": category,
            "retryable": retryable, "error": message}


def http_failure(status: Any) -> dict[str, Any]:
    if type(status) is not int:
        reason = "execution_failed"
    elif status == 429:
        reason = "model_rate_limited"
    elif status == 408:
        reason = "model_timeout"
    elif 500 <= status <= 599:
        reason = "model_upstream_error"
    elif 400 <= status <= 499:
        reason = "model_http_error"
    else:
        reason = "execution_failed"
    return safe_failure_projection({"reason_code": reason})


class SafeExecutionError(RuntimeError):
    """不携带响应正文、URL、凭据或患者内容的异常。"""

    def __init__(self, reason_code: str, *, status_code: int | None = None,
                 retryable: bool | None = None) -> None:
        failure = safe_failure_projection({"reason_code": reason_code, "retryable": retryable})
        self.reason_code = failure["reason_code"]
        self.error_category = failure["error_category"]
        self.retryable = failure["retryable"]
        self.status_code = status_code if type(status_code) is int and 100 <= status_code <= 599 else None
        super().__init__(failure["error"])


def safe_exception_failure(error: BaseException, *, stage: str = "call") -> dict[str, Any]:
    if isinstance(error, SafeExecutionError):
        return safe_failure_projection({"reason_code": error.reason_code, "retryable": error.retryable})
    from .task_execution_contract import TaskExecutionContractError
    from .luxian_0609.llm_prompt_privacy import PatientPrivacyViolation, PrivacyIdentityContextError

    if isinstance(error, TaskExecutionContractError):
        reason = error.code if error.code in _TASK_CONTRACT_MESSAGES else "execution_program_error"
        return safe_failure_projection({"reason_code": reason})
    if isinstance(error, (PatientPrivacyViolation, PrivacyIdentityContextError)):
        return safe_failure_projection({"reason_code": "privacy_guard_blocked"})
    code = getattr(error, "code", None)
    from .material_admission import MESSAGES as material_messages
    if type(error).__name__ == "MaterialSnapshotError" and str(error) in material_messages:
        return safe_failure_projection({"reason_code": str(error)})
    if code == "gateway_provider_rejected":
        # 现有 Gateway 将上游 429/5xx 收敛为此安全码 + retryable + HTTP503。
        # 保留该已验证合同，不能把模型确定性拒绝或未知码提升成可重试。
        transient = getattr(error, "retryable", None) is True and getattr(error, "status_code", None) in {None, 503}
        return safe_failure_projection({"reason_code": "model_upstream_error" if transient else "model_http_error"})
    if isinstance(code, str) and code in {"gateway_error", "gateway_invalid_response"} and type(getattr(error, "status_code", None)) is int:
        result = http_failure(error.status_code)
        if getattr(error, "retryable", None) is False:
            result = safe_failure_projection({**result, "retryable": False})
        return result
    if isinstance(code, str) and (code in _GATEWAY_REASONS or code in CONTEXT_FAILURE_REASON_CODES):
        return safe_failure_projection({"reason_code": _GATEWAY_REASONS.get(code, code),
                                        "retryable": getattr(error, "retryable", None)})
    status = getattr(error, "status_code", None)
    if type(status) is not int:
        status = getattr(getattr(error, "response", None), "status_code", None)
    if type(status) is not int and isinstance(error, RuntimeError):
        # 兼容旧客户端固定数字标记；绝不输出或持久化异常文字。
        match = re.search(r"\bupstream_http_status=(\d{3})\b", str(error))
        status = int(match.group(1)) if match else None
    if type(status) is int:
        result = http_failure(status)
        if getattr(error, "retryable", None) is False:
            result = safe_failure_projection({**result, "retryable": False})
        return result
    if isinstance(error, (httpx.TimeoutException, TimeoutError)):
        reason = "model_timeout"
    elif isinstance(error, (httpx.TransportError, ConnectionError)):
        reason = "model_transport_error"
    elif isinstance(error, json.JSONDecodeError):
        reason = "model_parse_error"
    elif stage == "validate" and isinstance(error, (ValueError, TypeError, KeyError)):
        reason = "model_invalid_output"
    elif type(error).__name__ == "ProviderConfigurationError" or (
        isinstance(error, RuntimeError) and any(marker in str(error).lower() for marker in
        ("not configured", "configuration", "missing api key", "missing endpoint"))
    ):
        reason = "model_configuration_error"
    else:
        reason = "execution_program_error"
    return safe_failure_projection({"reason_code": reason,
                                    "retryable": getattr(error, "retryable", None)})
