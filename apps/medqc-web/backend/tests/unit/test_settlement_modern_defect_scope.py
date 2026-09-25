"""结算清单已执行范围的可信度边界与旧自动缺陷关闭范围反例。"""

import pytest
from sqlalchemy import Column, MetaData, String, Table
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.dml import Insert, Update
from sqlalchemy.sql.selectable import Select

from app.routers import settlement as route
from app.services import qc_persistence_service as persistence
from app.services.qc_persistence_service import VerifiedQCIdentity


def _result(rule_id: str, passed: bool) -> dict:
    return {"rule_id": rule_id, "rule_name": rule_id, "passed": passed}


def _build(
    summary: dict,
    results: list,
    *,
    source: str = "settlement_qc",
    institute_id: str | None = None,
) -> dict:
    return route._build_settlement_persistence_result(
        patient_id="p1",
        visit_id="v1",
        settlement={"institute_id": institute_id} if institute_id else {},
        summary=summary,
        results=results,
        source=source,
        institute_id=institute_id,
    )


def test_scope_covers_passed_rules_in_execution_order_without_duplicates():
    payload = _build(
        {"total": 3, "passed": 3, "failed": 0, "pass_rate": "100%"},
        [_result("B", True), _result("A", True), _result("B", True)],
    )
    assert payload["issues"] == []
    assert payload["metadata"]["executed_defect_scope"] == {
        "kind": "rule_codes",
        "values": ["B", "A"],
    }


def test_generated_source_also_publishes_executed_rule_scope():
    payload = _build(
        {"total": 1, "passed": 1, "failed": 0, "pass_rate": "100%"},
        [_result("A", True)],
        source="settlement_generate_qc",
        institute_id="hospital-1",
    )
    assert payload["metadata"]["data_source"] == "settlement_generate_qc"
    assert payload["metadata"]["executed_defect_scope"] == {
        "kind": "rule_codes",
        "values": ["A"],
    }


def test_published_scope_always_covers_published_issues():
    payload = _build(
        {"total": 2, "passed": 1, "failed": 1, "pass_rate": "50%"},
        [_result("A", True), _result("B", False)],
    )
    scope = payload["metadata"]["executed_defect_scope"]
    # 与 writer 合同一致：scope 只能是 {kind, values}，且必须覆盖本次产出的全部问题
    assert set(scope) == {"kind", "values"}
    assert all(issue["rule_code"] in scope["values"] for issue in payload["issues"])


@pytest.mark.parametrize(
    "results",
    [
        [],
        ["not-a-result-dict"],
        [{"passed": True}],
        [{"rule_id": None}],
        [{"rule_id": ""}],
        [{"rule_id": "   "}],
        # 非字符串规则代码一律视为畸形，不得 str() 成规则号后发布关闭范围
        [{"rule_id": 0}],
        [{"rule_id": 1}],
        [{"rule_id": True}],
        [{"rule_id": 1.5}],
        [{"rule_id": {"code": "A"}}],
        [{"rule_id": ["A"]}],
        # 已 trim 才可信：带前后空白/换行的代码不得参与关闭
        [{"rule_id": " A"}],
        [{"rule_id": "A "}],
        [{"rule_id": " A "}],
        [{"rule_id": "A\n"}],
        [{"rule_id": None}, {"rule_id": ""}],
        # 只要出现一个不可信规则代码，整份结果都不发布范围（不允许按部分规则关闭）
        [{"rule_id": "A"}, {"rule_id": 1}],
        [{"rule_id": "A"}, {"rule_id": " A"}],
        [{"rule_id": "A"}, {"passed": True}],
    ],
)
def test_scope_helper_withholds_scope_for_any_untrustworthy_rule_id(results):
    assert route._settlement_executed_defect_scope(results) is None


@pytest.mark.parametrize(
    "results",
    [
        [],
        [{"passed": True}],
        [{"rule_id": "", "passed": False, "message": "缺规则代码"}],
        [{"rule_id": "   ", "passed": False, "message": "缺规则代码"}],
        [{"rule_id": 1, "passed": False, "message": "规则代码类型错误"}],
        [{"rule_id": " A ", "passed": False, "message": "规则代码未 trim"}],
    ],
)
def test_results_without_trustworthy_rule_id_publish_no_scope(results):
    payload = _build({"total": 1, "passed": 1, "failed": 0}, results)
    assert "executed_defect_scope" not in payload["metadata"]


def test_scope_is_withheld_when_a_failing_item_has_no_rule_id():
    payload = _build(
        {"total": 2, "passed": 1, "failed": 1, "pass_rate": "50%"},
        [_result("A", True), {"passed": False, "message": "缺规则代码"}],
    )
    # 失败项无可信规则代码时不得声称已执行范围：否则 writer 会越界关闭旧缺陷或直接拒绝落库
    assert "executed_defect_scope" not in payload["metadata"]
    assert [issue["rule_code"] for issue in payload["issues"]] == ["settlement_rule"]


def test_malformed_source_list_still_fails_instead_of_closing_scope():
    # 源 list 畸形必须显式失败（交上层脱敏 503），不得静默退化成“无范围不关闭”。
    with pytest.raises((AttributeError, TypeError)):
        _build({"total": 1, "passed": 1, "failed": 0}, ["not-a-result-dict"])
    with pytest.raises((AttributeError, TypeError)):
        _build({"total": 1, "passed": 1, "failed": 0}, None)


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, rows, *, write_rowcount=1):
        self.rows = rows
        self.writes = []
        self.write_rowcount = write_rowcount

    def execute(self, statement):
        if isinstance(statement, Select):
            return _Rows(self.rows)
        self.writes.append(statement)
        return type("WriteResult", (), {"rowcount": self.write_rowcount})()


def _defects_table():
    return Table(
        "qc_defects",
        MetaData(),
        Column("id", String, primary_key=True),
        Column("record_id", String),
        Column("rule_code", String),
        Column("rule_name", String),
        Column("location", String),
        Column("category", String),
        Column("status", String),
        Column("origin", String),
        Column("identity_version", String),
        Column("source_key", String),
        Column("institute_id", String),
        Column("patient_id", String),
        Column("visit_id", String),
        schema="qc",
    )


def _auto_defect(rule_code: str) -> dict:
    return {
        "id": f"defect-{rule_code}",
        "record_id": "settlement::v1",
        "rule_code": rule_code,
        "rule_name": rule_code,
        "location": "结算清单",
        "category": "settlement",
        "status": "pending",
        "origin": "auto",
    }


def _persist(monkeypatch, payload: dict, rows: list):
    table = _defects_table()
    session = _Session(rows)
    histories = []
    monkeypatch.setattr(persistence, "_table", lambda _schema, _name: table)
    service = persistence.QCPersistenceService(session_factory=lambda: session)
    monkeypatch.setattr(
        service,
        "_insert_defect_history",
        lambda _session, **kwargs: histories.append(kwargs),
    )
    summary = service._persist_qc_defects(
        session,
        payload,
        "result-1",
        "actor-1",
        "tester",
        VerifiedQCIdentity("hospital-1", "p1", "v1", payload["metadata"]["data_source"]),
    )
    return summary, session.writes, histories


def _resolve_sql(writes) -> list:
    return [
        str(
            statement.whereclause.compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        for statement in writes
        if isinstance(statement, Update) and "status" in statement._values
    ]


def _closure_payload(source: str = "settlement_generate_qc") -> dict:
    return _build(
        {"total": 2, "passed": 1, "failed": 1, "pass_rate": "50%"},
        [_result("A", True), _result("B", False)],
        source=source,
        institute_id="hospital-1",
    )


def test_published_scope_closes_only_defects_of_disappeared_executed_rules(monkeypatch):
    payload = _closure_payload()
    assert payload["metadata"]["executed_defect_scope"] == {
        "kind": "rule_codes",
        "values": ["A", "B"],
    }

    # A 本次已通过（旧缺陷应消失）、C 本次未执行（旧缺陷不得动）、B 本次失败（新建）。
    summary, writes, histories = _persist(
        monkeypatch, payload, [_auto_defect("A"), _auto_defect("C")]
    )

    assert summary["resolved"] == 1
    assert summary["created"] == 1
    resolve_sql = _resolve_sql(writes)
    assert len(resolve_sql) == 1
    # 关闭范围锁在同一来源 + 同一三坐标 + origin='auto' 内，不跨来源/病例：
    # 该 where 子句就是真实库里阻止跨来源关闭的依据（替身会话不模拟 WHERE 过滤）。
    assert "'defect-A'" in resolve_sql[0]
    assert "'defect-C'" not in resolve_sql[0]
    assert "source_key = 'settlement_generate_qc'" in resolve_sql[0]
    assert "institute_id = 'hospital-1'" in resolve_sql[0]
    assert "patient_id = 'p1'" in resolve_sql[0]
    assert "visit_id = 'v1'" in resolve_sql[0]
    assert "origin = 'auto'" in resolve_sql[0]
    assert "identity_version = 1" in resolve_sql[0]
    assert [history["action"] for history in histories] == [
        "auto_created",
        "auto_resolved",
    ]


def test_disappeared_rule_defect_stays_open_without_published_scope(monkeypatch):
    payload = _closure_payload()
    payload["metadata"].pop("executed_defect_scope")

    summary, writes, histories = _persist(monkeypatch, payload, [_auto_defect("A")])

    # 旧合同（不发布范围）下旧缺陷必须保持 open，本用例即该行为的回归证据。
    assert summary["resolved"] == 0
    assert summary["created"] == 1
    assert _resolve_sql(writes) == []
    assert len([stmt for stmt in writes if isinstance(stmt, Insert)]) == 1
    assert [history["action"] for history in histories] == ["auto_created"]
