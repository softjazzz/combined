"""五类材料固定验收：只比较各层，不写库、不重判业务或猜测时间/签名。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .. import dual_source_sync as sync
from ..document_assembly.assembler import extract_document_identity_metadata
from ..document_assembly.signatures import body_physician_signatures


@dataclass(frozen=True)
class MaterialSpec:
    category: str
    table: str
    key: str
    fields: tuple[str, ...]
    domains: tuple[str, ...]


ORDER_TIMES = ("planned_end_datetime", "reviewed_datetime", "carried_datetime", "canceled_datetime")
SPECS = (
    MaterialSpec("transfusion", "bloodtrans_record", "document_id", ("record_content",), ("course",)),
    MaterialSpec("transfusion", "blood_application", "application_id", ("reason_for_blood", "record_content"), ("course",)),
    MaterialSpec("discharge", "discharge_record", "document_id", (
        "admission_condition", "treatment_course", "discharge_order", "record_content",
        "chief_physician_sign_datetime", "v2_schema",
    ), ("terminal",)),
    MaterialSpec("orders", "inpat_drug_order", "order_id", ORDER_TIMES, ("course", "consult_discussion")),
    MaterialSpec("orders", "inpat_nondrug_order", "order_id", ORDER_TIMES, ("course", "consult_discussion")),
    MaterialSpec("pathology", "pathology_exam_report", "pathology_exam_id", ("diagnosis", "eye_findings"), ("course", "surgery")),
    MaterialSpec("signatures", "daily_course_record", "document_id", ("signature_names",), ("course",)),
    MaterialSpec("signatures", "senior_course_record", "document_id", ("signature_names",), ("course",)),
    MaterialSpec("signatures", "postsurg_firstcourse_record", "document_id", ("signature_names",), ("course", "surgery")),
)
TEXT_FIELDS = frozenset({"record_content", "admission_condition", "treatment_course", "discharge_order", "diagnosis", "eye_findings", "reason_for_blood"})


def has_value(field: str, value: Any) -> bool:
    return not sync.blank(value) and not (field in TEXT_FIELDS and isinstance(value, str) and value.strip() in {"[]", "{}", "null"})


def normalized(row: Mapping[str, Any]) -> dict[str, Any]:
    result, _issues = sync.normalize_row(row)
    # 验收也观察源端已有、但同步白名单未覆盖的明确字段，不把漏映射误作源端空值。
    for spec in SPECS:
        for field in spec.fields:
            if field not in result and not sync.blank(row.get(field)):
                result[field] = sync.normalized_value(field, row[field])
    names = {item["name"] for item in extract_document_identity_metadata(dict(row))["signatures"] if item.get("name")}
    for item in row.get("signatures", []) or []:
        if isinstance(item, Mapping) and item.get("name"):
            names.add(str(item["name"]))
    names.update(body_physician_signatures(result.get("record_content") or row.get("content")))
    result["signature_names"] = tuple(sorted(names))
    return result


def same(field: str, expected: Any, actual: Any, *, bundle: bool = False, row: Mapping[str, Any] | None = None) -> bool:
    if field == "signature_names":
        return set(expected).issubset(set(actual or ()))
    if sync.blank(actual):
        if bundle and field in TEXT_FIELDS:
            return "".join(str(expected).split()) in "".join(str((row or {}).get("content") or "").split())
        return False
    try:
        return sync.equivalent(field, expected, actual)
    except (TypeError, ValueError):
        return False


def check_table_chain(*, spec: MaterialSpec, sample: str, case: Mapping[str, str],
                      clinical: sync.SourceSnapshot, homology: sync.SourceSnapshot,
                      local_rows: Sequence[Mapping[str, Any]], source_institutes: Mapping[str, str],
                      bundles: Mapping[str, Sequence[Mapping[str, Any]] | None],
                      rules: Mapping[str, Sequence[Mapping[str, Any]] | None],
                      projections: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """源端零行与源端失败不同；冲突保留待核实，不因匹配其中一侧就消除冲突。"""
    plan = sync.plan_table(spec.table, case, clinical, homology,
                           sync.SourceSnapshot("local", tuple(local_rows)),
                           source_institutes=source_institutes, stable_keys=(spec.key,))
    gaps, conflicts, projection_omissions = [], [], []
    checked = source_values = local_only = 0
    stages = {"local_pg": list(local_rows), **{
        "bundle:" + name: bundles.get(name) for name in ("final", *spec.domains)
    }, **{"rule:" + name: rules.get(name) for name in ("native", "snapshot")}}
    indexes = {}
    for stage, rows in stages.items():
        if rows is None:
            indexes[stage] = None
            continue
        indexed = {}
        for raw in rows:
            if stage.startswith("bundle:") and str(raw.get("source_table") or raw.get("document_type") or raw.get("doc_type") or "") != spec.table:
                continue
            row = normalized(raw)
            identity = str(row.get(spec.key) or (raw.get("document_id") if stage.startswith("bundle:") else "") or "")
            indexed.setdefault(identity, []).append((raw, row))
        indexes[stage] = indexed
    for index, candidate in enumerate(plan.candidates, 1):
        remote = {key: value for key, value in candidate.variants.items() if key != "local"}
        local_only += int(not remote)
        expected = dict(candidate.values)
        extra_conflicts = set()
        for field in spec.fields:
            alternatives = [normalized(candidate.raw_variants[source]).get(field) for source in remote]
            alternatives = [value for value in alternatives if not sync.blank(value)]
            if alternatives and field not in expected:
                expected[field] = alternatives[0]
                if any(not same(field, alternatives[0], value) for value in alternatives[1:]):
                    extra_conflicts.add(field)
        expected_names = set()
        for source in remote:
            expected_names.update(normalized(candidate.raw_variants[source])["signature_names"])
        if spec.category == "signatures":
            expected["signature_names"] = tuple(sorted(expected_names))
        # 本验收核对指定材料字段，不把源端本就没有签名/时间的行误报成该字段同步丢失。
        if not any(has_value(field, expected.get(field)) for field in spec.fields):
            continue
        key_value = candidate.key[0]
        # 双源正文冲突是显式待核实项，不自动拼接或二选一覆盖。
        relevant_conflicts = set(spec.fields).intersection(candidate.conflicts) | extra_conflicts
        conflicts.extend({"record_index": index, "field": field} for field in sorted(relevant_conflicts))
        for stage, indexed in indexes.items():
            if indexed is None:
                gaps.append({"record_index": index, "stage": stage, "field": "*", "reason": "layer_unavailable"})
                continue
            matches = indexed.get(key_value, [])
            if len(matches) != 1:
                if not matches and stage.startswith("bundle:"):
                    projection = (projections or {}).get(stage[7:]) or {}
                    per_source = projection.get("per_source") or {}
                    declared = (per_source.get(spec.table) or {}).get("has_more") is True or spec.table not in per_source
                    actual_rule_rows_present = all(len((indexes.get("rule:" + name) or {}).get(key_value, [])) == 1 for name in ("native", "snapshot"))
                    if projection.get("is_evidence_source") is False and declared and actual_rule_rows_present:
                        projection_omissions.append({"record_index": index, "stage": stage, "reason": "declared_display_projection_rule_rows_present"})
                        continue
                gaps.append({"record_index": index, "stage": stage, "field": "*", "reason": "record_missing" if not matches else "duplicate_record"})
                continue
            raw, row = matches[0]
            for field in spec.fields:
                value = expected.get(field)
                if not has_value(field, value):
                    continue
                if stage == "local_pg":
                    source_values += int(any(not sync.blank(values.get(field)) for values in remote.values()) or (field == "signature_names" and bool(expected_names)))
                checked += 1
                if not same(field, value, row.get(field), bundle=stage.startswith("bundle:"), row=raw):
                    gaps.append({"record_index": index, "stage": stage, "field": field, "reason": "value_missing_or_changed"})
    return {
        "sample": sample, "category": spec.category, "table": spec.table,
        "source_status": plan.source_status, "source_counts": plan.source_counts,
        "records": len(plan.candidates), "local_only_records": local_only,
        "checked_values": checked, "source_nonempty_fields": source_values,
        "gaps": gaps, "conflicts": conflicts, "issues": plan.issues,
        "display_projection_omissions": projection_omissions,
        "quarantined_rows": plan.quarantined_rows,
        "passed": plan.complete and not (gaps or conflicts or plan.issues or plan.quarantined_rows),
    }


def summarize_checks(checks: Sequence[Mapping[str, Any]], *, cases: int) -> dict[str, Any]:
    categories = {}
    for category in dict.fromkeys(spec.category for spec in SPECS):
        rows = [row for row in checks if row["category"] == category]
        values = sum(int(row["source_nonempty_fields"]) for row in rows)
        categories[category] = {"passed": bool(rows) and values > 0 and all(row["passed"] for row in rows),
                                "source_nonempty_fields": values,
                                "gap_count": sum(len(row["gaps"]) for row in rows),
                                "conflict_count": sum(len(row["conflicts"]) for row in rows),
                                "display_projection_omissions": sum(len(row.get("display_projection_omissions", [])) for row in rows)}
    return {"schema_version": "medqc-p0-material-chain-v1", "cases": cases,
            "passed": cases > 0 and len(checks) == cases * len(SPECS) and all(row["passed"] for row in categories.values()),
            "categories": categories, "database_writes": 0, "model_calls": 0, "qc_tasks_started": 0}
