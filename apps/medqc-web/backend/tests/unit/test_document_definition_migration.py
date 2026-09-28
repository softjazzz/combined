from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


def migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260928_000070_document_definitions.py"
    spec = importlib.util.spec_from_file_location("document_definition_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _type(spec):
    kind, length = spec
    return kind(length) if length else kind()


def _deployed(module):
    return {
        "exists": True,
        "columns": {
            name: {"type": _type(spec), "nullable": False, "default": None}
            for name, spec in module.COLUMNS.items()
        },
        "pk": {"name": module.PK_NAME, "constrained_columns": ["id"]},
        "uniques": [{"name": module.UNIQUE_NAME, "column_names": ["code"]}],
        "indexes": [
            {"name": module.CREATED_INDEX, "column_names": ["created_at", "code"], "unique": False},
            {"name": module.BATCH_INDEX, "column_names": ["import_batch_id"], "unique": False},
        ],
        "checks": dict(module.CHECKS),
    }


class Inspector:
    def __init__(self, data): self.data = data
    def has_table(self, _table, schema): return self.data[schema]["exists"]
    def get_columns(self, _table, schema):
        return [dict(name=name, **copy.copy(value)) for name, value in self.data[schema]["columns"].items()]
    def get_pk_constraint(self, _table, schema): return self.data[schema]["pk"]
    def get_unique_constraints(self, _table, schema): return self.data[schema]["uniques"]
    def get_indexes(self, _table, schema): return self.data[schema]["indexes"]
    def get_check_constraints(self, _table, schema):
        return [{"name": name, "sqltext": sql} for name, sql in self.data[schema]["checks"].items()]


class Scalar:
    def __init__(self, value): self.value = value
    def scalar_one(self): return self.value


class Bind:
    def __init__(self, counts=None):
        self.counts = counts or {}
        self.queries = []

    def execute(self, statement):
        sql = str(statement)
        self.queries.append(sql)
        if sql.startswith("LOCK TABLE"):
            return None
        for schema, count in self.counts.items():
            if f'"{schema}"."qc_document_definitions"' in sql:
                return Scalar(count)
        raise AssertionError(sql)


def _state(module, deployed):
    return {schema: _deployed(module) if deployed else {"exists": False} for schema in module.SCHEMAS}


def _fake(monkeypatch, module, data, counts=None):
    calls = []
    bind = Bind(counts)
    monkeypatch.setattr(module.sa, "inspect", lambda _: Inspector(data))
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    for operation in ("create_table", "create_index", "drop_index", "drop_table"):
        monkeypatch.setattr(module.op, operation, lambda *args, _op=operation, **kwargs: calls.append((_op, args, kwargs)))
    return bind, calls


def test_upgrade_creates_exact_table_in_both_schemas(monkeypatch):
    module = migration()
    assert module.revision == "20260928_000070" and module.down_revision == "20260928_000069"
    _, calls = _fake(monkeypatch, module, _state(module, False))
    module.upgrade()
    creates = [(args, kwargs) for op, args, kwargs in calls if op == "create_table"]
    assert [kwargs["schema"] for _, kwargs in creates] == ["qc", "public"]
    columns = {item.name: item for item in creates[0][0] if isinstance(item, sa.Column)}
    assert set(columns) == set(module.COLUMNS)
    indexes = [(args[0], args[2], kwargs["schema"]) for op, args, kwargs in calls if op == "create_index"]
    assert indexes == [
        (module.CREATED_INDEX, ["created_at", "code"], "qc"),
        (module.BATCH_INDEX, ["import_batch_id"], "qc"),
        (module.CREATED_INDEX, ["created_at", "code"], "public"),
        (module.BATCH_INDEX, ["import_batch_id"], "public"),
    ]


def test_upgrade_is_idempotent_and_rejects_partial_schema(monkeypatch):
    module = migration()
    _, calls = _fake(monkeypatch, module, _state(module, True))
    module.upgrade()
    assert calls == []
    partial = _state(module, False)
    partial["qc"] = _deployed(module)
    _, calls = _fake(monkeypatch, module, partial)
    with pytest.raises(RuntimeError, match="部署不一致"):
        module.upgrade()
    assert calls == []


def test_existing_contract_drift_is_rejected(monkeypatch):
    module = migration()
    data = _state(module, True)
    data["qc"]["columns"]["code"]["nullable"] = True
    _, calls = _fake(monkeypatch, module, data)
    with pytest.raises(RuntimeError, match="合同漂移"):
        module.upgrade()
    assert calls == []


@pytest.mark.parametrize("drift", ["length", "default", "pk", "unique", "index", "check"])
def test_each_contract_family_drift_is_rejected(monkeypatch, drift):
    module = migration()
    data = _state(module, True)
    target = data["qc"]
    if drift == "length":
        target["columns"]["code"]["type"] = sa.String(63)
    elif drift == "default":
        target["columns"]["name"]["default"] = "x"
    elif drift == "pk":
        target["pk"]["constrained_columns"] = ["code"]
    elif drift == "unique":
        target["uniques"] = []
    elif drift == "index":
        target["indexes"][0]["column_names"] = ["code"]
    else:
        target["checks"].pop("ck_qc_document_definitions_code_nonblank")
    _, calls = _fake(monkeypatch, module, data)
    with pytest.raises(RuntimeError):
        module.upgrade()
    assert calls == []


def test_postgres_reflected_nonblank_checks_match_contract(monkeypatch):
    module = migration()
    data = _state(module, True)
    ws = "' \t\n\r\f\v'::text"
    fields = {
        "ck_qc_document_definitions_code_nonblank": "code",
        "ck_qc_document_definitions_name_nonblank": "name",
        "ck_qc_document_definitions_category_nonblank": "category",
        "ck_qc_document_definitions_template_nonblank": "template_content",
        "ck_qc_document_definitions_creator_nonblank": "created_by",
    }
    for schema in module.SCHEMAS:
        data[schema]["checks"] = {
            name: f"(btrim(({field})::text, {ws}) <> ''::text)"
            for name, field in fields.items()
        }
    _, calls = _fake(monkeypatch, module, data)
    module.upgrade()
    assert calls == []


def test_downgrade_refuses_data_before_any_drop(monkeypatch):
    module = migration()
    bind, calls = _fake(monkeypatch, module, _state(module, True), {"qc": 0, "public": 1})
    with pytest.raises(RuntimeError, match="拒绝降级"):
        module.downgrade()
    assert not [call for call in calls if call[0].startswith("drop")]
    assert bind.queries[:2] == [
        'LOCK TABLE "qc"."qc_document_definitions" IN ACCESS EXCLUSIVE MODE',
        'LOCK TABLE "public"."qc_document_definitions" IN ACCESS EXCLUSIVE MODE',
    ]


def test_downgrade_drops_empty_schemas_in_reverse_order(monkeypatch):
    module = migration()
    _, calls = _fake(monkeypatch, module, _state(module, True), {"qc": 0, "public": 0})
    module.downgrade()
    drops = [(op, args[0], kwargs["schema"]) for op, args, kwargs in calls if op.startswith("drop")]
    assert drops == [
        ("drop_index", module.BATCH_INDEX, "public"),
        ("drop_index", module.CREATED_INDEX, "public"),
        ("drop_table", module.TABLE, "public"),
        ("drop_index", module.BATCH_INDEX, "qc"),
        ("drop_index", module.CREATED_INDEX, "qc"),
        ("drop_table", module.TABLE, "qc"),
    ]
