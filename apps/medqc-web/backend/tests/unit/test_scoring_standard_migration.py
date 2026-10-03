"""迁移 62 评分标准三表合同：只用 fake inspector 与 SQLite，不连接真实数据库。"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


def _load_migration(filename, module_name):
    path = Path(__file__).resolve().parents[2] / "alembic/versions" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def special_report_migration():
    return _load_migration("20261003_000083_special_report_scoring_binding.py", "special_report_binding_migration")


def migration():
    return _load_migration("20260927_000062_scoring_standards.py", "scoring_standard_migration")


def _model_contract_specs():
    """ORM 模型对应“62 建表 + 后续增量迁移”的累计合同；目前只有 69 为评分条目加科室范围列。"""
    specs = copy.deepcopy(migration().SPECS)
    scope = _load_migration("20260928_000069_scoring_item_scope.py", "scoring_item_scope_migration")
    item_spec = specs[scope.TABLE]
    for name, (column_type, default) in scope.COLUMNS.items():
        size = getattr(column_type, "length", None)
        item_spec["columns"][name] = (type(column_type), size, False, default)
    item_spec["checks"].update(scope.CHECKS)
    return specs


def _type(spec):
    kind, size, _, _ = spec
    if kind is sa.String:
        return sa.String(size)
    if kind is sa.Numeric:
        return sa.NUMERIC(*size)
    return kind()


def deployed_table(module, schema, table):
    spec = module.SPECS[table]
    indexes = [
        # PostgreSQL 反射会带出唯一约束支撑索引
        {"name": name, "column_names": list(columns), "unique": True, "duplicates_constraint": name}
        for name, columns in spec["uniques"].items()
    ]
    for name, (columns, _predicate) in spec["indexes"].items():
        indexes.append({
            "name": name, "column_names": list(columns), "unique": True,
            "dialect_options": {
                "postgresql_where": "(((status)::text = 'active'::text) AND is_default)",
            },
        })
    return {
        "columns": {
            name: {"type": _type(column), "nullable": column[2], "default": column[3]}
            for name, column in spec["columns"].items()
        },
        "pk": {"name": spec["pk"], "constrained_columns": ["id"]},
        "uniques": [{"name": name, "column_names": list(columns)} for name, columns in spec["uniques"].items()],
        "indexes": indexes,
        "fks": [
            {
                "name": name, "constrained_columns": list(columns),
                # public 在 search_path 上时 PG 反射 referred_schema 为 None
                "referred_schema": None if schema == "public" else schema,
                "referred_table": module.STANDARDS, "referred_columns": ["id"],
                "options": {"ondelete": "CASCADE"},
            }
            for name, columns in spec["fks"].items()
        ],
        "checks": dict(spec["checks"]),
    }


def state(module, *, deployed):
    return {
        schema: {table: deployed_table(module, schema, table) for table in module.TABLES} if deployed else {}
        for schema in module.SCHEMAS
    }


class Inspector:
    def __init__(self, data):
        self.data = data

    def has_table(self, table, schema):
        return table in self.data[schema]

    def get_columns(self, table, schema):
        return [dict(name=name, **copy.copy(value)) for name, value in self.data[schema][table]["columns"].items()]

    def get_pk_constraint(self, table, schema):
        return self.data[schema][table]["pk"]

    def get_unique_constraints(self, table, schema):
        return self.data[schema][table]["uniques"]

    def get_indexes(self, table, schema):
        return self.data[schema][table]["indexes"]

    def get_foreign_keys(self, table, schema):
        return self.data[schema][table]["fks"]

    def get_check_constraints(self, table, schema):
        return [{"name": name, "sqltext": sql} for name, sql in self.data[schema][table]["checks"].items()]


def special_report_state(deployed):
    module = special_report_migration()
    data = state(migration(), deployed=True)
    for schema in module.SCHEMAS:
        if deployed:
            data[schema][module.TABLE] = {
                "columns": {name: {"type": _type(spec), "nullable": spec[2], "default": spec[3]}
                            for name, spec in module.COLUMNS.items()},
                "pk": {"name": "pk_qc_scoring_default_bindings", "constrained_columns": ["purpose", "execution_scene"]},
                "uniques": [], "indexes": [], "checks": dict(module.CHECKS),
                "fks": [{"name": "fk_qc_scoring_default_bindings_standard", "constrained_columns": ["standard_id"],
                         "referred_schema": schema, "referred_table": module.PARENT,
                         "referred_columns": ["id"], "options": {}}],
            }
    return data


@pytest.mark.parametrize("deployed", [False, True])
def test_special_report_migration_exact_baselines(deployed):
    assert special_report_migration().schema_state(Inspector(special_report_state(deployed))) == {
        "qc": deployed, "public": deployed,
    }


@pytest.mark.parametrize("drift", ["partial_schema", "parent_column", "binding_column", "reference_check", "foreign_key"])
def test_special_report_migration_rejects_unknown_baseline(drift):
    module = special_report_migration()
    data = special_report_state(True)
    binding = data["qc"][module.TABLE]
    if drift == "partial_schema":
        del data["qc"][module.TABLE]
    elif drift == "parent_column":
        data["qc"][module.PARENT]["columns"]["scene"]["type"] = sa.String(24)
    elif drift == "binding_column":
        binding["columns"]["version_seq"]["nullable"] = True
    elif drift == "reference_check":
        binding["checks"]["ck_qc_scoring_default_bindings_reference"] = "standard_version_seq > 0"
    else:
        binding["fks"][0]["referred_schema"] = "other"
    with pytest.raises(RuntimeError):
        module.schema_state(Inspector(data))


def test_special_report_migration_matches_orm():
    from app.database.models.qc import QCScoringDefaultBinding

    module = special_report_migration()
    columns = QCScoringDefaultBinding.__table__.columns
    assert set(columns.keys()) == set(module.COLUMNS)
    for name, (kind, size, nullable, default) in module.COLUMNS.items():
        assert isinstance(columns[name].type, kind)
        assert getattr(columns[name].type, "length", None) == size
        assert columns[name].nullable is nullable
        assert columns[name].server_default is default
    checks = {constraint.name: module._baseline().normalized_check(str(constraint.sqltext))
              for constraint in QCScoringDefaultBinding.__table__.constraints
              if isinstance(constraint, sa.CheckConstraint)}
    assert checks == {name: module._baseline().normalized_check(sql) for name, sql in module.CHECKS.items()}


class Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class Bind:
    def __init__(self, counts=None):
        self.counts = counts or {}
        self.queries = []

    def execute(self, statement):
        sql = str(statement)
        self.queries.append(sql)
        if sql.startswith("LOCK TABLE"):
            return None
        for (schema, table), count in self.counts.items():
            if f'"{schema}"."{table}"' in sql:
                return Scalar(count)
        return Scalar(0)


def fake(monkeypatch, module, data, counts=None):
    calls = []
    bind = Bind(counts)
    monkeypatch.setattr(module.sa, "inspect", lambda _: Inspector(data))
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    for operation in ("create_table", "create_index", "drop_index", "drop_table"):
        monkeypatch.setattr(
            module.op, operation,
            lambda *args, _operation=operation, **kwargs: calls.append((_operation, args, kwargs)),
        )
    return bind, calls


def test_upgrade_creates_three_tables_and_default_partial_index_in_both_schemas(monkeypatch):
    module = migration()
    assert module.revision == "20260927_000062"
    assert module.down_revision == "20260927_000061"
    _, calls = fake(monkeypatch, module, state(module, deployed=False))
    module.upgrade()
    creates = [(args, kwargs) for name, args, kwargs in calls if name == "create_table"]
    assert [(args[0], kwargs["schema"]) for args, kwargs in creates] == [
        (table, schema) for schema in module.SCHEMAS for table in module.TABLES
    ]
    for args, kwargs in creates:
        spec = module.SPECS[args[0]]
        columns = {item.name: item for item in args if isinstance(item, sa.Column)}
        assert set(columns) == set(spec["columns"])
        for name, (_, _, nullable, default) in spec["columns"].items():
            assert columns[name].nullable is nullable
            actual = None if columns[name].server_default is None else str(columns[name].server_default.arg)
            assert actual == default
        assert isinstance(columns["id"].type, sa.String)
        names = {item.name for item in args if isinstance(item, sa.Constraint)}
        assert {spec["pk"], *spec["uniques"], *spec["checks"], *spec["fks"]} <= names
        for fk in (item for item in args if isinstance(item, sa.ForeignKeyConstraint)):
            assert fk.ondelete == "CASCADE"
            assert fk.elements[0].target_fullname == f"{kwargs['schema']}.qc_scoring_standards.id"
    numeric = {item.name: item for item in creates[0][0] if isinstance(item, sa.Column)}["base_score"]
    assert (numeric.type.precision, numeric.type.scale) == (6, 2)
    indexes = [(args, kwargs) for name, args, kwargs in calls if name == "create_index"]
    assert [(args[0], args[1], args[2], kwargs["schema"], kwargs["unique"]) for args, kwargs in indexes] == [
        (module.DEFAULT_INDEX_NAME, module.STANDARDS, ["scene"], "qc", True),
        (module.DEFAULT_INDEX_NAME, module.STANDARDS, ["scene"], "public", True),
    ]
    assert str(indexes[0][1]["postgresql_where"]) == "status = 'active' AND is_default"


def test_upgrade_is_idempotent_when_fully_deployed(monkeypatch):
    module = migration()
    _, calls = fake(monkeypatch, module, state(module, deployed=True))
    module.upgrade()
    assert calls == []


def test_postgres_reflected_checks_defaults_and_predicate_match_contract(monkeypatch):
    """PG 反射形态：IN → = ANY(ARRAY[...])、btrim → TRIM(BOTH ... FROM col)、numeric 字面量、默认值括号。"""
    module = migration()
    data = state(module, deployed=True)
    ws = "' \t\n\r\f\v'::text"
    for schema in module.SCHEMAS:
        standards = data[schema][module.STANDARDS]
        checks = standards["checks"]
        checks["ck_qc_scoring_standards_scene"] = (
            "((scene)::text = ANY ((ARRAY['running'::character varying, 'final'::character varying, "
            "'outpatient'::character varying])::text[]))"
        )
        checks["ck_qc_scoring_standards_status"] = (
            "((status)::text = ANY ((ARRAY['draft'::character varying, 'active'::character varying, "
            "'archived'::character varying])::text[]))"
        )
        checks["ck_qc_scoring_standards_name_nonblank"] = f"(TRIM(BOTH {ws} FROM name) <> ''::text)"
        checks["ck_qc_scoring_standards_key_nonblank"] = f"(btrim((rule_set_key)::text, {ws}) <> ''::text)"
        checks["ck_qc_scoring_standards_veto_nonblank"] = f"(TRIM(BOTH {ws} FROM veto_grade) <> ''::text)"
        checks["ck_qc_scoring_standards_base_positive"] = "(base_score > (0)::numeric)"
        checks["ck_qc_scoring_standards_seq_positive"] = "(version_seq > 0)"
        checks["ck_qc_scoring_standards_default_active"] = (
            "(((status)::text = 'active'::text) OR (NOT is_default))"
        )
        checks["ck_qc_scoring_standards_activated_fields"] = (
            "(((status)::text = 'draft'::text) OR ((activated_by IS NOT NULL) AND (activated_at IS NOT NULL)))"
        )
        standards["columns"]["version_seq"]["default"] = "(1)"
        data[schema][module.GROUPS]["checks"]["ck_qc_scoring_groups_max_nonnegative"] = (
            "((max_deduction IS NULL) OR (max_deduction >= (0)::numeric))"
        )
        data[schema][module.ITEMS]["checks"]["ck_qc_scoring_items_deduction_nonnegative"] = (
            "(deduction >= (0)::numeric)"
        )
        data[schema][module.ITEMS]["checks"]["ck_qc_scoring_items_rule_nonblank"] = (
            f"(TRIM(BOTH {ws} FROM rule_id) <> ''::text)"
        )
    _, calls = fake(monkeypatch, module, data)
    module.upgrade()
    assert calls == []


@pytest.mark.parametrize("reflected", [
    "status = 'active' AND is_default",
    "(((status)::text = 'active'::text) AND is_default)",
    "(((status)::text = 'active'::text) AND (is_default = true))",
])
def test_partial_index_predicate_reflected_forms_accepted(monkeypatch, reflected):
    module = migration()
    data = state(module, deployed=True)
    for schema in module.SCHEMAS:
        data[schema][module.STANDARDS]["indexes"][-1]["dialect_options"] = {"postgresql_where": reflected}
    _, calls = fake(monkeypatch, module, data)
    module.upgrade()
    assert calls == []


def test_upgrade_rejects_partial_deployment_across_and_within_schemas(monkeypatch):
    module = migration()
    data = state(module, deployed=False)
    data["public"] = {table: deployed_table(module, "public", table) for table in module.TABLES}
    _, calls = fake(monkeypatch, module, data)
    with pytest.raises(RuntimeError, match="部署不一致"):
        module.upgrade()
    assert calls == []

    data = state(module, deployed=True)
    del data["qc"][module.ITEMS]
    _, calls = fake(monkeypatch, module, data)
    with pytest.raises(RuntimeError, match="只部署了"):
        module.upgrade()
    assert calls == []


@pytest.mark.parametrize("drift", [
    "extra_column", "missing_column", "numeric_scale", "float_base", "nullable_veto",
    "bad_pk", "missing_unique", "bad_unique", "missing_default_index", "default_index_not_partial",
    "default_index_wrong_predicate", "default_index_not_unique", "extra_index",
    "missing_fk", "fk_no_cascade", "fk_other_schema", "missing_check", "bad_check",
])
def test_upgrade_rejects_drift_before_ddl(monkeypatch, drift):
    module = migration()
    data = state(module, deployed=True)
    standards = data["qc"][module.STANDARDS]
    items = data["qc"][module.ITEMS]
    default_index = standards["indexes"][-1]
    if drift == "extra_column":
        standards["columns"]["extra"] = {"type": sa.Text(), "nullable": True, "default": None}
    elif drift == "missing_column":
        del items["columns"]["enabled"]
    elif drift == "numeric_scale":
        items["columns"]["deduction"]["type"] = sa.NUMERIC(6, 1)
    elif drift == "float_base":
        standards["columns"]["base_score"]["type"] = sa.Float()
    elif drift == "nullable_veto":
        standards["columns"]["veto_grade"]["nullable"] = True
    elif drift == "bad_pk":
        standards["pk"] = {"name": "pk_other", "constrained_columns": ["id"]}
    elif drift == "missing_unique":
        items["uniques"] = []
    elif drift == "bad_unique":
        standards["uniques"][0]["column_names"] = ["name"]
    elif drift == "missing_default_index":
        standards["indexes"] = standards["indexes"][:-1]
    elif drift == "default_index_not_partial":
        default_index["dialect_options"] = {}
    elif drift == "default_index_wrong_predicate":
        default_index["dialect_options"] = {"postgresql_where": "is_default"}
    elif drift == "default_index_not_unique":
        default_index["unique"] = False
    elif drift == "extra_index":
        items["indexes"].append({"name": "ix_extra", "column_names": ["rule_id"], "unique": False})
    elif drift == "missing_fk":
        items["fks"] = []
    elif drift == "fk_no_cascade":
        items["fks"][0]["options"] = {}
    elif drift == "fk_other_schema":
        items["fks"][0]["referred_schema"] = "public"
    elif drift == "missing_check":
        del standards["checks"]["ck_qc_scoring_standards_default_active"]
    else:
        standards["checks"]["ck_qc_scoring_standards_scene"] = "scene IN ('running', 'final')"
    _, calls = fake(monkeypatch, module, data)
    with pytest.raises(RuntimeError):
        module.upgrade()
    assert calls == []


def test_downgrade_rejects_rows_in_any_table(monkeypatch):
    module = migration()
    bind, calls = fake(
        monkeypatch, module, state(module, deployed=True), counts={("public", module.ITEMS): 1},
    )
    with pytest.raises(RuntimeError, match="public.qc_scoring_items.*拒绝降级"):
        module.downgrade()
    assert len([query for query in bind.queries if query.startswith("LOCK TABLE")]) == 6
    assert calls == []


def test_downgrade_empty_drops_children_first(monkeypatch):
    module = migration()
    _, calls = fake(monkeypatch, module, state(module, deployed=True))
    module.downgrade()
    assert [(name, args[0], kwargs["schema"]) for name, args, kwargs in calls] == [
        ("drop_table", module.ITEMS, "public"), ("drop_table", module.GROUPS, "public"),
        ("drop_index", module.DEFAULT_INDEX_NAME, "public"), ("drop_table", module.STANDARDS, "public"),
        ("drop_table", module.ITEMS, "qc"), ("drop_table", module.GROUPS, "qc"),
        ("drop_index", module.DEFAULT_INDEX_NAME, "qc"), ("drop_table", module.STANDARDS, "qc"),
    ]


def test_models_match_migration_contract():
    from app.database.models.qc import QCScoringGroup, QCScoringItem, QCScoringStandard

    module = migration()
    specs = _model_contract_specs()
    for model in (QCScoringStandard, QCScoringGroup, QCScoringItem):
        table = model.__table__
        spec = specs[table.name]
        assert set(table.c.keys()) == set(spec["columns"])
        for name, (kind, size, nullable, default) in spec["columns"].items():
            column = table.c[name]
            assert isinstance(column.type, kind) and column.nullable is nullable
            if kind is sa.String:
                assert column.type.length == size
            if kind is sa.Numeric:
                assert (column.type.precision, column.type.scale) == size
            actual_default = None if column.server_default is None else str(column.server_default.arg)
            assert actual_default == default
        checks = {
            item.name: module.normalized_check(str(item.sqltext))
            for item in table.constraints if isinstance(item, sa.CheckConstraint)
        }
        assert checks == {name: module.normalized_check(sql) for name, sql in spec["checks"].items()}
        uniques = {
            item.name: [column.name for column in item.columns]
            for item in table.constraints if isinstance(item, sa.UniqueConstraint)
        }
        assert uniques == spec["uniques"]
        fks = {item.name: item for item in table.constraints if isinstance(item, sa.ForeignKeyConstraint)}
        assert set(fks) == set(spec["fks"])
        assert all(fk.ondelete == "CASCADE" for fk in fks.values())
        indexes = {item.name: item for item in table.indexes}
        assert set(indexes) == set(spec["indexes"])
        for name, (columns, predicate) in spec["indexes"].items():
            assert [column.name for column in indexes[name].columns] == columns
            assert indexes[name].unique
            assert str(indexes[name].dialect_options["postgresql"]["where"]) == predicate


def _standard_values(standard_id, *, scene="running", status="draft", is_default=False, name=None):
    now = sa.func.current_timestamp()
    values = dict(
        id=standard_id, name=name or f"标准{standard_id}", scene=scene, rule_set_key="luxian_0609_qc_v1",
        status=status, is_default=is_default, base_score=100, grade_bands_json="[]", veto_grade="丙",
        created_by="u-1", created_at=now, updated_by="u-1", updated_at=now,
    )
    if status != "draft":
        values.update(activated_by="u-1", activated_at=now)
    return values


def test_model_partial_unique_index_and_checks_in_sqlite():
    from app.database.models.qc import QCScoringGroup, QCScoringItem, QCScoringStandard

    engine = sa.create_engine("sqlite://")
    for model in (QCScoringStandard, QCScoringGroup, QCScoringItem):
        model.__table__.create(engine)
    table = QCScoringStandard.__table__
    with engine.begin() as connection:
        connection.execute(table.insert().values(**_standard_values("a", status="active", is_default=True)))
        connection.execute(table.insert().values(**_standard_values("b", status="active")))
        connection.execute(table.insert().values(**_standard_values("c", scene="final", status="active", is_default=True)))
        connection.execute(table.insert().values(**_standard_values("d", status="archived")))
    bad_rows = [
        _standard_values("e", status="active", is_default=True),  # 同场景第二个默认
        _standard_values("f", status="draft", is_default=True),  # 草稿不能是默认
        _standard_values("g", scene="other"),
        {**_standard_values("h"), "base_score": 0},
        {**_standard_values("i"), "status": "active"},  # 缺启用人/时间
        _standard_values("j", name="标准a"),  # (name, scene) 重复
    ]
    for values in bad_rows:
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as connection:
                connection.execute(table.insert().values(**values))
    items = QCScoringItem.__table__
    base_item = dict(id="i-1", standard_id="a", group_name="病案首页", rule_id="LX0609-001", deduction=2)
    with engine.begin() as connection:
        connection.execute(items.insert().values(**base_item))
    for values in ({**base_item, "id": "i-2"}, {**base_item, "id": "i-3", "rule_id": "LX0609-002", "deduction": -1}):
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as connection:
                connection.execute(items.insert().values(**values))
    engine.dispose()
