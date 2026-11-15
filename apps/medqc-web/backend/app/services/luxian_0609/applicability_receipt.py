"""不适用判定的安全审计回执；来源观察不是不存在事件的原始文书。"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
import re

from .decision_model import ALLOWED_REASON_CODES_BY_FINAL_STATE, ApplicabilityState, EvidenceState, QcDirection
from .evidence_material import EvidenceMaterialUnavailable
from .evidence_snapshot import Luxian0609EvidenceSnapshot, SourceCompleteness
from .fact_schema import Assertion, CurrentVisitRelevance, EventStatus, TriggerScope
from .source_manifest import QueryStatus
from . import source_registry


SCHEMA_VERSION = "lx0609-applicability-receipt-v1"
_HASH = re.compile(r"^[a-f0-9]{64}$")
_SCOPE_STATUSES = frozenset({"available", "empty", "table_missing", "columns_missing", "empty_unconfirmed", "body_empty", "not_supplied", "unknown"})
_COVERAGES = frozenset({"complete", "unknown", "partial", "registered_materials", "registered_materials_complete"})


def consumed_source_keys(*, decision, snapshot, materials=None):
    """仅用已绑定引用找实际依赖；不把备选来源全集当作判定分支。"""
    from .decision_binding import _allowed_source_keys

    allowed = _allowed_source_keys(decision.rule_id)
    refs = set(decision.fact_refs)
    keys = {item.source_key for item in snapshot.observations
            if item.source_key in allowed and item.snapshot_ref.removeprefix("sha256:") in refs}
    keys.update(item.source_key for item in snapshot.facts if item.source_key in allowed and item.fact_id in refs)
    document_refs = refs.intersection(snapshot.document_refs)
    if materials is not None and document_refs:
        for key in allowed:
            if not materials.has_source(key):
                continue
            try:
                rows = materials.document_rows(key, snapshot=snapshot)
            except EvidenceMaterialUnavailable:
                continue  # 未消费的备选来源可能缺供给或截断。
            if any(ref in document_refs for ref, _ in rows):
                keys.add(key)
    return frozenset(keys)


def guard_not_applicable_sources(decision, *, snapshot, materials, source_keys):
    """缺供给不能证明无事件；错误优先于缺口，完整零行可以证明无事件。"""
    if decision.applicability is not ApplicabilityState.NOT_APPLICABLE:
        return decision
    observations = {item.source_key: item for item in snapshot.observations}
    selected = [observations[key] for key in source_keys if key in observations]
    reason = None
    if any(item.query_state is QueryStatus.ERROR for item in selected):
        reason = "source_query_error"
    elif not source_keys or len(selected) != len(source_keys):
        reason = "source_readiness_unproven"
    elif any(item.query_state is QueryStatus.UNAVAILABLE for item in selected):
        reason = "source_unavailable"
    elif any(item.completeness is SourceCompleteness.TRUNCATED for item in selected):
        reason = "source_truncated"
    elif any(item.completeness is not SourceCompleteness.COMPLETE for item in selected):
        reason = "source_readiness_unproven"
    elif materials is not None and any(not materials.permits_absence(key) for key in source_keys):
        reason = "source_readiness_unproven"
    if reason is None:
        return decision
    technical = reason == "source_query_error"
    return replace(decision, applicability=ApplicabilityState.ERROR if technical else ApplicabilityState.UNKNOWN,
                   evidence_state=EvidenceState.TECHNICAL_ERROR if technical else EvidenceState.DATA_GAP,
                   qc_direction=QcDirection.UNKNOWN, reason_code=reason, criterion_results=(),
                   positive_document_refs=(), confidence=None, evaluator_version="applicability-source-guard-v1")


def _safe_scope(value):
    if not isinstance(value, Mapping):
        return None
    return {"status": value.get("status") if isinstance(value.get("status"), str) and value["status"] in _SCOPE_STATUSES else "unknown",
            "coverage": value.get("coverage") if isinstance(value.get("coverage"), str) and value["coverage"] in _COVERAGES else "unknown",
            "can_judge_clinical_absence": value.get("can_judge_clinical_absence") is True}


def build_applicability_receipt(*, decision, snapshot, materials=None):
    """保留规则相关观察与实际依赖标记；拒绝未绑定会话，不输出正文和异常。"""
    from .decision_binding import _allowed_source_keys

    if not isinstance(snapshot, Luxian0609EvidenceSnapshot) or decision.snapshot_hash != snapshot.snapshot_hash:
        raise ValueError("applicability receipt snapshot mismatch")
    if materials is not None and materials.snapshot_hash != snapshot.snapshot_hash:
        raise ValueError("applicability receipt material mismatch")
    if decision.final_state.value != "not_applicable":
        raise ValueError("applicability receipt requires not applicable decision")
    allowed = _allowed_source_keys(decision.rule_id)
    consumed = consumed_source_keys(decision=decision, snapshot=snapshot, materials=materials)
    checks = []
    for item in snapshot.observations:
        if item.source_key not in allowed:
            continue
        check = {"source_key": item.source_key, "query_state": item.query_state.value,
                 "completeness": item.completeness.value, "record_count": item.record_count,
                 "query_version": item.query_version, "snapshot_ref": item.snapshot_ref,
                 "depended_on": item.source_key in consumed}
        scope = _safe_scope(materials.scope(item.source_key)) if materials is not None else None
        if scope is not None:
            check["scope"] = scope
        checks.append(check)
    receipt = {"schema_version": SCHEMA_VERSION, "rule_id": decision.rule_id,
               "status": decision.final_state.value, "reason_code": decision.reason_code,
               "snapshot_hash": decision.snapshot_hash, "decision_fingerprint": decision.decision_fingerprint,
               "evaluator_version": decision.evaluator_version, "fact_refs": list(decision.fact_refs),
               "source_checks": checks,
               "event_basis": [{"fact_ref": fact.fact_id, "source_key": fact.source_key,
                                "assertion": fact.assertion.value, "trigger_scope": fact.trigger_scope.value,
                                "current_visit_relevance": fact.current_visit_relevance.value,
                                "event_status": fact.event_status.value}
                               for fact in snapshot.facts if fact.fact_id in decision.fact_refs]}
    return validate_applicability_receipt(receipt)


def validate_applicability_receipt(raw):
    """持久化白名单入口；未知键与不安全自由文本均拒绝，不静默剥除。"""
    def require(condition):
        if not condition:
            raise ValueError("invalid applicability receipt")

    def keys(value, required, optional=()):
        require(isinstance(value, Mapping))
        require(set(required).issubset(value) and set(value).issubset(set(required) | set(optional)))

    def digest(value):
        require(isinstance(value, str) and _HASH.fullmatch(value) is not None)

    keys(raw, {"schema_version", "rule_id", "status", "reason_code", "snapshot_hash", "decision_fingerprint", "evaluator_version", "fact_refs", "source_checks", "event_basis"}, {"material_fingerprint"})
    require(raw["schema_version"] == SCHEMA_VERSION and raw["status"] == "not_applicable")
    from .decision_binding import _allowed_source_keys
    from .decision_model import _VERSION_PATTERN, _has_forbidden_version_marker
    require(isinstance(raw["rule_id"], str) and re.fullmatch(r"LX0609-\d{2}-\d{2}-\d{2}", raw["rule_id"]) is not None)
    allowed = _allowed_source_keys(raw["rule_id"])
    require(isinstance(raw["reason_code"], str) and raw["reason_code"] in ALLOWED_REASON_CODES_BY_FINAL_STATE["not_applicable"])
    for name in ("snapshot_hash", "decision_fingerprint", "material_fingerprint"):
        if name in raw:
            digest(raw[name])
    version = raw["evaluator_version"]
    require(isinstance(version, str) and _VERSION_PATTERN.fullmatch(version) is not None and not _has_forbidden_version_marker(version))
    refs = raw["fact_refs"]
    require(type(refs) is list and 0 < len(refs) <= 128)
    for ref in refs:
        digest(ref)
    require(len(refs) == len(set(refs)))
    checks = raw["source_checks"]
    require(type(checks) is list and 0 < len(checks) <= 128)
    seen = set()
    for check in checks:
        keys(check, {"source_key", "query_state", "completeness", "record_count", "query_version", "snapshot_ref", "depended_on"}, {"scope"})
        source = check["source_key"]
        require(isinstance(source, str) and source in allowed and source_registry.is_registered_luxian_0609_source_key(source) and source not in seen)
        seen.add(source)
        require(isinstance(check["query_state"], str) and check["query_state"] in {item.value for item in QueryStatus})
        require(isinstance(check["completeness"], str) and check["completeness"] in {item.value for item in SourceCompleteness})
        count = check["record_count"]
        require(count is None or type(count) is int and count >= 0)
        if check["query_state"] == "empty":
            require(count == 0 and check["completeness"] != "truncated")
        elif check["query_state"] == "available":
            require(count is not None and count > 0)
        else:
            require(count is None and check["completeness"] == "unproven")
        require(isinstance(check["query_version"], str) and check["query_version"] == check["query_version"].strip() and source_registry.source_key_accepts_query_version(source, check["query_version"]))
        ref = check["snapshot_ref"]
        require(isinstance(ref, str) and ref.startswith("sha256:"))
        digest(ref.removeprefix("sha256:"))
        require(type(check["depended_on"]) is bool)
        if check["depended_on"]:
            require(check["query_state"] in {"available", "empty"} and check["completeness"] == "complete")
        if "scope" in check:
            scope = check["scope"]
            keys(scope, {"status", "coverage", "can_judge_clinical_absence"})
            require(isinstance(scope["status"], str) and scope["status"] in _SCOPE_STATUSES and isinstance(scope["coverage"], str) and scope["coverage"] in _COVERAGES and type(scope["can_judge_clinical_absence"]) is bool)
            if check["depended_on"]:
                require(scope["can_judge_clinical_absence"])
    require(any(check["depended_on"] for check in checks))
    basis = raw["event_basis"]
    require(type(basis) is list and len(basis) <= 128)
    for item in basis:
        keys(item, {"fact_ref", "source_key", "assertion", "trigger_scope", "current_visit_relevance", "event_status"})
        digest(item["fact_ref"])
        require(item["fact_ref"] in refs and isinstance(item["source_key"], str) and item["source_key"] in seen)
        for key, enum in (("assertion", Assertion), ("trigger_scope", TriggerScope), ("current_visit_relevance", CurrentVisitRelevance), ("event_status", EventStatus)):
            require(isinstance(item[key], str) and item[key] in {value.value for value in enum})
    return deepcopy(dict(raw))
