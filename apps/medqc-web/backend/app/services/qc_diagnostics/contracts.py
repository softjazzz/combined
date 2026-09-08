"""首批匿名展示回放合同，不代表客户采集、脱敏或执行器回放已经可用。"""

from __future__ import annotations

import re
from uuid import UUID

from app.services.luxian_0609.decision_model import (
    ApplicabilityState, EvidenceState, QcDirection, RuleDecision,
)
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision

REQUIRED_FILES = (
    "manifest.json", "issue.json", "inputs.json", "model-calls.json",
    "results.json", "privacy-report.json",
)
SCHEMA_VERSION = "qc-diagnostic-render-v1"
_RULES = {"LX0609-032", "LX0609-066"}
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
_MANIFEST_KEYS = {
    "schema_version", "package_id", "git_commit", "build_id", "rule_ids",
    "replay_capability", "capture_completeness", "missing_components",
    "redaction_policy_version", "files",
}
_DECISION_KEYS = {
    "snapshot_hash", "applicability", "evidence_state", "qc_direction",
    "reason_code", "fact_refs", "evaluator_version", "confidence",
}


class DiagnosticPackageError(ValueError):
    """只暴露固定错误码，不把不可信输入拼入异常消息。"""

    def __init__(self, code: str = "invalid_contract") -> None:
        self.code = code if re.fullmatch(r"[a-z_]{1,64}", code) else "invalid_contract"
        super().__init__(self.code)


def _require(condition: bool, code: str = "invalid_contract") -> None:
    if not condition:
        raise DiagnosticPackageError(code)


def _object(value: object, keys: set[str]) -> dict:
    _require(type(value) is dict and set(value) == keys)
    return value


def _matches(value: object, pattern: re.Pattern) -> bool:
    return type(value) is str and pattern.fullmatch(value) is not None


def _rule_ids(value: object) -> list[str]:
    _require(type(value) is list and 1 <= len(value) <= len(_RULES))
    _require(all(type(item) is str and item in _RULES for item in value))
    _require(len(set(value)) == len(value))
    return value


def _validate_manifest(value: object) -> dict:
    manifest = _object(value, _MANIFEST_KEYS)
    _require(manifest["schema_version"] == SCHEMA_VERSION, "unsupported_schema")
    _require(type(manifest["package_id"]) is str)
    try:
        _require(str(UUID(manifest["package_id"])) == manifest["package_id"])
    except (ValueError, AttributeError):
        raise DiagnosticPackageError() from None
    _require(_matches(manifest["git_commit"], re.compile(r"[0-9a-f]{40}\Z")))
    _require(_matches(manifest["build_id"], _TOKEN))
    _rule_ids(manifest["rule_ids"])
    _require(manifest["replay_capability"] == "render_only", "unsupported_capability")
    _require(manifest["capture_completeness"] == "partial")
    _require(manifest["missing_components"] == ["execution_inputs", "model_responses"])
    _require(manifest["redaction_policy_version"] == "synthetic-v1")
    files = _object(manifest["files"], set(REQUIRED_FILES) - {"manifest.json"})
    _require(all(_matches(digest, _HEX64) for digest in files.values()))
    return manifest


def _validate_input(value: object):
    item = _object(value, {"rule_id", "decision", "display_facts"})
    _require(type(item["rule_id"]) is str and item["rule_id"] in _RULES)
    raw = _object(item["decision"], _DECISION_KEYS)
    _require(_matches(raw["snapshot_hash"], _HEX64))
    refs = raw["fact_refs"]
    _require(type(refs) is list and len(refs) <= 128)
    _require(all(_matches(ref, _HEX64) for ref in refs))
    _require(len(set(refs)) == len(refs))
    _require(_matches(raw["evaluator_version"], _TOKEN))
    _require(all(type(raw[key]) is str for key in (
        "applicability", "evidence_state", "qc_direction", "reason_code",
    )))
    _require(raw["confidence"] is None or type(raw["confidence"]) in (int, float))
    if item["rule_id"] == "LX0609-032":
        expected = ("not_applicable", "sufficient", "unknown", "trigger_absent_complete")
        _object(item["display_facts"], set())
    else:
        expected = ("applicable", "sufficient", "satisfied", "requirement_satisfied")
        facts = _object(item["display_facts"], {
            "verification_kind", "performed_surgery_count", "postoperative_first_course_count",
        })
        _require(facts["verification_kind"] == "postoperative_first_course_presence_check")
        for key in ("performed_surgery_count", "postoperative_first_course_count"):
            _require(type(facts[key]) is int and 0 <= facts[key] <= 10000)
    _require(tuple(raw[key] for key in (
        "applicability", "evidence_state", "qc_direction", "reason_code",
    )) == expected, "unsupported_decision")
    try:
        decision = RuleDecision(
            rule_id=item["rule_id"], snapshot_hash=raw["snapshot_hash"],
            applicability=ApplicabilityState(raw["applicability"]),
            evidence_state=EvidenceState(raw["evidence_state"]),
            qc_direction=QcDirection(raw["qc_direction"]), reason_code=raw["reason_code"],
            fact_refs=tuple(refs), evaluator_version=raw["evaluator_version"],
            confidence=raw["confidence"],
        )
        return reduce_luxian_0609_rule_decision(decision)
    except (TypeError, ValueError, OverflowError):
        raise DiagnosticPackageError("invalid_decision") from None


def validate_documents(documents: dict[str, object]) -> dict[str, object]:
    """严格校验并原样返回；synthetic 标记是声明，不构成自动脱敏证明。"""
    _object(documents, set(REQUIRED_FILES))
    if type(documents["manifest.json"]) is dict and documents["manifest.json"].get("schema_version") == "qc-diagnostic-history-v1":
        from .history import validate_history
        return validate_history(documents)
    manifest = _validate_manifest(documents["manifest.json"])
    issue = _object(documents["issue.json"], {"category", "source"})
    _require(issue == {"category": "customer_wording", "source": "synthetic_regression"})
    privacy = _object(documents["privacy-report.json"], {"data_class", "contains_identity_mapping"})
    _require(privacy["data_class"] == "synthetic" and privacy["contains_identity_mapping"] is False)
    calls = _object(documents["model-calls.json"], {"calls"})
    _require(type(calls["calls"]) is list and not calls["calls"])
    inputs = _object(documents["inputs.json"], {"rules"})["rules"]
    results = _object(documents["results.json"], {"rules"})["rules"]
    _require(type(inputs) is list and 1 <= len(inputs) <= 2)
    _require(type(results) is list and len(results) == len(inputs))
    decisions = [_validate_input(item) for item in inputs]
    input_ids = _rule_ids([decision.rule_id for decision in decisions])
    _require(set(input_ids) == set(manifest["rule_ids"]))
    by_rule = {decision.rule_id: decision for decision in decisions}
    result_ids = []
    for result in results:
        result = _object(result, {"rule_id", "status", "reason_code", "findings"})
        _require(type(result["rule_id"]) is str and result["rule_id"] in by_rule)
        result_ids.append(result["rule_id"])
        decision = by_rule[result["rule_id"]]
        _require(result["status"] == decision.final_state.value)
        _require(result["reason_code"] == decision.reason_code)
        finding = result["findings"]
        _require(type(finding) is str and 1 <= len(finding) <= 4000)
        _require(not any(ord(char) < 32 and char not in "\n\t" for char in finding))
    _require(set(_rule_ids(result_ids)) == set(input_ids))
    return documents
