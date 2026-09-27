"""只迁移已发布 LX0609 历史记录中的结构化规则身份。

此模块刻意不导入运行时规则目录或服务。对应表只在离线迁移中读取；任何
JSON 原始模型响应、提示词和评论字段都是不透明归档，绝不做全文替换。
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

import sqlalchemy as sa
from sqlalchemy import MetaData, Table, and_, inspect, select

MAPPING_VERSION = "lx0609-four-part-rule-code-mapping-v1"
EXPECTED_LEGACY_COUNT = 79
ENVELOPE_SCHEMA = "lx0609-record-result-envelope-v1"
_IDENTITY_FIELDS = frozenset(
    {"rule_id", "rule_code", "qc_point_id", "customer_rule_id"}
)
_IDENTITY_LIST_FIELDS = frozenset(
    {
        "rule_ids",
        "rule_codes",
        "qc_point_ids",
        "selected_rule_ids",
        "failed_rule_ids",
        "mapped_rule_ids",
        "execution_rule_ids",
        "customer_rule_ids",
        "covered_customer_rule_ids",
        "scoped_customer_rule_ids",
        "gate_only_customer_rule_ids",
        "paused_customer_rule_ids",
        "planned_rule_ids",
        "expected_rule_ids",
        "selected_customer_rule_ids",
    }
)
_IDENTITY_MAP_FIELDS = frozenset(
    {"results_by_rule_id", "rule_results_by_id", "rules_by_id"}
)
_RECORD_RULE_MAP_FIELDS = frozenset({"record_rule_map"})
_OPAQUE_FIELDS = frozenset(
    {
        "comment",
        "prompt",
        "raw_model_response",
        "model_response",
        "raw_response",
        "raw_execution_snapshot",
        "raw_execution_response",
    }
)
_KNOWN_CANONICAL_STATUSES = frozenset(
    {
        "compliant",
        "non_compliant",
        "ai_suggested_compliant",
        "ai_suggested_non_compliant",
        "data_gap",
        "not_applicable",
        "not_executed",
    }
)


class MigrationBlocked(RuntimeError):
    """预检、版本或 compare-and-swap 失败；调用者不得提交部分写入。"""


@dataclass(frozen=True)
class MappingSet:
    version: str
    digest: str
    legacy_to_new: dict[str, str]


@dataclass(frozen=True)
class Issue:
    code: str
    location: str
    detail: str


@dataclass
class Operation:
    table: str
    row_id: str
    changes: dict[str, dict[str, Any]]


@dataclass
class MigrationPlan:
    mapping_version: str
    mapping_digest: str
    operations: list[Operation] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not self.issues

    def safe_summary(self) -> dict[str, Any]:
        return {
            "mapping_version": self.mapping_version,
            "mapping_digest": self.mapping_digest,
            "ready": self.ready,
            "operation_count": len(self.operations),
            "issue_count": len(self.issues),
            "issues": [asdict(issue) for issue in self.issues],
        }

    def as_dict(self) -> dict[str, Any]:
        """仅用于受控私有审计计划；其中可能含历史 JSON 原值。"""
        return {
            "mapping_version": self.mapping_version,
            "mapping_digest": self.mapping_digest,
            "operations": [asdict(item) for item in self.operations],
            "issues": [asdict(item) for item in self.issues],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MigrationPlan":
        operations = [
            Operation(**item)
            for item in raw.get("operations", [])
            if isinstance(item, dict)
        ]
        issues = [
            Issue(**item) for item in raw.get("issues", []) if isinstance(item, dict)
        ]
        return cls(
            str(raw.get("mapping_version") or ""),
            str(raw.get("mapping_digest") or ""),
            operations,
            issues,
        )


def _mapping_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "plans"
        / "lx0609-four-part-rule-code-mapping-v1.csv"
    )


def load_mapping(
    path: Path | str | None = None, *, expected_version: str = MAPPING_VERSION
) -> MappingSet:
    if expected_version != MAPPING_VERSION:
        raise MigrationBlocked(f"mapping_version_mismatch:{expected_version}")
    source = Path(path) if path else _mapping_path()
    raw = source.read_bytes()
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    pairs: dict[str, str] = {}
    values: set[str] = set()
    for row in rows:
        legacy, current = (
            str(row.get(key) or "").strip().upper()
            for key in ("legacy_rule_id", "rule_id")
        )
        if not legacy or not current or legacy in pairs or current in values:
            raise MigrationBlocked("invalid_or_non_unique_mapping")
        if legacy in {"LX0609-080", "LX0609-081"}:
            raise MigrationBlocked("unpublished_rule_in_mapping")
        pairs[legacy], values = current, values | {current}
    expected_legacy_ids = {f"LX0609-{number:03d}" for number in range(1, 80)}
    if set(pairs) != expected_legacy_ids:
        raise MigrationBlocked("legacy_mapping_is_not_exactly_001_to_079")
    if len(pairs) != EXPECTED_LEGACY_COUNT:
        raise MigrationBlocked(f"unexpected_mapping_count:{len(pairs)}")
    if any(
        re.fullmatch(r"LX0609-(?!00)\d{2}-(?!00)\d{2}-(?!00)\d{2}", rule_id) is None
        for rule_id in values
    ):
        raise MigrationBlocked("invalid_four_part_rule_id_in_mapping")
    return MappingSet(MAPPING_VERSION, hashlib.sha256(raw).hexdigest(), pairs)


def write_private_plan(plan: MigrationPlan, path: Path | str) -> None:
    """禁止把可能含患者原文的原值计划写到非私有审计目录。"""
    target = Path(path).resolve()
    audit_root = (
        Path(__file__).resolve().parents[3] / ".tmp" / "0910-full-audit"
    ).resolve()
    if audit_root not in target.parents or not target.name.endswith("-private.json"):
        raise MigrationBlocked("private_plan_path_required")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(plan.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def read_private_plan(path: Path | str) -> MigrationPlan:
    source = Path(path).resolve()
    audit_root = (
        Path(__file__).resolve().parents[3] / ".tmp" / "0910-full-audit"
    ).resolve()
    if audit_root not in source.parents or not source.name.endswith("-private.json"):
        raise MigrationBlocked("private_plan_path_required")
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationBlocked("invalid_plan_file") from exc
    if not isinstance(raw, dict):
        raise MigrationBlocked("invalid_plan_file")
    return MigrationPlan.from_dict(raw)


def _text(value: Any) -> str:
    return str(value or "").strip().upper()


def _is_lx(value: Any) -> bool:
    return _text(value).startswith("LX0609-")


class _JsonTransformer:
    def __init__(self, mapping: MappingSet, location: str) -> None:
        self.mapping, self.location, self.issues = mapping, location, []

    def identity(self, value: Any, path: str) -> Any:
        if not isinstance(value, str):
            self.issues.append(
                Issue("invalid_identity_type", path, type(value).__name__)
            )
            return value
        normalized = _text(value)
        if normalized in self.mapping.legacy_to_new:
            return self.mapping.legacy_to_new[normalized]
        if normalized in self.mapping.legacy_to_new.values() or not _is_lx(value):
            return value
        self.issues.append(Issue("unknown_lx0609_identity", path, normalized))
        return value

    def transform(self, value: Any, path: str = "$") -> Any:
        if isinstance(value, list):
            return [
                self.transform(item, f"{path}[{index}]")
                for index, item in enumerate(value)
            ]
        if not isinstance(value, dict):
            return value
        result: dict[str, Any] = {}
        for key, item in value.items():
            child = f"{path}.{key}"
            if key in _OPAQUE_FIELDS:
                result[key] = item
            elif key in _IDENTITY_FIELDS:
                result[key] = self.identity(item, child)
            elif key in _IDENTITY_LIST_FIELDS:
                if not isinstance(item, list):
                    self.issues.append(
                        Issue("invalid_identity_list", child, type(item).__name__)
                    )
                    result[key] = item
                else:
                    result[key] = [
                        self.identity(entry, f"{child}[{index}]")
                        for index, entry in enumerate(item)
                    ]
            elif key in _IDENTITY_MAP_FIELDS:
                if not isinstance(item, dict):
                    self.issues.append(
                        Issue("invalid_identity_map", child, type(item).__name__)
                    )
                    result[key] = item
                else:
                    mapped_entries: dict[Any, Any] = {}
                    for map_key, map_value in item.items():
                        mapped_key = self.identity(map_key, f"{child}.<key>")
                        if mapped_key in mapped_entries:
                            self.issues.append(
                                Issue(
                                    "identity_map_key_collision", child, str(mapped_key)
                                )
                            )
                        mapped_entries[mapped_key] = self.transform(
                            map_value, f"{child}.{map_key}"
                        )
                    result[key] = mapped_entries
            elif key in _RECORD_RULE_MAP_FIELDS:
                # failed_rule_retry.record_rule_map 的 key 是病历坐标；只有 value
                # 才是规则数组。迁移 key 会让补跑错误关联到另一份病历。
                if not isinstance(item, dict):
                    self.issues.append(
                        Issue("invalid_record_rule_map", child, type(item).__name__)
                    )
                    result[key] = item
                else:
                    mapped_records: dict[Any, Any] = {}
                    for record_key, rule_ids in item.items():
                        record_path = f"{child}.{record_key}"
                        if not isinstance(rule_ids, list):
                            self.issues.append(
                                Issue(
                                    "invalid_record_rule_map_value",
                                    record_path,
                                    type(rule_ids).__name__,
                                )
                            )
                            mapped_records[record_key] = rule_ids
                            continue
                        mapped_records[record_key] = [
                            self.identity(rule_id, f"{record_path}[{index}]")
                            for index, rule_id in enumerate(rule_ids)
                        ]
                    result[key] = mapped_records
            else:
                result[key] = self.transform(item, child)
        present = {
            _text(result[key])
            for key in _IDENTITY_FIELDS & result.keys()
            if isinstance(result[key], str) and _text(result[key])
        }
        if len(present) > 1:
            self.issues.append(
                Issue("conflicting_identity_fields", path, ",".join(sorted(present)))
            )
        return result


def _json_change(
    raw: Any, mapping: MappingSet, location: str
) -> tuple[Any, list[Issue]]:
    if raw is None:
        return raw, []
    if not isinstance(raw, str):
        return raw, [Issue("json_column_not_text", location, type(raw).__name__)]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw, [Issue("invalid_json", location, "cannot safely inspect")]
    transformer = _JsonTransformer(mapping, location)
    updated = transformer.transform(parsed)
    if updated == parsed:
        return raw, transformer.issues
    return (
        json.dumps(updated, ensure_ascii=False, separators=(",", ":")),
        transformer.issues,
    )


def _identity_change(
    value: Any, mapping: MappingSet, location: str
) -> tuple[Any, list[Issue]]:
    transformer = _JsonTransformer(mapping, location)
    return transformer.identity(value, location), transformer.issues


def _identity_list_json_change(
    raw: Any, mapping: MappingSet, location: str
) -> tuple[Any, list[Issue]]:
    """处理列本身就是规则数组的受控合同，而非递归猜测任意顶层数组。"""
    if not isinstance(raw, str):
        return raw, [Issue("json_column_not_text", location, type(raw).__name__)]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw, [Issue("invalid_json", location, "cannot safely inspect")]
    if not isinstance(parsed, list):
        return raw, [Issue("invalid_identity_list", location, type(parsed).__name__)]
    transformer = _JsonTransformer(mapping, location)
    updated = [
        transformer.identity(value, f"{location}[{index}]")
        for index, value in enumerate(parsed)
    ]
    if updated == parsed:
        return raw, transformer.issues
    return (
        json.dumps(updated, ensure_ascii=False, separators=(",", ":")),
        transformer.issues,
    )


def _require_columns(table: Table, columns: Iterable[str], issues: list[Issue]) -> bool:
    missing = sorted(set(columns) - set(table.c.keys()))
    if missing:
        issues.append(Issue("missing_required_columns", table.name, ",".join(missing)))
        return False
    return True


def _validate_envelope(
    row: Mapping[str, Any], updated_json: str, location: str
) -> list[Issue]:
    issues: list[Issue] = []
    try:
        envelope = json.loads(updated_json)
    except json.JSONDecodeError:
        return [Issue("invalid_json", location, "cannot safely inspect")]
    if (
        not isinstance(envelope, dict)
        or envelope.get("schema_version") != ENVELOPE_SCHEMA
    ):
        return [Issue("unsupported_envelope_contract", location, "schema_version")]
    for key in ("root_job_id", "record_ref", "rule_set_key", "rule_set_version"):
        if not str(envelope.get(key) or "").strip():
            issues.append(
                Issue("incomplete_envelope_identity", f"{location}.{key}", "missing")
            )
    if str(envelope.get("root_job_id") or "") != str(row.get("root_job_id") or ""):
        issues.append(Issue("envelope_root_job_mismatch", location, "row/root_job_id"))
    items = envelope.get("items")
    if not isinstance(items, list):
        return issues + [Issue("invalid_envelope_items", location, "not_list")]
    if int(row.get("result_count") or 0) != len(items):
        issues.append(Issue("envelope_result_count_mismatch", location, "result_count"))
    seen: set[str] = set()
    for index, item in enumerate(items):
        item_path = f"{location}.items[{index}]"
        if not isinstance(item, dict):
            issues.append(Issue("invalid_envelope_item", item_path, "not_object"))
            continue
        rule_id = _text(item.get("rule_id") or item.get("rule_code"))
        status = str(item.get("status") or "")
        if not rule_id or rule_id in seen or status not in _KNOWN_CANONICAL_STATUSES:
            issues.append(
                Issue("invalid_envelope_item_contract", item_path, rule_id or status)
            )
            continue
        seen.add(rule_id)
        if item.get("result_status") != status or (
            item.get("display_status") and item.get("display_status") != status
        ):
            issues.append(Issue("invalid_envelope_status_contract", item_path, status))
        expected = (
            True
            if status == "compliant"
            else False
            if status == "non_compliant"
            else None
        )
        if item.get("is_compliant") is not expected:
            issues.append(
                Issue("invalid_envelope_compliance_contract", item_path, status)
            )
    return issues


def _digest(item: Mapping[str, Any]) -> str:
    payload = {
        "rule_id": _text(item.get("rule_id") or item.get("rule_code")),
        "status": str(
            item.get("status")
            or item.get("result_status")
            or item.get("display_status")
            or ""
        ).strip(),
        "reason_code": str(item.get("reason_code") or "").strip(),
        "customer_display_facts": item.get("customer_display_facts")
        if isinstance(item.get("customer_display_facts"), (dict, list))
        else {},
        "customer_evidence": item.get("customer_evidence")
        if isinstance(item.get("customer_evidence"), (dict, list))
        else item.get("evidence")
        if isinstance(item.get("evidence"), (dict, list))
        else [],
    }
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _tables(
    engine: sa.Engine, schema: str | None, issues: list[Issue]
) -> dict[str, Table]:
    inspector, metadata, result = inspect(engine), MetaData(), {}
    for name in (
        "custom_qc_batch_jobs",
        "luxian_0609_record_result_envelopes",
        "qc_result_feedback_demo",
        "manual_problem_sample_pool_items",
    ):
        if inspector.has_table(name, schema=schema):
            result[name] = Table(name, metadata, autoload_with=engine, schema=schema)
    for name in (
        "custom_qc_batch_jobs",
        "luxian_0609_record_result_envelopes",
        "qc_result_feedback_demo",
        "manual_problem_sample_pool_items",
    ):
        if name not in result:
            issues.append(
                Issue(
                    "missing_required_table",
                    "database",
                    f"cannot verify complete migration:{name}",
                )
            )
    return result


def _op(
    table: Table,
    row: Mapping[str, Any],
    changes: dict[str, dict[str, Any]],
    plan: MigrationPlan,
) -> None:
    if changes:
        plan.operations.append(Operation(table.name, str(row["id"]), changes))


def build_plan(
    database_url: str,
    *,
    schema: str | None = None,
    mapping_path: Path | str | None = None,
    expected_mapping_version: str = MAPPING_VERSION,
) -> MigrationPlan:
    mapping = load_mapping(mapping_path, expected_version=expected_mapping_version)
    plan = MigrationPlan(mapping.version, mapping.digest)
    engine = sa.create_engine(database_url)
    try:
        tables = _tables(engine, schema, plan.issues)
        batch = tables.get("custom_qc_batch_jobs")
        if batch is not None and _require_columns(
            batch,
            (
                "id",
                "status",
                "rule_code",
                "filters_json",
                "items_json",
                "summary_json",
                "failed_records_json",
                "child_summary_json",
            ),
            plan.issues,
        ):
            with engine.connect() as conn:
                for row in conn.execute(select(batch)).mappings():
                    # 活跃任务的范围摘要仍绑定旧身份；禁止边执行边迁移。
                    # 全部任务排空后只保留历史摘要，不冒充按新编号执行过。
                    if str(row["status"] or "").strip().lower() not in {
                        "completed",
                        "failed",
                        "canceled",
                    }:
                        plan.issues.append(
                            Issue(
                                "active_or_unknown_job_status",
                                f"batch:{row['id']}",
                                "migration_requires_drained_jobs",
                            )
                        )
                    changes: dict[str, dict[str, Any]] = {}
                    # 顶层 rule_code 也承载批次/组合/其他规则集标识；只有冻结表中
                    # 的单规则旧值才允许改写，未知值绝不能据前缀猜测。
                    current_code = _text(row["rule_code"])
                    new_code = mapping.legacy_to_new.get(current_code, row["rule_code"])
                    if new_code != row["rule_code"]:
                        changes["rule_code"] = {
                            "before": row["rule_code"],
                            "after": new_code,
                        }
                    for column in (
                        "filters_json",
                        "items_json",
                        "summary_json",
                        "failed_records_json",
                        "child_summary_json",
                    ):
                        updated, issues = _json_change(
                            row.get(column), mapping, f"batch:{row['id']}.{column}"
                        )
                        plan.issues.extend(issues)
                        if updated != row.get(column):
                            changes[column] = {
                                "before": row.get(column),
                                "after": updated,
                            }
                    _op(batch, row, changes, plan)
        envelope = tables.get("luxian_0609_record_result_envelopes")
        envelope_rows: list[Mapping[str, Any]] = []
        if envelope is not None and _require_columns(
            envelope,
            ("id", "root_job_id", "created_by", "envelope_json", "result_count"),
            plan.issues,
        ):
            with engine.connect() as conn:
                envelope_rows = list(conn.execute(select(envelope)).mappings())
            for row in envelope_rows:
                updated, issues = _json_change(
                    row["envelope_json"], mapping, f"envelope:{row['id']}.envelope_json"
                )
                plan.issues.extend(
                    issues + _validate_envelope(row, updated, f"envelope:{row['id']}")
                )
                if updated != row["envelope_json"]:
                    _op(
                        envelope,
                        row,
                        {
                            "envelope_json": {
                                "before": row["envelope_json"],
                                "after": updated,
                            }
                        },
                        plan,
                    )
        feedback = tables.get("qc_result_feedback_demo")
        if feedback is not None:
            _plan_feedback(feedback, envelope_rows, mapping, plan, engine)
        sample_items = tables.get("manual_problem_sample_pool_items")
        if sample_items is not None and _require_columns(
            sample_items,
            ("id", "candidate_rule_ids_json", "raw_payload_json"),
            plan.issues,
        ):
            _plan_sample_pool_items(sample_items, mapping, plan, engine)
        _audit_custom_rule_drafts(engine, schema, mapping, plan)
    finally:
        engine.dispose()
    return plan


def _plan_sample_pool_items(
    table: Table, mapping: MappingSet, plan: MigrationPlan, engine: sa.Engine
) -> None:
    """样本池候选规则和客户自建 payload 都会参与后续规则选择。"""
    with engine.connect() as conn:
        rows = list(conn.execute(select(table)).mappings())
    for row in rows:
        changes: dict[str, dict[str, Any]] = {}
        for column in ("candidate_rule_ids_json", "raw_payload_json"):
            change_fn = (
                _identity_list_json_change
                if column == "candidate_rule_ids_json"
                else _json_change
            )
            updated, issues = change_fn(
                row[column], mapping, f"sample_pool_item:{row['id']}.{column}"
            )
            plan.issues.extend(issues)
            if updated != row[column]:
                changes[column] = {"before": row[column], "after": updated}
        _op(table, row, changes, plan)


def _audit_custom_rule_drafts(
    engine: sa.Engine, schema: str | None, mapping: MappingSet, plan: MigrationPlan
) -> None:
    """published_rule_id 正常是 qc_rules UUID；旧规则号属于异常数据，必须人工处理。"""
    inspector = inspect(engine)
    if not inspector.has_table("custom_qc_rule_drafts", schema=schema):
        return
    table = Table(
        "custom_qc_rule_drafts", MetaData(), autoload_with=engine, schema=schema
    )
    required = {"id", "rule_code", "published_rule_id"}
    if not required.issubset(table.c.keys()):
        plan.issues.append(
            Issue(
                "incomplete_custom_draft_contract",
                table.name,
                ",".join(sorted(required - set(table.c.keys()))),
            )
        )
        return
    with engine.connect() as conn:
        rows = list(
            conn.execute(
                select(table.c.id, table.c.rule_code, table.c.published_rule_id)
            ).mappings()
        )
    for row in rows:
        for column in ("rule_code", "published_rule_id"):
            value = _text(row[column])
            if value in mapping.legacy_to_new:
                plan.issues.append(
                    Issue(
                        "legacy_identity_in_custom_draft",
                        f"custom_qc_rule_drafts:{row['id']}.{column}",
                        value,
                    )
                )


def _plan_feedback(
    feedback: Table,
    envelope_rows: list[Mapping[str, Any]],
    mapping: MappingSet,
    plan: MigrationPlan,
    engine: sa.Engine,
) -> None:
    if not _require_columns(
        feedback,
        (
            "id",
            "root_job_id",
            "record_ref",
            "rule_id",
            "original_status",
            "result_digest",
            "created_by",
        ),
        plan.issues,
    ):
        return
    index: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for row in envelope_rows:
        try:
            envelope = json.loads(row["envelope_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(envelope, dict):
            continue
        for item in envelope.get("items", []):
            if isinstance(item, dict):
                key = (
                    str(row.get("created_by") or ""),
                    str(envelope.get("root_job_id") or ""),
                    str(envelope.get("record_ref") or ""),
                    _text(item.get("rule_id") or item.get("rule_code")),
                )
                index.setdefault(key, []).append(item)
    targets: set[tuple[str, str, str, str]] = set()
    with engine.connect() as conn:
        rows = list(conn.execute(select(feedback)).mappings())
    for row in rows:
        old_id = _text(row["rule_id"])
        new_id, issues = _identity_change(
            row["rule_id"], mapping, f"feedback:{row['id']}.rule_id"
        )
        plan.issues.extend(issues)
        candidates = index.get(
            (
                str(row["created_by"]),
                str(row["root_job_id"]),
                str(row["record_ref"]),
                old_id,
            ),
            [],
        )
        if len(candidates) != 1:
            plan.issues.append(
                Issue(
                    "orphan_or_ambiguous_feedback",
                    f"feedback:{row['id']}",
                    str(len(candidates)),
                )
            )
            continue
        if row["result_digest"] != _digest(candidates[0]) or str(
            row["original_status"]
        ) != str(
            candidates[0].get("status")
            or candidates[0].get("result_status")
            or candidates[0].get("display_status")
            or ""
        ):
            plan.issues.append(
                Issue(
                    "feedback_digest_or_status_mismatch",
                    f"feedback:{row['id']}",
                    old_id,
                )
            )
            continue
        target = (
            str(row["created_by"]),
            str(row["root_job_id"]),
            str(row["record_ref"]),
            str(new_id),
        )
        if target in targets:
            plan.issues.append(
                Issue(
                    "feedback_target_unique_conflict",
                    f"feedback:{row['id']}",
                    str(new_id),
                )
            )
            continue
        targets.add(target)
        # 摘要必须对应最终保存的整个item，包括证据内受控身份字段。
        # 即便顶层身份已迁移，证据中仍可能有旧身份，摘要也需要一起更新。
        updated_item = _JsonTransformer(mapping, f"feedback:{row['id']}").transform(
            candidates[0]
        )
        changes = {}
        for column, updated in (
            ("rule_id", new_id),
            ("result_digest", _digest(updated_item)),
        ):
            if updated != row[column]:
                changes[column] = {"before": row[column], "after": updated}
        _op(feedback, row, changes, plan)


def apply_plan(
    database_url: str,
    plan: MigrationPlan,
    *,
    schema: str | None = None,
    expected_mapping_version: str = MAPPING_VERSION,
    expected_mapping_digest: str | None = None,
) -> None:
    if not plan.ready:
        raise MigrationBlocked("plan_has_blocking_issues")
    current_mapping = load_mapping(expected_version=expected_mapping_version)
    required_digest = expected_mapping_digest or current_mapping.digest
    if (
        plan.mapping_version != current_mapping.version
        or plan.mapping_digest != current_mapping.digest
        or plan.mapping_digest != required_digest
    ):
        raise MigrationBlocked("plan_mapping_version_or_digest_mismatch")
    # 审阅计划不能被删掉部分操作或改成任意SQL更新。重新盘点完整快照，
    # 对比操作集合及归属/摘要校验；之后逐列CAS继续防止执行期间的变化。
    fresh_plan = build_plan(database_url, schema=schema)
    operation_key = lambda operation: (operation.table, operation.row_id)
    if not fresh_plan.ready or sorted(plan.operations, key=operation_key) != sorted(
        fresh_plan.operations, key=operation_key
    ):
        raise MigrationBlocked("compare_and_swap_failed:plan_stale_or_modified")
    engine, metadata = sa.create_engine(database_url), MetaData()
    try:
        with engine.begin() as conn:
            reflected: dict[str, Table] = {}
            for operation in plan.operations:
                table = reflected.setdefault(
                    operation.table,
                    Table(
                        operation.table, metadata, autoload_with=engine, schema=schema
                    ),
                )
                if "id" not in table.c:
                    raise MigrationBlocked(f"missing_primary_id:{operation.table}")
                conditions = [table.c.id == operation.row_id]
                values: dict[str, Any] = {}
                for column, change in operation.changes.items():
                    if column not in table.c:
                        raise MigrationBlocked(
                            f"missing_column:{operation.table}.{column}"
                        )
                    conditions.append(table.c[column] == change["before"])
                    values[column] = change["after"]
                if (
                    conn.execute(
                        table.update().where(and_(*conditions)).values(**values)
                    ).rowcount
                    != 1
                ):
                    raise MigrationBlocked(
                        f"compare_and_swap_failed:{operation.table}:{operation.row_id}"
                    )
    finally:
        engine.dispose()
