"""病程签名迁移与客户机独立升级脚本必须遵循同一字段合同。"""

import importlib.util
from io import StringIO
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations

from test_course_signature_sync import FIELDS


@pytest.fixture
def migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20261020_000050_course_signature_fields.py"
    spec = importlib.util.spec_from_file_location("course_signature_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("mode,schema", (("split", "cdm"), ("single", "public")))
@pytest.mark.parametrize("already_added", (False, True))
def test_upgrade_adds_only_missing_nullable_fields_in_local_schema(migration, monkeypatch, mode, schema, already_added):
    monkeypatch.setenv("DB_SCHEMA_MODE", mode)
    inspector = SimpleNamespace(
        get_schema_names=lambda: ["cdm", "public", "qc"],
        get_table_names=lambda schema: list(FIELDS),
        get_columns=lambda table, schema: [{"name": c} for c in (FIELDS[table] if already_added else ("document_id",))],
    )
    monkeypatch.setattr(migration.sa, "inspect", lambda _: inspector)
    output = StringIO()
    with Operations.context(MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output},
    )):
        migration.upgrade()
    sql = output.getvalue()
    if already_added:
        assert sql == ""
    else:
        assert sql.count("ADD COLUMN") == 11
        assert sql.count("TIMESTAMP WITH TIME ZONE") == 4
        assert sql.count(" TEXT") == 7
        assert all(f"ALTER TABLE {schema}.{table} " in sql for table in FIELDS)
        other = "public" if schema == "cdm" else "cdm"
        assert f"ALTER TABLE {other}." not in sql
        assert not any(token in sql for token in ("NOT NULL", "DROP ", "UPDATE ", "DELETE "))
    assert migration.TABLE_COLUMNS == FIELDS
    assert migration.down_revision == "20261016_000049"


@pytest.mark.parametrize("missing_schema", (True, False))
def test_missing_target_is_detected_before_any_schema_change(migration, monkeypatch, missing_schema):
    monkeypatch.setenv("DB_SCHEMA_MODE", "split")
    inspector = SimpleNamespace(
        get_schema_names=lambda: [] if missing_schema else ["cdm"],
        get_table_names=lambda schema: ["daily_course_record"],
    )
    monkeypatch.setattr(migration.sa, "inspect", lambda _: inspector)
    output = StringIO()
    with Operations.context(MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output},
    )):
        with pytest.raises(RuntimeError, match="缺少"):
            migration.upgrade()
    assert output.getvalue() == ""


def test_migration_does_not_drop_preexisting_signatures(migration):
    with pytest.raises(RuntimeError, match="不支持自动删除"):
        migration.downgrade()


@pytest.fixture
def customer_upgrade():
    path = Path(__file__).resolve().parents[3] / "scripts/customer-course-signature-upgrade.ps1"
    text = path.read_text(encoding="utf-8")
    python = re.search(r"(?ms)^    @'\n(.*?)\n'@ \|", text).group(1)
    namespace = {"__name__": "customer_signature_upgrade"}
    exec(compile(python, str(path), "exec"), namespace)
    return namespace


@pytest.mark.parametrize("mode,schema", (("split", "cdm"), ("single", "public")))
def test_customer_script_matches_migration_and_verifies_columns_without_stamping_revision(
    customer_upgrade, tmp_path, monkeypatch, capsys, mode, schema,
):
    (tmp_path / ".env").write_text(
        f"DATABASE_URL=postgresql://tester:synthetic@127.0.0.1:5432/medqc\nDB_SCHEMA_MODE={mode}\n",
        encoding="utf-8",
    )
    statements = []

    class Cursor:
        table = None

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, sql, params=None):
            statements.append(sql)
            if params and "information_schema.columns" in sql:
                assert params[0] == schema
                self.table = params[1]

        def fetchone(self):
            return ("present",)

        def fetchall(self):
            return [(name, "timestamp with time zone" if name.endswith("_datetime") else "text", "YES")
                    for name in FIELDS[self.table]]

    class Connection(Cursor):
        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr(customer_upgrade["psycopg2"], "connect", lambda **_: Connection())
    customer_upgrade["main"](tmp_path)
    assert customer_upgrade["TABLE_COLUMNS"] == FIELDS
    assert len([s for s in statements if s.startswith("ALTER TABLE")]) == 3
    assert all(f'"{schema}".' in s for s in statements if s.startswith("ALTER TABLE"))
    assert not any("alembic_version" in s or s.startswith(("UPDATE ", "DELETE ")) for s in statements)
    output = capsys.readouterr().out
    assert "UPGRADE_OK" in output and "synthetic" not in output


@pytest.mark.parametrize("url", (
    "postgresql://tester:synthetic@192.0.2.1:5432/medqc",
    "postgresql://tester:synthetic@127.0.0.1:5432/clinical_data",
))
def test_customer_script_never_connects_to_hospital_source(customer_upgrade, tmp_path, monkeypatch, url):
    (tmp_path / ".env").write_text(f"DATABASE_URL={url}\nDB_SCHEMA_MODE=split\n", encoding="utf-8")
    def forbidden(**_):
        pytest.fail("不得连接源库")
    monkeypatch.setattr(customer_upgrade["psycopg2"], "connect", forbidden)
    with pytest.raises(RuntimeError, match="local PostgreSQL"):
        customer_upgrade["main"](tmp_path)
