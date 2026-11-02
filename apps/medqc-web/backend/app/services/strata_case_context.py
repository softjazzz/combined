"""最小检查结果核验的显式前缀描述；不改写医学 Prompt。"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
import re


_CURRENT = ContextVar("strata_exam_result_prefix", default=None)
_VERSION = "exam-result-record-prefix-v1"
_START = "你核对报告出具后的病程是否记录了本次CT/MRI报告的结果"
_MARKER = "\nEVENTS_JSON="


@dataclass
class _RequestBudget:
    remaining: int
    active: bool = True


@dataclass
class _PrefixScope:
    budget: _RequestBudget
    active: bool = True


@contextmanager
def exam_result_prefix_scope(*, expected_requests: int | None = None):
    """显式调度预算才可>=2；生产者默认不预测补核必然发生。"""
    outer = _CURRENT.get()
    inherits = expected_requests is None and outer is not None and outer.active and outer.budget.active
    if expected_requests is None:
        expected_requests = max(1, outer.budget.remaining) if inherits else 1
    if type(expected_requests) is not int or not 1 <= expected_requests <= 16:
        raise ValueError("invalid prefix request budget")
    budget = outer.budget if inherits else _RequestBudget(expected_requests)
    scope = _PrefixScope(budget)
    token = _CURRENT.set(scope)
    try:
        yield
    finally:
        scope.active = False
        if not inherits:
            budget.active = False
        _CURRENT.reset(token)


def consume_exam_result_prefix_request():
    """仅在最终隐私校验后、提交Gateway描述符前扣除，不跨await持锁。"""
    scope = _CURRENT.get()
    if scope is not None and scope.active and scope.budget.active:
        scope.budget.remaining = max(0, scope.budget.remaining - 1)


def current_exam_result_prefix(payload, *, model_role="first_pass"):
    """对最终脱敏内容计算偏移/摘要；无病例归属时保留原始请求。"""
    from .llm_dispatch.contracts import GatewayCasePrefix
    from .llm_observability import current_llm_observation_context, opaque_observation_id
    from .luxian_0609.exam_result_record_check import SCHEMA_VERSION

    scope = _CURRENT.get()
    if scope is None or not scope.active or not scope.budget.active:
        return None
    context = current_llm_observation_context()
    if not isinstance(context.record_key_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", context.record_key_hash):
        return None
    messages = payload.get("messages")
    if not isinstance(messages, list) or len(messages) != 1:
        return None
    message = messages[0]
    if not isinstance(message, dict) or set(message) != {"role", "content"} or message["role"] != "user":
        return None
    text = message["content"]
    if not isinstance(text, str) or not text.startswith(_START) or len(text) > 262144:
        return None
    split = text.rfind(_MARKER)
    if split <= 0:
        return None
    try:
        data = json.loads(text[split + len(_MARKER):])
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("events"), list) or not isinstance(data.get("course_docs"), list):
        return None
    start = split + 1  # 保留原换行于指令段，证据段包含完整EVENTS_JSON标签。
    case_key = opaque_observation_id("strata_case_prefix", json.dumps([
        context.record_key_hash, context.root_job_id, context.rule_set_key, context.rule_set_version,
        model_role,
    ], ensure_ascii=False, separators=(",", ":")))
    return GatewayCasePrefix(
        case_key=case_key, evidence_version=hashlib.sha256(text[start:].encode("utf-8")).hexdigest(),
        # 修改医学Prompt或拆分协议时必须升级_VERSION；schema另外显式绑定。
        context_version=f"{_VERSION}-schema-{SCHEMA_VERSION}",
        prefix_start=start, expected_requests=max(1, scope.budget.remaining),
    )
