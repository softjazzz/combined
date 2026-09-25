"""现代病例只读快照的离线反例集。

全部用例只使用内存 SQLite（qc/cdm 以 ATTACH 挂载）或假 Session，
绝不连接业务库；断言身份四维隔离、NULL 排序、空结果语义与 schema/来源失败语义。
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    SmallInteger,
    String,
    Table,
    Text,
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import modern_case_qc_result_service as modern
from app.services.qc_persistence_service import VerifiedQCIdentity


IDENTITY = VerifiedQCIdentity("LX001", "patient-a", "visit-1", "settlement_qc")

_DDL = (
    "CREATE TABLE cdm.mr (institute_id TEXT, patient_id TEXT, visit_id TEXT)",
    """
    CREATE TABLE qc.qc_results (
        id TEXT PRIMARY KEY,
        identity_version INTEGER,
        source_key TEXT,
        institute_id TEXT,
        patient_id TEXT,
        visit_id TEXT,
        record_id TEXT,
        rule_set TEXT,
        overall_score REAL,
        grade TEXT,
        defect_count INTEGER,
        analysis_date DATETIME,
        raw_output TEXT,
        issues TEXT,
        metadata TEXT,
        created_by TEXT,
        created_at DATETIME,
        updated_at DATETIME
    )
    """,
    """
    CREATE TABLE qc.qc_defects (
        id TEXT PRIMARY KEY,
        result_id TEXT,
        record_id TEXT,
        identity_version INTEGER,
        source_key TEXT,
        institute_id TEXT,
        patient_id TEXT,
        visit_id TEXT,
        rule_code TEXT,
        rule_name TEXT,
        description TEXT,
        severity TEXT,
        category TEXT,
        location TEXT,
        evidence TEXT,
        suggestion TEXT,
        department TEXT,
        deduct_score REAL,
        origin TEXT,
        status TEXT,
        created_at DATETIME,
        updated_at DATETIME
    )
    """,
    """
    CREATE TABLE qc.notifications (
        id TEXT PRIMARY KEY,
        "type" TEXT,
        title TEXT,
        content TEXT,
        record_id TEXT,
        identity_version INTEGER,
        source_key TEXT,
        institute_id TEXT,
        patient_id TEXT,
        visit_id TEXT,
        recipient_id TEXT,
        sender_id TEXT,
        severity TEXT,
        related_type TEXT,
        related_id TEXT,
        is_read BOOLEAN,
        read_at DATETIME,
        created_at DATETIME
    )
    """,
)


@pytest.fixture
def store(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _attach(dbapi_connection, _record):
        dbapi_connection.execute("ATTACH DATABASE ':memory:' AS qc")
        dbapi_connection.execute("ATTACH DATABASE ':memory:' AS cdm")

    statements: list[str] = []
    calls: list[tuple[str, object]] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _capture(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)
        calls.append((statement, _parameters))

    with engine.begin() as conn:
        for ddl in _DDL:
            conn.execute(text(ddl))

    monkeypatch.setattr(modern, "engine", engine)
    modern._table.cache_clear()

    tables = {
        name: modern._table(schema, name)
        for schema, name in (
            ("cdm", "mr"),
            ("qc", "qc_results"),
            ("qc", "qc_defects"),
            ("qc", "notifications"),
        )
    }
    service = modern.ModernCaseQCResultService(
        session_factory=sessionmaker(bind=engine, autocommit=False, autoflush=False)
    )

    def insert(key, **values):
        with engine.begin() as conn:
            conn.execute(tables[key].insert().values(**values))

    yield SimpleNamespace(insert=insert, service=service, statements=statements, calls=calls)

    modern._table.cache_clear()
    engine.dispose()


def _owner(identity=IDENTITY, **overrides):
    return {**identity.columns(), **overrides}


def _case(store, institute="LX001", patient="patient-a", visit="visit-1"):
    store.insert("mr", institute_id=institute, patient_id=patient, visit_id=visit)


def _result(store, result_id, *, identity=IDENTITY, date=None, created=None, **overrides):
    store.insert(
        "qc_results",
        id=result_id,
        analysis_date=date,
        created_at=created,
        record_id="settlement::visit-1",
        raw_output='{"patient_text": "患者张某某主诉"}',
        issues='[{"description": "患者张某某主诉"}]',
        metadata='{"internal": true}',
        created_by="internal-user-1",
        **{**_owner(identity), **overrides},
    )


def _defect(store, defect_id, *, result_id, status="pending", identity=IDENTITY, **overrides):
    store.insert(
        "qc_defects",
        id=defect_id,
        result_id=result_id,
        status=status,
        rule_code="R1",
        rule_name="主诉缺失",
        description="患者张某某主诉未记录",
        suggestion="请补充主诉",
        evidence="患者张某某主诉",
        department="心内科",
        deduct_score=1.0,
        origin="auto",
        created_at=datetime(2026, 9, 1, 0, 0, 0),
        **{**_owner(identity), **overrides},
    )


def _notification(
    store,
    notification_id,
    *,
    result_id,
    recipient="u1",
    identity=IDENTITY,
    created=None,
    **overrides,
):
    store.insert(
        "notifications",
        id=notification_id,
        type="settlement_qc",
        recipient_id=recipient,
        sender_id="internal-sender",
        severity="warning",
        related_type="qc_result",
        related_id=result_id,
        is_read=False,
        created_at=created,
        **{**_owner(identity), **overrides},
    )


def _where_clause(statement: str) -> str:
    parts = statement.split("WHERE", 1)
    return parts[1] if len(parts) > 1 else ""


def _projection(statement: str) -> str:
    return statement.split("FROM", 1)[0]


def _selects(statements, table_name):
    return [stmt for stmt in statements if f"FROM qc.{table_name}" in stmt]


def test_snapshot_keys_and_identity_echo(store):
    _case(store)
    _result(store, "r1", date=datetime(2026, 9, 1), created=datetime(2026, 9, 1))
    snapshot = store.service.get_snapshot(IDENTITY, "u1")
    assert set(snapshot) == {
        "identity_status",
        "source_key",
        "institute_id",
        "patient_id",
        "visit_id",
        "latest_qc_result",
        "recent_results",
        "active_defects",
        "current_result_defects",
        "latest_notification",
    }
    assert snapshot["identity_status"] == "verified"
    assert snapshot["source_key"] == IDENTITY.source_key
    assert snapshot["institute_id"] == IDENTITY.institute_id
    assert snapshot["patient_id"] == IDENTITY.patient_id
    assert snapshot["visit_id"] == IDENTITY.visit_id


def test_latest_one_plus_recent_five_excludes_legacy_and_foreign_owners(store):
    _case(store)
    for index in range(2, 8):
        _result(
            store, f"r{index}", date=datetime(2026, 9, index), created=datetime(2026, 9, index)
        )
    # 旧结果：单键 record_id 且日期最新，绝不能被兜底选中。
    store.insert(
        "qc_results",
        id="legacy-newest",
        record_id="settlement::visit-1",
        identity_version=None,
        source_key=None,
        institute_id=None,
        patient_id=None,
        visit_id=None,
        analysis_date=datetime(2026, 12, 31),
        created_at=datetime(2026, 12, 31),
    )
    # 同 visit 不同患者 / 不同机构 / 不同结算来源：日期更新但身份不同。
    _result(
        store,
        "foreign-patient",
        identity=VerifiedQCIdentity("LX001", "patient-b", "visit-1", "settlement_qc"),
        date=datetime(2026, 11, 1),
    )
    _result(
        store,
        "foreign-institute",
        identity=VerifiedQCIdentity("LX002", "patient-a", "visit-1", "settlement_qc"),
        date=datetime(2026, 11, 2),
    )
    _result(
        store,
        "foreign-source",
        identity=VerifiedQCIdentity("LX001", "patient-a", "visit-1", "settlement_generate_qc"),
        date=datetime(2026, 11, 3),
    )

    snapshot = store.service.get_snapshot(IDENTITY, None)

    assert snapshot["latest_qc_result"]["id"] == "r7"
    assert [row["id"] for row in snapshot["recent_results"]] == [
        "r6", "r5", "r4", "r3", "r2",
    ]
    assert "legacy-newest" not in {
        snapshot["latest_qc_result"]["id"],
        *[row["id"] for row in snapshot["recent_results"]],
    }
    # 只投影客户字段白名单；时间转 ISO。
    assert set(snapshot["latest_qc_result"]) == {
        "id",
        "rule_set",
        "overall_score",
        "grade",
        "defect_count",
        "analysis_date",
        "created_at",
    }
    assert snapshot["latest_qc_result"]["analysis_date"] == "2026-09-07T00:00:00"
    assert snapshot["latest_qc_result"]["id"] == "r7"
    # 查询条件不按 record_id 兜底，只按现代身份四维。
    result_sql = _selects(store.statements, "qc_results")[0]
    assert "record_id" not in _where_clause(result_sql)
    assert "identity_version" in _where_clause(result_sql)
    assert "source_key" in _where_clause(result_sql)


def test_history_sort_puts_null_analysis_date_and_created_at_last(store):
    _case(store)
    _result(store, "dated", date=datetime(2026, 9, 1), created=datetime(2026, 9, 1))
    _result(store, "null-date", date=None, created=datetime(2026, 9, 30))
    _result(store, "null-both", date=None, created=None)

    snapshot = store.service.get_snapshot(IDENTITY, None)

    assert snapshot["latest_qc_result"]["id"] == "dated"
    assert [row["id"] for row in snapshot["recent_results"]] == ["null-date", "null-both"]


def test_two_settlement_sources_stay_separate(store):
    _case(store)
    generated = VerifiedQCIdentity("LX001", "patient-a", "visit-1", "settlement_generate_qc")
    _result(store, "saved", date=datetime(2026, 9, 2), created=datetime(2026, 9, 2))
    _result(
        store, "generated", identity=generated, date=datetime(2026, 9, 3), created=datetime(2026, 9, 3)
    )
    _defect(store, "d-saved", result_id="saved")
    _defect(store, "d-generated", result_id="generated", identity=generated)
    _notification(store, "n-saved", result_id="saved", created=datetime(2026, 9, 2))
    _notification(
        store, "n-generated", result_id="generated", identity=generated, created=datetime(2026, 9, 3)
    )

    saved = store.service.get_snapshot(IDENTITY, "u1")
    assert saved["latest_qc_result"]["id"] == "saved"
    assert [row["id"] for row in saved["active_defects"]] == ["d-saved"]
    assert saved["latest_notification"]["id"] == "n-saved"

    other = store.service.get_snapshot(generated, "u1")
    assert other["latest_qc_result"]["id"] == "generated"
    assert [row["id"] for row in other["active_defects"]] == ["d-generated"]
    assert other["latest_notification"]["id"] == "n-generated"


def test_defect_semantics_are_not_merged(store):
    _case(store)
    _result(store, "r-new", date=datetime(2026, 9, 5), created=datetime(2026, 9, 5))
    _result(store, "r-old", date=datetime(2026, 9, 1), created=datetime(2026, 9, 1))
    _defect(store, "d-active-old", result_id="r-old", status="pending")
    _defect(store, "d-active-new", result_id="r-new", status="pending")
    _defect(store, "d-completed-new", result_id="r-new", status="completed")
    _defect(store, "d-null-status", result_id="r-old", status=None)
    _defect(
        store,
        "d-foreign-patient",
        result_id="r-new",
        identity=VerifiedQCIdentity("LX001", "patient-b", "visit-1", "settlement_qc"),
    )
    _defect(
        store,
        "d-foreign-source",
        result_id="r-new",
        identity=VerifiedQCIdentity("LX001", "patient-a", "visit-1", "settlement_generate_qc"),
    )

    snapshot = store.service.get_snapshot(IDENTITY, None)

    assert {row["id"] for row in snapshot["active_defects"]} == {
        "d-active-old", "d-active-new", "d-null-status",
    }
    assert {row["id"] for row in snapshot["current_result_defects"]} == {
        "d-active-new", "d-completed-new",
    }
    assert snapshot["latest_qc_result"]["id"] == "r-new"


def test_notification_is_scoped_to_recipient_and_owner(store):
    _case(store)
    _result(store, "r1", date=datetime(2026, 9, 1), created=datetime(2026, 9, 1))
    _notification(store, "n-old", result_id="r1", recipient="u1", created=datetime(2026, 9, 10))
    _notification(store, "n-new", result_id="r1", recipient="u1", created=datetime(2026, 9, 20))
    _notification(
        store, "n-other-recipient", result_id="r1", recipient="u2", created=datetime(2026, 9, 30)
    )
    _notification(
        store,
        "n-foreign-source",
        result_id="r1",
        recipient="u1",
        identity=VerifiedQCIdentity("LX001", "patient-a", "visit-1", "settlement_generate_qc"),
        created=datetime(2026, 9, 25),
    )

    snapshot = store.service.get_snapshot(IDENTITY, "u1")
    assert snapshot["latest_notification"]["id"] == "n-new"
    notification_sql = _selects(store.statements, "notifications")[0]
    assert "recipient_id" in _where_clause(notification_sql)
    assert "record_id" not in _where_clause(notification_sql)
    assert "type" not in _where_clause(notification_sql)

    # 未登录 / 空 recipient：不查询，也不返回他人通知。
    for anonymous in (None, "", "   "):
        store.statements.clear()
        assert store.service.get_snapshot(IDENTITY, anonymous)["latest_notification"] is None
        assert not _selects(store.statements, "notifications")


def test_latest_notification_must_target_the_latest_result(store):
    _case(store)
    _result(store, "r-old", date=datetime(2026, 9, 1), created=datetime(2026, 9, 1))
    _result(store, "r-new", date=datetime(2026, 9, 5), created=datetime(2026, 9, 5))
    # 另一轮通知：时间最新，但 related_id 指向旧结果，不得挂到最新结果下。
    _notification(store, "n-other-round", result_id="r-old", created=datetime(2026, 9, 30))
    # 旧通知：即使 related_id 巧合命中，身份列不完整也不进入现代快照。
    store.insert(
        "notifications",
        id="n-legacy",
        type="settlement_qc",
        recipient_id="u1",
        related_id="r-new",
        identity_version=None,
        created_at=datetime(2026, 9, 29),
    )
    _notification(
        store, "n-other-recipient", result_id="r-new", recipient="u2", created=datetime(2026, 9, 28)
    )
    _notification(store, "n-current", result_id="r-new", created=datetime(2026, 9, 27))

    snapshot = store.service.get_snapshot(IDENTITY, "u1")

    assert snapshot["latest_qc_result"]["id"] == "r-new"
    assert snapshot["latest_notification"]["id"] == "n-current"
    notification_sql = _selects(store.statements, "notifications")[0]
    assert "related_id" in _where_clause(notification_sql)
    assert "recipient_id" in _where_clause(notification_sql)
    # 过滤值必须是真实的最新 result.id，而不是上一轮结果。
    bound = [params for stmt, params in store.calls if "FROM qc.notifications" in stmt][0]
    assert "r-new" in str(bound)
    assert "r-old" not in str(bound)


def test_empty_modern_result_never_implies_pass(store):
    _case(store)
    store.insert(
        "qc_results",
        id="legacy",
        record_id="settlement::visit-1",
        identity_version=None,
        analysis_date=datetime(2026, 9, 9),
    )
    _notification(store, "n-legacy", result_id="legacy-result")
    store.insert(
        "qc_defects",
        id="d-legacy",
        record_id="settlement::visit-1",
        identity_version=None,
        status="pending",
    )

    snapshot = store.service.get_snapshot(IDENTITY, "u1")

    assert snapshot["latest_qc_result"] is None
    assert snapshot["recent_results"] == []
    assert snapshot["active_defects"] == []
    assert snapshot["current_result_defects"] == []
    assert snapshot["latest_notification"] is None
    assert not {"passed", "compliant", "status", "overall_score"} & set(snapshot)
    assert not _selects(store.statements, "qc_defects")
    assert not _selects(store.statements, "notifications")


def test_case_not_found_and_ambiguous(store):
    with pytest.raises(modern.CaseNotFound):
        store.service.get_snapshot(IDENTITY, "u1")
    assert not _selects(store.statements, "qc_results")

    _case(store)
    _case(store)  # 三坐标在 cdm.mr 重复，无法安全归属。
    with pytest.raises(modern.CaseIdentityAmbiguous):
        store.service.get_snapshot(IDENTITY, "u1")
    assert not _selects(store.statements, "qc_results")


def test_projection_excludes_internal_and_patient_text_columns(store):
    _case(store)
    _result(store, "r1", date=datetime(2026, 9, 1), created=datetime(2026, 9, 1))
    _defect(store, "d1", result_id="r1")
    _notification(store, "n1", result_id="r1", created=datetime(2026, 9, 2))

    snapshot = store.service.get_snapshot(IDENTITY, "u1")

    assert set(snapshot["latest_qc_result"]) == {
        "id",
        "rule_set",
        "overall_score",
        "grade",
        "defect_count",
        "analysis_date",
        "created_at",
    }
    assert set(snapshot["active_defects"][0]) == {
        "id",
        "rule_code",
        "rule_name",
        "description",
        "severity",
        "category",
        "location",
        "suggestion",
        "status",
        "created_at",
        "updated_at",
    }
    assert set(snapshot["latest_notification"]) == {
        "id",
        "type",
        "title",
        "content",
        "severity",
        "is_read",
        "read_at",
        "created_at",
    }
    # 内部/患者原文列既不在返回字典，也不在 SQL 投影里。
    result_sql = _selects(store.statements, "qc_results")[0]
    for column in ("raw_output", "issues", "metadata", "created_by", "record_id"):
        assert column not in result_sql
    defect_sqls = _selects(store.statements, "qc_defects")
    assert len(defect_sqls) == 2
    assert all("evidence" not in sql for sql in defect_sqls)
    assert all("origin" not in _projection(sql) for sql in defect_sqls)
    current_sql = [sql for sql in defect_sqls if "result_id" in _where_clause(sql)][0]
    assert "result_id" not in _projection(current_sql)
    notification_sql = _selects(store.statements, "notifications")[0]
    assert "recipient_id" not in _projection(notification_sql)
    assert "recipient_id" in _where_clause(notification_sql)
    assert "related_id" not in _projection(notification_sql)
    assert "related_id" in _where_clause(notification_sql)
    assert "sender_id" not in notification_sql
    # 接收人隔离只能出现在通知查询，绝不能串到结果/缺陷查询（曾出现错位）。
    assert all("recipient_id" not in sql for sql in _selects(store.statements, "qc_results"))
    assert all("recipient_id" not in sql for sql in defect_sqls)


# ---- schema 与来源失败语义（假 Session，不连库）----


class _Rows:
    def __init__(self, rows=(), count=None):
        self.rows = rows
        self.count = count

    def mappings(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None

    def scalar_one(self):
        return self.count


class _FakeSession:
    def __init__(self, *, mr_count=1, error=None):
        self.mr_count = mr_count
        self.error = error
        self.statements: list[str] = []

    def execute(self, stmt):
        if self.error is not None:
            raise self.error
        sql = str(stmt)
        self.statements.append(sql)
        if "cdm.mr" in sql:
            return _Rows(count=self.mr_count)
        return _Rows()

    def close(self):
        pass


_FAKE_COLUMNS = {
    "mr": (("institute_id", Text), ("patient_id", Text), ("visit_id", Text)),
    "qc_results": (
        ("id", String),
        ("identity_version", SmallInteger),
        ("source_key", String(64)),
        ("institute_id", Text),
        ("patient_id", Text),
        ("visit_id", Text),
        ("record_id", Text),
        ("rule_set", String),
        ("overall_score", Float),
        ("grade", String),
        ("defect_count", Integer),
        ("analysis_date", DateTime),
        ("raw_output", Text),
        ("issues", Text),
        ("metadata", Text),
        ("created_by", String),
        ("created_at", DateTime),
        ("updated_at", DateTime),
    ),
    "qc_defects": (
        ("id", String),
        ("result_id", String),
        ("identity_version", SmallInteger),
        ("source_key", String(64)),
        ("institute_id", Text),
        ("patient_id", Text),
        ("visit_id", Text),
        ("rule_code", String),
        ("rule_name", String),
        ("description", Text),
        ("severity", String),
        ("category", String),
        ("location", String),
        ("evidence", Text),
        ("suggestion", Text),
        ("department", String),
        ("deduct_score", Float),
        ("origin", String),
        ("status", String),
        ("created_at", DateTime),
        ("updated_at", DateTime),
    ),
    "notifications": (
        ("id", String),
        ("identity_version", SmallInteger),
        ("source_key", String(64)),
        ("institute_id", Text),
        ("patient_id", Text),
        ("visit_id", Text),
        ("type", String),
        ("title", String),
        ("content", Text),
        ("severity", String),
        ("is_read", Boolean),
        ("read_at", DateTime),
        ("recipient_id", String),
        ("related_id", String),
        ("created_at", DateTime),
    ),
}


def _fake_table(name, *, schema="qc", drop=()):
    columns = [
        Column(column_name, column_type, primary_key=(column_name == "id"))
        for column_name, column_type in _FAKE_COLUMNS[name]
        if column_name not in drop
    ]
    return Table(name, MetaData(), *columns, schema=schema)


def _fake_tables(**drops):
    return {
        ("cdm", "mr"): _fake_table("mr", schema="cdm", drop=drops.get("mr", ())),
        ("qc", "qc_results"): _fake_table("qc_results", drop=drops.get("qc_results", ())),
        ("qc", "qc_defects"): _fake_table("qc_defects", drop=drops.get("qc_defects", ())),
        ("qc", "notifications"): _fake_table("notifications", drop=drops.get("notifications", ())),
    }


@pytest.mark.parametrize("table_name", ["qc_results", "qc_defects", "notifications"])
@pytest.mark.parametrize("column", ["identity_version", "source_key", "visit_id"])
def test_missing_modern_column_is_schema_unavailable(monkeypatch, table_name, column):
    tables = _fake_tables(**{table_name: (column,)})
    monkeypatch.setattr(modern, "_table", lambda schema, name: tables[(schema, name)])
    session = _FakeSession()
    service = modern.ModernCaseQCResultService(session_factory=lambda: session)

    with pytest.raises(modern.SchemaUnavailable) as excinfo:
        service.get_snapshot(IDENTITY, "u1")
    assert f"qc.{table_name} missing modern identity columns" in str(excinfo.value)
    assert column in str(excinfo.value)
    assert not any("qc_results" in sql for sql in session.statements)


@pytest.mark.parametrize("column", ["institute_id", "patient_id", "visit_id"])
def test_missing_cdm_coordinate_is_schema_unavailable(monkeypatch, column):
    tables = _fake_tables(mr=(column,))
    monkeypatch.setattr(modern, "_table", lambda schema, name: tables[(schema, name)])
    session = _FakeSession()
    service = modern.ModernCaseQCResultService(session_factory=lambda: session)

    with pytest.raises(modern.SchemaUnavailable) as excinfo:
        service.get_snapshot(IDENTITY, "u1")
    assert "cdm.mr missing case identity columns" in str(excinfo.value)
    assert column in str(excinfo.value)


@pytest.mark.parametrize(
    ("table_name", "column"),
    [
        ("qc_results", "id"),
        ("qc_results", "analysis_date"),
        ("qc_results", "created_at"),
        ("qc_results", "grade"),
        ("qc_defects", "id"),
        ("qc_defects", "result_id"),
        ("qc_defects", "status"),
        ("qc_defects", "updated_at"),
        ("notifications", "id"),
        ("notifications", "recipient_id"),
        ("notifications", "related_id"),
        ("notifications", "created_at"),
    ],
)
def test_missing_required_query_column_is_schema_unavailable(monkeypatch, table_name, column):
    tables = _fake_tables(**{table_name: (column,)})
    monkeypatch.setattr(modern, "_table", lambda schema, name: tables[(schema, name)])
    session = _FakeSession()
    service = modern.ModernCaseQCResultService(session_factory=lambda: session)

    with pytest.raises(modern.SchemaUnavailable) as excinfo:
        service.get_snapshot(IDENTITY, "u1")
    assert f"qc.{table_name} missing required columns" in str(excinfo.value)
    assert column in str(excinfo.value)
    assert not any("qc.qc_results" in sql for sql in session.statements)


def test_reflection_and_query_errors_map_to_source_unavailable_without_leak(monkeypatch):
    secret = "postgresql://qc_user:secret-value@db.internal:5432/business"

    def _boom(_schema, _name):
        raise RuntimeError(secret)

    monkeypatch.setattr(modern, "_table", _boom)
    service = modern.ModernCaseQCResultService(session_factory=lambda: _FakeSession())
    with pytest.raises(modern.SourceUnavailable) as excinfo:
        service.get_snapshot(IDENTITY, "u1")
    assert str(excinfo.value) == "modern case QC source is unavailable"
    assert secret not in repr(excinfo.value)
    assert excinfo.value.__cause__ is None

    monkeypatch.undo()
    modern._table.cache_clear()
    tables = _fake_tables()
    monkeypatch.setattr(modern, "_table", lambda schema, name: tables[(schema, name)])
    failing = _FakeSession(error=RuntimeError(f"connect failed: {secret}"))
    service = modern.ModernCaseQCResultService(session_factory=lambda: failing)
    with pytest.raises(modern.SourceUnavailable) as excinfo:
        service.get_snapshot(IDENTITY, "u1")
    assert str(excinfo.value) == "modern case QC source is unavailable"
    assert secret not in repr(excinfo.value)


def test_unavailable_session_factory_and_bad_identity(monkeypatch):
    monkeypatch.setattr(modern, "SessionLocal", None)
    service = modern.ModernCaseQCResultService()
    with pytest.raises(modern.SourceUnavailable):
        service.get_snapshot(IDENTITY, None)

    def _boom():
        raise RuntimeError("dsn missing")

    with pytest.raises(modern.SourceUnavailable):
        modern.ModernCaseQCResultService(session_factory=_boom).get_snapshot(IDENTITY, None)

    tables = _fake_tables()
    monkeypatch.setattr(modern, "_table", lambda schema, name: tables[(schema, name)])
    with pytest.raises(TypeError):
        modern.ModernCaseQCResultService(session_factory=lambda: _FakeSession()).get_snapshot(
            "visit-1", None
        )
