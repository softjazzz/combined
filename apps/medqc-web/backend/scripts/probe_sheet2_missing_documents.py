#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text as sql_text


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
REPO_ROOT = BACKEND_ROOT.parents[2]
DEFAULT_LEDGER_CSV = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC" / "sheet2_verification_ledger_seed.csv"
DEFAULT_RELEASE_0426_DIR = REPO_ROOT / "release" / "0426" / "0426"
DEFAULT_RELEASE_0426_FULL_AUTO_DIR = REPO_ROOT / "release" / "0426_full_auto" / "0426_full_auto"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from import_visit_export import _read_csv_rows  # noqa: E402
from app.database.connection import DATABASE_URL, engine  # noqa: E402
from app.services.document_assembly import assemble_document  # noqa: E402
from app.services.medical_records.detail_service import get_documents  # noqa: E402
from app.services.medical_records.shared import DOC_TYPES  # noqa: E402


EXTRA_DOC_LABELS: dict[str, str] = {
    "anesthesia_record": "麻醉记录",
    "blood_application": "输血申请单",
    "bloodtrans_record": "输血记录",
    "crisis_value_record": "危急值记录",
    "death_discussion": "死亡讨论记录",
    "diffcase_discussion_record": "疑难病例讨论记录",
    "docpat_commu_record": "知情沟通记录",
    "handoff_record": "交班记录",
    "handover_record": "接班记录",
    "mr_bloodtrans": "输血首页摘要",
    "postane_surveil_record": "麻醉术后访视记录",
    "preane_surveil_record": "麻醉术前访视记录",
    "presurg_discussion": "术前讨论记录",
    "presurg_summary": "术前小结",
    "rescue_record": "抢救记录",
    "summary_record": "阶段小结",
    "surgery_inform_consent": "手术知情同意书",
    "surgery_risk_assessment": "手术风险评估表",
    "surgery_safecheck_record": "手术安全核查记录",
    "transfer_in_record": "转入记录",
    "transfer_out_record": "转出记录",
}
TABLE_LABELS = {name: label for name, label in DOC_TYPES}
TABLE_LABELS.update(EXTRA_DOC_LABELS)
STANDARD_DOC_TABLES = {name for name, _ in DOC_TYPES}
CSV_BOOL_TRUE = "true"
CSV_BOOL_FALSE = "false"
WRITEBACK_FIELDS = [
    "verification_status",
    "evidence_status",
    "evidence_summary",
    "skip_reason",
    "next_action",
    "skip_allowed",
    "missing_document_types",
    "checked_sources",
    "fallback_available",
    "suggested_skip_reason",
]


@dataclass(frozen=True)
class DocumentGroup:
    logical_type: str
    primary_tables: tuple[str, ...]
    fallback_tables: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceCheck:
    source_name: str
    table_name: str
    location: str
    status: str
    row_count: int
    content_count: int
    is_fallback: bool = False
    error_message: str = ""

    def summary_token(self) -> str:
        detail = f"{self.source_name}@{self.location}:{self.status}"
        if self.error_message:
            return f"{detail}({self.error_message})"
        if self.status in {"content", "row_empty"}:
            return f"{detail}(rows={self.row_count},content={self.content_count})"
        return detail


class SnapshotCSVStore:
    def __init__(self, root: Path, source_name: str) -> None:
        self.root = root
        self.source_name = source_name
        self._cache: dict[str, tuple[str, dict[str, list[dict[str, Any]]]]] = {}

    def probe(self, *, table_name: str, visit_id: str, is_fallback: bool) -> SourceCheck:
        path = self.root / f"{table_name}.csv"
        location = str(path)
        if not visit_id:
            return SourceCheck(
                source_name=self.source_name,
                table_name=table_name,
                location=location,
                status="visit_id_missing",
                row_count=0,
                content_count=0,
                is_fallback=is_fallback,
            )
        if not path.exists():
            return SourceCheck(
                source_name=self.source_name,
                table_name=table_name,
                location=location,
                status="file_missing",
                row_count=0,
                content_count=0,
                is_fallback=is_fallback,
            )

        load_status, visit_map = self._load_table(table_name=table_name, path=path)
        if load_status != "ok":
            return SourceCheck(
                source_name=self.source_name,
                table_name=table_name,
                location=location,
                status="read_error",
                row_count=0,
                content_count=0,
                is_fallback=is_fallback,
                error_message=load_status,
            )

        rows = visit_map.get(visit_id) or []
        content_count = sum(1 for row in rows if _row_has_meaningful_content(table_name, row))
        status = "content" if content_count > 0 else ("row_empty" if rows else "no_row")
        return SourceCheck(
            source_name=self.source_name,
            table_name=table_name,
            location=location,
            status=status,
            row_count=len(rows),
            content_count=content_count,
            is_fallback=is_fallback,
        )

    def _load_table(self, *, table_name: str, path: Path) -> tuple[str, dict[str, list[dict[str, Any]]]]:
        cached = self._cache.get(table_name)
        if cached is not None:
            return cached
        try:
            _, rows = _read_csv_rows(path)
        except Exception as exc:  # pragma: no cover - 依赖本地文件状态
            result = (str(exc), {})
            self._cache[table_name] = result
            return result

        visit_map: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            visit_id = _safe_text(row.get("visit_id"))
            if not visit_id:
                continue
            visit_map.setdefault(visit_id, []).append(row)
        result = ("ok", visit_map)
        self._cache[table_name] = result
        return result


class LocalPGStore:
    def __init__(self) -> None:
        self._standard_cache: dict[str, tuple[str, dict[str, list[dict[str, Any]]]]] = {}
        self._direct_cache: dict[tuple[str, str], tuple[str, list[dict[str, Any]]]] = {}

    def probe(self, *, table_name: str, visit_id: str, is_fallback: bool) -> SourceCheck:
        location = f"local_pg::{table_name}"
        if not visit_id:
            return SourceCheck(
                source_name="local_pg",
                table_name=table_name,
                location=location,
                status="visit_id_missing",
                row_count=0,
                content_count=0,
                is_fallback=is_fallback,
            )
        if not DATABASE_URL or engine is None:
            return SourceCheck(
                source_name="local_pg",
                table_name=table_name,
                location=location,
                status="source_unavailable",
                row_count=0,
                content_count=0,
                is_fallback=is_fallback,
                error_message="DATABASE_URL 未配置",
            )

        if table_name in STANDARD_DOC_TABLES:
            status, doc_map = self._load_standard_documents(visit_id=visit_id)
            if status != "ok":
                return SourceCheck(
                    source_name="local_pg",
                    table_name=table_name,
                    location=location,
                    status="query_error",
                    row_count=0,
                    content_count=0,
                    is_fallback=is_fallback,
                    error_message=status,
                )
            docs = doc_map.get(table_name) or []
            content_count = sum(1 for doc in docs if bool(doc.get("has_content")))
            row_count = sum(1 for doc in docs if _safe_text(doc.get("document_id")))
            if content_count > row_count:
                row_count = content_count
            status_name = "content" if content_count > 0 else ("row_empty" if row_count > 0 else "no_row")
            return SourceCheck(
                source_name="local_pg",
                table_name=table_name,
                location=location,
                status=status_name,
                row_count=row_count,
                content_count=content_count,
                is_fallback=is_fallback,
            )

        status, rows = self._load_direct_rows(table_name=table_name, visit_id=visit_id)
        if status != "ok":
            return SourceCheck(
                source_name="local_pg",
                table_name=table_name,
                location=location,
                status="query_error",
                row_count=0,
                content_count=0,
                is_fallback=is_fallback,
                error_message=status,
            )
        content_count = sum(1 for row in rows if _row_has_meaningful_content(table_name, row))
        status_name = "content" if content_count > 0 else ("row_empty" if rows else "no_row")
        return SourceCheck(
            source_name="local_pg",
            table_name=table_name,
            location=location,
            status=status_name,
            row_count=len(rows),
            content_count=content_count,
            is_fallback=is_fallback,
        )

    def _load_standard_documents(self, *, visit_id: str) -> tuple[str, dict[str, list[dict[str, Any]]]]:
        cached = self._standard_cache.get(visit_id)
        if cached is not None:
            return cached
        try:
            result = get_documents(visit_id=visit_id)
            documents = list(result.get("documents") or [])
        except Exception as exc:  # pragma: no cover - 依赖本地数据库状态
            failure = (str(exc), {})
            self._standard_cache[visit_id] = failure
            return failure

        doc_map: dict[str, list[dict[str, Any]]] = {}
        for document in documents:
            table_name = _safe_text(document.get("source_table") or document.get("type"))
            if not table_name:
                continue
            doc_map.setdefault(table_name, []).append(document)
        success = ("ok", doc_map)
        self._standard_cache[visit_id] = success
        return success

    def _load_direct_rows(self, *, table_name: str, visit_id: str) -> tuple[str, list[dict[str, Any]]]:
        cache_key = (table_name, visit_id)
        cached = self._direct_cache.get(cache_key)
        if cached is not None:
            return cached
        if not _is_safe_ident(table_name):
            failure = (f"非法表名: {table_name}", [])
            self._direct_cache[cache_key] = failure
            return failure

        query = sql_text(f"SELECT * FROM {table_name} WHERE visit_id = :visit_id")
        try:
            with engine.connect() as connection:
                rows = [dict(row) for row in connection.execute(query, {"visit_id": visit_id}).mappings().all()]
        except Exception as exc:  # pragma: no cover - 依赖本地数据库状态
            failure = (str(exc), [])
            self._direct_cache[cache_key] = failure
            return failure

        success = ("ok", rows)
        self._direct_cache[cache_key] = success
        return success


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def _normalize_issue_text(value: Any) -> str:
    return re.sub(r"\s+", " ", _safe_text(value).replace("\u3000", " "))


def _is_safe_ident(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value or ""))


def _csv_bool(value: bool) -> str:
    return CSV_BOOL_TRUE if value else CSV_BOOL_FALSE


def _unique_in_order(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _safe_text(value)
        if text and text not in result:
            result.append(text)
    return result


def _split_rule_ids(row: dict[str, Any]) -> set[str]:
    rule_ids: list[str] = []
    for field_name in ("primary_rule_id", "secondary_rule_ids"):
        raw_value = _safe_text(row.get(field_name))
        if not raw_value:
            continue
        rule_ids.extend(item.strip().upper() for item in raw_value.split("|") if item.strip())
    return set(rule_ids)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _append_group(
    groups: list[DocumentGroup],
    *,
    logical_type: str,
    primary_tables: tuple[str, ...],
    fallback_tables: tuple[str, ...] = (),
) -> None:
    if any(item.logical_type == logical_type for item in groups):
        return
    groups.append(
        DocumentGroup(
            logical_type=logical_type,
            primary_tables=primary_tables,
            fallback_tables=fallback_tables,
        )
    )


def _infer_document_groups(row: dict[str, Any]) -> list[DocumentGroup]:
    issue_text = _normalize_issue_text(row.get("manual_issue_text"))
    issue_family = _safe_text(row.get("issue_family"))
    rule_ids = _split_rule_ids(row)
    groups: list[DocumentGroup] = []

    if rule_ids & {"SC-008", "SC-009", "SC-010", "SC-011", "SC-012", "SC-013", "SC-018", "SC-019", "SC-020"}:
        _append_group(
            groups,
            logical_type="入院记录",
            primary_tables=("admission_record",),
        )
    if rule_ids & {"SC-021", "SC-022", "SC-023", "SC-024", "SC-025", "SC-026", "SC-027"}:
        _append_group(
            groups,
            logical_type="首次病程记录",
            primary_tables=("first_course_record",),
            fallback_tables=("senior_course_record", "daily_course_record"),
        )
    if rule_ids & {"SC-032", "SC-033", "SC-036", "LXE-18"}:
        _append_group(
            groups,
            logical_type="日常病程记录",
            primary_tables=("daily_course_record",),
            fallback_tables=("senior_course_record",),
        )
    if rule_ids & {"SC-048", "SC-049", "SC-050", "SC-051", "SC-052", "SC-077"}:
        _append_group(
            groups,
            logical_type="上级医师查房记录",
            primary_tables=("senior_course_record",),
            fallback_tables=("daily_course_record",),
        )
    if rule_ids & {"SC-062", "SC-063"}:
        _append_group(
            groups,
            logical_type="交接班记录",
            primary_tables=("handoff_record", "handover_record"),
        )
    if rule_ids & {"SC-064"}:
        _append_group(
            groups,
            logical_type="转科记录",
            primary_tables=("transfer_in_record", "transfer_out_record"),
        )
    if rule_ids & {"SC-065"}:
        _append_group(
            groups,
            logical_type="阶段小结",
            primary_tables=("summary_record",),
        )
    if rule_ids & {"SC-067", "SC-068", "SC-069", "SC-071", "SC-072"}:
        _append_group(
            groups,
            logical_type="会诊记录",
            primary_tables=("consultation_record",),
            fallback_tables=("daily_course_record",),
        )
    if rule_ids & {"SC-070", "LX-016"}:
        _append_group(
            groups,
            logical_type="会诊执行证据",
            primary_tables=("consultation_record",),
            fallback_tables=("daily_course_record",),
        )
    if rule_ids & {"SC-039"}:
        _append_group(
            groups,
            logical_type="危急值记录",
            primary_tables=("crisis_value_record",),
            fallback_tables=("daily_course_record", "senior_course_record"),
        )
    if rule_ids & {"SC-073", "SC-074", "LX-018"}:
        _append_group(
            groups,
            logical_type="输血相关文书",
            primary_tables=("bloodtrans_record", "mr_bloodtrans", "blood_application"),
            fallback_tables=("daily_course_record",),
        )
    if rule_ids & {"SC-080", "SC-081"}:
        _append_group(
            groups,
            logical_type="术前小结",
            primary_tables=("presurg_summary",),
            fallback_tables=("presurg_discussion", "surgery_record"),
        )
    if rule_ids & {"SC-082", "SC-083", "SC-084", "SC-085"}:
        _append_group(
            groups,
            logical_type="术前讨论",
            primary_tables=("presurg_discussion",),
            fallback_tables=("presurg_summary", "surgery_record"),
        )
    if rule_ids & {"SC-086"}:
        _append_group(
            groups,
            logical_type="术前主刀查房/麻醉术前访视",
            primary_tables=("senior_course_record", "preane_surveil_record"),
            fallback_tables=("presurg_summary", "presurg_discussion"),
        )
    if rule_ids & {"SC-087", "SC-089", "SC-128", "LX-021"}:
        _append_group(
            groups,
            logical_type="知情同意书/知情沟通",
            primary_tables=("surgery_inform_consent", "docpat_commu_record"),
        )
    if rule_ids & {"SC-095", "SC-096", "SC-097", "SC-098"}:
        _append_group(
            groups,
            logical_type="手术记录",
            primary_tables=("surgery_record",),
            fallback_tables=("presurg_summary", "postsurg_firstcourse_record"),
        )
    if rule_ids & {"SC-104", "SC-105"}:
        _append_group(
            groups,
            logical_type="术后首次病程/麻醉术后访视",
            primary_tables=("postsurg_firstcourse_record", "postane_surveil_record"),
            fallback_tables=("surgery_record", "daily_course_record"),
        )
    if rule_ids & {"SC-107", "LXE-35"}:
        _append_group(
            groups,
            logical_type="术后病程/查房记录",
            primary_tables=("daily_course_record",),
            fallback_tables=("senior_course_record", "postsurg_firstcourse_record"),
        )
    if rule_ids & {"SC-116", "SC-117", "SC-118", "SC-126"}:
        _append_group(
            groups,
            logical_type="出院记录",
            primary_tables=("discharge_record",),
        )

    # 对 manual_review 或缺主规则条目，优先按原文关键词兜底。
    combined_text = issue_text + issue_family
    if _contains_any(
        combined_text,
        (
            "入院记录",
            "主诉",
            "现病史",
            "既往史",
            "体格检查",
            "专科检查",
            "入院诊断",
            "初步诊断",
            "院外辅助检查",
            "喂养史",
            "月经史",
            "婚育史",
            "受伤地点",
        ),
    ) or issue_family == "入院记录内容不完整/前后矛盾":
        _append_group(
            groups,
            logical_type="入院记录",
            primary_tables=("admission_record",),
        )
    if _contains_any(combined_text, ("危急值",)):
        _append_group(
            groups,
            logical_type="危急值记录",
            primary_tables=("crisis_value_record",),
            fallback_tables=("daily_course_record", "senior_course_record"),
        )
    if _contains_any(combined_text, ("输血",)):
        _append_group(
            groups,
            logical_type="输血相关文书",
            primary_tables=("bloodtrans_record", "mr_bloodtrans", "blood_application"),
            fallback_tables=("daily_course_record",),
        )
    if _contains_any(combined_text, ("会诊执行", "遵会诊意见", "遵执")):
        _append_group(
            groups,
            logical_type="会诊执行证据",
            primary_tables=("consultation_record",),
            fallback_tables=("daily_course_record",),
        )
    elif _contains_any(combined_text, ("会诊",)):
        _append_group(
            groups,
            logical_type="会诊记录",
            primary_tables=("consultation_record",),
            fallback_tables=("daily_course_record",),
        )
    if _contains_any(combined_text, ("术前小结",)):
        _append_group(
            groups,
            logical_type="术前小结",
            primary_tables=("presurg_summary",),
            fallback_tables=("presurg_discussion", "surgery_record"),
        )
    if _contains_any(combined_text, ("术前讨论", "MDT", "多学科讨论")):
        _append_group(
            groups,
            logical_type="术前讨论",
            primary_tables=("presurg_discussion",),
            fallback_tables=("presurg_summary", "surgery_record"),
        )
    if _contains_any(combined_text, ("手术同意书", "知情同意", "授权受托人", "知情沟通")):
        _append_group(
            groups,
            logical_type="知情同意书/知情沟通",
            primary_tables=("surgery_inform_consent", "docpat_commu_record"),
        )
    if _contains_any(combined_text, ("术后首次病程", "麻醉术后访视")):
        _append_group(
            groups,
            logical_type="术后首次病程/麻醉术后访视",
            primary_tables=("postsurg_firstcourse_record", "postane_surveil_record"),
            fallback_tables=("surgery_record", "daily_course_record"),
        )
    if _contains_any(combined_text, ("手术记录", "有创操作", "清创", "穿刺", "胸腔闭式引流")):
        _append_group(
            groups,
            logical_type="手术/操作记录",
            primary_tables=("surgery_record",),
            fallback_tables=("presurg_summary", "postsurg_firstcourse_record"),
        )
    if _contains_any(combined_text, ("交接班", "交班记录", "接班记录")):
        _append_group(
            groups,
            logical_type="交接班记录",
            primary_tables=("handoff_record", "handover_record"),
        )
    if _contains_any(combined_text, ("转入记录", "转出记录", "转科")):
        _append_group(
            groups,
            logical_type="转科记录",
            primary_tables=("transfer_in_record", "transfer_out_record"),
        )
    if _contains_any(combined_text, ("出院记录",)):
        _append_group(
            groups,
            logical_type="出院记录",
            primary_tables=("discharge_record",),
        )
    if _contains_any(combined_text, ("首次病程",)):
        _append_group(
            groups,
            logical_type="首次病程记录",
            primary_tables=("first_course_record",),
            fallback_tables=("senior_course_record", "daily_course_record"),
        )
    if _contains_any(combined_text, ("查房", "上级医师")) and "会诊" not in issue_text:
        _append_group(
            groups,
            logical_type="上级医师查房记录",
            primary_tables=("senior_course_record",),
            fallback_tables=("daily_course_record",),
        )
    has_daily_course_keyword = _contains_any(combined_text, ("日常病程", "无病程", "后无病程", "病程查房记录"))
    if "病程记录" in combined_text and not _contains_any(combined_text, ("首次病程记录", "术后首次病程记录")):
        has_daily_course_keyword = True
    if has_daily_course_keyword:
        _append_group(
            groups,
            logical_type="日常病程记录",
            primary_tables=("daily_course_record",),
            fallback_tables=("senior_course_record",),
        )
    return groups


def _row_has_meaningful_content(table_name: str, row: dict[str, Any]) -> bool:
    try:
        assembled = assemble_document(table_name, dict(row))
        if _safe_text(getattr(assembled, "assembled_text", "")):
            return True
    except Exception:
        pass

    for key, value in row.items():
        field_name = _safe_text(key).lower()
        if not field_name:
            continue
        if field_name in {"visit_id", "patient_id", "institute_id", "document_id", "mr_no", "inpat_no"}:
            continue
        if _contains_any(field_name, ("content", "process", "summary", "discussion", "opinion", "result", "plan", "reason", "analysis", "diagnosis", "note")):
            text = _safe_text(value)
            if len(text) >= 8 and not text.isdigit():
                return True
    return False


def _probe_group(
    *,
    group: DocumentGroup,
    visit_id: str,
    local_store: LocalPGStore,
    snapshot_stores: list[SnapshotCSVStore],
) -> dict[str, Any]:
    checks: list[SourceCheck] = []
    for table_name in group.primary_tables:
        checks.append(local_store.probe(table_name=table_name, visit_id=visit_id, is_fallback=False))
        for snapshot_store in snapshot_stores:
            checks.append(snapshot_store.probe(table_name=table_name, visit_id=visit_id, is_fallback=False))
    for table_name in group.fallback_tables:
        checks.append(local_store.probe(table_name=table_name, visit_id=visit_id, is_fallback=True))
        for snapshot_store in snapshot_stores:
            checks.append(snapshot_store.probe(table_name=table_name, visit_id=visit_id, is_fallback=True))

    primary_has_content = any(check.status == "content" and not check.is_fallback for check in checks)
    fallback_has_content = any(check.status == "content" and check.is_fallback for check in checks)
    primary_missing = not primary_has_content
    return {
        "logical_type": group.logical_type,
        "checks": checks,
        "primary_missing": primary_missing,
        "fallback_available": fallback_has_content,
    }


def _select_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    selected = rows
    sheet2_row_ids = {_safe_text(item) for item in list(args.sheet2_row_id or []) if _safe_text(item)}
    visit_ids = {_safe_text(item) for item in list(args.visit_id or []) if _safe_text(item)}
    primary_rule_ids = {_safe_text(item).upper() for item in list(args.primary_rule_id or []) if _safe_text(item)}

    if sheet2_row_ids:
        selected = [row for row in selected if _safe_text(row.get("sheet2_row_id")) in sheet2_row_ids]
    if visit_ids:
        selected = [row for row in selected if _safe_text(row.get("visit_id")) in visit_ids]
    if primary_rule_ids:
        selected = [
            row
            for row in selected
            if _safe_text(row.get("primary_rule_id")).upper() in primary_rule_ids
        ]
    if args.only_skip_candidates:
        selected = [row for row in selected if "skip" in _safe_text(row.get("next_action")).lower()]
    if args.limit and args.limit > 0:
        selected = selected[: args.limit]
    return selected


def _build_record_result(
    *,
    row: dict[str, Any],
    local_store: LocalPGStore,
    snapshot_stores: list[SnapshotCSVStore],
) -> dict[str, Any]:
    visit_id = _safe_text(row.get("visit_id"))
    manual_issue_text = _normalize_issue_text(row.get("manual_issue_text"))
    issue_groups = _infer_document_groups(row)

    base_result: dict[str, Any] = {
        "sheet2_row_id": _safe_text(row.get("sheet2_row_id")),
        "visit_id": visit_id,
        "patient_name": _safe_text(row.get("patient_name")),
        "manual_issue_text": manual_issue_text,
        "issue_family": _safe_text(row.get("issue_family")),
        "primary_rule_id": _safe_text(row.get("primary_rule_id")),
        "secondary_rule_ids": _safe_text(row.get("secondary_rule_ids")),
    }
    if not manual_issue_text:
        return {
            **base_result,
            "skip_allowed": False,
            "missing_document_types": [],
            "checked_sources": ["manual_issue_text_missing"],
            "fallback_available": False,
            "suggested_skip_reason": "缺人工问题原文，不能判定 skip",
            "target_document_types": [],
        }
    if not visit_id:
        return {
            **base_result,
            "skip_allowed": False,
            "missing_document_types": [],
            "checked_sources": ["visit_id_missing"],
            "fallback_available": False,
            "suggested_skip_reason": "缺 visit_id，无法核对本地 PG 与快照",
            "target_document_types": [group.logical_type for group in issue_groups],
        }
    if not issue_groups:
        return {
            **base_result,
            "skip_allowed": False,
            "missing_document_types": [],
            "checked_sources": ["target_document_type_unresolved"],
            "fallback_available": False,
            "suggested_skip_reason": "未识别目标原始文书类型，需人工判定",
            "target_document_types": [],
        }

    group_results = [
        _probe_group(
            group=group,
            visit_id=visit_id,
            local_store=local_store,
            snapshot_stores=snapshot_stores,
        )
        for group in issue_groups
    ]
    missing_document_types = [
        _safe_text(item.get("logical_type"))
        for item in group_results
        if bool(item.get("primary_missing"))
    ]
    fallback_available = any(bool(item.get("fallback_available")) for item in group_results)
    has_any_primary_content = any(not bool(item.get("primary_missing")) for item in group_results)
    checked_sources = _unique_in_order(
        [
            check.summary_token()
            for item in group_results
            for check in list(item.get("checks") or [])
        ]
    )
    skip_allowed = bool(missing_document_types) and not has_any_primary_content and not fallback_available

    if skip_allowed:
        suggested_skip_reason = (
            "本地 PG、release/0426、release/0426_full_auto 均缺 "
            f"{'、'.join(missing_document_types)}，且无可回退文书，可判 skip"
        )
    elif fallback_available:
        suggested_skip_reason = (
            f"{'、'.join(missing_document_types) or '目标原始文书'} 原表缺失或无正文，但存在可回退文书，不建议 skip"
        )
    else:
        suggested_skip_reason = "已在至少一个数据源找到目标原始文书，不建议 skip"

    return {
        **base_result,
        "skip_allowed": skip_allowed,
        "missing_document_types": missing_document_types,
        "checked_sources": checked_sources,
        "fallback_available": fallback_available,
        "suggested_skip_reason": suggested_skip_reason,
        "target_document_types": [group.logical_type for group in issue_groups],
    }


def _to_csv_row(result: dict[str, Any]) -> dict[str, str]:
    return {
        "sheet2_row_id": _safe_text(result.get("sheet2_row_id")),
        "visit_id": _safe_text(result.get("visit_id")),
        "patient_name": _safe_text(result.get("patient_name")),
        "manual_issue_text": _safe_text(result.get("manual_issue_text")),
        "issue_family": _safe_text(result.get("issue_family")),
        "primary_rule_id": _safe_text(result.get("primary_rule_id")),
        "skip_allowed": _csv_bool(bool(result.get("skip_allowed"))),
        "missing_document_types": "|".join(list(result.get("missing_document_types") or [])),
        "checked_sources": "; ".join(list(result.get("checked_sources") or [])),
        "fallback_available": _csv_bool(bool(result.get("fallback_available"))),
        "suggested_skip_reason": _safe_text(result.get("suggested_skip_reason")),
        "target_document_types": "|".join(list(result.get("target_document_types") or [])),
    }


def _write_results_csv(path: Path, results: list[dict[str, Any]]) -> None:
    fieldnames = [
        "sheet2_row_id",
        "visit_id",
        "patient_name",
        "manual_issue_text",
        "issue_family",
        "primary_rule_id",
        "skip_allowed",
        "missing_document_types",
        "checked_sources",
        "fallback_available",
        "suggested_skip_reason",
        "target_document_types",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for result in results:
            writer.writerow(_to_csv_row(result))


def _writeback_rows(
    *,
    source_rows: list[dict[str, Any]],
    source_fieldnames: list[str],
    results: list[dict[str, Any]],
    output_path: Path,
) -> None:
    result_map = {_safe_text(item.get("sheet2_row_id")): item for item in results}
    fieldnames = list(source_fieldnames)
    for field_name in WRITEBACK_FIELDS:
        if field_name not in fieldnames:
            fieldnames.append(field_name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in source_rows:
            merged = dict(row)
            result = result_map.get(_safe_text(row.get("sheet2_row_id")))
            if result is not None:
                skip_allowed = bool(result.get("skip_allowed"))
                suggested_skip_reason = _safe_text(result.get("suggested_skip_reason"))
                missing_document_types = list(result.get("missing_document_types") or [])
                target_document_types = list(result.get("target_document_types") or [])
                merged["verification_status"] = "skip" if skip_allowed else _safe_text(merged.get("verification_status"))
                merged["evidence_status"] = "document_missing" if skip_allowed else _safe_text(merged.get("evidence_status"))
                merged["evidence_summary"] = (
                    f"缺文书：{'|'.join(missing_document_types or target_document_types)}"
                    if skip_allowed
                    else _safe_text(merged.get("evidence_summary"))
                )
                merged["skip_reason"] = suggested_skip_reason if skip_allowed else _safe_text(merged.get("skip_reason"))
                merged["next_action"] = "已确认skip" if skip_allowed else _safe_text(merged.get("next_action"))
                merged["skip_allowed"] = _csv_bool(bool(result.get("skip_allowed")))
                merged["missing_document_types"] = "|".join(missing_document_types)
                merged["checked_sources"] = "; ".join(list(result.get("checked_sources") or []))
                merged["fallback_available"] = _csv_bool(bool(result.get("fallback_available")))
                merged["suggested_skip_reason"] = suggested_skip_reason
            writer.writerow(merged)


def _build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "record_count": len(results),
        "skip_allowed_count": sum(1 for item in results if bool(item.get("skip_allowed"))),
        "fallback_available_count": sum(1 for item in results if bool(item.get("fallback_available"))),
        "missing_document_type_breakdown": {
            key: value
            for key, value in _count_values(item for result in results for item in list(result.get("missing_document_types") or [])).items()
        },
    }


def _count_values(values: Any) -> dict[str, int]:
    counter: dict[str, int] = {}
    for value in values:
        text = _safe_text(value)
        if not text:
            continue
        counter[text] = counter.get(text, 0) + 1
    return counter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="探测 Sheet2 逐条台账缺文书与 skip 条件")
    parser.add_argument("--input-csv", default=str(DEFAULT_LEDGER_CSV), help="逐条台账 CSV 路径")
    parser.add_argument("--sheet2-row-id", action="append", default=[], help="按 sheet2_row_id 过滤，可重复传入")
    parser.add_argument("--visit-id", action="append", default=[], help="按 visit_id 过滤，可重复传入")
    parser.add_argument("--primary-rule-id", action="append", default=[], help="按 primary_rule_id 过滤，可重复传入")
    parser.add_argument("--limit", type=int, default=0, help="最多处理前 N 条")
    parser.add_argument("--only-skip-candidates", action="store_true", help="只处理 next_action 含 skip 的条目")
    parser.add_argument("--output-csv", default="", help="把探测结果另存为 CSV")
    parser.add_argument("--output-json", default="", help="把探测结果另存为 JSON")
    parser.add_argument("--writeback-csv", default="", help="回写带新字段的完整台账 CSV")
    parser.add_argument("--writeback-in-place", action="store_true", help="直接回写到输入 CSV")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_csv = Path(args.input_csv).resolve()
    fieldnames, rows = _read_csv_rows(input_csv)
    selected_rows = _select_rows(rows, args)
    if not selected_rows:
        raise SystemExit("未选中任何台账记录")

    local_store = LocalPGStore()
    snapshot_stores = [
        SnapshotCSVStore(DEFAULT_RELEASE_0426_DIR, "release_0426"),
        SnapshotCSVStore(DEFAULT_RELEASE_0426_FULL_AUTO_DIR, "release_0426_full_auto"),
    ]
    results = [
        _build_record_result(
            row=row,
            local_store=local_store,
            snapshot_stores=snapshot_stores,
        )
        for row in selected_rows
    ]
    payload = {
        "input_csv": str(input_csv),
        "summary": _build_summary(results),
        "results": results,
    }

    if args.output_csv:
        _write_results_csv(Path(args.output_csv).resolve(), results)
    if args.output_json:
        output_json_path = Path(args.output_json).resolve()
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    if args.writeback_csv or args.writeback_in_place:
        writeback_path = input_csv if args.writeback_in_place else Path(args.writeback_csv).resolve()
        _writeback_rows(
            source_rows=rows,
            source_fieldnames=fieldnames,
            results=results,
            output_path=writeback_path,
        )

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
