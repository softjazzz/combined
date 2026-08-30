"""LX0609 单病例单规则只读分层对账（不执行质控、不写库）。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import sqlalchemy as sa

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

_SCHEMA_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def resolve_schema_defaults(schema_mode: str | None) -> dict[str, str]:
    """Resolve the three physical schemas used by the runtime.

    In split mode source tables live in ``cdm``.  The current bundle refresh
    contract still persists domain bundles in ``public`` (the function's
    explicit default), while Canonical envelopes use the ``qc`` draft schema.
    Keeping this mapping here prevents a read-only audit from silently
    reporting an empty ``public`` source or an unavailable bundle table.
    """

    if str(schema_mode or "").strip().lower() == "split":
        return {"source": "cdm", "bundle": "public", "canonical": "qc"}
    return {"source": "public", "bundle": "public", "canonical": "public"}


def _safe_schema(value: str, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not _SCHEMA_PATTERN.fullmatch(normalized):
        raise ValueError(f"invalid {field_name}")
    return normalized


def _json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return None
    return value


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _case_ref(institute_id: str, patient_id: str, visit_id: str) -> str:
    return "sha256:" + _hash({"institute_id": institute_id, "patient_id": patient_id, "visit_id": visit_id})


def _attr(value: Any, name: str, default: Any = None) -> Any:
    return getattr(value, name, default)


def _derived_source_marker_keys(rule_id: str) -> tuple[str, ...]:
    """返回来源注册表中仅用于标识派生投影的逻辑键。

    Snapshot provider 会为这类键留下 ``UNAVAILABLE`` 标记，但实际执行器
    读取的是其受控物理/派生父来源。审计必须保留标记，却不能把它当成查询
    能力缺失；真正的父来源缺失仍由 ``expected_source_keys`` 校验。
    """

    try:
        from app.services.luxian_0609.source_registry import (
            resolve_luxian_0609_rule_sources,
        )

        entries = resolve_luxian_0609_rule_sources((rule_id.upper(),)).get(
            rule_id.upper(), ()
        )
        return tuple(
            sorted(
                {
                    str(entry.document_type)
                    for entry in entries
                    if str(getattr(getattr(entry, "access_mode", None), "value", ""))
                    == "derived_projection_v1"
                }
            )
        )
    except Exception:
        return ()


def _source_summary(
    session: Any,
    *,
    ignored_source_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    snapshot = _attr(session, "snapshot")
    observations = list(_attr(snapshot, "observations", ()) or ())
    rows = []
    blocked = False
    blocked_keys: set[str] = set()
    ignored_keys = {str(key) for key in ignored_source_keys}
    observed_ignored_keys: set[str] = set()
    for item in observations:
        source_key = str(_attr(item, "source_key", ""))
        state = str(_attr(_attr(item, "query_state"), "value", _attr(item, "query_state", "")))
        completeness = str(_attr(_attr(item, "completeness"), "value", _attr(item, "completeness", "")))
        is_blocking = (
            source_key not in ignored_keys
            and (
                state in {"unavailable", "error"}
                or completeness in {"unproven", "truncated"}
            )
        )
        if is_blocking:
            blocked = True
            blocked_keys.add(source_key)
        elif source_key in ignored_keys:
            observed_ignored_keys.add(source_key)
        rows.append({
            "source_key": source_key,
            "query_state": state,
            "completeness": completeness,
            "record_count": _attr(item, "record_count"),
            "query_version": str(_attr(item, "query_version", "")),
            "snapshot_ref": str(_attr(item, "snapshot_ref", "")),
        })
    rows.sort(key=lambda x: x["source_key"])
    materials = _attr(session, "materials")
    summary_fn = getattr(materials, "safe_summary", None)
    try:
        material_count = summary_fn() if callable(summary_fn) else {}
    except Exception:
        material_count = {}
    return {
        "observations": rows,
        "material_count": material_count.get("source_count", 0) if isinstance(material_count, Mapping) else 0,
        "hash": _hash({"observations": rows, "snapshot_hash": _attr(snapshot, "snapshot_hash", "")}),
        "snapshot_hash": _attr(snapshot, "snapshot_hash", ""),
        "created_at": str(_attr(snapshot, "created_at", "")),
        "blocked_keys": sorted(blocked_keys),
        "ignored_source_keys": sorted(observed_ignored_keys),
        # 没有任何 observation 不是“没有病例资料”，而是本次读取链没有
        # 形成可审计的来源快照；必须阻断后续 ready 判断。
        "blocked": blocked or not rows,
        "empty_observations": not rows,
    }


def _bundle_summary(bundle: Any) -> dict[str, Any]:
    if not isinstance(bundle, Mapping):
        return {
            "present": False,
            "schema": None,
            "hits": 0,
            "flags": 0,
            "count": 0,
            "hit_keys": [],
            "coverage_keys": [],
            "table_counts": {},
            "domains": [],
            "missing_domains": [],
            "coverage_conflicts": [],
            "hash": _hash(None),
        }
    hits = _json(bundle.get("document_hits")) or {}
    flags = _json(bundle.get("data_quality_flags")) or []
    context = _json(bundle.get("structured_context")) or {}
    coverage = context.get("source_table_coverage") if isinstance(context, Mapping) else {}
    if not isinstance(hits, Mapping):
        hits = {}
    if not isinstance(flags, list):
        flags = []
    if not isinstance(coverage, Mapping):
        coverage = {}
    table_counts = {
        str(table): int(value.get("row_count"))
        for table, value in coverage.items()
        if isinstance(value, Mapping)
        and isinstance(value.get("row_count"), (int, float))
        and not isinstance(value.get("row_count"), bool)
    }
    audit_domains = context.get("audit_domains", ()) if isinstance(context, Mapping) else ()
    coverage_conflicts = (
        context.get("audit_coverage_conflicts", ())
        if isinstance(context, Mapping)
        else ()
    )
    missing_domains = (
        context.get("audit_missing_domains", ())
        if isinstance(context, Mapping)
        else ()
    )
    return {
        "present": True,
        "schema": bundle.get("bundle_schema_version"),
        "domains": list(
            audit_domains
            if isinstance(audit_domains, (list, tuple))
            else ()
        ),
        "missing_domains": sorted(
            str(item) for item in missing_domains
        )
        if isinstance(missing_domains, (list, tuple, set))
        else [],
        "coverage_conflicts": sorted(
            str(item) for item in coverage_conflicts
        )
        if isinstance(coverage_conflicts, (list, tuple, set))
        else [],
        "hits": len(hits),
        "flags": len(flags),
        "count": sum(int(v) for v in hits.values() if isinstance(v, (int, float)) and not isinstance(v, bool)),
        "hit_keys": sorted(str(key) for key in hits),
        "coverage_keys": sorted(table_counts),
        "table_counts": table_counts,
        "hash": _hash(
            {
                "schema": bundle.get("bundle_schema_version"),
                "hits": hits,
                "flags": flags,
                "coverage": table_counts,
                "domains": audit_domains,
                "missing_domains": missing_domains,
                "coverage_conflicts": coverage_conflicts,
            }
        ),
    }


def merge_domain_bundles(bundles: Mapping[str, Any]) -> dict[str, Any] | None:
    """合并本次规则涉及的多个域 Bundle，只合并覆盖摘要，不改变业务证据。

    同一源表可能同时投影到 course/consult 等域，因此重复表的行数取最大值，
    不把同一批记录相加；没有任何可读取的域 Bundle 时返回 ``None``。
    """

    requested_domains = {
        str(domain)
        for domain in (bundles or {})
        if str(domain).strip()
    }
    present: dict[str, Mapping[str, Any]] = {
        str(domain): bundle
        for domain, bundle in (bundles or {}).items()
        if isinstance(bundle, Mapping)
    }
    if not present:
        return None
    merged_hits: dict[str, Any] = {}
    merged_flags: set[str] = set()
    merged_coverage: dict[str, dict[str, Any]] = {}
    schemas: set[str] = set()
    coverage_conflicts: set[str] = set()
    missing_domains = sorted(requested_domains - set(present))
    for domain, bundle in sorted(present.items()):
        schema = str(bundle.get("bundle_schema_version") or "")
        if schema:
            schemas.add(schema)
        hits = _json(bundle.get("document_hits")) or {}
        if isinstance(hits, Mapping):
            for key, value in hits.items():
                normalized_key = str(key)
                merged_hits[normalized_key] = bool(merged_hits.get(normalized_key)) or bool(value)
        flags = _json(bundle.get("data_quality_flags")) or []
        if isinstance(flags, list):
            merged_flags.update(str(flag) for flag in flags)
        context = _json(bundle.get("structured_context")) or {}
        coverage = context.get("source_table_coverage") if isinstance(context, Mapping) else {}
        if not isinstance(coverage, Mapping):
            continue
        for table, value in coverage.items():
            if not isinstance(value, Mapping):
                continue
            row_count = value.get("row_count")
            if not isinstance(row_count, (int, float)) or isinstance(row_count, bool):
                continue
            normalized_table = str(table)
            current = merged_coverage.get(normalized_table)
            normalized_count = int(row_count)
            if current is not None and int(current["row_count"]) != normalized_count:
                coverage_conflicts.add(normalized_table)
            if current is None or normalized_count > int(current["row_count"]):
                merged_coverage[normalized_table] = {
                    "row_count": normalized_count,
                    "hit": bool(value.get("hit")),
                }
    schema = next(iter(schemas)) if len(schemas) == 1 else "mixed"
    return {
        "bundle_schema_version": schema,
        "document_hits": merged_hits,
        "data_quality_flags": sorted(merged_flags),
        "structured_context": {
            "source_table_coverage": merged_coverage,
            "audit_domains": sorted(present),
            "audit_missing_domains": missing_domains,
            "audit_coverage_conflicts": sorted(coverage_conflicts),
        },
    }


def _resolve_bundle_domain_mapping(
    rule_contract: Any,
) -> tuple[tuple[str, ...], tuple[str, ...], str | None]:
    """解析适用文书到 Bundle 域，并显式报告无法映射的文书。

    返回 ``(domains, unmapped_documents, reason_code)``。没有声明适用文书
    的兼容测试契约不参与域完整性校验；真实 LX0609 契约必须至少映射到一个
    已注册域，且不能静默忽略其中任意未知文书。
    """

    documents = getattr(rule_contract, "applicable_documents", ())
    if isinstance(rule_contract, Mapping):
        documents = rule_contract.get("applicable_documents") or ()
    normalized_documents = tuple(
        dict.fromkeys(
            str(item).strip()
            for item in documents
            if str(item).strip()
        )
    )
    if not normalized_documents:
        # 旧的 family-only 调用没有足够信息判断 Bundle 域，保持兼容；
        # 真实规则契约由规则加载器保证 applicable_documents 非空。
        return (), (), None
    try:
        from app.services.bundles.assembly import _DOMAIN_DOC_PRIORITY
        from app.services.luxian_0609.source_registry import (
            load_luxian_0609_source_registry,
        )
    except Exception:
        return (), normalized_documents, "domain_mapping_unavailable"

    registry = load_luxian_0609_source_registry()
    domains: list[str] = []
    mapped_documents: set[str] = set()
    for domain, priority in _DOMAIN_DOC_PRIORITY.items():
        matched = set(normalized_documents).intersection(priority)
        if matched:
            domains.append(str(domain))
            mapped_documents.update(matched)
    # 关注摘要、medical_order 等派生文书可能不在 Bundle 域的直接优先级
    # 中；只要其注册表明确声明了父来源，就按父来源反查域。派生文书本身
    # 是否生成仍由 Bundle 的 projection 元数据另行审计，不伪造为物理覆盖。
    unresolved_documents: list[str] = []
    for document in normalized_documents:
        if document in mapped_documents:
            continue
        entry = registry.get(document)
        parent_keys = tuple(getattr(entry, "derived_from_source_keys", ()) or ())
        parent_domains = [
            str(domain)
            for domain, priority in _DOMAIN_DOC_PRIORITY.items()
            if set(parent_keys).intersection(priority)
        ]
        if parent_domains:
            domains.extend(parent_domains)
            mapped_documents.add(document)
            continue
        unresolved_documents.append(document)
    domains = list(dict.fromkeys(domains))
    unmapped_documents = tuple(unresolved_documents)
    if not domains or unmapped_documents:
        return (
            tuple(domains),
            unmapped_documents or normalized_documents,
            "domain_mapping_unavailable",
        )
    return tuple(domains), (), None


def _bundle_domains_for_rule(rule_contract: Any) -> tuple[str, ...]:
    """按规则适用文书反查 Bundle 域；映射不完整时返回空元组。"""

    domains, _unmapped_documents, reason_code = _resolve_bundle_domain_mapping(
        rule_contract
    )
    return domains if reason_code is None else ()


def _expected_source_keys(rule_id: str, rule_contract: Any) -> tuple[str, ...]:
    """返回来源快照必须出现的物理键，避免漏读被误当成空资料。"""

    # 只有带有适用文书声明的规则契约才可以做来源完整性断言；测试或
    # 兼容调用传入的 family-only 映射不能凭 rule_id 猜测来源范围。
    if isinstance(rule_contract, Mapping):
        explicit = rule_contract.get("source_keys")
        if isinstance(explicit, (list, tuple, set)):
            return tuple(sorted({str(item).strip() for item in explicit if str(item).strip()}))
        if not rule_contract.get("applicable_documents"):
            return ()
    try:
        from app.services.luxian_0609.source_registry import (
            resolve_luxian_0609_controlled_fact_source_keys,
            resolve_luxian_0609_decision_support_source_keys,
            resolve_luxian_0609_rule_sources,
        )

        entries = resolve_luxian_0609_rule_sources((rule_id.upper(),)).get(rule_id.upper(), ())
        expected: set[str] = set()
        for entry in entries:
            # 派生逻辑文书只会留下一个不可查询的 marker；它的真实输入由
            # decision-support/typed source keys 声明，不能把 marker 本身当
            # 作必须可读取的来源。
            access_mode = str(
                getattr(getattr(entry, "access_mode", None), "value", "")
            )
            if access_mode == "derived_projection_v1":
                continue
            expected.update(entry.physical_source_keys or (entry.document_type,))
        for source_key in (
            *resolve_luxian_0609_decision_support_source_keys((rule_id.upper(),)),
            *resolve_luxian_0609_controlled_fact_source_keys((rule_id.upper(),)),
        ):
            # Horizon is a derived fact created in the request and is not a
            # database observation.
            if not str(source_key).startswith("evaluation_context."):
                expected.add(str(source_key).strip())
        return tuple(sorted(key for key in expected if key))
    except Exception:
        documents = getattr(rule_contract, "applicable_documents", ())
        if isinstance(rule_contract, Mapping):
            documents = rule_contract.get("applicable_documents") or ()
        return tuple(sorted({str(item).strip() for item in documents if str(item).strip()}))


def _expected_bundle_keys(rule_id: str, rule_contract: Any) -> tuple[str, ...]:
    """返回 Bundle 应覆盖的文书类型，而不是把物理表别名直接当作 Bundle key。"""

    if isinstance(rule_contract, Mapping):
        explicit = rule_contract.get("bundle_source_keys") or rule_contract.get(
            "physical_source_keys"
        )
        if isinstance(explicit, (list, tuple, set)):
            return tuple(sorted({str(item).strip() for item in explicit if str(item).strip()}))
        applicable = rule_contract.get("applicable_documents")
        if isinstance(applicable, (list, tuple, set)):
            try:
                from app.services.luxian_0609.source_registry import (
                    load_luxian_0609_source_registry,
                )

                registry = load_luxian_0609_source_registry()
                expected: set[str] = set()
                for item in applicable:
                    document = str(item).strip()
                    if not document:
                        continue
                    entry = registry.get(document)
                    if entry is not None and str(
                        getattr(getattr(entry, "access_mode", None), "value", "")
                    ) == "derived_projection_v1":
                        expected.update(
                            str(key).strip()
                            for key in entry.derived_from_source_keys
                            if str(key).strip()
                        )
                    else:
                        expected.add(document)
                return tuple(sorted(expected))
            except Exception:
                return tuple(
                    sorted(
                        {
                            str(item).strip()
                            for item in applicable
                            if str(item).strip()
                        }
                    )
                )
    try:
        from app.services.luxian_0609.source_registry import (
            load_luxian_0609_source_registry,
            resolve_luxian_0609_rule_sources,
        )

        entries = resolve_luxian_0609_rule_sources((rule_id.upper(),)).get(rule_id.upper(), ())
        expected: set[str] = set()
        for entry in entries:
            access_mode = str(
                getattr(getattr(entry, "access_mode", None), "value", "")
            )
            if access_mode == "derived_projection_v1":
                # Bundle 覆盖摘要记录物理父来源；关注摘要/medical_order
                # 等派生投影是否生成是另一项展示审计，不在这里伪造覆盖。
                expected.update(str(key).strip() for key in entry.derived_from_source_keys)
            else:
                expected.add(str(entry.document_type).strip())
        return tuple(sorted(key for key in expected if key))
    except Exception:
        return ()


def _envelope_summary(
    envelope: Any,
    rule_id: str,
    *,
    expected_job_id: str | None = None,
    expected_record_id: str | None = None,
) -> tuple[dict[str, Any], bool]:
    if not isinstance(envelope, Mapping) or envelope.get("schema_version") != "lx0609-record-result-envelope-v1":
        return ({"present": False, "status": None, "reason_code": "canonical_envelope_missing", "evidence_count": 0, "hash": _hash(None)}, False)
    if expected_job_id is not None and str(envelope.get("job_id") or "") != str(expected_job_id):
        return ({"present": False, "status": None, "reason_code": "canonical_envelope_identity_mismatch", "evidence_count": 0, "hash": _hash(envelope.get("job_id"))}, False)
    if expected_record_id is not None and str(envelope.get("record_id") or "") != str(expected_record_id):
        return ({"present": False, "status": None, "reason_code": "canonical_envelope_identity_mismatch", "evidence_count": 0, "hash": _hash(envelope.get("record_id"))}, False)
    items = envelope.get("items")
    if not isinstance(items, list):
        return ({"present": False, "status": None, "reason_code": "canonical_result_envelope_invalid", "evidence_count": 0, "hash": _hash(envelope.get("schema_version"))}, False)
    try:
        from app.services.qc_workspace.canonical_result_store import canonical_envelope_items_are_consistent
        consistent = canonical_envelope_items_are_consistent(items)
    except Exception:
        consistent = False
    selected = [item for item in items if isinstance(item, Mapping) and str(item.get("rule_id") or item.get("rule_code") or "").upper() == rule_id.upper()]
    if not consistent:
        return ({"present": False, "status": None, "reason_code": "canonical_result_envelope_invalid", "evidence_count": 0, "hash": _hash(items)}, False)
    if len(selected) != 1:
        return ({"present": False, "status": None, "reason_code": "canonical_result_envelope_invalid", "evidence_count": 0, "hash": _hash(items)}, False)
    item = selected[0]
    status = str(item.get("status") or item.get("result_status") or "")
    reason = str(item.get("reason_code") or "reason_unavailable")
    evidence = item.get("evidence") if isinstance(item.get("evidence"), list) else []
    safe_refs = []
    try:
        from app.services.custom_qc_workspace_service import build_customer_safe_source_ref
        for evidence_item in evidence:
            if isinstance(evidence_item, Mapping):
                material = evidence_item.get("source_ref") or evidence_item.get("document_ref") or evidence_item.get("source_document_id")
                if material:
                    safe_refs.append(build_customer_safe_source_ref(material))
    except Exception:
        safe_refs = []
    safe_item = {"rule_id": rule_id.upper(), "status": status, "reason_code": reason, "evidence_count": len(evidence), "evidence_refs": sorted(safe_refs)}
    return ({"present": True, "status": status, "reason_code": reason, "evidence_count": len(evidence), "hash": _hash(safe_item)}, True)


def audit_case_rule_chain(*, institute_id: str, patient_id: str, visit_id: str, rule_id: str,
                          evidence_session: Any, rule_contract: Any, bundle: Any,
                          envelope: Any, api_summary: Mapping[str, Any] | None = None,
                          git_commit: str | None = None,
                          expected_job_id: str | None = None,
                          expected_record_id: str | None = None) -> dict[str, Any]:
    """把已读取的三层对象投影为无敏感字段审计产物。"""
    rule_id = str(rule_id).strip().upper()
    contract = rule_contract if isinstance(rule_contract, Mapping) else {
        "family_key": _attr(rule_contract, "family_key", ""), "rule_version": _attr(rule_contract, "rule_version", "")
    }
    expected_source_keys = _expected_source_keys(rule_id, rule_contract)
    ignored_source_keys = tuple(
        key
        for key in _derived_source_marker_keys(rule_id)
        if key not in set(expected_source_keys)
    )
    source = _source_summary(
        evidence_session,
        ignored_source_keys=ignored_source_keys,
    )
    bundle_domains, unmapped_bundle_documents, domain_mapping_reason = (
        _resolve_bundle_domain_mapping(rule_contract)
    )
    bundle_info = _bundle_summary(bundle)
    envelope_info, envelope_ok = _envelope_summary(
        envelope,
        rule_id,
        expected_job_id=expected_job_id,
        expected_record_id=expected_record_id,
    )
    expected_bundle_keys = _expected_bundle_keys(rule_id, rule_contract)
    observed_source_keys = {
        str(item.get("source_key"))
        for item in source.get("observations", ())
        if isinstance(item, Mapping)
    }
    missing_source_keys = [
        key for key in expected_source_keys if key not in observed_source_keys
    ]
    # ``document_hits`` 只表示该域的逻辑命中（包含 false 键），不能证明
    # 源表覆盖元数据已生成；长期验收只认可 source_table_coverage。
    bundle_keys = set(bundle_info.get("coverage_keys", ()))
    missing_bundle_keys = [key for key in expected_bundle_keys if key not in bundle_keys]
    source_count_by_key = {
        str(item.get("source_key")): item.get("record_count")
        for item in source.get("observations", [])
        if isinstance(item, Mapping)
        and isinstance(item.get("record_count"), (int, float))
        and not isinstance(item.get("record_count"), bool)
    }
    bundle_count_mismatches = [
        {
            "source_key": source_key,
            "source_count": int(record_count),
            "bundle_count": int(bundle_info["table_counts"][source_key]),
        }
        for source_key, record_count in source_count_by_key.items()
        if source_key in bundle_info.get("table_counts", {})
        and int(record_count) != int(bundle_info["table_counts"][source_key])
    ]
    if domain_mapping_reason:
        # 未知/未注册的 applicable_documents 不能退化成 family_key，也不能
        # 继续读取一个猜出来的 Bundle 后声称链路已核对。
        status, reason = "technical_error", domain_mapping_reason
        stage = "bundle"
    elif source.get("empty_observations"):
        status, reason = "blocked", "source_gap"
        stage = "source"
    elif source["blocked"]:
        status, reason = "blocked", "data_gap"
        stage = "source"
    elif missing_source_keys:
        status, reason = "blocked", "source_observation_missing"
        stage = "source"
    elif not bundle_info["present"]:
        status, reason = "technical_error", "bundle_missing"
        stage = "bundle"
    elif bundle_info.get("missing_domains"):
        status, reason = "technical_error", "bundle_domain_missing"
        stage = "bundle"
    elif bundle_info.get("coverage_conflicts"):
        status, reason = "technical_error", "bundle_coverage_conflict"
        stage = "bundle"
    elif bundle_count_mismatches:
        status, reason = "technical_error", "bundle_source_count_mismatch"
        stage = "bundle"
    elif missing_bundle_keys:
        status, reason = "technical_error", "bundle_source_coverage_missing"
        stage = "bundle"
    elif not envelope_ok:
        status, reason = "technical_error", envelope_info["reason_code"]
        stage = "canonical_envelope"
    else:
        status, reason, stage = "ready", "ready", "canonical_envelope"
    report = {
        "artifact_schema_version": "lx0609-case-rule-chain-audit-v1",
        "git_commit": git_commit or _git_commit(),
        "rule": {"rule_id": rule_id, "family": contract.get("family_key", ""), "version": contract.get("rule_version", "")},
        "case_ref": _case_ref(institute_id, patient_id, visit_id),
        "source": {
            "storage": "local_cdm",
            **{k: v for k, v in source.items() if k != "blocked"},
        },
        "bundle": bundle_info,
        "canonical": envelope_info,
        "checks": {"status": status, "reason_code": reason, "failure_stage": stage},
        "cross_layer": {
            "bundle_domains": list(bundle_domains),
            "unmapped_bundle_documents": list(unmapped_bundle_documents),
            "domain_mapping_reason_code": domain_mapping_reason,
            "ignored_source_keys": list(source.get("ignored_source_keys", ())),
            "missing_source_keys": missing_source_keys,
            "bundle_source_count_mismatches": bundle_count_mismatches,
            "expected_bundle_keys": list(expected_bundle_keys),
            "missing_bundle_keys": missing_bundle_keys,
            "count_comparison": "direct_source_key_only",
        },
        "transaction": {"isolation": "REPEATABLE READ", "read_only": True, "scope": "audit-read", "layer_snapshot_consistency": "best_effort"},
        "verification_scope": {
            "source_cdm": "verified_by_snapshot_reader",
            "bundle": "verified_by_bundle_row",
            "canonical": "verified_by_envelope_row",
            "api": "not_verified_by_cli",
            "ui": "not_verified_by_cli",
        },
    }
    if api_summary is not None:
        report["api"] = {"status": str(api_summary.get("status", "")), "count": int(api_summary.get("count", 0) or 0), "ready": bool(api_summary.get("ready", False))}
        if (not report["api"]["ready"] or report["api"]["status"] != "ready") and status == "ready":
            report["checks"] = {"status": "blocked", "reason_code": "api_gap", "failure_stage": "api"}
    return report


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=BACKEND_ROOT.parent, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def _load_envelope_record(
    conn: Any,
    *,
    schema: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    job_id: str | None,
) -> tuple[Any, Mapping[str, Any] | None]:
    schema = _safe_schema(schema, field_name="canonical_schema")
    table = f'"{schema}"."luxian_0609_record_result_envelopes"'
    query = sa.text(
        f"SELECT envelope_json, job_id, root_job_id, record_id, institute_id, patient_id, visit_id, "
        f"rule_set_key, rule_set_version FROM {table} "
        "WHERE institute_id=:i AND patient_id=:p AND visit_id=:v"
        + (" AND job_id=:j" if job_id else "")
        + " ORDER BY updated_at DESC LIMIT 1"
    )
    params = {"i": institute_id, "p": patient_id, "v": visit_id}
    if job_id:
        params["j"] = job_id
    row = conn.execute(query, params).mappings().first()
    if not row:
        return None, None
    return _json(row["envelope_json"]), dict(row)


def _load_envelope(
    conn: Any,
    *,
    schema: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    job_id: str | None,
) -> Any:
    """兼容旧调用方；新入口同时读取 Canonical 行身份。"""

    envelope, _ = _load_envelope_record(
        conn,
        schema=schema,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        job_id=job_id,
    )
    return envelope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("institute-id", "patient-id", "visit-id", "rule-id"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--job-id", required=True)
    # Resolve the source schema after importing the application's runtime
    # settings.  A hard-coded ``public`` default is wrong in split mode.
    parser.add_argument("--source-schema")
    parser.add_argument("--bundle-schema")
    parser.add_argument("--canonical-schema")
    parser.add_argument("--created-at")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        from app.database.connection import DB_SCHEMA_MODE, engine
        from app.services.bundles.assembly import load_domain_bundle
        from app.services.bundles.assembly import _default_source_schema
        from app.services.custom_qc_workspace_service import _draft_schema
        from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
        from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
        if engine is None:
            raise RuntimeError("DATABASE_URL is not configured")
        contract = next((c for c in load_luxian_0609_rule_contracts() if c.rule_id == args.rule_id.upper()), None)
        if contract is None:
            raise ValueError("unknown rule_id")
        defaults = resolve_schema_defaults(DB_SCHEMA_MODE)
        # Use the application's authoritative schema helpers.  The explicit
        # mapping above remains a safe fallback for environments that do not
        # expose the private helper (e.g. a copied customer script).
        source_schema = args.source_schema or _default_source_schema() or defaults["source"]
        draft_schema = _draft_schema() or defaults["canonical"]
        # Domain bundles retain the explicit ``public`` default in the
        # refresh/assembly contract; only Canonical envelopes follow the
        # split-mode draft schema.
        bundle_schema = args.bundle_schema or defaults["bundle"]
        canonical_schema = args.canonical_schema or draft_schema
        source_schema = _safe_schema(source_schema, field_name="source_schema")
        bundle_schema = _safe_schema(bundle_schema, field_name="bundle_schema")
        canonical_schema = _safe_schema(canonical_schema, field_name="canonical_schema")
        with engine.connect() as conn:
            conn.execute(sa.text("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            created_at = args.created_at or datetime.now(timezone.utc).isoformat()
            session = build_luxian_0609_evidence_read_session(selected_rule_ids=(args.rule_id.upper(),), institute_id=args.institute_id, patient_id=args.patient_id, visit_id=args.visit_id, source_schema=source_schema, created_at=created_at)
            domains, _unmapped_documents, _domain_mapping_reason = (
                _resolve_bundle_domain_mapping(contract)
            )
            domain_bundles: dict[str, Any] = {}
            if _domain_mapping_reason is None:
                for domain in domains:
                    try:
                        domain_bundles[domain] = load_domain_bundle(
                            execution_domain=domain,
                            institute_id=args.institute_id,
                            patient_id=args.patient_id,
                            visit_id=args.visit_id,
                            schema=bundle_schema,
                        )
                    except Exception:
                        # 让报告明确显示 Bundle 不可读，而不是把底层 SQL 细节写入日志。
                        domain_bundles[domain] = None
            bundle = merge_domain_bundles(domain_bundles)
            envelope, envelope_row = _load_envelope_record(
                conn,
                schema=canonical_schema,
                institute_id=args.institute_id,
                patient_id=args.patient_id,
                visit_id=args.visit_id,
                job_id=args.job_id,
            )
            expected_record_id = (
                str(envelope_row.get("record_id"))
                if envelope_row is not None
                else None
            )
            report = audit_case_rule_chain(
                institute_id=args.institute_id,
                patient_id=args.patient_id,
                visit_id=args.visit_id,
                rule_id=args.rule_id,
                evidence_session=session,
                rule_contract=contract,
                bundle=bundle,
                envelope=envelope,
                expected_job_id=args.job_id,
                expected_record_id=expected_record_id,
            )
            conn.rollback()
        text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0 if report["checks"]["status"] in {"ready", "blocked"} else 2
    except Exception as exc:
        # 不把 SQL 参数、病例坐标或底层连接串写入审计日志。
        print(f"audit failed: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
