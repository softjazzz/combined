from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy import text

from app.core.roles import effective_roles
from app.database.connection import SessionLocal
from app.services.qc_agent.tools import assert_no_sensitive_output


_ADMIN_ROLES = frozenset({"admin", "super_admin", "sync_admin"})


def _now() -> datetime:
    return datetime.utcnow()


def _json(value: Any) -> str:
    assert_no_sensitive_output(value if value is not None else {})
    return json.dumps(value if value is not None else {}, ensure_ascii=False, default=str)


def _loads(value: Any) -> Dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        data = json.loads(str(value))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _user_id(user: Dict[str, Any] | None) -> str:
    if not isinstance(user, dict):
        return ""
    return str(user.get("id") or user.get("user_id") or user.get("email") or "").strip()


def _is_admin_user(user: Dict[str, Any] | None) -> bool:
    if not isinstance(user, dict):
        return False
    roles = set(effective_roles(user.get("roles")))
    single_role = str(user.get("role") or "").strip()
    if single_role:
        roles.update(effective_roles([single_role]))
    return bool(roles & _ADMIN_ROLES)


def _assert_session_owner(row_user_id: Any, current_user: Dict[str, Any] | None) -> None:
    """强制校验会话归属：非本人且非管理员一律拒绝 403。"""
    if _is_admin_user(current_user):
        return
    uid = _user_id(current_user)
    owner = str(row_user_id or "").strip()
    if not uid or not owner or owner != uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问或修改其他用户的 qc_agent 会话",
        )


def _is_sqlite(session: Any) -> bool:
    try:
        bind = session.get_bind()
        return getattr(getattr(bind, "dialect", None), "name", "") == "sqlite"
    except Exception:
        return False


def _tbl(session: Any, name: str) -> str:
    return name if _is_sqlite(session) else f"qc.{name}"


class QCAgentSessionStore:
    """qc_agent 最小会话与 trace 持久化。"""

    def __init__(self, session_factory: Any = None) -> None:
        self._session_factory = session_factory or SessionLocal
        if self._session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="数据库未配置，无法使用 qc_agent 会话存储",
            )

    def _ensure_tables(self, session: Any) -> None:
        sqlite_mode = _is_sqlite(session)
        pk_col = "INTEGER PRIMARY KEY AUTOINCREMENT" if sqlite_mode else "BIGSERIAL PRIMARY KEY"
        if not sqlite_mode:
            session.execute(text("CREATE SCHEMA IF NOT EXISTS qc"))
        t_sessions = _tbl(session, "qc_agent_sessions")
        t_messages = _tbl(session, "qc_agent_messages")
        t_runs = _tbl(session, "qc_agent_runs")
        t_confirmations = _tbl(session, "qc_agent_confirmations")
        session.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {t_sessions} (
                    id {pk_col},
                    session_id VARCHAR(64) UNIQUE NOT NULL,
                    user_id VARCHAR(128) NOT NULL DEFAULT '',
                    title VARCHAR(255) NOT NULL DEFAULT '',
                    status VARCHAR(32) NOT NULL DEFAULT 'active',
                    current_visit_id VARCHAR(64) NOT NULL DEFAULT '',
                    current_patient_id VARCHAR(64) NOT NULL DEFAULT '',
                    last_run_id VARCHAR(64) NOT NULL DEFAULT '',
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        session.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {t_messages} (
                    id {pk_col},
                    session_id VARCHAR(64) NOT NULL,
                    run_id VARCHAR(64) NOT NULL DEFAULT '',
                    role VARCHAR(32) NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    response_status VARCHAR(32) NOT NULL DEFAULT '',
                    result_type VARCHAR(64) NOT NULL DEFAULT '',
                    created_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        session.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {t_runs} (
                    run_id VARCHAR(64) PRIMARY KEY,
                    session_id VARCHAR(64) NOT NULL,
                    user_id VARCHAR(128) NOT NULL DEFAULT '',
                    parsed_intent TEXT NOT NULL DEFAULT '{{}}',
                    plan TEXT NOT NULL DEFAULT '[]',
                    result_summary TEXT NOT NULL DEFAULT '{{}}',
                    warnings TEXT NOT NULL DEFAULT '[]',
                    error_summary TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        session.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {t_confirmations} (
                    id {pk_col},
                    session_id VARCHAR(64) NOT NULL,
                    run_id VARCHAR(64) NOT NULL,
                    confirmation_type VARCHAR(64) NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{{}}',
                    expires_at TIMESTAMP NOT NULL,
                    resolved_at TIMESTAMP NULL
                )
                """
            )
        )

    def assert_session_access(
        self,
        session_id: str,
        *,
        current_user: Dict[str, Any] | None,
    ) -> None:
        """若 session_id 已存在，强制校验其归属权（本人或管理员）。"""
        sid = str(session_id or "").strip()
        if not sid:
            return
        with self._session_factory() as session:
            self._ensure_tables(session)
            t_sessions = _tbl(session, "qc_agent_sessions")
            row = session.execute(
                text(f"SELECT user_id FROM {t_sessions} WHERE session_id = :session_id LIMIT 1"),
                {"session_id": sid},
            ).mappings().first()
            if row is not None:
                _assert_session_owner(row.get("user_id"), current_user)

    def create_session(
        self,
        *,
        current_user: Dict[str, Any] | None,
        session_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        sid = session_id or str(uuid.uuid4())
        context = user_context or {}
        now = _now()
        with self._session_factory() as session:
            self._ensure_tables(session)
            t_sessions = _tbl(session, "qc_agent_sessions")
            existing = session.execute(
                text(f"SELECT user_id FROM {t_sessions} WHERE session_id = :session_id LIMIT 1"),
                {"session_id": sid},
            ).mappings().first()
            if existing is not None:
                _assert_session_owner(existing.get("user_id"), current_user)
                session.execute(
                    text(
                        f"""
                        UPDATE {t_sessions}
                        SET title = COALESCE(NULLIF(:title, ''), title),
                            current_visit_id = COALESCE(NULLIF(:visit_id, ''), current_visit_id),
                            current_patient_id = COALESCE(NULLIF(:patient_id, ''), current_patient_id),
                            updated_at = :updated_at
                        WHERE session_id = :session_id
                        """
                    ),
                    {
                        "session_id": sid,
                        "title": title or "",
                        "visit_id": str(context.get("visit_id") or ""),
                        "patient_id": str(context.get("patient_id") or ""),
                        "updated_at": now,
                    },
                )
            else:
                session.execute(
                    text(
                        f"""
                        INSERT INTO {t_sessions} (
                            session_id, user_id, title, status, current_visit_id,
                            current_patient_id, last_run_id, created_at, updated_at
                        )
                        VALUES (
                            :session_id, :user_id, :title, 'active', :visit_id,
                            :patient_id, '', :created_at, :updated_at
                        )
                        """
                    ),
                    {
                        "session_id": sid,
                        "user_id": _user_id(current_user),
                        "title": title or "",
                        "visit_id": str(context.get("visit_id") or ""),
                        "patient_id": str(context.get("patient_id") or ""),
                        "created_at": now,
                        "updated_at": now,
                    },
                )
            session.commit()
        return self.get_session(sid, current_user=current_user)

    def get_session(
        self,
        session_id: str,
        *,
        current_user: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        with self._session_factory() as session:
            self._ensure_tables(session)
            t_sessions = _tbl(session, "qc_agent_sessions")
            t_messages = _tbl(session, "qc_agent_messages")
            t_confirmations = _tbl(session, "qc_agent_confirmations")
            row = session.execute(
                text(f"SELECT * FROM {t_sessions} WHERE session_id = :session_id LIMIT 1"),
                {"session_id": session_id},
            ).mappings().first()
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="qc_agent 会话不存在")
            _assert_session_owner(row.get("user_id"), current_user)
            messages = session.execute(
                text(
                    f"""
                    SELECT role, message, response_status, result_type, run_id, created_at
                    FROM {t_messages}
                    WHERE session_id = :session_id
                    ORDER BY id DESC
                    LIMIT 30
                    """
                ),
                {"session_id": session_id},
            ).mappings().all()
            pending = session.execute(
                text(
                    f"""
                    SELECT confirmation_type, payload, run_id, expires_at
                    FROM {t_confirmations}
                    WHERE session_id = :session_id
                      AND resolved_at IS NULL
                      AND expires_at > :now
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"session_id": session_id, "now": _now()},
            ).mappings().first()
        return {
            "session_id": str(row.get("session_id") or ""),
            "status": str(row.get("status") or "active"),
            "current_visit_id": str(row.get("current_visit_id") or ""),
            "current_patient_id": str(row.get("current_patient_id") or ""),
            "title": str(row.get("title") or ""),
            "messages": [dict(item) for item in reversed(messages)],
            "pending_confirmation": (
                {
                    "confirmation_type": str(pending.get("confirmation_type") or ""),
                    "payload": _loads(pending.get("payload")),
                    "run_id": str(pending.get("run_id") or ""),
                    "expires_at": str(pending.get("expires_at") or ""),
                }
                if pending
                else None
            ),
        }

    def delete_session(
        self,
        session_id: str,
        *,
        current_user: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        with self._session_factory() as session:
            self._ensure_tables(session)
            t_sessions = _tbl(session, "qc_agent_sessions")
            t_messages = _tbl(session, "qc_agent_messages")
            t_runs = _tbl(session, "qc_agent_runs")
            t_confirmations = _tbl(session, "qc_agent_confirmations")
            row = session.execute(
                text(f"SELECT session_id, user_id FROM {t_sessions} WHERE session_id = :session_id LIMIT 1"),
                {"session_id": session_id},
            ).mappings().first()
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="qc_agent 会话不存在")
            _assert_session_owner(row.get("user_id"), current_user)
            session.execute(
                text(f"DELETE FROM {t_confirmations} WHERE session_id = :session_id"),
                {"session_id": session_id},
            )
            session.execute(
                text(f"DELETE FROM {t_messages} WHERE session_id = :session_id"),
                {"session_id": session_id},
            )
            session.execute(
                text(f"DELETE FROM {t_runs} WHERE session_id = :session_id"),
                {"session_id": session_id},
            )
            session.execute(
                text(f"DELETE FROM {t_sessions} WHERE session_id = :session_id"),
                {"session_id": session_id},
            )
            session.commit()
        return {"session_id": session_id, "deleted": True}

    def record_chat(
        self,
        *,
        current_user: Dict[str, Any] | None,
        request_message: str,
        response: Any,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        sid = str(getattr(response, "session_id", None) or "")
        if not sid:
            return
        result = getattr(response, "result", None)
        result_data = result.model_dump() if hasattr(result, "model_dump") else (result or {})
        result_type = str(result_data.get("result_type") or "")
        parsed_intent = getattr(response, "parsed_intent", {})
        plan = getattr(response, "plan", [])
        run_id = str(getattr(response, "run_id", "") or "")
        warnings = list(getattr(response, "warnings", []) or [])
        now = _now()
        context = user_context or {}
        with self._session_factory() as session:
            self._ensure_tables(session)
            t_sessions = _tbl(session, "qc_agent_sessions")
            t_messages = _tbl(session, "qc_agent_messages")
            t_runs = _tbl(session, "qc_agent_runs")
            t_confirmations = _tbl(session, "qc_agent_confirmations")
            existing = session.execute(
                text(f"SELECT user_id FROM {t_sessions} WHERE session_id = :session_id LIMIT 1"),
                {"session_id": sid},
            ).mappings().first()
            if existing is not None:
                _assert_session_owner(existing.get("user_id"), current_user)
                session.execute(
                    text(
                        f"""
                        UPDATE {t_sessions}
                        SET current_visit_id = COALESCE(NULLIF(:visit_id, ''), current_visit_id),
                            current_patient_id = COALESCE(NULLIF(:patient_id, ''), current_patient_id),
                            last_run_id = :run_id,
                            updated_at = :updated_at
                        WHERE session_id = :session_id
                        """
                    ),
                    {
                        "session_id": sid,
                        "visit_id": str(context.get("visit_id") or ""),
                        "patient_id": str(context.get("patient_id") or ""),
                        "run_id": run_id,
                        "updated_at": now,
                    },
                )
            else:
                session.execute(
                    text(
                        f"""
                        INSERT INTO {t_sessions} (
                            session_id, user_id, title, status, current_visit_id,
                            current_patient_id, last_run_id, created_at, updated_at
                        )
                        VALUES (
                            :session_id, :user_id, :title, 'active', :visit_id,
                            :patient_id, :run_id, :created_at, :updated_at
                        )
                        """
                    ),
                    {
                        "session_id": sid,
                        "user_id": _user_id(current_user),
                        "title": request_message[:80],
                        "visit_id": str(context.get("visit_id") or ""),
                        "patient_id": str(context.get("patient_id") or ""),
                        "run_id": run_id,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
            session.execute(
                text(
                    f"""
                    INSERT INTO {t_messages} (
                        session_id, run_id, role, message, response_status, result_type, created_at
                    )
                    VALUES (:session_id, :run_id, 'user', :message, '', '', :created_at)
                    """
                ),
                {"session_id": sid, "run_id": run_id, "message": request_message, "created_at": now},
            )
            session.execute(
                text(
                    f"""
                    INSERT INTO {t_messages} (
                        session_id, run_id, role, message, response_status, result_type, created_at
                    )
                    VALUES (:session_id, :run_id, 'assistant', :message, :status, :result_type, :created_at)
                    """
                ),
                {
                    "session_id": sid,
                    "run_id": run_id,
                    "message": str(getattr(response, "status", "")),
                    "status": str(getattr(response, "status", "")),
                    "result_type": result_type,
                    "created_at": now,
                },
            )
            parsed_payload = parsed_intent.model_dump() if hasattr(parsed_intent, "model_dump") else parsed_intent
            plan_payload = [item.model_dump() if hasattr(item, "model_dump") else item for item in plan]
            session.execute(
                text(
                    f"""
                    INSERT INTO {t_runs} (
                        run_id, session_id, user_id, parsed_intent, plan,
                        result_summary, warnings, error_summary, created_at
                    )
                    VALUES (
                        :run_id, :session_id, :user_id, :parsed_intent, :plan,
                        :result_summary, :warnings, :error_summary, :created_at
                    )
                    ON CONFLICT (run_id) DO NOTHING
                    """
                ),
                {
                    "run_id": run_id,
                    "session_id": sid,
                    "user_id": _user_id(current_user),
                    "parsed_intent": _json(parsed_payload),
                    "plan": _json(plan_payload),
                    "result_summary": _json(result_data.get("summary") or {}),
                    "warnings": _json(warnings),
                    "error_summary": "; ".join(warnings[:3]),
                    "created_at": now,
                },
            )
            if getattr(response, "status", "") == "needs_confirmation":
                session.execute(
                    text(
                        f"""
                        INSERT INTO {t_confirmations} (
                            session_id, run_id, confirmation_type, payload, expires_at, resolved_at
                        )
                        VALUES (:session_id, :run_id, :confirmation_type, :payload, :expires_at, NULL)
                        """
                    ),
                    {
                        "session_id": sid,
                        "run_id": run_id,
                        "confirmation_type": "record_selection",
                        "payload": _json({"candidates": getattr(response, "candidates", []) or []}),
                        "expires_at": now + timedelta(hours=2),
                    },
                )
            session.commit()

    def resolve_pending_confirmation(
        self,
        *,
        session_id: str,
        current_user: Dict[str, Any] | None = None,
    ) -> None:
        with self._session_factory() as session:
            self._ensure_tables(session)
            t_sessions = _tbl(session, "qc_agent_sessions")
            t_confirmations = _tbl(session, "qc_agent_confirmations")
            if current_user is not None:
                row = session.execute(
                    text(f"SELECT user_id FROM {t_sessions} WHERE session_id = :session_id LIMIT 1"),
                    {"session_id": session_id},
                ).mappings().first()
                if row is not None:
                    _assert_session_owner(row.get("user_id"), current_user)
            session.execute(
                text(
                    f"""
                    UPDATE {t_confirmations}
                    SET resolved_at = :resolved_at
                    WHERE session_id = :session_id
                      AND resolved_at IS NULL
                    """
                ),
                {"session_id": session_id, "resolved_at": _now()},
            )
            session.commit()
