"""迁移 68：缺陷场景列双 schema 合同（不连接真实数据库）。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


def migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260928_000068_defect_scene.py"
    spec = importlib.util.spec_from_file_location("defect_scene_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Inspector:
    def __init__(self, states, *, reflected=False, extra_check=False, wrong_type=False):
        self.states = states
        self.reflected = reflected
        self.extra_check = extra_check
        self.wrong_type = wrong_type

    def has_table(self, _table, schema):
        return self.states.get(schema) != "missing_table"

    def get_columns(self, _table, schema):
        columns = [{"name": "created_at", "type": sa.DateTime(), "nullable": False,
                    "default": None}]
        if self.states.get(schema) == "present":
            columns.append({
                "name": "scene",
                "type": sa.String(32 if self.wrong_type else 24),
                "nullable": True,
                "default": None,
            })
        return columns

    def get_check_constraints(self, _table, schema):
        if self.states.get(schema) != "present":
            return []
        sql = "scene IS NULL OR scene IN ('running', 'final', 'outpatient_emergency')"
        if self.reflected:
            sql = (
                "((scene IS NULL) OR ((scene)::text = ANY "
                "((ARRAY['running'::character varying, 'final'::character varying, "
                "'outpatient_emergency'::character varying])::text[])))"
            )
        checks = [{"name": "ck_qc_defects_scene", "sqltext": sql}]
        if self.extra_check:
            checks.append({"name": "ck_scene_extra", "sqltext": "scene <> 'legacy'"})
        return checks

    def get_indexes(self, _table, schema):
        if self.states.get(schema) != "present":
            return []
        return [{
            "name": "ix_qc_defects_scene_created",
            "column_names": ["scene", "created_at"],
            "unique": False,
        }]


class Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class Bind:
    def __init__(self, used_by_schema=None):
        self.used_by_schema = used_by_schema or {}
        self.statements = []

    def execute(self, statement):
        sql = str(statement)
        self.statements.append(sql)
        used = next((value for schema, value in self.used_by_schema.items()
                     if f'"{schema}"."qc_defects"' in sql and "count(*)" in sql), 0)
        return Scalar(used)


def _patch_contract(monkeypatch, module, states, **inspector_kwargs):
    bind = Bind()
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    monkeypatch.setattr(
        module.sa, "inspect", lambda _bind: Inspector(states, **inspector_kwargs),
    )
    return bind


def test_upgrade_adds_exact_scene_contract_to_both_schemas(monkeypatch):
    module = migration()
    added, checks, indexes = [], [], []
    _patch_contract(monkeypatch, module, {"qc": "absent", "public": "absent"})
    monkeypatch.setattr(module.op, "add_column", lambda *args, **kwargs: added.append((args, kwargs)))
    monkeypatch.setattr(
        module.op, "create_check_constraint", lambda *args, **kwargs: checks.append((args, kwargs)),
    )
    monkeypatch.setattr(module.op, "create_index", lambda *args, **kwargs: indexes.append((args, kwargs)))

    module.upgrade()

    assert module.revision == "20260928_000068"
    assert module.down_revision == "20260928_000067"
    assert [kwargs["schema"] for _, kwargs in added] == ["qc", "public"]
    assert all(args[1].name == "scene" and args[1].type.length == 24
               and args[1].nullable for args, _ in added)
    assert [kwargs["schema"] for _, kwargs in checks] == ["qc", "public"]
    assert [kwargs["schema"] for _, kwargs in indexes] == ["qc", "public"]
    assert all(args[2] == ["scene", "created_at"] for args, _ in indexes)


def test_upgrade_accepts_exact_postgres_reflection_without_ddl(monkeypatch):
    module = migration()
    _patch_contract(
        monkeypatch, module, {"qc": "present", "public": "present"}, reflected=True,
    )
    monkeypatch.setattr(module.op, "add_column", lambda *_args, **_kwargs: pytest.fail("不得重复 DDL"))
    module.upgrade()


def test_model_matches_migration_scene_contract():
    from app.database.models.qc import QCDefect

    module = migration()
    table = QCDefect.__table__
    column = table.c.scene
    assert isinstance(column.type, sa.String)
    assert column.type.length == 24
    assert column.nullable is True
    assert column.server_default is None
    checks = {
        item.name: str(item.sqltext)
        for item in table.constraints
        if isinstance(item, sa.CheckConstraint) and "scene" in str(item.sqltext)
    }
    assert set(checks) == {module.CHECK}
    assert module._normalized_sql(checks[module.CHECK]) == module._normalized_sql(module.CHECK_SQL)
    indexes = {
        item.name: [column.name for column in item.columns]
        for item in table.indexes
        if "scene" in [column.name for column in item.columns]
    }
    assert indexes == {module.INDEX: [module.COLUMN, "created_at"]}


@pytest.mark.parametrize("states,kwargs,match", [
    ({"qc": "present", "public": "absent"}, {}, "部分 schema"),
    ({"qc": "missing_table", "public": "absent"}, {}, "不存在"),
    ({"qc": "present", "public": "present"}, {"extra_check": True}, "合同漂移"),
    ({"qc": "present", "public": "present"}, {"wrong_type": True}, "合同漂移"),
])
def test_upgrade_rejects_partial_missing_or_drifted_contract(
    monkeypatch, states, kwargs, match,
):
    module = migration()
    _patch_contract(monkeypatch, module, states, **kwargs)
    with pytest.raises(RuntimeError, match=match):
        module.upgrade()


def test_downgrade_locks_both_schemas_before_refusing_used_scene(monkeypatch):
    module = migration()
    bind = Bind({"public": 1})
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    monkeypatch.setattr(
        module.sa, "inspect",
        lambda _bind: Inspector({"qc": "present", "public": "present"}),
    )
    monkeypatch.setattr(module.op, "drop_column", lambda *_args, **_kwargs: pytest.fail("不得删列"))

    with pytest.raises(RuntimeError, match="拒绝降级"):
        module.downgrade()

    locks = [sql for sql in bind.statements if sql.startswith("LOCK TABLE")]
    assert locks == [
        'LOCK TABLE "qc"."qc_defects" IN ACCESS EXCLUSIVE MODE',
        'LOCK TABLE "public"."qc_defects" IN ACCESS EXCLUSIVE MODE',
    ]


def test_downgrade_drops_public_then_qc_only_when_unused(monkeypatch):
    module = migration()
    bind = Bind()
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    monkeypatch.setattr(
        module.sa, "inspect",
        lambda _bind: Inspector({"qc": "present", "public": "present"}),
    )
    dropped = []
    monkeypatch.setattr(module.op, "drop_index", lambda *args, **kwargs: dropped.append(("index", kwargs["schema"])))
    monkeypatch.setattr(module.op, "drop_constraint", lambda *args, **kwargs: dropped.append(("check", kwargs["schema"])))
    monkeypatch.setattr(module.op, "drop_column", lambda *args, **kwargs: dropped.append(("column", kwargs["schema"])))

    module.downgrade()

    assert dropped == [
        ("index", "public"), ("check", "public"), ("column", "public"),
        ("index", "qc"), ("check", "qc"), ("column", "qc"),
    ]
