"""现代申诉创建：授权、科室、目标重验、冻结来源与零写入反例（合成 SQLite，不连库）。"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.database.models.qc import (
    QCAppeal,
    QCDefect,
    QCDefectHistory,
    QCTaskQCRun,
    QCTaskRecord,
)
from app.routers import appeals as appeals_router
from app.services import appeal_create_service as service
from app.services import appeal_manual_target_service as manual_target
from app.services import appeal_workspace_target_service as workspace_target
from app.services import record_review_service
from app.services.qc_workspace import canonical_result_store as canonical_store
from app.services.case_identity import CaseRef
from app.services.luxian_0609_result_schema import CANONICAL_RESULT_DELIVERY_MODE
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from app.services.qc_workspace.canonical_result_store import (
    RECORD_RESULT_ENVELOPE_SCHEMA,
    customer_safe_projection_key,
    keyed_ref,
    lock_case_result_mutations,
)

CASE_A = ("hospital-a", "patient-1", "visit-1")
CASE_B = ("hospital-a", "patient-2", "visit-2")
CASE_A_OTHER_HOSPITAL = ("hospital-b", "patient-1", "visit-1")
JOB_A = "job-a"
ENVELOPE_A = "envelope-a"
JOB_B = "job-b"
ENVELOPE_B = "envelope-b"
RULE_SET_VERSION = "2026.09"
DEPT = "心内科"
OTHER_DEPT = "骨科"

DEFECT_ID = "00000000-0000-4000-8000-000000000001"
TASK_ID = "task-1"
TASK_RECORD_ID = "task-record-1"
MANUAL_JOB = "job-manual"
QC_ACTOR = "qc-creator"
MANUAL_RULE_SET = ("luxian_0609_qc_v1", "2026-06-09")
REASON = "该缺陷与病历事实不符，病程记录已按时完成。"


def _doctor(
    department: str | None = DEPT,
    user_id: str = "doctor-1",
    roles=("doctor",),
    institute_id: str | None = CASE_A[0],
):
    user = {"id": user_id, "roles": list(roles), "display_name": "合成医生"}
    if institute_id is not None:
        user["institute_id"] = institute_id
    if department is not None:
        user["department"] = department
    return user


def _record_ref(identity: tuple[str, str, str]) -> str:
    return keyed_ref("rec", CaseRef(*identity).as_key(), hmac_key=customer_safe_projection_key())


def _ready(identity, job_id, envelope_id, items):
    return {
        "state": "ready", "job_id": job_id, "root_job_id": job_id, "envelope_id": envelope_id,
        "rule_set_key": LUXIAN_0609_RULE_SET_KEY, "rule_set_version": RULE_SET_VERSION,
        "record_ref": _record_ref(identity), "items": items,
    }


def _envelope_table() -> sa.Table:
    metadata = sa.MetaData()
    return sa.Table(
        "luxian_0609_record_result_envelopes", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("root_job_id", sa.String(36), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("record_id", sa.String(128), nullable=False),
        sa.Column("institute_id", sa.String(128), nullable=False),
        sa.Column("patient_id", sa.String(128), nullable=False),
        sa.Column("visit_id", sa.String(128), nullable=False),
        sa.Column("rule_set_key", sa.String(96), nullable=False),
        sa.Column("rule_set_version", sa.String(96), nullable=False),
        sa.Column("envelope_json", sa.Text, nullable=False),
        sa.Column("result_count", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )


def _job_table() -> sa.Table:
    metadata = sa.MetaData()
    return sa.Table(
        "custom_qc_batch_jobs", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("filters_json", sa.Text, nullable=False),
    )


class Workspace:
    """同时提供单病历最新结果读取（Canonical）与 job 表（人工缺陷）。"""

    def __init__(self, jobs: sa.Table, results: dict):
        self._batch_job_table = jobs
        self.results = results
        self.calls: list[tuple[str, str, str]] = []

    def build_latest_single_record_result_dto(self, *, institute_id, patient_id, visit_id):
        identity = (institute_id, patient_id, visit_id)
        self.calls.append(identity)
        return self.results.get(identity, {"state": "not_found", "items": []})


class Env:
    def __init__(self, sessions, workspace, departments):
        self.sessions = sessions
        self.workspace = workspace
        self.departments = departments
        self.department_calls: list = []
        self.scene = "running"

    def loader(self, identities, *, session):
        assert session is not None  # 科室必须在创建事务内读取
        identities = list(identities)
        self.department_calls.append(identities)
        return {identity: self.departments[identity] for identity in identities if identity in self.departments}

    def create(self, user=None, **overrides):
        session_factory = overrides.pop("_session_factory", self.sessions)
        payload = {
            "target_kind": "canonical_defect",
            "institute_id": CASE_A[0], "patient_id": CASE_A[1], "visit_id": CASE_A[2],
            "scene": "running", "reason": REASON,
            "expected_job_id": JOB_A, "expected_envelope_id": ENVELOPE_A,
            "rule_id": "LX0609-001",
        }
        payload.update(overrides)
        return service.create_modern_appeal(
            service.ModernAppealRequest(**payload),
            current_user=_doctor() if user is None else user,
            workspace_factory=lambda: self.workspace,
            department_loader=self.loader,
            session_factory=session_factory,
        )

    def manual(self, user=None, **overrides):
        payload = {
            "target_kind": "task_manual_defect", "defect_id": DEFECT_ID,
            "expected_job_id": None, "expected_envelope_id": None, "rule_id": None,
        }
        payload.update(overrides)
        return self.create(user, **payload)

    def appeal_rows(self) -> list[dict]:
        with self.sessions() as session:
            return [dict(row) for row in session.execute(sa.select(QCAppeal.__table__)).mappings()]

    def set_manual_status(self, status: str) -> None:
        with self.sessions.begin() as session:
            session.execute(
                sa.update(QCDefect).where(QCDefect.id == DEFECT_ID)
                .values(manual_review_status=status)
            )

    def set_defect_status(self, status: str) -> None:
        with self.sessions.begin() as session:
            session.execute(
                sa.update(QCDefect).where(QCDefect.id == DEFECT_ID).values(status=status)
            )


def _manual_filters() -> str:
    return json.dumps({
        "task_id": TASK_ID, "task_run_number": "2",
        "rule_set_key": MANUAL_RULE_SET[0], "rule_set_version": MANUAL_RULE_SET[1],
        "query_scope": "running",
        "record_refs": [dict(zip(("institute_id", "patient_id", "visit_id"), CASE_A))],
    })


@pytest.fixture
def env(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    for table in (
        QCAppeal.__table__, QCDefect.__table__, QCDefectHistory.__table__,
        QCTaskRecord.__table__, QCTaskQCRun.__table__,
    ):
        table.create(engine)
    envelopes = _envelope_table()
    envelopes.create(engine)
    jobs = _job_table()
    jobs.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2026, 9, 28)
    with sessions.begin() as session:
        session.add(QCTaskRecord(
            id=TASK_RECORD_ID, task_id=TASK_ID, record_id=TASK_RECORD_ID,
            institute_id=CASE_A[0], patient_id=CASE_A[1], visit_id=CASE_A[2],
            assignee_id="assignee", status="in_progress", created_at=now,
        ))
        session.add(QCTaskQCRun(
            task_id=TASK_ID, run_number=2, job_id=MANUAL_JOB,
            triggered_by=QC_ACTOR, run_scope="assigned", created_at=now,
        ))
        session.add(QCDefect(
            id=DEFECT_ID, record_id=TASK_RECORD_ID, identity_version=1,
            source_key="task_assigned_qc", scene="running",
            institute_id=CASE_A[0], patient_id=CASE_A[1], visit_id=CASE_A[2],
            origin="manual", manual_review_status="approved", manual_created_by=QC_ACTOR,
            rule_code="MANUAL-007", rule_name="人工规则", description="人工发现的缺陷",
            severity="warning", status="pending", deduct_score=0.0,
            created_at=now, updated_at=now,
        ))
        session.add(QCDefectHistory(
            id="history-1", defect_id=DEFECT_ID, action="manual_create", actor_id=QC_ACTOR,
            details=json.dumps({
                "task_id": TASK_ID, "task_record_id": TASK_RECORD_ID,
                "run_number": 2, "job_id": MANUAL_JOB, "scene": "running",
            }),
            created_at=now,
        ))
        session.execute(jobs.insert(), [
            {"id": MANUAL_JOB, "created_by": QC_ACTOR, "filters_json": _manual_filters()},
        ])
        session.execute(envelopes.insert().values(
            id="envelope-manual", job_id=MANUAL_JOB, root_job_id=MANUAL_JOB,
            created_by=QC_ACTOR, record_id=CASE_A[2],
            institute_id=CASE_A[0], patient_id=CASE_A[1], visit_id=CASE_A[2],
            rule_set_key=MANUAL_RULE_SET[0], rule_set_version=MANUAL_RULE_SET[1],
            envelope_json=json.dumps({
                "schema_version": RECORD_RESULT_ENVELOPE_SCHEMA,
                "delivery_mode": CANONICAL_RESULT_DELIVERY_MODE,
                "items": [{"rule_id": "LX0609-001"}],
            }),
            result_count=1, created_at=now, updated_at=now,
        ))

    items_a = [
        {"rule_id": "LX0609-001", "is_confirmed_issue": True, "rule_name": "规则一"},
        {"rule_id": "LX0609-002", "is_confirmed_issue": False},
        {"rule_id": "LX0609-003", "is_confirmed_issue": True},
        {"rule_id": "LX0609-003", "is_confirmed_issue": True},
    ]
    workspace = Workspace(jobs, {
        CASE_A: _ready(CASE_A, JOB_A, ENVELOPE_A, items_a),
        CASE_B: _ready(CASE_B, JOB_B, ENVELOPE_B, [
            {"rule_id": "LX0609-001", "is_confirmed_issue": True},
        ]),
    })
    state = Env(sessions, workspace, {CASE_A: DEPT, CASE_B: DEPT, CASE_A_OTHER_HOSPITAL: DEPT})
    monkeypatch.setattr(manual_target, "_envelope_table", lambda: envelopes)
    monkeypatch.setattr(workspace_target, "_project_items", lambda items: items)
    monkeypatch.setattr(
        record_review_service, "_envelope_ids",
        lambda _session, *, job_id, identity, **_kwargs: (
            [ENVELOPE_A] if (job_id, identity) == (JOB_A, CASE_A)
            else [ENVELOPE_B] if (job_id, identity) == (JOB_B, CASE_B) else []
        ),
    )
    monkeypatch.setattr(
        record_review_service, "_workspace_review_scene",
        lambda _session, **_kwargs: state.scene,
    )
    yield state
    engine.dispose()


# ---------------------------------------------------------------- 成功路径


def test_canonical_defect_success_freezes_source_and_reads_back(env):
    result = env.create()

    rows = env.appeal_rows()
    assert len(rows) == 1
    row = rows[0]
    assert result["id"] == row["id"]
    assert {key: row[key] for key in (
        "target_kind", "target_id", "institute_id", "patient_id", "visit_id", "scene",
        "root_job_id", "envelope_id", "rule_set_key", "rule_set_version",
        "case_department", "appellant_department", "appellant_id", "status",
        "qc_result_id", "record_id", "appeal_type", "defect_item",
    )} == {
        "target_kind": "canonical_defect", "target_id": "LX0609-001",
        "institute_id": CASE_A[0], "patient_id": CASE_A[1], "visit_id": CASE_A[2],
        "scene": "running", "root_job_id": JOB_A, "envelope_id": ENVELOPE_A,
        "rule_set_key": LUXIAN_0609_RULE_SET_KEY, "rule_set_version": RULE_SET_VERSION,
        "case_department": DEPT, "appellant_department": DEPT, "appellant_id": "doctor-1",
        "status": "pending", "qc_result_id": None, "record_id": None,
        "appeal_type": "defect", "defect_item": "LX0609-001",
    }
    assert result["evidence"] == []
    assert env.department_calls == [[CASE_A]]


def test_manual_defect_success_requires_approved_and_freezes_task_source(env):
    result = env.manual()

    row = env.appeal_rows()[0]
    assert result["target_kind"] == row["target_kind"] == "task_manual_defect"
    assert row["target_id"] == DEFECT_ID
    assert row["root_job_id"] == MANUAL_JOB
    assert row["envelope_id"] == "envelope-manual"
    assert (row["rule_set_key"], row["rule_set_version"]) == MANUAL_RULE_SET
    assert row["scene"] == "running"
    assert row["defect_item"] == "MANUAL-007"
    assert row["case_department"] == DEPT


def test_withdrawn_appeal_does_not_block_a_new_one(env):
    first = env.create()
    with env.sessions.begin() as session:
        session.execute(
            sa.update(QCAppeal).where(QCAppeal.id == first["id"]).values(status="withdrawn")
        )
    env.create()
    assert len(env.appeal_rows()) == 2


# ---------------------------------------------------------------- 反例：全部零写入


def _assert_rejected(env, error, call, match=None):
    with pytest.raises(error, match=match):
        call()
    assert env.appeal_rows() == []


def test_result_of_case_a_cannot_be_bound_to_case_b(env):
    _assert_rejected(
        env, service.ModernAppealConflict,
        lambda: env.create(institute_id=CASE_B[0], patient_id=CASE_B[1], visit_id=CASE_B[2]),
    )


def test_same_patient_and_visit_in_other_hospital_is_not_the_same_case(env):
    _assert_rejected(
        env, service.ModernAppealForbidden,
        lambda: env.create(institute_id=CASE_A_OTHER_HOSPITAL[0]), match="本机构",
    )
    assert env.department_calls == []
    assert env.workspace.calls == []


def test_department_comes_from_account_not_client(env):
    # 服务端请求对象根本没有科室字段；账号科室与病例不符即拒绝。
    _assert_rejected(
        env, service.ModernAppealForbidden, lambda: env.create(user=_doctor(OTHER_DEPT)),
        match="本科室",
    )
    assert env.workspace.calls == []  # 授权失败前不读取目标，避免泄露其他科室结果


def test_api_rejects_forged_department_and_legacy_fields_without_writes(env, monkeypatch):
    calls = []
    monkeypatch.setattr(
        service, "create_modern_appeal", lambda *args, **kwargs: calls.append(1),
    )
    app = FastAPI()
    app.include_router(appeals_router.router)
    app.dependency_overrides[get_current_user] = lambda: _doctor(OTHER_DEPT)
    client = TestClient(app)
    base = {
        "target_kind": "canonical_defect", "institute_id": CASE_A[0],
        "patient_id": CASE_A[1], "visit_id": CASE_A[2], "scene": "running",
        "expected_job_id": JOB_A, "expected_envelope_id": ENVELOPE_A,
        "rule_id": "LX0609-001", "reason": REASON,
    }
    for forged in (
        {"appellant_department": DEPT}, {"case_department": DEPT},
        {"qc_result_id": "00000000-0000-4000-8000-000000000009"},
        {"appellant_id": "doctor-2"}, {"scene": "all"},
    ):
        response = client.post("/api/v1/appeals/modern", json={**base, **forged})
        assert response.status_code == 422, forged
    assert calls == []
    assert env.appeal_rows() == []


def test_doctor_without_department_fails_closed(env):
    _assert_rejected(
        env, service.ModernAppealForbidden, lambda: env.create(user=_doctor(None)),
        match="未配置科室",
    )
    _assert_rejected(
        env, service.ModernAppealForbidden, lambda: env.create(user=_doctor("   ")),
        match="未配置科室",
    )
    assert env.department_calls == []


def test_doctor_without_server_side_institute_scope_fails_closed(env):
    _assert_rejected(
        env, service.ModernAppealForbidden,
        lambda: env.create(user=_doctor(institute_id=None)), match="机构范围",
    )
    assert env.department_calls == []
    assert env.workspace.calls == []


def test_same_department_name_in_other_hospital_does_not_grant_access(env):
    _assert_rejected(
        env, service.ModernAppealForbidden,
        lambda: env.create(
            user=_doctor(institute_id=CASE_A_OTHER_HOSPITAL[0]),
            institute_id=CASE_A[0],
        ),
        match="本机构",
    )
    assert env.department_calls == []
    assert env.workspace.calls == []


@pytest.mark.parametrize("roles", [("qc_manager",), ("admin",), ("coder",), ()])
def test_only_doctor_role_can_create(env, roles):
    _assert_rejected(
        env, service.ModernAppealForbidden, lambda: env.create(user=_doctor(roles=roles)),
        match="仅医生",
    )


def test_case_outside_own_department_is_forbidden(env):
    env.departments[CASE_A] = OTHER_DEPT
    _assert_rejected(env, service.ModernAppealForbidden, env.create, match="本科室")
    _assert_rejected(env, service.ModernAppealForbidden, env.manual, match="本科室")


def test_department_source_error_fails_closed(env):
    def broken(_identities, *, session):
        raise RuntimeError("private source detail")

    with pytest.raises(service.ModernAppealUnavailable) as caught:
        service.create_modern_appeal(
            service.ModernAppealRequest(
                target_kind="canonical_defect", institute_id=CASE_A[0],
                patient_id=CASE_A[1], visit_id=CASE_A[2], scene="running", reason=REASON,
                expected_job_id=JOB_A, expected_envelope_id=ENVELOPE_A, rule_id="LX0609-001",
            ),
            current_user=_doctor(), workspace_factory=lambda: env.workspace,
            department_loader=broken, session_factory=env.sessions,
        )
    assert "private" not in str(caught.value)
    assert env.appeal_rows() == []


@pytest.mark.parametrize("status", ["pending", "rejected", None])
def test_pending_or_rejected_manual_defect_is_not_appealable(env, status):
    env.set_manual_status(status)
    _assert_rejected(env, service.ModernAppealConflict, env.manual, match="审核通过")


@pytest.mark.parametrize("status", ["remediated", "approved"])
def test_resolved_manual_defect_is_not_appealable_or_listed(env, status):
    env.set_defect_status(status)
    _assert_rejected(env, service.ModernAppealConflict, env.manual, match="已失效")
    data = service.list_modern_appeal_candidates(
        institute_id=CASE_A[0], patient_id=CASE_A[1], visit_id=CASE_A[2],
        current_user=_doctor(), workspace_factory=lambda: env.workspace,
        department_loader=env.loader, session_factory=env.sessions,
    )
    assert data["manual_defects"] == []


def test_manual_defect_scene_mismatch_and_foreign_case_are_rejected(env):
    _assert_rejected(env, service.ModernAppealConflict, lambda: env.manual(scene="final"),
                     match="场景")
    _assert_rejected(
        env, service.ModernAppealConflict,
        lambda: env.manual(institute_id=CASE_B[0], patient_id=CASE_B[1], visit_id=CASE_B[2]),
        match="三坐标",
    )
    _assert_rejected(env, service.ModernAppealConflict,
                     lambda: env.manual(expected_envelope_id=ENVELOPE_A), match="来源结果")


def test_manual_defect_rejects_rule_id_and_missing_defect(env):
    _assert_rejected(env, service.ModernAppealInvalid, lambda: env.manual(rule_id="LX0609-001"))
    _assert_rejected(
        env, service.ModernAppealNotFound,
        lambda: env.manual(defect_id="00000000-0000-4000-8000-00000000ffff"),
    )


def test_missing_or_duplicated_rule_is_rejected(env):
    _assert_rejected(env, service.ModernAppealNotFound, lambda: env.create(rule_id="LX0609-099"))
    _assert_rejected(env, service.ModernAppealConflict, lambda: env.create(rule_id="LX0609-003"),
                     match="不唯一")
    _assert_rejected(env, service.ModernAppealConflict, lambda: env.create(rule_id="LX0609-002"),
                     match="已确认缺陷")
    _assert_rejected(env, service.ModernAppealInvalid, lambda: env.create(rule_id=None))


def test_source_scene_conflict_is_rejected(env):
    env.scene = "final"
    _assert_rejected(env, service.ModernAppealConflict, env.create, match="场景")


def test_latest_result_switch_after_candidate_read_is_rejected(env):
    env.workspace.results[CASE_A] = _ready(
        CASE_A, "job-new", "envelope-new",
        [{"rule_id": "LX0609-001", "is_confirmed_issue": True}],
    )
    _assert_rejected(env, service.ModernAppealConflict, env.create)


def test_latest_switch_after_first_locked_read_is_rejected_without_writes(env):
    original = env.workspace.build_latest_single_record_result_dto

    def resolve_then_publish_new(**identity):
        result = original(**identity)
        env.workspace.results[CASE_A] = _ready(
            CASE_A, "job-new", "envelope-new",
            [{"rule_id": "LX0609-099", "is_confirmed_issue": True}],
        )
        return result

    env.workspace.build_latest_single_record_result_dto = resolve_then_publish_new
    _assert_rejected(env, service.ModernAppealConflict, env.create)


def test_duplicate_open_appeal_is_rejected(env):
    env.create()
    with pytest.raises(service.ModernAppealConflict, match="未完结"):
        env.create()
    assert len(env.appeal_rows()) == 1
    env.manual()
    with pytest.raises(service.ModernAppealConflict, match="未完结"):
        env.manual()
    assert len(env.appeal_rows()) == 2


def test_database_unique_race_is_mapped_to_duplicate_conflict(env, monkeypatch):
    env.create()
    monkeypatch.setattr(service, "_open_duplicate_exists", lambda *_args: False)
    with pytest.raises(service.ModernAppealConflict, match="未完结"):
        env.create()
    assert len(env.appeal_rows()) == 1


def test_non_duplicate_integrity_failure_is_unavailable_and_writes_nothing(env):
    def failing_session_factory():
        session = env.sessions()
        execute = session.execute

        def fail_appeal_insert(statement, *args, **kwargs):
            if isinstance(statement, sa.sql.dml.Insert) and statement.table.name == "qc_appeals":
                raise sa.exc.IntegrityError(
                    "insert", {}, RuntimeError("CHECK constraint failed: source contract"),
                )
            return execute(statement, *args, **kwargs)

        session.execute = fail_appeal_insert
        return session

    with pytest.raises(service.ModernAppealUnavailable, match="暂不可用"):
        env.create(_session_factory=failing_session_factory)
    assert env.appeal_rows() == []


def test_canonical_source_lock_uses_stable_sorted_case_keys():
    calls = []

    class Dialect:
        name = "postgresql"

    class Bind:
        dialect = Dialect()

    class Session:
        def get_bind(self):
            return Bind()

        def execute(self, statement, params):
            calls.append((str(statement), params))

    first = CaseRef("hospital-b", "patient-2", "visit-2")
    second = CaseRef("hospital-a", "patient-1", "visit-1")
    lock_case_result_mutations(
        Session(), [first, second, first], rule_set_key=LUXIAN_0609_RULE_SET_KEY,
    )

    assert [params["key"] for _, params in calls] == [
        "qc_canonical_case|hospital-a|patient-1|visit-1|luxian_0609_qc_v1",
        "qc_canonical_case|hospital-b|patient-2|visit-2|luxian_0609_qc_v1",
    ]
    assert all("pg_advisory_xact_lock" in statement for statement, _ in calls)


def test_appeal_create_and_canonical_writer_use_the_same_case_lock_key(env, monkeypatch):
    appeal_locks = []
    writer_locks = []
    expected_ref = CaseRef(*CASE_A)

    monkeypatch.setattr(
        service,
        "lock_case_result_mutations",
        lambda _session, refs, *, rule_set_key: appeal_locks.append(
            (tuple(refs), rule_set_key)
        ),
    )
    env.create()

    metadata = sa.MetaData()
    table = sa.Table(
        "record_result_envelopes",
        metadata,
        sa.Column("id", sa.String),
        sa.Column("job_id", sa.String),
        sa.Column("root_job_id", sa.String),
        sa.Column("created_by", sa.String),
        sa.Column("record_id", sa.String),
        sa.Column("institute_id", sa.String),
        sa.Column("patient_id", sa.String),
        sa.Column("visit_id", sa.String),
        sa.Column("rule_set_key", sa.String),
        sa.Column("rule_set_version", sa.String),
        sa.Column("envelope_json", sa.Text),
        sa.Column("result_count", sa.Integer),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )

    class WriterSession:
        def execute(self, _statement):
            return None

    monkeypatch.setattr(
        canonical_store,
        "lock_case_result_mutations",
        lambda _session, refs, *, rule_set_key: writer_locks.append(
            (tuple(refs), rule_set_key)
        ),
    )
    monkeypatch.setattr(
        canonical_store, "canonical_envelope_items_are_consistent", lambda _items: True,
    )
    monkeypatch.setattr(
        canonical_store, "validated_customer_explanation", lambda *_args, **_kwargs: None,
    )
    store = canonical_store.CanonicalResultStore(table)
    store.replace_for_job(
        WriterSession(),
        job_row={
            "id": JOB_A,
            "created_by": "qc-1",
            "filters_json": json.dumps({
                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                "rule_set_version": RULE_SET_VERSION,
                "record_refs": [dict(zip(
                    ("institute_id", "patient_id", "visit_id"), CASE_A,
                ))],
                "scoped_customer_rule_ids": ["LX0609-001"],
            }),
        },
        items=[{
            "institute_id": CASE_A[0], "patient_id": CASE_A[1], "visit_id": CASE_A[2],
            "rule_id": "LX0609-001", "status": "non_compliant",
            "result_status": "non_compliant", "is_compliant": False,
        }],
        now=datetime(2026, 9, 30),
        projector=dict,
        projection_key="synthetic-test-key",
    )

    expected = [((expected_ref,), LUXIAN_0609_RULE_SET_KEY)]
    assert appeal_locks == expected
    assert writer_locks == expected


def test_partial_unique_index_blocks_concurrent_duplicate_at_database(env):
    """即使绕过事务内检查，数据库部分唯一索引也拒绝同目标第二条未完结申诉。"""
    env.create()
    row = env.appeal_rows()[0]
    duplicate = {**row, "id": "other-id", "appeal_number": None}
    with pytest.raises(sa.exc.IntegrityError):
        with env.sessions.begin() as session:
            session.execute(QCAppeal.__table__.insert().values(**duplicate))
    closed = {**duplicate, "status": "approved"}
    with env.sessions.begin() as session:
        session.execute(QCAppeal.__table__.insert().values(**closed))

    # 同一病例、规则和申诉人对新一轮冻结结果可以另开一条申诉。
    next_result = {
        **duplicate, "id": "next-result", "root_job_id": "job-next",
        "envelope_id": "envelope-next",
    }
    with env.sessions.begin() as session:
        session.execute(QCAppeal.__table__.insert().values(**next_result))


def test_check_constraint_forbids_half_modern_rows_and_legacy_keys_on_modern_rows(env):
    env.create()
    row = env.appeal_rows()[0]
    for broken in (
        {"scene": None}, {"case_department": None}, {"qc_result_id": "legacy"},
        {"scene": "all"}, {"target_kind": "score"},
    ):
        with pytest.raises(sa.exc.IntegrityError):
            with env.sessions.begin() as session:
                session.execute(QCAppeal.__table__.insert().values(
                    **{**row, "id": "x", "status": "approved", **broken}
                ))
    with pytest.raises(sa.exc.IntegrityError):
        with env.sessions.begin() as session:
            session.execute(QCAppeal.__table__.insert().values(
                id="legacy-missing", appeal_type="defect", reason=REASON,
                priority="medium", appellant_id="d", appellant_name="d", status="pending",
                created_at=datetime(2026, 9, 1), updated_at=datetime(2026, 9, 1),
            ))


@pytest.mark.parametrize("overrides,error", [
    ({"scene": "all"}, service.ModernAppealInvalid),
    ({"reason": "太短"}, service.ModernAppealInvalid),
    ({"patient_id": " patient-1"}, service.ModernAppealInvalid),
    ({"expected_envelope_id": None}, service.ModernAppealInvalid),
    ({"defect_id": DEFECT_ID}, service.ModernAppealInvalid),
    ({"target_kind": "score"}, service.ModernAppealInvalid),
    ({"evidence": ["not-a-dict"]}, service.ModernAppealInvalid),
])
def test_invalid_requests_write_nothing(env, overrides, error):
    _assert_rejected(env, error, lambda: env.create(**overrides))


# ---------------------------------------------------------------- 医生端候选（只读）


def test_candidates_list_confirmed_unique_rules_and_approved_manual_defects(env):
    data = service.list_modern_appeal_candidates(
        institute_id=CASE_A[0], patient_id=CASE_A[1], visit_id=CASE_A[2],
        current_user=_doctor(), workspace_factory=lambda: env.workspace,
        department_loader=env.loader, session_factory=env.sessions,
    )
    assert data["canonical"]["state"] == "ready"
    assert data["canonical"]["job_id"] == JOB_A
    assert data["canonical"]["envelope_id"] == ENVELOPE_A
    assert data["canonical"]["scene"] == "running"
    assert [item["rule_id"] for item in data["canonical"]["items"]] == ["LX0609-001"]
    assert [item["defect_id"] for item in data["manual_defects"]] == [DEFECT_ID]

    env.set_manual_status("pending")
    data = service.list_modern_appeal_candidates(
        institute_id=CASE_A[0], patient_id=CASE_A[1], visit_id=CASE_A[2],
        current_user=_doctor(), workspace_factory=lambda: env.workspace,
        department_loader=env.loader, session_factory=env.sessions,
    )
    assert data["manual_defects"] == []


def test_candidates_map_only_explicit_not_found_to_no_result(env):
    env.workspace.results[CASE_A] = {"state": "not_found", "items": []}
    data = service.list_modern_appeal_candidates(
        institute_id=CASE_A[0], patient_id=CASE_A[1], visit_id=CASE_A[2],
        current_user=_doctor(), workspace_factory=lambda: env.workspace,
        department_loader=env.loader, session_factory=env.sessions,
    )
    assert data["canonical"] == {"state": "no_result", "items": []}


@pytest.mark.parametrize("dto", [
    None,
    [],
    {},
    {"state": "technical_error", "items": []},
    {"state": "unavailable", "items": []},
    {"state": "unknown_future_state", "items": []},
    {"state": 1, "items": []},
])
def test_candidates_map_error_unknown_and_malformed_dto_to_unavailable(env, dto):
    env.workspace.results[CASE_A] = dto
    data = service.list_modern_appeal_candidates(
        institute_id=CASE_A[0], patient_id=CASE_A[1], visit_id=CASE_A[2],
        current_user=_doctor(), workspace_factory=lambda: env.workspace,
        department_loader=env.loader, session_factory=env.sessions,
    )
    assert data["canonical"] == {"state": "unavailable", "items": []}


def test_candidates_are_forbidden_outside_own_department(env):
    with pytest.raises(service.ModernAppealForbidden):
        service.list_modern_appeal_candidates(
            institute_id=CASE_A[0], patient_id=CASE_A[1], visit_id=CASE_A[2],
            current_user=_doctor(OTHER_DEPT), workspace_factory=lambda: env.workspace,
            department_loader=env.loader, session_factory=env.sessions,
        )
    assert env.workspace.calls == []


# ---------------------------------------------------------------- 路由错误合同


@pytest.mark.parametrize("error,status", [
    (service.ModernAppealInvalid("x"), 422),
    (service.ModernAppealForbidden("x"), 403),
    (service.ModernAppealNotFound("x"), 404),
    (service.ModernAppealConflict("x"), 409),
    (service.ModernAppealUnavailable("private"), 503),
    (RuntimeError("private"), 503),
])
def test_route_maps_service_errors(monkeypatch, error, status):
    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(service, "create_modern_appeal", fail)
    app = FastAPI()
    app.include_router(appeals_router.router)
    app.dependency_overrides[get_current_user] = lambda: _doctor()
    response = TestClient(app).post("/api/v1/appeals/modern", json={
        "target_kind": "task_manual_defect", "institute_id": CASE_A[0],
        "patient_id": CASE_A[1], "visit_id": CASE_A[2], "scene": "running",
        "defect_id": DEFECT_ID, "reason": REASON,
    })
    assert response.status_code == status
    assert "private" not in response.text
