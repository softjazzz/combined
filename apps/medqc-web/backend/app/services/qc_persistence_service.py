"""QC persistence service.

Materializes analysis results into:
- qc.qc_results  : execution history
- qc.qc_defects  : latest state per workflow + visit + rule/location/category
- qc.notifications: latest aggregate message per workflow + visit + recipient
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import MetaData, Table, and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy.sql.dml import Update

from ..database.connection import SessionLocal, engine


def _now_utc() -> datetime:
    return datetime.utcnow()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _value_for_column(column: Any, value: Any) -> Any:
    if value is None:
        return None
    col_type_name = column.type.__class__.__name__.lower()
    if isinstance(value, (dict, list)):
        return value if "json" in col_type_name else _json_dumps(value)
    if isinstance(value, datetime):
        return value
    return value


def _stable_uuid(*parts: Any) -> str:
    normalized = "|".join("" if part is None else str(part) for part in parts)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, normalized))


def _as_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _normalize_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    metadata = issue.get("metadata") if isinstance(issue.get("metadata"), dict) else {}
    return {
        "rule_code": _safe_text(issue.get("rule_code") or issue.get("rule_id") or issue.get("id") or issue.get("rule_name") or "unknown_rule"),
        "rule_name": _safe_text(issue.get("rule_name") or issue.get("title") or issue.get("rule_code") or "未知规则"),
        "description": _safe_text(issue.get("description") or issue.get("message") or ""),
        "severity": _safe_text(issue.get("severity") or "warning").lower(),
        "category": _safe_text(issue.get("category") or metadata.get("workflow_type") or "general"),
        "location": _safe_text(issue.get("location") or issue.get("field_name") or "病历正文"),
        "suggestion": _safe_text(issue.get("suggestion") or issue.get("recommendation") or "请补充相关记录"),
        "evidence": issue.get("evidence"),
        "metadata": metadata,
    }


_VERIFIED_SOURCES = frozenset({
    "frontpage_formal_qc", "coding_qc", "settlement_qc", "settlement_generate_qc"
})
_SOURCE_WORKFLOWS = {
    "frontpage_formal_qc": "frontpage",
    "coding_qc": "coding",
    "settlement_qc": "settlement",
    "settlement_generate_qc": "settlement",
}


@dataclass(frozen=True)
class VerifiedQCIdentity:
    institute_id: str
    patient_id: str
    visit_id: str
    source_key: str

    def __post_init__(self) -> None:
        for name in ("institute_id", "patient_id", "visit_id", "source_key"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError(f"verified QC {name} must be a nonblank canonical string")
        if self.source_key not in _VERIFIED_SOURCES:
            raise ValueError(f"unsupported verified QC source: {self.source_key}")

    def columns(self) -> Dict[str, Any]:
        return {
            "identity_version": 1,
            "source_key": self.source_key,
            "institute_id": self.institute_id,
            "patient_id": self.patient_id,
            "visit_id": self.visit_id,
        }


@lru_cache(maxsize=8)
def _table(schema: str, table_name: str) -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; persistence unavailable")
    metadata = MetaData()
    return Table(table_name, metadata, schema=schema, autoload_with=engine)


class QCPersistenceService:
    """Persist normalized QC analysis results."""

    def __init__(self, session_factory: Optional[Any] = None) -> None:
        self._session_factory = session_factory or SessionLocal
        if self._session_factory is None:
            raise RuntimeError("DATABASE_URL is not configured; persistence unavailable")

    def _require_verified_identity(
        self, session: Session, result: Dict[str, Any], identity: VerifiedQCIdentity
    ) -> None:
        if not isinstance(identity, VerifiedQCIdentity):
            raise TypeError("verified_identity must be VerifiedQCIdentity")
        metadata = result.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("verified QC requires result metadata")
        for name in ("institute_id", "patient_id", "visit_id"):
            expected = getattr(identity, name)
            if metadata.get(name) != expected or (name in result and result[name] != expected):
                raise ValueError(f"verified QC {name} conflicts with result")
        if metadata.get("data_source") != identity.source_key:
            raise ValueError("verified QC source conflicts with result metadata")
        for source_field in ("source_key", "data_source"):
            if source_field in result and result[source_field] != identity.source_key:
                raise ValueError("verified QC source conflicts with result")
        if "source_key" in metadata and metadata["source_key"] != identity.source_key:
            raise ValueError("verified QC source conflicts with result metadata")
        expected_workflow = _SOURCE_WORKFLOWS[identity.source_key]
        workflows = (result.get("workflow_type"), metadata.get("workflow_type"))
        if all(workflow is None for workflow in workflows):
            raise ValueError("verified QC requires explicit workflow type")
        for workflow in workflows:
            if workflow is not None and workflow != expected_workflow:
                raise ValueError("verified QC source conflicts with workflow type")
        required = set(identity.columns())
        for name in ("qc_results", "qc_defects", "notifications"):
            missing = required - set(_table("qc", name).c.keys())
            if missing:
                raise RuntimeError(f"qc.{name} missing verified identity columns: {sorted(missing)}")
        mr = _table("cdm", "mr")
        if not {"institute_id", "patient_id", "visit_id"} <= set(mr.c.keys()):
            raise RuntimeError("cdm.mr missing case identity columns")
        count = session.execute(
            select(func.count()).select_from(mr).where(
                mr.c.institute_id == identity.institute_id,
                mr.c.patient_id == identity.patient_id,
                mr.c.visit_id == identity.visit_id,
            )
        ).scalar_one()
        if count != 1:
            raise ValueError("verified QC case identity must match exactly one cdm.mr row")

    def _owner_clause(self, table: Table, identity: VerifiedQCIdentity) -> Any:
        return and_(*(table.c[name] == value for name, value in identity.columns().items()))

    async def persist_analysis(
        self,
        result: Dict[str, Any],
        *,
        actor: Optional[Dict[str, Any]] = None,
        verified_identity: Optional[VerifiedQCIdentity] = None,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(self._persist_analysis_sync, result, actor, verified_identity)

    def _persist_analysis_sync(
        self,
        result: Dict[str, Any],
        actor: Optional[Dict[str, Any]] = None,
        verified_identity: Optional[VerifiedQCIdentity] = None,
    ) -> Dict[str, Any]:
        normalized = self._normalize_result(result)
        session: Session = self._session_factory()
        try:
            if verified_identity is not None:
                self._require_verified_identity(session, result, verified_identity)
            actor_id = str((actor or {}).get("id") or (actor or {}).get("user_id") or "")
            actor_name = str((actor or {}).get("display_name") or (actor or {}).get("username") or actor_id or "system")

            qc_result_row = self._persist_qc_result(session, normalized, actor_id, verified_identity)
            defect_summary = self._persist_qc_defects(session, normalized, qc_result_row["id"], actor_id, actor_name, verified_identity)
            notification_summary = self._persist_notification(
                session,
                normalized,
                qc_result_row,
                defect_summary,
                actor_id=actor_id,
                verified_identity=verified_identity,
            )
            session.commit()
            return {
                "qc_result_id": qc_result_row["id"],
                "workflow_type": normalized["workflow_type"],
                "record_id": normalized["record_id"],
                "defects_created": defect_summary["created"],
                "defects_updated": defect_summary["updated"],
                "defects_resolved": defect_summary["resolved"],
                "defect_ids": defect_summary["defect_ids"],
                "notification_created": notification_summary["created"],
                "notification_updated": notification_summary["updated"],
                "notification_id": notification_summary["id"],
            }
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
        issues = [_normalize_issue(item) for item in (result.get("issues") or []) if isinstance(item, dict)]
        overall_score = result.get("overall_score") or result.get("score") or 0
        defect_count = result.get("defect_count")
        workflow_type = _safe_text(metadata.get("workflow_type") or result.get("workflow_type") or "general")
        visit_id = _safe_text(metadata.get("visit_id") or result.get("visit_id") or "")
        patient_id = _safe_text(metadata.get("patient_id") or result.get("patient_id") or "")
        record_id = _safe_text(result.get("record_id") or result.get("recordId") or "")
        if not record_id:
            record_id = f"{workflow_type}::{visit_id or uuid.uuid4().hex[:8]}"
        metadata = {
            **metadata,
            "workflow_type": workflow_type,
            "visit_id": visit_id,
            "patient_id": patient_id,
            "department": _safe_text(
                metadata.get("department")
                or metadata.get("record", {}).get("department") if isinstance(metadata.get("record"), dict) else metadata.get("department")
                or result.get("department")
                or ""
            ),
            "data_source": _safe_text(metadata.get("data_source") or result.get("data_source") or "workstation_v4"),
            "trigger_source": _safe_text(metadata.get("trigger_source") or "workstation_v4"),
        }
        return {
            **result,
            "id": _safe_text(result.get("id") or result.get("analysis_id") or uuid.uuid4()),
            "record_id": record_id,
            "workflow_type": workflow_type,
            "visit_id": visit_id,
            "patient_id": patient_id,
            "overall_score": float(overall_score or 0),
            "grade": _safe_text(result.get("overall_grade") or result.get("grade") or "C"),
            "issues": issues,
            "defect_count": int(defect_count if defect_count is not None else len(issues)),
            "analysis_date": _as_datetime(result.get("analysis_date")) or _now_utc(),
            "metadata": metadata,
        }

    def _persist_qc_result(
        self,
        session: Session,
        result: Dict[str, Any],
        actor_id: str,
        verified_identity: Optional[VerifiedQCIdentity] = None,
    ) -> Dict[str, Any]:
        table = _table("qc", "qc_results")
        requested_id = _safe_text(result.get("id"))
        result_id = requested_id or str(uuid.uuid4())
        existing = session.execute(table.select().where(table.c.id == result_id).limit(1)).mappings().first()
        if existing:
            result_id = str(uuid.uuid4())

        metadata = result["metadata"]
        payload = {
            "id": result_id,
            "record_id": result["record_id"],
            "rule_set": _safe_text(metadata.get("workflow_type") or result.get("rule_set") or "workstation_v4"),
            "overall_score": result["overall_score"],
            "grade": result["grade"],
            "defect_count": result["defect_count"],
            "analysis_engine": _safe_text(metadata.get("engine") or result.get("analysis_engine") or "workstation-v4"),
            "analysis_date": result["analysis_date"],
            "raw_output": _json_dumps(result),
            "created_by": actor_id or None,
            "issues": result["issues"],
            "metadata": metadata,
            "created_at": _now_utc(),
            "updated_at": _now_utc(),
        }
        if verified_identity is not None:
            payload.update(verified_identity.columns())
        stmt = pg_insert(table).values({
            key: _value_for_column(table.c[key], value)
            for key, value in payload.items()
            if key in table.c
        })
        session.execute(stmt)
        return payload

    def _defect_identity(self, record_id: str, issue: Dict[str, Any]) -> Tuple[str, str]:
        identity = [
            record_id,
            issue.get("rule_code") or issue.get("rule_name") or "unknown_rule",
            issue.get("location") or "病历正文",
            issue.get("category") or "general",
        ]
        return _stable_uuid(*identity), "|".join(str(part) for part in identity)

    def _verified_defect_identity(
        self, identity: VerifiedQCIdentity, issue: Dict[str, Any]
    ) -> Tuple[str, str]:
        parts = (
            "qc_defect_v1", identity.source_key, identity.institute_id,
            identity.patient_id, identity.visit_id,
            issue.get("rule_code") or issue.get("rule_name") or "unknown_rule",
            issue.get("location") or "病历正文", issue.get("category") or "general",
        )
        return _stable_uuid(*parts), "|".join(str(part) for part in parts)

    def _is_auto_owned_defect(self, record_id: str, row: Dict[str, Any]) -> bool:
        origin = row.get("origin")
        if origin is not None:
            return origin == "auto"
        # Historical rows have no provenance. Only the old writer's deterministic ID proves ownership.
        expected_id, _ = self._defect_identity(record_id, row)
        return str(row["id"]) == expected_id

    def _executed_defect_scope(
        self, metadata: Dict[str, Any]
    ) -> Optional[Tuple[str, set[str]]]:
        if "executed_defect_scope" not in metadata:
            return None
        scope = metadata["executed_defect_scope"]
        if scope == {"kind": "all"}:
            return "all", set()
        if (
            not isinstance(scope, dict)
            or set(scope) != {"kind", "values"}
            or scope["kind"] not in ("rule_codes", "categories")
            or not isinstance(scope["values"], list)
            or any(
                not isinstance(value, str) or not value.strip()
                for value in scope["values"]
            )
        ):
            raise ValueError("Invalid executed_defect_scope")
        return scope["kind"], set(scope["values"])

    def _matches_defect_scope(
        self, defect: Dict[str, Any], scope: Tuple[str, set[str]]
    ) -> bool:
        kind, values = scope
        if kind == "all":
            return True
        field = "rule_code" if kind == "rule_codes" else "category"
        return defect.get(field) in values

    def _insert_defect_history(
        self,
        session: Session,
        *,
        defect_id: str,
        action: str,
        actor_id: str,
        actor_name: str,
        details: Dict[str, Any],
    ) -> None:
        table = _table("qc", "qc_defect_history")
        payload = {
            "id": str(uuid.uuid4()),
            "defect_id": defect_id,
            "action": action,
            "actor_id": actor_id or None,
            "actor_name": actor_name or "system",
            "details": details,
            "created_at": _now_utc(),
        }
        stmt = pg_insert(table).values({
            key: _value_for_column(table.c[key], value)
            for key, value in payload.items()
            if key in table.c
        })
        session.execute(stmt)

    def _persist_qc_defects(
        self,
        session: Session,
        result: Dict[str, Any],
        result_id: str,
        actor_id: str,
        actor_name: str,
        verified_identity: Optional[VerifiedQCIdentity] = None,
    ) -> Dict[str, Any]:
        table = _table("qc", "qc_defects")
        record_id = result["record_id"]
        department = _safe_text(result["metadata"].get("department") or "")
        executed_scope = self._executed_defect_scope(result["metadata"])
        issues = [issue for issue in result["issues"] if isinstance(issue, dict)]
        if executed_scope is not None and any(
            not self._matches_defect_scope(issue, executed_scope) for issue in issues
        ):
            raise ValueError("QC issue is outside executed_defect_scope")
        if verified_identity is not None:
            existing_filter = self._owner_clause(table, verified_identity)
        else:
            existing_filter = table.c.record_id == record_id
            if "identity_version" in table.c:
                existing_filter = and_(existing_filter, table.c.identity_version.is_(None))
        existing_rows = session.execute(table.select().where(existing_filter)).mappings().all()
        existing_by_id = {str(row["id"]): dict(row) for row in existing_rows}
        open_existing_ids = {
            str(row["id"])
            for row in existing_rows
            if str(row.get("status") or "").lower() != "completed"
        }
        active_existing_ids = {
            str(row["id"])
            for row in existing_rows
            if str(row.get("status") or "").lower() != "completed"
            and (
                row.get("origin") == "auto"
                if verified_identity is not None
                else self._is_auto_owned_defect(record_id, row)
            )
            and executed_scope is not None
            and self._matches_defect_scope(row, executed_scope)
        }

        def restrict_to_observed_owner(stmt: Update, row: Dict[str, Any]) -> Update:
            if verified_identity is not None:
                return stmt.where(self._owner_clause(table, verified_identity), table.c.origin == "auto")
            if "identity_version" in table.c:
                stmt = stmt.where(table.c.identity_version.is_(None))
            previous_origin = row.get("origin")
            if "origin" in table.c:
                stmt = stmt.where(
                    table.c.origin.is_(None)
                    if previous_origin is None else table.c.origin == previous_origin
                )
            if previous_origin is None:
                for name in ("record_id", "rule_code", "rule_name", "location", "category"):
                    value = row.get(name)
                    column = table.c[name]
                    stmt = stmt.where(column.is_(None) if value is None else column == value)
            return stmt

        created = 0
        updated = 0
        resolved = 0
        resolved_ids: set[str] = set()
        touched_ids: set[str] = set()
        defect_ids: List[str] = []

        for issue in issues:
            defect_id, identity_key = (
                self._verified_defect_identity(verified_identity, issue)
                if verified_identity is not None else self._defect_identity(record_id, issue)
            )
            if defect_id in touched_ids:
                continue
            touched_ids.add(defect_id)
            defect_ids.append(defect_id)
            payload = {
                "id": defect_id,
                "result_id": result_id,
                "record_id": record_id,
                "department": department or None,
                "rule_code": issue["rule_code"],
                "rule_name": issue["rule_name"],
                "description": issue["description"],
                "severity": issue["severity"] or "warning",
                "category": issue["category"] or result["workflow_type"],
                "deduct_score": 0.0,
                "location": issue["location"],
                "evidence": issue.get("evidence"),
                "suggestion": issue["suggestion"],
                "origin": "auto",
                "status": "pending",
                "updated_at": _now_utc(),
            }
            if verified_identity is not None:
                payload.update(verified_identity.columns())
            existing = existing_by_id.get(defect_id)
            if existing:
                if not (
                    existing.get("origin") == "auto"
                    if verified_identity is not None
                    else self._is_auto_owned_defect(record_id, existing)
                ):
                    raise RuntimeError(f"Defect {defect_id} is not owned by automatic QC")
                update_stmt = restrict_to_observed_owner(
                    table.update().where(table.c.id == defect_id), existing
                )
                update_result = session.execute(
                    update_stmt.values({
                        key: _value_for_column(table.c[key], value)
                        for key, value in payload.items()
                        if key in table.c and key != "id"
                    })
                )
                if update_result.rowcount != 1:
                    raise RuntimeError(f"Defect {defect_id} changed ownership during automatic QC")
                updated += 1
                self._insert_defect_history(
                    session,
                    defect_id=defect_id,
                    action="auto_updated",
                    actor_id=actor_id,
                    actor_name=actor_name,
                    details={"identity": identity_key, "status": "pending"},
                )
                continue

            payload["created_at"] = _now_utc()
            stmt = pg_insert(table).values({
                key: _value_for_column(table.c[key], value)
                for key, value in payload.items()
                if key in table.c
            }).on_conflict_do_nothing(index_elements=["id"])
            insert_result = session.execute(stmt)
            if insert_result.rowcount != 1:
                raise RuntimeError(f"Defect {defect_id} was concurrently created")
            created += 1
            self._insert_defect_history(
                session,
                defect_id=defect_id,
                action="auto_created",
                actor_id=actor_id,
                actor_name=actor_name,
                details={"identity": identity_key, "status": "pending"},
            )

        for defect_id in sorted(active_existing_ids - touched_ids):
            existing = existing_by_id[defect_id]
            resolve_stmt = table.update().where(
                and_(
                    table.c.id == defect_id,
                    or_(table.c.status.is_(None), table.c.status != "completed"),
                )
            )
            resolve_stmt = restrict_to_observed_owner(resolve_stmt, existing)
            resolve_result = session.execute(
                resolve_stmt.values({
                    "status": "completed",
                    "updated_at": _now_utc(),
                })
            )
            if resolve_result.rowcount != 1:
                raise RuntimeError(f"Defect {defect_id} changed during automatic QC")
            resolved += 1
            resolved_ids.add(defect_id)
            self._insert_defect_history(
                session,
                defect_id=defect_id,
                action="auto_resolved",
                actor_id=actor_id,
                actor_name=actor_name,
                details={"status": "completed"},
            )

        return {
            "created": created,
            "updated": updated,
            "resolved": resolved,
            "defect_ids": defect_ids,
            "active_count": len(touched_ids),
            "remaining_active_count": len((open_existing_ids - resolved_ids) | touched_ids),
        }

    def _workflow_label(self, workflow_type: str) -> str:
        labels = {
            "frontpage": "首页质控",
            "coding": "编码质控",
            "settlement": "控费监测",
        }
        return labels.get(workflow_type, workflow_type or "质控")

    def _persist_notification(
        self,
        session: Session,
        result: Dict[str, Any],
        qc_result_row: Dict[str, Any],
        defect_summary: Dict[str, Any],
        *,
        actor_id: str,
        verified_identity: Optional[VerifiedQCIdentity] = None,
    ) -> Dict[str, Any]:
        table = _table("qc", "notifications")
        workflow_type = result["workflow_type"]
        workflow_label = self._workflow_label(workflow_type)
        record_id = result["record_id"]
        recipient_id = actor_id or "system"
        notification_id = (
            _stable_uuid(
                "qc_notification_v1", verified_identity.source_key,
                verified_identity.institute_id, verified_identity.patient_id,
                verified_identity.visit_id, recipient_id,
            )
            if verified_identity is not None
            else _stable_uuid("qc_notification", workflow_type, result.get("visit_id") or record_id, recipient_id)
        )
        existing = session.execute(table.select().where(table.c.id == notification_id).limit(1)).mappings().first()
        if existing and verified_identity is not None:
            if any(existing.get(name) != value for name, value in verified_identity.columns().items()):
                raise RuntimeError(f"Notification {notification_id} changed verified owner")
            if existing.get("recipient_id") != recipient_id:
                raise RuntimeError(f"Notification {notification_id} changed recipient")

        remaining_active = defect_summary["remaining_active_count"]
        current_issues = len(defect_summary["defect_ids"])
        if remaining_active:
            title = f"{workflow_label}发现问题" if current_issues else f"{workflow_label}仍有待处理问题"
            content = (
                f"病历 {result.get('visit_id') or record_id} {workflow_label}完成，"
                f"本次发现 {current_issues} 条问题，当前有 {remaining_active} 条未关闭缺陷。"
            )
            severity = "warning"
            is_read = False
            read_at = None
        else:
            if not existing:
                return {"id": None, "created": False, "updated": False}
            title = f"{workflow_label}本次执行范围未发现问题"
            content = f"病历 {result.get('visit_id') or record_id} 本次执行范围未发现问题，当前无未关闭缺陷。"
            severity = "info"
            is_read = True
            read_at = _now_utc()

        payload = {
            "id": notification_id,
            "type": f"{workflow_type}_qc",
            "title": title,
            "content": content,
            "record_id": record_id,
            "severity": severity,
            "sender_id": actor_id or None,
            "recipient_id": recipient_id,
            "related_type": "qc_result",
            "related_id": qc_result_row["id"],
            "is_read": is_read,
            "read_at": read_at,
            "created_at": existing.get("created_at") if existing else _now_utc(),
        }
        if verified_identity is not None:
            payload.update(verified_identity.columns())

        if existing:
            update_stmt = table.update().where(table.c.id == notification_id)
            if verified_identity is not None:
                update_stmt = update_stmt.where(
                    self._owner_clause(table, verified_identity),
                    table.c.recipient_id == recipient_id,
                )
            update_result = session.execute(
                update_stmt.values({
                    key: _value_for_column(table.c[key], value)
                    for key, value in payload.items()
                    if key in table.c and key != "id"
                })
            )
            if verified_identity is not None and update_result.rowcount != 1:
                raise RuntimeError(f"Notification {notification_id} changed during automatic QC")
            return {"id": notification_id, "created": False, "updated": True}

        stmt = pg_insert(table).values({
            key: _value_for_column(table.c[key], value)
            for key, value in payload.items()
            if key in table.c
        })
        session.execute(stmt)
        return {"id": notification_id, "created": True, "updated": False}


default_qc_persistence_service = QCPersistenceService()
