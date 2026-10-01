"""规则集版本接入运行链（合同第 5 节）的金样等价性与已发布版本场景（SQLite 合成数据，不连真实库）。

金样参考：tests/fixtures/legacy_workspace_batch_prepare.py 为接入前（b34aadce9）prepare 原实现的
逐字冻结副本；worker 投影以同一 filters 分别走“带摘要新分支”与“无摘要历史分支”对比。
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.database.models.qc import QCTask, QCTaskRecord, QCRuleSetVersion
from app.routers import tasks as tasks_router
from app.services import rule_set_version_service as version_service
from app.services import sichuan_workspace_batch_prepare as prepare_module
from app.services import task_qc_run_service
from app.services.luxian_0609.phase_scope import (
    build_luxian_0609_paused_rule_result,
    build_luxian_0609_pending_definition_result,
)
from app.services.qc_rule_sets import SICHUAN_RULE_SETS
from app.services.sample_validation_rule_sets import LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
from app.services.sichuan_workspace_batch_worker import _luxian_0609_customer_output_scope
from tests.fixtures import legacy_workspace_batch_prepare as legacy_module


KEY = "luxian_0609_qc_v1"
BUILTIN = SICHUAN_RULE_SETS[KEY].version
ACTOR = "u-manager"
ACTIVE_RULE = "LX0609-001"  # phase_1_target，内置版本 active
PENDING_RULE = "LX0609-020"  # pending_definition，内置版本 paused
EXCLUDED_RULE = "LX0609-033"  # 客户排除


@pytest.fixture
def version_sessions(monkeypatch):
    """独立的版本表（空表起步），并让发布时间严格递增，避免同毫秒发布导致当前版本不确定。"""
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCRuleSetVersion.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(version_service, "SessionLocal", factory)
    clock = {"now": datetime(2026, 9, 27, 8, 0, 0)}

    def _tick() -> datetime:
        clock["now"] += timedelta(seconds=1)
        return clock["now"]

    monkeypatch.setattr(version_service, "_now", _tick)
    yield factory
    engine.dispose()


def _native_settings() -> SimpleNamespace:
    return SimpleNamespace(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=True,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_MDT_040_ENABLED=True,
        LUXIAN_0609_NATIVE_EXTENDED_DOCUMENT_ENABLED=True,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=True,
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=True,
        LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED=True,
        LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=True,
        LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED=True,
        LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED=True,
        LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED=True,
        LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED=True,
        LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED=True,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
        LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED=True,
        LUXIAN_0609_RUNTIME_SHADOW_ENABLED=False,
    )


class _Workspace:
    def __init__(self, scope: str = "running"):
        self.scope = scope

    def collect_records(self, **_: Any) -> list[dict[str, Any]]:
        return [{
            "institute_id": "SYN-HOSP", "patient_id": "SYN-PAT", "record_id": "SYN-VISIT",
            "visit_id": "SYN-VISIT", "scope": self.scope,
            "admission_datetime": "2026-06-01 08:00:00", "discharge_datetime": "2026-06-05 08:00:00",
        }]


class _QCService:
    def assert_sc_rule_source_ready(self, **_: Any) -> dict[str, Any]:
        return {}


_SYN_REF = {"institute_id": "SYN-HOSP", "patient_id": "SYN-PAT", "visit_id": "SYN-VISIT"}

# 代表性输入：(用例名, payload 字段, 任务运行上下文, 记录场景)
_GOLDEN_CASES = [
    ("lx0609_full", {"rule_set_key": KEY, "scope": "running"}, None, "running"),
    (
        "lx0609_partial_with_pending_and_excluded",
        {"rule_set_key": KEY, "scope": "running",
         "rule_ids": [PENDING_RULE, ACTIVE_RULE.lower(), EXCLUDED_RULE, "LX0609-010"]},
        None, "running",
    ),
    (
        "lx0609_task_run",
        {"rule_set_key": KEY, "scope": "running", "record_refs": [_SYN_REF]},
        {"task_id": "task-1", "run_number": "3"}, "running",
    ),
    ("lx0916_full", {"rule_set_key": "luxian_0916_qc_v1", "scope": "running"}, None, "running"),
    ("sc_content_full", {"rule_set_key": "sc_content_v1", "scope": "final"}, None, "final"),
    (
        "sc_content_task_run",
        {"rule_set_key": "sc_content_v1", "scope": "final", "record_refs": [_SYN_REF]},
        {"task_id": "task-2", "run_number": "1"}, "final",
    ),
    ("no_rule_set", {"rule_ids": ["SC-001"], "scope": "final"}, None, "final"),
]


def _run_prepare(module, fields, task_run_context, record_scope, **extra):
    return module.prepare_workspace_batch_job(
        module.SichuanWorkspaceBatchJobCreateRequest(**fields),
        qc_service=_QCService(),  # type: ignore[arg-type]
        workspace=_Workspace(record_scope),  # type: ignore[arg-type]
        settings_provider=_native_settings,
        task_run_context=task_run_context,
        **extra,
    )


def _idempotency_key(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    return f"sichuan-workspace-run:{digest}"


# ---------------------------------------------------------------------------
# 金样：表为空（只有内置版本）时 prepare 与改动前逐键相同
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fields", "task_run_context", "record_scope"),
    [case[1:] for case in _GOLDEN_CASES],
    ids=[case[0] for case in _GOLDEN_CASES],
)
def test_prepare_filters_equal_legacy_reference_with_builtin_only(
    version_sessions, fields, task_run_context, record_scope,
):
    rule_set = SICHUAN_RULE_SETS.get(str(fields.get("rule_set_key") or ""))
    extra = (
        {"frozen_rule_set_version": rule_set.version}
        if task_run_context is not None and rule_set is not None
        else {}
    )
    legacy = _run_prepare(legacy_module, fields, task_run_context, record_scope)
    new = _run_prepare(prepare_module, fields, task_run_context, record_scope, **extra)

    legacy_kwargs = copy.deepcopy(legacy.create_kwargs)
    new_kwargs = copy.deepcopy(new.create_kwargs)
    new_filters = new_kwargs["filters"]
    digest = new_filters.pop("rule_set_content_digest", None)
    excluded = new_filters.pop("excluded_customer_rule_ids", None)
    payload_digest = new_filters["idempotency_payload"].pop("rule_set_content_digest", None)
    # 新增摘要写入 idempotency_payload，幂等键随之变化；两侧均按各自 payload 自洽。
    assert legacy_kwargs["filters"].pop("idempotency_key") == _idempotency_key(
        legacy.create_kwargs["filters"]["idempotency_payload"]
    ) == legacy.idempotency_key
    assert new_filters.pop("idempotency_key") == _idempotency_key(
        new.create_kwargs["filters"]["idempotency_payload"]
    ) == new.idempotency_key

    # 除新增字段与派生幂等键外，create_kwargs（含 filters 各列表顺序）与 response_fields 逐键相同。
    assert new_kwargs.keys() == legacy_kwargs.keys()
    for key in legacy_kwargs:
        if key == "filters":
            assert new_filters.keys() == legacy_kwargs["filters"].keys()
            for filter_key, legacy_value in legacy_kwargs["filters"].items():
                assert new_filters[filter_key] == legacy_value, filter_key
        else:
            assert new_kwargs[key] == legacy_kwargs[key], key
    assert new.response_fields == legacy.response_fields

    if rule_set is None:
        assert digest is None and excluded is None and payload_digest is None
        return
    builtin = version_service.resolve_rule_set_version(rule_set.key, rule_set.version)
    assert digest == payload_digest == builtin["content_digest"]
    assert excluded == builtin["excluded_rule_ids"]
    if rule_set.key == KEY:
        assert set(excluded) == set(LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS)


def _projection(filters: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    """复刻 worker 对 filters 的读取，返回输出规则顺序与每条规则的结果来源。"""
    scoped = {str(r).strip().upper() for r in filters.get("scoped_customer_rule_ids") or [] if str(r).strip()}
    paused = {str(r).strip().upper() for r in filters.get("paused_customer_rule_ids") or [] if str(r).strip()}
    executed = {str(r).strip().upper() for r in filters.get("rule_ids") or []}
    paused_set, output = _luxian_0609_customer_output_scope(
        filters, scoped_customer_rule_ids=scoped, paused_customer_rule_ids=paused,
    )
    output_ids = [rule_id for rule_id, _ in output]
    states = {
        rule_id: ("executed" if rule_id in executed else "not_executed" if rule_id in paused_set else "missing")
        for rule_id in output_ids
    }
    return output_ids, states


@pytest.mark.parametrize(
    ("fields", "task_run_context"),
    [(case[1], case[2]) for case in _GOLDEN_CASES if case[1].get("rule_set_key") == KEY],
    ids=[case[0] for case in _GOLDEN_CASES if case[1].get("rule_set_key") == KEY],
)
def test_worker_projection_new_branch_equals_legacy_branch_with_builtin(
    version_sessions, fields, task_run_context,
):
    extra = {"frozen_rule_set_version": BUILTIN} if task_run_context is not None else {}
    filters = _run_prepare(prepare_module, fields, task_run_context, "running", **extra).create_kwargs["filters"]
    assert filters["rule_set_content_digest"]
    legacy_filters = {
        key: value for key, value in filters.items()
        if key not in {"rule_set_content_digest", "excluded_customer_rule_ids"}
    }

    new_ids, new_states = _projection(filters)
    legacy_ids, legacy_states = _projection(legacy_filters)
    assert new_ids == legacy_ids
    assert new_states == legacy_states
    assert "missing" not in new_states.values()


# ---------------------------------------------------------------------------
# 已发布版本：暂停一条 active 规则
# ---------------------------------------------------------------------------


def _publish_pausing(rule_id: str, version: str) -> dict[str, Any]:
    draft = version_service.create_draft(KEY, actor=ACTOR)
    entries = [
        {
            **item,
            "state": "paused" if item["rule_id"] == rule_id else item["state"],
            "department_scope_mode": "all",
            "department_refs": [],
            "doctor_visible": False,
        }
        for item in draft["entries"]
    ]
    draft = version_service.update_draft(
        KEY, actor=ACTOR, version_seq=draft["version_seq"], entries=entries,
    )
    return version_service.publish_draft(KEY, actor=ACTOR, version=version)


def test_published_version_pauses_active_rule_through_prepare_worker_and_canonical_check(version_sessions):
    published = _publish_pausing(ACTIVE_RULE, "2026-09-27.1")
    assert version_service.current_version(KEY) == "2026-09-27.1"

    filters = _run_prepare(
        prepare_module, {"rule_set_key": KEY, "scope": "running"}, None, "running",
    ).create_kwargs["filters"]
    assert filters["rule_set_version"] == "2026-09-27.1"
    assert filters["rule_set_content_digest"] == published["content_digest"]
    assert filters["idempotency_payload"]["rule_set_content_digest"] == published["content_digest"]
    assert ACTIVE_RULE not in filters["rule_ids"]
    assert ACTIVE_RULE not in filters["active_customer_rule_ids"]
    assert ACTIVE_RULE in filters["paused_customer_rule_ids"]
    assert ACTIVE_RULE in filters["scoped_customer_rule_ids"]
    assert not set(filters["scoped_customer_rule_ids"]) & set(filters["excluded_customer_rule_ids"])
    assert filters["execution_rule_count"] == len(filters["rule_ids"])

    output_ids, states = _projection(filters)
    assert states[ACTIVE_RULE] == "not_executed"
    assert "missing" not in states.values()
    # worker 对暂停规则的正式结果：not_executed，版本暂停原因码；原 phase 暂停规则文案不变。
    paused_result = build_luxian_0609_paused_rule_result(ACTIVE_RULE)
    assert paused_result["status"] == "not_executed"
    assert paused_result["metadata"]["reason_code"] == "rule_set_version_paused"
    assert build_luxian_0609_paused_rule_result(PENDING_RULE) == build_luxian_0609_pending_definition_result(
        PENDING_RULE
    )

    # task_qc_run_service Canonical 完整性校验的期望集合 == worker 输出集合（不报 Conflict）。
    expected = {
        str(rule_id).strip().upper()
        for group in (
            filters.get("scoped_customer_rule_ids") or filters.get("rule_ids") or [],
            filters.get("gate_only_customer_rule_ids") or [],
            filters.get("paused_customer_rule_ids") or [],
        )
        for rule_id in group
    }
    assert expected == set(output_ids)


def test_worker_new_branch_uses_frozen_excluded_not_static_list():
    """新 job 以 filters 冻结的 excluded 为准：静态排除名单外的规则被下线时同样不输出。"""
    filters = {
        "rule_set_content_digest": "d" * 64,
        "excluded_customer_rule_ids": ["LX0609-002"],
        "scoped_customer_rule_ids": [],
        "paused_customer_rule_ids": [],
    }
    paused, output = _luxian_0609_customer_output_scope(
        filters, scoped_customer_rule_ids=set(), paused_customer_rule_ids=set(),
    )
    output_ids = [rule_id for rule_id, _ in output]
    assert "LX0609-002" not in output_ids
    assert EXCLUDED_RULE in output_ids  # 不再读取静态排除名单
    assert paused == set()  # 不再补入当前 phase 未就绪规则


# ---------------------------------------------------------------------------
# prepare 版本来源
# ---------------------------------------------------------------------------


def test_task_run_prepare_uses_frozen_version_and_fails_closed(version_sessions):
    _publish_pausing(ACTIVE_RULE, "2026-09-27.1")
    fields = {"rule_set_key": KEY, "scope": "running", "record_refs": [_SYN_REF]}
    context = {"task_id": "task-1", "run_number": "1"}

    frozen_builtin = _run_prepare(
        prepare_module, fields, context, "running", frozen_rule_set_version=BUILTIN,
    ).create_kwargs["filters"]
    assert frozen_builtin["rule_set_version"] == BUILTIN
    assert ACTIVE_RULE in frozen_builtin["rule_ids"]

    with pytest.raises(HTTPException) as missing:
        _run_prepare(prepare_module, fields, context, "running")
    assert missing.value.status_code == 422
    with pytest.raises(HTTPException) as unknown:
        _run_prepare(prepare_module, fields, context, "running", frozen_rule_set_version="no-such")
    assert unknown.value.status_code == 409


def test_prepare_maps_version_store_unavailable_to_503(monkeypatch):
    monkeypatch.setattr(version_service, "SessionLocal", None)
    with pytest.raises(HTTPException) as exc:
        _run_prepare(prepare_module, {"rule_set_key": KEY, "scope": "running"}, None, "running")
    assert exc.value.status_code == 503


# ---------------------------------------------------------------------------
# 任务创建冻结与运行解析
# ---------------------------------------------------------------------------


class _Database:
    def __init__(self):
        self.inserted: list[dict[str, Any]] = []

    def table(self, name):
        assert name == "qc_tasks"
        return self

    def insert(self, payload):
        self.inserted.append(dict(payload))
        return self

    def execute(self):
        return SimpleNamespace(data=[self.inserted[-1]])


def _create_task(monkeypatch, database) -> Any:
    app = FastAPI()
    app.include_router(tasks_router.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "creator-1", "display_name": "质控员", "roles": ["admin"]
    }
    monkeypatch.setattr(tasks_router, "get_supabase", lambda: database)

    async def execute(query):
        return query.execute()

    monkeypatch.setattr(tasks_router, "async_execute", execute)
    return TestClient(app).post(
        "/api/v1/tasks", json={"task_name": "合成任务", "scene": "running", "rule_set_key": KEY},
    )


def test_task_creation_freezes_current_version(monkeypatch, version_sessions):
    database = _Database()
    assert _create_task(monkeypatch, database).status_code == 200
    assert database.inserted[-1]["rule_set_version"] == BUILTIN

    _publish_pausing(ACTIVE_RULE, "2026-09-27.1")
    assert _create_task(monkeypatch, database).status_code == 200
    assert database.inserted[-1]["rule_set_version"] == "2026-09-27.1"


def test_task_creation_version_store_unavailable_is_503(monkeypatch):
    monkeypatch.setattr(version_service, "SessionLocal", None)
    database = _Database()
    response = _create_task(monkeypatch, database)
    assert response.status_code == 503
    assert database.inserted == []


@pytest.fixture
def task_session():
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def _task_with_version(factory, version):
    with factory.begin() as session:
        session.execute(sa.delete(QCTaskRecord.__table__))
        session.execute(sa.delete(QCTask.__table__))
        session.execute(QCTask.__table__.insert().values(
            id="task-1", task_number="TASK-1", task_name="测试", task_type="one_time",
            scene="running", rule_set_key=KEY, rule_set_version=version,
            creator_id="user-1", status="sampling", total_records=1,
        ))
        session.execute(QCTaskRecord.__table__.insert().values(
            id="association-1", task_id="task-1", record_id="association-1",
            institute_id="hospital", patient_id="patient", visit_id="visit-1",
            status="pending", defect_count=0,
        ))
    with factory() as session:
        return task_qc_run_service._task_and_refs(session, "task-1", "user-1", "all")


def test_frozen_versions_remain_runnable_after_publish_and_retire(version_sessions, task_session):
    # 冻结内置版本：发布新版本后仍可运行。
    _publish_pausing(ACTIVE_RULE, "2026-09-27.1")
    task, refs = _task_with_version(task_session, BUILTIN)
    assert task["rule_set_version"] == BUILTIN and len(refs) == 1

    # 冻结已发布版本：再发布新版本并下线旧版本后仍可解析运行。
    _publish_pausing("LX0609-002", "2026-09-27.2")
    version_service.retire_version(KEY, "2026-09-27.1", actor=ACTOR)
    assert version_service.resolve_rule_set_version(KEY, "2026-09-27.1")["source"] == "retired"
    task, _ = _task_with_version(task_session, "2026-09-27.1")
    assert task["rule_set_version"] == "2026-09-27.1"


@pytest.mark.parametrize("version", ["no-such-version", None, ""])
def test_unknown_or_missing_frozen_version_is_conflict(version_sessions, task_session, version):
    with pytest.raises(task_qc_run_service.TaskQCRunConflict, match="任务规则集版本缺失"):
        _task_with_version(task_session, version)


def test_create_task_qc_run_passes_frozen_version_to_prepare(monkeypatch, version_sessions, task_session):
    _publish_pausing(ACTIVE_RULE, "2026-09-27.1")
    _task_with_version(task_session, "2026-09-27.1")
    monkeypatch.setattr(task_qc_run_service, "SessionLocal", task_session)
    monkeypatch.setattr(task_qc_run_service, "_next_run_number", lambda *_: 1)
    calls: list[dict[str, Any]] = []

    def prepare(payload, **kwargs):
        calls.append(kwargs)
        raise HTTPException(status_code=418, detail="stop")

    monkeypatch.setattr(task_qc_run_service, "prepare_workspace_batch_job", prepare)
    with pytest.raises(HTTPException):
        task_qc_run_service.create_task_qc_run(
            task_id="task-1", actor_id="user-1", current_user={"id": "user-1"},
            workspace_factory=lambda: object(), qc_service=object(), dispatch=lambda _: None,
        )
    assert calls[0]["frozen_rule_set_version"] == "2026-09-27.1"
    assert calls[0]["task_run_context"] == {"task_id": "task-1", "run_number": "1"}
