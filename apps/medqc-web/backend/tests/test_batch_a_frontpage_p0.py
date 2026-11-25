"""Batch A 首页质控（新）P0 回归测试：PG 日期筛选、SAVEPOINT 缺表回退、临床源冻结、管理员院区隔离、空 record_refs 拒降级、分批查询与排除大文本。"""
from __future__ import annotations

import re
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Dict, List

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine, event, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import clinical_connection
from app.database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    InpatRegistration,
    MedicalRecordFrontpage,
)
from app.database.models.v36_reports import SysUser
from app.routers import frontpage_qc_v2 as api
from app.services.bundles import assembly
from app.services.case_identity import CaseRef
from app.services.defect_rectification_service import RectificationError
from app.services.frontpage_qc_v2 import FrontpageRef, build_frontpage_doc, evaluate_frontpage
from app.services.frontpage_qc_v2.access import resolve_frontpage_access
from app.services.frontpage_qc_v2.jobs import run_frontpage_qc_job
from app.services.frontpage_qc_v2.loader import default_cdm_schema, load_frontpage_raw
from app.services.frontpage_qc_v2.store import FrontpageQcStore
from app.services.qc_workspace.record_repository import RecordRepository
from tests.unit.frontpage_qc_v2_support import (
    compliant_cost,
    compliant_diagnoses,
    compliant_mr,
    diagnosis_row,
    seed_cdm_frontpages,
    surgery_row,
)
from tests.unit.test_frontpage_qc_v2_router import FakeRepository


def _create_cdm_tables(engine, *, schema: str | None = None) -> None:
    models = (MedicalRecordFrontpage, InpatRegistration, AdmissionRecord, DischargeRecord)
    if schema is None:
        for model in models:
            model.__table__.create(bind=engine)
    else:
        for model in models:
            model.__table__.to_metadata(MetaData(), schema=schema).create(bind=engine)


# ============================================================================
# P0-1: PG 出院日期筛选不再生成 date(varchar)，兼容 PG & SQLite 及空串/脏值
# ============================================================================


def test_p0_1_pg_discharge_date_filter_never_emits_date_varchar_and_handles_dirty_values(monkeypatch):
    monkeypatch.setenv("MEDQC_CLINICAL_SOURCE_MODE", "legacy_compat")
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(clinical_connection, "get_engine", lambda: None)

    engine = create_engine("sqlite:///:memory:")
    _create_cdm_tables(engine)
    try:
        repo = RecordRepository(session_factory=lambda: Session(engine), frontpage_display=True)
        with Session(engine) as session:
            for field in ("discharge", "admission", "visit"):
                q = repo._build_records_query(
                    session,
                    scope="final" if field == "discharge" else "all",
                    department=None,
                    doctor=None,
                    date_field=field,
                    start_date="2026-03-01",
                    end_date="2026-03-31",
                    keyword=None,
                )
                pg_sql = str(q.statement.compile(dialect=postgresql.dialect()))
                assert re.search(r"\bdate\s*\(", pg_sql, re.IGNORECASE) is None, pg_sql
                assert " ~ " in pg_sql, pg_sql
                assert "nullif(" in pg_sql.lower(), pg_sql

        # 写入合法日期、边界日期、空串、空格及非 YYYY-MM-DD 脏值
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO mr (institute_id, patient_id, visit_id, name, admission_datetime, discharge_datetime) "
                    "VALUES "
                    "('H1', 'P1', 'V1', '正常范围内', '2026-03-01 08:00:00', '2026-03-15 10:30:00'),"
                    "('H1', 'P2', 'V2', '边界起始', '2026-02-20 08:00:00', '2026-03-01 00:00:00'),"
                    "('H1', 'P3', 'V3', '边界结束', '2026-03-20 08:00:00', '2026-03-31 23:59:59'),"
                    "('H1', 'P4', 'V4', '范围外', '2026-04-01 08:00:00', '2026-04-05 10:00:00'),"
                    "('H1', 'P5', 'V5', '空串出院', '2026-03-10 08:00:00', ''),"
                    "('H1', 'P6', 'V6', '空格出院', '2026-03-10 08:00:00', '   '),"
                    "('H1', 'P7', 'V7', '中文脏值', '2026-03-10 08:00:00', '未知日期'),"
                    "('H1', 'P8', 'V8', '非法月日', '2026-03-10 08:00:00', '2026-99-99'),"
                    "('H1', 'P9', 'V9', '仅入院在范围', '2026-03-12 08:00:00', '2026-04-10 10:00:00')"
                )
            )

        # 出院日期区间筛选：命中 P1/P2/P3，不崩溃且不误命中空串/脏值
        listed = repo.list_records(
            scope="final",
            department=None,
            doctor=None,
            date_field="discharge",
            start_date="2026-03-01",
            end_date="2026-03-31",
            keyword=None,
            page=1,
            page_size=20,
        )
        assert {item["patient_id"] for item in listed.items} == {"P1", "P2", "P3"}
        assert listed.total == 3

        # 仅传 start_date 时中文脏值（Unicode 排序 > '2026-03-01'）绝不能被误命中
        start_only = repo.list_records(
            scope="all",
            department=None,
            doctor=None,
            date_field="discharge",
            start_date="2026-03-01",
            end_date=None,
            keyword=None,
            page=1,
            page_size=20,
        )
        assert {item["patient_id"] for item in start_only.items} == {"P1", "P2", "P3", "P4", "P9"}

        # date_field="visit"：入院或出院任一落入范围即命中（且 SQLAlchemy AST 缓存区分两列）
        visit_listed = repo.list_records(
            scope="all",
            department=None,
            doctor=None,
            date_field="visit",
            start_date="2026-03-11",
            end_date="2026-03-16",
            keyword=None,
            page=1,
            page_size=20,
        )
        assert {item["patient_id"] for item in visit_listed.items} == {"P1", "P9"}

        # scope="final" 排除空串与纯空格出院时间（不会把 ''/'   ' 误判为已出院）
        with Session(engine) as session:
            final_ids = {
                row[0]
                for row in repo._build_records_query(
                    session,
                    scope="final",
                    department=None,
                    doctor=None,
                    date_field="discharge",
                    start_date=None,
                    end_date=None,
                    keyword=None,
                    _metadata_only=True,
                )
                .with_entities(MedicalRecordFrontpage.patient_id)
                .all()
            }
        assert "P5" not in final_ids
        assert "P6" not in final_ids
        assert {"P1", "P2", "P3", "P4", "P9"}.issubset(final_ids)
    finally:
        engine.dispose()


# ============================================================================
# P0-2: load_frontpage_raw 使用 SAVEPOINT 查询可选表，缺表/无权限绝不污染外层事务
# ============================================================================


def _create_raw_table(session, table: str, ref: FrontpageRef, rows: List[Dict[str, Any]], extra: tuple = ()) -> None:
    keys = {"institute_id": ref.institute_id, "patient_id": ref.patient_id, "visit_id": ref.visit_id}
    cols = sorted({k for r in rows for k in r} | set(keys) | set(extra))
    session.execute(text(f'CREATE TABLE "{table}" ({", ".join(f"{c} TEXT" for c in cols)})'))
    for row in rows:
        payload = {**keys, **row}
        session.execute(
            text(f'INSERT INTO "{table}" ({", ".join(payload)}) VALUES ({", ".join(":" + k for k in payload)})'),
            payload,
        )


def test_p0_2_loader_missing_optional_tables_sqlite_falls_back_and_keeps_outer_tx_healthy():
    ref = FrontpageRef("INST-SYN", "C01", "C01-V1")
    engine = create_engine("sqlite://")
    try:
        with sessionmaker(bind=engine)() as session:
            # 仅建 mr 和 diagnosis，故意不建 mr_diagnosis / mr_surgery / mr_cost
            _create_raw_table(session, "mr", ref, [compliant_mr()])
            fallback_diags = [
                {k: v for k, v in diagnosis_row(1, "急性阑尾炎", "K35.800", main=True, diagnosis_type="主要诊断").items() if k != "diagnosis_main"},
                {k: v for k, v in diagnosis_row(2, "高血压", "I10.x00", diagnosis_type="其他诊断").items() if k != "diagnosis_main"},
            ]
            _create_raw_table(session, "diagnosis", ref, fallback_diags, extra=("diagnosis_type", "is_deleted"))
            session.commit()

            raw = load_frontpage_raw(session, ref, schema=None)
            assert raw is not None
            assert raw.diagnosis_source == "diagnosis"
            assert len(raw.diagnosis_rows) == 2
            assert raw.surgery_rows == []
            assert raw.cost_row is None
            assert any("mr_diagnosis" in note for note in raw.notes)
            assert any("mr_surgery" in note for note in raw.notes)
            assert any("mr_cost" in note for note in raw.notes)

            # 外层事务仍可正常继续执行查询
            assert session.execute(text("SELECT COUNT(*) FROM mr")).scalar() == 1
    finally:
        engine.dispose()


def test_p0_2_loader_uses_savepoint_for_pg_42p01_and_42501_and_reraises_other_errors():
    ref = FrontpageRef("INST-SYN", "C01", "C01-V1")

    class _FakeOrig(Exception):
        def __init__(self, msg: str, pgcode: str) -> None:
            super().__init__(msg)
            self.pgcode = pgcode

    class _FakeMappingResult:
        def __init__(self, rows: List[Dict[str, Any]]) -> None:
            self._rows = rows

        def mappings(self):
            return self

        def all(self):
            return self._rows

    class _PgStrictSession:
        """模拟 PG 事务语义：未在 SAVEPOINT 内抛错即标记外层事务 aborted，后续一切 SQL 必崩。"""

        def __init__(self, table_errors: Dict[str, str]) -> None:
            self.table_errors = table_errors
            self.aborted = False
            self.in_savepoint = False
            self.savepoint_count = 0

        @contextmanager
        def begin_nested(self):
            self.savepoint_count += 1
            prev = self.in_savepoint
            self.in_savepoint = True
            try:
                yield self
            finally:
                self.in_savepoint = prev

        def execute(self, statement, params=None):
            if self.aborted:
                raise RuntimeError("current transaction is aborted, commands ignored until end of transaction block")
            sql = str(statement)
            for tbl, code in self.table_errors.items():
                if f'"{tbl}"' in sql:
                    if not self.in_savepoint:
                        self.aborted = True
                    raise ProgrammingError(sql, params, _FakeOrig(f"pg error {code}", code))
            if '"mr"' in sql:
                return _FakeMappingResult([{**compliant_mr(), "institute_id": ref.institute_id, "patient_id": ref.patient_id, "visit_id": ref.visit_id}])
            if '"diagnosis"' in sql:
                return _FakeMappingResult([diagnosis_row(1, "急性阑尾炎", "K35.800", main=True, diagnosis_type="主要诊断")])
            return _FakeMappingResult([])

    # 42P01 (UndefinedTable) on mr_diagnosis + 42501 (InsufficientPrivilege) on mr_surgery / mr_cost
    pg_session = _PgStrictSession({"mr_diagnosis": "42P01", "mr_surgery": "42501", "mr_cost": "42501"})
    raw = load_frontpage_raw(pg_session, ref, schema="cdm")
    assert raw is not None
    assert pg_session.aborted is False
    assert pg_session.savepoint_count >= 4  # mr_diagnosis, diagnosis, mr_surgery, mr_cost
    assert raw.diagnosis_source == "diagnosis"
    assert len(raw.diagnosis_rows) == 1
    assert raw.surgery_rows == []
    assert raw.cost_row is None
    assert any("mr_diagnosis" in note for note in raw.notes)
    assert any("mr_surgery" in note for note in raw.notes)
    assert any("mr_cost" in note for note in raw.notes)

    # 非缺表/无权限错误（如 42703 UndefinedColumn）绝不吞掉
    bad_col_session = _PgStrictSession({"mr_diagnosis": "42703"})
    with pytest.raises(ProgrammingError):
        load_frontpage_raw(bad_col_session, ref, schema="cdm")


# ============================================================================
# P0-3: 首页质控（新）接入 clinical_connection 临床源绑定与后台任务快照冻结
# ============================================================================


def test_p0_3_default_cdm_schema_respects_clinical_connection_configured(monkeypatch):
    from app.database import connection as db_conn

    monkeypatch.setattr(db_conn, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(clinical_connection, "configured", lambda: True)
    assert default_cdm_schema() == "cdm"

    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    assert default_cdm_schema() is None

    monkeypatch.setattr(db_conn, "DB_SCHEMA_MODE", "split")
    assert default_cdm_schema() == "cdm"


def test_p0_3_router_and_background_job_read_independent_cdm_and_write_business_store(tmp_path, monkeypatch):
    from app.database import connection as db_conn

    monkeypatch.setenv("MEDQC_CLINICAL_SOURCE_MODE", "legacy_compat")
    monkeypatch.setattr(db_conn, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "single")

    # 业务库：仅建 frontpage_qc_* 结果表，没有任何临床 mr 表！
    business_engine = create_engine(
        f"sqlite:///{tmp_path / 'business.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    business_factory = sessionmaker(bind=business_engine)
    store = FrontpageQcStore(business_factory)
    store.create_all(business_engine)

    # 独立 CDM 只读库：在 cdm schema 下建临床表与首页数据
    cdm_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with cdm_engine.begin() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
    _create_cdm_tables(cdm_engine, schema="cdm")

    ref = FrontpageRef("H-CDM", "P-CDM-01", "V-CDM-01")
    with Session(cdm_engine.execution_options(schema_translate_map={None: "cdm"})) as s:
        s.add(
            MedicalRecordFrontpage(
                institute_id=ref.institute_id,
                patient_id=ref.patient_id,
                visit_id=ref.visit_id,
                name="独立CDM患者",
                mr_no="MR-CDM-01",
                inpat_no="ZY-CDM-01",
                discharge_dept_name="心血管内科",
                admission_datetime=datetime(2026, 3, 1, 9, 0),
                discharge_datetime=datetime(2026, 3, 8, 10, 0),
                leaving_hospital_way="医嘱离院",
            )
        )
        s.commit()

    # 额外为 loader 在 cdm schema 下创建诊断/手术/费用表
    with cdm_engine.begin() as conn:
        conn.execute(
            text(
                'CREATE TABLE "cdm"."mr_diagnosis" ('
                "institute_id TEXT, patient_id TEXT, visit_id TEXT, diagnosis_id TEXT, "
                "diagnosis_type TEXT, diagnosis_no TEXT, diagnosis_name TEXT, diagnosis_code TEXT, "
                "diagnosis_main TEXT, admission_condition TEXT, discharge_condition TEXT, is_deleted TEXT)"
            )
        )
        for row in compliant_diagnoses():
            payload = {
                "institute_id": ref.institute_id,
                "patient_id": ref.patient_id,
                "visit_id": ref.visit_id,
                "diagnosis_id": row.get("diagnosis_id", ""),
                "diagnosis_type": row.get("diagnosis_type", ""),
                "diagnosis_no": row.get("diagnosis_no", ""),
                "diagnosis_name": row.get("diagnosis_name", ""),
                "diagnosis_code": row.get("diagnosis_code", ""),
                "diagnosis_main": row.get("diagnosis_main", ""),
                "admission_condition": row.get("admission_condition", ""),
                "discharge_condition": row.get("discharge_condition", ""),
                "is_deleted": "0",
            }
            conn.execute(
                text(
                    'INSERT INTO "cdm"."mr_diagnosis" '
                    "(institute_id, patient_id, visit_id, diagnosis_id, diagnosis_type, diagnosis_no, "
                    "diagnosis_name, diagnosis_code, diagnosis_main, admission_condition, discharge_condition, is_deleted) "
                    "VALUES (:institute_id, :patient_id, :visit_id, :diagnosis_id, :diagnosis_type, :diagnosis_no, "
                    ":diagnosis_name, :diagnosis_code, :diagnosis_main, :admission_condition, :discharge_condition, :is_deleted)"
                ),
                payload,
            )

    independent_snapshot = {
        "id": "independent_cdm",
        "version": 3,
        "name": "独立CDM测试源",
        "binding": "cdm-read-v1:test-binding",
        "url": "postgresql+psycopg2://reader@127.0.0.1:5432/medqc_sync_cdm",
    }

    seen_selections_in_engine: List[Dict[str, Any] | None] = []

    def fake_get_engine():
        sel = clinical_connection.current_selection()
        seen_selections_in_engine.append(dict(sel) if sel is not None else None)
        if sel is not None and sel.get("id") == "independent_cdm":
            return cdm_engine
        return None

    monkeypatch.setattr(clinical_connection, "get_engine", fake_get_engine)
    monkeypatch.setattr(api, "_cdm_session_factory", lambda: business_factory)

    captured_tasks: List[tuple] = []

    def defer_task(_name, func, *args, **kwargs):
        captured_tasks.append((func, args, kwargs))

    monkeypatch.setattr(api, "submit_detached_task", defer_task)

    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.require_frontpage_qc_user] = lambda: {
        "id": "u-admin",
        "roles": ["admin"],
        "_frontpage_institute": None,
    }
    app.dependency_overrides[api.get_frontpage_qc_store] = lambda: store
    app.dependency_overrides[api.get_home_institute] = lambda: ""

    try:
        with TestClient(app) as client:
            with clinical_connection.selected(independent_snapshot):
                # 1. 列表走 independent_cdm
                listed = client.get("/api/v1/frontpage-qc/records")
                assert listed.status_code == 200
                assert listed.json()["data"]["total"] == 1
                assert listed.json()["data"]["items"][0]["patient_name"] == "独立CDM患者"

                # 2. 详情 get_record 走 independent_cdm（业务库没有 mr 表，走错就会 OperationalError）
                detail = client.get(
                    "/api/v1/frontpage-qc/record",
                    params={
                        "institute_id": ref.institute_id,
                        "patient_id": ref.patient_id,
                        "visit_id": ref.visit_id,
                    },
                )
                assert detail.status_code == 200
                assert detail.json()["data"]["record"]["patient_name"] == "独立CDM患者"

                # 3. POST /runs 冻结当前 clinical_sources 快照并传给后台任务
                created = client.post(
                    "/api/v1/frontpage-qc/runs",
                    json={
                        "record_refs": [
                            {
                                "institute_id": ref.institute_id,
                                "patient_id": ref.patient_id,
                                "visit_id": ref.visit_id,
                            }
                        ]
                    },
                )
                assert created.status_code == 200
                run_id = created.json()["data"]["id"]

            # 退出请求上下文（模拟独立后台线程中 ContextVar 为 None）
            assert clinical_connection.current_selection() is None
            assert len(captured_tasks) == 1
            func, args, kwargs = captured_tasks[0]
            assert kwargs["clinical_source"] == independent_snapshot

            seen_selections_in_engine.clear()
            result_run = func(*args, **kwargs)
            assert result_run["status"] == "completed"
            assert result_run["success_count"] == 1
            # 后台线程内确实通过 clinical_connection.selected(frozen_source) 读取了独立 CDM
            assert independent_snapshot in seen_selections_in_engine
            # 后台线程执行完毕后 ContextVar 已恢复
            assert clinical_connection.current_selection() is None

            # 结果已写入业务库 frontpage_qc_results
            saved = store.latest_detail(ref)
            assert saved is not None
            assert saved["run_id"] == run_id
            assert saved["department"] == "心血管内科"
    finally:
        business_engine.dispose()
        cdm_engine.dispose()


# ============================================================================
# P0-4: 绑定院区的 admin / super_admin 强制按本院区隔离，不得绕过院区隔离
# ============================================================================


def test_p0_4_bound_admin_and_super_admin_are_isolated_to_their_institute(monkeypatch):
    from app.database import connection as db_conn

    monkeypatch.setenv("MEDQC_CLINICAL_SOURCE_MODE", "legacy_compat")
    monkeypatch.setattr(db_conn, "DB_SCHEMA_MODE", "single")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine)
    SysUser.__table__.create(engine)
    store = FrontpageQcStore(factory)
    store.create_all(engine)

    with factory() as session:
        for uid, role, inst in [
            ("bound-admin", "admin", "H1"),
            ("bound-super", "super_admin", "H1"),
            ("global-admin", "admin", None),
            ("global-admin-empty", "admin", ""),
            ("global-super", "super_admin", None),
            ("bound-sync", "sync_admin", "H1"),
            ("bad-space-admin", "admin", "   "),
        ]:
            session.add(
                SysUser(
                    id=uid,
                    username=uid,
                    display_name=uid,
                    role=role,
                    institute_id=inst,
                    is_active=True,
                )
            )
        session.commit()

    try:
        with factory() as session:
            assert resolve_frontpage_access(session, "bound-admin").institute_id == "H1"
            assert resolve_frontpage_access(session, "bound-super").institute_id == "H1"
            assert resolve_frontpage_access(session, "global-admin").institute_id is None
            assert resolve_frontpage_access(session, "global-admin-empty").institute_id is None
            assert resolve_frontpage_access(session, "global-super").institute_id is None
            assert resolve_frontpage_access(session, "bound-sync").institute_id is None
            with pytest.raises(RectificationError):
                resolve_frontpage_access(session, "bad-space-admin")

        # 端到端路由校验：绑定 H1 的 super_admin 即使传 data_scope=all 也看不到 H2，且跨院操作返回 403
        monkeypatch.setattr(api, "_cdm_session_factory", lambda: factory)
        repo = FakeRepository(
            [
                FrontpageRef("H1", "P1", "V1"),
                FrontpageRef("H2", "P2", "V2"),
            ]
        )
        app = FastAPI()
        app.include_router(api.router)
        app.dependency_overrides[api.require_product_activation] = lambda: {
            "id": "bound-super",
            "roles": ["super_admin"],
        }
        app.dependency_overrides[api.get_record_repository] = lambda: repo
        app.dependency_overrides[api.get_home_institute] = lambda: ""

        with TestClient(app) as client:
            res = client.get("/api/v1/frontpage-qc/records", params={"data_scope": "all"})
            assert res.status_code == 200
            assert {item["institute_id"] for item in res.json()["data"]["items"]} == {"H1"}
            assert (
                client.get(
                    "/api/v1/frontpage-qc/record",
                    params={"institute_id": "H2", "patient_id": "P2", "visit_id": "V2"},
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/v1/frontpage-qc/runs",
                    json={"record_refs": [{"institute_id": "H2", "patient_id": "P2", "visit_id": "V2"}]},
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/v1/frontpage-qc/records/export",
                    json={"record_refs": [{"institute_id": "H2", "patient_id": "P2", "visit_id": "V2"}]},
                ).status_code
                == 403
            )
    finally:
        engine.dispose()


# ============================================================================
# P0-5: 传空 record_refs: [] 返回 422，绝不静默降级为全院批量质控/导出
# ============================================================================


def test_p0_5_empty_record_refs_returns_422_for_runs_and_export(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDQC_CLINICAL_SOURCE_MODE", "legacy_compat")
    from app.database import connection as db_conn

    monkeypatch.setattr(db_conn, "DB_SCHEMA_MODE", "single")

    engine = create_engine(f"sqlite:///{tmp_path / 'empty_refs.sqlite'}")
    factory = sessionmaker(bind=engine)
    refs = [FrontpageRef("INST-SYN", f"C{n:02d}", f"C{n:02d}-V1") for n in range(1, 4)]
    with factory() as session:
        seed_cdm_frontpages(session, refs)
    store = FrontpageQcStore(factory)
    store.create_all(engine)
    repo = FakeRepository(refs)

    monkeypatch.setattr(api, "_cdm_session_factory", lambda: factory)
    monkeypatch.setattr(api, "submit_detached_task", lambda _name, fn, *a, **kw: fn(*a, **kw))

    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.require_frontpage_qc_user] = lambda: {
        "id": "qc-1",
        "roles": ["admin"],
        "_frontpage_institute": None,
    }
    app.dependency_overrides[api.get_frontpage_qc_store] = lambda: store
    app.dependency_overrides[api.get_record_repository] = lambda: repo
    app.dependency_overrides[api.get_home_institute] = lambda: ""

    try:
        with TestClient(app) as client:
            # 1. POST /runs 传空列表 -> 422，且不创建任何任务
            resp_run_empty = client.post("/api/v1/frontpage-qc/runs", json={"record_refs": []})
            assert resp_run_empty.status_code == 422
            assert store.list_runs() == []

            # 2. POST /runs 不传 record_refs (None) -> 200，正常按筛选全量执行
            resp_run_all = client.post("/api/v1/frontpage-qc/runs", json={})
            assert resp_run_all.status_code == 200
            assert resp_run_all.json()["data"]["total_records"] == 3

            # 3. POST /records/export 传空列表 -> 422，绝不导出全院结果
            resp_export_empty = client.post("/api/v1/frontpage-qc/records/export", json={"record_refs": []})
            assert resp_export_empty.status_code == 422

            # 4. POST /records/export 不传 record_refs (None) -> 200，正常按筛选导出
            resp_export_all = client.post("/api/v1/frontpage-qc/records/export", json={})
            assert resp_export_all.status_code == 200
            assert resp_export_all.headers["x-export-total"] == "3"
    finally:
        engine.dispose()


# ============================================================================
# P0-6: record_refs 按 <=200 分批查询 & 元信息/列表查询排除 record_content 大文本
# ============================================================================


def test_p0_6_record_refs_batched_under_200_and_excludes_record_content(monkeypatch):
    monkeypatch.setenv("MEDQC_CLINICAL_SOURCE_MODE", "legacy_compat")
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(clinical_connection, "get_engine", lambda: None)

    engine = create_engine("sqlite:///:memory:")
    _create_cdm_tables(engine)
    total_count = 450
    all_refs = [CaseRef("H1", f"P{i:04d}", f"V{i:04d}") for i in range(total_count)]
    huge_text = "大段非结构化病历全文" * 200

    with Session(engine) as session:
        session.add_all(
            [
                MedicalRecordFrontpage(
                    institute_id=ref.institute_id,
                    patient_id=ref.patient_id,
                    visit_id=ref.visit_id,
                    name=f"患者-{ref.patient_id}",
                    mr_no=f"MR-{ref.patient_id}",
                    inpat_no=f"ZY-{ref.patient_id}",
                    discharge_dept_name="内科",
                    admission_datetime=datetime(2026, 3, 1, 8, 0),
                    discharge_datetime=datetime(2026, 3, 10, 10, 0),
                    record_content=huge_text,
                )
                for ref in all_refs
            ]
        )
        session.commit()

    executed: List[tuple[str, Any]] = []

    def _capture(_conn, _cursor, statement, parameters, _ctx, _many):
        executed.append((statement, parameters))

    event.listen(engine, "before_cursor_execute", _capture)
    repo = RecordRepository(session_factory=lambda: Session(engine), frontpage_display=True)

    try:
        # 1. 大批量 record_refs（450 条）元数据收集：拆为 3 批（200 + 200 + 50），排除 record_content，不拼 OR 树
        executed.clear()
        collected = repo.collect_records(
            scope="final",
            department=None,
            doctor=None,
            date_field="discharge",
            start_date=None,
            end_date=None,
            keyword=None,
            record_refs=all_refs,
            _metadata_only=True,
        )
        assert len(collected) == total_count
        assert all(item["medical_text"] == "" and item["medical_text_length"] == 0 for item in collected)
        mr_queries = [(sql, params) for sql, params in executed if "FROM mr" in sql]
        assert len(mr_queries) == 3  # ceil(450 / 200)
        for sql, params in mr_queries:
            assert "record_content" not in sql.lower()
            assert " or " not in sql.lower()
            param_count = len(params) if isinstance(params, (list, tuple, dict)) else 0
            assert param_count <= 200 * 3 + 20

        # 2. list_records（frontpage_display=True）同样不查 record_content
        executed.clear()
        listed = repo.list_records(
            scope="final",
            department=None,
            doctor=None,
            date_field="discharge",
            start_date=None,
            end_date=None,
            keyword=None,
            page=1,
            page_size=20,
        )
        assert listed.total == total_count
        assert len(listed.items) == 20
        assert all(item["medical_text"] == "" for item in listed.items)
        for sql, _params in executed:
            assert "record_content" not in sql.lower()

        # 3. 显式正文水合 hydrate_records_with_medical_text 仍正常返回 record_content
        hydrated = repo.hydrate_records_with_medical_text([all_refs[0].as_dict()])
        assert hydrated[0]["medical_text"] == huge_text

        # 4. frontpage_qc_v2._collect 对超 200 条 refs 也会显式分批并传 _metadata_only=True
        calls: List[tuple[int, bool]] = []

        class _SpyRepo:
            def collect_records(self, **kwargs):
                calls.append((len(kwargs["record_refs"]), bool(kwargs.get("_metadata_only"))))
                return [ref.as_dict() for ref in kwargs["record_refs"]]

        result_rows = api._collect(_SpyRepo(), refs=all_refs)
        assert len(result_rows) == total_count
        assert calls == [(200, True), (200, True), (50, True)]
    finally:
        engine.dispose()
