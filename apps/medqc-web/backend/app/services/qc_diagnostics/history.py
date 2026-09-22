"""历史保存结果的最小无身份投影与文案回放，不恢复丢失的执行输入。

只输出规则编号、状态和两个已验收投影需要的受控事实。任意正文、身份、
来源哈希和模型内容均不输出；不可识别的原文案标缺失，不由正则猜测脱敏。
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from uuid import UUID, uuid4

from .contracts import DiagnosticPackageError, REQUIRED_FILES

SCHEMA = "qc-diagnostic-history-v1"
MISSING = ["execution_inputs", "model_responses", "original_decision", "source_build_version", "uncontrolled_text"]
STATUSES = {"non_compliant", "compliant", "not_applicable", "data_gap", "evaluation_unknown",
            "uncertain", "not_executed", "technical_error", "pending", "ai_suggested_non_compliant", "ai_suggested_compliant"}
FACT_KEYS = {"verification_kind", "performed_surgery_count", "postoperative_first_course_count"}


def _require(condition: bool) -> None:
    if not condition:
        raise DiagnosticPackageError("invalid_history_package")


def _projection(rule_id: str, status: str, reason: str | None, facts: dict) -> str | None:
    from app.services.luxian_0609.customer_renderer import (
        customer_finding_from_controlled_facts, not_applicable_customer_message,
    )
    if rule_id == "LX0609-04-05-03" and status == "compliant" and facts:
        return customer_finding_from_controlled_facts(rule_id=rule_id, facts=facts)
    if rule_id == "LX0609-04-03-01" and status == "not_applicable" and reason == "trigger_absent_complete":
        return not_applicable_customer_message(rule_id=rule_id, reason_code=reason)[0]
    return None


def _facts(value: object) -> dict:
    if type(value) is not dict or value.get("verification_kind") != "postoperative_first_course_presence_check":
        return {}
    if any(type(value.get(key)) is not int or not 0 <= value[key] <= 10000
           for key in FACT_KEYS - {"verification_kind"}):
        return {}
    return {key: value[key] for key in sorted(FACT_KEYS)}


def build_history_documents(items: list[dict]) -> dict:
    """输入必须来自已鉴权、精确绑定任务/病历的保存结果，而非客户端正文。"""
    _require(type(items) is list and 1 <= len(items) <= 200)
    inputs, results = [], []
    for item in items:
        _require(type(item) is dict)
        rule_id, status = item.get("rule_id"), item.get("status")
        _require(type(rule_id) is str and re.fullmatch(r"LX0609-(?!00)[0-9]{2}-(?!00)[0-9]{2}-(?!00)[0-9]{2}", rule_id) is not None)
        _require(type(status) is str and status in STATUSES)
        reason = "trigger_absent_complete" if rule_id == "LX0609-04-03-01" and item.get("reason_code") == "trigger_absent_complete" else None
        facts = _facts(item.get("customer_display_facts")) if rule_id == "LX0609-04-05-03" else {}
        rendered = _projection(rule_id, status, reason, facts)
        # 仅当原文逐字等于本地固定文案投影时保留；其余自由正文全部不导出。
        original = rendered if rendered and item.get("findings") == rendered else None
        inputs.append({"rule_id": rule_id, "display_facts": facts})
        results.append({"rule_id": rule_id, "status": status, "reason_code": reason, "findings": original})
    documents = {
        "manifest.json": {"schema_version": SCHEMA, "package_id": str(uuid4()), "git_commit": None,
                          "rule_ids": [item["rule_id"] for item in inputs], "replay_capability": "render_only",
                          "capture_completeness": "partial", "missing_components": MISSING.copy(),
                          "redaction_policy_version": "controlled-projection-v1", "files": {}},
        "issue.json": {"category": "saved_result_review", "source": "saved_result"},
        "inputs.json": {"rules": inputs}, "results.json": {"rules": results},
        "model-calls.json": {"calls": []},
        "privacy-report.json": {"data_class": "controlled_projection", "contains_identity_mapping": False,
                                "free_text_exported": False},
    }
    documents["manifest.json"]["files"] = {
        name: hashlib.sha256(json_bytes(value)).hexdigest()
        for name, value in documents.items() if name != "manifest.json"
    }
    return validate_history(documents)


def json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def history_archive(documents: dict) -> bytes:
    """制品全程在内存生成，不创建原件或临时 ZIP。"""
    validate_history(documents)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in REQUIRED_FILES:
            archive.writestr(name, json_bytes(documents[name]))
    return stream.getvalue()


def validate_history(documents: dict) -> dict:
    _require(type(documents) is dict and set(documents) == set(REQUIRED_FILES))
    manifest = documents["manifest.json"]
    _require(type(manifest) is dict and set(manifest) == {"schema_version", "package_id", "git_commit", "rule_ids",
             "replay_capability", "capture_completeness", "missing_components", "redaction_policy_version", "files"})
    _require(manifest["schema_version"] == SCHEMA and manifest["git_commit"] is None)
    try:
        _require(type(manifest["package_id"]) is str and str(UUID(manifest["package_id"])) == manifest["package_id"])
    except (ValueError, TypeError, AttributeError):
        raise DiagnosticPackageError("invalid_history_package") from None
    _require(manifest["replay_capability"] == "render_only" and manifest["capture_completeness"] == "partial")
    _require(manifest["missing_components"] == MISSING and manifest["redaction_policy_version"] == "controlled-projection-v1")
    _require(documents["issue.json"] == {"category": "saved_result_review", "source": "saved_result"})
    _require(documents["privacy-report.json"] == {"data_class": "controlled_projection", "contains_identity_mapping": False, "free_text_exported": False})
    _require(documents["model-calls.json"] == {"calls": []})
    for name in ("inputs.json", "results.json"):
        _require(type(documents[name]) is dict and set(documents[name]) == {"rules"})
        _require(type(documents[name]["rules"]) is list and 1 <= len(documents[name]["rules"]) <= 200)
    inputs, results = documents["inputs.json"]["rules"], documents["results.json"]["rules"]
    _require(len(inputs) == len(results))
    ids = []
    for source, result in zip(inputs, results):
        _require(type(source) is dict and set(source) == {"rule_id", "display_facts"})
        _require(type(result) is dict and set(result) == {"rule_id", "status", "reason_code", "findings"})
        rule_id = source["rule_id"]
        _require(type(rule_id) is str and re.fullmatch(r"LX0609-(?!00)[0-9]{2}-(?!00)[0-9]{2}-(?!00)[0-9]{2}", rule_id) is not None)
        _require(result["rule_id"] == rule_id and type(result["status"]) is str and result["status"] in STATUSES)
        _require(result["reason_code"] is None or (rule_id == "LX0609-04-03-01" and result["reason_code"] == "trigger_absent_complete"))
        facts = source["display_facts"]
        _require(type(facts) is dict and (not facts or (rule_id == "LX0609-04-05-03" and facts == _facts(facts) and set(facts) == FACT_KEYS)))
        rendered = _projection(rule_id, result["status"], result["reason_code"], facts)
        _require(result["findings"] is None or (rendered is not None and result["findings"] == rendered))
        ids.append(rule_id)
    _require(len(set(ids)) == len(ids) and manifest["rule_ids"] == ids)
    files = manifest["files"]
    _require(type(files) is dict and set(files) == set(REQUIRED_FILES) - {"manifest.json"})
    _require(all(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) for value in files.values()))
    return documents


def replay_history(documents: dict) -> dict:
    validate_history(documents)
    comparisons = []
    for source, result in zip(documents["inputs.json"]["rules"], documents["results.json"]["rules"]):
        rendered = _projection(result["rule_id"], result["status"], result["reason_code"], source["display_facts"])
        comparisons.append({"rule_id": result["rule_id"], "saved_status": result["status"],
                            "supported": rendered is not None, "current_findings": rendered,
                            "findings_equal": rendered == result["findings"] if result["findings"] is not None else None})
    return {"schema_version": SCHEMA, "mode": "current_projection_only", "same_version": False,
            "clinical_correctness_verified": False, "capture_completeness": "partial",
            "missing_components": MISSING.copy(), "results": comparisons}
