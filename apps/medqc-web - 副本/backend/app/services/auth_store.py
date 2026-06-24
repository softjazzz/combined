from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, or_, select, text

from ..database.connection import SessionLocal
from ..database.models.qc import SysUser
from ..storage.memory import users_db


logger = logging.getLogger(__name__)
_PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")
_REQUIRED_AUTH_COLUMNS = {
    "id",
    "username",
    "email",
    "password_hash",
    "display_name",
    "department",
    "role",
    "roles_json",
    "is_active",
    "last_login_at",
    "created_at",
    "phone",
}


def _iso_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat() + "Z"
    text = str(value).strip()
    return text or None


def _derive_username(email: str | None) -> str:
    text = str(email or "").strip()
    if "@" in text:
        return text.split("@", 1)[0]
    return text


def _normalize_roles(role: str | None, roles_json: str | None) -> list[str]:
    if roles_json:
        try:
            parsed = json.loads(roles_json)
            if isinstance(parsed, list):
                roles = [str(item).strip() for item in parsed if str(item).strip()]
                if roles:
                    return roles
        except Exception:
            logger.warning("Failed to parse roles_json for auth user", exc_info=True)
    if role:
        return [str(role)]
    return ["doctor"]


def _memory_overlay(*, email: str | None, user_id: str | None) -> dict[str, Any]:
    email_key = str(email or "").strip().lower()
    if email_key and email_key in users_db:
        return dict(users_db[email_key])
    for user in users_db.values():
        if str(user.get("id") or "").strip() == str(user_id or "").strip():
            return dict(user)
    return {}


def _supports_persistent_auth(session) -> bool:
    try:
        rows = session.execute(
            text(
                """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema IN ('sys', 'public')
              AND table_name = 'sys_users'
                """
            )
        ).fetchall()
    except Exception:
        logger.warning("Failed to inspect sys_users schema; fallback to memory store", exc_info=True)
        return False

    columns = {str(row[0]) for row in rows}
    return _REQUIRED_AUTH_COLUMNS.issubset(columns)


def _normalize_memory_user(user: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(user)
    normalized["username"] = str(normalized.get("username") or "").strip() or _derive_username(
        normalized.get("email")
    )
    roles = normalized.get("roles")
    if not isinstance(roles, list) or not roles:
        role = normalized.get("role")
        normalized["roles"] = [role] if role else ["doctor"]
    normalized.setdefault("avatar", "")
    normalized.setdefault("bio", "")
    normalized.setdefault("phone", None)
    return normalized


def _orm_user_to_dict(user: SysUser) -> dict[str, Any]:
    overlay = _memory_overlay(email=user.email, user_id=user.id)
    roles = _normalize_roles(user.role, user.roles_json)
    username = str(user.username or "").strip() or overlay.get("username") or _derive_username(user.email)
    return {
        "id": user.id,
        "username": username,
        "email": str(user.email or "").strip().lower(),
        "display_name": str(user.display_name or "").strip(),
        "department": str(user.department or "").strip(),
        "roles": roles,
        "role": roles[0] if roles else "doctor",
        "avatar": overlay.get("avatar", ""),
        "phone": str(user.phone or "").strip() or None,
        "bio": overlay.get("bio", ""),
        "created_at": _iso_or_none(user.created_at) or datetime.utcnow().isoformat() + "Z",
        "last_login": _iso_or_none(user.last_login_at),
        "password_hash": str(user.password_hash or ""),
        "is_active": bool(user.is_active),
    }


def _sync_memory_user(user: dict[str, Any]) -> None:
    email = str(user.get("email") or "").strip().lower()
    if not email:
        return
    users_db[email] = {
        "id": user["id"],
        "username": str(user.get("username") or "").strip() or _derive_username(email),
        "email": email,
        "display_name": user.get("display_name") or "",
        "department": user.get("department") or "",
        "roles": list(user.get("roles") or ["doctor"]),
        "password_hash": user.get("password_hash") or "",
        "avatar": user.get("avatar") or "",
        "phone": user.get("phone"),
        "bio": user.get("bio") or "",
        "created_at": user.get("created_at") or datetime.utcnow().isoformat() + "Z",
        "last_login": user.get("last_login"),
    }


def _query_db_user_by_account(account: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        return None

    normalized = str(account or "").strip()
    if not normalized:
        return None

    session = SessionLocal()
    try:
        if not _supports_persistent_auth(session):
            return None

        normalized_lower = normalized.lower()
        conditions = [
            func.lower(SysUser.username) == normalized_lower,
            func.lower(SysUser.email) == normalized_lower,
        ]
        if _PHONE_PATTERN.fullmatch(normalized):
            conditions.insert(1, SysUser.phone == normalized)

        user = session.execute(select(SysUser).where(or_(*conditions)).limit(1)).scalar_one_or_none()
        if user is None or not bool(user.is_active):
            return None
        return _orm_user_to_dict(user)
    except Exception:
        logger.warning("Auth DB account lookup failed; fallback to memory store", exc_info=True)
        return None
    finally:
        session.close()


def _query_db_user_by_subject(subject: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        return None

    normalized = str(subject or "").strip()
    if not normalized:
        return None

    session = SessionLocal()
    try:
        if not _supports_persistent_auth(session):
            return None

        normalized_lower = normalized.lower()
        conditions = [
            SysUser.id == normalized,
            func.lower(SysUser.username) == normalized_lower,
            func.lower(SysUser.email) == normalized_lower,
        ]
        if _PHONE_PATTERN.fullmatch(normalized):
            conditions.append(SysUser.phone == normalized)

        user = session.execute(select(SysUser).where(or_(*conditions)).limit(1)).scalar_one_or_none()
        if user is None or not bool(user.is_active):
            return None
        return _orm_user_to_dict(user)
    except Exception:
        logger.warning("Auth DB subject lookup failed; fallback to memory store", exc_info=True)
        return None
    finally:
        session.close()


def find_user_by_account(account: str) -> dict[str, Any] | None:
    db_user = _query_db_user_by_account(account)
    if db_user is not None:
        return db_user

    normalized = str(account or "").strip()
    normalized_lower = normalized.lower()
    for user in users_db.values():
        candidate = _normalize_memory_user(user)
        if candidate["username"].lower() == normalized_lower:
            return candidate
        if _PHONE_PATTERN.fullmatch(normalized) and str(candidate.get("phone") or "").strip() == normalized:
            return candidate
        if str(candidate.get("email") or "").strip().lower() == normalized_lower:
            return candidate
    return None


def resolve_user_by_subject(subject: str | None) -> dict[str, Any] | None:
    normalized = str(subject or "").strip()
    if not normalized:
        return None

    db_user = _query_db_user_by_subject(normalized)
    if db_user is not None:
        return db_user

    normalized_lower = normalized.lower()
    for user in users_db.values():
        candidate = _normalize_memory_user(user)
        if str(candidate.get("id") or "").strip() == normalized:
            return candidate
        if candidate["username"].lower() == normalized_lower:
            return candidate
        if str(candidate.get("email") or "").strip().lower() == normalized_lower:
            return candidate
        if _PHONE_PATTERN.fullmatch(normalized) and str(candidate.get("phone") or "").strip() == normalized:
            return candidate
    return None


def create_user(
    *,
    email: str,
    username: str | None,
    display_name: str,
    department: str,
    phone: str | None,
    bio: str | None,
    role: str,
    password_hash: str,
) -> dict[str, Any]:
    normalized_email = str(email or "").strip().lower()
    normalized_username = str(username or "").strip() or _derive_username(normalized_email)
    normalized_phone = str(phone or "").strip() or None

    persistent_auth_ready = False
    if SessionLocal is not None:
        session = SessionLocal()
        try:
            persistent_auth_ready = _supports_persistent_auth(session)
        except Exception:
            persistent_auth_ready = False
        finally:
            session.close()

    existing = find_user_by_account(normalized_email)
    if existing is not None:
        raise ValueError("邮箱已被注册")
    existing = find_user_by_account(normalized_username)
    if existing is not None:
        raise ValueError("用户名已被占用")
    if normalized_phone:
        existing = find_user_by_account(normalized_phone)
        if existing is not None:
            raise ValueError("手机号已被占用")

    roles = [role or "doctor"]
    payload = {
        "id": str(uuid.uuid4()),
        "username": normalized_username,
        "email": normalized_email,
        "display_name": display_name,
        "department": department,
        "roles": roles,
        "role": roles[0],
        "avatar": "",
        "phone": normalized_phone,
        "bio": bio or "",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "last_login": None,
        "password_hash": password_hash,
        "is_active": True,
    }

    if SessionLocal is not None and persistent_auth_ready:
        session = SessionLocal()
        try:
            orm_user = SysUser(
                id=payload["id"],
                username=payload["username"],
                email=payload["email"],
                phone=payload["phone"],
                password_hash=password_hash,
                display_name=payload["display_name"],
                department=payload["department"],
                role=payload["role"],
                roles_json=json.dumps(payload["roles"], ensure_ascii=False),
                is_active=True,
            )
            session.add(orm_user)
            session.commit()
            session.refresh(orm_user)
            payload = _orm_user_to_dict(orm_user)
            payload["bio"] = bio or ""
            payload["avatar"] = ""
        except Exception as exc:
            session.rollback()
            logger.error("Auth DB create failed in persistent mode", exc_info=True)
            raise ValueError("创建用户失败，请稍后重试") from exc
        finally:
            session.close()

    _sync_memory_user(payload)
    return payload


def touch_last_login(user_id: str) -> dict[str, Any] | None:
    if SessionLocal is not None:
        session = SessionLocal()
        try:
            if not _supports_persistent_auth(session):
                return None
            user = session.execute(select(SysUser).where(SysUser.id == user_id).limit(1)).scalar_one_or_none()
            if user is not None:
                user.last_login_at = datetime.utcnow()
                session.commit()
                session.refresh(user)
                payload = _orm_user_to_dict(user)
                _sync_memory_user(payload)
                return payload
        except Exception:
            session.rollback()
            logger.warning("Auth DB last_login update failed; fallback to memory store", exc_info=True)
        finally:
            session.close()

    for email, raw_user in users_db.items():
        if str(raw_user.get("id") or "").strip() == str(user_id or "").strip():
            raw_user["last_login"] = datetime.utcnow().isoformat() + "Z"
            users_db[email] = raw_user
            return _normalize_memory_user(raw_user)
    return None


def update_user_profile(
    *,
    user_id: str,
    display_name: str | None = None,
    department: str | None = None,
    phone: str | None = None,
    bio: str | None = None,
) -> dict[str, Any] | None:
    updated_payload: dict[str, Any] | None = None
    persistent_auth_ready = False

    if SessionLocal is not None:
        session = SessionLocal()
        try:
            persistent_auth_ready = _supports_persistent_auth(session)
            if not persistent_auth_ready:
                raise RuntimeError("sys_users persistent auth schema is not ready")
            user = session.execute(select(SysUser).where(SysUser.id == user_id).limit(1)).scalar_one_or_none()
            if user is not None:
                normalized_phone = str(phone or "").strip() or None
                if normalized_phone and normalized_phone != str(user.phone or "").strip():
                    duplicate = session.execute(
                        select(SysUser.id).where(SysUser.phone == normalized_phone, SysUser.id != user_id).limit(1)
                    ).scalar_one_or_none()
                    if duplicate is not None:
                        raise ValueError("手机号已被占用")
                    user.phone = normalized_phone
                if display_name is not None:
                    user.display_name = display_name
                if department is not None:
                    user.department = department
                session.commit()
                session.refresh(user)
                updated_payload = _orm_user_to_dict(user)
        except ValueError:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            logger.warning("Auth DB profile update failed", exc_info=True)
            if persistent_auth_ready:
                raise ValueError("资料更新失败，请稍后重试")
        finally:
            session.close()

    if persistent_auth_ready:
        if updated_payload is not None and bio is not None:
            updated_payload["bio"] = bio
            _sync_memory_user(updated_payload)
        return updated_payload

    for email, raw_user in users_db.items():
        if str(raw_user.get("id") or "").strip() == str(user_id or "").strip():
            if display_name is not None:
                raw_user["display_name"] = display_name
            if department is not None:
                raw_user["department"] = department
            if phone is not None:
                raw_user["phone"] = str(phone or "").strip() or None
            if bio is not None:
                raw_user["bio"] = bio
            users_db[email] = raw_user
            updated_payload = _normalize_memory_user(raw_user)
            break

    if updated_payload is not None:
        if bio is not None:
            updated_payload["bio"] = bio
        _sync_memory_user(updated_payload)
    return updated_payload


def update_user_password(*, user_id: str, password_hash: str) -> dict[str, Any] | None:
    updated_payload: dict[str, Any] | None = None
    persistent_auth_ready = False

    if SessionLocal is not None:
        session = SessionLocal()
        try:
            persistent_auth_ready = _supports_persistent_auth(session)
            if not persistent_auth_ready:
                return None
            user = session.execute(select(SysUser).where(SysUser.id == user_id).limit(1)).scalar_one_or_none()
            if user is not None:
                user.password_hash = password_hash
                session.commit()
                session.refresh(user)
                updated_payload = _orm_user_to_dict(user)
        except Exception:
            session.rollback()
            logger.warning("Auth DB password update failed", exc_info=True)
            if persistent_auth_ready:
                raise ValueError("密码更新失败，请稍后重试")
        finally:
            session.close()

    if persistent_auth_ready:
        if updated_payload is not None:
            _sync_memory_user(updated_payload)
        return updated_payload

    for email, raw_user in users_db.items():
        if str(raw_user.get("id") or "").strip() == str(user_id or "").strip():
            raw_user["password_hash"] = password_hash
            users_db[email] = raw_user
            updated_payload = _normalize_memory_user(raw_user)
            break

    if updated_payload is not None:
        _sync_memory_user(updated_payload)
    return updated_payload
