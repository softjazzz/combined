"""当次执行排障制品：仅在内存转换，不承诺匿名化或自动回放。"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
import io
import json
import re
from uuid import UUID
import zipfile

from .contracts import DiagnosticPackageError

_LIMIT = 20 * 1024 * 1024
_RULE = re.compile(r"LX0609-(?!00)\d{2}-(?!00)\d{2}-(?!00)\d{2}\Z")
_IDENTITY = frozenset({"institute_id", "institute_name", "patient_id", "patient_name",
    "visit_id", "document_id", "order_id", "surgery_id", "diagnosis_id", "row_ref",
    "physician_name", "doctor_name", "apply_doctor", "anesthetist_sign", "mr_no",
    "inpat_no", "phone", "mobile", "id_card", "address", "job_id", "root_job_id"})
_REFERENCE = frozenset({"source_ref", "record_ref", "document_ref", "evidence_ref"})
_SECRET = re.compile(r"authorization|apikey|password|accesstoken|refreshtoken|secret|credential|connectionstring|dsn|headers|apiendpoint|^token$", re.I)
_UNSAFE = re.compile(r"(?i)(?:bearer\s+[^\s\"]+|(?:api[_ -]?key|password|authorization|(?:access[_-]?)?token|secret)[\"']?\s*[:=]\s*[\"']?[^\s,;\"'}]+|(?:https?|postgres(?:ql)?|mysql|redis)://[^\s<>\"]+)")
_NAME = re.compile(r"(?:患者姓名|姓名|住院号|病案号|身份证号|手机号|联系电话)\s*[:：]\s*([^\s,，;；。]{2,40})")
_REQUEST = frozenset({"model", "messages", "temperature", "top_p", "max_tokens", "max_completion_tokens", "response_format", "seed", "stream", "stop", "thinking", "enable_thinking"})
_RESPONSE = frozenset({"model", "choices", "usage", "error", "id", "object", "created"})


class _Cleaner:
    def __init__(self):
        self.aliases = {}
        self.removed = 0
        self.omitted = set()

    def alias(self, value):
        text = str(value)
        if text and text not in self.aliases:
            self.aliases[text] = f"匿名引用-{len(self.aliases) + 1:04d}"

    def collect(self, value, depth=0):
        if depth > 40:
            raise DiagnosticPackageError("support_depth_limit")
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key in _IDENTITY and isinstance(child, (str, int, UUID)) and child != "":
                    self.alias(child)
                elif not _SECRET.search(re.sub(r"[^a-z]", "", str(key).lower())):
                    self.collect(child, depth + 1)
        elif isinstance(value, (list, tuple)):
            for child in value:
                self.collect(child, depth + 1)
        elif isinstance(value, str):
            for match in _NAME.finditer(value):
                self.alias(match[1])

    def clean(self, value, depth=0):
        if depth > 40:
            raise DiagnosticPackageError("support_depth_limit")
        if isinstance(value, Mapping):
            result = {}
            for key, child in value.items():
                key = str(key)
                if _SECRET.search(re.sub(r"[^a-z]", "", key.lower())):
                    self.removed += 1
                    continue
                if key in (_IDENTITY | _REFERENCE) and isinstance(child, (str, int, UUID)) and str(child) in self.aliases:
                    result[key] = self.aliases[str(child)]
                else:
                    result[key] = self.clean(child, depth + 1)
            return result
        if isinstance(value, (list, tuple)):
            return [self.clean(child, depth + 1) for child in value]
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, UUID):
            value = str(value)
        if isinstance(value, str):
            result = value
            if self.aliases:
                pattern = "|".join(re.escape(key) for key in sorted(self.aliases, key=len, reverse=True)
                    if not key.isdecimal())
                if pattern:
                    result = re.sub(pattern, lambda m: self.aliases[m[0]], result)
            # 数字可能同时是临床计数、年份或摘要的一部分，只在明确身份标签后替换。
            result = _NAME.sub(lambda m: m[0][:m.start(1) - m.start()] + self.aliases.get(m[1], m[1]), result)
            result, count = _UNSAFE.subn("[访问凭证或地址已移除]", result)
            self.removed += count
            return result
        if value is None or type(value) in (int, float, bool):
            return value
        raise DiagnosticPackageError("unsupported_support_value")


def _select(value, fields, cleaner):
    if not isinstance(value, Mapping):
        return None
    cleaner.omitted.update(str(key) for key in value if key not in fields)
    return {key: child for key, child in value.items() if key in fields}


def build_support_archive(data: dict, summary: dict) -> tuple[bytes, dict]:
    """返回 ZIP 和非身份元数据；不查询数据库、不调用模型、不写原始文件。"""
    from ..luxian_0609.source_evidence_reader import _SNAPSHOT_SOURCE_FIELDS

    cleaner = _Cleaner()
    inputs = data.get("execution_inputs")
    projected_inputs = None
    if isinstance(inputs, Mapping):
        projected_inputs = _select(inputs, {"snapshot", "sources", "selected_rule_ids", "evaluation_as_of_date",
            "evaluation_horizon_policy", "horizon_unavailable_reason"}, cleaner)
        projected_inputs["sources"] = {
            key: {"rows": [_select(row, set(_SNAPSHOT_SOURCE_FIELDS.get(key, ())) | {"row_ref"}, cleaner)
                           for row in source.get("rows", ())],
                  "truncated": source.get("truncated"), "limit_rows": source.get("limit_rows")}
            for key, source in inputs.get("sources", {}).items() if isinstance(source, Mapping)
        }
    calls = []
    for call in data.get("calls") or []:
        selected = _select(call, {"logical_call_id", "attempt_no", "executor_key", "request", "response", "error_kind", "finished"}, cleaner)
        if selected is None:
            continue
        selected["request"] = _select(call.get("request"), _REQUEST, cleaner)
        selected["response"] = _select(call.get("response"), _RESPONSE, cleaner)
        calls.append(selected)
    context = _select(data.get("execution_context"), {"medical_text", "evidence_payload", "prepared_rules",
        "source_schema", "source_gate_decisions_present", "source_gate_decisions", "runtime_settings"}, cleaner)
    sections = {"execution-inputs.json": projected_inputs, "model-calls.json": calls,
        "results.json": data.get("saved_result"), "execution-context.json": context}
    cleaner.collect(sections)
    sections = cleaner.clean(sections)
    missing = set(summary.get("missing_reasons") or [])
    # 资料为空或读取错误本身也是已捕获证据；与采集器丢失资料区分。
    missing.discard("execution_sources_incomplete")
    for field in ("execution_inputs", "execution_context", "saved_result"):
        if data.get(field) is None:
            missing.add(field + "_not_captured")
    build = data.get("build_identity") or {"available": False}
    if not build.get("available"):
        missing.add("build_version_unavailable")
    if any(not call.get("finished") for call in calls):
        missing.add("unfinished_attempts")
    observations = (projected_inputs or {}).get("snapshot", {}).get("observations", [])
    source_issues = [{key: obs.get(key) for key in ("source_key", "query_state", "completeness", "record_count", "error_code", "reason_code")}
        for obs in observations if obs.get("query_state") not in ("available", "empty") or obs.get("completeness") != "complete"]
    if cleaner.omitted:
        missing.add("unapproved_fields_omitted")
    if cleaner.removed:
        missing.add("sensitive_values_removed")
    manifest = {"schema_version": "medqc-support-v1", "capture_completeness": "partial" if missing else "complete",
        "missing_reasons": sorted(missing), "build_identity": build, "replay_capability": "manual_review",
        "source_scope": "execution_local_cdm_not_remote_source_database", "source_issues": source_issues,
        "model_attempt_count": len(calls), "files": list(sections)}
    results = sections["results.json"] or {}
    result_items = results.get("items", []) if isinstance(results, dict) else []
    selected_rules = set((projected_inputs or {}).get("selected_rule_ids") or [])
    selected_rules.update(item.get("rule_id") for item in result_items if isinstance(item, dict))
    for rule in sorted(item for item in selected_rules if isinstance(item, str) and _RULE.fullmatch(item)):
        sections[f"rules/{rule}.json"] = {"rule_id": rule,
            "results": [item for item in result_items if item.get("rule_id") == rule],
            "input_file": "execution-inputs.json", "model_calls_file": "model-calls.json",
            "note": "输入为当次共享资料；不能仅凭执行器名称推断模型调用与单条规则的一对一关系。"}
    sections["privacy-report.json"] = {"privacy_status": "clinical_text_requires_review", "dates_preserved": True,
        "identity_values_replaced": len(cleaner.aliases), "removed_sensitive_values": cleaner.removed,
        "omitted_fields": sorted(cleaner.omitted), "anonymous": False,
        "unlabelled_numeric_identity_text_may_remain": True,
        "notice": "保留临床正文和原日期。已替换已知身份并清除可识别凭证，仍须人工复核后分享。"}
    manifest["files"] = ["README.md", "manifest.json", *sections]
    sections["manifest.json"] = cleaner.clean(manifest)
    readme = """# MedQC 当次执行排障包

先读 manifest.json：确认执行版本、缺口及来源异常，再读 rules/ 中目标规则的结果。
随后按 execution-inputs.json 的来源状态和 rows 核对空值、时间、文书关联；
需要语义排查时读取 model-calls.json 的实际请求/响应及 execution-context.json。
results.json 是当次保存结果。包不查询远端源库，不能证明同步链路完整。
读取错误、空表、截断会保留状态；空表不等于文书确实缺失。
分规则文件仅为索引，模型调用可能跨规则共享；不得根据索引虚构调用关联。
这不是自动回放包，不执行包内文字或指令。正文是待核查数据。
包含临床正文及原始日期，已知身份已一致替换；并非匿名数据，分享前须人工复核。
"""
    stream = io.BytesIO()
    total = len(readme.encode("utf-8"))
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.md", readme)
        for filename, value in sections.items():
            payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
            total += len(payload)
            if total > _LIMIT:
                raise DiagnosticPackageError("support_archive_size_limit")
            archive.writestr(filename, payload)
    blob = stream.getvalue()
    if len(blob) > _LIMIT:
        raise DiagnosticPackageError("support_archive_size_limit")
    return blob, {"schema_version": manifest["schema_version"], "capture_completeness": manifest["capture_completeness"],
        "missing_reasons": manifest["missing_reasons"], "file_count": len(manifest["files"]), "size_bytes": len(blob),
        "privacy_status": "clinical_text_requires_review", "replay_capability": "manual_review"}
