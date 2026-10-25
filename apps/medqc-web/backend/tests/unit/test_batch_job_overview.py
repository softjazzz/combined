"""任务概览只读小列；筛选分页与完整列表一致，结果内容只在详情入口读取。"""
from datetime import datetime, timedelta
import json
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.services import custom_qc_workspace_service as workspace
from app.routers import qc_sichuan


@pytest.fixture
def overview_store(monkeypatch):
    metadata = sa.MetaData()
    names = ("id", "draft_id", "rule_code", "rule_name", "scene", "scope", "status",
             "job_kind", "filters_json", "created_by", "parent_job_id", "record_ids_json",
             "summary_json", "items_json", "failed_records_json")
    table = sa.Table("jobs", metadata,
        *(sa.Column(name, sa.Text) for name in names),
        *(sa.Column(name, sa.DateTime) for name in ("created_at", "started_at", "finished_at", "updated_at")),
        *(sa.Column(name, sa.Integer) for name in ("total_records", "success_count", "failed_count", "issue_records", "compliant_records")))
    engine = sa.create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    filters = json.dumps({"selected_rule_ids": ["r2", "r1"], "customer_rule_count": 2,
                          "record_refs": [{"patient_id": "PRIVATE_ID"}]})
    rows = []
    for index, status in enumerate(("completed", "failed", "running", "canceled", "queued")):
        rows.append(dict(id=status, draft_id="workspace", rule_code="LX0609", rule_name="样本验证",
            scene="final", scope="running" if status == "running" else "final", status=status,
            job_kind="single", filters_json=filters, created_by="u-1", parent_job_id=None,
            record_ids_json='["visit_100"]', summary_json='{"private":"PRIVATE_RESULT"}',
            items_json='[{"private":"PRIVATE_RESULT"}]', failed_records_json='[]',
            created_at=datetime(2026, 10, 23) + timedelta(hours=index),
            total_records=27, success_count=25, failed_count=2, issue_records=1, compliant_records=0))
    rows.extend([{**rows[0], "id": "other-user", "created_by": "u-2"},
                 {**rows[0], "id": "child", "parent_job_id": "parent"}])
    with engine.begin() as connection:
        connection.execute(table.insert(), rows)
    service = workspace.CustomQCWorkspaceService.__new__(workspace.CustomQCWorkspaceService)
    service._batch_job_table = table
    monkeypatch.setattr(workspace, "_session", sessionmaker(bind=engine))
    statements = []
    sa.event.listen(engine, "before_cursor_execute", lambda conn, cursor, statement, *args: statements.append(statement))
    yield service, statements
    engine.dispose()


@pytest.mark.parametrize("filters", [
    {}, {"status": "failed"}, {"scope": "running"}, {"query": "样本"},
    {"created_start_date": "2026-10-24"}, {"record_id": "visit_100"},
    {"record_id": "visit%100"},
])
def test_overview_matches_full_list_filters_and_paging_without_reading_blobs(overview_store, filters):
    service, statements = overview_store
    overview = service.list_batch_job_overviews(created_by="u-1", page=1, page_size=2, **filters)
    for statement in statements:
        assert "summary_json" not in statement
        assert "items_json" not in statement
        assert "failed_records_json" not in statement
    full = service.list_batch_jobs(created_by="u-1", page=1, page_size=2, **filters)
    assert overview.total == full.total
    assert [row["id"] for row in overview.items] == [row["id"] for row in full.items]
    if not filters:
        assert overview.total == 5
        assert [row["id"] for row in overview.items] == ["queued", "canceled"]
        second = service.list_batch_job_overviews(created_by="u-1", page=2, page_size=2)
        assert [row["id"] for row in second.items] == ["running", "failed"]


def test_overview_projection_drops_all_private_result_fields(overview_store):
    service, _ = overview_store
    job = service.list_batch_job_overviews(created_by="u-1", status="failed").items[0]
    job.update(summary={"private": "PRIVATE_RESULT"}, items=["PRIVATE_RESULT"], error_message="PRIVATE_ERROR")
    dto = workspace.project_batch_job_overview(job)
    assert dto["draft_ids"] == ["r2", "r1"]
    assert dto["status"] == "failed" and dto["has_results"] is True
    assert dto["created_at"] == "2026-10-23 01:00:00"
    assert dto["summary"] == {"total_records": 27, "success_count": 25, "customer_rule_count": 2}
    assert "PRIVATE" not in json.dumps(dto)
    assert not ({"filters", "items", "issue_records", "compliant_records", "error_message"} & dto.keys())


@pytest.mark.asyncio
async def test_overview_route_never_invokes_full_list_or_result_projection(monkeypatch):
    calls = []

    def overview(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(items=[{"id": "light", "draft_id": "workspace", "status": "failed"}],
                               total=1, page=2, page_size=20)

    def forbidden(*args, **kwargs):
        raise AssertionError("概览不得读取或投影完整结果")

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: SimpleNamespace(
        list_batch_job_overviews=overview, list_batch_jobs=forbidden))
    monkeypatch.setattr(qc_sichuan, "_workspace_batch_list_item", forbidden)
    monkeypatch.setattr(qc_sichuan, "_is_workspace_batch_job", lambda job: job.get("draft_id") == "workspace")
    result = await qc_sichuan.list_workspace_batch_jobs(
        Request({"type": "http", "headers": []}), view="overview", current_user={"id": "u-1"},
        status="failed", scope="final", q="样本", created_start_date="2026-10-20", created_end_date=None,
        record_id=None, page=2, page_size=20)
    assert result["data"]["total"] == 1
    assert calls == [{"created_by": "u-1", "status": "failed", "scope": "final", "query": "样本",
                      "created_start_date": "2026-10-20", "created_end_date": None, "record_id": None,
                      "page": 2, "page_size": 20}]
