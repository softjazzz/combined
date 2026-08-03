"""只读审计 LX0609 权威资料源的每病例行数与读取上限。"""

from __future__ import annotations

import argparse
import math
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlalchemy as sa


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class AuditContractError(ValueError):
    """审计输入或只读合同不满足，错误消息为稳定原因码。"""


_SQL_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


@dataclass(frozen=True, order=True)
class VisitCoordinate:
    institute_id: str
    patient_id: str
    visit_id: str

    @property
    def ref(self) -> str:
        material = json.dumps(
            [self.institute_id, self.patient_id, self.visit_id],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


def coordinate_set_hash(coordinates: Sequence[VisitCoordinate]) -> str:
    """生成与输入顺序无关、不可逆的冻结坐标集合摘要。"""

    normalized = sorted(
        (item.institute_id, item.patient_id, item.visit_id) for item in coordinates
    )
    material = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def select_unique_pool(
    rows: Sequence[Mapping[str, Any]],
    *,
    pool_id: str | None,
    pool_name: str | None,
) -> dict[str, Any]:
    """从已按条件读取的候选行中选择唯一池，绝不按顺序猜测。"""

    if bool(pool_id) == bool(pool_name):
        raise AuditContractError("exactly_one_pool_selector_required")
    normalized_id = str(pool_id or "").strip()
    normalized_name = str(pool_name or "").strip()
    matches = [
        dict(row)
        for row in rows
        if (
            str(row.get("id") or "").strip() == normalized_id
            if normalized_id
            else str(row.get("name") or "").strip() == normalized_name
        )
    ]
    if not matches:
        raise AuditContractError("pool_not_found")
    if len(matches) > 1:
        reason = "pool_id_ambiguous" if normalized_id else "pool_name_ambiguous"
        raise AuditContractError(reason)
    return matches[0]


def freeze_coordinate_rows(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[VisitCoordinate, ...], int]:
    """冻结 matched 样本的完整三坐标，去重并统计缺失项。"""

    coordinates: set[VisitCoordinate] = set()
    excluded = 0
    for row in rows:
        values = tuple(
            str(row.get(field) or "").strip()
            for field in (
                "matched_institute_id",
                "matched_patient_id",
                "matched_visit_id",
            )
        )
        if not all(values):
            excluded += 1
            continue
        coordinates.add(VisitCoordinate(*values))
    return tuple(sorted(coordinates)), excluded


def resolve_focus_coordinate(
    *,
    visit_id: str,
    frozen_coordinates: Sequence[VisitCoordinate],
    fallback_coordinates: Sequence[VisitCoordinate],
) -> tuple[VisitCoordinate, str]:
    """解析重点病例唯一坐标，池内坐标优先，歧义时立即停止。"""

    normalized_visit = str(visit_id or "").strip()
    pool_matches = {
        item for item in frozen_coordinates if item.visit_id == normalized_visit
    }
    if len(pool_matches) == 1:
        return next(iter(pool_matches)), "pool"
    if len(pool_matches) > 1:
        raise AuditContractError("focus_coordinate_ambiguous")
    fallback_matches = {
        item for item in fallback_coordinates if item.visit_id == normalized_visit
    }
    if not fallback_matches:
        raise AuditContractError("focus_coordinate_missing")
    if len(fallback_matches) > 1:
        raise AuditContractError("focus_coordinate_ambiguous")
    return next(iter(fallback_matches)), "fallback"


def merge_audit_coordinates(
    frozen_coordinates: Sequence[VisitCoordinate],
    focus_coordinates: Mapping[str, VisitCoordinate],
) -> tuple[VisitCoordinate, ...]:
    """将唯一解析成功的重点病例加入冻结审计集合并去重。"""

    return tuple(sorted({*frozen_coordinates, *focus_coordinates.values()}))


def count_source_rows_in_batches(
    connection: Any,
    *,
    schema: str,
    source_key: str,
    coordinates: Sequence[VisitCoordinate],
    batch_size: int = 200,
    allowed_source_keys: set[str] | frozenset[str],
) -> dict[str, int]:
    """按受控物理表和完整三坐标批量统计每病例真实行数。"""

    if source_key not in allowed_source_keys:
        raise AuditContractError("source_key_not_allowed")
    if not _SQL_IDENTIFIER.fullmatch(schema) or not _SQL_IDENTIFIER.fullmatch(source_key):
        raise AuditContractError("invalid_sql_identifier")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    counts = {item.ref: 0 for item in coordinates}
    for offset in range(0, len(coordinates), batch_size):
        batch = coordinates[offset : offset + batch_size]
        values_sql: list[str] = []
        params: dict[str, str] = {}
        coordinates_by_value: dict[tuple[str, str, str], VisitCoordinate] = {}
        for index, coordinate in enumerate(batch):
            values_sql.append(f"(:i{index}, :p{index}, :v{index})")
            params[f"i{index}"] = coordinate.institute_id
            params[f"p{index}"] = coordinate.patient_id
            params[f"v{index}"] = coordinate.visit_id
            coordinates_by_value[
                (coordinate.institute_id, coordinate.patient_id, coordinate.visit_id)
            ] = coordinate
        statement = sa.text(
            "WITH visit_keys(institute_id, patient_id, visit_id) AS ("
            f"VALUES {', '.join(values_sql)}"
            ") "
            "SELECT k.institute_id, k.patient_id, k.visit_id, "
            "count(t.*) AS row_count "
            "FROM visit_keys AS k "
            f'LEFT JOIN "{schema}"."{source_key}" AS t '
            "ON t.institute_id::text = k.institute_id "
            "AND t.patient_id::text = k.patient_id "
            "AND t.visit_id::text = k.visit_id "
            "GROUP BY k.institute_id, k.patient_id, k.visit_id"
        )
        rows = connection.execute(statement, params).mappings().all()
        for row in rows:
            key = (
                str(row.get("institute_id") or ""),
                str(row.get("patient_id") or ""),
                str(row.get("visit_id") or ""),
            )
            coordinate = coordinates_by_value.get(key)
            if coordinate is not None:
                counts[coordinate.ref] = max(0, int(row.get("row_count") or 0))
    return counts


def run_in_read_only_snapshot(engine: Any, operation: Callable[[Any], Any]) -> Any:
    """在一个 REPEATABLE READ、READ ONLY 快照中执行完整审计。"""

    configured = engine.connect().execution_options(isolation_level="REPEATABLE READ")
    with configured as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            return operation(connection)


def _qualified(schema: str, table: str) -> str:
    if not _SQL_IDENTIFIER.fullmatch(schema) or not _SQL_IDENTIFIER.fullmatch(table):
        raise AuditContractError("invalid_sql_identifier")
    return f'"{schema}"."{table}"'


def load_pool_candidates(
    connection: Any,
    *,
    pool_schema: str,
    pool_id: str | None,
    pool_name: str | None,
) -> tuple[dict[str, Any], ...]:
    if bool(pool_id) == bool(pool_name):
        raise AuditContractError("exactly_one_pool_selector_required")
    field = "id" if pool_id else "name"
    selector = str(pool_id or pool_name or "").strip()
    statement = sa.text(
        f"SELECT id::text AS id, name::text AS name "
        f"FROM {_qualified(pool_schema, 'manual_problem_sample_pools')} "
        f'WHERE "{field}"::text = :selector ORDER BY id::text'
    )
    rows = connection.execute(statement, {"selector": selector}).mappings().all()
    return tuple(dict(row) for row in rows)


def load_matched_pool_coordinate_rows(
    connection: Any, *, pool_schema: str, pool_id: str
) -> tuple[dict[str, Any], ...]:
    statement = sa.text(
        "SELECT matched_institute_id::text AS matched_institute_id, "
        "matched_patient_id::text AS matched_patient_id, "
        "matched_visit_id::text AS matched_visit_id "
        f"FROM {_qualified(pool_schema, 'manual_problem_sample_pool_items')} "
        "WHERE pool_id::text = :pool_id AND match_status = 'matched' "
        "ORDER BY matched_institute_id::text, matched_patient_id::text, "
        "matched_visit_id::text"
    )
    rows = connection.execute(statement, {"pool_id": pool_id}).mappings().all()
    return tuple(dict(row) for row in rows)


def load_table_columns(connection: Any, *, schema: str, table: str) -> tuple[str, ...]:
    statement = sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = :schema AND table_name = :table "
        "ORDER BY ordinal_position"
    )
    rows = connection.execute(
        statement, {"schema": schema, "table": table}
    ).mappings().all()
    return tuple(str(row.get("column_name") or "") for row in rows)


def load_focus_fallback_coordinates(
    connection: Any, *, source_schema: str, visit_id: str
) -> tuple[VisitCoordinate, ...]:
    coordinates: set[VisitCoordinate] = set()
    for table in ("mr", "admission_record"):
        columns = set(load_table_columns(connection, schema=source_schema, table=table))
        if not {"institute_id", "patient_id", "visit_id"}.issubset(columns):
            continue
        statement = sa.text(
            "SELECT DISTINCT institute_id::text AS institute_id, "
            "patient_id::text AS patient_id, visit_id::text AS visit_id "
            f"FROM {_qualified(source_schema, table)} "
            "WHERE visit_id::text = :visit_id"
        )
        rows = connection.execute(statement, {"visit_id": visit_id}).mappings().all()
        for row in rows:
            values = tuple(
                str(row.get(field) or "").strip()
                for field in ("institute_id", "patient_id", "visit_id")
            )
            if all(values):
                coordinates.add(VisitCoordinate(*values))
    return tuple(sorted(coordinates))


class _BorrowedConnectionEngine:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def connect(self) -> Any:
        return nullcontext(self._connection)


@contextmanager
def borrowed_reader_environment(
    connection: Any, *, columns_by_source: Mapping[str, Sequence[str]]
) -> Any:
    """让现有 reader 借用审计事务，不改变生产 reader 接口。"""

    from app.services.bundles import assembly as bundle_assembly

    original_engine = bundle_assembly.engine
    original_get_columns = bundle_assembly._get_table_columns
    bundle_assembly.engine = _BorrowedConnectionEngine(connection)
    bundle_assembly._get_table_columns = lambda schema, table: tuple(
        columns_by_source.get(str(table), ())
    )
    try:
        yield
    finally:
        bundle_assembly._get_table_columns = original_get_columns
        bundle_assembly.engine = original_engine


def build_source_rule_map() -> dict[str, tuple[str, ...]]:
    from app.services.luxian_0609.executor_registry import (
        resolve_legacy_executor_material_source_keys,
    )
    from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
    from app.services.luxian_0609.source_registry import resolve_luxian_0609_rule_sources

    contracts = load_luxian_0609_rule_contracts()
    rule_ids = tuple(item.rule_id for item in contracts)
    declared = resolve_luxian_0609_rule_sources(rule_ids)
    rules_by_source: dict[str, list[str]] = {}
    for contract in contracts:
        source_keys = [
            source_key
            for entry in declared[contract.rule_id]
            for source_key in entry.source_keys
        ]
        source_keys.extend(
            resolve_legacy_executor_material_source_keys(
                (contract.executor_key,), selected_rule_ids=(contract.rule_id,)
            )
        )
        for source_key in dict.fromkeys(source_keys):
            rules_by_source.setdefault(source_key, []).append(contract.rule_id)
    return {key: tuple(value) for key, value in rules_by_source.items()}


def _read_source(
    *, source_key: str, coordinate: VisitCoordinate, source_schema: str
) -> Any:
    from app.services.luxian_0609.source_evidence_reader import (
        read_luxian_0609_snapshot_source_rows,
    )

    return read_luxian_0609_snapshot_source_rows(
        source_key=source_key,
        institute_id=coordinate.institute_id,
        patient_id=coordinate.patient_id,
        visit_id=coordinate.visit_id,
        source_schema=source_schema,
    )


def audit_all_sources(
    connection: Any,
    *,
    coordinates: Sequence[VisitCoordinate],
    source_schema: str,
    focus_coordinates: Mapping[str, VisitCoordinate],
) -> list[dict[str, Any]]:
    from app.services.luxian_0609 import source_evidence_reader as reader
    from app.services.luxian_0609.source_evidence_reader import (
        SourceEvidenceQueryError,
        SourceEvidenceUnavailable,
    )

    all_source_keys = tuple(sorted(reader._SNAPSHOT_SOURCE_FIELDS))
    derived_keys = tuple(key for key in all_source_keys if "." in key)
    physical_keys = tuple(key for key in all_source_keys if "." not in key)
    allowed_physical = frozenset(physical_keys)
    columns_by_source = {
        source_key: load_table_columns(
            connection, schema=source_schema, table=source_key
        )
        for source_key in physical_keys
    }
    rule_map = build_source_rule_map()
    all_refs = tuple(item.ref for item in coordinates)
    source_summaries: list[dict[str, Any]] = []

    with borrowed_reader_environment(
        connection, columns_by_source=columns_by_source
    ):
        for source_key in physical_keys:
            current_limit = reader._source_limit(source_key)
            columns = set(columns_by_source[source_key])
            affected_rules = rule_map.get(source_key, ())
            base: dict[str, Any] = {
                "source_key": source_key,
                "physical_table": f"{source_schema}.{source_key}",
                "current_limit": current_limit,
                "affected_rule_ids": list(affected_rules),
                "complete_set_required": bool(affected_rules),
            }
            if not {"institute_id", "patient_id", "visit_id"}.issubset(columns):
                base.update(
                    {
                        **summarize_source_counts(
                            counts_by_visit={},
                            all_visit_refs=all_refs,
                            current_limit=current_limit,
                        ),
                        "reader_truncated_count": 0,
                        "availability_status": "table_or_coordinates_unavailable",
                        "recommendation": "keep_limit",
                    }
                )
                source_summaries.append(base)
                continue

            counts = count_source_rows_in_batches(
                connection,
                schema=source_schema,
                source_key=source_key,
                coordinates=coordinates,
                allowed_source_keys=allowed_physical,
            )
            candidates = [
                coordinate
                for coordinate in coordinates
                if counts.get(coordinate.ref, 0) > current_limit
            ]
            truncated_refs: set[str] = set()
            validation_errors = 0
            for coordinate in candidates:
                try:
                    source_rows = _read_source(
                        source_key=source_key,
                        coordinate=coordinate,
                        source_schema=source_schema,
                    )
                except (SourceEvidenceUnavailable, SourceEvidenceQueryError):
                    validation_errors += 1
                    continue
                if source_rows.truncated:
                    truncated_refs.add(coordinate.ref)
            base.update(
                {
                    **summarize_source_counts(
                        counts_by_visit=counts,
                        all_visit_refs=all_refs,
                        current_limit=current_limit,
                    ),
                    "reader_truncated_count": len(truncated_refs),
                    "reader_validation_error_count": validation_errors,
                    "availability_status": "available",
                    "recommendation": (
                        "propose_limit_change"
                        if truncated_refs and affected_rules
                        else "keep_limit"
                    ),
                }
            )
            for alias, coordinate in focus_coordinates.items():
                base[alias] = {
                    "row_count": counts.get(coordinate.ref, 0),
                    "truncated": coordinate.ref in truncated_refs,
                }
            source_summaries.append(base)

        for source_key in derived_keys:
            if source_key == "evaluation_context.horizon":
                source_summaries.append(
                    {
                        "source_key": source_key,
                        "physical_table": "not_physical",
                        "current_limit": 1,
                        "sample_visit_count": len(coordinates),
                        "recommendation": "keep_limit",
                        "availability_status": "runtime_derived",
                        "affected_rule_ids": list(rule_map.get(source_key, ())),
                        "complete_set_required": False,
                    }
                )
                continue
            counts: dict[str, int] = {}
            truncated_refs: set[str] = set()
            current_limit = 1
            validation_errors = 0
            for coordinate in coordinates:
                try:
                    source_rows = _read_source(
                        source_key=source_key,
                        coordinate=coordinate,
                        source_schema=source_schema,
                    )
                except (SourceEvidenceUnavailable, SourceEvidenceQueryError):
                    validation_errors += 1
                    continue
                current_limit = source_rows.limit_rows
                counts[coordinate.ref] = len(source_rows.rows)
                if source_rows.truncated:
                    truncated_refs.add(coordinate.ref)
            affected_rules = rule_map.get(source_key, ())
            item: dict[str, Any] = {
                "source_key": source_key,
                "physical_table": "derived_reader",
                "current_limit": current_limit,
                **summarize_source_counts(
                    counts_by_visit=counts,
                    all_visit_refs=all_refs,
                    current_limit=current_limit,
                ),
                "reader_truncated_count": len(truncated_refs),
                "reader_validation_error_count": validation_errors,
                "availability_status": "derived_reader",
                "affected_rule_ids": list(affected_rules),
                "complete_set_required": bool(affected_rules),
                "recommendation": (
                    "propose_limit_change"
                    if truncated_refs and affected_rules
                    else "keep_limit"
                ),
            }
            for alias, coordinate in focus_coordinates.items():
                item[alias] = {
                    "row_count": counts.get(coordinate.ref, 0),
                    "truncated": coordinate.ref in truncated_refs,
                }
            source_summaries.append(item)
    return source_summaries


def current_git_commit() -> str:
    completed = subprocess.run(
        ["git", "-c", "safe.directory=D:/LLM/LX888", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def execute_audit(
    connection: Any,
    *,
    pool_id: str | None,
    pool_name: str | None,
    focus_visit_ids: Sequence[str],
    audit_started_at: str,
    git_commit: str,
) -> dict[str, Any]:
    from app.database.connection import DB_SCHEMA_MODE
    from app.services.bundles import assembly as bundle_assembly

    pool_schema = "qc" if DB_SCHEMA_MODE == "split" else "public"
    source_schema = bundle_assembly._default_source_schema()
    candidates = load_pool_candidates(
        connection,
        pool_schema=pool_schema,
        pool_id=pool_id,
        pool_name=pool_name,
    )
    pool = select_unique_pool(
        candidates, pool_id=pool_id, pool_name=pool_name
    )
    coordinate_rows = load_matched_pool_coordinate_rows(
        connection, pool_schema=pool_schema, pool_id=str(pool["id"])
    )
    frozen_coordinates, excluded = freeze_coordinate_rows(coordinate_rows)
    if not frozen_coordinates:
        raise AuditContractError("frozen_coordinate_set_empty")

    focus_coordinates: dict[str, VisitCoordinate] = {}
    focus_results: dict[str, dict[str, Any]] = {}
    missing = 0
    ambiguous = 0
    for index, visit_id in enumerate(focus_visit_ids):
        alias = f"focus_case_{chr(ord('a') + index)}"
        fallback = load_focus_fallback_coordinates(
            connection, source_schema=source_schema, visit_id=visit_id
        )
        try:
            coordinate, resolved_from = resolve_focus_coordinate(
                visit_id=visit_id,
                frozen_coordinates=frozen_coordinates,
                fallback_coordinates=fallback,
            )
        except AuditContractError as exc:
            if str(exc) == "focus_coordinate_missing":
                missing += 1
                focus_results[alias] = {"coordinate_status": "missing"}
            else:
                ambiguous += 1
                focus_results[alias] = {"coordinate_status": "ambiguous"}
            continue
        focus_coordinates[alias] = coordinate
        focus_results[alias] = {
            "coordinate_status": "resolved",
            "resolved_from": resolved_from,
        }

    audit_coordinates = merge_audit_coordinates(
        frozen_coordinates, focus_coordinates
    )
    source_summaries = audit_all_sources(
        connection,
        coordinates=audit_coordinates,
        source_schema=source_schema,
        focus_coordinates=focus_coordinates,
    )
    return build_safe_report_payload(
        audit_started_at=audit_started_at,
        git_commit=git_commit,
        pool_id=str(pool["id"]),
        pool_name=str(pool["name"]),
        frozen_coordinates=audit_coordinates,
        excluded_missing_coordinates=excluded,
        focus_coordinate_missing=missing,
        focus_coordinate_ambiguous=ambiguous,
        focus_results=focus_results,
        source_summaries=source_summaries,
    )


def render_markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# LX0609 真实源表行数与读取上限审计",
        "",
        "## 冻结快照",
        "",
        f"- 审计时间（UTC）：`{report['audit_started_at']}`",
        f"- Git commit：`{report['git_commit']}`",
        f"- 事务：`REPEATABLE READ, READ ONLY`",
        f"- 样本池：`{report['pool_name']}`（ID `{report['pool_id']}`）",
        f"- 冻结病例：{report['frozen_coordinate_count']} 份",
        f"- 坐标集合哈希：`{report['coordinate_set_hash']}`",
        f"- 缺三坐标排除：{report['excluded_missing_coordinates']} 份",
        f"- 重点病例坐标缺失/歧义：{report['focus_coordinate_missing']} / {report['focus_coordinate_ambiguous']}",
        "",
        "## 结论",
        "",
    ]
    sources = list(report.get("source_summaries") or ())
    proposed = [item for item in sources if item.get("recommendation") == "propose_limit_change"]
    lines.append(
        f"- 审计资料源 {len(sources)} 个；确认截断并建议评估上限的资料源 {len(proposed)} 个。"
    )
    lines.append("- 零行和正常稀疏默认保持当前上限，不据此推断同步或字段映射异常。")
    lines.extend(
        [
            "",
            "## 分资料源统计",
            "",
            "|资料源|物理表|上限|病例|非空|P50|P95|P99|最大|等于上限|超过上限|reader截断|重点A|重点B|影响规则|建议|",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|",
        ]
    )
    for item in sources:
        focus_a = item.get("focus_case_a") or {}
        focus_b = item.get("focus_case_b") or {}
        affected = ", ".join(item.get("affected_rule_ids") or ()) or "—"
        lines.append(
            "|{source_key}|{physical_table}|{current_limit}|{sample_visit_count}|"
            "{nonempty_visit_count}|{p50}|{p95}|{p99}|{max}|{at_limit_count}|"
            "{above_limit_count}|{reader_truncated_count}|{focus_a}|{focus_b}|"
            "{affected}|{recommendation}|".format(
                source_key=item.get("source_key", "—"),
                physical_table=item.get("physical_table", "—"),
                current_limit=item.get("current_limit", "—"),
                sample_visit_count=item.get("sample_visit_count", "—"),
                nonempty_visit_count=item.get("nonempty_visit_count", "—"),
                p50=item.get("p50", "—"),
                p95=item.get("p95", "—"),
                p99=item.get("p99", "—"),
                max=item.get("max", "—"),
                at_limit_count=item.get("at_limit_count", "—"),
                above_limit_count=item.get("above_limit_count", "—"),
                reader_truncated_count=item.get("reader_truncated_count", 0),
                focus_a=(
                    f"{focus_a.get('row_count', 0)} / {'截断' if focus_a.get('truncated') else '完整'}"
                    if focus_a
                    else "—"
                ),
                focus_b=(
                    f"{focus_b.get('row_count', 0)} / {'截断' if focus_b.get('truncated') else '完整'}"
                    if focus_b
                    else "—"
                ),
                affected=affected,
                recommendation=item.get("recommendation", "keep_limit"),
            )
        )
    lines.extend(
        [
            "",
            "## 决策门",
            "",
            "本报告只提供只读证据。未获得用户对具体 source key 和新值的再次确认前，不修改生产读取上限。",
            "",
        ]
    )
    return "\n".join(lines)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    selectors = parser.add_mutually_exclusive_group(required=True)
    selectors.add_argument("--pool-id")
    selectors.add_argument("--pool-name")
    parser.add_argument("--focus-visit-id", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    from app.database.connection import engine

    args = build_argument_parser().parse_args(argv)
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured")
    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    commit = current_git_commit()
    report = run_in_read_only_snapshot(
        engine,
        lambda connection: execute_audit(
            connection,
            pool_id=args.pool_id,
            pool_name=args.pool_name,
            focus_visit_ids=tuple(args.focus_visit_id),
            audit_started_at=started_at,
            git_commit=commit,
        ),
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown_report(report), encoding="utf-8", newline="\n")
    proposed = sum(
        item.get("recommendation") == "propose_limit_change"
        for item in report["source_summaries"]
    )
    print(
        f"pool_id={report['pool_id']} frozen={report['frozen_coordinate_count']} "
        f"sources={len(report['source_summaries'])} proposed={proposed} output={output}"
    )
    return 0


def build_safe_report_payload(
    *,
    audit_started_at: str,
    git_commit: str,
    pool_id: str,
    pool_name: str,
    frozen_coordinates: Sequence[VisitCoordinate],
    excluded_missing_coordinates: int,
    focus_coordinate_missing: int,
    focus_coordinate_ambiguous: int,
    focus_results: Mapping[str, Mapping[str, Any]],
    source_summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """返回不含患者信息和原始三坐标的审计交付对象。"""

    return {
        "audit_started_at": audit_started_at,
        "git_commit": git_commit,
        "transaction_isolation": "repeatable_read",
        "transaction_read_only": True,
        "pool_id": pool_id,
        "pool_name": pool_name,
        "frozen_coordinate_count": len(frozen_coordinates),
        "coordinate_set_hash": coordinate_set_hash(frozen_coordinates),
        "excluded_missing_coordinates": int(excluded_missing_coordinates),
        "focus_coordinate_missing": int(focus_coordinate_missing),
        "focus_coordinate_ambiguous": int(focus_coordinate_ambiguous),
        "focus_results": {
            str(key): dict(value) for key, value in focus_results.items()
        },
        "source_summaries": [dict(item) for item in source_summaries],
    }


def nearest_rank(values: Sequence[int], percentile: float) -> int:
    """使用确定性的 nearest-rank 算法计算百分位数。"""

    ordered = sorted(int(value) for value in values)
    if not ordered:
        return 0
    if not 0 < percentile <= 1:
        raise ValueError("percentile must be in (0, 1]")
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def summarize_source_counts(
    *,
    counts_by_visit: Mapping[str, int],
    all_visit_refs: Sequence[str],
    current_limit: int,
) -> dict[str, int | float]:
    """汇总一个资料源的行数分布，未命中的冻结病例按零行计。"""

    if current_limit < 1:
        raise ValueError("current_limit must be positive")
    counts = [max(0, int(counts_by_visit.get(ref, 0))) for ref in all_visit_refs]
    return {
        "sample_visit_count": len(counts),
        "nonempty_visit_count": sum(value > 0 for value in counts),
        "p50": nearest_rank(counts, 0.50),
        "p95": nearest_rank(counts, 0.95),
        "p99": nearest_rank(counts, 0.99),
        "max": max(counts, default=0),
        "at_limit_count": sum(value == current_limit for value in counts),
        "above_limit_count": sum(value > current_limit for value in counts),
    }


if __name__ == "__main__":
    raise SystemExit(main())
