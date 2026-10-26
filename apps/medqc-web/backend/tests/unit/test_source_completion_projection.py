"""结构化死亡字段与医嘱业务时间不得在保存、Bundle 和读取时静默丢失。"""

from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.database.models.cdm import DeathRecord
from app.services import etl_sync
from app.services.bundles import assembly, emr_view
from app.services.document_assembly.assembler import build_document_select_columns
from app.services.luxian_0609 import source_evidence_reader as reader


ORDER_TIMES = (
    "planned_end_datetime", "reviewed_datetime", "carried_datetime", "canceled_datetime",
)
DEATH_FIELDS = ("death_datetime", "admission_condition", "treatment_course", "death_reason")


@pytest.mark.parametrize("table", ("inpat_drug_order", "inpat_nondrug_order", "death_record", "discharge_record"))
def test_business_fields_survive_select_inventory_and_emr_without_changing_document_clock(table):
    fields = (DEATH_FIELDS if table == "death_record" else (
        "record_content", "admission_condition", "treatment_course", "discharge_order", "chief_physician_sign_datetime", "v2_schema",
    ) if table == "discharge_record" else ORDER_TIMES)
    row = {
        "document_id": "synthetic-document", "order_id": "synthetic-order",
        "record_content": "合成正文", "generic_name": "合成药品", "order_name": "合成检查",
    }
    for index, field in enumerate(fields):
        row[field] = (datetime(2026, 1, index + 1, tzinfo=timezone.utc)
                      if field.endswith("datetime") else "合成结构化内容" * (index + 1))
    if table == "discharge_record":
        row["v2_schema"] = '{"synthetic":"extra JSON"}'
    selected = build_document_select_columns(table, set(row))
    assert set(fields).issubset(selected)
    projected = {field: row[field] for field in selected}
    entry = assembly._inventory_entry(table_name=table, row=projected)
    normalized = emr_view._normalize_source_document(raw_doc=entry, index=0, execution_domain="course")
    for field in fields:
        expected = row[field].isoformat() if isinstance(row[field], datetime) else row[field]
        assert entry[field] == expected
        assert normalized[field] == expected
    assert entry["record_time"] == entry["submit_time"] == entry["display_time"] == ""
    assert normalized["record_time"] == normalized["submit_time"] == ""
    assert not entry.get("stop_time")


def test_death_structured_columns_and_rule_whitelist_are_complete():
    columns = DeathRecord.__table__.columns
    assert set(DEATH_FIELDS).issubset(columns.keys())
    assert columns["death_datetime"].type.timezone is True
    assert set(DEATH_FIELDS).issubset(reader._NATIVE_SOURCE_FIELDS["death_record"])
    assert set(DEATH_FIELDS).issubset(reader._SNAPSHOT_SOURCE_FIELDS["death_record"])


def test_death_sections_are_available_without_body_and_existing_body_is_not_replaced():
    row = {"document_id": "synthetic", "death_datetime": "2026-01-01T01:00:00+08:00",
           "admission_condition": "合成入院情况", "treatment_course": "合成诊疗经过", "death_reason": "合成原因"}
    entry = assembly._inventory_entry(table_name="death_record", row=row)
    assert entry["hit"] is True
    assert {section["source_field"] for section in entry["sections"]} == set(DEATH_FIELDS)
    assert all(value in entry["content"] for key, value in row.items() if key != "document_id")
    row["record_content"] = "完整原始正文，保留其内容和签名。"
    entry = assembly._inventory_entry(table_name="death_record", row=row)
    assert entry["content"] == row["record_content"]
    assert all(entry[field] == row[field] for field in DEATH_FIELDS)


@pytest.mark.parametrize("field", DEATH_FIELDS)
def test_death_missing_target_column_is_rejected_before_any_write(field):
    row = {field: "2026-01-01T01:00:00+08:00" if field.endswith("datetime") else "合成内容"}
    if field == "death_datetime":
        row = {"death_time": row[field]}
    with pytest.raises(ValueError, match="结构化字段未保留"):
        etl_sync._validate_document_field_preservation(
            table_name="death_record", normalized=row, existing_columns={"record_content"},
        )


def test_unmigrated_death_table_cannot_delete_previous_visit_rows(monkeypatch):
    from app.services.case_identity import CaseRef

    keys = ["institute_id", "patient_id", "visit_id", "document_id"]
    monkeypatch.setattr(etl_sync, "_get_local_table_meta", lambda *_: (
        "cdm", [*keys, "record_content"], keys,
    ))

    class NoWrites:
        def execute(self, *_, **__):
            raise AssertionError("缺列时不得执行写 SQL，尤其不能先删除旧资料")

        def commit(self):
            raise AssertionError("禁止提交")

    source = dict(zip(keys, ("H", "P", "V", "D")))
    source.update(death_time="2026-01-01T00:00:00+08:00", treatment_course="合成诊疗经过")
    with pytest.raises(ValueError, match="结构化字段未保留"):
        etl_sync.upsert_to_local(
            "death_record", [source], keys, session=NoWrites(),
            replace_case_refs=[CaseRef("H", "P", "V")],
        )


@pytest.mark.parametrize("mode,schema", (("split", "cdm"), ("single", "public")))
@pytest.mark.parametrize("existing", ((), DEATH_FIELDS))
def test_death_migration_only_adds_missing_nullable_columns_offline(monkeypatch, mode, schema, existing):
    path = Path(__file__).parents[2] / "alembic/versions/20261023_000052_death_structured_fields.py"
    spec = spec_from_file_location("death_structured_migration", path)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    monkeypatch.setenv("DB_SCHEMA_MODE", mode)
    monkeypatch.setattr(migration.sa, "inspect", lambda _: SimpleNamespace(
        get_schema_names=lambda: [schema], get_table_names=lambda **_: ["death_record"],
        get_columns=lambda *_, **__: [{"name": name} for name in existing],
    ))
    output = StringIO()
    with Operations.context(MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output},
    )):
        migration.upgrade()
    sql = output.getvalue()
    assert sql.count("ADD COLUMN") == (0 if existing else 4)
    if not existing:
        assert f"{schema}.death_record ADD COLUMN death_datetime TIMESTAMP WITH TIME ZONE" in sql
        assert all(f"ADD COLUMN {field} TEXT" in sql for field in DEATH_FIELDS[1:])
    assert not any(token in sql for token in ("NOT NULL", "UPDATE ", "DELETE ", "DROP "))
    assert migration.down_revision == "20261022_000051"
    with pytest.raises(RuntimeError, match="不支持自动删除"):
        migration.downgrade()


def test_dual_source_death_fill_preserves_conflicts_and_maps_source_time():
    from app.services import dual_source_sync as policy
    from app.services.dual_source_write_policy import build_write_batch

    case = {"sample": "C01", "institute_id": "H", "patient_id": "P", "visit_id": "V"}
    before = {**case, "document_id": "D", "record_content": "完整原始正文", "death_reason": "已有原因"}
    source = {**before, "death_time": "2026-01-01T01:00:00+08:00", "death_reason": "冲突原因",
              "admission_condition": "合成入院情况", "treatment_course": "合成诊疗经过"}
    plan = policy.plan_table("death_record", case,
        policy.SourceSnapshot("clinical_data", (source,)), policy.SourceSnapshot("homology"),
        policy.SourceSnapshot("local", (before,)), source_institutes={s: "H" for s in policy.SOURCES})
    keys = [*policy.IDENTITY_FIELDS, "document_id"]
    columns = {key: {"data_type": "text", "is_nullable": "NO" if key in keys else "YES"}
               for key in (*keys, *DEATH_FIELDS, "record_content")}
    columns["death_datetime"]["data_type"] = "timestamp with time zone"
    batch = build_write_batch("death_record", plan, case, columns, keys, [before])
    assert len(batch.operations) == 1
    assert set(batch.operations[0]["values"]) == set(DEATH_FIELDS) - {"death_reason"}
    assert batch.operations[0]["values"]["death_datetime"].isoformat() == source["death_time"]
    assert "death_reason" in batch.records[0]["conflicts"]
    assert before["death_reason"] == "已有原因"
