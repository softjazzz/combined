"""
visit_index 轻量写入服务。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database.connection import engine
from ..core import acceptance_startup
from ..core.settings import get_settings

logger = logging.getLogger(__name__)


def _ensure_visit_index_table(session: Session) -> None:
    session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS visit_index (
                institute_id VARCHAR(64) NOT NULL,
                patient_id VARCHAR(64) NOT NULL,
                visit_id VARCHAR(64) NOT NULL,
                scene_current VARCHAR(32) NOT NULL DEFAULT '',
                policy_version VARCHAR(128) NOT NULL DEFAULT '',
                latest_mirror_success_time TIMESTAMP NULL,
                mirror_delay_base_minutes INTEGER NOT NULL DEFAULT 30,
                sync_interval_minutes INTEGER NOT NULL DEFAULT 30,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (institute_id, patient_id, visit_id)
            )
            """
        )
    )
    session.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_visit_index_scene_updated
            ON visit_index(scene_current, updated_at DESC)
            """
        )
    )


def ingest_sync_rows(
    *,
    table_name: str,
    rows: list[dict[str, Any]],
    policy_version: Optional[str] = None,
    sync_scene: str = "both",
    allow_frontpage_only: bool = False,
    latest_mirror_success_time: Optional[datetime] = None,
    mirror_delay_base_minutes: int = 30,
    sync_interval_minutes: int = 30,
    ensure_existing_only: bool = False,
) -> dict[str, int]:
    """
    将同步到的病例键轻量 upsert 到 visit_index。
    normal 尽量成功；acceptance 不发DDL且结构/写入异常向上传播。
    """
    acceptance = acceptance_startup.resolve_startup_mode(
        os.getenv("MEDQC_STARTUP_MODE"), environment=get_settings().ENV,
    ) == "acceptance"
    if engine is None:
        if acceptance:
            raise RuntimeError("Acceptance visit_index requires a PostgreSQL engine")
        return {"processed": len(rows or []), "upserted": 0, "skipped": len(rows or [])}

    visit_params: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    skipped = 0
    for row in rows or []:
        institute_id = str((row or {}).get("institute_id") or "").strip()
        patient_id = str((row or {}).get("patient_id") or "").strip()
        visit_id = str((row or {}).get("visit_id") or "").strip()
        if not (institute_id and patient_id and visit_id):
            skipped += 1
            continue
        key = (institute_id, patient_id, visit_id)
        if key in seen:
            continue
        seen.add(key)
        visit_params.append(
            {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "scene_current": str(sync_scene or "both")[:32],
                "policy_version": str(policy_version or "")[:128],
                "latest_mirror_success_time": latest_mirror_success_time,
                "mirror_delay_base_minutes": int(mirror_delay_base_minutes or 30),
                "sync_interval_minutes": int(sync_interval_minutes or 30),
            }
        )

    if not visit_params:
        return {"processed": len(rows or []), "upserted": 0, "skipped": skipped}

    try:
        with Session(engine) as session:
            if acceptance or ensure_existing_only:
                acceptance_startup.validate_visit_index_schema(session.connection())
            else:
                _ensure_visit_index_table(session)
            session.execute(
                text(
                    """
                    INSERT INTO visit_index (
                        institute_id,
                        patient_id,
                        visit_id,
                        scene_current,
                        policy_version,
                        latest_mirror_success_time,
                        mirror_delay_base_minutes,
                        sync_interval_minutes,
                        updated_at
                    )
                    VALUES (
                        :institute_id,
                        :patient_id,
                        :visit_id,
                        :scene_current,
                        :policy_version,
                        :latest_mirror_success_time,
                        :mirror_delay_base_minutes,
                        :sync_interval_minutes,
                        CURRENT_TIMESTAMP
                    )
                    ON CONFLICT (institute_id, patient_id, visit_id) DO UPDATE SET
                        scene_current = EXCLUDED.scene_current,
                        policy_version = EXCLUDED.policy_version,
                        latest_mirror_success_time = EXCLUDED.latest_mirror_success_time,
                        mirror_delay_base_minutes = EXCLUDED.mirror_delay_base_minutes,
                        sync_interval_minutes = EXCLUDED.sync_interval_minutes,
                        updated_at = CURRENT_TIMESTAMP
                    """
                ),
                visit_params,
            )
            session.commit()
    except Exception as exc:
        if acceptance:
            raise
        logger.warning(
            "visit_index 轻量写入失败（不阻断主同步） table=%s rows=%s scene=%s allow_frontpage_only=%s error=%s",
            table_name,
            len(rows or []),
            sync_scene,
            allow_frontpage_only,
            exc,
        )
        return {"processed": len(rows or []), "upserted": 0, "skipped": skipped + len(visit_params)}

    return {"processed": len(rows or []), "upserted": len(visit_params), "skipped": skipped}
