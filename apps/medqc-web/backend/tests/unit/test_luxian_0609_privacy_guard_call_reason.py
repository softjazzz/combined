"""隐私护栏拦截不得被模型调用点归为可重试的传输错误。

只用合成身份与合成诊断名，不连接数据库、不调用真实模型。
"""
from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from app.services.luxian_0609.extended_document.discharge_diagnosis_equivalence import (
    extract_discharge_diagnosis_equivalence,
)
from app.services.luxian_0609.extended_document.invasive_procedure_record import (
    map_orders_to_invasive_catalog,
)
from app.services.luxian_0609.llm_prompt_privacy import (
    PatientPrivacyViolation,
    luxian_0609_llm_call_failure_reason,
    wrap_luxian_0609_llm_client,
)
from app.services.qc_execution_errors import safe_failure_projection

LUXIAN_ROOT = Path(__file__).resolve().parents[2] / "app" / "services" / "luxian_0609"


class _NeverCalledDelegate:
    """护栏必须在下游发送前拦截；被调用即说明拦截失效。"""

    calls = 0

    async def generate(self, prompt, **kwargs):
        type(self).calls += 1
        raise AssertionError("隐私护栏未拦截")


def _unavailable_identity():
    raise RuntimeError("合成：身份上下文不可用")


def _guarded_client():
    _NeverCalledDelegate.calls = 0
    return wrap_luxian_0609_llm_client(
        _NeverCalledDelegate(), identity_provider=_unavailable_identity
    )


class _ViolationClient:
    async def generate(self, prompt, **kwargs):
        raise PatientPrivacyViolation("Known patient identity remains")


def _assert_privacy_blocked(reason_code: str) -> None:
    assert reason_code == "privacy_guard_blocked"
    assert safe_failure_projection({"reason_code": reason_code})["retryable"] is False


@pytest.mark.parametrize("client_factory", [_guarded_client, _ViolationClient])
def test_diagnosis_equivalence_privacy_block_is_not_transport(client_factory):
    result = asyncio.run(
        extract_discharge_diagnosis_equivalence(
            ["合成诊断甲型"], ["合成诊断乙型"], client_factory()
        )
    )
    assert result.state == "technical_error"
    _assert_privacy_blocked(result.reason_code)
    assert _NeverCalledDelegate.calls == 0


@pytest.mark.parametrize("client_factory", [_guarded_client, _ViolationClient])
def test_invasive_call_privacy_block_is_not_transport(client_factory):
    result = asyncio.run(map_orders_to_invasive_catalog(["合成医嘱甲"], client_factory()))
    assert result.state == "technical_error"
    _assert_privacy_blocked(result.reason_code)


def test_shared_reason_keeps_fallback_for_other_errors():
    assert luxian_0609_llm_call_failure_reason(ConnectionError()) == "model_transport_error"
    assert (
        luxian_0609_llm_call_failure_reason(ValueError(), fallback="model_invalid_output")
        == "model_invalid_output"
    )
    _assert_privacy_blocked(
        luxian_0609_llm_call_failure_reason(PatientPrivacyViolation("x"))
    )


def test_no_generate_handler_hardcodes_transport_error():
    """所有包住 generate 的 except Exception 不得直接写死传输错误码。"""
    offenders = []
    for path in sorted(LUXIAN_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "model_transport_error" not in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Try):
                continue
            body = "\n".join(ast.get_source_segment(source, stmt) or "" for stmt in node.body)
            if ".generate(" not in body:
                continue
            for handler in node.handlers:
                # 只允许传输错误码作为共享函数的回退参数出现。
                allowed = {
                    id(inner)
                    for call in ast.walk(handler)
                    if isinstance(call, ast.Call)
                    and getattr(call.func, "id", None) == "luxian_0609_llm_call_failure_reason"
                    for inner in ast.walk(call)
                }
                for inner in ast.walk(handler):
                    if (
                        isinstance(inner, ast.Constant)
                        and inner.value == "model_transport_error"
                        and id(inner) not in allowed
                    ):
                        offenders.append(f"{path.relative_to(LUXIAN_ROOT)}:{inner.lineno}")
    assert offenders == []
