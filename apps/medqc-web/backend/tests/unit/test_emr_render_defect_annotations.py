"""原病历缺陷标注读取回归：qc_results 当前表结构没有 evaluation_results 列。

用 SQLite 按 alembic 的 qc_results 列建表，经真实 _PgClient 拼 SQL 执行，
证明标注从 raw_output 还原且不再查询不存在的列。数据均为合成病例 C01。
"""

import json
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.core.supabase_client import _PgClient, _Query
from app.routers import emr_render as emr_router_module

# 与 alembic_upgrade_preview.sql 中 qc_results 定义一致（无 issues / evaluation_results）
_ALEMBIC_QC_RESULTS_DDL = """
CREATE TABLE qc_results (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    record_id VARCHAR(100) NOT NULL,
    rule_set VARCHAR(100),
    overall_score FLOAT,
    grade VARCHAR(10),
    defect_count INTEGER NOT NULL,
    analysis_engine VARCHAR(30),
    analysis_date TIMESTAMP,
    raw_output TEXT,
    created_by VARCHAR(36),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
)
"""

_CONTENT = "主诉：发热3天。现病史：患者C01三天前出现发热。"


def _session_factory(extra_columns: str = ""):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ddl = _ALEMBIC_QC_RESULTS_DDL
    if extra_columns:
        ddl = ddl.replace("updated_at TIMESTAMP NOT NULL", f"updated_at TIMESTAMP NOT NULL, {extra_columns}")
    with engine.begin() as conn:
        conn.execute(text(ddl))
    return engine, sessionmaker(bind=engine)


def _insert_result(engine, *, result_id: str, raw_output: dict, created_at: datetime, **extra):
    row = {
        "id": result_id,
        "record_id": "C01",
        "defect_count": len(raw_output.get("issues") or []),
        "raw_output": json.dumps(raw_output, ensure_ascii=False),
        "created_at": created_at,
        "updated_at": created_at,
        **extra,
    }
    cols = ", ".join(row)
    params = ", ".join(f":{key}" for key in row)
    with engine.begin() as conn:
        conn.execute(text(f"INSERT INTO qc_results ({cols}) VALUES ({params})"), row)


def _client(monkeypatch, session_factory) -> TestClient:
    monkeypatch.setattr(emr_router_module, "get_supabase", lambda: _PgClient(session_factory))
    monkeypatch.setattr(
        emr_router_module,
        "_load_documents_from_bundle",
        lambda **_kwargs: {
            "documents": [{"id": "DOC-1", "doc_type": "admission_record", "content": _CONTENT}],
            "documents_tree": [],
            "empty_reason": "",
        },
    )
    monkeypatch.setattr(emr_router_module, "pick_document", lambda documents, **_kwargs: documents[0])
    monkeypatch.setattr(
        emr_router_module,
        "build_render_view",
        lambda selected: {"content": selected["content"], "content_type": "text"},
    )
    app = FastAPI()
    app.include_router(emr_router_module.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-qc",
        "roles": ["qc_manager"],
        "role": "qc_manager",
    }
    return TestClient(app)


def test_render_restores_annotations_from_raw_output_on_alembic_schema(monkeypatch):
    engine, factory = _session_factory()
    _insert_result(
        engine,
        result_id="R-OLD",
        raw_output={"issues": [{"id": "old", "description": "旧结果", "evidence": "主诉"}]},
        created_at=datetime(2026, 10, 1),
    )
    _insert_result(
        engine,
        result_id="R-NEW",
        raw_output={
            "issues": [
                {
                    "id": "ISSUE-1",
                    "description": "现病史未写明体温峰值",
                    "evidence": "三天前出现发热",
                    "severity": "error",
                    "rule_name": "现病史完整性",
                }
            ],
            "evaluation_results": [
                {"rule_id": "LX-PASS", "status": "compliant", "is_compliant": True},
                {
                    "rule_id": "LX-FAIL",
                    "status": "non_compliant",
                    "is_compliant": False,
                    "findings": "主诉未写明伴随症状",
                    "evidence": "主诉：发热3天",
                },
            ],
        },
        created_at=datetime(2026, 10, 2),
    )

    response = _client(monkeypatch, factory).get("/api/v1/emr/C01/render")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["annotation_status"] == "loaded"
    assert [item["defect_id"] for item in data["defect_annotations"]] == ["ISSUE-1", "LX-FAIL"]
    first = data["defect_annotations"][0]
    assert _CONTENT[first["start_offset"]:first["end_offset"]] == "三天前出现发热"
    assert data["total_annotations"] == 2


def test_render_prefers_legacy_issues_column_when_present(monkeypatch):
    engine, factory = _session_factory(extra_columns="issues TEXT")
    _insert_result(
        engine,
        result_id="R-LEGACY",
        raw_output={"issues": []},
        created_at=datetime(2026, 10, 2),
        issues=json.dumps([{"id": "LEGACY-1", "description": "旧库独立列", "evidence": "主诉"}], ensure_ascii=False),
    )

    data = _client(monkeypatch, factory).get("/api/v1/emr/C01/render").json()["data"]

    assert data["annotation_status"] == "loaded"
    assert [item["defect_id"] for item in data["defect_annotations"]] == ["LEGACY-1"]


def test_render_marks_annotations_unavailable_instead_of_silently_empty(monkeypatch):
    # 表不存在等数据库错误：不能伪装成“无缺陷”
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    data = _client(monkeypatch, sessionmaker(bind=engine)).get("/api/v1/emr/C01/render").json()["data"]

    assert data["annotation_status"] == "unavailable"
    assert data["defect_annotations"] == []


def test_render_reports_no_result_when_record_never_checked(monkeypatch):
    _engine, factory = _session_factory()
    data = _client(monkeypatch, factory).get("/api/v1/emr/C01/render").json()["data"]

    assert data["annotation_status"] == "no_result"
    assert data["defect_annotations"] == []


def test_annotation_query_does_not_name_schema_dependent_columns(monkeypatch):
    # 旧查询点名 evaluation_results，PostgreSQL 报 UndefinedColumn 后标注静默缺失。
    # SQLite 会把不存在的带引号列名当字符串字面量，无法复现该报错，因此直接断言查询列。
    _engine, factory = _session_factory()
    requested_columns: list[str] = []
    original_select = _Query.select

    def spy_select(self, columns="*", count=None):
        requested_columns.append(columns)
        return original_select(self, columns, count)

    monkeypatch.setattr(_Query, "select", spy_select)
    _client(monkeypatch, factory).get("/api/v1/emr/C01/render")

    assert requested_columns == ["*"]
