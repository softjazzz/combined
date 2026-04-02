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
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import MetaData, Table, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

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

    async def persist_analysis(
        self,
        result: Dict[str, Any],
        *,
        actor: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(self._persist_analysis_sync, result, actor)

    def _persist_analysis_sync(
        self,
        result: Dict[str, Any],
        actor: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized = self._normalize_result(result)
        session: Session = self._session_factory()
        try:
            actor_id = str((actor or {}).get("id") or (actor or {}).get("user_id") or "")
            actor_name = str((actor or {}).get("display_name") or (actor or {}).get("username") or actor_id or "system")

            qc_result_row = self._persist_qc_result(session, normalized, actor_id)
            defect_summary = self._persist_qc_defects(session, normalized, qc_result_row["id"], actor_id, actor_name)
            notification_summary = self._persist_notification(
                session,
                normalized,
                qc_result_row,
                defect_summary,
                actor_id=actor_id,
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
    ) -> Dict[str, Any]:
        table = _table("qc", "qc_defects")
        record_id = result["record_id"]
        department = _safe_text(result["metadata"].get("department") or "")
        issues = [issue for issue in result["issues"] if isinstance(issue, dict)]
        existing_rows = session.execute(
            table.select().where(table.c.record_id == record_id)
        ).mappings().all()
        existing_by_id = {str(row["id"]): dict(row) for row in existing_rows}
        active_existing_ids = {
            str(row["id"])
            for row in existing_rows
            if str(row.get("status") or "").lower() != "completed"
        }

        created = 0
        updated = 0
        resolved = 0
        touched_ids: set[str] = set()
        defect_ids: List[str] = []

        for issue in issues:
            defect_id, identity_key = self._defect_identity(record_id, issue)
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
                "status": "pending",
                "updated_at": _now_utc(),
            }
            existing = existing_by_id.get(defect_id)
            if existing:
                session.execute(
                    table.update()
                    .where(table.c.id == defect_id)
                    .values({
                        key: _value_for_column(table.c[key], value)
                        for key, value in payload.items()
                        if key in table.c and key != "id"
                    })
                )
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
            session.execute(stmt)
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
            session.execute(
                table.update()
                .where(and_(table.c.id == defect_id, table.c.status != "completed"))
                .values({
                    "status": "completed",
                    "updated_at": _now_utc(),
                })
            )
            resolved += 1
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
    ) -> Dict[str, Any]:
        table = _table("qc", "notifications")
        workflow_type = result["workflow_type"]
        workflow_label = self._workflow_label(workflow_type)
        record_id = result["record_id"]
        recipient_id = actor_id or "system"
        notification_id = _stable_uuid("qc_notification", workflow_type, result.get("visit_id") or record_id, recipient_id)
        existing = session.execute(table.select().where(table.c.id == notification_id).limit(1)).mappings().first()

        has_issues = result["defect_count"] > 0
        if has_issues:
            title = f"{workflow_label}发现问题"
            content = (
                f"病历 {result.get('visit_id') or record_id} {workflow_label}完成，"
                f"当前有 {defect_summary['active_count']} 条待处理问题。"
            )
            severity = "warning"
            is_read = False
            read_at = None
        else:
            if not existing:
                return {"id": None, "created": False, "updated": False}
            title = f"{workflow_label}最近一次复核已通过"
            content = f"病历 {result.get('visit_id') or record_id} 最近一次{workflow_label}未发现问题。"
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

        if existing:
            session.execute(
                table.update()
                .where(table.c.id == notification_id)
                .values({
                    key: _value_for_column(table.c[key], value)
                    for key, value in payload.items()
                    if key in table.c and key != "id"
                })
            )
            return {"id": notification_id, "created": False, "updated": True}

        stmt = pg_insert(table).values({
            key: _value_for_column(table.c[key], value)
            for key, value in payload.items()
            if key in table.c
        })
        session.execute(stmt)
        return {"id": notification_id, "created": True, "updated": False}


default_qc_persistence_service = QCPersistenceService()
