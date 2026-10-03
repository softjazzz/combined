"""首页场景迁移仅用反射夹具/操作记录，不连接真实数据库。"""
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from tests.unit.test_scoring_standard_migration import Inspector, _load_migration, migration, state


def module():
    return _load_migration("20261003_000084_frontpage_scoring_scene.py", "frontpage_84")


def baseline(new=False):
    m = module()
    data = state(migration(), deployed=True)
    if new:
        for schema in m.SCHEMAS:
            data[schema][m.TABLE]["checks"][m.CONSTRAINT] = m.NEW_CHECK
    return data


def operations(monkeypatch, m, data, populated=None):
    calls = []
    populated = populated or {}

    def execute(statement, parameters=None):
        sql = str(statement)
        calls.append(("execute", sql, parameters))
        schema = "qc" if '"qc"' in sql else "public"
        return SimpleNamespace(scalar_one=lambda: populated.get(schema, 0))

    bind = SimpleNamespace(execute=execute)
    monkeypatch.setattr(m.op, "get_bind", lambda: bind)
    monkeypatch.setattr(m.sa, "inspect", lambda _: Inspector(data))
    for name in ("drop_constraint", "create_check_constraint"):
        monkeypatch.setattr(m.op, name, lambda *args, _name=name, **kwargs: calls.append((_name, args, kwargs)))
    return calls


@pytest.mark.parametrize("new", [False, True])
def test_exact_baseline_and_idempotent_upgrade(monkeypatch, new):
    m = module()
    assert m.revision == "20261003_000084" and m.down_revision == "20261003_000083"
    assert m.schema_state(Inspector(baseline(new))) == ("new" if new else "old")
    calls = operations(monkeypatch, m, baseline(new))
    m.upgrade()
    assert [c[0] for c in calls] == ["execute"] * 2 + ([] if new else ["drop_constraint", "create_check_constraint"] * 2)
    if not new:
        assert [c[2]["schema"] for c in calls[2:]] == ["qc", "qc", "public", "public"]
        assert all(c[1][2] == m.NEW_CHECK for c in calls if c[0] == "create_check_constraint")


@pytest.mark.parametrize("drift", ["missing", "partial", "check", "column", "index"])
def test_unknown_baseline_rejected_before_ddl(monkeypatch, drift):
    m = module()
    data = baseline()
    table = data["public"][m.TABLE]
    if drift == "missing":
        del data["public"][m.TABLE]
    elif drift == "partial":
        table["checks"][m.CONSTRAINT] = m.NEW_CHECK
    elif drift == "check":
        table["checks"][m.CONSTRAINT] = "scene <> ''"
    elif drift == "column":
        table["columns"]["scene"]["type"] = sa.String(32)
    else:
        table["indexes"] = []
    calls = operations(monkeypatch, m, data)
    with pytest.raises(RuntimeError):
        m.upgrade()
    assert calls == []


@pytest.mark.parametrize("schema", ["qc", "public"])
def test_populated_frontpage_prevents_downgrade(monkeypatch, schema):
    m = module()
    calls = operations(monkeypatch, m, baseline(True), {schema: 1})
    with pytest.raises(RuntimeError, match="已有首页标准"):
        m.downgrade()
    assert all(c[0] == "execute" for c in calls)


def test_empty_downgrade_keeps_all_other_contracts(monkeypatch):
    m = module()
    calls = operations(monkeypatch, m, baseline(True))
    m.downgrade()
    assert [c[0] for c in calls] == ["execute"] * 4 + ["drop_constraint", "create_check_constraint"] * 2
    assert [c[2]["schema"] for c in calls[4:]] == ["public", "public", "qc", "qc"]
    assert all(c[1][2] == m.OLD_CHECK for c in calls if c[0] == "create_check_constraint")


def test_accepts_postgres_reflected_array_expression():
    m = module()
    data = baseline(True)
    for schema in m.SCHEMAS:
        data[schema][m.TABLE]["checks"][m.CONSTRAINT] = (
            "((scene)::text = ANY ((ARRAY['running'::character varying, 'final'::character varying, "
            "'outpatient'::character varying, 'frontpage'::character varying])::text[]))"
        )
    assert m.schema_state(Inspector(data)) == "new"
