"""抽样失败不能伪造候选、落关联或返回成功。"""

from types import SimpleNamespace
from datetime import date, datetime, timedelta, timezone
import random

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import supabase_client
from app.core.security import get_current_user
from app.routers import tasks
from app.services.task_sampling_service import TaskSamplingService
from app.services.case_identity import CaseRef


class Database:
    def __init__(self, task=None, records=None, fail=None):
        self.task = {"status": "draft", "creator_id": "qc-user", **task} if task is not None else None
        self.records = records or []
        self.fail = fail
        self.calls = []
        self.writes = []
        self.save_calls = []
        self.save_error = None
        self.saved_result = None

    def table(self, name):
        return Query(self, name)


class Query:
    def __init__(self, db, table):
        self.db, self.table = db, table
        self.operation = "select"
        self.payload = None
        self.page = None

    def select(self, *_args, **_kwargs):
        return self

    def order(self, *_args):
        return self

    def range(self, start, end):
        self.page = (start, end)
        return self

    def eq(self, *_args):
        return self

    def in_(self, *_args):
        return self

    def gte(self, *_args):
        return self

    def lte(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def single(self):
        return self

    def insert(self, payload):
        self.operation, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.operation, self.payload = "update", payload
        return self

    def execute(self):
        key = (self.table, self.operation)
        self.db.calls.append(key)
        if self.db.fail == key:
            raise RuntimeError("internal database connection detail")
        if self.operation != "select":
            self.db.writes.append((key, self.payload))
            return SimpleNamespace(data=[])
        if self.table == "qc_tasks":
            return SimpleNamespace(data=self.db.task)
        rows = self.db.records
        if self.page is not None:
            start, end = self.page
            rows = rows[start:end + 1]
        return SimpleNamespace(data=rows, count=len(self.db.records))


def wire(monkeypatch, db):
    from app.services import task_sampling_persistence

    async def execute(query):
        return query.execute()

    def save(task, records, *, actor_id):
        db.save_calls.append((task, records, actor_id))
        if db.save_error is not None:
            raise db.save_error
        if db.fail in {("qc_task_records", "insert"), ("qc_tasks", "update")}:
            raise RuntimeError("internal database persistence detail")
        return db.saved_result or {
            "task_id": task["id"],
            "sampled_count": len(records),
            "records": records[:20],
        }

    monkeypatch.setattr(task_sampling_persistence, "save_task_sample", save)
    monkeypatch.setattr(supabase_client, "get_supabase", lambda: db)
    monkeypatch.setattr(supabase_client, "async_execute", execute)
    monkeypatch.setattr(tasks, "get_supabase", lambda: db)
    monkeypatch.setattr(tasks, "async_execute", execute)
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "qc-user", "roles": ["admin"]}
    return TestClient(app)


def active_source(monkeypatch, rows, *, status="ready", failure=None):
    from app.services import case_scope_service

    calls = []

    def resolve(self, **kwargs):
        calls.append(kwargs)
        if failure:
            raise failure
        return SimpleNamespace(
            source_status=status,
            case_refs=tuple(CaseRef(row["institute_id"], row["patient_id"], row["visit_id"]) for row in rows),
            selected=tuple(rows),
        )

    monkeypatch.setattr(case_scope_service.CaseScopeService, "resolve_hospitalization_scope", resolve)
    return calls


def active_row(hospital, patient, visit, admitted="2026-09-01", department="内科"):
    return {
        "institute_id": hospital,
        "patient_id": patient,
        "visit_id": visit,
        "hospitalization_status": "active",
        "admission_time": datetime.fromisoformat(admitted),
        "department": department,
    }


def test_stratified_count_reallocates_unfilled_department_quota():
    candidates = [{"id": "a", "department": "甲"}] + [
        {"id": f"b-{index}", "department": "乙"} for index in range(4)
    ]
    sampled = TaskSamplingService()._sample_by_count(candidates, {"total": 4, "by_department": True})
    assert len(sampled) == 4
    assert len({record["id"] for record in sampled}) == 4
    assert {record["id"] for record in sampled} <= {record["id"] for record in candidates}
    assert sum(record["department"] == "甲" for record in sampled) == 1


def test_stratified_count_does_not_always_take_first_departments(monkeypatch):
    fixed_random = random.Random(20260924)
    monkeypatch.setattr("app.services.task_sampling_service.random.sample", fixed_random.sample)
    candidates = [{"id": str(index), "department": str(index)} for index in range(8)]
    selected = [
        tuple(record["department"] for record in TaskSamplingService()._sample_by_count(
            candidates, {"total": 2, "by_department": True}
        ))
        for _ in range(30)
    ]
    assert all(len(set(group)) == 2 for group in selected)
    assert len(set(selected)) > 1
    assert any("0" not in group for group in selected)


@pytest.mark.asyncio
async def test_scene_count_rejects_non_boolean_by_department_before_source_read(monkeypatch):
    calls = active_source(monkeypatch, [active_row("H1", "P1", "V1")])
    with pytest.raises(ValueError, match="按科室抽样参数必须为布尔值"):
        await TaskSamplingService().sample({
            "scene": "running", "sampling_method": "count",
            "sampling_config": {"case_scope": "active", "total": 1, "by_department": "false"},
        })
    assert calls == []


@pytest.mark.asyncio
async def test_explicit_active_running_uses_scope_and_preserves_institution(monkeypatch):
    rows = [active_row("H1", "P1", "V1"), active_row("H2", "P1", "V1")]
    calls = active_source(monkeypatch, rows)
    db = Database()
    wire(monkeypatch, db)
    result = await TaskSamplingService().sample({"scene": "running", "sampling_config": {"case_scope": "active"}})
    assert {(row["institute_id"], row["patient_id"], row["visit_id"]) for row in result} == {
        ("H1", "P1", "V1"), ("H2", "P1", "V1")
    }
    assert calls[0]["scope_mode"] == "active"
    assert calls[0]["as_of_date"] == datetime.now(timezone(timedelta(hours=8))).date()
    assert db.calls == []


@pytest.mark.asyncio
async def test_active_running_filters_admission_end_and_department(monkeypatch):
    calls = active_source(monkeypatch, [active_row("H1", "P1", "V1", "2026-09-01", "内科"), active_row("H1", "P2", "V2", "2026-09-20", "内科")])
    wire(monkeypatch, Database())
    result = await TaskSamplingService().sample({
        "scene": "running", "sampling_config": {"case_scope": "active"},
        "date_range": {"start": "2026-09-01", "end": "2026-09-10"},
        "department_filter": ["内科"],
    })
    assert [row["patient_id"] for row in result] == ["P1"]
    assert calls[0]["admission_start_date"] == date(2026, 9, 1)
    assert calls[0]["departments"] == ["内科"]


@pytest.mark.parametrize("config", [None, {}, {"case_scope": "discharged"}])
@pytest.mark.asyncio
async def test_running_without_explicit_active_stays_closed(monkeypatch, config):
    calls = active_source(monkeypatch, [])
    with pytest.raises(NotImplementedError):
        await TaskSamplingService().sample({"scene": "running", "sampling_config": config})
    assert calls == []


@pytest.mark.parametrize("status,failure", [("degraded", None), ("ready", OSError("remote failed"))])
@pytest.mark.asyncio
async def test_active_running_source_failure_is_not_empty_success(monkeypatch, status, failure):
    calls = active_source(monkeypatch, [active_row("H1", "P1", "V1")], status=status, failure=failure)
    with pytest.raises(RuntimeError, match="候选病历数据源"):
        await TaskSamplingService().sample({"scene": "running", "sampling_config": {"case_scope": "active"}})
    assert len(calls) == 1


@pytest.mark.parametrize("row", [
    active_row("H1", "P1", "V1") | {"hospitalization_status": "discharged"},
    active_row("H1", "P1", "V1") | {"patient_id": ""},
    active_row("H1", "P1", "V1") | {"admission_time": None},
])
@pytest.mark.asyncio
async def test_active_running_malformed_source_fails_closed(monkeypatch, row):
    active_source(monkeypatch, [row])
    with pytest.raises(RuntimeError, match="候选病历数据无效"):
        await TaskSamplingService().sample({"scene": "running", "sampling_config": {"case_scope": "active"}})


@pytest.mark.asyncio
async def test_active_running_duplicate_outside_end_date_still_fails(monkeypatch):
    row = active_row("H1", "P1", "V1", "2026-09-20")
    active_source(monkeypatch, [row, row])
    with pytest.raises(RuntimeError, match="候选病历数据无效"):
        await TaskSamplingService().sample({
            "scene": "running", "sampling_config": {"case_scope": "active"},
            "date_range": {"end": "2026-09-10"},
        })


@pytest.mark.parametrize("refs", [
    [{"institute_id": "H2", "patient_id": "P1", "visit_id": "V1"}],
    [{"institute_id": "H1", "patient_id": "P2", "visit_id": "V2"}],
    [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}] * 2,
])
@pytest.mark.asyncio
async def test_active_running_explicit_refs_must_be_unique_and_in_scope(monkeypatch, refs):
    active_source(monkeypatch, [active_row("H1", "P1", "V1")])
    with pytest.raises(ValueError):
        await TaskSamplingService().sample({"scene": "running", "sampling_config": {"case_scope": "active"}, "record_refs": refs})


@pytest.mark.asyncio
async def test_active_running_legacy_ids_and_final_stay_closed(monkeypatch):
    calls = active_source(monkeypatch, [active_row("H1", "P1", "V1")])
    with pytest.raises(ValueError, match="旧病历 ID"):
        await TaskSamplingService().sample({"scene": "running", "sampling_config": {"case_scope": "active"}, "record_ids": ["legacy"]})
    with pytest.raises(NotImplementedError):
        await TaskSamplingService().sample({"scene": "final", "sampling_config": {"case_scope": "active"}})
    assert calls == []


def test_active_running_route_maps_source_and_scope_errors(monkeypatch):
    calls = active_source(monkeypatch, [active_row("H1", "P1", "V1")], status="degraded")
    db = Database(task={"id": "task-1", "scene": "running", "sampling_config": {"case_scope": "active"}})
    client = wire(monkeypatch, db)
    response = client.post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 503
    assert db.save_calls == [] and db.writes == []

    active_source(monkeypatch, [active_row("H1", "P1", "V1")])
    db.task["record_refs"] = [{"institute_id": "H2", "patient_id": "P1", "visit_id": "V1"}]
    response = client.post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 422
    assert db.save_calls == [] and db.writes == []
    assert len(calls) == 1


@pytest.mark.parametrize("method,config", [
    ("unknown", {"case_scope": "active"}),
    ({}, {"case_scope": "active"}),
    ("count", {"case_scope": "active", "total": "2"}),
    ("count", {"case_scope": "active", "total": True}),
    ("percentage", {"case_scope": "active", "percentage": 0}),
    ("percentage", {"case_scope": "active", "group_by": "doctor_name"}),
])
def test_active_running_invalid_sampling_config_is_422_not_full_sample(monkeypatch, method, config):
    calls = active_source(monkeypatch, [active_row("H1", "P1", "V1")], status="degraded")
    db = Database(task={"id": "task-1", "scene": "running", "sampling_method": method, "sampling_config": config})
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 422
    assert calls == []
    assert db.save_calls == [] and db.writes == []


@pytest.mark.parametrize("field,bad", [
    ("department_filter", {}),
    ("department_filter", ""),
    ("record_refs", {}),
    ("record_refs", ""),
    ("date_range", ""),
])
def test_active_running_malformed_scope_does_not_expand_query(monkeypatch, field, bad):
    calls = active_source(monkeypatch, [active_row("H1", "P1", "V1")])
    db = Database(task={
        "id": "task-1", "scene": "running", "sampling_config": {"case_scope": "active"}, field: bad,
    })
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 422
    assert calls == []
    assert db.save_calls == [] and db.writes == []


@pytest.mark.parametrize("start", ["1900-01-01", "2099-01-01"])
def test_active_running_invalid_admission_window_is_422(monkeypatch, start):
    calls = active_source(monkeypatch, [active_row("H1", "P1", "V1")])
    db = Database(task={
        "id": "task-1", "scene": "running", "sampling_config": {"case_scope": "active"},
        "date_range": {"start": start},
    })
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 422
    assert calls == []
    assert db.save_calls == [] and db.writes == []


def test_active_running_empty_scope_is_422_without_persistence(monkeypatch):
    active_source(monkeypatch, [])
    db = Database(task={"id": "task-1", "scene": "running", "sampling_config": {"case_scope": "active"}})
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 422
    assert db.save_calls == [] and db.writes == []


def test_active_running_route_saves_verified_case_coordinates(monkeypatch):
    active_source(monkeypatch, [active_row("H1", "P1", "V1"), active_row("H2", "P1", "V1")])
    db = Database(task={"id": "task-1", "scene": "running", "sampling_config": {"case_scope": "active"}})
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 200
    assert response.json()["data"]["sampled_count"] == 2
    assert {(row["institute_id"], row["patient_id"], row["visit_id"]) for row in db.save_calls[0][1]} == {
        ("H1", "P1", "V1"), ("H2", "P1", "V1")
    }
    assert db.writes == []


@pytest.mark.parametrize("scene", ["running", "final", "invalid", ""])
@pytest.mark.asyncio
async def test_scoped_sampling_never_uses_unscoped_source(monkeypatch, scene):
    db = Database(records=[{"id": "wrong-scene"}])
    wire(monkeypatch, db)
    with pytest.raises(NotImplementedError, match="场景抽样暂不可用"):
        await TaskSamplingService().sample({"scene": scene})
    assert db.calls == []


@pytest.mark.parametrize("record_ids", [[], ["record-1"]])
@pytest.mark.parametrize("unavailable", ["missing", "query_failure"])
@pytest.mark.asyncio
async def test_missing_source_and_query_failure_raise_not_fake_success(monkeypatch, record_ids, unavailable):
    db = None if unavailable == "missing" else Database(fail=("medical_records", "select"))
    wire(monkeypatch, db)
    with pytest.raises(RuntimeError, match="候选病历数据源不可用"):
        await TaskSamplingService().sample({"record_ids": record_ids})


@pytest.mark.asyncio
async def test_missing_explicit_id_rejects_partial_candidates(monkeypatch):
    db = Database(records=[{"id": "record-1"}])
    wire(monkeypatch, db)
    with pytest.raises(ValueError, match="指定病历不存在"):
        await TaskSamplingService().sample({"record_ids": ["record-1", "record-2"]})


@pytest.mark.asyncio
async def test_legacy_candidates_remain_compatible_and_empty_is_valid(monkeypatch):
    db = Database(records=[{"id": "record-1"}])
    wire(monkeypatch, db)
    assert await TaskSamplingService().sample({"scene": None, "record_ids": ["record-1", "record-1"]}) == [{"id": "record-1"}]
    db.records = []
    assert await TaskSamplingService().sample({}) == []


@pytest.mark.parametrize("scene", ["running", "final"])
def test_scene_route_refuses_before_candidate_read_or_write(monkeypatch, scene):
    db = Database(task={"id": "task-1", "scene": scene})
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 409
    assert "场景抽样暂不可用" in response.json()["detail"]
    assert db.calls == [("qc_tasks", "select")]
    assert db.writes == []


def test_outpatient_route_saves_only_verified_case_coordinates(monkeypatch):
    db = Database(
        task={"id": "task-1", "scene": "outpatient", "record_refs": []},
        records=[
            {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "document_id": "D1", "visit_datetime": None, "dept_name": "内科"},
            {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "document_id": "D2", "visit_datetime": None, "dept_name": "内科"},
        ],
    )
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 200
    assert response.json()["data"]["sampled_count"] == 1
    assert db.calls == [("qc_tasks", "select"), ("cdm.outpat_record", "select")]
    assert db.save_calls[0][1][0]["visit_id"] == "V1"
    assert "id" not in db.save_calls[0][1][0]
    assert db.writes == []


@pytest.mark.parametrize("creator_id", ["another-user", None, ""])
def test_route_rejects_non_creator_before_candidate_read(monkeypatch, creator_id):
    db = Database(task={"id": "task-1", "creator_id": creator_id}, records=[{"id": "r-1"}])
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 403
    assert db.calls == [("qc_tasks", "select")]
    assert db.save_calls == [] and db.writes == []


def test_outpatient_malformed_source_is_503_not_invalid_user_input(monkeypatch):
    db = Database(
        task={"id": "task-1", "scene": "outpatient", "record_refs": []},
        records=[{"institute_id": "H1", "patient_id": None, "visit_id": "V1"}],
    )
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 503
    assert db.save_calls == []
    assert db.writes == []


@pytest.mark.parametrize("field,bad", [
    ("department_filter", {}),
    ("record_refs", {}),
    ("date_range", ""),
])
def test_outpatient_malformed_scope_fails_before_candidate_read(monkeypatch, field, bad):
    db = Database(task={"id": "task-1", "scene": "outpatient", field: bad})
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 422
    assert db.calls == [("qc_tasks", "select")]
    assert db.save_calls == [] and db.writes == []


@pytest.mark.parametrize("scene", ["running", "final", "outpatient"])
def test_modern_task_never_uses_legacy_reanalyze_or_marks_it_running(monkeypatch, scene):
    db = Database(task={"id": "task-1", "scene": scene}, records=[{"record_id": "not-a-case-id"}])
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/re-analyze")
    assert response.status_code == 409
    assert db.calls == [("qc_tasks", "select")]
    assert db.writes == []


@pytest.mark.parametrize("failure", [("qc_tasks", "select"), ("medical_records", "select")])
def test_route_query_failure_is_503_without_writes(monkeypatch, failure):
    db = Database(task={"id": "task-1"}, fail=failure)
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 503
    assert "internal database" not in response.text
    assert db.writes == []


def test_route_nonexistent_task_remains_404(monkeypatch):
    db = Database()
    response = wire(monkeypatch, db).post("/api/v1/tasks/missing/sample")
    assert response.status_code == 404
    assert db.writes == []


def test_route_missing_explicit_id_is_422_before_writes(monkeypatch):
    db = Database(task={"id": "task-1", "record_ids": ["missing"]})
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 422
    assert db.writes == []


@pytest.mark.parametrize("failure", [("qc_task_records", "insert"), ("qc_tasks", "update")])
def test_route_persistence_failure_does_not_report_success(monkeypatch, failure):
    db = Database(task={"id": "task-1"}, records=[{"id": "record-1"}], fail=failure)
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 503
    assert "internal database" not in response.text
    assert len(db.save_calls) == 1
    assert db.writes == []


def test_route_successful_empty_candidates_is_distinct_from_failure(monkeypatch):
    db = Database(task={"id": "task-1"})
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 200
    assert response.json()["data"]["sampled_count"] == 0
    assert len(db.save_calls) == 1
    assert db.save_calls[0][1] == []
    assert db.writes == []


@pytest.mark.parametrize("status", ["assigned", "in_progress", "completed", "cancelled", "unknown", None])
def test_route_rejects_non_draft_states_before_candidate_read(monkeypatch, status):
    db = Database(task={"id": "task-1", "status": status})
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 409
    assert db.calls == [("qc_tasks", "select")]
    assert db.save_calls == []


def test_route_sampling_retry_replays_persisted_result_without_candidates(monkeypatch):
    db = Database(task={"id": "task-1", "status": "sampling"}, fail=("medical_records", "select"))
    db.saved_result = {
        "task_id": "task-1",
        "sampled_count": 1,
        "records": [{"id": "saved-assignment", "record_id": "first-sampled-record"}],
    }
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 200
    assert response.json()["data"] == db.saved_result
    assert db.calls == [("qc_tasks", "select")]
    assert db.save_calls == [(db.task, [], "qc-user")]


@pytest.mark.parametrize("kind,code", [("missing", 404), ("forbidden", 403), ("conflict", 409), ("driver", 503)])
def test_route_maps_transaction_failure_without_retry(monkeypatch, kind, code):
    from app.services.task_sampling_persistence import SamplingConflict, SamplingForbidden, SamplingTaskNotFound

    db = Database(task={"id": "task-1"}, records=[{"id": "record-1"}])
    db.save_error = {
        "missing": SamplingTaskNotFound("missing"),
        "forbidden": SamplingForbidden("仅任务创建人可执行抽样"),
        "conflict": SamplingConflict("任务状态已变化"),
        "driver": ValueError("internal driver implementation detail"),
    }[kind]
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == code
    assert len(db.save_calls) == 1
    assert "internal driver" not in response.text
    assert db.writes == []
