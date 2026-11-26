"""T1-Batch 2 规则治理 / custom_qc / rule_validation / 上传同步病历线程化回归测试。

纯离线（SQLite / FastAPI TestClient / AsyncIO 并发验证 / Mock），不连真实数据库或真实 LLM。
"""
from __future__ import annotations

import asyncio
import inspect
import io
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.core.security import get_current_user
from app.database import clinical_connection, connection as db_connection
from app.database.models.v36_reports import SysUser
from app.routers import (
    custom_qc,
    medical_records_detail,
    medical_records_export,
    medical_records_maintenance,
    qc_sichuan,
    rule_validation,
    smart_upload,
    sync as sync_router,
)
from app.services import clinical_sources, etl_sync
from app.services.custom_qc_workspace_service import (
    CustomQCWorkspaceService,
    WorkspaceBatchJobListResult,
    WorkspaceListResult,
)
from app.services.product_activation import require_product_activation
from app.services.qc_rule_registry_service import QCRuleRegistryService
from app.services.rule_validation import RuleValidationService, define_tables as define_rv_tables
from app.services.smart_upload_async_service import SmartUploadAsyncService


# =============================================================================
# 1. QCRuleRegistryService 动态 Schema 前缀（single / split / SQLite）
# =============================================================================


def _make_single_sqlite_registry_db(tmp_path: Path):
    engine = sa.create_engine(
        f"sqlite:///{(tmp_path / 'single_rules.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    tick = {"seq": 0}

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _conn_record):
        def _now():
            tick["seq"] += 1
            return f"2026-11-25 00:00:{tick['seq']:02d}"

        dbapi_conn.create_function("NOW", 0, _now)

    sessions = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with sessions() as session:
        session.execute(
            text(
                """
                CREATE TABLE qc_rule_versions (
                    id TEXT PRIMARY KEY,
                    rule_id TEXT NOT NULL,
                    version_no INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    checksum TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL DEFAULT 'system',
                    created_at TEXT NOT NULL
                )
                """
            )
        )
        session.execute(
            text(
                """
                CREATE TABLE qc_rule_publish_history (
                    id TEXT PRIMARY KEY,
                    rule_id TEXT NOT NULL,
                    rule_version_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    operator TEXT NOT NULL DEFAULT 'system',
                    created_at TEXT NOT NULL
                )
                """
            )
        )
        session.commit()
    return engine, sessions


class TestQCRuleRegistryDynamicSchema:
    def test_single_sqlite_full_lifecycle_without_qc_schema(self, tmp_path, monkeypatch):
        monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "single")
        engine, sessions = _make_single_sqlite_registry_db(tmp_path)
        rules_json = tmp_path / "rules.json"
        rules_json.write_text(
            json.dumps(
                [
                    {
                        "rule_id": "SC-101",
                        "name": "单库测试规则",
                        "description": "验证无 qc. 前缀下完整读写",
                        "category": "完整性",
                        "complexity": "中复杂度",
                        "defect_level": "一般缺陷",
                        "applicable_documents": ["入院记录"],
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        try:
            svc = QCRuleRegistryService(session_factory=sessions, json_path=rules_json)
            boot = svc.bootstrap_rules_from_json_to_pg(operator="admin", mark_published=True)
            assert boot == {"inserted": 1, "skipped": 0, "published": 1}

            rules, source = svc.load_active_rules()
            assert source == "pg_governance"
            assert [r["rule_id"] for r in rules] == ["SC-101"]

            versions = svc.list_rule_versions("SC-101")
            assert len(versions) == 1

            assert svc.update_rule_prompt_version(
                rule_id="SC-101",
                custom_prompt="自定义提示词v2",
                operator="admin",
            ) is True
            assert len(svc.list_rule_versions("SC-101")) == 2

            assert svc.rollback_rule_version(
                rule_id="SC-101",
                version_no=1,
                operator="admin",
                reason="revert",
            ) is True
            history = svc.list_publish_history(rule_id="SC-101", limit=10)
            assert len(history) == 3
            assert history[0]["action"] == "rollback"
        finally:
            engine.dispose()

    @pytest.mark.parametrize("mode,expect_prefix", [("single", False), ("split", True)])
    def test_pg_dialect_sql_uses_dynamic_schema_prefix(self, tmp_path, monkeypatch, mode, expect_prefix):
        monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", mode)
        executed_sql: list[str] = []

        class _FakeResult:
            def __init__(self, rows):
                self._rows = rows

            def mappings(self):
                return self

            def all(self):
                return list(self._rows)

            def first(self):
                return self._rows[0] if self._rows else None

        class _FakePGSession:
            def get_bind(self):
                return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

            def execute(self, stmt, params=None):
                sql = str(stmt)
                executed_sql.append(sql)
                if "SELECT id, version_no, payload_json, checksum" in sql:
                    return _FakeResult(
                        [
                            {
                                "id": "v1",
                                "version_no": 1,
                                "payload_json": json.dumps({"rule_id": "SC-1", "name": "R1"}),
                                "checksum": "old",
                            }
                        ]
                    )
                if "SELECT id" in sql and "version_no = :version_no" in sql:
                    return _FakeResult([{"id": "v1"}])
                if "SELECT id, rule_id, version_no, status, payload_json, created_at" in sql:
                    return _FakeResult(
                        [
                            {
                                "id": "v1",
                                "rule_id": "SC-1",
                                "version_no": 1,
                                "status": "published",
                                "payload_json": json.dumps({"rule_id": "SC-1", "name": "R1"}),
                                "created_at": "2026-11-25",
                            }
                        ]
                    )
                return _FakeResult([])

            def commit(self):
                pass

            def rollback(self):
                pass

            def close(self):
                pass

        rules_json = tmp_path / "r.json"
        rules_json.write_text(json.dumps([{"rule_id": "SC-1", "name": "R1"}]), encoding="utf-8")
        svc = QCRuleRegistryService(session_factory=_FakePGSession, json_path=rules_json)

        svc.list_publish_history(rule_id="SC-1")
        svc.bootstrap_rules_from_json_to_pg(operator="op", mark_published=True)
        svc.list_rule_versions("SC-1")
        svc.update_rule_prompt_version(rule_id="SC-1", custom_prompt="new prompt", operator="op")
        svc.load_active_rules()
        svc.publish_rule_version(rule_id="SC-1", version_no=1, operator="op")

        assert len(executed_sql) >= 13
        for sql in executed_sql:
            has_qc_prefix = ("qc.qc_rule_versions" in sql) or ("qc.qc_rule_publish_history" in sql)
            assert has_qc_prefix is expect_prefix, f"mode={mode} unexpected SQL: {sql}"


# =============================================================================
# 2. custom_qc 院区 SQL 下推、分页准确、临床源冻结、缓存失效、RFC 5987 与脱敏
# =============================================================================


class TestCustomQCWorkspaceAndRouterFixes:
    def test_workspace_list_records_and_filters_push_down_institute_id(self, monkeypatch):
        captured: dict[str, dict] = {}

        class _FakeRepo:
            def list_records(self, **kwargs):
                captured["list_records"] = kwargs
                return WorkspaceListResult(
                    items=[{"institute_id": kwargs.get("institute_id"), "visit_id": "V1"}],
                    total=1,
                    page=kwargs["page"],
                    page_size=kwargs["page_size"],
                )

            def get_record_filters(self, **kwargs):
                captured["get_record_filters"] = kwargs
                return {"departments": ["心内科"], "doctors": ["张医生"], "date_bounds": {}}

        svc = CustomQCWorkspaceService.__new__(CustomQCWorkspaceService)
        monkeypatch.setattr(svc, "_record_repository", lambda: _FakeRepo())

        rec_res = svc.list_records(
            scope="final",
            department=None,
            doctor=None,
            date_field="admission",
            start_date=None,
            end_date=None,
            keyword=None,
            page=1,
            page_size=20,
            institute_id="H1",
        )
        assert rec_res.total == 1
        assert captured["list_records"]["institute_id"] == "H1"

        flt_res = svc.get_record_filters(scope="final", department=None, institute_id="H1")
        assert flt_res["departments"] == ["心内科"]
        assert captured["get_record_filters"]["institute_id"] == "H1"

    def test_list_workspace_records_uses_pushdown_without_collect_fallback(self, monkeypatch):
        collect_called = {"count": 0}
        list_calls: list[dict] = []

        class _PushdownWorkspace:
            def list_records(self, **kwargs):
                list_calls.append(kwargs)
                return WorkspaceListResult(
                    items=[{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}],
                    total=42,
                    page=kwargs["page"],
                    page_size=kwargs["page_size"],
                )

            def collect_records(self, **_kwargs):
                collect_called["count"] += 1
                raise AssertionError("不应退化到全表 collect_records")

        app = FastAPI()
        app.include_router(custom_qc.router)
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "u-qcm-h1",
            "roles": ["qc_manager"],
            "institute_id": "H1",
        }
        app.dependency_overrides[custom_qc.get_workspace_service] = lambda: _PushdownWorkspace()
        monkeypatch.setattr(custom_qc, "_resolve_workspace_institute_scope_sync", lambda _u: "H1")

        client = TestClient(app)
        resp = client.get("/api/v1/custom-qc/workspace/records?page=2&page_size=10")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 42
        assert len(data["items"]) == 1
        assert list_calls[0]["institute_id"] == "H1"
        assert collect_called["count"] == 0

    def test_list_workspace_batch_jobs_filters_institute_before_pagination(self, monkeypatch):
        # 构造 12 条任务：前 10 条属于 H2，后 2 条属于 H1；
        # 模拟不带 institute_id 参数的旧 mock，验证路由器仍先过滤再分页并返回准确 total=2。
        all_jobs = [
            {
                "id": f"job-h2-{i}",
                "status": "completed",
                "filters": {"record_refs": [{"institute_id": "H2", "patient_id": f"P{i}", "visit_id": f"V{i}"}]},
                "total_records": 1,
            }
            for i in range(10)
        ] + [
            {
                "id": f"job-h1-{i}",
                "status": "completed",
                "filters": {"record_refs": [{"institute_id": "H1", "patient_id": f"P{i}", "visit_id": f"V{i}"}]},
                "total_records": 1,
            }
            for i in range(3)
        ]

        class _LegacyMockWorkspace:
            def list_batch_jobs(
                self,
                *,
                created_by: str,
                draft_id=None,
                status=None,
                scope=None,
                query=None,
                executor_type=None,
                cache_hit=None,
                created_start_date=None,
                created_end_date=None,
                page: int = 1,
                page_size: int = 10,
            ):
                offset = (page - 1) * page_size
                return WorkspaceBatchJobListResult(
                    items=all_jobs[offset : offset + page_size],
                    total=len(all_jobs),
                    page=page,
                    page_size=page_size,
                )

        app = FastAPI()
        app.include_router(custom_qc.router)
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "u-qcm-h1",
            "roles": ["qc_manager"],
            "institute_id": "H1",
        }
        app.dependency_overrides[custom_qc.get_workspace_service] = lambda: _LegacyMockWorkspace()
        monkeypatch.setattr(custom_qc, "_resolve_workspace_institute_scope_sync", lambda _u: "H1")

        client = TestClient(app)
        resp1 = client.get("/api/v1/custom-qc/workspace/batch-jobs?page=1&page_size=2")
        assert resp1.status_code == 200
        d1 = resp1.json()["data"]
        assert d1["total"] == 3
        assert [item["id"] for item in d1["items"]] == ["job-h1-0", "job-h1-1"]

        resp2 = client.get("/api/v1/custom-qc/workspace/batch-jobs?page=2&page_size=2")
        assert resp2.status_code == 200
        d2 = resp2.json()["data"]
        assert d2["total"] == 3
        assert [item["id"] for item in d2["items"]] == ["job-h1-2"]

    def test_workspace_service_list_batch_jobs_filters_institute_before_pagination(self, monkeypatch):
        """验证真实 CustomQCWorkspaceService.list_batch_jobs(institute_id=...) 先过滤再分页并返回精确 total。"""
        import app.services.custom_qc_workspace_service as ws_mod

        engine = sa.create_engine(
            "sqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        meta = sa.MetaData()
        jobs_tbl = sa.Table(
            "custom_qc_batch_jobs",
            meta,
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("created_by", sa.String(64)),
            sa.Column("draft_id", sa.String(64)),
            sa.Column("rule_code", sa.String(64)),
            sa.Column("rule_name", sa.String(128)),
            sa.Column("scene", sa.String(32)),
            sa.Column("scope", sa.String(32)),
            sa.Column("status", sa.String(32)),
            sa.Column("job_kind", sa.String(32)),
            sa.Column("parent_job_id", sa.String(64)),
            sa.Column("filters_json", sa.Text),
            sa.Column("record_ids_json", sa.Text),
            sa.Column("summary_json", sa.Text),
            sa.Column("items_json", sa.Text),
            sa.Column("failed_records_json", sa.Text),
            sa.Column("child_job_ids_json", sa.Text),
            sa.Column("child_summary_json", sa.Text),
            sa.Column("total_records", sa.Integer),
            sa.Column("created_at", sa.DateTime),
            sa.Column("updated_at", sa.DateTime),
        )
        meta.create_all(engine)
        sessions = sessionmaker(bind=engine)
        base_ts = datetime(2026, 11, 25, 1, 0, 0)
        with sessions.begin() as s:
            for idx in range(5):
                inst = "H2" if idx >= 2 else "H1"
                s.execute(
                    jobs_tbl.insert().values(
                        id=f"db-job-{idx}",
                        created_by="u1",
                        draft_id="d1",
                        rule_code="CUST-1",
                        rule_name="规则1",
                        scene="final",
                        scope="final",
                        status="completed",
                        job_kind="leaf",
                        parent_job_id=None,
                        filters_json=json.dumps(
                            {"record_refs": [{"institute_id": inst, "patient_id": f"P{idx}", "visit_id": f"V{idx}"}]}
                        ),
                        record_ids_json=json.dumps([f"V{idx}"]),
                        summary_json=json.dumps({}),
                        items_json=json.dumps([]),
                        failed_records_json=json.dumps([]),
                        child_job_ids_json=json.dumps([]),
                        child_summary_json=json.dumps({}),
                        total_records=1,
                        created_at=base_ts.replace(minute=idx),
                        updated_at=base_ts.replace(minute=idx),
                    )
                )

        monkeypatch.setattr(ws_mod, "_session", sessions)
        svc = CustomQCWorkspaceService.__new__(CustomQCWorkspaceService)
        svc._batch_job_table = jobs_tbl
        try:
            res = svc.list_batch_jobs(created_by="u1", institute_id="H1", page=1, page_size=1)
            assert res.total == 2
            assert len(res.items) == 1
            assert res.items[0]["id"] == "db-job-1"

            res2 = svc.list_batch_jobs(created_by="u1", institute_id="H1", page=2, page_size=1)
            assert res2.total == 2
            assert len(res2.items) == 1
            assert res2.items[0]["id"] == "db-job-0"
        finally:
            engine.dispose()

    @pytest.mark.asyncio
    async def test_run_workspace_batch_job_activates_frozen_clinical_source_and_sanitizes_errors(self, monkeypatch):
        cdm_url = "postgresql+psycopg2://cdm_ro@10.20.30.40:5432/medqc_cdm"
        binding = clinical_connection.build_source_binding("10.20.30.40", 5432, "medqc_cdm", "cdm_ro")
        frozen_source = {
            "id": "independent_cdm",
            "version": 3,
            "name": "东华独立CDM",
            "binding": binding,
            "url": cdm_url,
        }
        observed_sources: list[dict | None] = []
        failed_messages: list[str] = []

        class _SourceCheckingWorkspace:
            def get_batch_job_for_processing(self, *, job_id: str):
                return {
                    "id": job_id,
                    "draft_id": "d1",
                    "draft_ids": ["d1"],
                    "created_by": "u1",
                    "scope": "final",
                    "status": "queued",
                    "filters": {
                        clinical_sources.TASK_KEY: frozen_source,
                        "record_refs": [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}],
                    },
                }

            def mark_batch_job_running(self, *, job_id: str):
                return True

            def get_draft(self, *, draft_id: str, created_by: str):
                observed_sources.append(clinical_connection.current_selection())
                return {"id": draft_id, "rule_code": "CUST-1", "name": "规则1"}

            def collect_records(self, **_kwargs):
                observed_sources.append(clinical_connection.current_selection())
                raise RuntimeError("FATAL: password authentication failed for postgresql://secret@10.0.0.1/db")

            def fail_batch_job(self, *, job_id: str, error_message: str):
                failed_messages.append(error_message)

        monkeypatch.setattr(custom_qc, "get_workspace_service", lambda: _SourceCheckingWorkspace())
        assert clinical_connection.current_selection() is None

        await custom_qc._run_workspace_batch_job("job-cdm-1")

        # 验证后台任务与工作线程内均严格激活了冻结的 independent_cdm 临床源
        assert len(observed_sources) == 2
        assert all(src == frozen_source for src in observed_sources)
        # 退出后 ContextVar 干净恢复
        assert clinical_connection.current_selection() is None
        # 错误信息脱敏，不泄露连接串与底层异常
        assert len(failed_messages) == 1
        assert "postgresql://" not in failed_messages[0]
        assert "secret" not in failed_messages[0]

    def test_publish_draft_invalidates_in_process_rule_caches(self, monkeypatch):
        from app.services import customer_rule_sets, sichuan_qc_service

        calls: list[str] = []
        fake_singleton = SimpleNamespace(invalidate_rule_cache=lambda: calls.append("singleton"))
        monkeypatch.setattr(qc_sichuan, "service", fake_singleton, raising=False)
        monkeypatch.setattr(
            sichuan_qc_service,
            "invalidate_rule_cache",
            lambda: calls.append("module_fn"),
            raising=False,
        )
        monkeypatch.setattr(
            customer_rule_sets,
            "invalidate_customer_rule_set_cache",
            lambda: calls.append("customer_rule_set"),
        )

        # 构造内存 SQLite 表验证 publish_draft 完整执行后联动清缓存
        engine = sa.create_engine(
            "sqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        meta = sa.MetaData()
        drafts_tbl = sa.Table(
            "custom_qc_drafts",
            meta,
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("created_by", sa.String(64)),
            sa.Column("rule_code", sa.String(64)),
            sa.Column("name", sa.String(128)),
            sa.Column("description", sa.Text),
            sa.Column("document_type", sa.String(64)),
            sa.Column("applicable_documents", sa.Text),
            sa.Column("severity", sa.String(32)),
            sa.Column("defect_level", sa.String(32)),
            sa.Column("scene", sa.String(32)),
            sa.Column("prompt_template", sa.Text),
            sa.Column("check_logic", sa.Text),
            sa.Column("generation_mode", sa.String(32)),
            sa.Column("examples", sa.Text),
            sa.Column("last_test_summary", sa.Text),
            sa.Column("status", sa.String(32)),
            sa.Column("published_rule_id", sa.String(64)),
            sa.Column("created_at", sa.DateTime),
            sa.Column("updated_at", sa.DateTime),
        )
        qc_rules_tbl = sa.Table(
            "qc_rules",
            meta,
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("rule_code", sa.String(64)),
            sa.Column("name", sa.String(128)),
            sa.Column("description", sa.Text),
            sa.Column("status", sa.String(32)),
            sa.Column("is_active", sa.Boolean),
            sa.Column("updated_at", sa.DateTime),
        )
        meta.create_all(engine)
        sessions = sessionmaker(bind=engine)
        with sessions.begin() as s:
            s.execute(
                drafts_tbl.insert().values(
                    id="draft-pub-1",
                    created_by="admin-1",
                    rule_code="CUST-PUB-001",
                    name="测试发布规则",
                    description="描述",
                    document_type="入院记录",
                    applicable_documents=json.dumps(["入院记录"]),
                    severity="major",
                    defect_level="一般缺陷",
                    scene="final",
                    prompt_template="prompt",
                    check_logic=json.dumps({}),
                    generation_mode="fallback_template",
                    examples=json.dumps([]),
                    last_test_summary=json.dumps({"success_count": 1}),
                    status="draft",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )

        import app.services.custom_qc_workspace_service as ws_mod

        monkeypatch.setattr(ws_mod, "_session", sessions)
        monkeypatch.setattr(ws_mod, "_qc_rules_table", lambda: qc_rules_tbl)
        svc = CustomQCWorkspaceService.__new__(CustomQCWorkspaceService)
        svc._draft_table = drafts_tbl

        try:
            res = svc.publish_draft(draft_id="draft-pub-1", created_by="admin-1")
            assert res["status"] == "published"
            assert "singleton" in calls
            assert "module_fn" in calls
            assert "customer_rule_set" in calls
        finally:
            engine.dispose()

    def test_export_rfc5987_content_disposition_and_sanitized_errors(self, monkeypatch):
        class _ExportWorkspace:
            def get_batch_job(self, *, job_id: str, created_by: str):
                return {
                    "id": job_id,
                    "created_by": created_by,
                    "rule_code": "自定义规则/中文_01",
                    "status": "completed",
                    "filters": {"record_refs": [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}]},
                }

            def export_batch_job_csv(self, *, job: dict):
                return io.StringIO("col1,col2\n1,2\n")

            def export_batch_job_workbook(self, *, job: dict):
                if job["id"] == "boom":
                    raise RuntimeError("psycopg2 internal stack secret://dsn")
                return io.BytesIO(b"PK\x03\x04fake-xlsx")

        app = FastAPI()
        app.include_router(custom_qc.router)
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "admin-global",
            "roles": ["admin"],
            "institute_id": None,
        }
        app.dependency_overrides[custom_qc.get_workspace_service] = lambda: _ExportWorkspace()
        monkeypatch.setattr(custom_qc, "_resolve_workspace_institute_scope_sync", lambda _u: None)

        client = TestClient(app)
        r_csv = client.get("/api/v1/custom-qc/workspace/batch-jobs/job-1/export?format=csv")
        assert r_csv.status_code == 200
        cd_csv = r_csv.headers["content-disposition"]
        assert "attachment;" in cd_csv
        assert 'filename="' in cd_csv
        assert "filename*=UTF-8''" in cd_csv
        # 必须是纯 ASCII header（能被 latin-1 编码，不含未转义中文/CRLF）
        cd_csv.encode("ascii")

        r_xlsx = client.get("/api/v1/custom-qc/workspace/batch-jobs/job-1/export?format=xlsx")
        assert r_xlsx.status_code == 200
        cd_xlsx = r_xlsx.headers["content-disposition"]
        assert "filename*=UTF-8''" in cd_xlsx
        assert ".xlsx" in cd_xlsx
        cd_xlsx.encode("ascii")

        # 导出内部异常脱敏
        r_err = client.get("/api/v1/custom-qc/workspace/batch-jobs/boom/export?format=xlsx")
        assert r_err.status_code == 500
        detail = str(r_err.json().get("detail") or "")
        assert "psycopg2" not in detail
        assert "secret://" not in detail


# =============================================================================
# 3. rule_validation.py 非阻塞事件循环与批量查询
# =============================================================================


class TestRuleValidationNonBlockingAndBatch:
    def test_sync_crud_routes_are_plain_def(self):
        assert not inspect.iscoroutinefunction(rule_validation.list_candidate_cases)
        assert not inspect.iscoroutinefunction(rule_validation.upsert_case_answer)
        assert not inspect.iscoroutinefunction(rule_validation.remove_case_answer)
        assert not inspect.iscoroutinefunction(rule_validation.approve)

    @pytest.mark.asyncio
    async def test_list_rules_runs_batched_sql_off_event_loop(self, monkeypatch):
        engine = sa.create_engine(
            "sqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        meta = sa.MetaData()
        items_tbl = sa.Table(
            "manual_problem_sample_pool_items",
            meta,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("pool_id", sa.String(64)),
            sa.Column("matched_institute_id", sa.String(64)),
            sa.Column("matched_patient_id", sa.String(64)),
            sa.Column("matched_visit_id", sa.String(64)),
            sa.Column("patient_name", sa.String(64)),
            sa.Column("department", sa.String(64)),
            sa.Column("raw_payload_json", sa.Text),
        )
        runs_tbl, events_tbl = define_rv_tables(meta)
        meta.create_all(engine)
        sessions = sessionmaker(bind=engine)

        sql_count = {"selects": 0}
        entered = threading.Event()
        release = threading.Event()
        main_thread = threading.get_ident()
        query_threads: list[int] = []

        @event.listens_for(engine, "before_cursor_execute")
        def _count_select(_conn, _cursor, statement, _params, _ctx, _many):
            if statement.lstrip().upper().startswith("SELECT"):
                sql_count["selects"] += 1
                query_threads.append(threading.get_ident())
                if sql_count["selects"] == 1:
                    entered.set()
                    assert release.wait(1.0), "事件循环被同步查库阻塞"

        # 构造 10 条待验收规则，验证总 SELECT 次数为常数 3 次（items/runs/events），而非 6*N
        fake_catalog = {
            f"LX0609-{i:03d}": {
                "rule_id": f"LX0609-{i:03d}",
                "name": f"规则{i}",
                "source_document": "入院记录",
                "release_scope": "acceptance_only",
                "policy_summary": "",
                "rule_set_key": rule_validation.RULE_SET_0609,
                "publication_supported": True,
                "impact": None,
            }
            for i in range(1, 11)
        }
        svc = RuleValidationService(
            item_table=items_tbl,
            runs_table=runs_tbl,
            events_table=events_tbl,
            session_factory=sessions,
            catalog=lambda: fake_catalog,
        )
        monkeypatch.setattr(rule_validation, "_service", lambda: svc)

        async def _concurrent_ping():
            for _ in range(200):
                if entered.is_set():
                    release.set()
                    return "unblocked"
                await asyncio.sleep(0.002)
            pytest.fail("主事件循环被阻塞，无法响应并发协程")

        req = Request({"type": "http", "method": "GET", "path": "/api/v1/qc/rule-validation/rules", "headers": []})
        try:
            resp, ping = await asyncio.gather(
                rule_validation.list_rules(
                    req,
                    include_released=False,
                    rule_set_key=rule_validation.RULE_SET_0609,
                    current_user={"id": "admin-1", "roles": ["admin"]},
                ),
                _concurrent_ping(),
            )
            assert ping == "unblocked"
            assert len(resp["data"]["items"]) == 10
            assert sql_count["selects"] == 3  # 批量 3 次查询替代 10*6=60 次 N+1
            assert all(tid != main_thread for tid in query_threads)
        finally:
            engine.dispose()


# =============================================================================
# 4. smart_upload / sync / medical_records_* 线程化与脱敏
# =============================================================================


class TestSmartUploadSyncAndMedicalRecordsThreading:
    @pytest.mark.asyncio
    async def test_smart_upload_suggest_and_confirm_run_pandas_in_threadpool(self, tmp_path, monkeypatch):
        from app.services import async_job_store

        monkeypatch.setattr(async_job_store, "engine", None)
        upload_dir = tmp_path / "uploads"
        file_id = "a1b2c3d4"
        file_dir = upload_dir / file_id
        file_dir.mkdir(parents=True)

        df = pd.DataFrame([{"科室": "内科", "总费用": 1000, "DIP支付标准": 1200}])
        df.to_excel(file_dir / "cases.xlsx", index=False)

        svc = SmartUploadAsyncService(str(upload_dir))
        monkeypatch.setattr(smart_upload, "UPLOAD_DIR", str(upload_dir))
        monkeypatch.setattr(smart_upload, "get_smart_upload_async_service", lambda *_a, **_kw: svc)

        admin_user = {"id": "u-global-admin", "roles": ["admin"], "role": "admin", "institute_id": None}
        monkeypatch.setattr(svc, "assert_file_access", lambda *_a, **_kw: file_dir)

        main_thread = threading.get_ident()
        suggest_threads: list[int] = []
        entered = threading.Event()
        release = threading.Event()
        orig_read_excel = pd.read_excel

        def _tracked_read_excel(*args, **kwargs):
            suggest_threads.append(threading.get_ident())
            entered.set()
            assert release.wait(1.0), "suggest_mapping Excel 读取阻塞了事件循环"
            return orig_read_excel(*args, **kwargs)

        async def _fake_llm(cols, _samples):
            return {
                "mappings": {"科室": "department", "总费用": "total_cost", "DIP支付标准": "dip_payment"},
                "confidence": 0.9,
                "unmapped": [],
                "missing_required": [],
                "fallback": False,
            }

        monkeypatch.setattr(smart_upload.pd, "read_excel", _tracked_read_excel)
        monkeypatch.setattr(smart_upload, "suggest_field_mapping", _fake_llm)

        async def _unblock():
            for _ in range(200):
                if entered.is_set():
                    release.set()
                    return True
                await asyncio.sleep(0.002)
            pytest.fail("主事件循环被 smart_upload.suggest_mapping 阻塞")

        suggest_res, ok = await asyncio.gather(
            smart_upload.suggest_mapping(
                smart_upload.MappingSuggestRequest(file_id=file_id),
                current_user=admin_user,
            ),
            _unblock(),
        )
        assert ok is True
        assert suggest_res["suggested_mappings"]["科室"] == "department"
        assert suggest_threads and all(tid != main_thread for tid in suggest_threads)

        # 验证 confirm_mapping 在工作线程中执行
        confirm_threads: list[int] = []
        orig_confirm = smart_upload._confirm_mapping_sync

        def _tracked_confirm(req, user):
            confirm_threads.append(threading.get_ident())
            return orig_confirm(req, user)

        monkeypatch.setattr(smart_upload, "_confirm_mapping_sync", _tracked_confirm)
        monkeypatch.setattr(smart_upload.pd, "read_excel", orig_read_excel)
        confirm_res = await smart_upload.confirm_mapping(
            smart_upload.MappingConfirmRequest(
                file_id=file_id,
                mappings={"科室": "department", "总费用": "total_cost", "DIP支付标准": "dip_payment"},
            ),
            current_user=admin_user,
        )
        assert confirm_res["success"] is True
        assert confirm_threads == [confirm_threads[0]]
        assert confirm_threads[0] != main_thread

    def test_sync_blocking_routes_are_plain_def_and_sanitize_urls_and_errors(self, monkeypatch):
        for fn in (
            sync_router.get_sync_status,
            sync_router.get_statistics,
            sync_router.get_pg_config,
            sync_router.update_pg_config,
            sync_router.get_sync_policy,
            sync_router.update_sync_policy,
            sync_router.get_pg_sync_tables,
            sync_router.get_pg_sync_table_groups,
            sync_router.update_pg_sync_tables,
            sync_router.test_pg_remote,
            sync_router.test_pg_local,
            sync_router.test_all_connections,
            sync_router.run_preflight,
            sync_router.get_sync_runs,
            sync_router.get_sync_templates,
            sync_router.apply_sync_template,
        ):
            assert not inspect.iscoroutinefunction(fn), f"{fn.__name__} 应为普通 def 避免阻塞事件循环"

        # 构造隔离 FastAPI App 测试连接测试与错误脱敏
        app = FastAPI()
        app.include_router(sync_router.router)
        app.dependency_overrides[sync_router.require_legacy_sync_available] = lambda: None
        app.dependency_overrides[sync_router.require_sync_write_access] = lambda: {
            "id": "sync-admin",
            "roles": ["sync_admin"],
        }
        app.dependency_overrides[sync_router.require_sync_read_access] = lambda: {
            "id": "sync-admin",
            "roles": ["sync_admin"],
        }
        client = TestClient(app)

        monkeypatch.setattr(
            etl_sync,
            "test_remote_connection",
            lambda: {
                "connected": False,
                "url": "postgresql://his_user:***@10.99.88.77:5432/his_prod",
                "display_url": "postgresql://his_user:***@10.99.88.77:5432/his_prod",
                "error": 'psycopg2.OperationalError: could not connect to server 10.99.88.77:5432\nTraceback (most recent call last):\nFile "/srv/app.py"',
            },
        )
        monkeypatch.setattr(
            etl_sync,
            "test_local_connection",
            lambda: {
                "connected": True,
                "version": "PostgreSQL 16.2",
                "url": "postgresql://medqc:***@127.0.0.1:5432/medqc",
                "error": "",
            },
        )

        r_remote = client.post("/api/v1/sync/test-connection/pg-remote")
        assert r_remote.status_code == 200
        d_remote = r_remote.json()["data"]
        assert d_remote["connected"] is False
        assert "url" not in d_remote
        assert "display_url" not in d_remote
        assert "10.99.88.77" not in d_remote["error"]
        assert "psycopg2" not in d_remote["error"]
        assert "Traceback" not in d_remote["error"]

        r_local = client.post("/api/v1/sync/test-connection/pg-local")
        assert r_local.status_code == 200
        d_local = r_local.json()["data"]
        assert d_local["connected"] is True
        assert "url" not in d_local

        r_all = client.post("/api/v1/sync/test-connection/all")
        assert r_all.status_code == 200
        d_all = r_all.json()["data"]
        assert "url" not in d_all["pg_remote"]
        assert "url" not in d_all["pg_local"]
        assert "10.99.88.77" not in json.dumps(d_all, ensure_ascii=False)

        # RuntimeError / OperationalError 脱敏为 503，不暴露连接串与异常文本
        monkeypatch.setattr(
            etl_sync,
            "get_sync_state",
            lambda: (_ for _ in ()).throw(
                RuntimeError("internal crash at postgresql://root:pass@10.0.0.2/secret")
            ),
        )
        r_status = client.get("/api/v1/sync/status")
        assert r_status.status_code == 503
        assert "postgresql://" not in str(r_status.json())
        assert "10.0.0.2" not in str(r_status.json())

    def test_medical_records_detail_export_maintenance_routes_non_blocking(self, monkeypatch):
        for fn in (
            medical_records_detail.get_frontpage_api,
            medical_records_detail.get_frontpage_by_mr_no_api,
            medical_records_detail.get_diagnoses_api,
            medical_records_detail.get_surgeries_api,
            medical_records_detail.get_cost_api,
            medical_records_detail.get_record_content_api,
            medical_records_detail.get_documents_api,
            medical_records_export.get_schema_api,
            medical_records_export.get_table_data_api,
            medical_records_maintenance.save_frontpage_api,
            medical_records_maintenance.save_ai_frontpage_draft_api,
            medical_records_maintenance.get_ai_frontpage_draft_api,
            medical_records_maintenance.save_qc_results_api,
            medical_records_maintenance.get_qc_results_api,
        ):
            assert not inspect.iscoroutinefunction(fn), f"{fn.__name__} 应为普通 def"

        # get_frontpage_sheet_api 保持 async 兼容直接 asyncio.run 调用，同时在工作线程执行同步读取
        main_thread = threading.get_ident()
        observed: list[int] = []
        monkeypatch.setattr(
            medical_records_export,
            "get_frontpage_sheet",
            lambda p, v, **_kw: (observed.append(threading.get_ident()), {"patient_id": p, "visit_id": v})[1],
        )
        req = Request({
            "type": "http",
            "method": "GET",
            "path": "/frontpage-sheet/P1/V1",
            "headers": [],
            "query_string": b"",
        })
        req.state.doctor_case_identity = {"institute_id": "H1"}
        result = asyncio.run(medical_records_export.get_frontpage_sheet_api(req, "P1", "V1"))
        assert result == {"patient_id": "P1", "visit_id": "V1"}
        assert observed and observed[0] != main_thread
