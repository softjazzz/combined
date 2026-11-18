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
                        and inner.value in _TRANSPORT_ALIASES
                        and id(inner) not in allowed
                    ):
                        key = (path.relative_to(LUXIAN_ROOT).as_posix(), inner.value)
                        if key not in _EXEMPT:
                            offenders.append(f"{key[0]}:{inner.lineno} {inner.value}")
    assert offenders == []


# 会被下游映射为可重试传输错误的各族别名（含 MDT 急诊确认的 "transport" 状态）。
_TRANSPORT_ALIASES = frozenset({
    "model_transport_error", "transport", "tumor_llm_failure",
    "malignancy_llm_transport_error", "surgery_llm_failure", "exam_lab_llm_failure",
    "llm_transport_error", "surgery_document_llm_failure", "consultation_llm_failure",
    "course_llm_failure",
})
# 豁免：首次调用失败直接落 data_gap（不进入自动补跑分支；改为 technical_error 会改变
# 结果状态合同，作为遗留另行处理），或影子审计独立码空间，不参与正式结果。
# 会诊并发汇总已改走共享函数，不再豁免。
_EXEMPT = frozenset({
    ("native_course_quality_execution.py", "course_llm_failure"),
    ("native_exam_lab_execution.py", "exam_lab_llm_failure"),
    ("native_surgery_document_execution.py", "surgery_document_llm_failure"),
    ("native_surgery_gate_execution.py", "surgery_llm_failure"),
    ("native_treatment_order_consistency.py", "llm_transport_error"),
})


def test_mdt_emergency_confirm_privacy_block_is_not_transport():
    from app.services.luxian_0609.native_mdt_execution import _confirm_emergency_surgery

    state, calls, _usage = asyncio.run(_confirm_emergency_surgery(["合成急诊文本"], _ViolationClient()))
    assert state == "privacy_guard_blocked" and calls == 1


def test_malignancy_resolver_privacy_block_is_not_transport():
    from app.services.luxian_0609.malignancy_fact import MalignancyFactResolver, MalignancySource

    rows = ({"document_id": "synthetic", "diagnosis_name": "合成诊断"},)
    resolution, _ = asyncio.run(
        MalignancyFactResolver(_ViolationClient())._resolve_uncached(
            (MalignancySource("diagnosis", "available", rows),)
        )
    ) if hasattr(MalignancyFactResolver, "_resolve_uncached") else (
        asyncio.run(MalignancyFactResolver(_ViolationClient()).resolve(
            (MalignancySource("diagnosis", "available", rows),)
        )), None,
    )
    assert resolution.state == "technical_error"
    _assert_privacy_blocked(resolution.reason_code)


# 包住模型调用的宽捕获，以及 gather(return_exceptions=True) 后的异常分支，必须能识别隐私拒绝：
# 引用共享函数/谓词或安全分类器，或原样上抛。否则补核、二次调用会把拒绝吞成无效输出或回退。
_MODEL_CALLS = (".generate(", "token_generate(", "_generate_exam_lab_fact_response(", "generate_response(")
_PRIVACY_AWARE = (
    "luxian_0609_llm_call_failure_reason", "is_luxian_0609_privacy_block",
    "classify_luxian_0609_llm_call_failure", "classify_model_failure",
    "safe_exception_failure", "safe_status_for_exception",
)
# (文件, 所在函数) -> 允许的未识别处理器数与原因。
_BROAD_HANDLER_EXEMPT = {
    ("llm_prompt_privacy.py", "generate"): (1, "包装器自身的传输重试；隐私拒绝在发送前已抛出"),
    ("native_consultation_episode_execution.py", "_execute_consultation_episode_rules"): (
        1, "首轮执行调用仅在可重试传输失败时补问，隐私拒绝原样上抛到外层 classify_model_failure"),
    ("consultation_measure_check.py", "check_consultation_measures"): (
        1, "措施核查失败按未核实并回 023，无原因码通道；调用点不在第二阶段处理器内，上抛会变执行器异常"),
    ("exam_finding_relevance.py", "classify_exam_finding_relevance"): (1, "相关性前置提示，失败时不带提示继续主抽取"),
    ("extended_document/discharge_course_content.py", "call"): (1, "首次调用，失败由调用方收敛为不确定"),
    ("prophylactic_antimicrobial_duration.py", "_infection_evidence"): (1, "首次调用，三元组返回无原因码通道"),
    ("native_exam_lab_execution.py", "execute_luxian_0609_native_exam_lab_rules"): (1, "首次调用，失败落 data_gap"),
    ("native_surgery_document_execution.py", "execute_luxian_0609_native_surgery_document_rules"): (
        1, "首次调用，失败落 data_gap"),
    ("native_surgery_gate_execution.py", "execute_luxian_0609_native_surgery_gate_rules"): (1, "首次调用，失败落 data_gap"),
    ("native_treatment_order_consistency.py", "evaluate_lx0609_059_treatment_order_consistency"): (
        1, "影子审计独立码空间"),
}


def _is_broad(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    names = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(getattr(name, "id", None) in {"Exception", "BaseException"} for name in names)


def _unaware_handlers():
    found: dict[tuple[str, str], int] = {}
    for path in sorted(LUXIAN_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

        def owner(node):
            enclosing = [f for f in functions if f.lineno <= node.lineno <= f.end_lineno]
            return max(enclosing, key=lambda f: f.lineno).name if enclosing else "<module>"

        def record(node):
            key = (path.relative_to(LUXIAN_ROOT).as_posix(), owner(node))
            found[key] = found.get(key, 0) + 1

        gathers_exceptions = "return_exceptions=True" in source
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                body = "\n".join(ast.get_source_segment(source, stmt) or "" for stmt in node.body)
                if not any(call in body for call in _MODEL_CALLS):
                    continue
                for handler in node.handlers:
                    segment = ast.get_source_segment(source, handler) or ""
                    if not _is_broad(handler) or any(name in segment for name in _PRIVACY_AWARE):
                        continue
                    if any(isinstance(stmt, ast.Raise) and stmt.exc is None for stmt in handler.body):
                        continue
                    record(handler)
            elif (
                gathers_exceptions
                and isinstance(node, ast.If)
                and isinstance(node.test, ast.Call)
                and getattr(node.test.func, "id", None) == "isinstance"
                and len(node.test.args) == 2
                and getattr(node.test.args[1], "id", None) in {"Exception", "BaseException"}
                and not any(name in (ast.get_source_segment(source, node) or "") for name in _PRIVACY_AWARE)
            ):
                record(node)
    return found


def test_model_call_broad_handlers_recognise_privacy_block():
    """补核、二次调用与并发汇总的异常分支不得把隐私拒绝吞成其他失败或回退。"""
    found = _unaware_handlers()
    unexpected = {
        key: count for key, count in found.items()
        if count > _BROAD_HANDLER_EXEMPT.get(key, (0, ""))[0]
    }
    assert unexpected == {}
    stale = sorted(key for key in _BROAD_HANDLER_EXEMPT if key not in found)
    assert stale == []
