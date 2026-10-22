"""出院签署时间与二级结构化原样保留，不升级为文书记录/提交时间。"""

import json

import pytest
from app.database.models.cdm import DischargeRecord
from app.services import etl_sync, dual_source_sync as dual
from app.services.document_assembly import assemble_document
from app.services.document_assembly.assembler import extract_document_identity_metadata

CASE = {"institute_id": "H", "patient_id": "P", "visit_id": "V"}
TIME = "2026-10-01T00:00:00+08:00"
COLUMNS = (
    *CASE,
    "document_id",
    "record_time",
    "submit_datetime",
    "record_content",
    "chief_physician_sign",
    "chief_physician_sign_datetime",
    "v2_schema",
)


class Capture:
    def __init__(self):
        self.rows = []

    def execute(self, statement, params):
        assert str(statement).startswith("INSERT INTO")
        self.rows.extend(params if isinstance(params, list) else [params])


def save(monkeypatch, extra, missing=()):
    columns = [k for k in COLUMNS if k not in missing]
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda *_: ("cdm", columns, [*CASE, "document_id"]),
    )
    capture = Capture()
    assert (
        etl_sync.upsert_to_local(
            "discharge_record",
            [
                {
                    **CASE,
                    "document_id": "D",
                    "record_time": None,
                    "submit_time": None,
                    **extra,
                }
            ],
            [],
            session=capture,
        )
        == 1
    )
    return capture.rows[0]


def test_model_has_nullable_signature_clock_and_unbounded_json_text():
    columns = DischargeRecord.__table__.columns
    assert columns["chief_physician_sign_datetime"].nullable
    assert columns["chief_physician_sign_datetime"].type.timezone
    assert str(columns["v2_schema"].type) == "TEXT"
    assert columns["v2_schema"].nullable


@pytest.mark.parametrize(
    "alias", ["cheifphy_sign_time", "chief_physician_sign_datetime"]
)
@pytest.mark.parametrize(
    "payload",
    [
        None,
        {
            "treatment_course": [{"original_text": "合成章节。"}],
            "extra": {"complete": True},
        },
    ],
)
def test_insert_keeps_signature_and_entire_json_without_inventing_document_clock(
    monkeypatch, alias, payload
):
    raw = json.dumps(payload, ensure_ascii=False) if payload else None
    row = save(monkeypatch, {alias: TIME, "v2_schema": raw})
    assert row["chief_physician_sign_datetime"] == TIME
    assert row.get("record_time") is None and row.get("submit_datetime") is None
    if payload:
        assert json.loads(row["v2_schema"]) == payload
    assert not assemble_document("discharge_record", row).record_time
    assert not assemble_document("discharge_record", row).submit_time


@pytest.mark.parametrize(
    "field,value", [("chief_physician_sign_datetime", TIME), ("v2_schema", '{"x":1}')]
)
def test_old_schema_rejects_silent_discard_before_any_insert(monkeypatch, field, value):
    raw = (
        {"cheifphy_sign_time": value} if field.endswith("_datetime") else {field: value}
    )
    with pytest.raises(ValueError, match=field):
        save(monkeypatch, raw, (field,))


def test_dict_json_is_encoded_for_real_text_column(monkeypatch):
    payload = {"record_content": [{"original_text": "完整正文"}], "other": [1, 2, None]}
    row = save(monkeypatch, {"v2_schema": payload})
    assert isinstance(row["v2_schema"], str)
    assert json.loads(row["v2_schema"]) == payload


def test_dual_source_projection_retains_signature_and_json_into_model_columns():
    raw = {
        **CASE,
        "document_id": "D",
        "cheifphy_sign_time": TIME,
        "v2_schema": '{"extra":[1,2]}',
    }
    candidate = dual.plan_table(
        "discharge_record",
        CASE,
        dual.SourceSnapshot("clinical_data", (raw,)),
        dual.SourceSnapshot("homology"),
        dual.SourceSnapshot("local"),
        source_institutes={"clinical_data": "H", "homology": "H", "local": "H"},
    ).candidates[0]
    columns = {k: "text" for k in COLUMNS}
    columns["chief_physician_sign_datetime"] = "timestamp with time zone"
    result = dual.project_candidate(candidate, CASE, columns)
    assert "chief_physician_sign_datetime" not in result.unmapped_fields
    assert "v2_schema" not in result.unmapped_fields
    assert json.loads(result.values["v2_schema"]) == {"extra": [1, 2]}
    assert result.values["chief_physician_sign_datetime"] == TIME
    assert "record_time" not in result.values and "submit_datetime" not in result.values


def test_chief_signature_time_only_attaches_to_chief_signer():
    metadata = extract_document_identity_metadata(
        {
            "chief_physician_sign": "合成主任",
            "resident_physician_sign": "合成住院",
            "chief_physician_sign_datetime": TIME,
        }
    )
    chief = next(s for s in metadata["signatures"] if s["role"] == "chief_physician")
    assert chief["signed_at"] == TIME
    assert all(
        "signed_at" not in s
        for s in metadata["signatures"]
        if s["role"] != "chief_physician"
    )


@pytest.mark.parametrize("with_name", [False, True])
def test_bundle_keeps_independent_signature_clock_even_without_signer(with_name):
    from app.services.bundles.assembly import _inventory_entry
    from app.services.bundles.emr_view import (
        _normalize_source_document,
        _normalize_source_document_summary,
    )

    row = {
        "document_id": "D",
        "chief_physician_sign_datetime": TIME,
        "record_content": "合成出院记录。",
    }
    if with_name:
        row["chief_physician_sign"] = "合成主任"
    entry = _inventory_entry(table_name="discharge_record", row=row)
    assert entry["chief_physician_sign_datetime"] == TIME
    assert entry["record_time"] == "" and not entry["display_time"]
    for normalize in (_normalize_source_document, _normalize_source_document_summary):
        projected = normalize(raw_doc=entry, index=0, execution_domain="terminal")
        assert projected["chief_physician_sign_datetime"] == TIME
        assert projected["record_time"] == ""


@pytest.mark.parametrize("mode,schema", [("split", "cdm"), ("single", "public")])
@pytest.mark.parametrize(
    "existing", [(), ("chief_physician_sign_datetime", "v2_schema")]
)
def test_migration_only_adds_missing_nullable_columns(
    monkeypatch, mode, schema, existing
):
    import importlib.util
    from io import StringIO
    from pathlib import Path
    from types import SimpleNamespace
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = (
        Path(__file__).parents[2]
        / "alembic/versions/20261022_000051_discharge_signature_payload.py"
    )
    spec = importlib.util.spec_from_file_location("discharge_payload_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    monkeypatch.setenv("DB_SCHEMA_MODE", mode)
    monkeypatch.setattr(
        migration.sa,
        "inspect",
        lambda _: SimpleNamespace(
            get_schema_names=lambda: [schema],
            get_table_names=lambda schema: ["discharge_record"],
            get_columns=lambda *a, **k: [{"name": c} for c in existing],
        ),
    )
    output = StringIO()
    with Operations.context(
        MigrationContext.configure(
            dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
        )
    ):
        migration.upgrade()
    sql = output.getvalue()
    assert sql.count("ADD COLUMN") == (0 if existing else 2)
    if not existing:
        assert (
            f"ALTER TABLE {schema}.discharge_record ADD COLUMN chief_physician_sign_datetime TIMESTAMP WITH TIME ZONE"
            in sql
        )
        assert f"ALTER TABLE {schema}.discharge_record ADD COLUMN v2_schema TEXT" in sql
    assert not any(
        token in sql for token in ("NOT NULL", "UPDATE ", "DELETE ", "DROP ")
    )
    assert migration.down_revision == "20261020_000050"
    with pytest.raises(RuntimeError, match="不支持自动删除"):
        migration.downgrade()


def test_large_json_is_saved_entirely_without_changing_plain_body(monkeypatch):
    payload = {
        "record_content": [{"original_text": "合成数据" * 30000}],
        "all_fields": [1, None, {"a": True}],
    }
    text = json.dumps(payload, ensure_ascii=False)
    result = save(monkeypatch, {"v2_schema": text, "record_content": "原普通正文"})
    assert result["v2_schema"] == text
    assert result["record_content"] == "原普通正文"


@pytest.mark.parametrize(
    "field,old,new",
    [
        ("v2_schema", '{"version":"old"}', '{"version":"new"}'),
        ("chief_physician_sign_datetime", "2026-09-30T00:00:00+08:00", TIME),
    ],
)
def test_existing_nonempty_payload_conflict_is_preserved_for_review(field, old, new):
    before = {**CASE, "document_id": "D", field: old}
    source = {**CASE, "document_id": "D", field: new}
    result = dual.plan_table(
        "discharge_record",
        CASE,
        dual.SourceSnapshot("clinical_data", (source,)),
        dual.SourceSnapshot("homology"),
        dual.SourceSnapshot("local", (before,)),
        source_institutes={s: "H" for s in dual.SOURCES},
    )
    candidate = result.candidates[0]
    assert field in candidate.conflicts
    assert dual.equivalent(field, candidate.values[field], old)
    assert dual.equivalent(field, candidate.variants["clinical_data"][field], new)


def test_signature_clock_is_selected_as_metadata_but_not_rule_document_clock():
    from app.services.document_assembly.assembler import build_document_select_columns
    from app.services.luxian_0609.source_evidence_reader import (
        authoritative_document_time_value,
    )

    columns = build_document_select_columns("discharge_record", set(COLUMNS))
    assert "chief_physician_sign_datetime" in columns and "v2_schema" in columns
    row = {
        "chief_physician_sign_datetime": TIME,
        "v2_schema": '{"cheifphy_sign_time":"2026-10-01 00:00:00"}',
    }
    assert authoritative_document_time_value(row) is None
    assembled = assemble_document("discharge_record", row)
    assert assembled.record_time is None and assembled.submit_time is None
