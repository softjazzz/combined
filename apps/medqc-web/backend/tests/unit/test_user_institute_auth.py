"""账号医院归属始终取持久 owner；旧 token 与内存回退不得保留院级权限。"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import security
from app.database.models.qc import SysUser
from app.services import appeal_create_service, auth_store
from app.storage.memory import users_db


def test_old_token_reads_latest_persistent_scope_and_database_failure_clears_institute(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    SysUser.__table__.to_metadata(sa.MetaData(), schema=None).create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2026, 9, 30)
    email = "scope-doctor@example.invalid"
    with sessions.begin() as session:
        session.add(SysUser(
            id="doctor-scope", username="doctor-scope", email=email,
            password_hash="unused", display_name="范围医生",
            institute_id="hospital-a", department="心内科", role="doctor",
            is_active=True, created_at=now, updated_at=now,
        ))
    monkeypatch.setattr(auth_store, "SessionLocal", sessions)
    monkeypatch.setitem(users_db, email, {
        "id": "doctor-scope", "username": "doctor-scope", "email": email,
        "display_name": "旧镜像", "institute_id": "hospital-old", "department": "旧科室",
        "roles": ["doctor"], "password_hash": "unused",
    })
    token = security.create_access_token({
        "sub": email, "uid": "doctor-scope",
        # 即使历史 token 曾携带范围声明，鉴权也不读取这些字段。
        "institute_id": "hospital-token", "department": "令牌科室",
    })

    first = security.resolve_current_user_from_token(token)
    assert (first["institute_id"], first["department"]) == ("hospital-a", "心内科")
    assert appeal_create_service.resolve_appellant(first).institute_id == "hospital-a"

    with sessions.begin() as session:
        session.execute(sa.update(SysUser).where(SysUser.id == "doctor-scope").values(
            institute_id="hospital-b", department="骨科",
        ))
    refreshed = security.resolve_current_user_from_token(token)
    assert (refreshed["institute_id"], refreshed["department"]) == ("hospital-b", "骨科")

    with sessions.begin() as session:
        session.execute(sa.update(SysUser).where(SysUser.id == "doctor-scope").values(
            institute_id=None, department=None,
        ))
    cleared = security.resolve_current_user_from_token(token)
    assert cleared["institute_id"] is None
    try:
        appeal_create_service.resolve_appellant(cleared)
    except appeal_create_service.ModernAppealForbidden as exc:
        assert "机构范围" in str(exc)
    else:
        raise AssertionError("清空机构后不应保留申诉权限")

    def unavailable_session():
        raise RuntimeError("synthetic database outage")

    monkeypatch.setattr(auth_store, "SessionLocal", unavailable_session)
    fallback = security.resolve_current_user_from_token(token)
    assert fallback["institute_id"] is None
    try:
        appeal_create_service.resolve_appellant(fallback)
    except appeal_create_service.ModernAppealForbidden as exc:
        assert "机构范围" in str(exc)
    else:
        raise AssertionError("内存回退不得拥有院级申诉权限")
    engine.dispose()


def test_memory_normalization_always_drops_stale_institute():
    normalized = auth_store._normalize_memory_user({
        "id": "doctor-1", "email": "doctor@example.invalid",
        "institute_id": "hospital-stale", "department": "心内科",
        "roles": ["doctor"],
    })
    assert normalized["institute_id"] is None
