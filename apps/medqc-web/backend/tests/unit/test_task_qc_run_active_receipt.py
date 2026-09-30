"""显式在院任务运行必须匹配最近一次成功同步快照。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskQCRun, QCTaskRecord
from app.services import task_qc_run_service as service
from app.services.qc_rule_sets import get_sichuan_rule_set
from app.services.task_record_sync_service import CONTRACT_VERSION, normalize_bundle_timestamp


REF = {"institute_id": "hospital", "patient_id": "patient", "visit_id": "visit-1"}
UPDATED_AT = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)


@pytest.fixture
def env(monkeypatch):
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.connect() as conn:
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS qc")
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    QCTaskQCRun.__table__.create(engine)
    metadata = sa.MetaData()
    jobs = sa.Table(
        "qc_async_jobs", metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("job_type", sa.String), sa.Column("business_type", sa.String),
        sa.Column("business_id", sa.String), sa.Column("status", sa.String),
        sa.Column("payload", sa.Text), sa.Column("result_summary", sa.Text),
        sa.Column("created_at", sa.DateTime),
        schema="qc",
    )
    metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as session:
        session.execute(QCTask.__table__.insert().values(
            id="task-1", task_number="TASK-1", task_name="测试", task_type="one_time",
            scene="running", rule_set_key="luxian_0916_qc_v1",
            rule_set_version=get_sichuan_rule_set("luxian_0916_qc_v1").version,
            creator_id="creator", status="sampling", total_records=1,
            sampling_config=json.dumps({"case_scope": "active"}),
        ))
        session.execute(QCTaskRecord.__table__.insert().values(
            id="association-1", task_id="task-1", record_id="association-1",
            **REF, status="pending", defect_count=0,
        ))
    payload = {
        "contract_version": CONTRACT_VERSION, "task_id": "task-1", "scene": "running",
        "records": [{"task_record_id": "association-1", **REF}],
    }
    summary = {
        "contract_version": CONTRACT_VERSION, "task_id": "task-1", "scene": "running",
        "total": 1, "ready_count": 1, "failed_count": 0,
        "records": [{
            "task_record_id": "association-1", "status": "ready",
            "bundle_schema_version": service.BUNDLE_SCHEMA_VERSION_CURRENT,
            "policy_version": CONTRACT_VERSION,
            "bundle_updated_at": normalize_bundle_timestamp(UPDATED_AT),
        }],
    }
    bundle = {
        **REF, "bundle_schema_version": service.BUNDLE_SCHEMA_VERSION_CURRENT,
        "policy_version": CONTRACT_VERSION, "bundle_updated_at": UPDATED_AT,
        "text_available": True, "medical_text": "合成病历",
    }
    monkeypatch.setattr(service, "SessionLocal", sessions)
    monkeypatch.setattr(service, "_load_scene_bundle", lambda **_: bundle)
    created = []
    workspace = SimpleNamespace(
        create_batch_job=lambda **kwargs: created.append(kwargs) or {"id": "workspace-1"},
    )
    monkeypatch.setattr(service, "prepare_workspace_batch_job", lambda request, **_: SimpleNamespace(
        create_kwargs={"filters": {
            "rule_set_key": request.rule_set_key,
            "rule_set_version": get_sichuan_rule_set(request.rule_set_key).version,
        }},
    ))
    state = SimpleNamespace(
        sessions=sessions, jobs=jobs, payload=payload, summary=summary,
        bundle=bundle, workspace=workspace, created=created, dispatched=[],
    )
    yield state
    engine.dispose()


def _job(env, *, job_id="sync-1", status="succeeded", created_at=UPDATED_AT):
    with env.sessions.begin() as session:
        session.execute(env.jobs.insert().values(
            id=job_id, job_type="task_record_sync", business_type="qc_task",
            business_id="task-1", status=status,
            payload=json.dumps(env.payload), result_summary=json.dumps(env.summary),
            created_at=created_at,
        ))


def _run(env, *, actor="creator", scope="all"):
    return service.create_task_qc_run(
        task_id="task-1", actor_id=actor, current_user={"id": actor},
        workspace_factory=lambda: env.workspace, qc_service=object(),
        dispatch=env.dispatched.append, run_scope=scope,
    )


def _blocked(env, pattern):
    with pytest.raises(service.TaskQCRunConflict, match=pattern):
        _run(env)
    assert env.created == []
    assert env.dispatched == []
    with env.sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(QCTaskQCRun.__table__)) == 0


def test_active_run_requires_successful_receipt(env):
    _blocked(env, "同步收据")


@pytest.mark.parametrize("status", ["accepted", "queued", "running", "retry_waiting"])
def test_active_run_blocks_inflight_sync_even_with_older_receipt(env, status):
    _job(env)
    _job(env, job_id="sync-2", status=status)
    _blocked(env, "尚未完成")


def test_active_run_cannot_reuse_old_receipt_after_partial_sync_failure(env):
    _job(env, created_at=datetime(2026, 9, 24, 7, 0, tzinfo=timezone.utc))
    _job(env, job_id="sync-2", status="failed", created_at=UPDATED_AT)
    _blocked(env, "同步收据")


@pytest.mark.parametrize("mutate", [
    lambda env: env.payload.update(contract_version="old"),
    lambda env: env.payload["records"][0].update(patient_id="other"),
    lambda env: env.payload["records"][0].update(task_record_id="other"),
    lambda env: env.summary.update(ready_count=0),
    lambda env: env.summary["records"][0].update(status="failed"),
    lambda env: env.summary["records"][0].update(task_record_id="other"),
    lambda env: env.summary["records"][0].update(policy_version="old"),
    lambda env: env.summary["records"][0].update(bundle_updated_at="2020-01-01T00:00:00+00:00"),
])
def test_active_run_rejects_drifted_receipt(env, mutate):
    mutate(env)
    _job(env)
    _blocked(env, "同步收据|Bundle")


def test_active_run_rejects_changed_current_bundle(env):
    _job(env)
    env.bundle["bundle_updated_at"] = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)
    _blocked(env, "Bundle")


def test_active_run_rejects_invalid_bundle_timestamp(env):
    _job(env)
    env.bundle["bundle_updated_at"] = None
    _blocked(env, "Bundle")


def test_active_run_rejects_bundle_read_failure(env, monkeypatch):
    _job(env)

    def unavailable(**_kwargs):
        raise RuntimeError("bundle database unavailable")

    monkeypatch.setattr(service, "_load_scene_bundle", unavailable)
    _blocked(env, "Bundle")


def test_active_run_accepts_exact_receipt(env):
    _job(env)
    result = _run(env)
    assert result["job_id"] == "workspace-1"
    assert env.dispatched == ["workspace-1"]
    assert len(env.created) == 1


def test_assigned_active_run_checks_only_actors_exact_case(env, monkeypatch):
    other_ref = {"institute_id": "hospital", "patient_id": "patient-2", "visit_id": "visit-2"}
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1")
                        .values(status="assigned", total_records=2))
        session.execute(QCTaskRecord.__table__.update().where(QCTaskRecord.id == "association-1")
                        .values(assignee_id="user-a"))
        session.execute(QCTaskRecord.__table__.insert().values(
            id="association-2", task_id="task-1", record_id="association-2",
            **other_ref, assignee_id="user-b", status="pending", defect_count=0,
        ))
    env.payload["records"].append({"task_record_id": "association-2", **other_ref})
    env.summary.update(total=2, ready_count=2)
    env.summary["records"].append({
        **env.summary["records"][0], "task_record_id": "association-2",
    })
    _job(env)
    looked_up = []

    def bundle_for_selected(**kwargs):
        looked_up.append(kwargs["patient_id"])
        assert kwargs["patient_id"] == "patient"
        return env.bundle

    monkeypatch.setattr(service, "_load_scene_bundle", bundle_for_selected)
    result = _run(env, actor="user-a", scope="assigned")
    assert result["run_scope"] == "assigned"
    assert looked_up == ["patient"]


def test_non_active_running_task_preserves_legacy_local_contract(env):
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1")
                        .values(sampling_config=json.dumps({"case_scope": "discharged"})))
    assert _run(env)["job_id"] == "workspace-1"


# ---------------------------------------------------------------------------
# 终末口径 B：终末“已出院”任务与在院任务同一回执合同，场景按任务自身校验
# ---------------------------------------------------------------------------


def _as_final_discharged(env):
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1").values(
            scene="final", rule_set_key="sc_content_v1",
            rule_set_version=get_sichuan_rule_set("sc_content_v1").version,
            sampling_config=json.dumps({"case_scope": "discharged"}),
        ))
    env.payload["scene"] = "final"
    env.summary["scene"] = "final"


def test_final_discharged_run_requires_successful_receipt(env):
    _as_final_discharged(env)
    _blocked(env, "缺少成功的资料同步收据")


def test_final_discharged_run_accepts_exact_final_receipt_and_final_bundle(env, monkeypatch):
    _as_final_discharged(env)
    _job(env)
    scenes = []

    def bundle(**kwargs):
        scenes.append(kwargs["scene"])
        return env.bundle

    monkeypatch.setattr(service, "_load_scene_bundle", bundle)
    result = _run(env)
    assert result["job_id"] == "workspace-1"
    assert scenes == ["final"]


def test_final_discharged_run_rejects_running_receipt(env):
    _as_final_discharged(env)
    env.payload["scene"] = "running"
    env.summary["scene"] = "running"
    _job(env)
    _blocked(env, "合同不一致")


def test_final_task_without_scope_keeps_legacy_local_contract(env):
    _as_final_discharged(env)
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1")
                        .values(sampling_config=json.dumps({})))
    assert _run(env)["job_id"] == "workspace-1"
