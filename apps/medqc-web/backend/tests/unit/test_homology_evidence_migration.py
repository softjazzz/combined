"""仅编译增列 SQL，验证 public/cdm 迁移兼容性；不连接数据库。"""

import importlib.util
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.database.models.cdm import InpatDrugOrder, InpatNondrugOrder, LabtestItemReport


@pytest.fixture
def migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20261016_000049_homology_evidence_fields.py"
    spec = importlib.util.spec_from_file_location("homology_evidence", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("schemas", [("cdm",), ("public",), ("cdm", "public")])
@pytest.mark.parametrize("already_added", [False, True])
def test_upgrade_only_adds_missing_nullable_columns(migration, monkeypatch, schemas, already_added):
    fields = {
        "inpat_drug_order": ["reviewed_datetime", "carried_datetime", "canceled_datetime", "planned_end_datetime"],
        "inpat_nondrug_order": ["reviewed_datetime", "carried_datetime", "canceled_datetime"],
        "labtest_item_report": ["report_status"],
    }
    inspector = SimpleNamespace(
        get_schema_names=lambda: list(schemas),
        get_table_names=lambda schema: list(fields),
        get_columns=lambda table, schema: [
            {"name": name} for name in (["institute_id", *fields[table]] if already_added else ["institute_id"])
        ],
    )
    monkeypatch.setattr(migration.sa, "inspect", lambda _: inspector)
    output = StringIO()
    with Operations.context(MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )):
        migration.upgrade()
    sql = output.getvalue()
    if already_added:
        assert sql == ""
    else:
        assert sql.count("ADD COLUMN") == len(schemas) * 8
        assert "DROP" not in sql and "NOT NULL" not in sql
        assert "UPDATE " not in sql and "DELETE " not in sql
        for schema in schemas:
            assert f"ALTER TABLE {schema}.inpat_drug_order ADD COLUMN planned_end_datetime TIMESTAMP WITH TIME ZONE" in sql
            assert f"ALTER TABLE {schema}.labtest_item_report ADD COLUMN report_status TEXT" in sql
    assert migration.down_revision == "20261016_000048"


def test_upgrade_skips_absent_tables(migration, monkeypatch):
    inspector = SimpleNamespace(
        get_schema_names=lambda: ["public"], get_table_names=lambda schema: []
    )
    monkeypatch.setattr(migration.sa, "inspect", lambda _: inspector)
    output = StringIO()
    with Operations.context(MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )):
        migration.upgrade()
    assert output.getvalue() == ""


def test_model_matches_new_evidence_columns_and_keeps_primary_keys():
    for model in (InpatDrugOrder, InpatNondrugOrder):
        table = model.__table__
        for name in ("reviewed_datetime", "carried_datetime", "canceled_datetime"):
            assert table.c[name].nullable
            assert not table.c[name].type.timezone
        assert set(table.primary_key.columns.keys()) == {"institute_id", "patient_id", "visit_id", "order_id"}
    assert InpatDrugOrder.__table__.c.planned_end_datetime.type.timezone
    assert LabtestItemReport.__table__.c.report_status.nullable


def test_downgrade_does_not_discard_execution_evidence(migration):
    with pytest.raises(RuntimeError, match="不支持自动删除"):
        migration.downgrade()
