"""迁移 72：现代申诉来源列只改权威 qc.qc_appeals（伪造 inspector + 离线 PostgreSQL DDL，不连库）。"""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.dialects import postgresql

from app.database.models import qc as qc_models
from app.database.models.qc import QCAppeal


def migration():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/20260929_000072_modern_appeal_source.py"
    )
    spec = importlib.util.spec_from_file_location(
        "modern_appeal_source_migration", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LEGACY_COLUMNS = [
    {"name": "id", "type": sa.String(36), "nullable": False, "default": None},
    {"name": "appellant_id", "type": sa.String(36), "nullable": False, "default": None},
    {"name": "status", "type": sa.String(20), "nullable": False, "default": None},
]


class Inspector:
    def __init__(
        self,
        module,
        state="absent",
        *,
        drift=None,
        missing_table=False,
        profile="varchar",
    ):
        self.module = module
        self.state = state
        self.drift = drift
        self.missing_table = missing_table
        self.profile = profile
        self.schemas: list[str | None] = []

    def has_table(self, _table, schema=None):
        self.schemas.append(schema)
        return not self.missing_table and schema == "qc"

    def get_columns(self, _table, schema=None):
        self.schemas.append(schema)
        present = self.state == "present"
        columns = [*LEGACY_COLUMNS] + [
            {
                "name": name,
                "type": sa.Text() if self.profile == "text" else sa.String(36),
                "nullable": present or self.profile == "text",
                "default": None,
            }
            for name in ("qc_result_id", "record_id")
        ]
        if self.state in ("present", "partial"):
            names = list(self.module.COLUMNS)
            if self.state == "partial":
                names = names[:3]
            for name in names:
                kind, length = self.module.COLUMNS[name]
                if self.drift == "type" and name == "scene":
                    length = 32
                columns.append(
                    {
                        "name": name,
                        "type": kind(length),
                        "nullable": True,
                        "default": None,
                    }
                )
        if self.drift == "legacy_nullable":
            for column in columns:
                if column["name"] == "record_id":
                    column["nullable"] = not column["nullable"]
        for column in columns:
            if column["name"] == "record_id":
                if self.drift == "legacy_mixed_type":
                    column["type"] = (
                        sa.String(36) if self.profile == "text" else sa.Text()
                    )
                elif self.drift == "legacy_length":
                    column["type"] = sa.String(100)
                elif self.drift == "legacy_default":
                    column["default"] = "''::text"
        return columns

    def get_check_constraints(self, _table, schema=None):
        if self.state != "present":
            return (
                []
                if self.drift != "orphan_check"
                else [
                    {"name": self.module.CHECK, "sqltext": "true"},
                ]
            )
        sql = self.module.CHECK_SQL
        if self.drift == "check":
            sql = sql.replace("'final', ", "")
        # PostgreSQL 反射形状：IN 变 ANY(ARRAY)、带类型转换与括号。
        reflected = sql.replace(
            "target_kind IN ('canonical_defect', 'task_manual_defect')",
            "((target_kind)::text = ANY ((ARRAY['canonical_defect'::character varying, "
            "'task_manual_defect'::character varying])::text[]))",
        )
        return [{"name": self.module.CHECK, "sqltext": f"({reflected})"}]

    def get_indexes(self, _table, schema=None):
        if self.state != "present":
            return []
        where = (
            "((target_kind IS NOT NULL) AND ((status)::text = ANY ((ARRAY['pending'::character "
            "varying, 'reviewing'::character varying])::text[])))"
        )
        if self.drift == "where":
            where = "(target_kind IS NOT NULL)"
        return [
            {
                "name": "ix_qc_appeals_status",
                "column_names": ["status"],
                "unique": False,
            },
            {
                "name": self.module.OPEN_TARGET_INDEX,
                "column_names": list(self.module.OPEN_TARGET_COLUMNS),
                "unique": self.drift != "not_unique",
                "dialect_options": {"postgresql_where": where},
            },
            {
                "name": self.module.SCENE_INDEX,
                "column_names": ["scene", "status"],
                "unique": False,
            },
        ]


class Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class Bind:
    def __init__(self, used=0):
        self.used = used
        self.statements: list[str] = []

    def execute(self, statement):
        self.statements.append(str(statement))
        return Scalar(self.used)


def _offline_sql(
    module, monkeypatch, direction: str, inspector: Inspector, bind=None
) -> str:
    buffer = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": buffer},
    )
    monkeypatch.setattr(module.sa, "inspect", lambda _bind: inspector)
    with Operations.context(context):
        if bind is not None:
            monkeypatch.setattr(module.op, "get_bind", lambda: bind)
        else:
            monkeypatch.setattr(module.op, "get_bind", lambda: Bind())
        getattr(module, direction)()
    return buffer.getvalue()


def test_revision_chain_follows_71():
    module = migration()
    assert module.revision == "20260929_000072"
    assert module.down_revision == "20260928_000071"


def test_upgrade_emits_postgres_ddl_only_for_qc_schema(monkeypatch):
    module = migration()
    inspector = Inspector(module, "absent")
    sql = _offline_sql(module, monkeypatch, "upgrade", inspector)

    assert set(inspector.schemas) == {"qc"}
    assert "public." not in sql
    assert "ALTER TABLE qc.qc_appeals ALTER COLUMN qc_result_id DROP NOT NULL" in sql
    assert "ALTER TABLE qc.qc_appeals ALTER COLUMN record_id DROP NOT NULL" in sql
    for name, (_kind, length) in module.COLUMNS.items():
        assert f"ALTER TABLE qc.qc_appeals ADD COLUMN {name} VARCHAR({length})" in sql
    assert "ADD CONSTRAINT ck_qc_appeals_modern_source CHECK" in sql
    assert (
        "CREATE UNIQUE INDEX uq_qc_appeals_open_target ON qc.qc_appeals "
        "(appellant_id, target_kind, target_id, institute_id, patient_id, visit_id, scene, "
        "root_job_id, envelope_id) "
        "WHERE target_kind IS NOT NULL AND status IN ('pending', 'reviewing')"
    ) in sql
    assert (
        "CREATE INDEX ix_qc_appeals_scene_status ON qc.qc_appeals (scene, status)"
        in sql
    )
    # 历史行不回填：迁移不含任何 UPDATE。
    assert "UPDATE" not in sql.upper()


def test_upgrade_is_idempotent_on_exact_postgres_reflection(monkeypatch):
    module = migration()
    sql = _offline_sql(module, monkeypatch, "upgrade", Inspector(module, "present"))
    assert "ALTER TABLE" not in sql and "CREATE" not in sql


def test_upgrade_text_nullable_profile_locks_and_validates_history_before_ddl(
    monkeypatch,
):
    module = migration()
    bind = Bind()
    sql = _offline_sql(
        module, monkeypatch, "upgrade", Inspector(module, profile="text"), bind
    )
    assert bind.statements[0] == 'LOCK TABLE "qc"."qc_appeals" IN ACCESS EXCLUSIVE MODE'
    precheck = bind.statements[1]
    for name in module.LEGACY_REQUIRED:
        assert f"{name} IS NULL" in precheck
        assert f"btrim({name}," in precheck
    assert "ADD CONSTRAINT ck_qc_appeals_modern_source CHECK" in sql
    assert "ALTER COLUMN qc_result_id" not in sql
    assert "ALTER COLUMN record_id" not in sql
    assert "public." not in sql and "UPDATE" not in sql.upper()


@pytest.mark.parametrize("profile", ["varchar", "text"])
def test_upgrade_refuses_missing_or_blank_legacy_association_before_ddl(
    monkeypatch, profile
):
    module = migration()
    bind = Bind(used=1)
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    monkeypatch.setattr(
        module.sa, "inspect", lambda _bind: Inspector(module, profile=profile)
    )
    monkeypatch.setattr(
        module.op, "add_column", lambda *_a, **_k: pytest.fail("不得执行 DDL")
    )
    monkeypatch.setattr(
        module.op, "alter_column", lambda *_a, **_k: pytest.fail("不得修改旧列")
    )
    with pytest.raises(RuntimeError, match="旧关联.*缺失或空白"):
        module.upgrade()
    assert bind.statements[0].startswith('LOCK TABLE "qc".')


def test_deployed_text_profile_is_idempotent(monkeypatch):
    module = migration()
    sql = _offline_sql(
        module, monkeypatch, "upgrade", Inspector(module, "present", profile="text")
    )
    assert "ALTER TABLE" not in sql and "CREATE" not in sql


@pytest.mark.parametrize("state", ["absent", "present"])
@pytest.mark.parametrize("profile", ["varchar", "text"])
@pytest.mark.parametrize(
    "drift", ["legacy_mixed_type", "legacy_length", "legacy_default", "legacy_nullable"]
)
def test_legacy_profiles_reject_exact_type_default_and_nullable_drift(
    monkeypatch, state, profile, drift
):
    module = migration()
    monkeypatch.setattr(module.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(
        module.sa,
        "inspect",
        lambda _bind: Inspector(module, state, profile=profile, drift=drift),
    )
    monkeypatch.setattr(
        module.op, "add_column", lambda *_a, **_k: pytest.fail("不得执行 DDL")
    )
    with pytest.raises(RuntimeError):
        module.upgrade()


@pytest.mark.parametrize(
    "state,drift,match",
    [
        ("partial", None, "部分部署或漂移"),
        ("present", "type", "部分部署或漂移"),
        ("present", "check", "部分部署或漂移"),
        ("present", "where", "部分部署或漂移"),
        ("present", "not_unique", "部分部署或漂移"),
        ("present", "legacy_nullable", "部分部署或漂移"),
        ("absent", "legacy_nullable", "可空性漂移"),
        ("absent", "orphan_check", "残留"),
    ],
)
def test_upgrade_rejects_partial_or_drifted_contract(monkeypatch, state, drift, match):
    module = migration()
    monkeypatch.setattr(module.op, "get_bind", lambda: object())
    monkeypatch.setattr(
        module.sa, "inspect", lambda _bind: Inspector(module, state, drift=drift)
    )
    monkeypatch.setattr(
        module.op, "add_column", lambda *_a, **_k: pytest.fail("不得执行 DDL")
    )
    with pytest.raises(RuntimeError, match=match):
        module.upgrade()


def test_upgrade_refuses_missing_authoritative_table(monkeypatch):
    module = migration()
    monkeypatch.setattr(module.op, "get_bind", lambda: object())
    monkeypatch.setattr(
        module.sa,
        "inspect",
        lambda _bind: Inspector(module, missing_table=True),
    )
    with pytest.raises(RuntimeError, match="不存在"):
        module.upgrade()


def test_downgrade_refuses_when_modern_appeals_exist(monkeypatch):
    module = migration()
    bind = Bind(used=1)
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    monkeypatch.setattr(
        module.sa, "inspect", lambda _bind: Inspector(module, "present")
    )
    monkeypatch.setattr(
        module.op, "drop_column", lambda *_a, **_k: pytest.fail("不得删列")
    )
    with pytest.raises(RuntimeError, match="拒绝降级"):
        module.downgrade()
    assert bind.statements[0] == 'LOCK TABLE "qc"."qc_appeals" IN ACCESS EXCLUSIVE MODE'


def test_downgrade_restores_legacy_not_null_when_unused(monkeypatch):
    module = migration()
    sql = _offline_sql(
        module,
        monkeypatch,
        "downgrade",
        Inspector(module, "present"),
        bind=Bind(used=0),
    )
    assert "DROP INDEX qc.uq_qc_appeals_open_target" in sql
    assert "DROP CONSTRAINT ck_qc_appeals_modern_source" in sql
    assert "ALTER TABLE qc.qc_appeals ALTER COLUMN record_id SET NOT NULL" in sql


def test_downgrade_preserves_original_text_nullable_profile(monkeypatch):
    module = migration()
    sql = _offline_sql(
        module,
        monkeypatch,
        "downgrade",
        Inspector(module, "present", profile="text"),
        bind=Bind(),
    )
    assert "DROP CONSTRAINT ck_qc_appeals_modern_source" in sql
    assert "SET NOT NULL" not in sql and "ALTER COLUMN" not in sql
    assert "public." not in sql


def test_model_matches_migration_contract():
    module = migration()
    table = QCAppeal.__table__
    for name, (kind, length) in module.COLUMNS.items():
        column = table.c[name]
        assert isinstance(column.type, kind) and column.type.length == length, name
        assert column.nullable is True and column.server_default is None
    assert table.c.qc_result_id.nullable is True
    assert table.c.record_id.nullable is True
    assert tuple(module.COLUMNS) == qc_models.QC_APPEAL_MODERN_COLUMNS
    checks = {
        item.name: str(item.sqltext)
        for item in table.constraints
        if isinstance(item, sa.CheckConstraint)
    }
    assert module.normalized_sql(checks[module.CHECK]) == module.normalized_sql(
        module.CHECK_SQL
    )
    indexes = {item.name: item for item in table.indexes}
    unique = indexes[module.OPEN_TARGET_INDEX]
    assert unique.unique is True
    assert [column.name for column in unique.columns] == module.OPEN_TARGET_COLUMNS
    assert module.normalized_sql(
        str(unique.dialect_options["postgresql"]["where"])
    ) == module.normalized_sql(module.OPEN_TARGET_WHERE)
    assert [column.name for column in indexes[module.SCENE_INDEX].columns] == [
        "scene",
        "status",
    ]


def test_modern_insert_targets_qc_schema_and_jsonb_on_postgres():
    from sqlalchemy import cast

    statement = QCAppeal.__table__.insert().values(
        id="x",
        evidence=cast("[]", postgresql.JSONB),
    )
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            schema_translate_map={None: "qc"},
            render_schema_translate=True,
        )
    )
    assert "qc.qc_appeals" in sql
    assert "CAST(%(param_1)s AS JSONB)" in sql
