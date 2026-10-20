"""病理肉眼所见长文本回归；仅编译 SQL，不连接数据库。"""

import importlib.util
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.dialects import postgresql

from app.database.models.cdm import PathologyExamReport


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic/versions/20261016_000048_pathology_eye_findings_text.py"
)


def test_model_accepts_complete_378_character_eye_findings():
    table = PathologyExamReport.__table__
    assert isinstance(table.c.eye_findings.type, sa.Text)
    findings = "合成病理描述" * 63
    assert len(findings) == 378
    statement = table.insert().values(
        institute_id="H1", patient_id="P1", visit_id="V1",
        pathology_exam_id="E1", eye_findings=findings,
    ).compile(dialect=postgresql.dialect())
    assert statement.params["eye_findings"] == findings
    for name in ("institute_id", "patient_id", "visit_id", "pathology_exam_id"):
        assert table.c[name].type.length == 100


@pytest.fixture
def migration():
    spec = importlib.util.spec_from_file_location("pathology_eye_findings", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("schemas", [("cdm",), ("public",), ("cdm", "public")])
@pytest.mark.parametrize("existing_type", [sa.String(100), sa.Text(), sa.String()])
def test_upgrade_only_widens_bounded_eye_findings(
    migration, monkeypatch, schemas, existing_type
):
    inspector = SimpleNamespace(
        get_schema_names=lambda: list(schemas),
        get_table_names=lambda schema: ["pathology_exam_report"],
        get_columns=lambda table, schema: [
            {"name": "eye_findings", "type": existing_type},
            {"name": "patient_id", "type": sa.String(100)},
        ],
    )
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: inspector)
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    with Operations.context(context):
        migration.upgrade()
    statements = output.getvalue().strip()
    if existing_type.length is None:
        assert statements == ""
    else:
        assert statements == "\n\n".join(
            f"ALTER TABLE {schema}.pathology_exam_report ALTER COLUMN eye_findings TYPE TEXT;"
            for schema in schemas
        )
    assert migration.revision == "20261016_000048"
    assert migration.down_revision == "20261006_000047"


def test_upgrade_skips_absent_optional_pathology_table(migration, monkeypatch):
    inspector = SimpleNamespace(
        get_schema_names=lambda: ["cdm", "public"],
        get_table_names=lambda schema: [],
    )
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: inspector)
    output = StringIO()
    with Operations.context(MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )):
        migration.upgrade()
    assert output.getvalue() == ""


def test_downgrade_refuses_to_truncate_saved_findings(migration):
    with pytest.raises(RuntimeError, match="不支持自动降级"):
        migration.downgrade()
