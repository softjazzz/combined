from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol

from .luxian_0609_trigger_gate import (
    TRIGGER_ABSENT,
    TRIGGER_DATA_GAP,
    TRIGGER_PRESENT,
    TRIGGER_UNKNOWN,
    Luxian0609GateDecision,
    evaluate_luxian_0609_trigger_gates,
)

logger = logging.getLogger(__name__)

_SUPPORTED_LLM_GATE_RULE_IDS = {"LX0609-04-02-03"}
_VALID_LLM_GATE_STATUSES = {TRIGGER_PRESENT, TRIGGER_ABSENT, TRIGGER_DATA_GAP, TRIGGER_UNKNOWN}
_MAX_GATE_CONTEXT_CHARS = 7000

_LX0609_024_LLM_GATE_CANDIDATE_PATTERNS = (
    re.compile(r"(手术记录|手术名称|术中所见|手术经过|术前诊断|术后诊断|手术医嘱)"),
    re.compile(r"(肿物|肿瘤|恶性|癌|腺癌|鳞癌|病理|病检|送检|送病理|送病检|标本|活检|冰冻|淋巴结)"),
)


class LLMGateClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]:
        ...


def _norm_rule_id(rule: dict[str, Any]) -> str:
    return str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()


def _record_payload_text(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        return str(payload)


def _combined_record_text(medical_text: str, evidence_payload: dict[str, Any] | None) -> str:
    text = "\n".join(part for part in (str(medical_text or ""), _record_payload_text(evidence_payload)) if part)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) <= _MAX_GATE_CONTEXT_CHARS:
        return text
    return text[:_MAX_GATE_CONTEXT_CHARS] + "\n...[已截断，仅用于适用性门控判断]"


def _should_call_lx0609_024_llm_gate(
    *,
    decision: Luxian0609GateDecision | None,
    record_text: str,
) -> bool:
    if decision and decision.status in {TRIGGER_PRESENT, TRIGGER_DATA_GAP}:
        return False
    return all(pattern.search(record_text) for pattern in _LX0609_024_LLM_GATE_CANDIDATE_PATTERNS)


def _extract_llm_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            return str(message.get("content") or "")
    return str(response.get("content") or response.get("text") or "")


def _parse_llm_gate_json(text: str) -> dict[str, Any] | None:
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _as_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, confidence))


def _as_text_tuple(value: Any, *, limit: int = 6) -> tuple[str, ...]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = [str(item) for item in value]
    else:
        items = []
    normalized: list[str] = []
    for item in items:
        text = re.sub(r"\s+", " ", str(item or "")).strip()
        if text:
            normalized.append(text[:160])
    return tuple(dict.fromkeys(normalized))[:limit]


def _build_lx0609_024_prompt(record_text: str) -> str:
    return f"""你是病历质控的“适用性门控”助手，只判断 LX0609-04-02-03 是否适用于本次病历。

LX0609-04-02-03 只适用于“本次住院/本次手术是恶性肿瘤相关手术，或本次手术涉及恶性肿瘤病灶、恶性肿瘤标本、淋巴结清扫/送检/冰冻病理”的场景。

请严格区分：
1. 本次手术是恶性肿瘤手术：status=present。
2. 只是既往史、无关诊断、术前排查、普通炎症/良性手术、普通阑尾/胆囊/泌尿手术，没有本次恶性肿瘤手术证据：status=absent。
3. 文书提到肿瘤/病理/送检，但无法判断是否本次恶性肿瘤手术：status=unknown。
4. 明确需要结构化字段但缺失才能判断时：status=data_gap，并列出 missing_fields。

你只输出 JSON，不要输出解释性散文：
{{
  "status": "present|absent|data_gap|unknown",
  "confidence": 0.0,
  "reason": "一句客户可读的适用性理由",
  "matched_evidence": ["最多3条原文短片段"],
  "missing_fields": ["缺失字段"]
}}

病历证据：
{record_text}
"""


def _decision_from_lx0609_024_llm_payload(
    *,
    original: Luxian0609GateDecision | None,
    payload: dict[str, Any],
) -> Luxian0609GateDecision | None:
    raw_status = str(payload.get("status") or "").strip().lower()
    status = raw_status if raw_status in _VALID_LLM_GATE_STATUSES else TRIGGER_UNKNOWN
    confidence = _as_confidence(payload.get("confidence"))
    reason = re.sub(r"\s+", " ", str(payload.get("reason") or "").strip())[:240]
    if not reason:
        reason = "LLM gate 未返回明确理由"
    evidence = _as_text_tuple(payload.get("matched_evidence"), limit=3)
    missing_fields = _as_text_tuple(payload.get("missing_fields"), limit=4)

    if status in {TRIGGER_PRESENT, TRIGGER_ABSENT} and confidence < 0.6:
        status = TRIGGER_UNKNOWN
    if status == TRIGGER_DATA_GAP and confidence < 0.55:
        status = TRIGGER_UNKNOWN

    if status == TRIGGER_UNKNOWN:
        if original and original.status != TRIGGER_ABSENT:
            return original
        return Luxian0609GateDecision(
            rule_id="LX0609-04-02-03",
            status=TRIGGER_UNKNOWN,
            reason=f"恶性肿瘤手术适用性未形成可靠自动结论：{reason}",
            matched_keywords=evidence,
            source="llm_gate",
            extra={
                "llm_gate_rule_id": "LX0609-04-02-03",
                "llm_gate_status": status,
                "llm_gate_confidence": confidence,
                "llm_gate_reason": reason,
                "llm_gate_original_status": original.status if original else "",
            },
        )

    if status == TRIGGER_PRESENT:
        final_reason = reason if reason else "模型门控识别到本次恶性肿瘤相关手术适用场景"
    elif status == TRIGGER_ABSENT:
        final_reason = reason if reason else "模型门控未识别到本次恶性肿瘤相关手术适用场景"
    else:
        final_reason = reason if reason else "模型门控认为缺少适用性判定字段"

    return Luxian0609GateDecision(
        rule_id="LX0609-04-02-03",
        status=status,
        reason=final_reason,
        data_gap_fields=missing_fields if status == TRIGGER_DATA_GAP else (),
        matched_keywords=evidence,
        source="llm_gate",
        extra={
            "llm_gate_rule_id": "LX0609-04-02-03",
            "llm_gate_status": status,
            "llm_gate_confidence": confidence,
            "llm_gate_reason": reason,
            "llm_gate_evidence": list(evidence),
            "llm_gate_missing_fields": list(missing_fields),
            "llm_gate_original_status": original.status if original else "",
        },
    )


async def evaluate_luxian_0609_trigger_gates_with_llm(
    *,
    rules: list[dict[str, Any]],
    visit_id: str = "",
    medical_text: str = "",
    evidence_payload: dict[str, Any] | None = None,
    llm_client: LLMGateClient | None = None,
    enabled: bool = True,
) -> dict[str, Luxian0609GateDecision]:
    """Run deterministic gates first, then ask LLM only for supported grey-zone gates.

    The LLM gate is an applicability layer. It must not create a defect result by
    itself; it only changes whether a customer rule should enter normal execution,
    be skipped as not applicable, or be marked as data gap.
    """

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        visit_id=visit_id,
        medical_text=medical_text,
        evidence_payload=evidence_payload,
    )
    if not enabled or llm_client is None:
        return decisions

    record_text = _combined_record_text(medical_text, evidence_payload)
    for rule in rules:
        rule_id = _norm_rule_id(rule)
        if rule_id not in _SUPPORTED_LLM_GATE_RULE_IDS:
            continue
        original = decisions.get(rule_id)
        if rule_id == "LX0609-04-02-03" and not _should_call_lx0609_024_llm_gate(
            decision=original,
            record_text=record_text,
        ):
            continue
        try:
            response = await llm_client.generate(_build_lx0609_024_prompt(record_text))
            parsed = _parse_llm_gate_json(_extract_llm_text(response))
            if not parsed:
                logger.warning("LX0609 LLM gate returned non-json payload: visit_id=%s rule_id=%s", visit_id, rule_id)
                continue
            decision = _decision_from_lx0609_024_llm_payload(original=original, payload=parsed)
            if decision is not None:
                decisions[rule_id] = decision
        except Exception as exc:
            logger.warning("LX0609 LLM gate failed: visit_id=%s rule_id=%s error=%s", visit_id, rule_id, exc)
            continue
    return decisions
