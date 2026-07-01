from __future__ import annotations

import re
from typing import Any

from .luxian_0609_evidence_formatter import format_luxian_0609_evidence
from .luxian_0609_result_schema import apply_luxian_0609_result_schema
from .luxian_0609_trigger_gate import (
    Luxian0609GateDecision,
    TRIGGER_ABSENT,
    TRIGGER_DATA_GAP,
    decision_to_result,
)


_STATUS_PRIORITY = {
    "non_compliant": 50,
    "data_gap": 45,
    "uncertain": 40,
    "compliant": 20,
    "not_applicable": 10,
    "not_executed": 5,
    "technical_error": 60,
}

CANONICAL_RESULT_STATUSES = (
    "non_compliant",
    "compliant",
    "not_applicable",
    "data_gap",
    "uncertain",
    "not_executed",
    "technical_error",
)

_SENSITIVE_KEYS = {
    "raw_response",
    "raw_output",
    "llm_raw_output",
    "prompt",
    "embedding",
    "medical_text",
    "documents",
    "bundle",
    "record_content",
    "internal_data",
}


def _norm_id(value: Any) -> str:
    return str(value or "").strip().upper()


def _confidence(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _status(item: dict[str, Any]) -> str:
    status = str(item.get("status") or "").strip().lower()
    if status in CANONICAL_RESULT_STATUSES:
        return status
    if status in {"technical_error_internal", "error"}:
        return "technical_error"
    if status in {"skipped", "unsupported"}:
        return "not_executed"
    return "compliant" if item.get("is_compliant") is True else "non_compliant"


def _strip_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_sensitive(item)
            for key, item in value.items()
            if str(key).lower() not in _SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_strip_sensitive(item) for item in value]
    return value


def _timeline_from_audit(audit_context: dict[str, Any] | None) -> dict[str, Any]:
    context = dict(audit_context or {})
    timeline = context.get("programmatic_timeline")
    if isinstance(timeline, dict):
        return timeline
    payload = context.get("evidence_payload")
    if isinstance(payload, dict) and isinstance(payload.get("programmatic_timeline"), dict):
        return dict(payload["programmatic_timeline"])
    return {}


def _doc_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(key) or "").strip()
        for key in ("content", "raw_text", "content_preview")
        if str(item.get(key) or "").strip()
    )


def _has_first_course_content(audit_context: dict[str, Any] | None) -> bool:
    timeline = _timeline_from_audit(audit_context)
    docs = timeline.get("documents")
    if not isinstance(docs, dict):
        return True
    first_courses = [item for item in list(docs.get("first_course_record") or []) if isinstance(item, dict)]
    if not first_courses:
        return False
    for item in first_courses:
        text = _doc_text(dict(item))
        normalized = "".join(text.split())
        if normalized and normalized not in {"首次病程记录", "首次病程"} and len(normalized) >= 20:
            return True
    return False


def _guard_copy_rule_without_first_course(
    *,
    wrapper_id: str,
    selected: dict[str, Any],
    audit_context: dict[str, Any] | None,
) -> dict[str, Any]:
    if wrapper_id != "LX0609-016" or _status(selected) != "non_compliant":
        return selected
    if _has_first_course_content(audit_context):
        return selected
    guarded = dict(selected)
    metadata = dict(guarded.get("metadata") or {})
    metadata.update(
        {
            "copy_rule_priority_guard": "first_course_missing",
            "data_gap_reason": "首次病程记录缺失或正文为空，无法进行复制病历比对",
        }
    )
    guarded.update(
        {
            "status": "data_gap",
            "is_compliant": False,
            "findings": "首次病程记录缺失或正文为空，无法判断是否存在复制病历内容。",
            "evidence": "数据缺口：首次病程记录正文为空；复制病历比对未执行。",
            "suggestion": "请先补齐首次病程记录正文，再复核是否与入院记录或其他病程存在复制。",
            "metadata": metadata,
        }
    )
    return guarded


def _has_any(text: str, *needles: str) -> bool:
    return any(needle and needle in text for needle in needles)


_PATHOLOGY_OBJECTIVE_POSITIVE_PATTERN = re.compile(
    r"("
    r"(?:送检|送病理|送病检|标本|取材).{0,60}(?:冰冻病理|术中冰冻|病理提示|病理诊断|病理结果|浸润性腺癌|腺癌|癌转移|恶性)"
    r"|(?:冰冻病理|术中冰冻|病理提示|病理诊断|病理结果|浸润性腺癌|腺癌|癌转移|恶性).{0,60}(?:送检|送病理|送病检|标本|取材)"
    r")"
)
_PATHOLOGY_MATERIAL_ABSENCE_PATTERN = re.compile(
    r"("
    r"(?:未记录|未见|缺失|缺少|不完整|仅笼统|未详细|未明确|无记录).{0,24}(?:取材|标本|送检|送病理|送病检|冰冻|术中病理|淋巴结清扫)"
    r"|(?:取材|标本|送检|送病理|送病检|淋巴结清扫).{0,24}(?:未记录|未见|缺失|缺少|不完整|仅笼统|未详细|未明确|无记录)"
    r")"
)
_PATHOLOGY_OBJECTIVE_NEGATIVE_CONTEXT_PATTERN = re.compile(
    r"缺(?:少)?病理(?:结果|诊断|来源|报告|对照)|未见病理(?:结果|诊断|报告)|病理(?:结果|诊断|报告)?对照不足"
)


def _has_recorded_pathology_material(text: str) -> bool:
    if not text:
        return False
    explicit_positive = _has_any(
        text,
        "已记录术中取材",
        "已记录取材",
        "已记录术中取材及冰冻病理结果",
        "记录了术中冰冻病理结果",
        "记录术中冰冻病理结果",
    )
    objective_positive = bool(_PATHOLOGY_OBJECTIVE_POSITIVE_PATTERN.search(text))
    if objective_positive and _PATHOLOGY_OBJECTIVE_NEGATIVE_CONTEXT_PATTERN.search(text):
        objective_positive = False
    if not explicit_positive and not objective_positive:
        return False
    return not bool(_PATHOLOGY_MATERIAL_ABSENCE_PATTERN.search(text))


def _extract_execution_evidence(text: str) -> str:
    marker = "执行证据："
    index = text.find(marker)
    if index < 0:
        return text.strip()
    return text[index + len(marker):].strip()


def _readable_uncertain_evidence(
    text: str,
    fallback: str = "系统未能提取到可直接支撑判定的结构化证据片段。",
) -> str:
    evidence = _extract_execution_evidence(text)
    if _has_any(evidence, "LLM", "非结构化结果", "原始输出"):
        return fallback
    return evidence or fallback


def _readable_uncertain_findings(wrapper_id: str) -> tuple[str, str, str]:
    if wrapper_id == "LX0609-017":
        return (
            "病程记录重复度未形成可靠自动结论，需人工复核。",
            "系统未能提取到可直接比较的两份以上病程记录结构化片段。",
            "请人工比对两次以上病程记录的主要内容、记录时间和病情变化描述，确认是否存在复制粘贴。",
        )
    return (
        "本质控点未形成可靠自动结论，需人工复核。",
        "系统未能提取到可直接支撑判定的结构化证据片段。",
        "请质控员结合来源文书、记录时间和关键字段进行人工复核。",
    )


def _consultation_execution_missing(text: str) -> bool:
    return _has_any(
        text,
        "未体现具体执行",
        "未记载具体执行",
        "未记录具体执行",
        "未体现会诊意见的具体执行",
        "未记录执行情况",
        "无请会诊执行记录",
        "执行记录缺失",
        "仅描述",
        "照抄会诊意见",
    )


def _consultation_positive_execution(text: str) -> bool:
    return _has_any(
        text,
        "已包含执行情况",
        "已记录执行情况",
        "已体现执行情况",
        "已有执行记录",
        "有执行记录",
        "未违反规则",
        "未违反本规则",
    )


_COPY_TWO_COURSE_RELIABLE_PATTERNS = (
    re.compile(r"(两次|2次|二次|两份|2份|多次|连续).{0,20}(病程记录|查房记录|日常病程)"),
    re.compile(r"(病程记录|查房记录|日常病程).{0,20}(两次|2次|二次|两份|2份|多次|连续)"),
    re.compile(r"(相似度|重复率).{0,12}(?:大于|超过|>|≥)?\s*70%"),
)


def _has_reliable_two_course_copy_evidence(text: str) -> bool:
    if not text.strip():
        return False
    if any(pattern.search(text) for pattern in _COPY_TWO_COURSE_RELIABLE_PATTERNS):
        return True
    date_course_mentions = re.findall(
        r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}.{0,24}(?:病程记录|查房记录|日常病程)",
        text,
    )
    return len(set(date_course_mentions)) >= 2


def _guard_customer_display_result(
    *,
    wrapper_id: str,
    selected: dict[str, Any],
) -> dict[str, Any]:
    status = _status(selected)
    findings = str(selected.get("findings") or "")
    evidence = str(selected.get("evidence") or "")
    suggestion = str(selected.get("suggestion") or "")
    combined_text = f"{findings}\n{evidence}\n{suggestion}"

    if wrapper_id == "LX0609-003" and status == "non_compliant":
        if _has_any(combined_text, "未超过24小时", "未超24小时", "符合质控规则要求", "符合规则要求"):
            guarded = dict(selected)
            has_missing_cross_check = _has_any(combined_text, "缺少麻醉记录", "无法通过", "无法交叉验证", "证据不足")
            guarded.update(
                {
                    "status": "data_gap" if has_missing_cross_check else "compliant",
                    "is_compliant": False if has_missing_cross_check else True,
                    "findings": (
                        "手术记录时间未超过术后24小时，但缺少麻醉记录等交叉核对字段，暂不能作为缺陷展示。"
                        if has_missing_cross_check
                        else "手术记录完成时间未超过术后24小时，本质控点未形成缺陷。"
                    ),
                    "evidence": _extract_execution_evidence(evidence) or findings,
                    "suggestion": (
                        "请补齐麻醉记录或手术结束时间等交叉核对字段后复核。"
                        if has_missing_cross_check
                        else "当前无需按超时缺陷处理。"
                    ),
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "lx0609_003_positive_time_result"
            guarded["metadata"] = metadata
            return guarded

    if wrapper_id in {"LX0609-019", "LX0609-024"} and status == "non_compliant":
        if _has_recorded_pathology_material(combined_text):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "compliant",
                    "is_compliant": True,
                    "findings": "手术记录已记录术中取材及冰冻/病理相关结果，本质控点未形成缺陷。",
                    "evidence": _extract_execution_evidence(evidence) or findings,
                    "suggestion": "当前无需按取材或病理记录缺陷处理；如需确认手术范围调整，请按对应规则人工复核。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "pathology_specimen_positive_recorded"
            guarded["metadata"] = metadata
            return guarded

    if wrapper_id in {"LX0609-020", "LX0609-023"} and status == "non_compliant":
        if _consultation_positive_execution(combined_text):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "compliant",
                    "is_compliant": True,
                    "findings": "会诊意见执行情况已有记录，本质控点未形成缺陷。",
                    "evidence": _extract_execution_evidence(evidence) or findings,
                    "suggestion": "当前无需按会诊执行情况缺陷处理；如需核对签名或申请单项目，请按对应质控点人工复核。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "consultation_execution_positive_recorded"
            guarded["metadata"] = metadata
            return guarded
        if "签名" in combined_text and not _consultation_execution_missing(combined_text):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "uncertain",
                    "is_compliant": False,
                    "findings": "当前证据主要指向签名或申请记录问题，未能确认会诊意见执行情况缺陷。",
                    "evidence": _extract_execution_evidence(evidence) or findings,
                    "suggestion": "请人工区分签名缺项、会诊申请缺项和会诊意见执行情况缺陷，避免串用质控点。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "consultation_signature_only_not_execution_defect"
            guarded["metadata"] = metadata
            return guarded

    if wrapper_id == "LX0609-017" and status == "non_compliant":
        if not _has_reliable_two_course_copy_evidence(combined_text):
            readable_findings, readable_evidence, readable_suggestion = _readable_uncertain_findings(wrapper_id)
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "uncertain",
                    "is_compliant": False,
                    "findings": readable_findings,
                    "evidence": _readable_uncertain_evidence(evidence, readable_evidence),
                    "suggestion": readable_suggestion,
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "copy_rule_requires_two_course_records"
            guarded["metadata"] = metadata
            return guarded

    if status == "uncertain" and _has_any(combined_text, "LLM", "非结构化结果", "原始输出"):
        readable_findings, readable_evidence, readable_suggestion = _readable_uncertain_findings(wrapper_id)
        guarded = dict(selected)
        guarded.update(
            {
                "status": "uncertain",
                "is_compliant": False,
                "findings": readable_findings,
                "evidence": _readable_uncertain_evidence(evidence, readable_evidence),
                "suggestion": readable_suggestion,
            }
        )
        metadata = dict(guarded.get("metadata") or {})
        metadata["customer_display_guard"] = "customer_readable_uncertain"
        guarded["metadata"] = metadata
        return guarded

    return selected


def _select_best_result(
    *,
    mapped_results: list[dict[str, Any]],
    primary_rule_id: str,
) -> tuple[dict[str, Any] | None, str]:
    if not mapped_results:
        return None, "missing_mapped_result"

    primary = [item for item in mapped_results if _norm_id(item.get("rule_id") or item.get("rule_code")) == primary_rule_id]
    for target_status, source in (
        ("technical_error", "mapped_technical_error"),
        ("non_compliant", "mapped_non_compliant"),
        ("data_gap", "mapped_data_gap"),
        ("uncertain", "mapped_uncertain"),
        ("not_executed", "mapped_not_executed"),
    ):
        candidates = [item for item in mapped_results if _status(item) == target_status]
        if candidates:
            candidates.sort(key=lambda item: (_confidence(item.get("confidence")), _norm_id(item.get("rule_id"))), reverse=True)
            primary_match = [item for item in primary if _status(item) == target_status]
            if primary_match:
                return primary_match[0], f"primary_{target_status}"
            return candidates[0], source

    if primary:
        return primary[0], "primary_result"
    return mapped_results[0], "first_mapped_result"


def _copy_customer_fields(
    *,
    wrapper: dict[str, Any],
    selected: dict[str, Any],
    mapped_results: list[dict[str, Any]],
    source: str,
    gate_decision: Luxian0609GateDecision | None,
) -> dict[str, Any]:
    wrapper_id = _norm_id(wrapper.get("rule_id") or wrapper.get("rule_code"))
    primary_rule_id = _norm_id(wrapper.get("primary_execution_rule_id"))
    mapped_rule_ids = [_norm_id(item) for item in list(wrapper.get("mapped_rule_ids") or []) if _norm_id(item)]
    status = _status(selected)
    if status not in {"compliant", "non_compliant", "not_applicable", "data_gap", "uncertain"}:
        status = "uncertain"
    metadata = _strip_sensitive(dict(selected.get("metadata") or {}))
    if gate_decision is not None:
        metadata.update(gate_decision.to_metadata())
    metadata.update(
        {
            "mapped_rule_ids": mapped_rule_ids,
            "primary_execution_rule_id": primary_rule_id,
            "aggregation_source": source,
            "selected_execution_rule_id": _norm_id(selected.get("rule_id") or selected.get("rule_code")),
            "mapped_result_count": len(mapped_results),
            "customer_rule_id": wrapper_id,
        }
    )
    result = {
        **_strip_sensitive(selected),
        "rule_id": wrapper_id,
        "rule_code": wrapper_id,
        "rule_name": str(wrapper.get("name") or wrapper.get("rule_name") or selected.get("rule_name") or wrapper_id),
        "status": status,
        "is_compliant": status in {"compliant", "not_applicable"},
        "metadata": metadata,
    }
    return result


def aggregate_luxian_0609_results(
    *,
    wrapper_rules: list[dict[str, Any]],
    execution_results: list[dict[str, Any]],
    gate_decisions: dict[str, Luxian0609GateDecision] | None = None,
    format_evidence: bool = True,
    audit_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    result_by_rule: dict[str, list[dict[str, Any]]] = {}
    for item in execution_results:
        key = _norm_id(item.get("rule_id") or item.get("rule_code"))
        if key:
            result_by_rule.setdefault(key, []).append(dict(item))

    customer_results: list[dict[str, Any]] = []
    decisions = gate_decisions or {}
    for wrapper in wrapper_rules:
        wrapper_id = _norm_id(wrapper.get("rule_id") or wrapper.get("rule_code"))
        if not wrapper_id:
            continue
        decision = decisions.get(wrapper_id)
        gate_result = None
        if decision and (
            decision.status == TRIGGER_ABSENT
            or (wrapper_id == "LX0609-016" and decision.status == TRIGGER_DATA_GAP)
        ):
            gate_result = decision_to_result(wrapper, decision)
            if gate_result is not None:
                result = _copy_customer_fields(
                    wrapper=wrapper,
                    selected=gate_result,
                    mapped_results=[],
                    source="trigger_gate",
                    gate_decision=decision,
                )
                if format_evidence:
                    result = format_luxian_0609_evidence(
                        result=result,
                        wrapper_rule=wrapper,
                        gate_decision=decision,
                    )
                result = apply_luxian_0609_result_schema(
                    result=result,
                    wrapper_rule=wrapper,
                    gate_decision=decision,
                    audit_context=audit_context,
                )
                customer_results.append(result)
                continue

        direct_results = list(result_by_rule.get(wrapper_id) or [])
        if direct_results:
            direct_results.sort(
                key=lambda item: (_confidence(item.get("confidence")), _norm_id(item.get("rule_id"))),
                reverse=True,
            )
            selected = direct_results[0]
            selected = _guard_copy_rule_without_first_course(
                wrapper_id=wrapper_id,
                selected=selected,
                audit_context=audit_context,
            )
            selected = _guard_customer_display_result(
                wrapper_id=wrapper_id,
                selected=selected,
            )
            source = "customer_programmatic"
            result = _copy_customer_fields(
                wrapper=wrapper,
                selected=selected,
                mapped_results=direct_results,
                source=source,
                gate_decision=decision,
            )
            if format_evidence:
                result = format_luxian_0609_evidence(
                    result=result,
                    wrapper_rule=wrapper,
                    gate_decision=decision,
                )
            result = apply_luxian_0609_result_schema(
                result=result,
                wrapper_rule=wrapper,
                gate_decision=decision,
                audit_context=audit_context,
            )
            customer_results.append(result)
            continue
        if decision and decision.status in {TRIGGER_ABSENT, TRIGGER_DATA_GAP}:
            gate_result = decision_to_result(wrapper, decision)
        if gate_result is not None:
            source = "trigger_gate"
            mapped_results: list[dict[str, Any]] = []
            result = _copy_customer_fields(
                wrapper=wrapper,
                selected=gate_result,
                mapped_results=mapped_results,
                source=source,
                gate_decision=decision,
            )
        else:
            mapped_rule_ids = [_norm_id(item) for item in list(wrapper.get("mapped_rule_ids") or []) if _norm_id(item)]
            mapped_results = []
            for rule_id in mapped_rule_ids:
                mapped_results.extend(result_by_rule.get(rule_id) or [])
            selected, source = _select_best_result(
                mapped_results=mapped_results,
                primary_rule_id=_norm_id(wrapper.get("primary_execution_rule_id")),
            )
            if selected is None:
                selected = {
                    "rule_id": wrapper_id,
                    "rule_name": str(wrapper.get("name") or wrapper_id),
                    "status": "uncertain",
                    "is_compliant": False,
                    "findings": "该质控点未返回底层执行结果，需人工复核。",
                    "evidence": "",
                    "suggestion": "请检查映射规则执行状态或重新运行质控。",
                    "confidence": 0.0,
                    "metadata": {"technical_error_internal": True},
                }
            else:
                selected = _guard_copy_rule_without_first_course(
                    wrapper_id=wrapper_id,
                    selected=selected,
                    audit_context=audit_context,
                )
                selected = _guard_customer_display_result(
                    wrapper_id=wrapper_id,
                    selected=selected,
                )
            result = _copy_customer_fields(
                wrapper=wrapper,
                selected=selected,
                mapped_results=mapped_results,
                source=source,
                gate_decision=decision,
            )

        if format_evidence:
            result = format_luxian_0609_evidence(
                result=result,
                wrapper_rule=wrapper,
                gate_decision=decision,
            )
        result = apply_luxian_0609_result_schema(
            result=result,
            wrapper_rule=wrapper,
            gate_decision=decision,
            audit_context=audit_context,
        )
        customer_results.append(result)
    return customer_results


def summarize_luxian_0609_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {status: 0 for status in CANONICAL_RESULT_STATUSES}
    for item in results:
        status = _status(item)
        status_counts[status] = int(status_counts.get(status) or 0) + 1
    total = len(results)
    not_applicable = int(status_counts.get("not_applicable") or 0)
    data_gap = int(status_counts.get("data_gap") or 0)
    not_executed = int(status_counts.get("not_executed") or 0)
    technical_error = int(status_counts.get("technical_error") or 0)
    compliance_denominator = max(0, total - not_applicable - data_gap - not_executed - technical_error)
    compliant = int(status_counts.get("compliant") or 0)
    compliance_rate = round((compliant / compliance_denominator * 100.0), 2) if compliance_denominator else 100.0
    return {
        "customer_rule_count": total,
        "status_counts": status_counts,
        "defect_count": int(status_counts.get("non_compliant") or 0),
        "not_applicable_count": not_applicable,
        "data_gap_count": data_gap,
        "uncertain_count": int(status_counts.get("uncertain") or 0),
        "not_executed_count": not_executed,
        "technical_error_count": technical_error,
        "compliant_count": compliant,
        "compliance_denominator": compliance_denominator,
        "compliance_rate": compliance_rate,
    }
