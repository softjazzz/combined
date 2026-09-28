"""全部任务导出的独立边界合同。

这里刻意只依赖公开服务和路由，防止列表导出在分页、筛选或 CSV 安全上
悄悄偏离“全部任务”页面。
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import get_current_user
from app.database.models.qc import QCTask
from app.routers import task_exports
from app.services import task_export_service


def _factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    QCTask.__table__.create(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _task(index: int, **overrides) -> QCTask:
    values = {
        "id": f"contract-{index:05d}",
        "task_number": f"CONTRACT-{index:05d}",
        "task_name": f"合同任务-{index}",
        "task_type": "one_time",
        "scene": "running",
        "rule_set_key": "sc_content_full_v1",
        "rule_set_version": "v1",
        "sampling_method": "all",
        "assign_method": "by_ratio",
        "status": "draft",
        "progress": 0,
        "total_records": 0,
        "completed_records": 0,
        "creator_id": "manager-id",
        "creator_name": "管理员",
        "created_at": datetime(2026, 9, 27) + timedelta(seconds=index),
    }
    values.update(overrides)
    return QCTask(**values)


def _csv_rows(content: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))


def _client(user: dict) -> TestClient:
    app = FastAPI()
    app.include_router(task_exports.router)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_export_preserves_list_keyword_and_status_semantics_without_trimming():
    factory = _factory()
    with factory.begin() as session:
        session.add_all([
            _task(1, task_name="前后有 空格", status="legacy status"),
            _task(2, task_name="前后无空格", status="legacy status"),
            _task(3, task_name="前后有 空格", status="draft"),
        ])

    result = task_export_service.export_all_tasks(
        keyword="有 空",
        status="legacy status",
        session_factory=factory,
    )

    assert result.row_count == 1
    assert _csv_rows(result.content)[0]["任务编号"] == "CONTRACT-00001"


def test_export_scene_contract_matches_list_null_scope_and_exact_scope():
    factory = _factory()
    with factory.begin() as session:
        session.add_all([
            _task(1, scene=None),
            _task(2, scene="running"),
            _task(3, scene="final"),
        ])

    unclassified = task_export_service.export_all_tasks(
        scene="unclassified", session_factory=factory,
    )
    running = task_export_service.export_all_tasks(scene="running", session_factory=factory)

    assert [row["任务编号"] for row in _csv_rows(unclassified.content)] == ["CONTRACT-00001"]
    assert [row["任务编号"] for row in _csv_rows(running.content)] == ["CONTRACT-00002"]


def test_keyword_comma_is_bound_as_literal_data_not_or_filter_syntax():
    factory = _factory()
    injected = "甲,task_number.ilike.%CONTRACT-00002"
    with factory.begin() as session:
        session.add_all([
            _task(1, task_name=f"包含完整文本 {injected}"),
            _task(2, task_name="不应被额外 OR 条件命中"),
        ])

    result = task_export_service.export_all_tasks(
        keyword=injected,
        session_factory=factory,
    )

    assert [row["任务编号"] for row in _csv_rows(result.content)] == ["CONTRACT-00001"]


def test_exact_export_limit_returns_every_matching_row_not_a_page():
    factory = _factory()
    with factory.begin() as session:
        session.add_all([
            _task(index)
            for index in range(task_export_service.MAX_EXPORT_ROWS)
        ])

    result = task_export_service.export_all_tasks(session_factory=factory)

    rows = _csv_rows(result.content)
    assert result.row_count == task_export_service.MAX_EXPORT_ROWS
    assert len(rows) == task_export_service.MAX_EXPORT_ROWS
    assert rows[0]["任务编号"] == "CONTRACT-04999"
    assert rows[-1]["任务编号"] == "CONTRACT-00000"


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r", "\n"])
def test_every_frozen_formula_prefix_is_neutralized(prefix: str):
    content = task_export_service.render_task_export_csv([
        {"task_number": f"{prefix}SUM(A1:A2)", "task_name": "普通任务"},
    ])

    assert _csv_rows(content)[0]["任务编号"] == f"'{prefix}SUM(A1:A2)"


def test_invalid_scene_and_service_failure_never_return_partial_csv(monkeypatch):
    invalid = _client({"id": "manager", "roles": ["admin"]}).get(
        "/api/v1/task-exports", params={"scene": "unknown"},
    )
    assert invalid.status_code == 422
    assert "text/csv" not in invalid.headers.get("content-type", "")

    monkeypatch.setattr(
        task_export_service,
        "export_all_tasks",
        lambda **_kwargs: (_ for _ in ()).throw(
            task_export_service.TaskExportUnavailable("含患者隐私的内部错误")
        ),
    )
    unavailable = _client({"id": "manager", "roles": ["qc_manager"]}).get(
        "/api/v1/task-exports",
    )
    assert unavailable.status_code == 503
    assert "text/csv" not in unavailable.headers.get("content-type", "")
    assert "患者隐私" not in unavailable.text
