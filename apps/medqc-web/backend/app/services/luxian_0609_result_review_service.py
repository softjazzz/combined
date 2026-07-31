from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .custom_qc_workspace_service import (
    _canonical_customer_status,
    customer_safe_projection_key,
    iter_unique_customer_result_source_items,
    project_customer_safe_result_item,
)

SCOPE_LUXIAN_0609 = "luxian_0609_qc_v1"

SENSITIVE_KEYS = {
    "prompt",
    "raw_response",
    "embedding",
    "medical_text",
    "record_content",
    "documents",
    "bundle",
    "llm_raw_output",
}

INTERNAL_TERM_PATTERN = re.compile(
    r"(LLM|raw_response|llm_raw_output|embedding|证据模板|映射执行规则|"
    r"\bevidence\b|\braw\b|\bbundle\b|\bprompt\b)",
    re.IGNORECASE,
)

POSITIVE_CONCLUSION_PATTERN = re.compile(r"(符合|未超过|已记录|已完成|未违反|无明显违规|无需整改)")
NEGATIVE_CONCLUSION_PATTERN = re.compile(r"(缺失|未见|超时|不完整|未完成|无记录|未记录)")

CONSULTATION_RULES = {"LX0609-020", "LX0609-023"}
TRANSFUSION_RULES = {"LX0609-041", "LX0609-044", "LX0609-048", "LX0609-049"}
CHEMO_RULES = {"LX0609-026"}
LEVEL4_SURGERY_RULES = {"LX0609-040"}


def review_luxian_0609_batch_job(
    job: dict[str, Any],
    *,
    llm_verifier: Optional[Callable[[list[dict[str, Any]]], list[dict[str, Any]]]] = None,
) -> dict[str, Any]:
    if not _is_luxian_0609_job(job):
        return {
            "review_status": "skipped",
            "scope": "unsupported",
            "reviewed_at": _now_iso(),
            "summary": {"total_findings": 0, "p0": 0, "p1": 0, "p2": 0},
            "findings": [],
            "llm_review_status": "skipped",
        }

    findings = _run_rule_verifier(job)
    llm_status = "skipped"
    if llm_verifier and findings:
        payloads = [_build_llm_payload(finding) for finding in findings]
        try:
            llm_results = llm_verifier(payloads)
            _merge_llm_results(findings, llm_results)
            llm_status = "completed"
        except Exception:  # pragma: no cover - defensive boundary
            llm_status = "failed"
            for finding in findings:
                finding.setdefault("llm_error_code", "review_provider_failed")

    return _build_report(findings, llm_status=llm_status)


def _is_luxian_0609_job(job: dict[str, Any]) -> bool:
    filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
    summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
    candidates = [
        filters.get("rule_set_id"),
        filters.get("rule_set"),
        filters.get("rule_set_key"),
        summary.get("rule_set_id"),
        summary.get("rule_set_key"),
        job.get("rule_set_id"),
        job.get("rule_set_key"),
        job.get("rule_code"),
        job.get("rule_name"),
    ]
    return any(SCOPE_LUXIAN_0609 in str(value or "") for value in candidates)


def _run_rule_verifier(job: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for item in _iter_result_items(job):
        findings.extend(_review_item(item))
    return findings


def _iter_result_items(job: dict[str, Any]) -> list[dict[str, Any]]:
    return iter_unique_customer_result_source_items(
        job,
        hmac_key=customer_safe_projection_key(),
    )


def _review_item(item: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    rule_id = _rule_id(item)
    status = _status(item)
    combined = _combined_text(item)

    if rule_id in CONSULTATION_RULES and status in {"non_compliant", "data_gap", "uncertain"}:
        if not _has_consultation_strong_fact(item):
            findings.append(
                _finding(
                    item,
                    severity="P1",
                    risk_type="applicability_gate",
                    suggested_status="not_applicable",
                    reason="未发现会诊申请单、会诊记录单或会诊意见等强触发事实。",
                    customer_message="当前病历未见会诊文书证据，本项不宜作为会诊执行问题展示。",
                )
            )

    if rule_id in TRANSFUSION_RULES and status in {"non_compliant", "data_gap", "uncertain"}:
        if not _has_transfusion_strong_fact(item):
            findings.append(
                _finding(
                    item,
                    severity="P1",
                    risk_type="applicability_gate",
                    suggested_status="not_applicable",
                    reason="未发现输血医嘱、输血申请、输血记录或收费血制品等强触发事实。",
                    customer_message="当前证据不足以证明发生输血事件，应展示为不适用或质控员确认，而不是正式缺陷。",
                )
            )

    if rule_id in CHEMO_RULES and status in {"non_compliant", "data_gap", "uncertain"}:
        if not _has_chemo_strong_fact(item):
            findings.append(
                _finding(
                    item,
                    severity="P1",
                    risk_type="applicability_gate",
                    suggested_status="not_applicable",
                    reason="未发现化疗医嘱、化疗记录或具体化疗药物证据。",
                    customer_message="仅有恶性肿瘤诊断不足以触发化疗记录一致性质控点。",
                )
            )

    if rule_id in LEVEL4_SURGERY_RULES and status in {"non_compliant", "data_gap", "uncertain"}:
        if not _has_level_4_surgery_fact(item):
            findings.append(
                _finding(
                    item,
                    severity="P1",
                    risk_type="applicability_gate",
                    suggested_status="not_applicable",
                    reason="未发现四级手术或明确高风险手术分级证据。",
                    customer_message="未证明为四级手术前，不宜判定 MDT 讨论缺失。",
                )
            )

    contradiction = _status_contradiction(status, combined)
    if contradiction:
        findings.append(
            _finding(
                item,
                severity="P0",
                risk_type="status_contradiction",
                suggested_status=contradiction["suggested_status"],
                reason=contradiction["reason"],
                customer_message="质控状态与结论文字存在矛盾，建议结合原文确认后再展示给客户。",
            )
        )

    if status == "data_gap" and _has_defect_badge(item):
        findings.append(
            _finding(
                item,
                severity="P1",
                risk_type="data_gap_display",
                suggested_status="data_gap",
                reason="数据不足结果仍带有正式缺陷等级标签。",
                customer_message="该项应明确展示为数据不足，需结合原文确认，不应呈现为正式缺陷。",
            )
        )

    if INTERNAL_TERM_PATTERN.search(combined):
        findings.append(
            _finding(
                item,
                severity="P2",
                risk_type="presentation",
                suggested_status=status,
                reason="结果证据包含内部技术话术。",
                customer_message="建议隐藏内部术语，改用来源文书、缺失字段和处理建议说明。",
            )
        )

    if _has_weak_evidence(item):
        findings.append(
            _finding(
                item,
                severity="P2",
                risk_type="evidence_quality",
                suggested_status=status,
                reason="证据片段过短或缺少来源文书。",
                customer_message="建议补充来源文书、字段、原文片段、时间或阈值信息。",
            )
        )

    return findings


def _rule_id(item: dict[str, Any]) -> str:
    return str(item.get("rule_id") or item.get("rule_code") or item.get("customer_rule_id") or "").strip()


def _status(item: dict[str, Any]) -> str:
    """内部复核读取原始规范状态，不受客户展示降级影响。"""
    return _canonical_customer_status(item)


def _combined_text(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "findings",
        "conclusion",
        "summary",
        "evidence",
        "evidence_text",
        "evidence_summary",
        "suggestion",
        "recommendation",
    ):
        value = item.get(key)
        if value:
            parts.append(str(value))
    for evidence in item.get("evidence_items") or []:
        if isinstance(evidence, dict):
            parts.extend(str(evidence.get(key) or "") for key in ("source_table", "source_document", "source_document_name", "field", "quote"))
    return "\n".join(part for part in parts if part)


def _has_consultation_strong_fact(item: dict[str, Any]) -> bool:
    text = _combined_text(item)
    for evidence in item.get("evidence_items") or []:
        if not isinstance(evidence, dict):
            continue
        source_table = str(evidence.get("source_table") or "").strip()
        if source_table == "consultation_record":
            return True
        source_doc = " ".join(str(evidence.get(key) or "") for key in ("source_document", "source_document_type", "source_document_name"))
        if re.search(r"(会诊申请单|会诊记录单|会诊记录)", source_doc):
            return True
    return bool(re.search(r"【[^】]*(会诊申请单|会诊记录单|会诊记录)[^】]*】", text))


def _has_transfusion_strong_fact(item: dict[str, Any]) -> bool:
    text = _strip_gap_scaffold_text(_combined_text(item))
    return bool(
        re.search(
            r"(输血医嘱|输血申请|输血记录|输血知情同意|悬浮红细胞|红细胞|血浆|血小板|冷沉淀|交叉配血|输注)",
            text,
        )
    )


def _has_chemo_strong_fact(item: dict[str, Any]) -> bool:
    text = _strip_gap_scaffold_text(_combined_text(item))
    return bool(
        re.search(
            r"(化疗医嘱|化疗记录|化学治疗记录|辅助化疗|新辅助化疗|化疗方案|"
            r"奥沙利铂|卡培他滨|顺铂|紫杉醇|吉西他滨|氟尿嘧啶|替吉奥|伊立替康|多西他赛)",
            text,
            re.IGNORECASE,
        )
    )


def _has_level_4_surgery_fact(item: dict[str, Any]) -> bool:
    text = _strip_gap_scaffold_text(_combined_text(item))
    return bool(re.search(r"(四级手术|4级手术|手术级别[:：]\s*四|手术分级[:：]\s*四)", text))


def _strip_gap_scaffold_text(text: str) -> str:
    lines = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if re.search(r"(应包含证据要素|缺失字段|缺少|未发现|未见|无.+记录|无法完成自动判定)", line):
            continue
        lines.append(line)
    return "\n".join(lines)


def _status_contradiction(status: str, text: str) -> Optional[dict[str, str]]:
    if status == "non_compliant" and POSITIVE_CONCLUSION_PATTERN.search(text):
        return {
            "suggested_status": "uncertain",
            "reason": "当前状态为不合规，但结论文字包含符合或已完成等正向表达。",
        }
    if status == "compliant" and NEGATIVE_CONCLUSION_PATTERN.search(text):
        return {
            "suggested_status": "uncertain",
            "reason": "当前状态为合规，但结论文字包含缺失、超时或不完整等问题表达。",
        }
    return None


def _has_defect_badge(item: dict[str, Any]) -> bool:
    defect_level = str(item.get("defect_level") or item.get("severity") or "").strip()
    return bool(re.search(r"(轻微缺陷|一般缺陷|严重缺陷|缺陷)", defect_level))


def _has_weak_evidence(item: dict[str, Any]) -> bool:
    evidence_items = [e for e in item.get("evidence_items") or [] if isinstance(e, dict)]
    if evidence_items:
        for evidence in evidence_items:
            source = str(evidence.get("source_document") or evidence.get("source_document_name") or evidence.get("source_table") or "").strip()
            quote = str(evidence.get("quote") or "").strip()
            if source and len(quote) >= 12:
                return False
        return True
    evidence_text = str(item.get("evidence") or item.get("evidence_text") or item.get("evidence_summary") or "").strip()
    if not evidence_text:
        return True
    compact = re.sub(r"\s+", "", evidence_text)
    has_source = bool(re.search(r"(【[^】]+】|来源|source_document|source_table)", evidence_text))
    return len(compact) < 16 or not has_source


def _finding(
    item: dict[str, Any],
    *,
    severity: str,
    risk_type: str,
    suggested_status: str,
    reason: str,
    customer_message: str,
) -> dict[str, Any]:
    projected = project_customer_safe_result_item(
        item,
        hmac_key=customer_safe_projection_key(),
    )
    rule_id = _rule_id(item)
    finding_key_material = (
        f"{projected['record_ref']}:{rule_id}:{risk_type}"
    )
    finding_key = project_customer_safe_result_item(
        {
            "record_id": finding_key_material,
            "rule_id": rule_id,
            "status": suggested_status,
            "reason_code": risk_type,
        },
        hmac_key=customer_safe_projection_key(),
    )["record_ref"]
    return {
        "finding_key": finding_key,
        "finding_ref": finding_key,
        "rule_id": rule_id,
        "rule_name": projected["rule_name"],
        "record_ref": projected["record_ref"],
        "canonical_status": projected["status"],
        "reason_code": projected["reason_code"],
        "original_status": projected["status"],
        "original_reason_code": projected["reason_code"],
        "suggested_status": suggested_status,
        "severity": severity,
        "risk_type": risk_type,
        "reason": reason,
        "customer_message": customer_message,
        "requires_human_review": True,
        "auto_applied": False,
        "reviewer": "rule_verifier",
        "evidence": projected["evidence"],
    }


def _build_llm_payload(finding: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "finding_key",
        "rule_id",
        "rule_name",
        "record_ref",
        "original_status",
        "original_reason_code",
        "suggested_status",
        "severity",
        "risk_type",
        "reason",
        "customer_message",
        "evidence",
    }
    return {key: finding.get(key) for key in allowed_keys if key in finding}


def _merge_llm_results(findings: list[dict[str, Any]], llm_results: list[dict[str, Any]]) -> None:
    by_key = {str(item.get("finding_key") or ""): item for item in findings}
    for result in llm_results or []:
        if not isinstance(result, dict):
            continue
        finding = by_key.get(str(result.get("finding_key") or ""))
        if not finding:
            continue
        finding["llm_review"] = {
            "risk_level": (
                str(result.get("risk_level") or finding.get("severity") or "").upper()
                if str(result.get("risk_level") or finding.get("severity") or "").upper()
                in {"P0", "P1", "P2"}
                else str(finding.get("severity") or "")
            ),
            "customer_message": "建议结合病历资料进一步确认。",
            "requires_human_review": bool(result.get("requires_human_review", True)),
        }


def _build_report(findings: list[dict[str, Any]], *, llm_status: str = "skipped") -> dict[str, Any]:
    summary = {"total_findings": len(findings), "p0": 0, "p1": 0, "p2": 0}
    for finding in findings:
        key = str(finding.get("severity") or "").strip().lower()
        if key in {"p0", "p1", "p2"}:
            summary[key] += 1
    return {
        "review_status": "completed",
        "reviewed_at": _now_iso(),
        "scope": SCOPE_LUXIAN_0609,
        "summary": summary,
        "findings": findings,
        "llm_review_status": llm_status,
    }


def _truncate(value: str, limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else f"{text[:limit]}..."


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
