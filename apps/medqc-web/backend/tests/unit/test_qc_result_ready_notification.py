"""真实保存事务、结果通知归属、重复刷新和重试失效回归。"""

import json
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.services import custom_qc_workspace_service as workspace_module
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.doctor_notification_service import (
    DoctorNotificationService,
    Notification,
)
from app.services.defect_rectification_service import RectificationError
from app.database.models.v36_reports import SysUser, DefectRectification, QCAppeal
from app.services.luxian_0609.basic_timeliness_customer_projection import (
    safe_basic_timeliness_customer_display_facts,
)
from app.services.qc_result_ready_notification import SOURCE

pytestmark = pytest.mark.usefixtures("workspace_tables_without_database")


def legal_item():
    return {
        "record_id": "V",
        "visit_id": "V",
        "institute_id": "I",
        "patient_id": "P",
        "schema_version": "lx0609-customer-result-v2",
        "rule_id": "LX0609-01-01-01",
        "status": "compliant",
        "result_status": "compliant",
        "display_status": "compliant",
        "is_compliant": True,
        "reason_code": "requirement_satisfied",
        "conclusion": "已核对",
        "customer_display_facts": safe_basic_timeliness_customer_display_facts(
            rule_id="LX0609-01-01-01",
            raw={
                "failure_kind": "timeliness_requirement_satisfied",
                "target_document": "admission_record",
                "source_label": "入院记录",
                "timeliness_state": "within",
                "threshold_hours": 24,
                "elapsed_hours": 1.0,
            },
        ),
    }


@pytest.fixture
def storage(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", execution_options={"schema_translate_map": {"qc": None}}
    )
    monkeypatch.setattr(workspace_module, "engine", engine)
    monkeypatch.setattr(workspace_module, "_draft_schema", lambda: None)
    service = CustomQCWorkspaceService(readonly=True)
    service._batch_job_table = service._batch_job_table.to_metadata(
        sa.MetaData(), schema=None
    )
    service._record_result_envelope_table = (
        service._record_result_envelope_table.to_metadata(sa.MetaData(), schema=None)
    )
    for table in (
        service._batch_job_table,
        service._record_result_envelope_table,
        SysUser.__table__,
        Notification.__table__,
        DefectRectification.__table__,
        QCAppeal.__table__,
    ):
        table.create(engine)
    sessions = sessionmaker(engine)
    monkeypatch.setattr(workspace_module, "_session", sessions)
    with sessions.begin() as session:
        for name, role, institution in (
            ("owner", "qc_manager", "I"),
            ("other", "qc_manager", "I"),
            ("doc", "doctor", "I"),
        ):
            session.add(
                SysUser(
                    id=name,
                    username=name,
                    display_name=name,
                    role=role,
                    roles_json=json.dumps([role]),
                    institute_id=institution,
                    department="合成科室",
                    is_active=True,
                )
            )
    yield service, sessions, DoctorNotificationService(sessions)
    engine.dispose()


def insert_job(storage, *, scene="running", job_id="J", **changes):
    service, sessions, _ = storage
    row = dict(
        id=job_id,
        draft_id="sichuan-rule-library",
        created_by="owner",
        scene=scene,
        status="queued",
        rule_code="LX0609",
        rule_name="合成结果通知",
        scope=scene,
        job_kind="leaf",
        total_records=1,
        created_at=datetime(2026, 10, 25),
        updated_at=datetime(2026, 10, 25),
        filters_json=json.dumps(
            {
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_set_version": "2026-06-09",
                "rule_ids": ["LX0609-01-01-01"],
                "record_refs": [
                    {"institute_id": "I", "patient_id": "P", "visit_id": "V"}
                ],
            }
        ),
    )
    row.update(changes)
    with sessions.begin() as session:
        session.execute(service._batch_job_table.insert().values(**row))


def complete(storage, job_id="J", **changes):
    service, _, _ = storage
    attempt = service.mark_batch_job_running(job_id=job_id)
    assert isinstance(attempt, str)
    kwargs = dict(
        summary={
            "execution_status": "completed",
            "total_records": 1,
            "success_count": 1,
        },
        items=[legal_item()],
        failed_records=[],
    )
    kwargs.update(changes)
    assert (
        service.complete_batch_job(
            job_id=job_id, attempt_filters_json=attempt, **kwargs
        )
        is True
    )
    return attempt


@pytest.mark.parametrize("scene", ["running", "final"])
def test_saved_completion_notifies_only_persistent_requester_and_exact_result(
    storage, scene
):
    service, sessions, notifications = storage
    insert_job(storage, scene=scene)
    complete(storage)
    page = notifications.list("owner")
    assert page["total"] == page["unread_count"] == 1
    item = page["items"][0]
    assert (
        item["title"]
        == {"running": "运行质控结果已就绪", "final": "终末质控结果已就绪"}[scene]
    )
    assert item["source_key"] == SOURCE
    assert item["interaction_target"] == {"kind": "qc_result_ready", "id": item["id"]}
    assert (
        notifications.list("other")["total"] == notifications.list("doc")["total"] == 0
    )
    assert notifications.result_ready(
        "owner", item["id"], lambda job, actor: (job, actor)
    ) == ("J", "owner")
    with pytest.raises(RectificationError):
        notifications.result_ready(
            "other", item["id"], lambda *_: pytest.fail("越权调用读取")
        )
    notifications.mark_read("owner", item["id"])
    assert notifications.list("owner")["unread_count"] == 0
    with sessions() as session:
        assert (
            session.scalar(sa.select(service._batch_job_table.c.status)) == "completed"
        )


def test_persistent_sync_admin_can_read_own_cross_institute_result_notice(storage):
    _, sessions, notifications = storage
    with sessions.begin() as session:
        owner = session.get(SysUser, "owner")
        owner.role = "sync_admin"
        owner.roles_json = '["sync_admin"]'
        owner.institute_id = "another-institute"
    insert_job(storage)
    complete(storage)
    page = notifications.list("owner")
    assert page["total"] == page["unread_count"] == 1
    item = page["items"][0]
    assert notifications.result_ready("owner", item["id"], lambda job, actor: (job, actor)) == ("J", "owner")
    assert notifications.list("other")["total"] == 0
    notifications.mark_read("owner", item["id"])
    assert notifications.list("owner")["unread_count"] == 0


def test_parent_child_and_repeated_refresh_have_one_notice_and_preserve_read(storage):
    service, sessions, notifications = storage
    insert_job(storage, job_id="parent", job_kind="parent", child_job_ids_json='["J"]')
    insert_job(storage, parent_job_id="parent")
    complete(storage)
    item = notifications.list("owner")["items"][0]
    assert item["record_id"] == "parent"
    notifications.mark_read("owner", item["id"])
    service.refresh_parent_batch_job(parent_job_id="parent")
    page = notifications.list("owner")
    assert page["total"] == 1 and page["unread_count"] == 0
    assert page["items"][0]["id"] == item["id"]
    assert (
        notifications.result_ready("owner", item["id"], lambda job, _: job) == "parent"
    )
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(Notification)) == 1


def test_retry_invalidates_old_notice_without_retargeting_new_round(storage):
    service, sessions, notifications = storage
    insert_job(storage)
    stale = complete(storage)
    old = notifications.list("owner")["items"][0]["id"]
    assert service.retry_batch_job(job_id="J", created_by="owner")
    assert notifications.list("owner")["total"] == 0
    with pytest.raises(RectificationError):
        notifications.result_ready(
            "owner", old, lambda *_: pytest.fail("旧轮结果被替换")
        )
    assert (
        service.complete_batch_job(
            job_id="J",
            attempt_filters_json=stale,
            summary={"total_records": 1},
            items=[legal_item()],
            failed_records=[],
        )
        is False
    )
    complete(storage)
    page = notifications.list("owner")
    assert page["total"] == 1 and page["items"][0]["id"] != old
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(Notification)) == 2
    with pytest.raises(RectificationError):
        notifications.mark_read("owner", old)


@pytest.mark.parametrize(
    "mode",
    [
        "zero",
        "failed",
        "partial_failed",
        "canceled",
        "invalid",
        "no_persist",
        "inactive",
        "doctor",
        "cross_institute",
    ],
)
def test_no_false_ready_notice(storage, mode):
    service, sessions, notifications = storage
    insert_job(storage)
    if mode in {"inactive", "doctor", "cross_institute"}:
        with sessions.begin() as session:
            user = session.get(SysUser, "owner")
            if mode == "inactive":
                user.is_active = False
            if mode == "doctor":
                user.role, user.roles_json = "doctor", '["doctor"]'
            if mode == "cross_institute":
                user.institute_id = "OTHER"
        complete(storage)
    elif mode == "canceled":
        attempt = service.mark_batch_job_running(job_id="J")
        service.cancel_batch_job(job_id="J", created_by="owner")
        assert (
            service.complete_batch_job(
                job_id="J",
                attempt_filters_json=attempt,
                summary={"total_records": 1},
                items=[legal_item()],
                failed_records=[],
            )
            is False
        )
    elif mode == "invalid":
        bad = legal_item()
        bad["patient_id"] = ""
        with pytest.raises(ValueError):
            complete(storage, items=[bad])
    elif mode in {"failed", "partial_failed"}:
        partial = mode == "partial_failed"
        complete(
            storage,
            summary={
                "execution_status": mode,
                "total_records": 2 if partial else 1,
                "completed_rule_count": 1 if partial else 0,
                "failed_rule_count": 1,
            },
            items=[legal_item()] if partial else [],
            failed_records=[
                {
                    "institute_id": "I",
                    "patient_id": "P2" if partial else "P",
                    "visit_id": "V2" if partial else "V",
                    "rule_id": "LX0609-01-01-01",
                    "error_phase": "execution",
                }
            ],
        )
    else:
        complete(
            storage,
            items=[] if mode == "zero" else [legal_item()],
            persist_record_envelopes=mode != "no_persist",
        )
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(Notification)) == 0


def test_notice_write_failure_rolls_back_completion_and_saved_results(storage):
    service, sessions, _ = storage
    insert_job(storage)

    def fail(*_):
        raise RuntimeError("合成消息写入失败")

    sa.event.listen(Notification, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="合成消息写入失败"):
            complete(storage)
    finally:
        sa.event.remove(Notification, "before_insert", fail)
    with sessions() as session:
        assert session.scalar(sa.select(service._batch_job_table.c.status)) == "running"
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(
                    service._record_result_envelope_table
                )
            )
            == 0
        )


def test_frozen_coordinates_and_actual_role_are_rechecked_for_list_count_read(storage):
    _, sessions, notifications = storage
    insert_job(storage)
    complete(storage)
    id = notifications.list("owner")["items"][0]["id"]
    with sessions.begin() as session:
        session.get(Notification, id).patient_id = "FORGED"
    assert (
        notifications.list("owner")["total"]
        == notifications.list("owner")["unread_count"]
        == 0
    )
    with pytest.raises(RectificationError):
        notifications.mark_read("owner", id)
    with sessions.begin() as session:
        session.get(Notification, id).patient_id = "P"
        session.get(SysUser, "owner").roles_json = '["doctor"]'
    assert notifications.list("owner")["total"] == 0


@pytest.mark.parametrize(
    "legacy", ["no_table", "old_columns", "custom_draft", "outpatient"]
)
def test_unsupported_or_old_notification_schema_does_not_break_existing_completion(
    storage, legacy
):
    service, sessions, _ = storage
    insert_job(
        storage,
        **(
            {"draft_id": "custom-draft"}
            if legacy == "custom_draft"
            else {"scene": "outpatient"}
            if legacy == "outpatient"
            else {}
        ),
    )
    engine = sessions.kw["bind"]
    if legacy in {"no_table", "old_columns"}:
        Notification.__table__.drop(engine)
        if legacy == "old_columns":
            sa.Table(
                "notifications",
                sa.MetaData(),
                sa.Column("id", sa.String, primary_key=True),
            ).create(engine)
    complete(storage)
    with sessions() as session:
        assert (
            session.scalar(sa.select(service._batch_job_table.c.status)) == "completed"
        )
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(
                    service._record_result_envelope_table
                )
            )
            == 1
        )


def test_notification_result_reuses_formal_projection_without_runtime_ddl(monkeypatch):
    from app.routers import notifications, qc_sichuan

    seen = []

    class ReadonlyWorkspace:
        def __init__(self, *, readonly):
            assert readonly is True

        def get_batch_job(self, *, job_id, created_by):
            seen.append((job_id, created_by))
            return {
                "id": job_id,
                "draft_id": "sichuan-rule-library",
                "status": "completed",
                "filters": {"rule_set_key": "luxian_0609_qc_v1"},
            }

    monkeypatch.setattr(workspace_module, "CustomQCWorkspaceService", ReadonlyWorkspace)

    def hydrate(*, workspace, job):
        return {**job, "items": ["formal-canonical"]}

    monkeypatch.setattr(
        qc_sichuan, "_hydrate_luxian_canonical_batch_job_or_409", hydrate
    )
    monkeypatch.setattr(
        qc_sichuan,
        "_workspace_batch_response_item",
        lambda job: {**job, "projected": True},
    )
    result = notifications._load_ready_batch_result("saved-root", "persistent-owner")
    assert seen == [("saved-root", "persistent-owner")]
    assert result["items"] == ["formal-canonical"] and result["projected"] is True
