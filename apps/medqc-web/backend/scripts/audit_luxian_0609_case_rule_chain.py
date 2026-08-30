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


def _source_summary(session: Any) -> dict[str, Any]:
    snapshot = _attr(session, "snapshot")
    observations = list(_attr(snapshot, "observations", ()) or ())
    rows = []
    blocked = False
    for item in observations:
        state = str(_attr(_attr(item, "query_state"), "value", _attr(item, "query_state", "")))
        completeness = str(_attr(_attr(item, "completeness"), "value", _attr(item, "completeness", "")))
        if state in {"unavailable", "error"} or completeness in {"unproven", "truncated"}:
            blocked = True
        rows.append({
            "source_key": str(_attr(item, "source_key", "")),
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
        "blocked": blocked,
    }


def _bundle_summary(bundle: Any) -> dict[str, Any]:
    if not isinstance(bundle, Mapping):
        return {
            "present": False,
            "schema": None,
            "hits": 0,
            "flags": 0,
            "count": 0,
            "table_counts": {},
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
    return {
        "present": True,
        "schema": bundle.get("bundle_schema_version"),
        "hits": len(hits),
        "flags": len(flags),
        "count": sum(int(v) for v in hits.values() if isinstance(v, (int, float)) and not isinstance(v, bool)),
        "table_counts": table_counts,
        "hash": _hash({"schema": bundle.get("bundle_schema_version"), "hits": hits, "flags": flags}),
    }


def _envelope_summary(envelope: Any, rule_id: str) -> tuple[dict[str, Any], bool]:
    if not isinstance(envelope, Mapping) or envelope.get("schema_version") != "lx0609-record-result-envelope-v1":
        return ({"present": False, "status": None, "reason_code": "canonical_envelope_missing", "evidence_count": 0, "hash": _hash(None)}, False)
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
                          git_commit: str | None = None) -> dict[str, Any]:
    """把已读取的三层对象投影为无敏感字段审计产物。"""
    rule_id = str(rule_id).strip().upper()
    source = _source_summary(evidence_session)
    contract = rule_contract if isinstance(rule_contract, Mapping) else {
        "family_key": _attr(rule_contract, "family_key", ""), "rule_version": _attr(rule_contract, "rule_version", "")
    }
    bundle_info = _bundle_summary(bundle)
    envelope_info, envelope_ok = _envelope_summary(envelope, rule_id)
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
    if source["blocked"]:
        status, reason = "blocked", "data_gap"
        stage = "source"
    elif not bundle_info["present"]:
        status, reason = "technical_error", "bundle_missing"
        stage = "bundle"
    elif bundle_count_mismatches:
        status, reason = "technical_error", "bundle_source_count_mismatch"
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
            "bundle_source_count_mismatches": bundle_count_mismatches,
            "count_comparison": "direct_source_key_only",
        },
        "transaction": {"isolation": "REPEATABLE READ", "read_only": True, "scope": "audit-read", "layer_snapshot_consistency": "best_effort"},
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


def _load_envelope(conn: Any, *, schema: str, institute_id: str, patient_id: str, visit_id: str, job_id: str | None) -> Any:
    schema = _safe_schema(schema, field_name="canonical_schema")
    table = f'"{schema}"."luxian_0609_record_result_envelopes"'
    query = sa.text(f"SELECT envelope_json FROM {table} WHERE institute_id=:i AND patient_id=:p AND visit_id=:v" + (" AND job_id=:j" if job_id else "") + " ORDER BY updated_at DESC LIMIT 1")
    params = {"i": institute_id, "p": patient_id, "v": visit_id}
    if job_id:
        params["j"] = job_id
    row = conn.execute(query, params).mappings().first()
    return _json(row["envelope_json"]) if row else None


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
            domain = {"basic_timeliness": "admission", "course_quality": "course", "surgery_anesthesia": "surgery", "consultation_quality": "consult_discussion", "extended_document": "terminal", "exam_lab": "course", "transfusion": "course", "tumor_pathology": "course"}.get(contract.family_key, contract.family_key)
            bundle = load_domain_bundle(execution_domain=domain, institute_id=args.institute_id, patient_id=args.patient_id, visit_id=args.visit_id, schema=bundle_schema)
            envelope = _load_envelope(conn, schema=canonical_schema, institute_id=args.institute_id, patient_id=args.patient_id, visit_id=args.visit_id, job_id=args.job_id)
            report = audit_case_rule_chain(institute_id=args.institute_id, patient_id=args.patient_id, visit_id=args.visit_id, rule_id=args.rule_id, evidence_session=session, rule_contract=contract, bundle=bundle, envelope=envelope)
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
