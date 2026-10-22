"""双源同步的纯内存规划器；无数据库、写入、模型或运行配置副作用。

候选记录与原始变体保存在内存，report 仅返回匿名元数据。
候选不能直接送入旧的整表替换入口；正式写入由独立的保守写入器验证。
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any


HOSPITAL_TZ = timezone(timedelta(hours=8))
SOURCES = ("clinical_data", "homology", "local")
DOC_TABLES = (
    "admission_record", "first_course_record", "daily_course_record", "senior_course_record",
    "consultation_record", "discharge_record", "death_record", "bloodtrans_record",
    "summary_record", "handoff_record", "handover_record", "diffcase_discussion_record",
    "surgery_record", "postsurg_firstcourse_record", "rescue_record", "transfer_in_record",
    "transfer_out_record",
)
TABLE_KEYS = {
    **{name: ("document_id",) for name in DOC_TABLES},
    "inpat_drug_order": ("order_id",), "inpat_nondrug_order": ("order_id",),
    "pathology_exam_report": ("pathology_exam_id",),
    "labtest_master": ("test_id",), "labtest_item": ("test_id", "test_item_id"),
    "labtest_item_report": ("test_id", "print_order_id"),
}
IDENTITY_FIELDS = ("institute_id", "patient_id", "visit_id")
ALIASES = {
    "document_id": ("document_id", "documentid", "sys_index_id", "id"),
    "order_id": ("order_id",), "pathology_exam_id": ("pathology_exam_id",),
    "test_id": ("test_id",), "test_item_id": ("test_item_id", "item_id"),
    "print_order_id": ("print_order_id",), "pathology_id": ("pathology_id",),
    "record_content": ("record_content", "recordcontent"),
    "v2_schema": ("v2_schema",),
    "document_title": ("document_title", "documenttitle", "title", "ward_round_type"),
    "document_status": ("document_status", "documentstatus"),
    "record_status": ("record_status",), "report_status": ("report_status",),
    "is_deleted": ("is_deleted", "is_delete"),
    "record_datetime": ("record_datetime", "record_time", "recorddatetime"),
    "submit_datetime": ("submit_datetime", "submit_time", "submitdatetime"),
    "report_datetime": ("report_datetime", "report_time"),
    "admission_datetime": ("admission_datetime", "admission_time"),
    "discharge_datetime": ("discharge_datetime", "discharge_time"),
    "death_datetime": ("death_datetime", "death_time"),
    "prescribed_datetime": ("prescribed_datetime", "prescribed_time"),
    "planned_start_datetime": ("planned_start_datetime", "planned_start_time"),
    "planned_end_datetime": ("planned_end_datetime", "planned_end_time"),
    "reviewed_datetime": ("reviewed_datetime", "reviewed_time"),
    "carried_datetime": ("carried_datetime", "carried_time"),
    "canceled_datetime": ("canceled_datetime", "canceled_time"),
    "physician_sign_datetime": ("physician_sign_datetime", "physician_sign_time"),
    "seniorphy_sign_datetime": ("seniorphy_sign_datetime", "seniorphy_sign_time"),
    "chief_physician_sign_datetime": ("chief_physician_sign_datetime", "cheifphy_sign_time"),
    "inpat_no": ("inpat_no", "inpatno"), "mr_no": ("mr_no", "mrno"),
    "order_status": ("order_status", "status"), "generic_name": ("generic_name", "drug_name"),
    "brand_name": ("brand_name",), "drug_code": ("drug_code",),
    "order_name": ("order_name", "item_name", "order_item_name"),
    "drug_specification": ("drug_specification", "specification"),
    "drug_frequency": ("drug_frequency", "frequency"),
    "drug_apply_method": ("drug_apply_method", "route"),
    "single_dose": ("single_dose", "dose", "dosage"),
    "single_dose_unit": ("single_dose_unit", "dose_unit"),
}
for _name in (
    "admission_condition", "treatment_course", "death_reason", "discharge_order", "discharge_condition",
    "positive_assist_exam", "tcm_diagnosis_summary", "tcm_rule", "discharge_sympton_condition",
    "condition_transform", "admission_date", "discharge_date", "inpatient_duration", "resident_physician_sign",
    "chief_physician_sign", "ward_name", "ward_no", "bed_no", "visit_type", "note",
    "diagnosis", "specimen_name", "eye_findings", "microscope_findings", "surgery_process", "surgeon",
    "physician_sign", "recorder_sign", "senior_physician_sign", "attending_physician_sign", "surgeon_sign",
    "application_id", "group_id", "repeat_indicator", "order_type", "drug_type", "quantity", "quantity_unit",
    "frequency", "medication_duration", "dose_form", "item_name", "item_result", "abnormal_indicator",
    "unit", "reference_range", "test_name", "dept_name",
):
    ALIASES.setdefault(_name, (_name,))

VERIFIED_HOMOLOGY_PREFERENCE = {
    "pathology_exam_report": frozenset({"diagnosis"}),
    **{t: frozenset({"planned_end_datetime", "reviewed_datetime", "carried_datetime", "canceled_datetime"})
       for t in ("inpat_drug_order", "inpat_nondrug_order")},
}
CONTENT_FIELDS = frozenset({
    "record_content", "admission_condition", "positive_assist_exam", "treatment_course", "discharge_condition",
    "discharge_order", "discharge_sympton_condition", "death_reason", "tcm_diagnosis_summary", "tcm_rule",
    "surgery_process", "diagnosis", "eye_findings", "microscope_findings",
})


def blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip()) or value == [] or value == {}


def normalized_value(name: str, value: Any) -> Any:
    if name == "v2_schema" and isinstance(value, str):
        return json.loads(value)
    if name.endswith("_datetime"):
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=HOSPITAL_TZ)
        return parsed.astimezone(HOSPITAL_TZ).isoformat()
    if isinstance(value, str):
        return value.strip()
    return value


def equivalent(name: str, left: Any, right: Any) -> bool:
    if name == "record_content":
        return "".join(str(left).split()) == "".join(str(right).split())
    return normalized_value(name, left) == normalized_value(name, right)


def selected_columns(available: Sequence[str]) -> list[str]:
    allowed = {*IDENTITY_FIELDS, "v2_schema"}
    for aliases in ALIASES.values():
        allowed.update(aliases)
    return sorted(allowed.intersection(available))


def normalize_row(raw: Mapping[str, Any]) -> tuple[dict[str, Any], set[str]]:
    """只读明确顶层 JSON 路径；不递归猜测姓名、时间或关联身份。"""
    row = {str(k).lower(): v for k, v in raw.items()}
    v2 = row.get("v2_schema")
    issues: set[str] = set()
    if isinstance(v2, str) and v2.strip():
        try:
            v2 = json.loads(v2)
        except (ValueError, TypeError):
            issues.add("invalid_v2_schema")
    if not isinstance(v2, dict):
        v2 = {}
    result: dict[str, Any] = {}
    for name, aliases in ALIASES.items():
        choices = [row[a] for a in aliases if a in row and not blank(row[a])]
        json_choices = []
        for alias in aliases:
            value = v2.get(alias)
            if name in CONTENT_FIELDS and isinstance(value, list):
                if all(isinstance(n, dict) and isinstance(n.get("original_text"), str) for n in value):
                    value = "".join(n["original_text"] for n in value)
                else:
                    issues.add("unreadable_json_text_nodes:" + name)
                    continue
            if isinstance(value, (str, int, float, bool)) and not blank(value):
                json_choices.append(value)
        choices.extend(json_choices)
        if name == "document_id":
            # 正式文书号优先。sys_index_id/id 仅在正式号缺失时作回退，
            # 它们可能是治理/存储行号，不能要求与正式文书号相等。
            business_ids = [obj[a] for obj in (row, v2) for a in ("document_id", "documentid")
                            if a in obj and isinstance(obj[a], (str, int)) and not blank(obj[a])]
            choices = business_ids or choices[:1]
        if not choices:
            continue
        try:
            chosen = normalized_value(name, choices[0])
            if any(not equivalent(name, chosen, value) for value in choices[1:]):
                issues.add("within_source_conflict:" + name)
            result[name] = chosen
        except (ValueError, TypeError, OverflowError):
            issues.add("invalid_v2_schema" if name == "v2_schema" else "invalid_time:" + name)
    return result, issues


@dataclass(frozen=True)
class SourceSnapshot:
    source: str
    rows: tuple[Mapping[str, Any], ...] = ()
    status: str = "ok"
    captured_at: str = ""
    error_type: str = ""
    sqlstate: str = ""


@dataclass
class Candidate:
    key: tuple[str, ...]
    values: dict[str, Any]
    variants: dict[str, dict[str, Any]]
    provenance: dict[str, str]
    conflicts: set[str] = field(default_factory=set)
    blockers: set[str] = field(default_factory=set)
    local_changes: set[str] = field(default_factory=set)
    raw_variants: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)


@dataclass
class TargetProjection:
    """内存目标列投影，缺列显式返回，不做 DDL/DML。"""

    values: dict[str, Any]
    unmapped_fields: set[str]


def project_candidate(candidate: Candidate, case: Mapping[str, str], columns: Mapping[str, str]) -> TargetProjection:
    projected, unmapped = {}, set()
    for name, value in {**candidate.values, **{k: case[k] for k in IDENTITY_FIELDS}}.items():
        if blank(value):
            continue
        target = next((a for a in (name, *ALIASES.get(name, ())) if a in columns), None)
        if target is None:
            unmapped.add(name)
            continue
        if name.endswith("_datetime") and columns[target] == "timestamp without time zone":
            # 旧客户库无时区列按医院北京时间保留墙上时间，不受客户机系统时区影响。
            value = datetime.fromisoformat(value).astimezone(HOSPITAL_TZ).replace(tzinfo=None).isoformat()
        if name == "v2_schema" and columns[target] == "text" and isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        projected[target] = value
    return TargetProjection(projected, unmapped)


@dataclass
class TablePlan:
    table: str
    candidates: list[Candidate]
    source_counts: dict[str, int]
    source_status: dict[str, str]
    issues: list[str]
    quarantined_rows: int
    quarantine_reasons: dict[str, int] = field(default_factory=dict)
    source_errors: dict[str, dict[str, str]] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return all(s == "ok" for s in self.source_status.values())

    @property
    def ready(self) -> bool:
        return self.complete and not self.issues and not any(c.blockers or c.conflicts for c in self.candidates)

    def report(self, sample: str, target_columns: Mapping[str, str] | None = None,
               case: Mapping[str, str] | None = None) -> dict[str, Any]:
        if target_columns is not None and case is None:
            raise ValueError("projection_case_required")
        records = []
        for candidate in self.candidates:
            token = hashlib.sha256(json.dumps([sample, self.table, candidate.key]).encode()).hexdigest()[:20]
            projection = project_candidate(candidate, case, target_columns) if target_columns is not None else None
            records.append({
                "record_token": token, "sources": sorted(candidate.variants),
                "field_sources": candidate.provenance, "conflicts": sorted(candidate.conflicts),
                "blockers": sorted(candidate.blockers), "local_changes": sorted(candidate.local_changes),
                "local_present": "local" in candidate.variants,
                "projection": ({"mapped_columns": sorted(projection.values),
                                "unmapped_fields": sorted(projection.unmapped_fields),
                                "has_readable_content": any(not blank(projection.values.get(f)) for f in CONTENT_FIELDS)}
                               if projection is not None else None),
                "content_lengths": {s: {f: len(str(v)) for f, v in values.items() if f in CONTENT_FIELDS}
                                    for s, values in candidate.variants.items()},
            })
        projection_complete = target_columns is None or not any(r["projection"]["unmapped_fields"] for r in records)
        return {"sample": sample, "table": self.table, "complete": self.complete,
                "ready": self.ready and projection_complete, "projection_complete": projection_complete,
                "source_counts": self.source_counts, "source_status": self.source_status,
                "candidate_records": len(records), "quarantined_rows": self.quarantined_rows,
                "quarantine_reasons": self.quarantine_reasons, "source_errors": self.source_errors,
                "issues": self.issues, "records": records}


def plan_table(
    table: str, case: Mapping[str, str], clinical: SourceSnapshot, homology: SourceSnapshot,
    local: SourceSnapshot, *, source_institutes: Mapping[str, str],
    stable_keys: Sequence[str] | None = None,
) -> TablePlan:
    if table not in TABLE_KEYS and stable_keys is None:
        raise ValueError("unsupported_table")
    keys_for_table = TABLE_KEYS.get(table, tuple(stable_keys or ()))
    if any(not case.get(k) for k in IDENTITY_FIELDS) or any(not source_institutes.get(s) for s in SOURCES):
        raise ValueError("explicit_identity_mapping_required")
    snapshots = (clinical, homology, local)
    if tuple(s.source for s in snapshots) != SOURCES:
        raise ValueError("source_order_invalid")
    grouped: dict[str, dict[tuple[str, ...], list[tuple[dict[str, Any], set[str], dict[str, Any]]]]] = {}
    issues, quarantined = [], 0
    quarantine_reasons: Counter[str] = Counter()
    for snap in snapshots:
        groups = defaultdict(list)
        if snap.status != "ok":
            issues.append(snap.source + ":" + snap.status)
        for raw in snap.rows:
            if (str(raw.get("patient_id") or "").strip() != case["patient_id"]
                    or str(raw.get("visit_id") or "").strip() != case["visit_id"]
                    or str(raw.get("institute_id") or "").strip() != source_institutes[snap.source]):
                issues.append(snap.source + ":identity_mismatch")
                quarantined += 1
                quarantine_reasons[snap.source + ":case_identity_mismatch"] += 1
                continue
            values, row_issues = normalize_row(raw)
            for key_field in keys_for_table:
                if key_field not in values and not blank(raw.get(key_field)):
                    values[key_field] = raw[key_field]
            key = tuple(str(values.get(k) or "").strip() for k in keys_for_table)
            if not all(key) and table == "labtest_item_report" and values.get("document_id"):
                # 旧本地检验明细只有稳定 document_id，缺上游复合键；保留原行，
                # 使用来源限定的内部匹配键，绝不据此生成源编号或跨库硬合并。
                key = ("unmatched_document_id", snap.source, str(values["document_id"]))
                row_issues.add("cross_source_identity_unavailable")
            if not all(key) or any("within_source_conflict:" + k in row_issues for k in keys_for_table):
                issues.append(snap.source + ":stable_identity_missing_or_conflicting")
                quarantined += 1
                reason = "stable_identity_missing" if not all(key) else "stable_identity_alias_conflict"
                quarantine_reasons[snap.source + ":" + reason] += 1
                continue
            groups[key].append((values, row_issues, dict(raw)))
        grouped[snap.source] = groups
    keys = set().union(*(set(g) for g in grouped.values()))
    candidates = []
    for key in sorted(keys):
        if any(len(groups.get(key, ())) > 1 for groups in grouped.values()):
            issues.append("duplicate_stable_identity")
            quarantined += sum(len(groups.get(key, ())) for groups in grouped.values())
            for source, groups in grouped.items():
                quarantine_reasons[source + ":duplicate_stable_identity"] += len(groups.get(key, ()))
            continue
        variants, raw_variants, blockers = {}, {}, set()
        for source in SOURCES:
            if key in grouped[source]:
                values, source_issues, raw_value = grouped[source][key][0]
                variants[source] = values
                raw_variants[source] = raw_value
                blockers.update(source_issues)
                if str(values.get("is_deleted", "")).lower() in {"1", "true", "t"}:
                    blockers.add("source_deleted")
        preferred = "local" if "local" in variants else "clinical_data" if "clinical_data" in variants else "homology"
        base = variants[preferred]
        values, provenance, conflicts = dict(base), {f: preferred for f in base}, set()
        # 编码或申请身份冲突时整条停止跨源补字段，不以同号直接认同一药品/报告。
        guards = ("drug_code",) if table == "inpat_drug_order" else ("pathology_id",) if table == "pathology_exam_report" else ()
        identity_conflict = False
        for name in guards:
            distinct = {str(v[name]) for v in variants.values() if not blank(v.get(name))}
            if len(distinct) > 1:
                blockers.add("identity_conflict:" + name)
                identity_conflict = True
        if not identity_conflict:
            for source in ("clinical_data", "homology"):
                for name, value in variants.get(source, {}).items():
                    if blank(values.get(name)):
                        values[name], provenance[name] = value, source
                    elif not equivalent(name, values[name], value):
                        conflicts.add(name)
                        # 只在内存候选采用已验证的字段优先级；本地非空值始终不覆盖。
                        if (source == "homology" and name in VERIFIED_HOMOLOGY_PREFERENCE.get(table, ())
                                and blank(variants.get("local", {}).get(name))):
                            values[name], provenance[name] = value, source
        if "homology" in variants and "clinical_data" not in variants and "local" not in variants:
            # 包括 Save：不能由保存状态推断正式有效，更不能自动影响质控。
            blockers.add("source_validity_unconfirmed")
        changes = {name for name, value in values.items() if blank(variants.get("local", {}).get(name)) and not blank(value)}
        candidates.append(Candidate(key, values, variants, provenance, conflicts, blockers, changes, raw_variants))
    return TablePlan(table, candidates, {s.source: len(s.rows) for s in snapshots},
                     {s.source: s.status for s in snapshots}, sorted(set(issues)), quarantined,
                     dict(quarantine_reasons), {s.source: {"error_type": s.error_type, "sqlstate": s.sqlstate}
                                                for s in snapshots if s.error_type or s.sqlstate})


def mark_cross_table_order_ids(plans: Sequence[TablePlan]) -> None:
    """跨药品/非药品同号不自动归类或合并。"""
    counts = Counter(c.key for p in plans if p.table.startswith("inpat_") for c in p.candidates)
    for plan in plans:
        if plan.table.startswith("inpat_"):
            for candidate in plan.candidates:
                if counts[candidate.key] > 1:
                    candidate.blockers.add("cross_table_order_identity")
