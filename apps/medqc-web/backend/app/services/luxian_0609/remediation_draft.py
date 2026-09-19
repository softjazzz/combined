"""LX0609 客户整改草稿的按需生成。

与 ``customer_remediation`` 的受控模板不同：本模块只在结果页被主动请求时
调用一次模型，把「客户已经能看到的缺陷事实」改写成针对本例的整改草稿。

硬边界：

- 不参与判定、不写入数据库、不改写权威的 ``suggestion``；
- 模型输入只取结果 DTO 中已经展示给客户的字段（结论、受控事实、证据定位、
  现有整改要点），不额外读取病历正文；
- 生成失败只降级为「无可生成草稿」，不得影响已保存的质控结论。
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

logger = logging.getLogger(__name__)

# 只在这三个已经产出逐条会诊痕迹或会诊语义状态的规则上试点。
REMEDIATION_DRAFT_RULE_IDS = frozenset({"LX0609-020", "LX0609-022", "LX0609-023"})

_SUPPORTED_STATUS = "non_compliant"
_MAX_CONCLUSION_CHARS = 400
_MAX_SUGGESTION_CHARS = 800
_MAX_FACTS_CHARS = 1200
_MAX_EVIDENCE_ITEMS = 8
_MAX_EXCERPT_CHARS = 200
_MAX_DRAFT_CHARS = 300
_MAX_COMPLETION_TOKENS = 1024

# 结果 DTO 中以证据引用形式出现的事实键，只保留可读定位，避免把 ref 噪声送进模型。
_REFERENCE_KEYS = ("opinion_evidence", "execution_evidence")

_REASON_RULE_NOT_SUPPORTED = "rule_not_supported"
_REASON_STATUS_NOT_SUPPORTED = "status_not_supported"
_REASON_EMPTY_DRAFT = "empty_draft"
_REASON_GENERATION_FAILED = "generation_failed"

GenerateCallable = Callable[[str], Awaitable[Mapping[str, Any]]]


def _compact_text(value: Any, *, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _compact_reference_entries(value: Any) -> list[str]:
    """把证据引用压缩成可读定位，只保留序号与证据角色。"""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    entries: list[str] = []
    for entry in value:
        if not isinstance(entry, Mapping):
            continue
        index = entry.get("recommendation_index")
        if type(index) is not int or index <= 0 or index > 100:
            continue
        roles = [
            label
            for key, label in (("opinion_evidence", "有会诊意见证据"), ("execution_evidence", "有执行证据"))
            if isinstance(entry.get(key), Sequence) and not isinstance(entry.get(key), (str, bytes)) and entry.get(key)
        ]
        if roles:
            entries.append(f"第{index}条建议：{'、'.join(roles)}")
    return entries


def _project_facts(raw: Any) -> list[str]:
    """把客户可见事实投影为「键：值」行；只做压缩，不做解释。"""

    if not isinstance(raw, Mapping):
        return []
    lines: list[str] = []
    for key in sorted(raw):
        value = raw.get(key)
        if key == "recommendation_evidence":
            entries = _compact_reference_entries(value)
            if entries:
                lines.append(f"{key}：{'；'.join(entries)}")
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            text = _compact_text(value, limit=120)
            if text:
                lines.append(f"{key}：{text}")
            continue
        try:
            text = _compact_text(json.dumps(value, ensure_ascii=False, default=str), limit=240)
        except Exception:
            continue
        if text:
            lines.append(f"{key}：{text}")
    joined = "\n".join(lines)
    if len(joined) <= _MAX_FACTS_CHARS:
        return [joined] if joined else []
    return [joined[:_MAX_FACTS_CHARS] + "\n…（事实已截断）"]


def _project_evidence(raw: Any) -> list[str]:
    """只使用结果页已经展示的证据定位与受控摘录。"""

    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    lines: list[str] = []
    for entry in raw[:_MAX_EVIDENCE_ITEMS]:
        if not isinstance(entry, Mapping):
            continue
        parts: list[str] = []
        index = entry.get("recommendation_index")
        if type(index) is int and index > 0:
            role = "会诊意见" if entry.get("evidence_role") == "opinion" else "执行证据"
            parts.append(f"第{index}条建议 · {role}")
        label = _compact_text(entry.get("source_label"), limit=40)
        if label:
            parts.append(label)
        record_time = _compact_text(entry.get("record_time"), limit=32)
        if record_time:
            parts.append(record_time)
        excerpt = _compact_text(entry.get("evidence_excerpt"), limit=_MAX_EXCERPT_CHARS)
        if excerpt:
            parts.append(f"摘录：{excerpt}")
        if parts:
            lines.append("- " + " · ".join(parts))
    return lines


def build_remediation_draft_prompt(*, item: Mapping[str, Any]) -> str:
    """构造只含客户可见事实的整改草稿提示词。"""

    rule_id = _compact_text(item.get("rule_id"), limit=32)
    rule_name = _compact_text(item.get("rule_name"), limit=80)
    qc_point = _compact_text(item.get("qc_point"), limit=400)
    conclusion = _compact_text(item.get("conclusion"), limit=_MAX_CONCLUSION_CHARS)
    suggestion = _compact_text(item.get("suggestion"), limit=_MAX_SUGGESTION_CHARS)
    fact_lines = _project_facts(item.get("customer_display_facts"))
    evidence_lines = _project_evidence(item.get("evidence"))

    facts_block = "\n".join(fact_lines) if fact_lines else "（未提供额外字段级事实）"
    evidence_block = "\n".join(evidence_lines) if evidence_lines else "（无可定位证据）"
    return f"""你是病案质控整改助手。系统已经完成质控判定，你的唯一任务是把下面「已确认事实」改写成一段针对本例、医生确认后可直接粘贴的整改草稿。

必须遵守：
1. 只能使用「已确认事实」「证据定位」「系统现有整改要点」中出现的信息。不得补充未给出的诊断、症状、体征、检验结果、用药、处置、时间、人员或科室。
2. 不得使用“已经”“已执行”“已完成”“已记录”等完成后口吻；草稿是医生将要补充的记录，统一使用“拟/建议/需补充/应记录”。
3. 事实中没有、只能由医生填写的具体内容，用「＿＿」占位，禁止猜测填写。
4. 只写 1 至 3 句，总长不超过 200 字，使用规范的医疗文书语气。
5. 只输出草稿正文：不要标题、不要编号、不要 Markdown、不要引号、不要任何解释。

【质控点】{rule_id} {rule_name}
【规则要求】{qc_point or "（未提供）"}
【系统判定】不合规：{conclusion or "（未提供）"}
【系统现有整改要点】
{suggestion or "（未提供）"}
【已确认事实】
{facts_block}
【证据定位】
{evidence_block}
"""


def sanitize_remediation_draft(text: Any) -> str:
    """清理模型输出，只保留可展示的草稿正文。"""

    draft = str(text or "")
    draft = re.sub(r"<think>[\s\S]*?</think>", "", draft, flags=re.IGNORECASE)
    draft = re.sub(r"```[a-zA-Z]*", "", draft)
    draft = draft.replace("```", "").strip()
    draft = re.sub(r"^(草稿|整改草稿|整改建议)\s*[：:]\s*", "", draft)
    draft = re.sub(r"\n{3,}", "\n\n", draft).strip()
    draft = draft.strip("\"'“”‘’")
    return draft.strip()


def _extract_llm_text(response: Mapping[str, Any] | None) -> str:
    if not isinstance(response, Mapping):
        return ""
    choices = response.get("choices")
    if isinstance(choices, Sequence) and choices:
        first = choices[0]
        if isinstance(first, Mapping):
            message = first.get("message")
            if isinstance(message, Mapping):
                return str(message.get("content") or "")
    return str(response.get("content") or response.get("text") or "")


async def generate_remediation_draft(
    *,
    item: Mapping[str, Any],
    generate: GenerateCallable | None = None,
) -> dict[str, Any]:
    """按需生成一份整改草稿；任何失败都降级为不可生成，不抛给调用方。"""

    rule_id = str(item.get("rule_id") or "").strip().upper()
    status = str(item.get("status") or "").strip().lower()
    if rule_id not in REMEDIATION_DRAFT_RULE_IDS:
        return {"available": False, "rule_id": rule_id, "reason": _REASON_RULE_NOT_SUPPORTED}
    if status != _SUPPORTED_STATUS:
        return {"available": False, "rule_id": rule_id, "reason": _REASON_STATUS_NOT_SUPPORTED}

    caller = generate
    if caller is None:
        from ..qc_llm_client import SichuanQCLLMClient

        client = SichuanQCLLMClient()

        async def caller(prompt: str) -> Mapping[str, Any]:  # type: ignore[misc]
            return await client.generate(
                prompt,
                max_completion_tokens=_MAX_COMPLETION_TOKENS,
                enable_thinking=False,
            )

    prompt = build_remediation_draft_prompt(item=item)
    try:
        response = await caller(prompt)
    except Exception:
        logger.warning("LX0609 整改草稿生成失败 rule_id=%s", rule_id, exc_info=True)
        return {"available": False, "rule_id": rule_id, "reason": _REASON_GENERATION_FAILED}

    draft = sanitize_remediation_draft(_extract_llm_text(response))
    if not draft:
        return {"available": False, "rule_id": rule_id, "reason": _REASON_EMPTY_DRAFT}
    if len(draft) > _MAX_DRAFT_CHARS:
        draft = draft[:_MAX_DRAFT_CHARS].rstrip() + "…"
    return {"available": True, "rule_id": rule_id, "draft": draft}
