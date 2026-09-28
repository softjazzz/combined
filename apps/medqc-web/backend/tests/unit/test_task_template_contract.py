"""任务模板独立合同：用户隔离、CAS、失效快照与写后回读原子性。"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTaskTemplate
from app.services import task_template_service as service


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    QCTaskTemplate.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def _config(**changes):
    config = {
        "scene": "final",
        "rule_set_key": "sc_content_full_v1",
        "date_range": {"start": "2026-09-01", "end": "2026-09-27"},
        "department_filter": ["内科"],
        "sampling_method": "count",
        "sampling_config": {"total": 20, "by_department": True},
        "assign_method": "by_ratio",
        "assignee_config": {},
    }
    config.update(changes)
    return config


def _create(*, owner="user-a", name="常用终末任务"):
    return service.create_task_template(owner_id=owner, name=name, config=_config())


def _stored_rows(factory):
    with factory() as session:
        return session.execute(
            sa.select(QCTaskTemplate.__table__).order_by(QCTaskTemplate.id)
        ).mappings().all()


def test_cross_owner_is_indistinguishable_from_missing(sessions):
    created = _create(owner="user-a")

    assert service.list_task_templates(owner_id="user-b")["items"] == []
    with pytest.raises(service.TaskTemplateNotFound):
        service.update_task_template(
            owner_id="user-b",
            template_id=created["id"],
            version=created["version"],
            name="越权改名",
        )
    with pytest.raises(service.TaskTemplateNotFound):
        service.delete_task_template(
            owner_id="user-b",
            template_id=created["id"],
            version=created["version"],
        )

    remaining = service.list_task_templates(owner_id="user-a")["items"]
    assert [(item["id"], item["name"], item["version"]) for item in remaining] == [
        (created["id"], "常用终末任务", 1),
    ]


def test_update_and_delete_require_current_version(sessions):
    created = _create()
    updated = service.update_task_template(
        owner_id="user-a",
        template_id=created["id"],
        version=1,
        name="已更新模板",
    )
    assert updated["version"] == 2

    with pytest.raises(service.TaskTemplateConflict) as stale_update:
        service.update_task_template(
            owner_id="user-a",
            template_id=created["id"],
            version=1,
            name="过时覆盖",
        )
    assert stale_update.value.code == "version_conflict"

    with pytest.raises(service.TaskTemplateConflict) as stale_delete:
        service.delete_task_template(
            owner_id="user-a",
            template_id=created["id"],
            version=1,
        )
    assert stale_delete.value.code == "version_conflict"
    assert service.list_task_templates(owner_id="user-a")["items"][0]["name"] == "已更新模板"

    assert service.delete_task_template(
        owner_id="user-a", template_id=created["id"], version=2,
    ) == {"id": created["id"], "deleted": True}


def test_rule_set_becoming_unavailable_disables_stored_snapshot(sessions, monkeypatch):
    created = _create()
    monkeypatch.setattr(service, "get_sichuan_rule_set", lambda _key: None)

    listed = service.list_task_templates(owner_id="user-a")["items"]
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]
    assert listed[0]["usable"] is False
    assert listed[0]["config"] is None
    assert listed[0]["unavailable_reason"]

    with pytest.raises(service.TaskTemplateInvalid):
        service.create_task_template(owner_id="user-a", name="过时规则模板", config=_config())
    assert len(_stored_rows(sessions)) == 1


@pytest.mark.parametrize(
    "illegal_fragment",
    [
        {"task_name": "不能冻结任务名称"},
        {"deadline": "2026-10-01T00:00:00+08:00"},
        {"record_refs": [{"institute_id": "i", "patient_id": "p", "visit_id": "v"}]},
        {"record_ids": ["legacy-record-id"]},
        {"assignees": [{"user_id": "qc-1", "user_name": "质控员"}]},
        {"sampling_config": {"total": 20, "unexpected": True}},
        {"assign_method": "by_record_type"},
    ],
)
def test_illegal_or_dynamic_snapshot_fields_are_rejected(sessions, illegal_fragment):
    with pytest.raises(service.TaskTemplateInvalid):
        service.create_task_template(
            owner_id="user-a",
            name="非法快照",
            config=_config(**illegal_fragment),
        )
    assert _stored_rows(sessions) == []


def test_create_readback_failure_rolls_back_insert(sessions, monkeypatch):
    monkeypatch.setattr(service, "_read_one", lambda *_args, **_kwargs: None)

    with pytest.raises(service.TaskTemplateUnavailable):
        _create()

    assert _stored_rows(sessions) == []


def test_update_readback_failure_rolls_back_values_and_version(sessions, monkeypatch):
    created = _create()
    monkeypatch.setattr(service, "_read_one", lambda *_args, **_kwargs: None)

    with pytest.raises(service.TaskTemplateUnavailable):
        service.update_task_template(
            owner_id="user-a",
            template_id=created["id"],
            version=1,
            name="不应提交的名称",
        )

    rows = _stored_rows(sessions)
    assert len(rows) == 1
    assert rows[0]["name"] == "常用终末任务"
    assert rows[0]["version"] == 1
