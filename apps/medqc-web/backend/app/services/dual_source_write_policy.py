"""双源候选到保守写入计划：纯函数，不连接数据库，不改变规则时间含义。"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import math

from . import dual_source_sync as policy


EXTRA_ALIASES = {
    "last_modified_datetime": ("last_modified_time", "lastmodifieddatetime"),
    "update_time": ("updatetime",),
}
REGIMEN_GROUPS = (
    {"single_dose", "single_dose_unit", "single_dose_number", "single_dose_form_unit",
     "drug_frequency", "drug_apply_method", "medication_duration"},
    {"quantity", "quantity_unit", "frequency"},
)


def approval_digest(values):
    """确认绑定文书身份、正文、正式时间和签名，不受备份日期序列化格式影响。"""
    identity_and_clocks = {"document_id", "document_title", "document_status", "record_status", "is_deleted",
                           "record_datetime", "submit_datetime", "report_datetime", "death_datetime"}
    selected = {key: value for key, value in values.items()
                if key in policy.CONTENT_FIELDS | identity_and_clocks or "sign" in key}
    return hashlib.sha256(json.dumps(selected, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


@dataclass
class WriteBatch:
    operations: list[dict] = field(default_factory=list)
    records: list[dict] = field(default_factory=list)


def cast_cell(value, meta):
    kind = meta["data_type"]
    if policy.blank(value):
        return None
    if kind.startswith("timestamp"):
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=policy.HOSPITAL_TZ)
        return parsed.astimezone(policy.HOSPITAL_TZ).replace(tzinfo=None) if kind == "timestamp without time zone" else parsed
    if kind == "date":
        return value if type(value) is date else date.fromisoformat(str(value)[:10])
    if kind in {"integer", "bigint", "smallint"}:
        number = Decimal(str(value))
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError("invalid_integer")
        limits = {"smallint": 15, "integer": 31, "bigint": 63}
        if not -(2 ** limits[kind]) <= number < 2 ** limits[kind]:
            raise ValueError("integer_out_of_range")
        return int(number)
    if kind in {"numeric", "decimal", "real", "double precision"}:
        result = Decimal(str(value))
        if not result.is_finite():
            raise ValueError("nonfinite_number")
        scale, precision = meta.get("numeric_scale"), meta.get("numeric_precision")
        if kind in {"numeric", "decimal"} and scale is not None:
            quantized = result.quantize(Decimal(1).scaleb(-scale))
            if quantized != result:
                raise ValueError("numeric_rounding_required")
            if precision is not None and abs(result) >= Decimal(10) ** (precision - scale):
                raise ValueError("numeric_overflow")
        if kind in {"real", "double precision"} and not math.isfinite(float(result)):
            raise ValueError("numeric_overflow")
        return float(result) if kind in {"real", "double precision"} else result
    if kind in {"json", "jsonb"}:
        return json.loads(value) if isinstance(value, str) else value
    if kind == "boolean":
        if str(value).lower() not in {"true", "t", "1", "false", "f", "0"}:
            raise ValueError("invalid_boolean")
        return str(value).lower() in {"true", "t", "1"}
    if kind not in {"text", "character varying", "character", "bit", "bit varying", "uuid"}:
        raise ValueError("unsupported_type")
    result = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    maximum = meta.get("character_maximum_length")
    if maximum is not None and len(result) > maximum:
        raise ValueError("value_too_long")
    return result


def _target_aliases(target, raw):
    aliases = {target}
    for name, names in policy.ALIASES.items():
        if target == name or target in names:
            aliases.update(names)
    for name, names in EXTRA_ALIASES.items():
        if target == name or target in names:
            aliases.update((name, *names))
    if target == "document_id" and any(not policy.blank(raw.get(k)) for k in ("document_id", "documentid")):
        aliases = {"document_id", "documentid"}
    return aliases


def _offered(candidate, columns, case):
    offered, problems = defaultdict(list), set()
    for source, raw in candidate.raw_variants.items():
        if source == "local":
            continue
        normalized, issues = policy.normalize_row(raw)
        problems.update(issues)
        for target, meta in columns.items():
            if target in policy.IDENTITY_FIELDS or meta.get("is_generated") == "ALWAYS" or meta.get("is_identity") == "YES":
                continue
            aliases = _target_aliases(target, raw)
            values = [raw[k] for k in aliases if not policy.blank(raw.get(k))]
            if target == "document_id" and not policy.blank(normalized.get("document_id")):
                # JSON中的正式文书号也优先于普通列的治理行号。
                values = [normalized["document_id"]]
            if not values:
                values = [normalized[k] for k, names in policy.ALIASES.items()
                          if target in (k, *names) and not policy.blank(normalized.get(k))]
            for value in values:
                try:
                    offered[target].append(cast_cell(value, meta))
                except (ValueError, TypeError, OverflowError, ArithmeticError):
                    problems.add("invalid_target_value:" + target)
        known = set().union(*(_target_aliases(target, raw) for target in columns))
        for name, value in normalized.items():
            if not policy.blank(value) and not any(alias in known for alias in (name, *policy.ALIASES.get(name, ()))):
                problems.add("target_column_missing:" + name)
    for key in policy.IDENTITY_FIELDS:
        offered[key] = [case[key]]
    return offered, problems


def build_write_batch(table, plan, case, columns, primary_keys, local_rows, *, approved_records=()):
    """仅补空值。身份问题整条隔离，非空冲突逐字段跳过；新增文书必须有明确正文。"""
    if not plan.complete:
        raise ValueError("source_coverage_incomplete")
    batch = WriteBatch()
    unmatched_local_lab = table == "labtest_item_report" and any(
        not all(policy.normalize_row(row)[0].get(k) for k in policy.TABLE_KEYS[table]) for row in local_rows
    )
    for candidate in plan.candidates:
        token = hashlib.sha256(json.dumps([case["sample"], table, candidate.key]).encode()).hexdigest()[:20]
        report = {"sample": case["sample"], "table": table, "record_token": token, "conflicts": [], "skipped": []}
        batch.records.append(report)
        blockers = set(candidate.blockers)
        if table not in policy.DOC_TABLES:
            blockers.discard("source_validity_unconfirmed")
        approved_digest = dict(approved_records).get(candidate.key)
        source_digest = approval_digest(candidate.variants.get("homology", {}))
        if approved_digest and approved_digest == source_digest:
            blockers.discard("source_validity_unconfirmed")
        # 同源非法时间/JSON不能拿另一来源的值静默替代。
        if blockers:
            report["skipped"] = sorted(blockers)
            continue
        existing = candidate.raw_variants.get("local")
        if unmatched_local_lab and existing is None:
            report["skipped"] = ["unresolved_local_composite_identity"]
            continue
        offered, issues = _offered(candidate, columns, case)
        conflicts = set(candidate.conflicts)
        blocked_targets = {target for target in columns for name in conflicts
                           if target in (name, *policy.ALIASES.get(name, ())) }
        for problem in issues:
            if problem.startswith("invalid_target_value:"):
                blocked_targets.add(problem.split(":", 1)[1])
        patch = {}
        for target, values in offered.items():
            if target in blocked_targets or not values:
                continue
            if any(value != values[0] for value in values[1:]):
                conflicts.add(target)
                continue
            old = (existing or {}).get(target)
            if not policy.blank(old):
                try:
                    if cast_cell(old, columns[target]) != values[0]:
                        conflicts.add(target)
                except (ValueError, TypeError, OverflowError, ArithmeticError):
                    conflicts.add(target)
                continue
            patch[target] = values[0]
        if existing:
            for key in ("document_id", "order_id", "drug_code", "pathology_id", *primary_keys):
                if key in conflicts:
                    report["skipped"] = ["business_identity_conflict"]
                    break
            if report["skipped"]:
                continue
            for key in primary_keys:
                patch.pop(key, None)
        for group in REGIMEN_GROUPS:
            if group.intersection(conflicts | blocked_targets):
                for key in group:
                    patch.pop(key, None)
        report["conflicts"] = sorted(conflicts)
        report["skipped"].extend(sorted(issues))
        if existing is None:
            if conflicts:
                report["skipped"].append("new_record_conflict")
                continue
            required = {key for key, meta in columns.items() if meta["is_nullable"] == "NO"
                        and not meta.get("column_default") and meta.get("is_identity") != "YES"
                        and meta.get("is_generated") != "ALWAYS"} | set(primary_keys)
            if any(policy.blank(patch.get(key)) for key in required):
                report["skipped"].append("required_target_value_missing")
                continue
            if table in policy.DOC_TABLES and not any(not policy.blank(patch.get(f)) for f in policy.CONTENT_FIELDS):
                report["skipped"].append("document_content_missing")
                continue
        if patch:
            batch.operations.append({"table": table, "sample": case["sample"], "before": existing,
                                     "values": patch, "primary_keys": tuple(primary_keys), "case": dict(case)})
            report["action"] = "insert" if existing is None else "fill"
            report["fields"] = sorted(patch)
        else:
            report["action"] = "unchanged"
    return batch
