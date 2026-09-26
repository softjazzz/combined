"""用户筛选模板服务：本人范围、白名单校验、上限、默认唯一、CAS（SQLite 合成数据）。"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCUserFilterTemplate
from app.services import filter_template_service as service

INPATIENT = "v5_records_inpatient"
DISCHARGED = "v5_records_discharged"


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCUserFilterTemplate.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def _create(name="模板", *, owner="u-1", page_key=INPATIENT, filters=None, is_default=False):
    return service.create_template(
        owner_id=owner, page_key=page_key, name=name,
        filters=filters if filters is not None else {"dept": "内科"}, is_default=is_default,
    )


def _rows(factory):
    table = QCUserFilterTemplate.__table__
    with factory() as session:
        return {
            row.id: row
            for row in session.execute(sa.select(table)).all()
        }


def test_create_and_list_sorted_default_first_then_name(sessions):
    _create("乙")
    default = _create("甲", is_default=True)
    _create("丙")
    _create("别页", page_key=DISCHARGED)
    _create("他人", owner="u-2")
    result = service.list_templates(owner_id="u-1", page_key=INPATIENT)
    names = [item["name"] for item in result["items"]]
    assert names[0] == "甲" and sorted(names[1:]) == names[1:] and set(names) == {"甲", "乙", "丙"}
    assert result["max_per_page"] == 20 and result["page_key"] == INPATIENT
    assert default["version"] == 1 and default["is_default"] is True
    assert set(default) == {
        "id", "page_key", "name", "filters", "is_default", "version", "created_at", "updated_at",
    }


def test_create_normalizes_filters_and_name(sessions):
    item = _create("  常用  ", filters={
        "dept": " 内科 ", "doctor": "", "keyword": None, "start_date": "2026-09-01",
        "end_date": "2026-09-27", "date_field": "discharge", "inpatient_sort": "longest",
        "review_state": ["pending_review", "pending_recheck", "pending_review"],
    })
    assert item["name"] == "常用"
    assert item["filters"] == {
        "dept": "内科", "start_date": "2026-09-01", "end_date": "2026-09-27",
        "date_field": "discharge", "inpatient_sort": "longest",
        "review_state": ["pending_review", "pending_recheck"],
    }


@pytest.mark.parametrize("filters", [
    {"page": 2},
    {"page_size": 50},
    {"hospital_status": "all"},
    {"dept": 1},
    {"keyword": "x" * 101},
    {"start_date": "2026/09/01"},
    {"start_date": "2026-02-30"},
    {"end_date": "2026-09-01T00:00:00"},
    {"start_date": "2026-09-02", "end_date": "2026-09-01"},
    {"date_field": "created"},
    {"inpatient_sort": "oldest"},
    {"review_state": "pending_review"},
    {"review_state": ["pending_review", "rejected"]},
    {"review_state": [1]},
    [],
])
def test_create_rejects_invalid_filters(sessions, filters):
    with pytest.raises(service.FilterTemplateInvalid):
        service.create_template(owner_id="u-1", page_key=INPATIENT, name="x", filters=filters)
    assert _rows(sessions) == {}


@pytest.mark.parametrize("kwargs", [
    {"page_key": "v5_records_outpatient"},
    {"name": "   "},
    {"name": "长" * 51},
    {"owner_id": " "},
    {"owner_id": "u" * 65},
    {"is_default": "true"},
])
def test_create_rejects_invalid_arguments(sessions, kwargs):
    params = {"owner_id": "u-1", "page_key": INPATIENT, "name": "x", "filters": {}, **kwargs}
    with pytest.raises(service.FilterTemplateInvalid):
        service.create_template(**params)


def test_duplicate_name_conflict_scoped_to_owner_and_page(sessions):
    _create("常用")
    with pytest.raises(service.FilterTemplateConflict) as caught:
        _create(" 常用 ")
    assert caught.value.code == "name_conflict"
    _create("常用", page_key=DISCHARGED)
    _create("常用", owner="u-2")


def test_limit_reached_per_owner_and_page(sessions):
    for index in range(service.MAX_TEMPLATES_PER_PAGE):
        _create(f"模板{index:02d}")
    with pytest.raises(service.FilterTemplateConflict) as caught:
        _create("第21个")
    assert caught.value.code == "limit_reached"
    _create("别页不受影响", page_key=DISCHARGED)
    _create("他人不受影响", owner="u-2")


def test_setting_default_clears_previous_default_in_same_page_and_bumps_version(sessions):
    first = _create("甲", is_default=True)
    other_page = _create("别页", page_key=DISCHARGED, is_default=True)
    other_owner = _create("他人", owner="u-2", is_default=True)
    second = _create("乙", is_default=True)
    rows = _rows(sessions)
    assert rows[first["id"]].is_default is False and rows[first["id"]].version == 2
    assert rows[second["id"]].is_default is True and rows[second["id"]].version == 1
    assert rows[other_page["id"]].is_default is True
    assert rows[other_owner["id"]].is_default is True

    # 更新方式设默认：清除乙
    updated = service.update_template(
        owner_id="u-1", template_id=first["id"], version=2, is_default=True,
    )
    assert updated["is_default"] is True and updated["version"] == 3
    rows = _rows(sessions)
    assert rows[second["id"]].is_default is False and rows[second["id"]].version == 2


def test_update_cas_and_fields(sessions):
    item = _create("甲")
    updated = service.update_template(
        owner_id="u-1", template_id=item["id"], version=1,
        name="甲改", filters={"review_state": ["approved"]},
    )
    assert updated["name"] == "甲改" and updated["filters"] == {"review_state": ["approved"]}
    assert updated["version"] == 2
    with pytest.raises(service.FilterTemplateConflict) as caught:
        service.update_template(owner_id="u-1", template_id=item["id"], version=1, name="再改")
    assert caught.value.code == "version_conflict"
    assert _rows(sessions)[item["id"]].name == "甲改"


def test_update_name_conflict_and_self_rename_allowed(sessions):
    a = _create("甲")
    _create("乙")
    with pytest.raises(service.FilterTemplateConflict) as caught:
        service.update_template(owner_id="u-1", template_id=a["id"], version=1, name="乙")
    assert caught.value.code == "name_conflict"
    same = service.update_template(owner_id="u-1", template_id=a["id"], version=1, name="甲")
    assert same["version"] == 2


def test_update_requires_changes_and_valid_version(sessions):
    item = _create("甲")
    with pytest.raises(service.FilterTemplateInvalid):
        service.update_template(owner_id="u-1", template_id=item["id"], version=1)
    with pytest.raises(service.FilterTemplateInvalid):
        service.update_template(owner_id="u-1", template_id=item["id"], version=0, name="x")
    with pytest.raises(service.FilterTemplateInvalid):
        service.update_template(owner_id="u-1", template_id=item["id"], version=1, filters={"x": 1})


def test_other_owner_template_is_not_found_for_all_operations(sessions):
    item = _create("甲")
    with pytest.raises(service.FilterTemplateNotFound):
        service.update_template(owner_id="u-2", template_id=item["id"], version=1, name="偷改")
    with pytest.raises(service.FilterTemplateNotFound):
        service.delete_template(owner_id="u-2", template_id=item["id"], version=1)
    assert service.list_templates(owner_id="u-2", page_key=INPATIENT)["items"] == []
    assert _rows(sessions)[item["id"]].name == "甲"
    with pytest.raises(service.FilterTemplateNotFound):
        service.update_template(owner_id="u-1", template_id="x" * 37, version=1, name="y")


def test_delete_cas(sessions):
    item = _create("甲")
    service.update_template(owner_id="u-1", template_id=item["id"], version=1, name="乙")
    with pytest.raises(service.FilterTemplateConflict) as caught:
        service.delete_template(owner_id="u-1", template_id=item["id"], version=1)
    assert caught.value.code == "version_conflict"
    assert service.delete_template(owner_id="u-1", template_id=item["id"], version=2) == {
        "id": item["id"], "deleted": True,
    }
    assert _rows(sessions) == {}
    with pytest.raises(service.FilterTemplateNotFound):
        service.delete_template(owner_id="u-1", template_id=item["id"], version=2)


def test_corrupted_stored_filters_are_reported_as_none(sessions):
    item = _create("甲")
    table = QCUserFilterTemplate.__table__
    with sessions.begin() as session:
        session.execute(table.update().where(table.c.id == item["id"]).values(filters_json='{"page": 3}'))
    listed = service.list_templates(owner_id="u-1", page_key=INPATIENT)["items"]
    assert listed[0]["filters"] is None


def test_lock_statement_skipped_on_sqlite_and_issued_on_postgres(sessions):
    class FakeSession:
        def __init__(self, dialect):
            self.dialect = dialect
            self.statements = []

        def get_bind(self):
            return type("Bind", (), {"dialect": type("D", (), {"name": self.dialect})()})()

        def execute(self, statement, params=None):
            self.statements.append((str(statement), params))

    sqlite_session = FakeSession("sqlite")
    service._lock_owner_page(sqlite_session, "u-1", INPATIENT)
    assert sqlite_session.statements == []
    pg_session = FakeSession("postgresql")
    service._lock_owner_page(pg_session, "u-1", INPATIENT)
    assert pg_session.statements == [(
        "SELECT pg_advisory_xact_lock(hashtext(:key))",
        {"key": "qc_user_filter_templates:u-1:v5_records_inpatient"},
    )]


def test_database_failure_raises_unavailable(monkeypatch):
    def broken():
        raise OperationalError("SELECT secret", {}, Exception("down"))

    monkeypatch.setattr(service, "SessionLocal", broken)
    with pytest.raises(service.FilterTemplateUnavailable):
        service.list_templates(owner_id="u-1", page_key=INPATIENT)
    with pytest.raises(service.FilterTemplateUnavailable):
        _create("甲")
    monkeypatch.setattr(service, "SessionLocal", None)
    with pytest.raises(service.FilterTemplateUnavailable):
        service.list_templates(owner_id="u-1", page_key=INPATIENT)
