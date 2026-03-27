"""medical_records 域 - 维护服务。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from sqlalchemy.orm import Session

from ...database.connection import engine
from ...database.repository import get_repository
from ...database.models.cdm import AiFrontpageDraft
from .errors import MedicalRecordsNotFoundError, MedicalRecordsValidationError


def _session_factory() -> Session:
    return Session(engine)


def _ensure_ai_frontpage_draft_table() -> None:
    AiFrontpageDraft.__table__.create(bind=engine, checkfirst=True)


def save_frontpage(data: dict[str, Any]) -> dict[str, Any]:
    repo = get_repository()
    return repo.save_frontpage(data)


def save_ai_frontpage_draft(
    data: dict[str, Any],
    session_factory: Callable[[], Any] | None = None,
    ensure_table: Callable[[], None] | None = None,
) -> dict[str, Any]:
    patient_id = str(data.get("patient_id", "")).strip()
    visit_id = str(data.get("visit_id", "")).strip()
    draft_json = data.get("draft_json", "")

    if not patient_id or not visit_id:
        raise MedicalRecordsValidationError("patient_id 和 visit_id 不能为空")
    if not draft_json:
        raise MedicalRecordsValidationError("draft_json 不能为空")

    if isinstance(draft_json, dict):
        draft_json = json.dumps(draft_json, ensure_ascii=False)

    session_factory = session_factory or _session_factory
    ensure_table = ensure_table or _ensure_ai_frontpage_draft_table

    try:
        ensure_table()
        with session_factory() as session:
            existing = session.query(AiFrontpageDraft).filter_by(visit_id=visit_id).first()
            if existing:
                existing.draft_json = draft_json
                existing.institute_id = data.get("institute_id") or existing.institute_id
                existing.patient_id = patient_id
                existing.updated_at = datetime.utcnow()
                session.commit()
                return {"action": "updated", "visit_id": visit_id}

            record = AiFrontpageDraft(
                institute_id=data.get("institute_id"),
                patient_id=patient_id,
                visit_id=visit_id,
                draft_json=draft_json,
            )
            session.add(record)
            session.commit()
            return {"action": "created", "visit_id": visit_id}
    except Exception as exc:
        raise RuntimeError(f"保存 AI 草稿失败: {exc}") from exc


def get_ai_frontpage_draft(
    visit_id: str,
    session_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    session_factory = session_factory or _session_factory
    try:
        with session_factory() as session:
            record = session.query(AiFrontpageDraft).filter_by(visit_id=visit_id).first()
            if not record:
                raise MedicalRecordsNotFoundError("未找到 AI 首页草稿")
            draft = json.loads(record.draft_json) if isinstance(record.draft_json, str) else record.draft_json
            return {
                "draft": draft,
                "visit_id": visit_id,
                "patient_id": record.patient_id,
                "updated_at": record.updated_at.isoformat() if record.updated_at else None,
            }
    except MedicalRecordsNotFoundError:
        raise
    except Exception as exc:
        raise RuntimeError(f"读取 AI 草稿失败: {exc}") from exc


def save_qc_results(data: dict[str, Any]) -> int:
    repo = get_repository()
    results = data.get("results", [])
    if not results:
        raise MedicalRecordsValidationError("results 不能为空")
    return repo.save_qc_results(results)


def get_qc_results(institute_id: str, patient_id: str, visit_id: str) -> list[dict]:
    repo = get_repository()
    return repo.get_qc_results(institute_id, patient_id, visit_id)

