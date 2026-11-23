"""Wave 3 离线回归测试：
1. P1-E3：全站导出公式注入防护（export_safety / qc_workspace / defect_export / frontpage_export / reports CSV）
          及 defect_export_service 纯内存流式化与隔离临时文件防并发串覆
2. P2-B3 + P2-E2：reports.py 角色与持久院区隔离、/qc/trend 时区桶匹配、/qc/summary 真实 pass_rate
3. P1-E4 + P2-B3：dashboard_api.py 角色与持久院区隔离、id 取值修正、_record_identity 外键优先、
                  defect_ranking 真实缺陷数计数、last_week 上界、移除假 KPI/假人名回退
4. P2-B3 + P2-E2：staff_ranking.py 角色与持久院区隔离、周期起点归零至 00:00:00、异常不泄露 str(e)
"""

from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import openpyxl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.export_safety import sanitize_spreadsheet_cell, sanitize_spreadsheet_row
from app.core.security import get_current_user
from app.database import connection as db_connection
from app.database.models.v36_reports import SysUser
from app.routers import dashboard_api, reports, staff_ranking
from app.services.defect_export_service import (
    DefectExportService,
    cleanup_temp_exports,
)
from app.services.frontpage_export_service import ExportFormat, FrontpageExportService
from app.services.qc_workspace.export_service import (
    append_complete_workbook_row,
    render_customer_safe_csv,
    render_customer_safe_workbook,
)


# =====================================================================
# Shared SQLite test environment helper
# =====================================================================

def _build_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / f"w3_exports_legacy_{uuid.uuid4().hex[:8]}.sqlite"
    engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    SysUser.__table__.create(bind=engine, checkfirst=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS medical_records (
                    id VARCHAR(64) PRIMARY KEY,
                    institute_id VARCHAR(128),
                    status VARCHAR(64),
                    department VARCHAR(64),
                    record_type VARCHAR(64)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO medical_records (id, institute_id, status, department, record_type)
                VALUES
                    ('rec-a-1', 'HOSP-A', 'running', '心内科', 'inpatient'),
                    ('rec-a-2', 'HOSP-A', 'final', '呼吸科', 'inpatient'),
                    ('rec-a-op', 'HOSP-A', 'completed', '急诊科', 'outpatient'),
                    ('rec-b-1', 'HOSP-B', 'running', '神经内科', 'inpatient')
                """
            )
        )

    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    now = datetime.utcnow()
    with session_factory() as session:
        session.add_all(
            [
                SysUser(
                    id="u-admin",
                    username="admin_u",
                    display_name="Global Admin",
                    role="admin",
                    roles_json=json.dumps(["admin"]),
                    institute_id=None,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-mgr-a",
                    username="mgr_a",
                    display_name="Manager A",
                    role="qc_manager",
                    roles_json=json.dumps(["qc_manager"]),
                    institute_id="HOSP-A",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-mgr-b",
                    username="mgr_b",
                    display_name="Manager B",
                    role="qc_manager",
                    roles_json=json.dumps(["qc_manager"]),
                    institute_id="HOSP-B",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-staff-a",
                    username="staff_a",
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
                    display_name="Doctor A",
                    role="doctor",
                    roles_json=json.dumps(["doctor"]),
                    institute_id="HOSP-A",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-noscope",
                    username="mgr_noscope",
                    display_name="No Scope",
                    role="qc_manager",
                    roles_json=json.dumps(["qc_manager"]),
                    institute_id="",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-inactive",
                    username="inactive_u",
                    display_name="Inactive",
                    role="admin",
                    roles_json=json.dumps(["admin"]),
                    institute_id=None,
                    is_active=False,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.commit()

    monkeypatch.setattr(db_connection, "SessionLocal", session_factory)
    monkeypatch.setattr(reports, "_QC_EXPORT_DIR", tmp_path / "qc_exports")
    monkeypatch.setattr(reports, "_QC_SUMMARY_CACHE", None)
    monkeypatch.setattr(reports, "_QC_SUMMARY_CACHE_TS", 0.0)

    app = FastAPI()
    app.include_router(reports.router)
    app.include_router(dashboard_api.router)
    app.include_router(staff_ranking.router)

    current = {"user": {"id": "u-admin", "roles": ["admin"]}}
    app.dependency_overrides[get_current_user] = lambda: current["user"]

    def set_user(user_id: str, **extra):
        current["user"] = {"id": user_id, **extra}

    client = TestClient(app)
    return {
        "client": client,
        "set_user": set_user,
        "engine": engine,
        "session_factory": session_factory,
    }


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ctx = _build_env(tmp_path, monkeypatch)
    try:
        yield ctx
    finally:
        ctx["engine"].dispose()


# =====================================================================
# 1. P1-E3: Formula Injection Safety & Pure-Memory Defect Export
# =====================================================================

class TestExportSafetyAndServices:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("=CMD|' /C calc'!A0", "'=CMD|' /C calc'!A0"),
            ("+1+1", "'+1+1"),
            ("-1+cmd", "'-1+cmd"),
            ("@SUM(1,2)", "'@SUM(1,2)"),
            ("\t=1+1", "'\t=1+1"),
            ("\rfoo", "'\rfoo"),
            ("  =HYPERLINK(\"http://x\")", "'  =HYPERLINK(\"http://x\")"),
            (" \n +2+2", "' \n +2+2"),
            ("   -cmd", "'   -cmd"),
            (" \tfoo", "' \tfoo"),
            (" \rbar", "' \rbar"),
            ("'=already_escaped", "'=already_escaped"),
            ("正常中文", "正常中文"),
            ("2026-11-23 10:00:00", "2026-11-23 10:00:00"),
            ("", ""),
        ],
    )
    def test_sanitize_spreadsheet_cell_strings(self, raw, expected):
        assert sanitize_spreadsheet_cell(raw) == expected

    def test_sanitize_spreadsheet_cell_preserves_numeric_types(self):
        assert sanitize_spreadsheet_cell(0) == 0
        assert isinstance(sanitize_spreadsheet_cell(0), int)
        assert sanitize_spreadsheet_cell(45) == 45
        assert sanitize_spreadsheet_cell(-12) == -12
        assert isinstance(sanitize_spreadsheet_cell(-12), int)
        assert sanitize_spreadsheet_cell(-3.14) == -3.14
        assert isinstance(sanitize_spreadsheet_cell(-3.14), float)
        dec = Decimal("-9.50")
        assert sanitize_spreadsheet_cell(dec) == dec
        assert isinstance(sanitize_spreadsheet_cell(dec), Decimal)
        assert sanitize_spreadsheet_cell(None) is None
        assert sanitize_spreadsheet_cell(True) is True
        assert sanitize_spreadsheet_row(["=1+1", -5, "ok"]) == ["'=1+1", -5, "ok"]

    def test_qc_workspace_export_sanitizes_workbook_and_csv(self):
        summary = {
            "operation_ref": "=HYPERLINK(\"http://evil\")",
            "result_count": 1,
            "issue_records": 1,
            "status_counts": {"non_compliant": 1},
        }
        items = [{"is_confirmed_issue": True, "status": "non_compliant"}]
        rows = [["+rec-1", "R-1", "  =rule", "不合规", "-code", "@SUM(1,1)", "\t建议", "正常证据"]]

        wb = openpyxl.load_workbook(
            render_customer_safe_workbook(items=items, rows=rows, summary=summary),
            data_only=False,
        )
        assert wb["管理摘要"].cell(2, 2).value == "'=HYPERLINK(\"http://evil\")"
        assert wb["管理摘要"].cell(3, 2).value == 1
        assert wb["问题明细"].cell(2, 1).value == "'+rec-1"
        assert wb["问题明细"].cell(2, 3).value == "'  =rule"
        assert wb["问题明细"].cell(2, 5).value == "'-code"
        assert wb["问题明细"].cell(2, 6).value == "'@SUM(1,1)"
        assert wb["问题明细"].cell(2, 7).value == "'\t建议"
        assert wb["问题明细"].cell(2, 8).value == "正常证据"

        csv_stream = render_customer_safe_csv(rows=rows, summary=summary)
        parsed = list(csv.reader(StringIO(csv_stream.getvalue())))
        assert parsed[1][1] == "'=HYPERLINK(\"http://evil\")"
        data_row = parsed[-1]
        assert data_row[0] == "'+rec-1"
        assert data_row[2] == "'  =rule"
        assert data_row[5] == "'@SUM(1,1)"

        # append_complete_workbook_row still preserves numeric types
        wb2 = openpyxl.Workbook()
        append_complete_workbook_row(wb2.active, ["=1+1", -42, -1.5, "ok"])
        assert wb2.active.cell(1, 1).value == "'=1+1"
        assert wb2.active.cell(1, 2).value == -42
        assert wb2.active.cell(1, 3).value == -1.5
        assert wb2.active.cell(1, 4).value == "ok"

    def test_frontpage_export_sanitizes_all_formats_and_keeps_numbers(self):
        service = FrontpageExportService()
        fp = {
            "patient_name": "=CMD|' /C calc'!A0",
            "sex": "男",
            "age": 45,
            "los_days": 9,
            "total_cost": 85000.5,
            "diagnoses": [
                {
                    "diagnosis_type": "主诊断",
                    "diagnosis_name": "  +恶性肿瘤",
                    "diagnosis_code": "-I21.0",
                    "admission_condition": "1",
                }
            ],
            "surgeries": [
                {
                    "surgery_name": "@SUM(A1:A2)",
                    "surgery_code": "36.07",
                    "surgery_date": "2026-01-01",
                    "surgeon_name": "\t李医生",
                    "anesthesia_method": "全麻",
                }
            ],
        }
        for fmt in (ExportFormat.NHC, ExportFormat.INSURANCE, ExportFormat.SETTLEMENT):
            raw = service.export(fp, fmt)
            wb = openpyxl.load_workbook(BytesIO(raw), data_only=False)
            ws = wb.active
            values = [cell.value for row in ws.iter_rows() for cell in row if cell.value is not None]
            assert "'=CMD|' /C calc'!A0" in values
            assert "'  +恶性肿瘤" in values
            assert "'-I21.0" in values
            assert "'@SUM(A1:A2)" in values
            assert "'\t李医生" in values
            assert 45 in values
            assert 9 in values
            assert 85000.5 in values

    @pytest.mark.asyncio
    async def test_defect_export_pure_memory_and_isolated_legacy_tempfiles(self, tmp_path):
        service = DefectExportService()
        sample_defects = [
            {
                "record_id": "=REC-1",
                "patient_name": " +张三",
                "department": "心内科",
                "rule_name": "-规则1",
                "description": "@SUM(1,2)",
                "severity": "critical",
                "category": "\t首页",
                "location": "主诊断",
                "suggestion": "\r立即整改",
                "status": "pending",
                "created_at": "2026-11-23T08:00:00",
            }
        ]

        # 1. Primary export(): pure in-memory BytesIO, zero disk file creation
        with patch.object(service, "_fetch_defects", return_value=sample_defects):
            xlsx_res = await service.export(format="xlsx")
            csv_res = await service.export(format="csv")

        assert "file_path" not in xlsx_res
        assert "file_path" not in csv_res
        assert isinstance(xlsx_res["content"], BytesIO)
        assert isinstance(csv_res["content"], BytesIO)

        wb = openpyxl.load_workbook(xlsx_res["content"], data_only=False)
        row2 = [cell.value for cell in wb.active[2]]
        assert row2[0] == "'=REC-1"
        assert row2[1] == "' +张三"
        assert row2[3] == "'-规则1"
        assert row2[4] == "'@SUM(1,2)"
        assert row2[6] == "'\t首页"
        assert row2[8] == "'\r立即整改"

        csv_rows = list(csv.reader(StringIO(csv_res["content"].getvalue().decode("utf-8-sig"))))
        assert csv_rows[1][0] == "'=REC-1"
        assert csv_rows[1][1] == "' +张三"

        # 2. Legacy compatibility (_export_xlsx/_export_csv with export_dir):
        #    NEVER writes to shared downloads/ directory, and same-second concurrent calls get distinct temp files
        fake_downloads = tmp_path / "downloads"
        fake_downloads.mkdir()
        translated = [service._translate_row(d) for d in sample_defects]
        try:
            r1 = await service._export_xlsx(translated, str(fake_downloads), "20261123_120000")
            r2 = await service._export_xlsx(translated, str(fake_downloads), "20261123_120000")
            assert list(fake_downloads.iterdir()) == []
            assert r1["file_path"] != r2["file_path"]
            assert Path(r1["file_path"]).exists()
            assert Path(r2["file_path"]).exists()
            assert r1["file_name"] == "缺陷列表_20261123_120000.xlsx"
        finally:
            cleanup_temp_exports(max_age_seconds=0)


# =====================================================================
# 2. P2-B3 + P2-E2: reports.py
# =====================================================================

class TestReportsRegressions:
    def test_reports_role_and_institute_isolation_and_cache_separation(self, env):
        client = env["client"]
        set_user = env["set_user"]

        # Unprivileged / unscoped / inactive denied across all report endpoints
        for uid in ("u-doc-a", "u-noscope", "u-inactive", "u-missing"):
            set_user(uid)
            assert client.get("/api/v1/reports/qc/summary").status_code == 403
            assert client.get("/api/v1/reports/qc/trend?period=week").status_code == 403
            assert client.post("/api/v1/reports/qc/export", json={}).status_code == 403

        # qc_staff can read summary/trend, but cannot export
        set_user("u-staff-a")
        assert client.post("/api/v1/reports/qc/export", json={}).status_code == 403

        mock_sb = MagicMock()
        view_resp = SimpleNamespace(
            data=[
                {
                    "record_id": "rec-a-1",
                    "total_documents": 10,
                    "passed_count": 7,
                    "warning_count": 2,
                    "failed_count": 1,
                    "pending_count": 0,
                    "avg_qc_score": 90.0,
                    "last_analyzed_time": datetime.now(timezone.utc).isoformat(),
                },
                {
                    "record_id": "rec-b-1",
                    "total_documents": 5,
                    "passed_count": 1,
                    "warning_count": 0,
                    "failed_count": 4,
                    "pending_count": 0,
                    "avg_qc_score": 50.0,
                    "last_analyzed_time": datetime.now(timezone.utc).isoformat(),
                },
            ]
        )
        rules_resp = SimpleNamespace(data=[{"id": "r1"}, {"id": "r2"}])
        defects_resp = SimpleNamespace(
            data=[
                {"category": "首页", "record_id": "rec-a-1"},
                {"category": "病程", "record_id": "rec-b-1"},
            ]
        )

        # HOSP-A manager sees ONLY HOSP-A stats & real pass_rate (70.0%)
        set_user("u-mgr-a")
        with patch("app.routers.reports.get_supabase", return_value=mock_sb), patch(
            "app.routers.reports.async_execute",
            side_effect=[view_resp, rules_resp, defects_resp],
        ):
            resp_a = client.get("/api/v1/reports/qc/summary")
        assert resp_a.status_code == 200
        kpis_a = resp_a.json()["data"]["kpis"]
        assert kpis_a["total_records"] == 1
        assert kpis_a["passed"] == 7
        assert kpis_a["pass_rate"] == 70.0
        assert resp_a.json()["data"]["top_categories"] == [{"category": "首页", "issue_count": 1}]

        # HOSP-B manager MUST NOT receive HOSP-A's cached summary (isolated cache + isolated data)
        set_user("u-mgr-b")
        with patch("app.routers.reports.get_supabase", return_value=mock_sb), patch(
            "app.routers.reports.async_execute",
            side_effect=[view_resp, rules_resp, defects_resp],
        ):
            resp_b = client.get("/api/v1/reports/qc/summary")
        assert resp_b.status_code == 200
        kpis_b = resp_b.json()["data"]["kpis"]
        assert kpis_b["total_records"] == 1
        assert kpis_b["passed"] == 1
        assert kpis_b["pass_rate"] == 20.0
        assert resp_b.json()["data"]["top_categories"] == [{"category": "病程", "issue_count": 1}]

    def test_reports_trend_handles_aware_and_naive_timestamps(self, env):
        client = env["client"]
        env["set_user"]("u-admin")
        now_utc = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
        plus8 = timezone(timedelta(hours=8))
        yesterday_plus8 = (now_utc - timedelta(days=1)).astimezone(plus8)

        mock_sb = MagicMock()
        trend_resp = SimpleNamespace(
            data=[
                {
                    "record_id": "rec-a-1",
                    "passed_count": 4,
                    "warning_count": 1,
                    "failed_count": 0,
                    "pending_count": 0,
                    "avg_qc_score": 92.0,
                    "last_analyzed_time": now_utc.isoformat().replace("+00:00", "Z"),
                },
                {
                    "record_id": "rec-a-2",
                    "passed_count": 2,
                    "warning_count": 0,
                    "failed_count": 2,
                    "pending_count": 0,
                    "avg_qc_score": 80.0,
                    "last_analyzed_time": yesterday_plus8.isoformat(),
                },
                {
                    "record_id": "rec-b-1",
                    "passed_count": 1,
                    "warning_count": 0,
                    "failed_count": 0,
                    "pending_count": 0,
                    "avg_qc_score": 100.0,
                    "last_analyzed_time": (now_utc - timedelta(days=2)).replace(tzinfo=None).isoformat(),
                },
            ]
        )

        with patch("app.routers.reports.get_supabase", return_value=mock_sb), patch(
            "app.routers.reports.async_execute",
            return_value=trend_resp,
        ):
            resp = client.get("/api/v1/reports/qc/trend?period=week")

        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 7
        assert sum(item["record_count"] for item in items) == 3
        today_bucket = items[-1]
        assert today_bucket["record_count"] == 1
        assert today_bucket["average_score"] == 92.0
        assert today_bucket["pass_rate"] == 80.0

    def test_reports_export_sanitizes_formula_injection_and_isolates_download(self, env):
        client = env["client"]
        set_user = env["set_user"]
        mock_sb = MagicMock()
        export_resp = SimpleNamespace(
            data=[
                {
                    "record_id": "=CMD|' /C calc'!A0",
                    "institute_id": "HOSP-A",
                    "total_documents": 3,
                    "passed_count": 2,
                    "warning_count": 1,
                    "failed_count": 0,
                    "pending_count": 0,
                    "avg_qc_score": 88.5,
                    "last_analyzed_time": "2026-11-23T10:00:00Z",
                },
                {
                    "record_id": "rec-b-1",
                    "institute_id": "HOSP-B",
                    "total_documents": 2,
                    "passed_count": 1,
                    "warning_count": 0,
                    "failed_count": 1,
                    "pending_count": 0,
                    "avg_qc_score": 70.0,
                    "last_analyzed_time": "2026-11-23T10:00:00Z",
                },
            ]
        )

        set_user("u-mgr-a")
        with patch("app.routers.reports.get_supabase", return_value=mock_sb), patch(
            "app.routers.reports.async_execute",
            return_value=export_resp,
        ):
            created = client.post("/api/v1/reports/qc/export", json={})

        assert created.status_code == 200
        assert created.json()["data"]["count"] == 1
        download_url = created.json()["data"]["download_url"]

        dl_a = client.get(download_url)
        assert dl_a.status_code == 200
        rows = list(csv.reader(StringIO(dl_a.content.decode("utf-8"))))
        assert len(rows) == 2
        assert rows[1][0] == "'=CMD|' /C calc'!A0"
        assert "rec-b-1" not in dl_a.content.decode("utf-8")

        # HOSP-B manager cannot download HOSP-A export
        set_user("u-mgr-b")
        assert client.get(download_url).status_code == 403

        # Global admin can download
        set_user("u-admin")
        assert client.get(download_url).status_code == 200


# =====================================================================
# 3. P1-E4 + P2-B3: dashboard_api.py
# =====================================================================

class _TableMockSupabase:
    """按表名分派数据的轻量 mock，同时记录查询过滤条件以供断言。"""

    def __init__(self, table_data: dict[str, list[dict]]):
        self.table_data = table_data
        self.queries: list[dict] = []

    def table(self, name: str):
        return _TableMockQuery(self, name)


class _TableMockQuery:
    def __init__(self, parent: _TableMockSupabase, table_name: str):
        self.parent = parent
        self.table_name = table_name
        self.filters: list[tuple[str, str, object]] = []
        self.selected: str = "*"

    def select(self, cols="*", **_kwargs):
        self.selected = cols
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val))
        return self

    def gte(self, col, val):
        self.filters.append(("gte", col, val))
        return self

    def lt(self, col, val):
        self.filters.append(("lt", col, val))
        return self

    def limit(self, _n):
        return self


async def _mock_table_execute(query: _TableMockQuery):
    query.parent.queries.append(
        {"table": query.table_name, "selected": query.selected, "filters": list(query.filters)}
    )
    rows = list(query.parent.table_data.get(query.table_name, []))
    for op, col, val in query.filters:
        if op == "eq":
            rows = [r for r in rows if r.get(col) == val]
        elif op == "gte":
            rows = [r for r in rows if str(r.get(col) or "") >= str(val)]
        elif op == "lt":
            rows = [r for r in rows if str(r.get(col) or "") < str(val)]
    return SimpleNamespace(data=rows)


class TestDashboardAPIRegressions:
    def test_dashboard_authz_and_persistent_institute_scope(self, env):
        client = env["client"]
        set_user = env["set_user"]

        for uid in ("u-doc-a", "u-noscope", "u-inactive", "u-missing"):
            set_user(uid)
            assert client.get("/api/v1/dashboard/todo-stats").status_code == 403
            assert client.get("/api/v1/dashboard/performance").status_code == 403
            assert client.get("/api/v1/dashboard/overview").status_code == 403

        # Verify current_user with only "id" (not "user_id") works and isolates by institute
        sb = _TableMockSupabase(
            {
                "medical_records": [
                    {"id": "rec-a-1", "institute_id": "HOSP-A", "status": "running", "department": "心内科", "record_type": "inpatient"},
                    {"id": "rec-b-1", "institute_id": "HOSP-B", "status": "running", "department": "神经内科", "record_type": "inpatient"},
                ],
                "qc_results": [
                    {"id": "qr-1", "record_id": "rec-a-1", "institute_id": "HOSP-A", "overall_score": 95.0, "grade": "A"},
                    {"id": "qr-2", "record_id": "rec-b-1", "institute_id": "HOSP-B", "overall_score": 60.0, "grade": "C"},
                ],
                "qc_appeals": [
                    {"id": "ap-1", "record_id": "rec-a-1", "institute_id": "HOSP-A", "status": "pending"},
                    {"id": "ap-2", "record_id": "rec-b-1", "institute_id": "HOSP-B", "status": "pending"},
                ],
                "qc_remediation_tasks": [
                    {"id": "rt-1", "record_id": "rec-a-1", "institute_id": "HOSP-A", "status": "in_progress"},
                    {"id": "rt-2", "record_id": "rec-b-1", "institute_id": "HOSP-B", "status": "in_progress"},
                ],
            }
        )
        set_user("u-mgr-a")  # only "id" is set, no "user_id"
        with patch("app.routers.dashboard_api.get_supabase", return_value=sb), patch(
            "app.routers.dashboard_api.async_execute",
            side_effect=_mock_table_execute,
        ):
            resp = client.get("/api/v1/dashboard/todo-stats?scene=all")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["overview"]["total_records"] == 1
        assert data["overview"]["avg_score"] == 95.0
        assert data["overview"]["grade_a"] == 1
        assert data["defect_stats"]["clinical_appeals"] == 1
        assert data["task_stats"]["in_progress"] == 1
        assert "神经内科" not in data["department_breakdown"]

    def test_dashboard_record_identity_preserves_child_matches_for_non_all_scenes(self, env):
        client = env["client"]
        env["set_user"]("u-admin")
        sb = _TableMockSupabase(
            {
                "medical_records": [
                    {"id": "rec-run-1", "status": "running", "department": "心内科", "record_type": "inpatient"},
                    {"id": "rec-fin-1", "status": "final", "department": "外科", "record_type": "inpatient"},
                ],
                "qc_results": [
                    # Child PK `id` differs from FK `record_id`!
                    {"id": "qc-row-pk-101", "record_id": "rec-run-1", "overall_score": 92.0, "grade": "A"},
                    {"id": "qc-row-pk-102", "record_id": "rec-fin-1", "overall_score": 78.0, "grade": "B"},
                ],
                "qc_appeals": [
                    {"id": "appeal-pk-201", "record_id": "rec-run-1", "status": "pending"},
                    {"id": "appeal-pk-202", "record_id": "rec-fin-1", "status": "pending"},
                ],
                "qc_remediation_tasks": [
                    {"id": "task-pk-301", "record_id": "rec-run-1", "status": "overdue"},
                    {"id": "task-pk-302", "record_id": "rec-fin-1", "status": "in_progress"},
                ],
            }
        )
        with patch("app.routers.dashboard_api.get_supabase", return_value=sb), patch(
            "app.routers.dashboard_api.async_execute",
            side_effect=_mock_table_execute,
        ):
            running = client.get("/api/v1/dashboard/todo-stats?scene=running")
            outpatient = client.get("/api/v1/dashboard/todo-stats?scene=outpatient_emergency")

        assert running.status_code == 200
        run_data = running.json()["data"]
        assert run_data["overview"]["total_records"] == 1
        assert run_data["overview"]["avg_score"] == 92.0
        assert run_data["overview"]["grade_a"] == 1
        assert run_data["defect_stats"]["clinical_appeals"] == 1
        assert run_data["task_stats"]["countdown"] == 1
        assert run_data["task_stats"]["in_progress"] == 0

        # Non-matching scene returns real zeros (appeals & tasks must NOT leak across scenes)
        assert outpatient.status_code == 200
        op_data = outpatient.json()["data"]
        assert op_data["overview"]["total_records"] == 0
        assert op_data["overview"]["avg_score"] == 0.0
        assert op_data["overview"]["pass_rate"] == 0.0
        assert op_data["defect_stats"]["clinical_appeals"] == 0
        assert op_data["task_stats"]["countdown"] == 0

    def test_dashboard_performance_defect_count_and_last_week_upper_bound(self, env):
        client = env["client"]
        env["set_user"]("u-admin")

        now = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
        this_week_mon = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        last_week_wed = this_week_mon - timedelta(days=5)
        this_week_tue = this_week_mon + timedelta(hours=10)

        sb = _TableMockSupabase(
            {
                "qc_results": [
                    # Last week: Alice reviewed 1 record with 5 defects; Bob reviewed 3 records with 0 defects
                    {"id": "q1", "record_id": "rec-a-1", "analyzed_by": "Alice", "defect_count": 5, "created_at": last_week_wed.isoformat()},
                    {"id": "q2", "record_id": "rec-a-2", "analyzed_by": "Bob", "defect_count": 0, "created_at": last_week_wed.isoformat()},
                    {"id": "q3", "record_id": "rec-a-3", "analyzed_by": "Bob", "defect_count": 0, "created_at": last_week_wed.isoformat()},
                    {"id": "q4", "record_id": "rec-a-4", "analyzed_by": "Bob", "defect_count": 0, "created_at": last_week_wed.isoformat()},
                    # This week: Charlie should be EXCLUDED when period=last_week!
                    {"id": "q5", "record_id": "rec-a-5", "analyzed_by": "Charlie", "defect_count": 99, "created_at": this_week_tue.isoformat()},
                ],
            }
        )

        with patch("app.routers.dashboard_api.get_supabase", return_value=sb), patch(
            "app.routers.dashboard_api.async_execute",
            side_effect=_mock_table_execute,
        ):
            resp = client.get("/api/v1/dashboard/performance?period=last_week")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["defect_ranking"] == [{"name": "Alice", "count": 5, "rank": 1}]
        assert data["record_ranking"] == [
            {"name": "Bob", "count": 3, "rank": 1},
            {"name": "Alice", "count": 1, "rank": 2},
        ]
        # Verify upper bound filter `lt` was applied on created_at
        qc_query = next(q for q in sb.queries if q["table"] == "qc_results")
        assert ("lt", "created_at", this_week_mon.isoformat()) in qc_query["filters"]
        assert ("gte", "created_at", (this_week_mon - timedelta(days=7)).isoformat()) in qc_query["filters"]

    def test_dashboard_no_fake_kpis_or_fake_staff_names_on_empty_or_timeout(self, env):
        client = env["client"]
        env["set_user"]("u-admin")

        # 1. Timeout / DB unavailable -> explicit 503 (never 87.5 / 94.2 / 王质控)
        with patch("app.routers.dashboard_api.get_supabase", return_value=None):
            r_todo = client.get("/api/v1/dashboard/todo-stats")
            r_over = client.get("/api/v1/dashboard/overview")
            r_perf = client.get("/api/v1/dashboard/performance")
        assert r_todo.status_code == 503
        assert r_over.status_code == 503
        assert r_perf.status_code == 503

        # 2. Empty DB -> real empty lists / zeros (never 87.5 / 94.2 / 王质控 / 张质控)
        empty_sb = _TableMockSupabase(
            {
                "medical_records": [],
                "qc_results": [],
                "qc_appeals": [],
                "qc_remediation_tasks": [],
            }
        )
        with patch("app.routers.dashboard_api.get_supabase", return_value=empty_sb), patch(
            "app.routers.dashboard_api.async_execute",
            side_effect=_mock_table_execute,
        ):
            todo_empty = client.get("/api/v1/dashboard/todo-stats")
            over_empty = client.get("/api/v1/dashboard/overview")
            perf_empty = client.get("/api/v1/dashboard/performance")

        assert todo_empty.status_code == 200
        t_data = todo_empty.json()["data"]
        assert t_data["overview"]["avg_score"] == 0.0
        assert t_data["overview"]["pass_rate"] == 0.0
        assert t_data["task_stats"] == {"countdown": 0, "in_progress": 0, "not_started": 0}
        assert t_data["record_stats"] == {"pending_review": 0, "pending_recheck": 0, "total": 0}

        assert over_empty.status_code == 200
        o_data = over_empty.json()["data"]
        assert o_data["avg_score"] == 0.0
        assert o_data["pass_rate"] == 0.0

        assert perf_empty.status_code == 200
        p_data = perf_empty.json()["data"]
        assert p_data["defect_ranking"] == []
        assert p_data["record_ranking"] == []
        assert "王质控" not in json.dumps(p_data, ensure_ascii=False)
        assert "张质控" not in json.dumps(p_data, ensure_ascii=False)


# =====================================================================
# 4. P2-B3 + P2-E2: staff_ranking.py
# =====================================================================

class TestStaffRankingRegressions:
    def test_period_start_zeroed_to_midnight(self):
        ref = datetime(2026, 11, 25, 16, 42, 33, 987654)  # Wednesday
        week_start = staff_ranking._get_period_start("this_week", now=ref)
        month_start = staff_ranking._get_period_start("this_month", now=ref)
        quarter_start = staff_ranking._get_period_start("this_quarter", now=ref)

        assert week_start == datetime(2026, 11, 23, 0, 0, 0, 0)
        assert month_start == datetime(2026, 11, 1, 0, 0, 0, 0)
        assert quarter_start == datetime(2026, 10, 1, 0, 0, 0, 0)
        assert staff_ranking._get_period_start("unknown", now=ref) is None

    def test_staff_ranking_role_and_institute_isolation(self, env):
        client = env["client"]
        set_user = env["set_user"]

        for uid in ("u-doc-a", "u-noscope", "u-inactive", "u-missing"):
            set_user(uid)
            assert client.get("/api/v1/staff-ranking").status_code == 403

        mock_sb = MagicMock()
        rows_resp = SimpleNamespace(
            data=[
                {
                    "user_id": "u-staff-a",
                    "name": "Staff A",
                    "department": "心内科",
                    "qc_count": 30,
                    "recheck_count": 5,
                    "defect_found": 10,
                    "pass_rate": 90.0,
                    "avg_daily": 3.0,
                },
                {
                    "user_id": "u-staff-b",
                    "name": "Staff B",
                    "department": "神经内科",
                    "qc_count": 50,
                    "recheck_count": 8,
                    "defect_found": 20,
                    "pass_rate": 80.0,
                    "avg_daily": 5.0,
                },
            ]
        )

        # HOSP-A manager sees ONLY HOSP-A staff
        set_user("u-mgr-a")
        with patch("app.routers.staff_ranking.get_supabase", return_value=mock_sb), patch(
            "app.routers.staff_ranking.async_execute",
            return_value=rows_resp,
        ):
            resp_a = client.get("/api/v1/staff-ranking")
        assert resp_a.status_code == 200
        data_a = resp_a.json()["data"]
        assert [r["user_id"] for r in data_a["rankings"]] == ["u-staff-a"]
        assert data_a["summary"]["total_qc"] == 30
        assert data_a["summary"]["staff_count"] == 1

        # Global admin sees all staff
        set_user("u-admin")
        with patch("app.routers.staff_ranking.get_supabase", return_value=mock_sb), patch(
            "app.routers.staff_ranking.async_execute",
            return_value=rows_resp,
        ):
            resp_admin = client.get("/api/v1/staff-ranking")
        assert resp_admin.status_code == 200
        assert len(resp_admin.json()["data"]["rankings"]) == 2

    def test_staff_ranking_error_does_not_leak_internal_exception(self, env):
        client = env["client"]
        env["set_user"]("u-admin")
        mock_sb = MagicMock()

        async def _boom(_query):
            raise RuntimeError("FATAL: password authentication failed for internal_pg_user_xyz")

        with patch("app.routers.staff_ranking.get_supabase", return_value=mock_sb), patch(
            "app.routers.staff_ranking.async_execute",
            side_effect=_boom,
        ):
            resp = client.get("/api/v1/staff-ranking")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["rankings"] == []
        assert body["message"] == "暂无排名数据"
        serialized = json.dumps(body, ensure_ascii=False)
        assert "FATAL" not in serialized
        assert "password" not in serialized
        assert "internal_pg_user_xyz" not in serialized
