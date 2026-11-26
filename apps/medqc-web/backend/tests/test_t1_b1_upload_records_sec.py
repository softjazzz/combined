"""T1-Batch 1 安全 P0 专项回归测试（纯离线 / SQLite / tmp_path）：
1. smart_upload.py & smart_upload_async_service.py: 鉴权/归属/路径遍历/流式 413/临时目录清理/异常脱敏
2. multi_file_processor.py: Zip Slip / Symlink / 条目上限 / 单文件与总字节上限 / 同名防覆盖
3. ingest.py / medical_records_alias.py / drg_operations.py / records.py: 角色与院区收口、流式限流、路径遮蔽修复、异常脱敏
4. medical_records_export.py / saved_result_access.py / detail_service.py / tasks.py: 绑定院区 admin/super_admin IDOR 修复
"""
from __future__ import annotations

import io
import json
import os
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import security
from app.core.rate_limit import reset_rate_limit_store_for_testing
from app.core.roles import effective_principal
from app.core.security import get_current_user
from app.core.supabase_client import _PgClient
from app.database import connection as db_connection
from app.database.models.cdm import Diagnosis, MedicalRecordFrontpage, MrCost, MrSurgery
from app.database.models.qc import QCTask as QCTaskLegacy, QCTaskRecord as QCTaskRecordLegacy
from app.database.models.v36_reports import SysUser
from app.routers import (
    drg as drg_router,
    drg_operations,
    ingest,
    medical_records_alias,
    medical_records_export,
    medical_records_maintenance,
    records,
    smart_upload,
    tasks as tasks_router,
)
from app.services import clinical_read, saved_result_access
from app.services.drg import batch_task_service
from app.services.medical_records import detail_service, export_service, maintenance_service
from app.services.multi_file_processor import MultiFileProcessor
from app.services.smart_upload_async_service import SmartUploadAsyncService
from app.storage.memory import medical_records_db


# =============================================================================
# Shared fixtures & helpers
# =============================================================================


def _make_persistent_users_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SysUser.__table__.create(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    now = datetime.utcnow()
    with factory() as session:
        session.add_all(
            [
                SysUser(
                    id="u-global-admin",
                    username="global_admin",
                    email="gadmin@local.test",
                    display_name="Global Admin",
                    role="admin",
                    roles_json=json.dumps(["admin"]),
                    institute_id=None,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-global-super",
                    username="global_super",
                    email="gsuper@local.test",
                    display_name="Global Super",
                    role="super_admin",
                    roles_json=json.dumps(["super_admin"]),
                    institute_id="",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-sync-admin",
                    username="sync_admin",
                    email="sync@local.test",
                    display_name="Sync Admin",
                    role="sync_admin",
                    roles_json=json.dumps(["sync_admin"]),
                    institute_id="HOSP-A",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-admin-a",
                    username="admin_a",
                    email="admin_a@local.test",
                    display_name="Admin A",
                    role="admin",
                    roles_json=json.dumps(["admin"]),
                    institute_id="HOSP-A",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-admin-b",
                    username="admin_b",
                    email="admin_b@local.test",
                    display_name="Admin B",
                    role="admin",
                    roles_json=json.dumps(["admin"]),
                    institute_id="HOSP-B",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-super-a",
                    username="super_a",
                    email="super_a@local.test",
                    display_name="Super A",
                    role="super_admin",
                    roles_json=json.dumps(["super_admin"]),
                    institute_id="HOSP-A",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-admin-blank",
                    username="admin_blank",
                    email="admin_blank@local.test",
                    display_name="Blank Admin",
                    role="admin",
                    roles_json=json.dumps(["admin"]),
                    institute_id="   ",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-qcm-a1",
                    username="qcm_a1",
                    email="qcm_a1@local.test",
                    display_name="QCM A1",
                    role="qc_manager",
                    roles_json=json.dumps(["qc_manager"]),
                    institute_id="HOSP-A",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-qcm-a2",
                    username="qcm_a2",
                    email="qcm_a2@local.test",
                    display_name="QCM A2",
                    role="qc_manager",
                    roles_json=json.dumps(["qc_manager"]),
                    institute_id="HOSP-A",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-qcm-b1",
                    username="qcm_b1",
                    email="qcm_b1@local.test",
                    display_name="QCM B1",
                    role="qc_manager",
                    roles_json=json.dumps(["qc_manager"]),
                    institute_id="HOSP-B",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-qcm-unbound",
                    username="qcm_unbound",
                    email="qcm_unbound@local.test",
                    display_name="QCM Unbound",
                    role="qc_manager",
                    roles_json=json.dumps(["qc_manager"]),
                    institute_id=None,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-staff-a",
                    username="staff_a",
                    email="staff_a@local.test",
                    display_name="Staff A",
                    role="qc_staff",
                    roles_json=json.dumps(["qc_staff"]),
                    institute_id="HOSP-A",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-staff-b",
                    username="staff_b",
                    email="staff_b@local.test",
                    display_name="Staff B",
                    role="qc_staff",
                    roles_json=json.dumps(["qc_staff"]),
                    institute_id="HOSP-B",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-doc-a",
                    username="doc_a",
                    email="doc_a@local.test",
                    display_name="Doctor A",
                    role="doctor",
                    roles_json=json.dumps(["doctor"]),
                    institute_id="HOSP-A",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.commit()
    return engine, factory


def _xlsx_bytes(rows: list[dict] | None = None) -> bytes:
    df = pd.DataFrame(
        rows
        or [
            {"科室": "内科", "总费用": 1000, "DIP支付标准": 1200},
            {"科室": "外科", "总费用": 2000, "DIP支付标准": 2100},
        ]
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def _user_dict(uid: str, role: str, institute_id: str | None = None) -> dict:
    return effective_principal(
        {
            "id": uid,
            "roles": [role],
            "role": role,
            "institute_id": institute_id,
            "display_name": uid,
            "email": f"{uid}@local.test",
            "is_active": True,
        }
    )


@pytest.fixture
def users_db(monkeypatch):
    engine, factory = _make_persistent_users_db()
    monkeypatch.setattr(db_connection, "SessionLocal", factory)
    try:
        yield engine, factory
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def _clean_memory_state():
    reset_rate_limit_store_for_testing()
    medical_records_db.clear()
    with drg_operations._owner_lock:
        drg_operations._task_owners.clear()
        drg_operations._session_owners.clear()
        drg_operations._batch_owners.clear()
    yield
    reset_rate_limit_store_for_testing()
    medical_records_db.clear()
    with drg_operations._owner_lock:
        drg_operations._task_owners.clear()
        drg_operations._session_owners.clear()
        drg_operations._batch_owners.clear()


# =============================================================================
# 1. smart_upload.py & smart_upload_async_service.py
# =============================================================================


class TestSmartUploadSecurity:
    def _build_app(self, tmp_path, monkeypatch):
        from app.services import async_job_store

        monkeypatch.setattr(async_job_store, "engine", None)
        upload_dir = tmp_path / "smart_uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        svc = SmartUploadAsyncService(str(upload_dir))
        monkeypatch.setattr(smart_upload, "UPLOAD_DIR", str(upload_dir))
        monkeypatch.setattr(smart_upload, "get_smart_upload_async_service", lambda *_a, **_kw: svc)

        app = FastAPI()
        app.include_router(smart_upload.router)
        holder = {"user": None}

        def _override():
            if holder["user"] is None:
                raise HTTPException(status_code=401, detail="Authentication required")
            return holder["user"]

        app.dependency_overrides[get_current_user] = _override
        return TestClient(app), holder, svc, upload_dir

    def test_auth_and_roles_enforced_across_all_smart_upload_endpoints(self, users_db, tmp_path, monkeypatch):
        client, holder, _svc, _upload_dir = self._build_app(tmp_path, monkeypatch)
        xlsx = _xlsx_bytes()

        # Unauthenticated -> 401
        assert client.post("/api/v1/drg/smart-upload", files={"file": ("a.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}).status_code == 401
        assert client.get("/api/v1/drg/smart-upload/tasks/t1").status_code == 401
        assert client.get("/api/v1/drg/smart-upload/tasks/t1/result").status_code == 401
        assert client.post("/api/v1/drg/smart-upload/tasks/t1/cancel").status_code == 401
        assert client.get("/api/v1/drg/mapping-status/a1b2c3d4").status_code == 401
        assert client.post("/api/v1/drg/mapping/suggest", json={"file_id": "a1b2c3d4"}).status_code == 401
        assert client.post("/api/v1/drg/mapping/confirm", json={"file_id": "a1b2c3d4", "mappings": {}}).status_code == 401
        assert client.get("/api/v1/drg/mapping/fields").status_code == 401

        # doctor & qc_staff -> 403
        for uid, role in (("u-doc-a", "doctor"), ("u-staff-a", "qc_staff")):
            holder["user"] = _user_dict(uid, role, "HOSP-A")
            assert client.post("/api/v1/drg/smart-upload", files={"file": ("a.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}).status_code == 403
            assert client.get("/api/v1/drg/smart-upload/tasks/t1").status_code == 403
            assert client.get("/api/v1/drg/smart-upload/tasks/t1/result").status_code == 403
            assert client.post("/api/v1/drg/smart-upload/tasks/t1/cancel").status_code == 403
            assert client.get("/api/v1/drg/mapping-status/a1b2c3d4").status_code == 403
            assert client.post("/api/v1/drg/mapping/suggest", json={"file_id": "a1b2c3d4"}).status_code == 403
            assert client.post("/api/v1/drg/mapping/confirm", json={"file_id": "a1b2c3d4", "mappings": {}}).status_code == 403
            assert client.get("/api/v1/drg/mapping/fields").status_code == 403

    def test_file_id_regex_and_path_traversal_blocked(self, users_db, tmp_path, monkeypatch):
        client, holder, _svc, upload_dir = self._build_app(tmp_path, monkeypatch)
        holder["user"] = _user_dict("u-global-admin", "admin", None)

        # Create a secret file outside UPLOAD_DIR
        secret_dir = tmp_path / "secret"
        secret_dir.mkdir()
        (secret_dir / "mapping.json").write_text(json.dumps({"mappings": {"leak": "secret"}}), encoding="utf-8")

        bad_ids = [
            "../secret",
            "..\\secret",
            "a1b2c3d4/../secret",
            "ABCDEF12",  # uppercase rejected
            "1234567",   # too short
            "123456789", # too long
            "file-123",  # non-hex
            "a1b2c3d4\n",
        ]
        for bad_id in bad_ids:
            assert client.post("/api/v1/drg/mapping/suggest", json={"file_id": bad_id}).status_code == 400
            assert client.post("/api/v1/drg/mapping/confirm", json={"file_id": bad_id, "mappings": {}}).status_code == 400
            if "/" not in bad_id and "\\" not in bad_id and "\n" not in bad_id:
                assert client.get(f"/api/v1/drg/mapping-status/{bad_id}").status_code == 400

    def test_owner_and_institute_isolation_and_confirm_cleanup(self, users_db, tmp_path, monkeypatch):
        client, holder, svc, upload_dir = self._build_app(tmp_path, monkeypatch)

        async def _fake_mapping(cols, _samples):
            return {
                "mappings": {"科室": "department", "总费用": "total_cost", "DIP支付标准": "dip_payment"},
                "confidence": 0.95,
                "unmapped": [],
                "missing_required": [],
                "fallback": False,
            }

        monkeypatch.setattr("app.services.smart_upload_async_service.suggest_field_mapping", _fake_mapping)
        monkeypatch.setattr(smart_upload, "suggest_field_mapping", _fake_mapping)

        # QCM A1 uploads via async
        holder["user"] = _user_dict("u-qcm-a1", "qc_manager", "HOSP-A")
        resp = client.post(
            "/api/v1/drg/smart-upload",
            files={"file": ("../../hosp_a.xlsx", _xlsx_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 202, resp.text
        task_id = resp.json()["task_id"]
        file_id = resp.json()["file_id"]
        assert resp.json()["filename"] == "hosp_a.xlsx"

        # Wait for task to succeed
        for _ in range(100):
            st = client.get(f"/api/v1/drg/smart-upload/tasks/{task_id}")
            assert st.status_code == 200
            if st.json()["status"] == "succeeded":
                break
            time.sleep(0.03)
        assert st.json()["status"] == "succeeded"

        # Another QCM in HOSP-B, another QCM in HOSP-A, and bound admin in HOSP-B all get 403
        for uid, role, inst in (
            ("u-qcm-b1", "qc_manager", "HOSP-B"),
            ("u-qcm-a2", "qc_manager", "HOSP-A"),
            ("u-admin-b", "admin", "HOSP-B"),
        ):
            holder["user"] = _user_dict(uid, role, inst)
            assert client.get(f"/api/v1/drg/smart-upload/tasks/{task_id}").status_code == 403
            assert client.get(f"/api/v1/drg/smart-upload/tasks/{task_id}/result").status_code == 403
            assert client.post(f"/api/v1/drg/smart-upload/tasks/{task_id}/cancel").status_code == 403
            assert client.get(f"/api/v1/drg/mapping-status/{file_id}").status_code == 403
            assert client.post("/api/v1/drg/mapping/suggest", json={"file_id": file_id}).status_code == 403
            assert client.post("/api/v1/drg/mapping/confirm", json={"file_id": file_id, "mappings": {}}).status_code == 403

        # Global admin can inspect
        holder["user"] = _user_dict("u-global-admin", "admin", None)
        assert client.get(f"/api/v1/drg/smart-upload/tasks/{task_id}").status_code == 200
        assert client.get(f"/api/v1/drg/mapping-status/{file_id}").status_code == 200

        # Owner confirms mapping -> succeeds and temp dir is cleaned up!
        holder["user"] = _user_dict("u-qcm-a1", "qc_manager", "HOSP-A")
        assert (upload_dir / file_id).exists()
        confirm_resp = client.post(
            "/api/v1/drg/mapping/confirm",
            json={
                "file_id": file_id,
                "mappings": {"科室": "department", "总费用": "total_cost", "DIP支付标准": "dip_payment"},
            },
        )
        assert confirm_resp.status_code == 200, confirm_resp.text
        assert not (upload_dir / file_id).exists()

    def test_streaming_413_and_error_sanitization_and_cleanup_on_failure_and_ttl(self, users_db, tmp_path, monkeypatch):
        client, holder, svc, upload_dir = self._build_app(tmp_path, monkeypatch)
        holder["user"] = _user_dict("u-qcm-a1", "qc_manager", "HOSP-A")

        # 1. Streaming 413 rejects oversized payload immediately
        monkeypatch.setattr(smart_upload, "MAX_FILE_SIZE", 16)
        big_resp = client.post(
            "/api/v1/drg/smart-upload",
            files={"file": ("big.csv", b"A" * 64, "text/csv")},
        )
        assert big_resp.status_code == 413
        assert "大小不能超过" in big_resp.text

        # 2. Failed task sanitizes error message & cleans up temp dir
        monkeypatch.setattr(smart_upload, "MAX_FILE_SIZE", 50 * 1024 * 1024)

        def _boom(*_args, **_kwargs):
            raise RuntimeError("SECRET_DSN=postgres://admin:pwd@10.0.0.1/prod")

        monkeypatch.setattr("app.services.smart_upload_async_service.MultiFileProcessor.explore_files", _boom)
        fail_resp = client.post(
            "/api/v1/drg/smart-upload",
            files={"file": ("fail.xlsx", _xlsx_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert fail_resp.status_code == 202
        fail_task_id = fail_resp.json()["task_id"]
        fail_file_id = fail_resp.json()["file_id"]
        for _ in range(100):
            st = client.get(f"/api/v1/drg/smart-upload/tasks/{fail_task_id}").json()
            if st["status"] == "failed":
                break
            time.sleep(0.03)
        assert st["status"] == "failed"
        assert "SECRET_DSN" not in st["error_message"]
        assert "postgres://" not in st["error_message"]
        assert not (upload_dir / fail_file_id).exists()

        # 3. TTL cleanup removes expired upload directories
        stale_dir = upload_dir / "deadbeef"
        stale_dir.mkdir()
        (stale_dir / "old.xlsx").write_bytes(b"old")
        old_ts = time.time() - 7200
        os.utime(stale_dir, (old_ts, old_ts))

        fresh_dir = upload_dir / "cafebabe"
        fresh_dir.mkdir()
        (fresh_dir / "new.xlsx").write_bytes(b"new")

        cleaned = svc.cleanup_expired_uploads(ttl_seconds=3600)
        assert cleaned == 1
        assert not stale_dir.exists()
        assert fresh_dir.exists()


# =============================================================================
# 2. multi_file_processor.py: Zip Slip / Zip Bomb / Anti-Overwrite
# =============================================================================


class TestMultiFileProcessorZipSecurity:
    def test_extract_zip_blocks_zip_slip_absolute_path_and_symlink(self, tmp_path):
        extract_dir = tmp_path / "out"
        extract_dir.mkdir()
        proc = MultiFileProcessor(str(extract_dir))

        # 1. Zip Slip ../
        slip_zip = tmp_path / "slip.zip"
        with zipfile.ZipFile(slip_zip, "w") as zf:
            zf.writestr("../escape.xlsx", b"evil")
        with pytest.raises(ValueError, match="路径遍历"):
            proc.extract_zip(str(slip_zip), str(extract_dir))
        assert not (tmp_path / "escape.xlsx").exists()

        # 2. Absolute path
        abs_zip = tmp_path / "abs.zip"
        with zipfile.ZipFile(abs_zip, "w") as zf:
            zf.writestr("/etc/passwd.xlsx", b"evil")
        with pytest.raises(ValueError, match="绝对路径"):
            proc.extract_zip(str(abs_zip), str(extract_dir))

        # 3. Unix symlink
        sym_zip = tmp_path / "sym.zip"
        with zipfile.ZipFile(sym_zip, "w") as zf:
            zi = zipfile.ZipInfo("link.xlsx")
            zi.create_system = 3
            zi.external_attr = (0o120777 << 16)
            zf.writestr(zi, "/etc/passwd")
        with pytest.raises(ValueError, match="符号链接"):
            proc.extract_zip(str(sym_zip), str(extract_dir))

    def test_extract_zip_enforces_entry_single_and_total_limits_and_rolls_back(self, tmp_path):
        extract_dir = tmp_path / "out"
        extract_dir.mkdir()
        proc = MultiFileProcessor(str(extract_dir))

        # 1. Max entries
        many_zip = tmp_path / "many.zip"
        with zipfile.ZipFile(many_zip, "w") as zf:
            for i in range(4):
                zf.writestr(f"f{i}.xlsx", b"123")
        with pytest.raises(ValueError, match="条目数超过限制"):
            proc.extract_zip(str(many_zip), str(extract_dir), max_entries=3)

        # 2. Single file uncompressed size limit (highly compressible payload)
        bomb_zip = tmp_path / "bomb.zip"
        with zipfile.ZipFile(bomb_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("bomb.xlsx", b"0" * 4096)
        with pytest.raises(ValueError, match="单文件解压大小超过限制"):
            proc.extract_zip(str(bomb_zip), str(extract_dir), max_single_file_bytes=1024, max_total_bytes=10000)
        assert list(extract_dir.iterdir()) == []

        # 3. Total uncompressed size limit across multiple files -> cleans up first extracted file!
        total_zip = tmp_path / "total.zip"
        with zipfile.ZipFile(total_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("a.xlsx", b"1" * 600)
            zf.writestr("b.xlsx", b"2" * 600)
        with pytest.raises(ValueError, match="总解压大小超过限制"):
            proc.extract_zip(str(total_zip), str(extract_dir), max_single_file_bytes=1000, max_total_bytes=1000)
        assert list(extract_dir.iterdir()) == []

    def test_extract_zip_prevents_silent_overwrite_of_duplicate_basenames(self, tmp_path):
        extract_dir = tmp_path / "out"
        extract_dir.mkdir()
        proc = MultiFileProcessor(str(extract_dir))

        dup_zip = tmp_path / "dup.zip"
        content_a = _xlsx_bytes([{"科室": "心内科", "总费用": 100}])
        content_b = _xlsx_bytes([{"科室": "呼吸科", "总费用": 200}])
        with zipfile.ZipFile(dup_zip, "w") as zf:
            zf.writestr("2025/report.xlsx", content_a)
            zf.writestr("2026/report.xlsx", content_b)

        extracted = proc.extract_zip(str(dup_zip), str(extract_dir))
        assert len(extracted) == 2
        assert extracted[0] != extracted[1]
        assert Path(extracted[0]).read_bytes() == content_a
        assert Path(extracted[1]).read_bytes() == content_b


# =============================================================================
# 3. ingest.py, medical_records_alias.py, drg_operations.py, records.py
# =============================================================================


class TestLegacyImportCompatDrgAndRecordsSecurity:
    def test_ingest_requires_roles_institute_scope_and_sanitizes_errors(self, users_db, monkeypatch):
        app = FastAPI()
        app.include_router(ingest.router)
        holder = {"user": None}

        def _override():
            if holder["user"] is None:
                raise HTTPException(status_code=401, detail="Authentication required")
            return holder["user"]

        app.dependency_overrides[get_current_user] = _override
        client = TestClient(app)

        payload = {"patient_name": "测试患者", "content": "病历正文"}

        # Unauth -> 401; doctor -> 403; unbound qc_manager -> 403
        assert client.post("/api/v1/medical-records", json=payload).status_code == 401
        holder["user"] = _user_dict("u-doc-a", "doctor", "HOSP-A")
        assert client.post("/api/v1/medical-records", json=payload).status_code == 403
        holder["user"] = _user_dict("u-qcm-unbound", "qc_manager", None)
        assert client.post("/api/v1/medical-records", json=payload).status_code == 403

        # HOSP-A manager cannot forge HOSP-B in metadata
        holder["user"] = _user_dict("u-qcm-a1", "qc_manager", "HOSP-A")
        cross_resp = client.post(
            "/api/v1/medical-records",
            json={**payload, "parse_metadata": {"institute_id": "HOSP-B"}},
        )
        assert cross_resp.status_code == 403

        # Valid HOSP-A ingest succeeds (memory fallback) and stamps institute_id
        monkeypatch.setattr("app.services.records_ingest_service.get_supabase", lambda: None)
        ok_resp = client.post("/api/v1/medical-records", json=payload)
        assert ok_resp.status_code == 200, ok_resp.text
        rec_id = ok_resp.json()["id"]
        assert medical_records_db[rec_id]["institute_id"] == "HOSP-A"

        # Internal exception sanitized (no secret leak)
        async def _boom(_data):
            raise RuntimeError("SECRET_INGEST_SQL_URL")

        monkeypatch.setattr(ingest, "ingest_llm_parse_result", _boom)
        err_resp = client.post("/api/v1/medical-records", json=payload)
        assert err_resp.status_code == 500
        assert "SECRET_INGEST_SQL_URL" not in err_resp.text

    def test_medical_records_alias_enforces_roles_and_institute_isolation(self, users_db, monkeypatch):
        monkeypatch.setattr(medical_records_alias, "get_supabase", lambda: None)
        medical_records_db["rec-a"] = {"id": "rec-a", "patient_name": "A患者", "institute_id": "HOSP-A"}
        medical_records_db["rec-b"] = {"id": "rec-b", "patient_name": "B患者", "institute_id": "HOSP-B"}

        app = FastAPI()
        app.include_router(medical_records_alias.router)
        holder = {"user": None}

        def _override():
            if holder["user"] is None:
                raise HTTPException(status_code=401, detail="Authentication required")
            return holder["user"]

        app.dependency_overrides[get_current_user] = _override
        client = TestClient(app)

        # Unauthenticated -> 401
        assert client.get("/api/v1/medical-records/rec-a").status_code == 401
        assert client.delete("/api/v1/medical-records/rec-a").status_code == 401

        # doctor -> 403
        holder["user"] = _user_dict("u-doc-a", "doctor", "HOSP-A")
        assert client.get("/api/v1/medical-records/rec-a").status_code == 403
        assert client.delete("/api/v1/medical-records/rec-a").status_code == 403

        # Bound admin A can read HOSP-A, denied on HOSP-B
        holder["user"] = _user_dict("u-admin-a", "admin", "HOSP-A")
        assert client.get("/api/v1/medical-records/rec-a").status_code == 200
        assert client.get("/api/v1/medical-records/rec-b").status_code == 403
        assert client.delete("/api/v1/medical-records/rec-b").status_code == 403
        assert "rec-b" in medical_records_db

        # Bound admin A deletes own HOSP-A record -> 200
        assert client.delete("/api/v1/medical-records/rec-a").status_code == 200
        assert "rec-a" not in medical_records_db

    def test_drg_operations_roles_session_ownership_streaming_413_and_sanitization(self, users_db, monkeypatch):
        app = FastAPI()
        app.include_router(drg_operations.router, prefix="/api/v1/drg")
        holder = {"user": None}

        def _override():
            if holder["user"] is None:
                raise HTTPException(status_code=401, detail="Authentication required")
            return holder["user"]

        app.dependency_overrides[get_current_user] = _override
        client = TestClient(app)

        fake_store = MagicMock()
        fake_store.get_statistics.return_value = {
            "summary": {"total_cases": 1, "success_rate": 100.0, "avg_cmi": 1.0, "total_cost": 1000, "total_profit": 200, "avg_los": 5},
            "department_stats": [],
        }
        fake_store.drill_down.return_value = ([], 0)
        fake_store.get_batch_list.return_value = []
        fake_store.get_all_records.return_value = []
        fake_store.delete_session.return_value = True
        fake_store.cleanup_expired_sessions.return_value = 0
        fake_store.list_active_sessions.return_value = [
            {"session_id": "sess_a1", "created_at": "2026-01-01", "last_modified": "2026-01-01", "size_bytes": 10},
            {"session_id": "sess_b1", "created_at": "2026-01-01", "last_modified": "2026-01-01", "size_bytes": 10},
        ]
        monkeypatch.setattr(drg_operations, "drg_batch_store", fake_store)

        # Register session ownerships
        drg_operations._record_task_ownership("task-a1", owner_id="u-qcm-a1", institute_id="HOSP-A", session_id="sess_a1", batch_id="BATCH_A1")
        drg_operations._record_task_ownership("task-b1", owner_id="u-qcm-b1", institute_id="HOSP-B", session_id="sess_b1", batch_id="BATCH_B1")

        # 1. Unauthenticated & doctor blocked
        assert client.get("/api/v1/drg/statistics?session_id=sess_a1").status_code == 401
        holder["user"] = _user_dict("u-doc-a", "doctor", "HOSP-A")
        assert client.get("/api/v1/drg/statistics?session_id=sess_a1").status_code == 403
        assert client.delete("/api/v1/drg/session/sess_a1").status_code == 403
        assert client.post("/api/v1/drg/cleanup-sessions").status_code == 403
        assert client.get("/api/v1/drg/export/excel?session_id=sess_a1").status_code == 403

        # 2. Path traversal session_id -> 400
        holder["user"] = _user_dict("u-global-admin", "admin", None)
        assert client.get("/api/v1/drg/statistics?session_id=../secret").status_code == 400
        assert client.delete("/api/v1/drg/session/bad.session").status_code == 400

        # 3. Cross-owner & cross-institute session access blocked (403)
        holder["user"] = _user_dict("u-qcm-a1", "qc_manager", "HOSP-A")
        assert client.get("/api/v1/drg/statistics?session_id=sess_a1").status_code == 200
        assert client.get("/api/v1/drg/statistics?session_id=sess_b1").status_code == 403
        assert client.get("/api/v1/drg/drill-down?session_id=sess_b1&dimension=drg&value=A").status_code == 403
        assert client.get("/api/v1/drg/batches?session_id=sess_b1").status_code == 403
        assert client.delete("/api/v1/drg/session/sess_b1").status_code == 403
        assert client.get("/api/v1/drg/export/excel?session_id=sess_b1").status_code == 403
        assert client.post("/api/v1/drg/notify?batch_id=BATCH_B1").status_code == 403

        # /sessions only returns own sessions for non-global user
        sess_list = client.get("/api/v1/drg/sessions")
        assert sess_list.status_code == 200
        assert [s["session_id"] for s in sess_list.json()["data"]] == ["sess_a1"]

        # Bound admin cannot run global /cleanup-sessions or read other institute's session
        holder["user"] = _user_dict("u-admin-a", "admin", "HOSP-A")
        assert client.post("/api/v1/drg/cleanup-sessions").status_code == 403
        assert client.get("/api/v1/drg/statistics?session_id=sess_b1").status_code == 403

        # Global admin can run /cleanup-sessions and see all active sessions
        holder["user"] = _user_dict("u-global-admin", "admin", None)
        assert client.post("/api/v1/drg/cleanup-sessions").status_code == 200
        assert len(client.get("/api/v1/drg/sessions").json()["data"]) == 2

        # 4. Streaming 413 + filename sanitization + error sanitization on /batch-upload
        monkeypatch.setattr(drg_operations, "DRG_BATCH_MAX_BYTES", 16)
        big = client.post(
            "/api/v1/drg/batch-upload",
            files={"file": ("../../big.csv", b"X" * 64, "text/csv")},
        )
        assert big.status_code == 413

        monkeypatch.setattr(drg_operations, "DRG_BATCH_MAX_BYTES", 50 * 1024 * 1024)
        captured_fname = {}

        def _fake_submit(**kwargs):
            captured_fname["filename"] = kwargs["filename"]
            return {"task_id": "t-ok", "status": "queued", "stage": "accepted", "progress": 0}

        monkeypatch.setattr(batch_task_service, "submit_batch_upload_task", _fake_submit)
        ok_up = client.post(
            "/api/v1/drg/batch-upload",
            files={"file": ("../../dir/clean_batch.csv", b"a,b\n1,2\n", "text/csv")},
        )
        assert ok_up.status_code == 200, ok_up.text
        assert captured_fname["filename"] == "clean_batch.csv"

        # 500 error sanitized
        monkeypatch.setattr(
            batch_task_service,
            "submit_batch_upload_task",
            lambda **_kw: (_ for _ in ()).throw(RuntimeError("SECRET_DRG_INTERNAL_TOKEN")),
        )
        err_up = client.post(
            "/api/v1/drg/batch-upload",
            files={"file": ("clean_batch.csv", b"a,b\n1,2\n", "text/csv")},
        )
        assert err_up.status_code == 500
        assert "SECRET_DRG_INTERNAL_TOKEN" not in err_up.text

    def test_records_upload_hardening_real_rate_limit_and_route_shadowing_fix(self, users_db, monkeypatch):
        app = FastAPI()
        app.include_router(records.router)
        holder = {"user": _user_dict("u-doc-a", "doctor", "HOSP-A")}
        app.dependency_overrides[get_current_user] = lambda: holder["user"]
        client = TestClient(app)

        # 1. POST /upload rejects doctor (403)
        assert (
            client.post(
                "/api/v1/records/upload",
                files={"file": ("note.txt", b"hello", "text/plain")},
            ).status_code
            == 403
        )

        # 2. POST /upload sanitizes filename & enforces streaming 413
        holder["user"] = _user_dict("u-qcm-a1", "qc_manager", "HOSP-A")
        ok_up = client.post(
            "/api/v1/records/upload",
            files={"file": ("../../etc/passwd.txt", b"safe text", "text/plain")},
        )
        assert ok_up.status_code == 200, ok_up.text
        assert ok_up.json()["file_name"] == "passwd.txt"
        assert ok_up.json()["file_url"] == "/uploads/passwd.txt"

        monkeypatch.setattr(records, "RECORD_UPLOAD_MAX_BYTES", 10)
        too_big = client.post(
            "/api/v1/records/upload",
            files={"file": ("big.txt", b"012345678901", "text/plain")},
        )
        assert too_big.status_code == 413

        # 3. Real enforce_rate_limit triggers 429 on 21st request (replacing no-op stub)
        monkeypatch.setattr(records, "RECORD_UPLOAD_MAX_BYTES", 10 * 1024 * 1024)
        reset_rate_limit_store_for_testing()
        for _ in range(20):
            r = client.post("/api/v1/records/upload", files={"file": ("ok.txt", b"hi", "text/plain")})
            assert r.status_code == 200
        r21 = client.post("/api/v1/records/upload", files={"file": ("ok.txt", b"hi", "text/plain")})
        assert r21.status_code == 429

        # 4. Route shadowing fixed: GET /statistics and DELETE /batch are NOT swallowed by /{record_id}
        medical_records_db["rec-a1"] = {
            "id": "rec-a1",
            "patient_name": "甲",
            "patient_age": 30,
            "patient_gender": "男",
            "department": "内科",
            "admission_date": "2026-01-01",
            "record_type": "inpatient",
            "content": "正文",
            "status": "pending",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "created_by": "u-admin-a",
            "institute_id": "HOSP-A",
        }
        medical_records_db["rec-b1"] = {
            **medical_records_db["rec-a1"],
            "id": "rec-b1",
            "institute_id": "HOSP-B",
        }

        holder["user"] = _user_dict("u-admin-a", "admin", "HOSP-A")
        stats_resp = client.get("/api/v1/records/statistics")
        assert stats_resp.status_code == 200, stats_resp.text
        # Bound admin A only sees HOSP-A statistics (total == 1, NOT 2)
        assert stats_resp.json()["data"]["total_records"] == 1

        # Bound admin A cannot batch-delete HOSP-B record -> 403
        cross_batch = client.request("DELETE", "/api/v1/records/batch", json=["rec-b1"])
        assert cross_batch.status_code == 403
        assert "rec-b1" in medical_records_db

        # Bound admin A can batch-delete own HOSP-A record -> 200
        own_batch = client.request("DELETE", "/api/v1/records/batch", json=["rec-a1"])
        assert own_batch.status_code == 200, own_batch.text
        assert own_batch.json()["data"]["deleted_count"] == 1
        assert "rec-a1" not in medical_records_db


# =============================================================================
# 4. Bound-Institute Admin IDOR Fix across all 4 modules
# =============================================================================


class TestBoundAdminIDORClosure:
    def test_detail_service_and_saved_result_access_global_condition(self, users_db):
        # Global roles: sync_admin (even with institute_id), unbound admin, unbound super_admin
        for uid, role in (
            ("u-global-admin", "admin"),
            ("u-global-super", "super_admin"),
            ("u-sync-admin", "sync_admin"),
        ):
            scope = detail_service.inspect_institute_scope({"id": uid, "roles": [role]})
            assert scope == detail_service.ResolvedInstituteScope(kind="global", institute_id=None)
            assert detail_service.resolve_non_global_institute_scope({"id": uid, "roles": [role]}) is None
            assert saved_result_access.saved_result_institute_scope(uid) is None

        # Bound admin & bound super_admin MUST be strictly scoped to their institute
        for uid, role, expected_inst in (
            ("u-admin-a", "admin", "HOSP-A"),
            ("u-admin-b", "admin", "HOSP-B"),
            ("u-super-a", "super_admin", "HOSP-A"),
            ("u-qcm-a1", "qc_manager", "HOSP-A"),
        ):
            scope = detail_service.inspect_institute_scope({"id": uid, "roles": [role]})
            assert scope == detail_service.ResolvedInstituteScope(kind="institute", institute_id=expected_inst)
            assert detail_service.resolve_non_global_institute_scope({"id": uid, "roles": [role]}) == expected_inst
            assert saved_result_access.saved_result_institute_scope(uid) == expected_inst

        # Whitespace-only institute on admin fails closed (not promoted to global)
        blank_scope = detail_service.inspect_institute_scope({"id": "u-admin-blank", "roles": ["admin"]})
        assert blank_scope == detail_service.ResolvedInstituteScope(kind="missing", institute_id=None)
        with pytest.raises(HTTPException) as exc1:
            detail_service.resolve_non_global_institute_scope({"id": "u-admin-blank", "roles": ["admin"]})
        assert exc1.value.status_code == 403
        with pytest.raises(HTTPException) as exc2:
            saved_result_access.saved_result_institute_scope("u-admin-blank")
        assert exc2.value.status_code == 403

    def test_medical_records_export_and_maintenance_block_bound_admin_cross_institute(self, users_db, monkeypatch):
        cdm_engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        for model in (MedicalRecordFrontpage, Diagnosis, MrSurgery, MrCost):
            model.__table__.create(cdm_engine)

        with cdm_engine.begin() as conn:
            conn.execute(
                insert(MedicalRecordFrontpage.__table__),
                [
                    {"institute_id": "HOSP-A", "patient_id": "PA1", "visit_id": "VA1", "name": "A院患者"},
                    {"institute_id": "HOSP-B", "patient_id": "PB1", "visit_id": "VB1", "name": "B院患者"},
                ],
            )
            conn.execute(
                insert(Diagnosis.__table__),
                [
                    {
                        "institute_id": "HOSP-A",
                        "patient_id": "PA1",
                        "visit_id": "VA1",
                        "diagnosis_id": "DA1",
                        "diagnosis_no": "1",
                        "diagnosis_type": "出院主要诊断（病理）",
                        "diagnosis_name": "A院主诊断",
                        "diagnosis_code": "I10",
                    },
                    {
                        "institute_id": "HOSP-B",
                        "patient_id": "PB1",
                        "visit_id": "VB1",
                        "diagnosis_id": "DB1",
                        "diagnosis_no": "1",
                        "diagnosis_type": "出院主要诊断（病理）",
                        "diagnosis_name": "B院主诊断",
                        "diagnosis_code": "E11",
                    },
                ],
            )
        monkeypatch.setattr(clinical_read, "clinical_read_schema", lambda: None)
        monkeypatch.setattr("app.database.clinical_connection.configured", lambda: False)
        monkeypatch.setattr(export_service, "_session_factory", lambda: Session(cdm_engine))
        monkeypatch.setattr(detail_service, "_session_factory", lambda: Session(cdm_engine))

        users = {
            "admin_a": _user_dict("u-admin-a", "admin", "HOSP-A"),
            "super_a": _user_dict("u-super-a", "super_admin", "HOSP-A"),
            "global_admin": _user_dict("u-global-admin", "admin", None),
            "sync_admin": _user_dict("u-sync-admin", "sync_admin", "HOSP-A"),
        }
        monkeypatch.setattr(security, "resolve_user_by_subject", lambda sub: users.get(sub))

        app = FastAPI()
        app.include_router(medical_records_export.router, prefix="/api/medical-records")
        app.include_router(medical_records_maintenance.router, prefix="/api/medical-records")
        client = TestClient(app)

        def _hdr(key: str) -> dict[str, str]:
            return {"Authorization": f"Bearer {security.create_access_token({'sub': key})}"}

        try:
            # 1. /table-data/mr: bound admin & bound super_admin ONLY see HOSP-A
            for key in ("admin_a", "super_a"):
                r = client.get("/api/medical-records/table-data/mr", headers=_hdr(key))
                assert r.status_code == 200, r.text
                assert r.json()["total"] == 1
                assert {row["institute_id"] for row in r.json()["items"]} == {"HOSP-A"}

            # Global admin & sync_admin see BOTH institutes
            for key in ("global_admin", "sync_admin"):
                r = client.get("/api/medical-records/table-data/mr", headers=_hdr(key))
                assert r.status_code == 200, r.text
                assert r.json()["total"] == 2

            # 2. /frontpage-sheet: bound admin A blocked from requesting HOSP-B (403)
            assert client.get("/api/medical-records/frontpage-sheet/PB1/VB1?institute_id=HOSP-B", headers=_hdr("admin_a")).status_code == 403
            assert client.get("/api/medical-records/frontpage-sheet/PB1/VB1?institute_id=HOSP-B", headers=_hdr("super_a")).status_code == 403
            # Own institute succeeds
            assert client.get("/api/medical-records/frontpage-sheet/PA1/VA1?institute_id=HOSP-A", headers=_hdr("admin_a")).status_code == 200
            # Global admin & sync_admin can read HOSP-B
            assert client.get("/api/medical-records/frontpage-sheet/PB1/VB1?institute_id=HOSP-B", headers=_hdr("global_admin")).status_code == 200
            assert client.get("/api/medical-records/frontpage-sheet/PB1/VB1?institute_id=HOSP-B", headers=_hdr("sync_admin")).status_code == 200

            # 3. Maintenance endpoints block bound admin A from mutating HOSP-B
            fake_repo = MagicMock()
            fake_repo.save_frontpage.return_value = {"ok": True}
            monkeypatch.setattr(maintenance_service, "get_repository", lambda: fake_repo)
            assert client.put("/api/medical-records/frontpage", json={"institute_id": "HOSP-B"}, headers=_hdr("admin_a")).status_code == 403
            assert client.put("/api/medical-records/frontpage", json={"institute_id": "HOSP-A"}, headers=_hdr("admin_a")).status_code == 200
        finally:
            cdm_engine.dispose()

    def test_tasks_blocks_bound_admin_cross_institute_operations(self, users_db, monkeypatch):
        engine, factory = users_db
        QCTaskLegacy.__table__.create(bind=engine, checkfirst=True)
        QCTaskRecordLegacy.__table__.create(bind=engine, checkfirst=True)

        pg_client = _PgClient(factory)
        monkeypatch.setattr(tasks_router, "get_supabase", lambda: pg_client)

        app = FastAPI()
        app.include_router(tasks_router.router)
        holder = {"user": _user_dict("u-staff-b", "qc_staff", "HOSP-B")}
        app.dependency_overrides[get_current_user] = lambda: holder["user"]
        client = TestClient(app)

        # HOSP-B staff creates a task
        created = client.post(
            "/api/v1/tasks",
            json={
                "task_name": "B院抽查任务",
                "task_type": "one_time",
                "sampling_method": "all",
                "assign_method": "keep",
            },
        )
        assert created.status_code == 200, created.text
        task_b_id = created.json()["data"]["id"]

        # Bound admin A (HOSP-A) MUST NOT see, read, update, cancel, or delete HOSP-B task!
        holder["user"] = _user_dict("u-admin-a", "admin", "HOSP-A")
        assert client.get("/api/v1/tasks").json()["data"]["items"] == []
        assert client.get("/api/v1/tasks/stats").json()["data"]["total"] == 0
        assert client.get(f"/api/v1/tasks/{task_b_id}").status_code == 403
        assert client.put(f"/api/v1/tasks/{task_b_id}", json={"task_name": "篡改"}).status_code == 403
        assert client.post(f"/api/v1/tasks/{task_b_id}/cancel").status_code == 403
        assert client.delete(f"/api/v1/tasks/{task_b_id}").status_code == 403

        # Bound admin A creates own HOSP-A task, cannot assign to HOSP-B staff or unknown user
        task_a_resp = client.post(
            "/api/v1/tasks",
            json={
                "task_name": "A院抽查任务",
                "task_type": "one_time",
                "sampling_method": "all",
                "assign_method": "keep",
            },
        )
        assert task_a_resp.status_code == 200
        task_a_id = task_a_resp.json()["data"]["id"]
        assert (
            client.post(
                f"/api/v1/tasks/{task_a_id}/assign",
                json={"assignees": [{"user_id": "u-staff-b", "user_name": "Staff B"}]},
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/tasks/{task_a_id}/assign",
                json={"assignees": [{"user_id": "u-ghost", "user_name": "Ghost"}]},
            ).status_code
            == 403
        )

        # Global admin (no institute) & sync_admin CAN view HOSP-B task
        for uid, role, inst in (
            ("u-global-admin", "admin", None),
            ("u-sync-admin", "sync_admin", "HOSP-A"),
        ):
            holder["user"] = _user_dict(uid, role, inst)
            assert client.get(f"/api/v1/tasks/{task_b_id}").status_code == 200
