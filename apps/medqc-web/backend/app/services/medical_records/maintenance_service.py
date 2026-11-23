"""medical_records 域 - 维护服务。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...database.connection import engine
from ...database.repository import get_repository
from ...database.models.cdm import AiFrontpageDraft
from ..saved_result_access import saved_result_institute_scope
from .errors import MedicalRecordsNotFoundError, MedicalRecordsValidationError


def _session_factory() -> Session:
    return Session(engine)


def _ensure_ai_frontpage_draft_table() -> None:
    AiFrontpageDraft.__table__.create(bind=engine, checkfirst=True)


def resolve_maintenance_institute_scope(current_user: dict[str, Any] | None) -> str | None:
    """解析维护接口的持久院区作用域；全局角色返回 None，非全局角色返回持久 institute_id。"""
    actor_id = ""
    if isinstance(current_user, dict):
        actor_id = str(current_user.get("id") or current_user.get("user_id") or "").strip()
    return saved_result_institute_scope(actor_id)


def _enforce_institute_scope(allowed_institute_id: str | None, target_institute_id: Any) -> str:
    target = str(target_institute_id or "").strip()
    if allowed_institute_id is not None:
        if not target or target != allowed_institute_id:
            raise HTTPException(status_code=403, detail="无权访问或修改其他院区的病历维护数据")
    return target


def save_frontpage(
    data: dict[str, Any],
    *,
    allowed_institute_id: str | None = None,
) -> dict[str, Any]:
    _enforce_institute_scope(allowed_institute_id, data.get("institute_id"))
    repo = get_repository()
    return repo.save_frontpage(data)


def save_ai_frontpage_draft(
    data: dict[str, Any],
    session_factory: Callable[[], Any] | None = None,
    ensure_table: Callable[[], None] | None = None,
    *,
    allowed_institute_id: str | None = None,
) -> dict[str, Any]:
    institute_id = str(data.get("institute_id") or "").strip()
    patient_id = str(data.get("patient_id") or "").strip()
    visit_id = str(data.get("visit_id") or "").strip()
    draft_json = data.get("draft_json", "")

    if not institute_id or not patient_id or not visit_id:
        raise MedicalRecordsValidationError("institute_id、patient_id 和 visit_id 不能为空")
    if not draft_json:
        raise MedicalRecordsValidationError("draft_json 不能为空")

    _enforce_institute_scope(allowed_institute_id, institute_id)

    if isinstance(draft_json, dict):
        draft_json = json.dumps(draft_json, ensure_ascii=False)

    session_factory = session_factory or _session_factory
    ensure_table = ensure_table or _ensure_ai_frontpage_draft_table

    try:
        ensure_table()
        with session_factory() as session:
            existing = (
                session.query(AiFrontpageDraft)
                .filter_by(
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                )
                .first()
            )
            if existing:
                existing.draft_json = draft_json
                existing.updated_at = datetime.utcnow()
                session.commit()
                return {
                    "action": "updated",
                    "institute_id": institute_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                }

            record = AiFrontpageDraft(
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                draft_json=draft_json,
            )
            session.add(record)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                raise HTTPException(
                    status_code=409,
                    detail="该就诊号已存在其他院区或患者的 AI 首页草稿，禁止覆写",
                ) from None
            return {
                "action": "created",
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
            }
    except (HTTPException, MedicalRecordsValidationError, MedicalRecordsNotFoundError):
        raise
    except Exception as exc:
        raise RuntimeError(f"保存 AI 草稿失败: {exc}") from exc


def get_ai_frontpage_draft(
    visit_id: str,
    session_factory: Callable[[], Any] | None = None,
    *,
    institute_id: str | None = None,
    patient_id: str | None = None,
    allowed_institute_id: str | None = None,
) -> dict[str, Any]:
    req_institute = str(institute_id or "").strip() or None
    req_patient = str(patient_id or "").strip() or None
    if allowed_institute_id is not None and req_institute is not None and req_institute != allowed_institute_id:
        raise HTTPException(status_code=403, detail="无权访问其他院区的 AI 首页草稿")

    session_factory = session_factory or _session_factory
    try:
        with session_factory() as session:
            query = session.query(AiFrontpageDraft).filter_by(visit_id=visit_id)
            if req_institute is not None:
                query = query.filter_by(institute_id=req_institute)
            if req_patient is not None:
                query = query.filter_by(patient_id=req_patient)
            rows = query.all()
            if not rows:
                raise MedicalRecordsNotFoundError("未找到 AI 首页草稿")
            if allowed_institute_id is not None:
                scoped_rows = [
                    row for row in rows
                    if str(row.institute_id or "").strip() == allowed_institute_id
                ]
                if not scoped_rows:
                    raise HTTPException(status_code=403, detail="无权访问其他院区的 AI 首页草稿")
                rows = scoped_rows
            if len(rows) > 1:
                raise MedicalRecordsValidationError("存在多条同就诊号草稿，请指定 institute_id 和 patient_id")
            record = rows[0]
            draft = json.loads(record.draft_json) if isinstance(record.draft_json, str) else record.draft_json
            return {
                "draft": draft,
                "institute_id": record.institute_id,
                "visit_id": visit_id,
                "patient_id": record.patient_id,
                "updated_at": record.updated_at.isoformat() if record.updated_at else None,
            }
    except (HTTPException, MedicalRecordsNotFoundError, MedicalRecordsValidationError):
        raise
    except Exception as exc:
        raise RuntimeError(f"读取 AI 草稿失败: {exc}") from exc


def save_qc_results(
    data: dict[str, Any],
    *,
    allowed_institute_id: str | None = None,
) -> int:
    repo = get_repository()
    results = data.get("results", [])
    if not results:
        raise MedicalRecordsValidationError("results 不能为空")
    if allowed_institute_id is not None:
        for item in results:
            if not isinstance(item, dict):
                raise MedicalRecordsValidationError("results 元素格式无效")
            _enforce_institute_scope(allowed_institute_id, item.get("institute_id"))
    return repo.save_qc_results(results)


def get_qc_results(
    institute_id: str,
    patient_id: str,
    visit_id: str,
    *,
    allowed_institute_id: str | None = None,
) -> list[dict]:
    _enforce_institute_scope(allowed_institute_id, institute_id)
    repo = get_repository()
    return repo.get_qc_results(institute_id, patient_id, visit_id)

