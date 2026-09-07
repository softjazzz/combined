"""匿名展示回放：仅调用现有文案函数，不执行质控、补查资料或采信包内指令。"""

from __future__ import annotations

import re

from app.services.luxian_0609.customer_renderer import (
    customer_finding_from_controlled_facts,
    not_applicable_customer_message,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState, EvidenceState, QcDirection, RuleDecision,
)
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision

from .contracts import DiagnosticPackageError, validate_documents


def inspect_documents(documents: dict[str, object]) -> dict[str, object]:
    """只输出经过合同约束的摘要，不输出包内自由文本或身份标识。"""
    validate_documents(documents)
    manifest = documents["manifest.json"]
    return {
        "schema_version": manifest["schema_version"],
        "rule_ids": manifest["rule_ids"],
        "source_git_commit": manifest["git_commit"],
        "replay_capability": "render_only",
        "capture_completeness": "partial",
        "missing_components": manifest["missing_components"],
        "privacy_verified": False,
        "evidence_verified": False,
        "notice": "仅接受匿名回归包；匿名标记不是脱敏证明，摘要不证明原始资料或临床结论正确。",
    }


def replay_documents(
    documents: dict[str, object], *, local_git_commit: str,
    compare_current: bool = False,
) -> dict[str, object]:
    """local_git_commit 必须由可信调用方读取本地 Git，不能取自包内字段。"""
    summary = inspect_documents(documents)
    if not re.fullmatch(r"[0-9a-f]{40}", local_git_commit):
        raise DiagnosticPackageError("local_version_unavailable")
    same_version = summary["source_git_commit"] == local_git_commit
    if not same_version and not compare_current:
        raise DiagnosticPackageError("version_mismatch")
    observations = {
        item["rule_id"]: item for item in documents["results.json"]["rules"]
    }
    comparisons = []
    for item in documents["inputs.json"]["rules"]:
        raw = item["decision"]
        decision = reduce_luxian_0609_rule_decision(RuleDecision(
            rule_id=item["rule_id"], snapshot_hash=raw["snapshot_hash"],
            applicability=ApplicabilityState(raw["applicability"]),
            evidence_state=EvidenceState(raw["evidence_state"]),
            qc_direction=QcDirection(raw["qc_direction"]), reason_code=raw["reason_code"],
            fact_refs=tuple(raw["fact_refs"]), evaluator_version=raw["evaluator_version"],
            confidence=raw["confidence"],
        ))
        # 两个已经有真实缺陷回归的公开文案入口；不是第二套结果装配链。
        if item["rule_id"] == "LX0609-066":
            findings = customer_finding_from_controlled_facts(
                rule_id=item["rule_id"], facts=item["display_facts"],
            )
            projection = "customer_finding_from_controlled_facts"
        else:
            findings = not_applicable_customer_message(
                rule_id=decision.rule_id, reason_code=decision.reason_code,
            )[0]
            projection = "not_applicable_customer_message"
        if not findings:
            raise DiagnosticPackageError("render_unavailable")
        saved = observations[item["rule_id"]]
        comparisons.append({
            "rule_id": item["rule_id"], "projection": projection,
            "status": decision.final_state.value, "reason_code": decision.reason_code,
            "status_unchanged": saved["status"] == decision.final_state.value,
            "reason_unchanged": saved["reason_code"] == decision.reason_code,
            "findings_equal": saved["findings"] == findings,
            # 仅展示本地受控函数生成的文案；不回显包内观察文本。
            "current_findings": findings,
        })
    return {
        **summary,
        "local_git_commit": local_git_commit,
        "same_version": same_version,
        "mode": "same_version_render" if same_version else "cross_version_comparison",
        "clinical_correctness_verified": False,
        "results": comparisons,
    }
