"""任务模板服务合同：私有 owner、严格配置、CAS 与事务回读。"""

from __future__ import annotations

import json

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTaskTemplate
from app.services import task_template_service as service


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCTaskTemplate.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def config(**changes):
    value = {
        "scene": "final",
        "rule_set_key": "sc_content_fast_v1",
        "date_range": {"start": "2026-09-01", "end": "2026-09-27"},
        "department_filter": ["内科"],
        "sampling_method": "count",
        "sampling_config": {"total": 20, "by_department": True},
        "assign_method": "by_ratio",
        "assignee_config": {},
    }
    value.update(changes)
    return value


def create(name="常用", owner="u-1", **changes):
    return service.create_task_template(
        owner_id=owner, name=name, config=config(**changes),
    )


def row_count(factory):
    with factory() as session:
        return session.execute(sa.select(sa.func.count(QCTaskTemplate.id))).scalar_one()


def test_create_list_update_delete_with_owner_and_cas(sessions):
    item = create()
    assert item["usable"] is True and item["version"] == 1
    assert "owner_id" not in item and item["config"] == config()
    assert [entry["id"] for entry in service.list_task_templates(owner_id="u-1")["items"]] == [item["id"]]
    assert service.list_task_templates(owner_id="u-2")["items"] == []

    with pytest.raises(service.TaskTemplateNotFound):
        service.update_task_template(
            owner_id="u-2", template_id=item["id"], version=1, name="偷改",
        )
    updated = service.update_task_template(
        owner_id="u-1", template_id=item["id"], version=1, name="改名",
    )
    assert updated["name"] == "改名" and updated["version"] == 2
    with pytest.raises(service.TaskTemplateConflict) as stale:
        service.delete_task_template(owner_id="u-1", template_id=item["id"], version=1)
    assert stale.value.code == "version_conflict"
    assert service.delete_task_template(
        owner_id="u-1", template_id=item["id"], version=2,
    ) == {"id": item["id"], "deleted": True}


@pytest.mark.parametrize("extra", [
    {"task_name": "不得保存"},
    {"deadline": "2026-10-01"},
    {"record_refs": [{"institute_id": "i", "patient_id": "p", "visit_id": "v"}]},
    {"assignee_config": {"user_ids": ["u-1"]}},
    {"assign_method": "by_original_reviewer", "assignee_config": {}},
    {"rule_set_key": "missing"},
    {"scene": "outpatient", "rule_set_key": "sc_content_fast_v1"},
])
def test_rejects_dynamic_identity_or_unavailable_config(sessions, extra):
    payload = config()
    payload.update(extra)
    with pytest.raises(service.TaskTemplateInvalid):
        service.create_task_template(owner_id="u-1", name="x", config=payload)
    assert row_count(sessions) == 0


def test_name_limit_and_bad_stored_config(sessions):
    create("甲")
    with pytest.raises(service.TaskTemplateConflict) as duplicate:
        create("甲")
    assert duplicate.value.code == "name_conflict"
    for index in range(1, service.MAX_TEMPLATES_PER_USER):
        create(f"模板{index}")
    with pytest.raises(service.TaskTemplateConflict) as over:
        create("第21个")
    assert over.value.code == "template_limit"

    table = QCTaskTemplate.__table__
    with sessions.begin() as session:
        session.execute(
            table.update().where(table.c.name == "甲").values(
                config_json=json.dumps({"scene": "final", "task_name": "越界"}),
            )
        )
    damaged = next(item for item in service.list_task_templates(owner_id="u-1")["items"] if item["name"] == "甲")
    assert damaged["config"] is None and damaged["usable"] is False
    assert damaged["unavailable_reason"]


def test_readback_failure_rolls_back_create_and_update(sessions, monkeypatch):
    original_read = service._read_one
    monkeypatch.setattr(service, "_read_one", lambda *_args: None)
    with pytest.raises(service.TaskTemplateUnavailable):
        create()
    assert row_count(sessions) == 0

    monkeypatch.setattr(service, "_read_one", original_read)
    item = create()
    monkeypatch.setattr(service, "_read_one", lambda *_args: None)
    with pytest.raises(service.TaskTemplateUnavailable):
        service.update_task_template(
            owner_id="u-1", template_id=item["id"], version=1, name="不应提交",
        )
    monkeypatch.setattr(service, "_read_one", original_read)
    listed = service.list_task_templates(owner_id="u-1")["items"]
    assert listed[0]["name"] == "常用" and listed[0]["version"] == 1
