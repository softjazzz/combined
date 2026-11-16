"""四类材料唯一业务投影：搬运同步选择，冻结整份DTO，不重新选择或去重。"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path

from . import case_material_snapshot as material

KINDS = ("daily_course_record", "presurg_summary", "surgery_record", "postsurg_firstcourse_record")
CONTRACT = "clinical-primary-four-v1"
_SCOPE_NOTICE = "来源覆盖与时间语义待核，不能据此认定未书写"
_VERSION_FIELDS = ("source_version_key", "version_id", "source_record_identity", "source_namespace", "source_object")
_TIME_FIELDS = {
    "record_time": ("record_time", "record_datetime"),
    "submit_time": ("submit_time", "submit_datetime"),
    "modified_time": ("modified_time", "last_modified_time", "last_modified_datetime", "update_time"),
    "surgery_begin_time": ("surgery_begin_time", "surgery_begin_datetime"),
    "surgery_end_time": ("surgery_end_time", "surgery_end_datetime"),
}


def enabled():
    return os.getenv("QC_PRIMARY_FOUR_MATERIAL_ENABLED", "").strip().lower() == "true"


def load_policy(identity):
    """仅接受部署者显式提供的批准文件；数据库管理表不构成批准输入。"""
    from ..database import clinical_connection as clinical
    from . import primary_material_readonly as readonly
    path = Path(os.getenv("QC_PRIMARY_FOUR_POLICY_FILE", ""))
    try:
        if (not path.is_absolute() or path.suffix.lower() != ".json" or path.is_symlink()
                or not path.is_file() or path.stat().st_size > 1024 * 1024
                or (os.name != "nt" and path.stat().st_mode & 0o022)):
            raise ValueError
        content = json.loads(path.read_text(encoding="utf-8"))
        entries = content["policies"] if isinstance(content, dict) else content
        if not isinstance(entries, list):
            raise ValueError
        matches = []
        for entry in entries:
            policy = readonly.PrimaryPolicy.from_dict(entry["policy"])
            if tuple(policy.canonical_case) != tuple(identity):
                continue
            if (entry["policy_hash"] != policy.policy_hash
                    or entry["source_binding"] != clinical.source_binding()
                    or not any(native[0] == "cache" for native in policy.native_cases)):
                raise ValueError
            matches.append(policy)
        if len(matches) != 1:
            raise ValueError
        return matches[0]
    except (OSError, ValueError, TypeError, KeyError):
        raise material.MaterialSnapshotError("primary_material_approved_policy_required") from None


def read_manifest(connection, identity):
    """能力探测与固定reader共用调用者RR只读连接，绝不创建第二连接。"""
    from . import primary_material_readonly as readonly
    if not readonly.primary_objects_available(connection):
        return None
    policy = load_policy(identity)
    if tuple(policy.canonical_case) != tuple(identity):
        raise material.MaterialSnapshotError("primary_material_identity_mismatch")
    result = readonly.read_primary_in_transaction(connection, policy, readonly.real_contracts())
    if result.get("case_id") != policy.case_id or result.get("policy_hash") != policy.policy_hash:
        raise material.MaterialSnapshotError("primary_material_identity_mismatch")
    _index(result)
    from ..database import clinical_connection as clinical
    # 业务三键只按明确批准的映射投影，原同步DTO及其selection_id含义保持不变。
    return {**deepcopy(result), "business_binding": {
        "canonical_case": list(policy.canonical_case), "native_cases": [list(case) for case in policy.native_cases],
        "source_binding": clinical.source_binding(), "policy_hash": policy.policy_hash,
        "reader_source_commit": readonly.SOURCE_COMMIT,
    }}


def capture_into(state, connection, identity):
    captured = read_manifest(connection, identity)
    state["primary_material_manifest"] = captured
    state["primary_material_capability"] = {"status": "AVAILABLE" if captured is not None else "NOT_DEPLOYED"}


def manifest(identity=None):
    from .validation_material_source import is_material_copy
    if identity is not None and is_material_copy(identity[1], identity[2]):
        return None
    state = material.context()
    if state is None and enabled():
        raise material.MaterialSnapshotError("primary_material_capture_required")
    if state is None or "primary_material_manifest" not in state:
        return None  # 旧快照只按已保存协议回放。
    if identity is not None:
        material.identity_check(state, identity)
    return deepcopy(state["primary_material_manifest"])


def _index(value):
    try:
        if value["contract"] != CONTRACT:
            raise ValueError
        entries = value["materials"]
        versions = {entry["version_id"]: entry for entry in entries}
        if len(versions) != len(entries):
            raise ValueError
        selected = set()
        for item in value["items"]:
            kind, version = item["document_type"], item["selected_version"]
            if kind not in KINDS:
                raise ValueError
            if version is not None:
                if (version in selected or version not in versions
                        or versions[version]["document_type"] != kind
                        or item["selection_reason"] == "HELD"):
                    raise ValueError
                selected.add(version)
        return versions
    except (KeyError, TypeError, ValueError):
        raise material.MaterialSnapshotError("primary_material_manifest_invalid") from None


def scope_from_manifest(value, source_key):
    versions = _index(value)
    items = [item for item in value["items"] if item["document_type"] == source_key]
    selected = [item for item in items if item["selected_version"] is not None]
    return deepcopy({
        "contract": CONTRACT, "selection_id": value.get("selection_id"), "policy_hash": value.get("policy_hash"),
        "status": "available" if selected else "held" if items else "empty_unconfirmed",
        "can_judge_clinical_absence": False,
        "coverage": value.get("coverage", {}).get(source_key, {}),
        "selected_versions": [item["selected_version"] for item in selected],
        "uncertain_fields": {item["selected_version"]: item.get("uncertain_fields", []) for item in selected},
        "time_availability": {item["selected_version"]: versions[item["selected_version"]].get("time_availability", {}) for item in selected},
        "time_role_status": {item["selected_version"]: versions[item["selected_version"]].get("time_role_status", {}) for item in selected},
    })


def scope(source_key):
    if source_key not in KINDS:
        return None
    value = manifest()
    return scope_from_manifest(value, source_key) if value is not None else None


def _row(entry, item, value, *, for_rules=True):
    from .daily_material_projection import _decode_scalar
    row = {key: _decode_scalar(raw) for key, raw in entry.get("target_payload", {}).items()}
    binding = value.get("business_binding")
    if binding is not None:
        if [entry["source_namespace"], *entry["native_key"][:3]] not in binding["native_cases"]:
            raise material.MaterialSnapshotError("primary_material_identity_mismatch")
        row.update(zip(("institute_id", "patient_id", "visit_id"), binding["canonical_case"]))
    kind = entry["document_type"]
    row.update(document_id=entry["native_key"][-1], document_title=entry.get("title"),
               document_status=entry.get("source_status"), __document_type=kind)
    # 手术record_content保持原值；正文严格来自本版本surgery_process。
    row["surgery_process" if kind == "surgery_record" else "record_content"] = entry.get("body")
    uncertain = set(item.get("uncertain_fields", ()))
    for role, fields in _TIME_FIELDS.items():
        role_status = entry.get("time_role_status", {}).get(role)
        # 固定Cache DTO可没有新增角色元数据；保留选择器已准入的显式偏移时间。
        role_usable = role_status == "CONFIRMED" or (entry["source_namespace"] == "cache" and role_status is None)
        usable = (role_usable
                  and entry.get("time_availability", {}).get(role) == "EXPLICIT_OFFSET"
                  and role not in uncertain)
        for field in fields:
            row[field] = entry.get("times", {}).get(role) if not for_rules or usable else None
    if for_rules and "body" in uncertain:
        # 不通过其他正文别名把冲突内容重新送回规则。
        for field in ("record_content", "surgery_process", "content", "raw_text", "assembled_text", "text", "original_text"):
            row[field] = None
    metadata = entry
    if for_rules:
        # 完整原文仅存manifest及目录；规则不能从metadata/source_payload绕回冲突正文或未知时间。
        row.pop("source_payload", None)
        metadata = {key: entry[key] for key in (
            "version_id", "record_identity", "source_namespace", "document_type", "native_key",
            "source_status", "record_status", "time_availability", "time_role_status", "publication",
            "source_metadata_revision", "source_metadata_sha256", "native_primary_key", "lifecycle_admission",
        ) if key in entry}
    row.update({
        "source_version_key": "::".join((kind, entry["record_identity"], entry["version_id"])),
        "version_id": entry["version_id"], "source_record_identity": entry["record_identity"],
        "source_namespace": entry["source_namespace"],
        "source_object": entry.get("source_object") or entry.get("publication", {}).get("interface"),
        "primary_material": {**deepcopy(metadata), "selection": deepcopy(item)},
        # 行级只附本版本范围，避免每行重复整个病例的所有版本；完整范围由scope()提供。
        "primary_material_scope": {
            "contract": CONTRACT, "selection_id": value.get("selection_id"), "policy_hash": value.get("policy_hash"),
            "status": "available" if item.get("selected_version") == entry["version_id"] else "held",
            "can_judge_clinical_absence": False, "coverage": deepcopy(value.get("coverage", {}).get(kind, {})),
            "uncertain_fields": deepcopy(item.get("uncertain_fields", [])),
            "time_availability": deepcopy(entry.get("time_availability", {})),
            "time_role_status": deepcopy(entry.get("time_role_status", {})),
        },
    })
    return row


def project_rows(value, source_key):
    versions = _index(value)
    return [_row(versions[item["selected_version"]], item, value) for item in value["items"]
            if item["document_type"] == source_key and item["selected_version"] is not None]


def rows(identity, source_key, *, limit=None):
    if source_key not in KINDS:
        return None
    value = manifest(identity)
    if value is None:
        return None
    result = project_rows(value, source_key)
    return result if limit is None else result[:limit]


def rule_rows(identity, source_key, approved_fields):
    projected = rows(identity, source_key)
    if projected is None:
        return None
    return [{key: row[key] for key in (*approved_fields, *_VERSION_FIELDS) if key in row} for row in projected]


def display_scope(value):
    if value is None:
        capability = (material.context() or {}).get("primary_material_capability", {})
        if capability.get("status") != "NOT_DEPLOYED":
            return None
        return {"contract": CONTRACT, "notice": "四类优先材料接口未部署，当前展示基础CDM材料", "kinds": {
            kind: {"status": "NOT_DEPLOYED", "notice": "优先材料接口未部署", "selected_count": 0,
                   "held_count": 0, "can_judge_clinical_absence": False} for kind in KINDS}}
    kinds = {}
    for kind in KINDS:
        scope_value = scope_from_manifest(value, kind)
        selected_count = len(scope_value["selected_versions"])
        held_count = sum(item["document_type"] == kind and item["selected_version"] is None for item in value["items"])
        kinds[kind] = {"status": scope_value["status"].upper(), "selected_count": selected_count,
                       "held_count": held_count, "can_judge_clinical_absence": False,
                       "notice": _SCOPE_NOTICE}
    return {"contract": CONTRACT, "selection_id": value.get("selection_id"), "policy_hash": value.get("policy_hash"),
            "notice": "已按批准清单选取整份版本；来源覆盖与时间语义待核", "kinds": kinds}


def display_item(entry, item, value):
    selected = item.get("selected_version") == entry["version_id"]
    labels = {"CLINICAL_PRIMARY": "临床来源优先", "CACHE_FALLBACK": "Caché可靠版本", "HELD": "待核，未纳入规则"}
    parts = [labels.get(item.get("selection_reason"), "替代版本，仅展示") if selected or item.get("selection_reason") == "HELD" else "替代版本，仅展示"]
    if item.get("relation") == "VERSION_DIFFERENCE":
        parts.append("版本存在差异")
    if not str(entry.get("body") or "").strip():
        parts.append("正文为空")
    if item.get("uncertain_fields"):
        parts.append("部分字段或时间语义待核")
    return {"material_state": item.get("selection_reason"), "material_selected": selected, "material_rule_usable": selected,
            "material_source_label": {"cache": "Caché", "clinical": "临床来源"}.get(entry["source_namespace"], "来源待核"),
            "material_notice": "；".join(parts), "material_scope_notice": _SCOPE_NOTICE}


def project_documents(value):
    from .bundles.emr_view import _normalize_source_document
    from .document_assembly import assemble_document
    _index(value)
    result = []
    selections = {version: candidate for candidate in value["items"]
                  for version in {candidate.get("selected_version"), *candidate.get("alternatives", ()), *candidate.get("exclusions", {})}
                  if version is not None}
    for entry in value["materials"]:
        version = entry["version_id"]
        item = selections.get(version, {"document_type": entry["document_type"], "selected_version": None, "selection_reason": "HELD"})
        raw = _row(entry, item, value, for_rules=False)
        assembled = assemble_document(entry["document_type"], raw)
        raw.update(document_type=entry["document_type"], content=assembled.assembled_text,
                   display_time=entry.get("times", {}).get("record_time"))
        doc = _normalize_source_document(raw_doc=raw, index=len(result),
                                         execution_domain="course" if entry["document_type"] == "daily_course_record" else "surgery")
        doc.update({key: raw[key] for key in (*_VERSION_FIELDS, "primary_material", "primary_material_scope")})
        doc["doc_key"] = raw["source_version_key"]
        doc.update(display_item(entry, item, value))
        result.append(doc)
    return result


@contextmanager
def live_context(identity, *, allow_unbound_view=False):
    """独立Bundle/目录共用一次RR；旧快照与PDF始终沿原协议。"""
    from .validation_material_source import is_material_copy
    state = material.context()
    if state is not None:
        material.identity_check(state, identity)
    if state is not None or is_material_copy(identity[1], identity[2]):
        yield
        return
    if not enabled():
        from .daily_material_projection import live_context as old_context
        with old_context(identity, allow_unbound_view=allow_unbound_view):
            yield
        return
    from ..database import clinical_connection as clinical
    from .bundles import assembly
    if not clinical.configured():
        raise material.MaterialSnapshotError("primary_material_independent_cdm_required")
    engine = assembly._source_engine("cdm")
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            connection.exec_driver_sql("SET LOCAL statement_timeout=10000")
            state = {"identity": list(identity), "binding": clinical.source_binding(), "schema": "cdm",
                     "engine": engine, "connection": connection, "columns": {}, "tables": {}, "queries": {}}
            capture_into(state, connection, identity)
            with material.recording(state):
                yield
