"""请求出口的白名单参数快照；不记录正文，不推测服务端思考行为。"""

from collections.abc import Mapping
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RequestParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    max_tokens: int | None = Field(default=None, ge=1, le=10000000)
    max_completion_tokens: int | None = Field(default=None, ge=1, le=10000000)
    top_level_enable_thinking: bool | None = None
    template_enable_thinking: bool | None = None
    thinking_type: Literal["enabled", "disabled"] | None = None
    top_level_thinking_budget: int | None = Field(default=None, ge=1, le=10000000)
    template_thinking_budget: int | None = Field(default=None, ge=1, le=10000000)
    effective_enable_thinking: bool | None = None
    thinking_parameters_conflict: bool = False


class GatewayRequestObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    source: Literal["gateway_prepared_only"] = "gateway_prepared_only"
    parameters: RequestParameters


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _integer(value, *, zero=False):
    return (
        value
        if type(value) is int and (0 if zero else 1) <= value <= 10000000
        else None
    )


def request_parameters(payload):
    """只读实际payload中的参数；没有参数不借用客户端默认值补齐。"""
    payload = _mapping(payload)
    template = _mapping(payload.get("chat_template_kwargs"))
    thinking = _mapping(payload.get("thinking"))
    top = payload.get("enable_thinking")
    nested = template.get("enable_thinking")
    kind = thinking.get("type")
    top = top if type(top) is bool else None
    nested = nested if type(nested) is bool else None
    kind = kind if isinstance(kind, str) and kind in {"enabled", "disabled"} else None
    values = [
        value
        for value in (top, nested, None if kind is None else kind == "enabled")
        if value is not None
    ]
    conflict = len(set(values)) > 1
    return RequestParameters(
        max_tokens=_integer(payload.get("max_tokens")),
        max_completion_tokens=_integer(payload.get("max_completion_tokens")),
        top_level_enable_thinking=top,
        template_enable_thinking=nested,
        thinking_type=kind,
        top_level_thinking_budget=_integer(payload.get("thinking_budget")),
        template_thinking_budget=_integer(template.get("thinking_budget")),
        effective_enable_thinking=values[0] if values and not conflict else None,
        thinking_parameters_conflict=conflict,
    ).model_dump()


def response_observation(result):
    """生成量只使用显式usage字段；不把总输出或文字长度当成推理Token。"""
    result = _mapping(result)
    usage = _mapping(result.get("usage"))
    details = _mapping(usage.get("completion_tokens_details"))
    issues = []

    def metric(name):
        sources = [_integer(owner.get(name), zero=True) for owner in (usage, details)]
        known = [value for value in sources if value is not None]
        if len(set(known)) > 1:
            issues.append(name + "_conflict")
            return None
        return known[0] if known else None

    reasoning, answer = metric("reasoning_tokens"), metric("answer_tokens")
    total = _integer(usage.get("completion_tokens"), zero=True)
    if total is not None and (
        any(value is not None and value > total for value in (reasoning, answer))
        or (reasoning is not None and answer is not None and reasoning + answer > total)
    ):
        reasoning = answer = None
        issues.append("output_breakdown_exceeds_total")
    choices = result.get("choices")
    choice = _mapping(choices[0]) if isinstance(choices, list) and choices else {}
    message = _mapping(choice.get("message"))
    content = message.get("content")
    finish = choice.get("finish_reason")
    return {
        "finish_reason": finish
        if isinstance(finish, str)
        and finish
        in {"stop", "length", "tool_calls", "function_call", "content_filter"}
        else None,
        "reasoning_tokens": reasoning,
        "answer_tokens": answer,
        "reasoning_content_present": bool(message.get("reasoning_content"))
        if message
        else None,
        "think_tags_present": bool(re.search(r"<think>[\s\S]*?</think>", content, re.I))
        if isinstance(content, str)
        else None,
        "issues": issues,
    }


def known_request_purpose(groups):
    return {
        "exam_result_record": "result_verification",
        "exam_finding_analysis": "finding_analysis",
        "exam_reason": "reason_verification",
    }.get(_mapping(groups).get("producer_kind"), "unknown")
