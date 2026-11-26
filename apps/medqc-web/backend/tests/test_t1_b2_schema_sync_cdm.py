"""T1-Batch 2 专项回归测试：单库/split Schema 闭环、CDM 白名单与 409 隔离、
循环 SAVEPOINT 防事务毒化、同步并发锁/租约与历史时区/DDL、路由非阻塞与报错脱敏。
"""

from __future__ import annotations

import inspect
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.core import security
from app.database import clinical_connection, connection as db_connection
from app.database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    HospitalizationStatusProjection,
    InpatRegistration,
    MedicalRecordFrontpage,
)
from app.database.models.qc import SysUser as QcSysUser
from app.database.models.v36_reports import SysUser as ReportSysUser
from app.database.repository import SqliteRepository
from app.routers import medical_records_common, medical_records_query, system_config
from app.services import (
    auth_store,
    clinical_read,
    clinical_source_policy,
    clinical_sources,
    data_pipeline_settings,
    etl_sync,
    sync_idempotency,
    sync_run_history,
)
from app.services.bundles import assembly
from app.services.case_identity import CaseRef
from app.services.case_scope_service import HospitalizationScopeResult
from app.services.medical_records import detail_service, export_service, maintenance_service
from app.services.medical_records.errors import MedicalRecordsStorageError
from app.services.medical_records.hospitalization_status_service import (
    HospitalizationStatusService,
)


def _http_request(path: str, method: str = "GET", query: str = "", header: str | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "query_string": query.encode(),
            "headers": [(b"x-clinical-source", header.encode())] if header else [],
        }
    )


@pytest.fixture
def cdm_profile(monkeypatch, tmp_path):
    passfile = tmp_path / "t1b2.pgpass"
    passfile.write_text("127.0.0.1:62998:synthetic_cdm:reader:secret", encoding="utf-8")
    passfile.chmod(0o600)
    monkeypatch.setenv("CDM_PGPASSFILE", str(passfile))
    settings = clinical_sources.SourceSettings()
    settings.default_source = "independent_cdm"
    settings.cdm.enabled = True
    settings.cdm.port = 62998
    settings.cdm.database = "synthetic_cdm"
    settings.cdm.username = "reader"
    return settings


# ============================================================================
# 1. Single-DB / Split Schema 闭环 + auth_store / repository / hospitalization
# ============================================================================


def test_single_db_mode_removes_hardcoded_qc_prefix_across_config_sync_and_idempotency(
    monkeypatch, cdm_profile
):
    """单库模式（无 qc schema）下 clinical_sources/data_pipeline_settings/etl_sync/sync_idempotency 不再 503。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE sync_config_registry (
                    namespace TEXT,
                    config_key TEXT,
                    payload_json TEXT,
                    updated_by TEXT,
                    source TEXT,
                    change_reason TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (namespace, config_key)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE sync_trigger_idempotency (
                    idempotency_key VARCHAR(255) PRIMARY KEY,
                    run_id VARCHAR(64) NOT NULL,
                    source VARCHAR(16) NOT NULL,
                    tier VARCHAR(16) NOT NULL,
                    sync_date VARCHAR(32) NOT NULL,
                    operator_email VARCHAR(255) NOT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'pending',
                    result_json TEXT NULL,
                    error TEXT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE sync_job_state (
                    job_name VARCHAR(64) PRIMARY KEY,
                    is_running BOOLEAN NOT NULL DEFAULT 0,
                    last_sync_time TEXT,
                    last_sync_status VARCHAR(32),
                    total_records_synced INTEGER DEFAULT 0,
                    logs_json TEXT,
                    progress_json TEXT,
                    remote_connected BOOLEAN DEFAULT 0,
                    local_connected BOOLEAN DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE sync_run_details (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    source_table TEXT NOT NULL,
                    target_table TEXT,
                    status TEXT NOT NULL,
                    pulled_count INTEGER DEFAULT 0,
                    upserted_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE sync_error_records (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    source_table TEXT NOT NULL,
                    source_primary_key TEXT,
                    visit_id TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    payload_json TEXT,
                    retry_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(etl_sync, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(etl_sync, "engine", engine)
    monkeypatch.setattr(sync_idempotency, "engine", engine)
    monkeypatch.setattr(clinical_sources, "fixed_cdm", lambda: False)
    monkeypatch.setattr(data_pipeline_settings, "fixed_cdm", lambda: False)
    monkeypatch.setattr(clinical_connection, "create_engine", lambda *a, **kw: object())

    try:
        # 1) clinical_sources
        with Session(engine) as session:
            loaded, raw = clinical_sources.load(session)
            assert raw is None and loaded.version == 0
            saved = clinical_sources.save(session, cdm_profile, "admin")
            assert saved.version == 1
            assert clinical_sources.load(session)[0].version == 1

        # 2) data_pipeline_settings
        with Session(engine) as session:
            pipe, raw = data_pipeline_settings.load(session)
            assert raw is None and pipe.version == 0
            saved_pipe = data_pipeline_settings.save(
                session,
                data_pipeline_settings.PipelineSettings(version=0, default_pipeline="legacy_pg"),
                "admin",
            )
            assert saved_pipe.version == 1

        # 3) etl_sync state & tracking tables
        etl_sync._upsert_sync_job_state(etl_sync.SyncState(is_running=False, last_sync_status="success", total_records_synced=7))
        state = etl_sync.get_sync_state()
        assert state["last_sync_status"] == "success"
        assert state["total_records_synced"] == 7

        etl_sync._record_sync_run_detail(
            run_id="r-1",
            source_table="mr",
            target_table="mr",
            status="success",
            pulled_count=3,
            upserted_count=3,
            failed_count=0,
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
        )
        etl_sync._record_sync_error(
            run_id="r-1",
            source_table="mr",
            source_primary_key="pk-1",
            visit_id="V1",
            error_code="E1",
            error_message="err",
        )

        # 4) sync_idempotency
        res = sync_idempotency.reserve_sync_trigger(
            idempotency_key="single-db-key",
            source="pg",
            tier="all",
            sync_date="2026-08-01",
            operator_email="admin@medqc.com",
        )
        assert res.created is True
        sync_idempotency.complete_sync_trigger(
            idempotency_key="single-db-key",
            status="success",
            result={"ok": True},
        )

        # 5) PG split mode resolves qc.* dynamically
        class _FakePgBind:
            class dialect:
                name = "postgresql"

        monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "split")
        monkeypatch.setattr(etl_sync, "DB_SCHEMA_MODE", "split")
        assert clinical_sources._qc_table("sync_config_registry", _FakePgBind()) == "qc.sync_config_registry"
        assert data_pipeline_settings._config_table(_FakePgBind()) == "qc.sync_config_registry"
        assert etl_sync._qc_table_name("sync_job_state", _FakePgBind()) == "qc.sync_job_state"
        assert sync_idempotency._sync_trigger_table(_FakePgBind()) == "qc.sync_trigger_idempotency"

        monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "single")
        monkeypatch.setattr(etl_sync, "DB_SCHEMA_MODE", "single")
        assert clinical_sources._qc_table("sync_config_registry", _FakePgBind()) == "sync_config_registry"
        assert data_pipeline_settings._config_table(_FakePgBind()) == "sync_config_registry"
        assert etl_sync._qc_table_name("sync_job_state", _FakePgBind()) == "sync_job_state"
        assert sync_idempotency._sync_trigger_table(_FakePgBind()) == "sync_trigger_idempotency"
    finally:
        engine.dispose()


def test_auth_store_write_paths_respect_user_owner_schema(monkeypatch):
    """touch_last_login / update_user_profile / update_user_password 必须严格读写 owner schema（sys），不误写 main/public。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS sys"))
    QcSysUser.__table__.create(engine)
    QcSysUser.__table__.to_metadata(MetaData(), schema="sys").create(engine)

    with engine.begin() as conn:
        for schema_name, disp in (("main", "MAIN_SHADOW"), ("sys", "SYS_OWNER")):
            conn.execute(
                text(
                    f"""
                    INSERT INTO {schema_name}.sys_users
                    (id, username, email, password_hash, display_name, department, role, roles_json, is_active, created_at, updated_at)
                    VALUES ('u-owner', 'owner', 'owner@medqc.com', 'hash-init', :disp, '内科', 'doctor', '["doctor"]', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """
                ),
                {"disp": disp},
            )

    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(auth_store, "SessionLocal", factory)
    monkeypatch.setattr(auth_store, "resolve_user_owner_schema", lambda _s: "sys")
    monkeypatch.setattr(auth_store, "user_owner_options", lambda _s: {"schema_translate_map": {None: "sys"}})

    try:
        touched = auth_store.touch_last_login("u-owner")
        assert touched is not None
        assert touched["display_name"] == "SYS_OWNER"
        assert touched["last_login"] is not None

        updated = auth_store.update_user_profile(
            user_id="u-owner",
            display_name="SYS_RENAMED",
            department="心内科",
            phone="13800138000",
        )
        assert updated is not None
        assert updated["display_name"] == "SYS_RENAMED"
        assert updated["phone"] == "13800138000"

        pwd_updated = auth_store.update_user_password(
            user_id="u-owner",
            password_hash="hash-new-sys",
        )
        assert pwd_updated is not None
        assert pwd_updated["password_hash"] == "hash-new-sys"

        # 断言 main.sys_users 完全未被污染，所有写入都落入 sys.sys_users
        with engine.connect() as conn:
            main_row = conn.execute(
                text("SELECT display_name, password_hash, last_login_at FROM main.sys_users WHERE id='u-owner'")
            ).mappings().first()
            sys_row = conn.execute(
                text("SELECT display_name, password_hash, last_login_at FROM sys.sys_users WHERE id='u-owner'")
            ).mappings().first()
        assert main_row["display_name"] == "MAIN_SHADOW"
        assert main_row["password_hash"] == "hash-init"
        assert main_row["last_login_at"] is None
        assert sys_row["display_name"] == "SYS_RENAMED"
        assert sys_row["password_hash"] == "hash-new-sys"
        assert sys_row["last_login_at"] is not None
    finally:
        engine.dispose()


def test_repository_save_frontpage_uses_cdm_in_split_and_blocks_mass_assignment(monkeypatch):
    """save_frontpage 在 split 模式下写入 cdm.mr 并通过字段白名单拦截非法/内部字段。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
    MedicalRecordFrontpage.__table__.create(engine)
    MedicalRecordFrontpage.__table__.to_metadata(MetaData(), schema="cdm").create(engine)

    monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "split")
    repo = SqliteRepository()
    repo._session_factory = sessionmaker(bind=engine)

    try:
        saved = repo.save_frontpage(
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "name": "张三",
                "discharge_dept_name": "心内科",
                # 内部/未知字段必须被白名单静默过滤，禁止 Mass Assignment
                "local_sync_completed_at": datetime(2020, 1, 1),
                "is_admin": True,
                "__class__": "evil",
            }
        )
        assert saved["name"] == "张三"
        assert saved["local_sync_completed_at"] is None

        # 更新路径同样走 cdm 且屏蔽内部字段
        updated = repo.save_frontpage(
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "name": "张三丰",
                "local_sync_completed_at": datetime(2021, 1, 1),
                "unknown_field": "ignored",
            }
        )
        assert updated["name"] == "张三丰"
        assert updated["local_sync_completed_at"] is None

        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM main.mr")).scalar() == 0
            assert conn.execute(text("SELECT name FROM cdm.mr WHERE visit_id='V1'")).scalar() == "张三丰"
    finally:
        engine.dispose()


def test_hospitalization_status_service_reads_and_writes_same_cdm_schema_in_split(monkeypatch):
    """split 模式下 hospitalization_status_service 读写均命中 cdm，不再读 cdm 写 public/main。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
    models = (
        MedicalRecordFrontpage,
        InpatRegistration,
        AdmissionRecord,
        DischargeRecord,
        HospitalizationStatusProjection,
    )
    for model in models:
        model.__table__.create(engine)
        model.__table__.to_metadata(MetaData(), schema="cdm").create(engine)

    with Session(engine.execution_options(schema_translate_map={None: "cdm"})) as session:
        session.add(
            InpatRegistration(
                institute_id="H1",
                patient_id="P1",
                visit_id="V1",
                admission_datetime=datetime(2026, 9, 1, 8, 0),
            )
        )
        session.commit()

    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "split")
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)

    class _ActiveScope:
        def resolve_hospitalization_scope(self, **_kwargs):
            row = {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "hospitalization_status": "active",
                "source_table": "inpat_registration",
            }
            return HospitalizationScopeResult(
                case_refs=(CaseRef("H1", "P1", "V1"),),
                selected=(row,),
                all_selected=(row,),
                sources_used=("inpat_registration",),
                source_status="ready",
                warnings=(),
            )

    try:
        svc = HospitalizationStatusService(
            session_factory=lambda: Session(engine),
            scope_service=_ActiveScope(),
            now_provider=lambda: datetime(2026, 9, 3, 9, 0),
        )
        summary = svc.verify_current_statuses()
        assert summary["inpatient"] == 1

        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM main.hospitalization_status_projection")).scalar() == 0
            assert conn.execute(text("SELECT status FROM cdm.hospitalization_status_projection WHERE visit_id='V1'")).scalar() == "inpatient"
    finally:
        engine.dispose()


# ============================================================================
# 2. clinical_sources 白名单补齐 + 独立 CDM 409 防护
# ============================================================================


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/core-system-reports/summary",
        "/api/v1/custom-qc/workspace/records",
    ],
)
def test_clinical_sources_whitelist_includes_core_system_reports_and_custom_qc_workspace(
    cdm_profile, monkeypatch, path
):
    disabled = clinical_sources.SourceSettings()
    disabled.cdm.enabled = False
    monkeypatch.setattr(clinical_sources, "configuration", lambda: disabled)
    monkeypatch.setattr(clinical_sources, "fixed_cdm", lambda: True)

    req_fallback = _http_request(path)
    clinical_sources.prepare_request(req_fallback)
    assert req_fallback.state.clinical_source["id"] == "legacy_pg"

    monkeypatch.setattr(clinical_sources, "configuration", lambda: cdm_profile)
    req_cdm = _http_request(path)
    clinical_sources.prepare_request(req_cdm)
    assert req_cdm.state.clinical_source["id"] == "independent_cdm"


def test_clinical_sources_allows_settlement_rules_list_readonly_in_independent_cdm(
    cdm_profile, monkeypatch
):
    monkeypatch.setattr(clinical_sources, "configuration", lambda: cdm_profile)
    monkeypatch.setattr(clinical_sources, "fixed_cdm", lambda: True)

    req_get = _http_request("/api/medical-records/settlement/rules/list", method="GET")
    clinical_sources.prepare_request(req_get)
    assert req_get.state.clinical_source["id"] == "independent_cdm"

    req_post = _http_request("/api/medical-records/settlement/rules/list", method="POST")
    with pytest.raises(HTTPException) as exc_info:
        clinical_sources.prepare_request(req_post)
    assert exc_info.value.status_code == 422


def test_independent_cdm_blocks_legacy_writes_table_data_verify_and_system_config_with_409(
    cdm_profile, monkeypatch
):
    cdm_snap = clinical_sources.snapshot(cdm_profile, "independent_cdm")

    # 1) maintenance_service & export_service -> 409 under independent_cdm
    with clinical_connection.selected(cdm_snap):
        with pytest.raises(HTTPException) as exc1:
            maintenance_service.save_frontpage({"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"})
        assert exc1.value.status_code == 409

        with pytest.raises(HTTPException) as exc2:
            maintenance_service.save_ai_frontpage_draft(
                {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "draft_json": {"a": 1}}
            )
        assert exc2.value.status_code == 409

        with pytest.raises(HTTPException) as exc3:
            maintenance_service.save_qc_results({"results": [{"institute_id": "H1"}]})
        assert exc3.value.status_code == 409

        with pytest.raises(HTTPException) as exc4:
            export_service.get_table_data("mr")
        assert exc4.value.status_code == 409

    # 2) medical_records_query verify tightened to global admin + 409 in CDM
    users_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ReportSysUser.__table__.create(users_engine)
    users_factory = sessionmaker(bind=users_engine)
    with users_factory.begin() as session:
        session.add_all(
            [
                ReportSysUser(id="u-qcm", username="qcm", display_name="QCM", institute_id="H1", role="qc_manager", roles_json='["qc_manager"]', is_active=True),
                ReportSysUser(id="u-bound-adm", username="badm", display_name="Bound", institute_id="H1", role="admin", roles_json='["admin"]', is_active=True),
                ReportSysUser(id="u-global-adm", username="gadm", display_name="Global", institute_id=None, role="admin", roles_json='["admin"]', is_active=True),
            ]
        )
    monkeypatch.setattr(db_connection, "SessionLocal", users_factory)

    app = FastAPI()
    app.include_router(medical_records_query.router, prefix="/api/medical-records")
    app.include_router(system_config.router)
    actor: dict[str, Any] = {"id": "u-qcm", "roles": ["qc_manager"], "institute_id": "H1"}
    app.dependency_overrides[security.get_current_user] = lambda: dict(actor)

    try:
        with TestClient(app) as client:
            # qc_manager & bound admin -> 403
            monkeypatch.setattr(clinical_source_policy, "fixed_cdm", lambda: True)
            assert client.post("/api/medical-records/workstation/hospitalization-status/verify").status_code == 403
            assert client.get("/api/system/db/status").status_code == 403

            actor.update(id="u-bound-adm", roles=["admin"], institute_id="H1")
            assert client.post("/api/medical-records/workstation/hospitalization-status/verify").status_code == 403
            assert client.get("/api/system/db/status").status_code == 403

            # global admin under fixed_cdm -> 409
            actor.update(id="u-global-adm", roles=["admin"], institute_id="")
            assert client.post("/api/medical-records/workstation/hospitalization-status/verify").status_code == 409
            assert client.get("/api/system/db/status").status_code == 409
            assert client.get("/api/system/db/local").status_code == 409
            assert client.get("/api/system/sync/status").status_code == 409

            # global admin under legacy_compat -> allowed (verify 200, system_config GET 200, retired PUT 410)
            monkeypatch.setattr(clinical_source_policy, "fixed_cdm", lambda: False)
            monkeypatch.setattr(clinical_connection, "configured", lambda: False)
            monkeypatch.setattr(
                medical_records_query.default_hospitalization_status_service,
                "verify_current_statuses",
                lambda: {"total": 0, "inpatient": 0, "discharged": 0, "unknown": 0},
            )
            monkeypatch.setattr(etl_sync, "test_local_connection", lambda: {"connected": True})
            monkeypatch.setattr(etl_sync, "test_remote_connection", lambda: {"connected": True})

            assert client.post("/api/medical-records/workstation/hospitalization-status/verify").status_code == 200
            assert client.get("/api/system/db/status").status_code == 200
            assert client.put("/api/system/db/config", json={}).status_code == 410
    finally:
        users_engine.dispose()


# ============================================================================
# 3. PG 同事务循环 SAVEPOINT 防事务毒化
# ============================================================================


def test_get_documents_and_test_local_connection_use_savepoint_to_prevent_pg_poisoning(monkeypatch):
    class _PoisoningResult:
        def __init__(self, rows=None, scalar_val=None):
            self._rows = rows or []
            self._scalar = scalar_val

        def mappings(self):
            return self

        def all(self):
            return self._rows

        def scalar(self):
            return self._scalar

    class _PgPoisoningSession:
        """模拟 PostgreSQL 事务：若未包 SAVEPOINT 发生异常，整个外层事务永久毒化。"""

        def __init__(self, fail_table: str):
            self.fail_table = fail_table
            self.poisoned = False
            self.in_savepoint = False
            self.savepoint_count = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get_bind(self):
            class _Bind:
                class dialect:
                    name = "postgresql"

            return _Bind()

        @contextmanager
        def begin_nested(self):
            self.savepoint_count += 1
            prev = self.in_savepoint
            self.in_savepoint = True
            try:
                yield self
            except Exception:
                # SAVEPOINT 回滚，不毒化外层事务
                raise
            finally:
                self.in_savepoint = prev

        def execute(self, stmt, params=None):
            if self.poisoned:
                raise RuntimeError("current transaction is aborted, commands ignored until end of transaction block")
            sql = str(stmt)
            if "SELECT version()" in sql:
                return _PoisoningResult(scalar_val="PostgreSQL 16.2")
            if "information_schema.columns" in sql:
                tname = (params or {}).get("table_name", "")
                if tname == self.fail_table:
                    if not self.in_savepoint:
                        self.poisoned = True
                    raise RuntimeError(f"permission denied for table {tname}")
                return _PoisoningResult(rows=[{"column_name": "record_content"}])
            if self.fail_table in sql:
                if not self.in_savepoint:
                    self.poisoned = True
                raise RuntimeError(f"relation {self.fail_table} does not exist")
            if "SELECT count(*)" in sql:
                return _PoisoningResult(scalar_val=5)
            return _PoisoningResult(rows=[{"record_content": "正常文书正文"}])

    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(clinical_read, "clinical_read_schema", lambda: None)

    doc_session = _PgPoisoningSession(fail_table="admission_record")
    docs = detail_service.get_documents("V1", session_factory=lambda: doc_session)
    assert doc_session.poisoned is False
    assert doc_session.savepoint_count >= 2
    by_type = {d["type"]: d for d in docs["documents"]}
    assert by_type["admission_record"]["has_content"] is False
    assert by_type["discharge_record"]["has_content"] is True

    # test_local_connection 逐表 SAVEPOINT 防毒化
    local_session = _PgPoisoningSession(fail_table="mr")
    monkeypatch.setattr(etl_sync, "Session", lambda _eng: local_session)
    monkeypatch.setattr(etl_sync, "engine", object())
    monkeypatch.setattr(etl_sync, "_upsert_sync_job_state", lambda _s: None)
    monkeypatch.setattr(etl_sync, "_get_local_table_meta", lambda _s, t: ("public", ["id"], ["id"]))
    res = etl_sync.test_local_connection()
    assert res["connected"] is True
    assert local_session.poisoned is False
    assert local_session.savepoint_count == 3
    assert res["tables"]["mr"] == 0
    assert res["tables"]["diagnosis"] == 5
    assert res["tables"]["admission_record"] == 5


def test_connection_sync_missing_columns_uses_savepoint_for_partial_failure(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE sp_test_tbl (id INTEGER PRIMARY KEY)"))

    test_meta = MetaData()
    Table(
        "sp_test_tbl",
        test_meta,
        Column("id", Integer, primary_key=True),
        Column("bad_col", String(50)),
        Column("good_col", String(50)),
    )

    class _FakeBase:
        metadata = test_meta

    real_connect = engine.connect
    savepoints_used = 0

    class _ConnProxy:
        def __init__(self, inner):
            self._inner = inner

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self._inner.__exit__(*args)

        def begin_nested(self):
            nonlocal savepoints_used
            savepoints_used += 1
            return self._inner.begin_nested()

        def execute(self, stmt, *args, **kwargs):
            if '"bad_col"' in str(stmt):
                raise RuntimeError("simulated DDL error")
            return self._inner.execute(stmt, *args, **kwargs)

        def commit(self):
            return self._inner.commit()

        def close(self):
            return self._inner.close()

        def __getattr__(self, name):
            return getattr(self._inner, name)

    monkeypatch.setattr(db_connection, "Base", _FakeBase)
    monkeypatch.setattr(db_connection, "engine", engine)
    monkeypatch.setattr(engine, "connect", lambda: _ConnProxy(real_connect()))

    try:
        db_connection._sync_missing_columns()
        assert savepoints_used == 2
        with engine.connect() as conn:
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(sp_test_tbl)")).fetchall()}
        assert "good_col" in cols
        assert "bad_col" not in cols
    finally:
        engine.dispose()


# ============================================================================
# 4. 同步并发锁反写/租约过期 + sync_run_history 一次初始化与 UTC 时区
# ============================================================================


def test_etl_sync_lock_never_resets_is_running_when_not_acquired_and_reclaims_expired_lease(
    monkeypatch,
):
    monkeypatch.setattr(clinical_source_policy, "fixed_cdm", lambda: False)

    # 1) Advisory lock 未获取到时，finally 绝不反写 is_running=False，也不写 sync_job_state
    upsert_calls: list[bool] = []
    etl_sync._sync_state.is_running = True
    etl_sync._sync_state_heartbeat_at = datetime.now(timezone.utc)

    class _BusyConn:
        def execute(self, stmt, params=None):
            class _R:
                def scalar(self):
                    return False

            return _R()

        def close(self):
            return None

    class _BusyEngine:
        def connect(self):
            return _BusyConn()

    monkeypatch.setattr(etl_sync, "engine", _BusyEngine())
    monkeypatch.setattr(etl_sync, "_upsert_sync_job_state", lambda st: upsert_calls.append(st.is_running))
    res = etl_sync.run_sync(sync_date="2026-08-01", tables=["mr"])
    assert res["success"] is False
    assert etl_sync._sync_state.is_running is True
    assert upsert_calls == []

    # 2) 内存模式过期的租约会被 get_sync_state 自动回收
    monkeypatch.setattr(etl_sync, "engine", None)
    monkeypatch.setattr(etl_sync, "_SYNC_LOCK_LEASE_SECONDS", 60)
    etl_sync._sync_state.is_running = True
    etl_sync._sync_state_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    state = etl_sync.get_sync_state()
    assert state["is_running"] is False

    # 3) DB 模式 sync_job_state 过期租约被 get_sync_state 自动回收
    db_engine = create_engine("sqlite:///:memory:")
    with db_engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE sync_job_state (
                    job_name VARCHAR(64) PRIMARY KEY,
                    is_running BOOLEAN NOT NULL,
                    last_sync_time TEXT,
                    last_sync_status TEXT,
                    total_records_synced INTEGER,
                    logs_json TEXT,
                    progress_json TEXT,
                    remote_connected BOOLEAN,
                    local_connected BOOLEAN,
                    updated_at TIMESTAMP
                )
                """
            )
        )
        old_ts = (datetime.now(timezone.utc) - timedelta(seconds=180)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            text(
                """
                INSERT INTO sync_job_state
                (job_name, is_running, last_sync_time, last_sync_status, total_records_synced, logs_json, progress_json, remote_connected, local_connected, updated_at)
                VALUES ('pg_sync', 1, '', 'running', 0, '[]', '{}', 1, 1, :old_ts)
                """
            ),
            {"old_ts": old_ts},
        )
    monkeypatch.setattr(etl_sync, "engine", db_engine)
    monkeypatch.setattr(etl_sync, "DB_SCHEMA_MODE", "single")
    try:
        recovered = etl_sync.get_sync_state()
        assert recovered["is_running"] is False
        with db_engine.connect() as conn:
            assert bool(conn.execute(text("SELECT is_running FROM sync_job_state WHERE job_name='pg_sync'")).scalar()) is False
    finally:
        db_engine.dispose()


def test_etl_sync_desensitizes_display_url_and_connection_errors(monkeypatch):
    monkeypatch.setattr(clinical_source_policy, "fixed_cdm", lambda: False)
    sanitized = etl_sync._sanitize_display_url("postgresql://admin:p@ss:word@10.0.0.9:5432/medqc?password=leak")
    assert "p@ss" not in sanitized
    assert "admin" not in sanitized
    assert "leak" not in sanitized
    assert "10.0.0.9:5432/medqc" in sanitized

    monkeypatch.setattr(
        etl_sync,
        "load_db_config",
        lambda: {
            "remote_host": "10.0.0.9",
            "remote_port": "5432",
            "remote_database": "his_db",
            "remote_username": "secret_user",
            "remote_password": "secret_password",
        },
    )
    monkeypatch.setattr(etl_sync, "_upsert_sync_job_state", lambda _s: None)
    monkeypatch.setattr(
        etl_sync.psycopg2,
        "connect",
        lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("FATAL password=secret_password postgresql://u:p@10.0.0.9/his_db")),
    )
    remote_res = etl_sync.test_remote_connection()
    assert remote_res["connected"] is False
    assert "secret_user" not in remote_res["url"]
    assert "secret_password" not in remote_res["error"]
    assert "postgresql://" not in remote_res["error"]


@pytest.mark.parametrize("storage", ("memory", "sqlite"))
def test_sync_idempotency_reclaims_expired_pending_lease(monkeypatch, storage: str):
    monkeypatch.setattr(sync_idempotency, "_PENDING_TRIGGER_LEASE_SECONDS", 60)
    monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "single")
    key = f"pg:all:2026-08-20:lease-{storage}"

    if storage == "memory":
        monkeypatch.setattr(sync_idempotency, "engine", None)
        sync_idempotency.reset_sync_idempotency_memory_for_testing()
        first = sync_idempotency.reserve_sync_trigger(
            idempotency_key=key, source="pg", tier="all", sync_date="2026-08-20", operator_email="a@b.com"
        )
        assert first.created is True
        # 未过期 pending 拒绝重入
        second = sync_idempotency.reserve_sync_trigger(
            idempotency_key=key, source="pg", tier="all", sync_date="2026-08-20", operator_email="a@b.com"
        )
        assert second.created is False and second.run_id == first.run_id
        # 模拟 OOM 过期后允许回收接管
        sync_idempotency._MEMORY_STORE[key]["updated_at"] = (
            datetime.now(timezone.utc) - timedelta(seconds=120)
        ).isoformat()
        reclaimed = sync_idempotency.reserve_sync_trigger(
            idempotency_key=key, source="pg", tier="all", sync_date="2026-08-20", operator_email="a@b.com"
        )
        assert reclaimed.created is True and reclaimed.run_id != first.run_id
    else:
        db_engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        with db_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE sync_trigger_idempotency (
                        idempotency_key VARCHAR(255) PRIMARY KEY,
                        run_id VARCHAR(64) NOT NULL,
                        source VARCHAR(16) NOT NULL,
                        tier VARCHAR(16) NOT NULL,
                        sync_date VARCHAR(32) NOT NULL,
                        operator_email VARCHAR(255) NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'pending',
                        result_json TEXT NULL,
                        error TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
        monkeypatch.setattr(sync_idempotency, "engine", db_engine)
        try:
            first = sync_idempotency.reserve_sync_trigger(
                idempotency_key=key, source="pg", tier="all", sync_date="2026-08-20", operator_email="a@b.com"
            )
            assert first.created is True
            second = sync_idempotency.reserve_sync_trigger(
                idempotency_key=key, source="pg", tier="all", sync_date="2026-08-20", operator_email="a@b.com"
            )
            assert second.created is False and second.run_id == first.run_id
            stale_ts = (datetime.now(timezone.utc) - timedelta(seconds=120)).strftime("%Y-%m-%d %H:%M:%S")
            with db_engine.begin() as conn:
                conn.execute(
                    text("UPDATE sync_trigger_idempotency SET updated_at = :ts WHERE idempotency_key = :k"),
                    {"ts": stale_ts, "k": key},
                )
            reclaimed = sync_idempotency.reserve_sync_trigger(
                idempotency_key=key, source="pg", tier="all", sync_date="2026-08-20", operator_email="a@b.com"
            )
            assert reclaimed.created is True and reclaimed.run_id != first.run_id
        finally:
            db_engine.dispose()


def test_sync_run_history_runs_ddl_once_per_engine_and_normalizes_timezone_to_utc(monkeypatch):
    db_engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    ddl_statements: list[str] = []

    def _capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        upper = str(statement).upper()
        if "CREATE TABLE" in upper or "CREATE INDEX" in upper:
            ddl_statements.append(upper)

    event.listen(db_engine, "before_cursor_execute", _capture)
    monkeypatch.setattr(sync_run_history, "engine", db_engine)

    try:
        # 1) 时区归一化：+08:00 字符串与 aware datetime 均转为 UTC naive（无 8 小时偏差、无 TypeError）
        tz8 = timezone(timedelta(hours=8))
        dt_from_str = sync_run_history._to_datetime("2026-08-20T16:00:00+08:00")
        dt_from_obj = sync_run_history._to_datetime(datetime(2026, 8, 20, 16, 0, 0, tzinfo=tz8))
        assert dt_from_str == datetime(2026, 8, 20, 8, 0, 0)
        assert dt_from_obj == datetime(2026, 8, 20, 8, 0, 0)
        assert dt_from_str.tzinfo is None and dt_from_obj.tzinfo is None

        # 2) 多次读写仅首次执行 DDL（1 CREATE TABLE + 2 CREATE INDEX = 3 条），后续为 0
        now_tz8 = datetime.now(tz8).isoformat()
        sync_run_history.append_sync_run_record(
            {"id": "h-1", "source": "pg", "tier": "all", "status": "success", "started_at": now_tz8, "finished_at": now_tz8}
        )
        first_ddl_count = len(ddl_statements)
        assert first_ddl_count == 3

        sync_run_history.append_sync_run_record(
            {"id": "h-2", "source": "pg", "tier": "all", "status": "failed", "started_at": now_tz8, "finished_at": now_tz8}
        )
        sync_run_history.list_sync_run_records()
        stats = sync_run_history.get_sync_health_stats(window_minutes=60)
        assert len(ddl_statements) == first_ddl_count
        assert stats["window_total_runs"] == 2
        assert stats["window_failed_runs"] == 1
        assert abs(stats["last_run_lag_seconds"]) < 60
    finally:
        db_engine.dispose()


# ============================================================================
# 5. 路由非阻塞（def）与报错脱敏
# ============================================================================


def test_medical_records_query_routes_are_sync_def_and_errors_are_sanitized(monkeypatch):
    for fn in (
        medical_records_query.verify_workstation_hospitalization_status,
        medical_records_query.list_medical_records_api,
        medical_records_query.get_stats_api,
        medical_records_query.get_departments_api,
        medical_records_query.get_workstation_data_api,
        medical_records_query.get_workstation_qc_summary_api,
    ):
        assert inspect.iscoroutinefunction(fn) is False, f"{fn.__name__} must be sync def"

    monkeypatch.setattr(clinical_connection, "configured", lambda: False)

    with pytest.raises(HTTPException) as storage_exc:
        medical_records_common.raise_medical_records_http_error(
            MedicalRecordsStorageError("SELECT * FROM secret_table WHERE password='abc' failed")
        )
    assert storage_exc.value.status_code == 500
    assert "SELECT" not in storage_exc.value.detail
    assert "secret_table" not in storage_exc.value.detail

    with pytest.raises(HTTPException) as generic_exc:
        medical_records_common.raise_medical_records_http_error(
            RuntimeError("psycopg2.OperationalError: postgresql://admin:topsecret@10.0.0.1/medqc")
        )
    assert generic_exc.value.status_code == 500
    assert "topsecret" not in generic_exc.value.detail
    assert "postgresql://" not in generic_exc.value.detail
