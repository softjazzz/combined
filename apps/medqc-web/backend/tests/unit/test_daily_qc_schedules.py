"""每日计划固定应答验收；严格离线入口、合成内存SQLite，禁止真实质控。"""

import asyncio
from datetime import datetime, timedelta, timezone, date
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
from app.database.models.v36_reports import SysUser
from app.routers import daily_qc as api
from app.services.daily_qc.contracts import (
    PlanInput,
    occurrence,
    next_occurrence,
    date_window,
    job_identity,
)
from app.services.daily_qc.store import ScheduleStore, tables, PlanConflict
from app.services.daily_qc.service import tick, require_manager


NOW = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)


def definition(**changes):
    values = dict(
        name="合成每日计划",
        time_of_day="08:05",
        timezone="Asia/Shanghai",
        institute_id="A",
        rule_set_key="luxian_0609_qc_v1",
        enabled=True,
    )
    values.update(changes)
    return PlanInput(**values).model_dump()


@pytest.fixture
def environment(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    sessions = sessionmaker(bind=engine)
    metadata, _, _ = tables()
    metadata.create_all(engine)
    SysUser.__table__.create(engine)
    with sessions() as session, session.begin():
        session.add(
            SysUser(
                id="manager",
                username="synthetic-manager",
                display_name="合成管理员",
                institute_id="A",
                role="sync_admin",
                roles_json='["sync_admin"]',
                is_active=True,
            )
        )
        session.add(
            SysUser(
                id="other",
                username="other",
                display_name="合成另一管理员",
                role="admin",
                is_active=True,
            )
        )
        session.add(
            SysUser(
                id="doctor",
                username="synthetic-doctor",
                display_name="合成医生",
                role="doctor",
                is_active=True,
            )
        )
    store = ScheduleStore(sessions)
    yield store, sessions, engine
    engine.dispose()


class FixedAdmission:
    def __init__(self):
        self.jobs = {}
        self.calls = []
        self.fail_after_commit = False
        self.error = None

    def job_status(self, job_id):
        return self.jobs.get(job_id, "missing")

    async def submit(self, claimed, run):
        if self.error:
            raise self.error
        if run["job_id"] not in self.jobs:
            self.calls.append((claimed["id"], run["id"], run["job_id"]))
            self.jobs[run["job_id"]] = "queued"
        if self.fail_after_commit:
            self.fail_after_commit = False
            raise RuntimeError("synthetic crash after job commit")
        return run["job_id"]


def add_plan(store, **changes):
    return store.save("manager", definition(**changes), NOW)


def test_default_off_and_time_contract():
    plan = PlanInput(
        name="默认", time_of_day="02:00", institute_id="A", rule_set_key="x"
    )
    assert plan.enabled is False
    assert date_window(date(2026, 11, 2), plan.model_dump()) == (
        "2026-11-01",
        "2026-11-01",
    )
    with pytest.raises(ValueError):
        PlanInput(**{**plan.model_dump(), "timezone": "invalid/zone"})
    with pytest.raises(ValueError):
        PlanInput(**{**plan.model_dump(), "time_of_day": "25:00"})
    assert occurrence(date(2026, 11, 2), "08:00", "Asia/Shanghai") == NOW.replace(
        tzinfo=None
    )
    assert next_occurrence(NOW, definition(time_of_day="08:00")) == datetime(
        2026, 11, 3
    )


def test_dst_gap_fold_and_utc_boundary():
    assert occurrence(date(2026, 3, 8), "02:30", "America/Chicago") == datetime(
        2026, 3, 8, 8
    )
    assert occurrence(date(2026, 11, 1), "01:30", "America/Chicago") == datetime(
        2026, 11, 1, 6, 30
    )
    assert occurrence(date(2026, 11, 2), "00:00", "UTC") == datetime(2026, 11, 2)


@pytest.mark.asyncio
async def test_disabled_plan_and_before_time_never_submit(environment):
    store, _, _ = environment
    add_plan(store, enabled=False)
    add_plan(store)
    admission = FixedAdmission()
    assert await tick(store, admission, NOW) == []
    assert admission.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scope,date_field", [("running", "admission"), ("final", "discharge")]
)
async def test_daily_once_and_next_day_overlap(environment, scope, date_field):
    store, _, _ = environment
    plan_id = add_plan(store, scope=scope, date_field=date_field)
    admission = FixedAdmission()
    due = NOW + timedelta(minutes=5)
    assert await tick(store, admission, due) == ["submitted"]
    assert await tick(store, admission, due) == []
    assert len(admission.calls) == 1
    assert await tick(store, admission, due + timedelta(days=1)) == ["skipped_overlap"]
    assert len(admission.calls) == 1
    history = store.history(plan_id, "manager")
    assert {r["state"] for r in history} == {"submitted", "skipped_overlap"}
    admission.jobs[admission.calls[0][2]] = "completed"
    assert await tick(store, admission, due + timedelta(days=2)) == ["submitted"]
    assert len(admission.calls) == 2


def test_lease_cas_and_expiry(environment):
    store, sessions, _ = environment
    add_plan(store)
    now = NOW + timedelta(minutes=5)
    first = store.claim(now)
    assert first
    second_store = ScheduleStore(sessions)
    assert second_store.claim(now) is None
    second = second_store.claim(now + timedelta(minutes=6))
    assert second and second["lease_token"] != first["lease_token"]
    store.release(first)
    assert second_store.current(second["id"])["lease_token"] == second["lease_token"]


@pytest.mark.parametrize("changes", [{"time_of_day": "09:00"}, {"enabled": False}])
def test_edit_after_claim_cannot_trigger_disabled_or_future_occurrence(
    environment, changes
):
    store, _, _ = environment
    plan_id = add_plan(store)
    due = NOW + timedelta(minutes=5)
    claimed = store.claim(due)
    store.save("manager", definition(**changes), due, plan_id, 1)
    assert store.prepare(claimed, due) is None
    store.release(claimed)
    assert store.history(plan_id, "manager") == []


@pytest.mark.asyncio
async def test_crash_after_commit_reuses_same_job_and_existing_results(environment):
    store, sessions, _ = environment
    plan_id = add_plan(store)
    admission = FixedAdmission()
    admission.fail_after_commit = True
    due = NOW + timedelta(minutes=5)
    assert await tick(store, admission, due) == ["pending_recovery"]
    old_run_id = store.current(plan_id)["pending_run_id"]
    assert old_run_id
    assert await tick(store, admission, due + timedelta(minutes=1)) == []
    restarted_store = ScheduleStore(sessions)
    assert await tick(restarted_store, admission, due + timedelta(minutes=6)) == [
        "submitted"
    ]
    assert len(admission.calls) == 1
    assert store.history(plan_id, "manager")[0]["job_id"] == job_identity(old_run_id)
    assert store.current(plan_id)["pending_run_id"] is None


@pytest.mark.asyncio
async def test_missed_days_bounded_not_replayed(environment):
    store, _, _ = environment
    plan_id = add_plan(store)
    admission = FixedAdmission()
    assert await tick(store, admission, NOW + timedelta(days=30, hours=3)) == ["missed"]
    assert admission.calls == []
    assert len(store.history(plan_id, "manager")) == 1
    assert store.current(plan_id)["next_due"] > (
        NOW + timedelta(days=30, hours=3)
    ).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_old_gap_still_runs_today_within_grace(environment):
    store, _, _ = environment
    add_plan(store)
    admission = FixedAdmission()
    assert await tick(store, admission, NOW + timedelta(days=3, minutes=10)) == [
        "missed",
        "submitted",
    ]
    assert len(admission.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error,state",
    [
        (HTTPException(422, "当前筛选条件下没有可执行病历"), "empty"),
        (HTTPException(403, "synthetic"), "failed"),
        (HTTPException(422, "too many records"), "failed"),
    ],
)
async def test_rejection_is_not_zero_success(environment, error, state):
    store, _, _ = environment
    plan_id = add_plan(store)
    admission = FixedAdmission()
    admission.error = error
    assert await tick(store, admission, NOW + timedelta(minutes=5)) == [state]
    assert store.history(plan_id, "manager")[0]["state"] == state
    assert admission.calls == []


@pytest.mark.asyncio
async def test_cancellation_keeps_pending_for_recovery(environment):
    store, _, _ = environment
    plan_id = add_plan(store)
    admission = FixedAdmission()
    admission.error = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await tick(store, admission, NOW + timedelta(minutes=5))
    assert store.current(plan_id)["pending_run_id"]
    admission.error = None
    assert await tick(store, admission, NOW + timedelta(minutes=11)) == ["submitted"]


def test_edit_owner_and_version_cas(environment):
    store, _, _ = environment
    plan_id = add_plan(store)
    with pytest.raises(PlanConflict):
        store.save("other", definition(), NOW, plan_id, 1)
    store.save("manager", definition(enabled=False), NOW, plan_id, 1)
    with pytest.raises(PlanConflict):
        store.save("manager", definition(), NOW, plan_id, 1)
    with pytest.raises(KeyError):
        store.history(plan_id, "other")


def test_persistent_account_fail_closed(environment):
    store, sessions, _ = environment
    assert "admin" in require_manager(store, "manager")["roles"]
    for actor in ["doctor", "missing"]:
        with pytest.raises(HTTPException) as exc:
            require_manager(store, actor)
        assert exc.value.status_code == 403
    for update in [{"is_active": False}, {"is_active": True, "roles_json": "{broken"}]:
        with sessions() as session, session.begin():
            session.execute(
                sa.update(SysUser).where(SysUser.id == "manager").values(**update)
            )
        with pytest.raises(HTTPException):
            require_manager(store, "manager")


def test_api_crud_and_http_roles_cannot_forge_authority(
    client, environment, monkeypatch
):
    store, _, _ = environment
    client.app.dependency_overrides[enforce_default_auth] = lambda: None
    user = {"id": "manager", "roles": ["doctor"]}
    client.app.dependency_overrides[get_current_user] = lambda: user
    client.app.dependency_overrides[api.store_dependency] = lambda: store
    # 仅目录使用固定结构，持久账号和计划SQL不mock。
    monkeypatch.setattr(
        api.service, "validate_definition", lambda store, actor, data: data.model_dump()
    )
    saved = client.post("/api/v1/qc/daily-schedules", json=definition(enabled=False))
    assert saved.status_code == 200, saved.text
    item = saved.json()["data"]
    assert not item["enabled"]
    listed = client.get("/api/v1/qc/daily-schedules").json()["data"]
    assert listed["scheduler_enabled"] is False and len(listed["items"]) == 1
    changed = client.put(
        "/api/v1/qc/daily-schedules/" + item["id"],
        json={"revision": item["revision"], "definition": definition(enabled=True)},
    )
    assert changed.status_code == 200
    assert (
        client.put(
            "/api/v1/qc/daily-schedules/" + item["id"],
            json={"revision": 1, "definition": definition()},
        ).status_code
        == 409
    )
    user.update(id="doctor", roles=["admin", "sync_admin"])
    assert client.get("/api/v1/qc/daily-schedules").status_code == 403
    assert (
        client.post("/api/v1/qc/daily-schedules", json=definition()).status_code == 403
    )


def test_063_migration_only_adds_schedule_tables(monkeypatch):
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/20261102_000063_daily_qc_schedules.py"
    )
    spec = importlib.util.spec_from_file_location("daily_qc_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "20261102_000062"
    monkeypatch.setenv("DB_SCHEMA_MODE", "single")
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE preserved_result (id INTEGER PRIMARY KEY, value TEXT)"
            )
        )
        connection.execute(
            sa.text("INSERT INTO preserved_result VALUES(1, 'existing-success')")
        )
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        assert set(sa.inspect(connection).get_table_names()) == {
            "preserved_result",
            "daily_qc_plans",
            "daily_qc_runs",
        }
        assert (
            connection.execute(
                sa.text("SELECT value FROM preserved_result")
            ).scalar_one()
            == "existing-success"
        )
        assert {
            c["name"] for c in sa.inspect(connection).get_columns("daily_qc_plans")
        } == set(tables()[1].c.keys())
        assert any(
            i["column_names"] == ["plan_id", "local_date"]
            for i in sa.inspect(connection).get_unique_constraints("daily_qc_runs")
        )
    engine.dispose()


@pytest.mark.asyncio
async def test_disabled_runner_never_opens_store(monkeypatch):
    from app.services.daily_qc import runner

    monkeypatch.setattr(
        runner,
        "get_settings",
        lambda: SimpleNamespace(QC_DAILY_SCHEDULER_ENABLED=False),
    )
    monkeypatch.setattr(
        runner,
        "default_store",
        lambda: pytest.fail("disabled runner must not touch database"),
    )
    app = SimpleNamespace(state=SimpleNamespace())
    runner.start(app)
    await runner.run_loop()
    assert not hasattr(app.state, "daily_qc_task")


@pytest.mark.parametrize("mode", ["legacy", "rabbitmq"])
def test_actual_task_creation_reuses_primary_key_and_single_outbox(
    environment, monkeypatch, mode
):
    from app.services import custom_qc_workspace_service as workspace_module
    from app.services.qc_dispatch.outbox import qc_dispatch_tables

    store, sessions, engine = environment
    monkeypatch.setattr(workspace_module, "engine", engine)
    monkeypatch.setattr(workspace_module, "SessionLocal", sessions)
    monkeypatch.setattr(workspace_module, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(
        workspace_module,
        "get_settings",
        lambda: SimpleNamespace(QC_TASK_DISPATCH_MODE=mode),
    )
    workspace = workspace_module.CustomQCWorkspaceService(readonly=True)
    workspace._batch_job_table.create(engine)
    if mode == "rabbitmq":
        dispatch_tables = qc_dispatch_tables()
        dispatch_tables.dispatch.metadata.create_all(engine)
    run_id = str(uuid4())
    args = dict(
        draft={"id": "synthetic", "name": "synthetic"},
        created_by="manager",
        scope="final",
        filters={
            "rule_set_key": "luxian_0609_qc_v1",
            "daily_schedule": {"run_id": run_id},
        },
        record_ids=["V1"],
        total_records=1,
        draft_ids=["LX0609-06-01-04"],
        scheduled_run_id=run_id,
    )
    first = workspace.create_batch_job(**args)
    with sessions() as session, session.begin():
        session.execute(
            workspace._batch_job_table.update()
            .where(workspace._batch_job_table.c.id == first["id"])
            .values(
                status="completed", items_json='[{"synthetic_preserved_result": true}]'
            )
        )
    second = workspace.create_batch_job(**args)
    assert first["id"] == second["id"] == job_identity(run_id)
    assert second["schedule_submission_reused"]
    with sessions() as session:
        assert (
            session.execute(
                sa.select(workspace._batch_job_table.c.items_json).where(
                    workspace._batch_job_table.c.id == first["id"]
                )
            ).scalar_one()
            == '[{"synthetic_preserved_result": true}]'
        )
        assert (
            session.execute(
                sa.select(sa.func.count()).select_from(workspace._batch_job_table)
            ).scalar_one()
            == 1
        )
        if mode == "rabbitmq":
            assert (
                session.execute(
                    sa.select(sa.func.count()).select_from(dispatch_tables.outbox)
                ).scalar_one()
                == 1
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,crash,revoked",
    [
        ("legacy", False, False),
        ("legacy", True, False),
        ("rabbitmq", False, False),
        ("rabbitmq", True, False),
        ("legacy", True, True),
        ("rabbitmq", True, True),
    ],
)
async def test_scheduler_reuses_real_admission_and_atomic_task_outbox(
    environment, monkeypatch, mode, crash, revoked
):
    from app.routers import qc_sichuan
    from app.services import custom_qc_workspace_service as workspace_module
    from app.services import detached_task_runner, product_activation
    from app.services.daily_qc.service import BatchAdmission
    from app.services.qc_dispatch.outbox import qc_dispatch_tables
    from tests.unit.test_qc_dispatch_entrypoints import _main_settings, _gateway_service
    from tests.unit.test_qc_sichuan_batch_throughput import _ServiceStub

    store, sessions, engine = environment
    settings = _main_settings(
        qc_mode=mode, llm_mode="gateway" if mode == "rabbitmq" else "direct"
    )
    for target in (workspace_module, qc_sichuan):
        monkeypatch.setattr(target, "get_settings", lambda: settings)
    monkeypatch.setattr(workspace_module, "engine", engine)
    monkeypatch.setattr(workspace_module, "SessionLocal", sessions)
    monkeypatch.setattr(workspace_module, "DB_SCHEMA_MODE", "single")
    workspace = workspace_module.CustomQCWorkspaceService(readonly=True)
    workspace._batch_job_table.create(engine)
    dispatch = qc_dispatch_tables()
    if mode == "rabbitmq":
        dispatch.outbox.metadata.create_all(engine)
    calls, selected = [], []

    def collect(**kwargs):
        selected.append(kwargs)
        return [
            dict(
                institute_id="A",
                patient_id="P1",
                visit_id="V1",
                record_id="V1",
                scope="final",
                admission_date="2026-10-01",
                discharge_date="2026-11-01",
            )
        ]

    monkeypatch.setattr(workspace, "collect_records", collect)
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    # 仅拦截Worker启动；规则快照、任务创建及Outbox使用正式代码。
    for target in (qc_sichuan, detached_task_runner):
        monkeypatch.setattr(
            target, "submit_detached_task", lambda *args, **kwargs: calls.append(args)
        )
    model = _gateway_service() if mode == "rabbitmq" else _ServiceStub()

    async def provider():
        return model

    monkeypatch.setattr(qc_sichuan, "get_qc_service", provider)
    monkeypatch.setattr(
        product_activation,
        "get_product_activation_service",
        lambda: SimpleNamespace(enforce=lambda: None),
    )
    plan_id = add_plan(store)
    admission = BatchAdmission(store)
    original = admission.submit
    if crash:

        async def committed_then_crash(claimed, run):
            await original(claimed, run)
            raise RuntimeError("synthetic lost receipt")

        admission.submit = committed_then_crash
    due = NOW + timedelta(minutes=5)
    assert await tick(store, admission, due) == (
        ["pending_recovery"] if crash else ["submitted"]
    )
    if crash:
        if revoked:
            with sessions() as session, session.begin():
                session.execute(
                    sa.update(SysUser)
                    .where(SysUser.id == "manager")
                    .values(is_active=False)
                )
        assert await tick(store, BatchAdmission(store), due + timedelta(minutes=6)) == [
            "submitted"
        ]
    assert len(selected) == 1
    assert selected[0]["institute_id"] == "A"
    assert selected[0]["start_date"] == selected[0]["end_date"] == "2026-11-01"
    with sessions() as session:
        jobs = session.execute(sa.select(workspace._batch_job_table)).mappings().all()
        assert len(jobs) == 1 and jobs[0]["status"] == "queued"
        assert jobs[0]["items_json"] is None
        filters = json.loads(jobs[0]["filters_json"])
        assert filters["daily_schedule"]["plan_id"] == plan_id
        assert filters["record_refs"] == [
            {"institute_id": "A", "patient_id": "P1", "visit_id": "V1"}
        ]
        from app.services.luxian_0609.rule_decision_settings import (
            LX0609_TASK_SETTINGS_FILTER_KEY,
        )

        assert filters[LX0609_TASK_SETTINGS_FILTER_KEY]
        if mode == "rabbitmq":
            assert (
                session.execute(
                    sa.select(sa.func.count()).select_from(dispatch.outbox)
                ).scalar_one()
                == 1
            )
            assert calls == []
        else:
            assert len(calls) == (2 if crash and not revoked else 1)
            assert all(call[-1] == jobs[0]["id"] for call in calls)
    assert store.current(plan_id)["last_job_id"] == jobs[0]["id"]
    assert model.evaluate_calls == 0


@pytest.mark.asyncio
async def test_runtime_revocation_blocks_admission(environment, monkeypatch):
    from app.services.daily_qc.service import BatchAdmission
    from app.services import product_activation
    from app.services import custom_qc_workspace_service as workspace_module

    store, sessions, _ = environment
    plan_id = add_plan(store)
    with sessions() as session, session.begin():
        session.execute(
            sa.update(SysUser).where(SysUser.id == "manager").values(is_active=False)
        )
    monkeypatch.setattr(
        workspace_module,
        "CustomQCWorkspaceService",
        lambda **kwargs: SimpleNamespace(get_scheduled_batch_job=lambda **kwargs: None),
    )
    monkeypatch.setattr(
        product_activation,
        "get_product_activation_service",
        lambda: pytest.fail(
            "revoked owner must be rejected before activation or QC service"
        ),
    )
    assert await tick(store, BatchAdmission(store), NOW + timedelta(minutes=5)) == [
        "failed"
    ]
    assert store.history(plan_id, "manager")[0]["reason"] == "permission_denied"


@pytest.mark.asyncio
async def test_unknown_admission_failure_has_finite_recovery(environment):
    store, _, _ = environment
    plan_id = add_plan(store)
    admission = FixedAdmission()
    admission.error = RuntimeError("synthetic unavailable")
    due = NOW + timedelta(minutes=5)
    for minute in (0, 6, 12):
        assert await tick(store, admission, due + timedelta(minutes=minute)) == [
            "pending_recovery"
        ]
    assert await tick(store, admission, due + timedelta(minutes=18)) == ["failed"]
    assert store.history(plan_id, "manager")[0]["reason"] == "recovery_budget_exhausted"
    assert admission.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("committed", [False, True])
async def test_pending_recovery_after_long_shutdown_never_creates_stale_job(
    environment, committed
):
    store, _, _ = environment
    plan_id = add_plan(store)
    admission = FixedAdmission()
    due = NOW + timedelta(minutes=5)
    if committed:
        admission.fail_after_commit = True
    else:
        admission.error = RuntimeError("synthetic unavailable")
    assert await tick(store, admission, due) == ["pending_recovery"]
    admission.error = None
    # 多日停机只补登记已经存在的任务；新周期也按错过处理，不重放旧日期。
    states = await tick(store, admission, due + timedelta(days=5, hours=3))
    assert states == (["submitted", "missed"] if committed else ["missed", "missed"])
    assert len(admission.calls) == int(committed)
    assert store.current(plan_id)["pending_run_id"] is None


@pytest.mark.asyncio
async def test_unknown_previous_task_status_blocks_overlap(environment):
    store, _, _ = environment
    add_plan(store)
    admission = FixedAdmission()
    due = NOW + timedelta(minutes=5)
    assert await tick(store, admission, due) == ["submitted"]
    admission.jobs[admission.calls[0][2]] = "future_nonterminal_state"
    assert await tick(store, admission, due + timedelta(days=1)) == ["skipped_overlap"]
    assert len(admission.calls) == 1


@pytest.mark.asyncio
async def test_temporary_503_is_recorded_and_recovered_with_same_identity(environment):
    store, _, _ = environment
    plan_id = add_plan(store)
    admission = FixedAdmission()
    admission.error = HTTPException(503, "synthetic temporarily unavailable")
    due = NOW + timedelta(minutes=5)
    assert await tick(store, admission, due) == ["pending_recovery"]
    previous = store.history(plan_id, "manager")[0]
    assert previous["reason"] == "submission_interrupted"
    admission.error = None
    assert await tick(store, admission, due + timedelta(minutes=6)) == ["submitted"]
    assert store.history(plan_id, "manager")[0]["id"] == previous["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "records,expected_status",
    [
        ([dict(institute_id="B", patient_id="P1", visit_id="V1")], 403),
        (
            [
                dict(institute_id="A", patient_id="P1", visit_id="V1"),
                dict(institute_id="A", patient_id="P2", visit_id="V2"),
            ],
            422,
        ),
        ([], 422),
        ([dict(institute_id="A", visit_id="V1")], 422),
    ],
)
async def test_common_admission_rejects_scope_overflow_empty_and_broken_identity(
    monkeypatch, records, expected_status
):
    from app.routers import qc_sichuan
    from tests.unit.test_qc_dispatch_entrypoints import _main_settings
    from tests.unit.test_qc_sichuan_batch_throughput import _ServiceStub

    workspace = SimpleNamespace(
        collect_records=lambda **kwargs: records,
        create_batch_job=lambda **kwargs: pytest.fail(
            "invalid candidates cannot create task"
        ),
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "get_settings", _main_settings)
    monkeypatch.setattr(
        qc_sichuan,
        "submit_detached_task",
        lambda *args: pytest.fail("must not dispatch"),
    )
    with pytest.raises(HTTPException) as exc:
        await qc_sichuan.admit_workspace_batch_job(
            SimpleNamespace(state=SimpleNamespace()),
            qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key="luxian_0609_qc_v1", scope="final"
            ),
            {"id": "manager", "roles": ["admin"]},
            _ServiceStub(),
            scheduled_origin={
                "institute_id": "A",
                "max_records": 1,
                "run_id": str(uuid4()),
                "plan_id": str(uuid4()),
            },
        )
    assert exc.value.status_code == expected_status


@pytest.mark.asyncio
async def test_disabled_pending_plan_cannot_start_new_task(environment, monkeypatch):
    from app.services.daily_qc.service import BatchAdmission
    from app.services import (
        custom_qc_workspace_service as workspace_module,
        product_activation,
    )

    store, _, _ = environment
    plan_id = add_plan(store)
    due = NOW + timedelta(minutes=5)
    claimed = store.claim(due)
    store.prepare(claimed, due)
    store.save("manager", definition(enabled=False), due, plan_id, 1)
    monkeypatch.setattr(
        workspace_module,
        "CustomQCWorkspaceService",
        lambda **kwargs: SimpleNamespace(get_scheduled_batch_job=lambda **kwargs: None),
    )
    monkeypatch.setattr(
        product_activation,
        "get_product_activation_service",
        lambda: SimpleNamespace(enforce=lambda: None),
    )
    assert await tick(store, BatchAdmission(store), due + timedelta(minutes=6)) == [
        "failed"
    ]
    assert store.history(plan_id, "manager")[0]["reason"] == "disabled"
