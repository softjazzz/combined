"""剩余接口合同的纯元数据与假数据测试，不连接医院或数据库。"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from medqc_ingest.domain import (
    INTERFACE_REGISTRY,
    IngestError,
    project_record,
    schema_signature,
    validate_interface_columns,
)
from medqc_ingest.remaining_contracts import (
    CONTRACT_SHA256,
    REMAINING_NAMES,
    VENDOR_BLOCKED,
    default_contract_path,
    get_contracts,
    load_profile,
    select_spec,
    validate_target_keys,
)

COMPLETED = datetime(2026, 11, 1, tzinfo=timezone.utc)


def items_by_name() -> dict[str, dict[str, Any]]:
    return {item["interface"]: item for item in get_contracts()}


def sample(name: str) -> dict[str, Any]:
    _, specs = load_profile()
    spec = specs[name]
    payload: dict[str, Any] = dict.fromkeys(spec.source_columns)
    for index, field in enumerate(spec.key_fields):
        payload[field] = f"synthetic-{index}"
    return payload


def test_frozen_scope_exactly_55_minus_13_minus_17() -> None:
    before = dict(INTERFACE_REGISTRY)
    document, specs = load_profile()
    scope = document["scope"]
    assert scope["baseline"] == 55
    assert len(scope["excluded_core13"]) == 13
    assert len(scope["excluded_periop17"]) == 17
    assert len(REMAINING_NAMES) == 25
    assert len(specs) == 23
    assert set(specs) == REMAINING_NAMES - VENDOR_BLOCKED
    assert not REMAINING_NAMES & set(scope["excluded_core13"])
    assert not REMAINING_NAMES & set(scope["excluded_periop17"])
    assert before == INTERFACE_REGISTRY
    assert hashlib.sha256(default_contract_path().read_bytes()).hexdigest() == CONTRACT_SHA256


def test_no_error_text_credentials_or_clinical_inference_in_contract() -> None:
    doc, _ = load_profile()
    policy = doc["policy"]
    assert policy["automatic_incremental"] is False
    assert policy["scheduled_tasks"] is False
    assert policy["raw_preserves_all_columns"] is True
    assert policy["clinical_inference"] is False
    assert policy["generated_clinical_keys"] is False
    assert doc["evidence"]["source_error_text_included"] is False
    for item in doc["interfaces"]:
        assert "error" not in item
        assert "password" not in item
        assert item["derived_document_id"] is None
        assert item["date_semantics"] == "unverified"


@pytest.mark.parametrize("name", sorted(VENDOR_BLOCKED))
def test_vendor_missing_schema_is_probe_only_not_publishable(name: str) -> None:
    item = items_by_name()[name]
    _, specs = load_profile()
    assert item["status"] == "vendor_blocked"
    assert item["ready"] is False
    assert item["source_columns"] == item["raw_key_fields"] == []
    assert "source_schema_unavailable" in item["block_reasons"]
    assert item["target_columns"]  # 目标模型存在不代表源接口可用。
    with pytest.raises(IngestError, match="remaining_disabled_or_unknown"):
        select_spec(specs, name)


@pytest.mark.parametrize("name", sorted(REMAINING_NAMES - VENDOR_BLOCKED))
def test_each_structural_candidate_has_explicit_fields_and_complete_primary_key(name: str) -> None:
    document, specs = load_profile()
    item = next(item for item in document["interfaces"] if item["interface"] == name)
    spec = specs[name]
    assert spec.publish is not None
    assert item["status"] == "candidate_ready"
    assert item["key_status"] == "candidate_requires_nonempty_uniqueness_gate"
    assert tuple(item["raw_key_fields"]) == spec.key_fields
    assert set(spec.key_fields) <= set(spec.source_columns)
    assert {"institute_id", "patient_id", "visit_id"} <= set(spec.key_fields)
    assert tuple(item["target_primary_key"]) == spec.publish.primary_key
    assert set(spec.publish.primary_key) <= set(spec.publish.target_columns)
    assert schema_signature(spec.source_columns)[0] == item["schema_hash"]
    assert not spec.publish.derived_document_id
    target_names = {column["name"] for column in item["target_columns"]}
    assert set(spec.publish.target_columns) <= target_names
    assert set(spec.source_columns) == {mapping.source for mapping in spec.publish.mappings} | {
        field["source"] for field in item["raw_only_fields"]
    }
    assert target_names == set(spec.publish.target_columns) | {
        field["target"] for field in item["target_missing_fields"]
    }
    payload = sample(name)
    projected = project_record(spec, payload, COMPLETED)
    assert set(projected) == set(spec.publish.target_columns)
    assert validate_target_keys(spec, [payload], COMPLETED) == 1


def test_duplicate_source_columns_preserved_without_arbitrary_target_selection() -> None:
    name = "web.medical_insurance_settlement_cost"
    item = items_by_name()[name]
    labels = item["observed_source_labels"]
    assert labels.count("last_modifier") == 2
    assert len(labels) == len(item["source_columns"]) == 33
    assert "last_modifier__2" in item["source_columns"]
    assert not any(m["target"] == "last_modifier" for m in item["mappings"])
    assert {"last_modifier", "last_modifier__2"} <= {
        row["source"] for row in item["raw_only_fields"]
    }
    assert {"target": "last_modifier", "reason": "ambiguous_duplicate_source_name"} in (
        item["target_missing_fields"]
    )
    _, specs = load_profile()
    assert validate_interface_columns(specs[name], labels) == item["source_columns"]


@pytest.mark.parametrize(
    ("name", "target", "source"),
    [
        ("web.mr_icu", "icu_end_datetime", "ice_end_datetime"),
        ("web.mr_customize", "living_ability_discharge_score", "living_ability_diacharge_score"),
        ("web.pathology_exam_report", "diagnosis", "Diagnosis"),
        ("web.medical_insurance_settlement_cost", "item_class_a_amount", "ITEMCLAAAMT"),
        ("web.medical_insurance_settlement_cost", "item_class_b_amount", "ITEMCLABAMT"),
        ("web.medical_insurance_settlement_cost", "item_own_pay_amount", "ITEMOWNPAYAMT"),
        ("web.medical_insurance_settlement_cost", "item_other_amount", "ITEMOTHAMT"),
        ("web.handoff_record", "document_id", "documentid"),
        ("web.transfer_out_record", "inpat_no", "inpatno"),
    ],
)
def test_explicit_spelling_aliases(name: str, target: str, source: str) -> None:
    item = items_by_name()[name]
    mapping = next(m for m in item["mappings"] if m["target"] == target)
    assert mapping["source"] == source
    assert mapping["basis"] == "explicit_spelling_alias"


def test_event_signature_and_clinical_fields_not_fabricated_from_submit_or_text() -> None:
    items = items_by_name()
    summary = items["web.summary_record"]
    assert {"record_datetime", "physician_sign", "physician_sign_datetime"} <= {
        row["source"] for row in summary["mappings"]
    }
    assert "pregnant_weeks" in {row["source"] for row in items["web.newborn_record"]["mappings"]}
    missing = items["web.transfer_in_record"]["target_missing_fields"]
    assert {"target": "physician_sign", "reason": "source_column_not_provided"} in missing
    assert not any(
        m["target"] == "record_datetime" for m in items["web.handoff_record"]["mappings"]
    )


@pytest.mark.parametrize("name", ["web.mr_cost", "web.mr_customize"])
def test_visit_target_collision_rejects_two_distinct_source_documents(name: str) -> None:
    _, specs = load_profile()
    spec = specs[name]
    first = sample(name)
    second = dict(first, document_id="synthetic-another-document")
    with pytest.raises(IngestError, match="remaining_target_key_collision") as caught:
        validate_target_keys(spec, iter([first, second]), COMPLETED)
    assert "synthetic" not in str(caught.value)


def test_source_duplicate_rejected_even_identical_content() -> None:
    _, specs = load_profile()
    payload = sample("web.diagnosis")
    with pytest.raises(IngestError, match="remaining_source_key_duplicate"):
        validate_target_keys(specs["web.diagnosis"], [payload, payload], COMPLETED)


def test_cross_chunk_source_and_target_keys_are_checked_over_the_whole_iterable() -> None:
    _, specs = load_profile()
    spec = specs["web.diagnosis"]
    a = sample(spec.name)
    b = dict(a, diagnosis_id="synthetic-other")
    assert validate_target_keys(spec, (row for row in [a, b]), COMPLETED) == 2
    with pytest.raises(IngestError, match="remaining_source_key_duplicate"):
        validate_target_keys(spec, (row for row in [a, b, a]), COMPLETED)


def test_schema_reorder_and_missing_key_are_blocked() -> None:
    _, specs = load_profile()
    spec = specs["web.diagnosis"]
    with pytest.raises(IngestError, match="source_contract_mismatch"):
        validate_interface_columns(spec, list(reversed(spec.source_columns)))
    payload = sample(spec.name)
    payload["diagnosis_id"] = " "
    with pytest.raises(IngestError, match="missing_source_key"):
        validate_target_keys(spec, [payload], COMPLETED)


def test_contract_tampering_is_rejected_without_echoing_payload(tmp_path: Path) -> None:
    path = tmp_path / "modified.json"
    path.write_text('{"private_test_value":"must-not-echo"}', encoding="utf-8")
    with pytest.raises(IngestError, match="remaining_frozen_contract_hash") as caught:
        load_profile(path)
    assert "must-not-echo" not in str(caught.value)
    assert str(path) not in str(caught.value)


def test_missing_contract_is_controlled_and_fresh_contract_copies_do_not_share_mutation(
    tmp_path: Path,
) -> None:
    with pytest.raises(IngestError, match="remaining_contract_read"):
        load_profile(tmp_path / "missing.json")
    first = get_contracts()
    first[0]["source_columns"].append("bad")
    assert "bad" not in get_contracts()[0]["source_columns"]


def test_unknown_or_previously_accepted_interfaces_not_in_candidate_registry() -> None:
    _, specs = load_profile()
    for name in ("web.mr", "web.surgery_record", "web.hidden_procedure", "select 1"):
        with pytest.raises(IngestError, match="remaining_disabled_or_unknown"):
            select_spec(specs, name)


def test_contract_is_deterministic_metadata_json() -> None:
    value = json.loads(default_contract_path().read_text(encoding="utf-8"))
    assert [item["interface"] for item in value["interfaces"]] == sorted(REMAINING_NAMES)
    assert len(value["evidence"]["baseline_sha256"]) == 64
    assert value["evidence"]["metadata_only"] is True


def backend_path() -> Path:
    service = Path(__file__).resolve().parents[1]
    packaged = service / "backend"
    return packaged if packaged.is_dir() else service.parent / "medqc-web" / "backend"


def load_migration() -> Any:
    path = backend_path() / "alembic/versions/20261101_000058_remaining_source_facts.py"
    spec = importlib.util.spec_from_file_location("remaining_source_facts_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_058_orm_metadata_and_frozen_contract_preserve_all_23_new_fields() -> None:
    import ast

    from sqlalchemy.orm import declarative_base

    migration = load_migration()
    path = backend_path() / "app/database/models/cdm.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    # 独立元数据Base，不导入应用connection/env或创建任何引擎。
    tree.body = [
        node for node in tree.body if not isinstance(node, ast.ImportFrom) or node.level == 0
    ]
    scope: dict[str, Any] = {"Base": declarative_base()}
    exec(compile(tree, str(path), "exec"), scope)
    models = {
        model.__tablename__: model.__table__
        for model in scope.values()
        if isinstance(model, type) and hasattr(model, "__tablename__")
    }
    items = items_by_name()
    assert len(migration.FIELDS) == 23
    assert sum(kind == "datetime" for _t, _c, kind in migration.FIELDS) == 10
    for table, name, kind in migration.FIELDS:
        column = models[table].columns[name]
        assert isinstance(column.type, type(migration.field_type(kind)))
        assert column.nullable is True
        assert column.default is None and column.server_default is None
        if kind == "datetime":
            assert column.type.timezone is False
        source = "MainDiag_Flag" if name == "main_diag_flag" else name
        mapping = next(m for m in items["web." + table]["mappings"] if m["target"] == name)
        assert mapping["source"] == source
        assert mapping["target_type"] == kind
        assert source not in {r["source"] for r in items["web." + table]["raw_only_fields"]}
    assert str(models["newborn_record"].columns.birthday.type) == "TEXT"
    assert load_profile()[0]["required_alembic_revision"] == migration.revision
    epidemic = models["epidemic_record"]
    assert set(epidemic.columns.keys()) == {c.name for c in migration.epidemic_columns()}
    assert tuple(epidemic.primary_key.columns.keys()) == migration.EPIDEMIC_PRIMARY_KEY
    for column in migration.epidemic_columns():
        model_column = epidemic.columns[column.name]
        assert str(column.type) == str(model_column.type)
        assert column.nullable == model_column.nullable
        assert column.server_default is None and column.default is None


@pytest.mark.parametrize(("mode", "schema"), [("single", "public"), ("split", "cdm")])
def test_058_offline_sql_only_adds_nullable_columns_without_dml(
    monkeypatch: pytest.MonkeyPatch, mode: str, schema: str
) -> None:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = load_migration()
    output = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    monkeypatch.setenv("DB_SCHEMA_MODE", mode)
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: True)
    monkeypatch.setattr(migration, "op", Operations(context))
    migration.upgrade()
    sql = output.getvalue()
    assert sql.count("ADD COLUMN") == 23
    assert sql.count(f"ALTER TABLE {schema}.") == 23
    assert f"CREATE TABLE IF NOT EXISTS {schema}.epidemic_record" in sql
    for line in sql.splitlines():
        if "ADD COLUMN" in line:
            assert "NOT NULL" not in line
    for forbidden in ("INSERT", "UPDATE", "DELETE", "DEFAULT", "DROP", "TRUNCATE"):
        assert forbidden not in sql


def test_058_online_baseline_columns_are_validated_and_not_added_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = load_migration()
    inspector = Mock()
    inspector.has_table.return_value = True
    inspector.get_columns.side_effect = lambda table, **_kwargs: (
        [
            {"name": name, "type": migration.field_type(kind), "nullable": True, "default": None}
            for target, name, kind in migration.FIELDS
            if target == table
        ]
        if table != "epidemic_record"
        else epidemic_catalog(migration)
    )
    inspector.get_pk_constraint.return_value = {
        "constrained_columns": list(migration.EPIDEMIC_PRIMARY_KEY)
    }
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: inspector)
    monkeypatch.setattr(migration, "op", Mock())
    migration.upgrade()
    migration.op.add_column.assert_not_called()
    assert inspector.has_table.call_count == 8


def test_058_online_checks_all_existing_fields_before_mutation_and_rejects_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = load_migration()
    inspector = Mock()
    inspector.has_table.return_value = True
    inspector.get_columns.side_effect = lambda table, **_kwargs: (
        [
            {
                "name": "main_diag_flag",
                "type": migration.field_type("text"),
                "nullable": True,
                "default": "false",
            }
        ]
        if table == "diagnosis"
        else epidemic_catalog(migration)
        if table == "epidemic_record"
        else []
    )
    inspector.get_pk_constraint.return_value = {
        "constrained_columns": list(migration.EPIDEMIC_PRIMARY_KEY)
    }
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: inspector)
    monkeypatch.setattr(migration, "op", Mock())
    with pytest.raises(RuntimeError, match="remaining_existing_column_contract_mismatch"):
        migration.upgrade()
    migration.op.add_column.assert_not_called()


def test_058_invalid_schema_mode_rejected_before_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = load_migration()
    monkeypatch.setenv("DB_SCHEMA_MODE", "unapproved")
    with pytest.raises(RuntimeError, match="unsupported_schema_mode"):
        migration.upgrade()


def epidemic_catalog(migration: Any) -> list[dict[str, Any]]:
    return [
        {"name": name, "type": migration.field_type(kind), "nullable": null, "default": None}
        for name, kind, null in migration.EPIDEMIC_FIELDS
    ]


@pytest.mark.parametrize("public_present", [True, False])
def test_058_recovers_omitted_epidemic_target_by_preserving_public_or_frozen_ddl(
    monkeypatch: pytest.MonkeyPatch, public_present: bool
) -> None:
    migration = load_migration()
    inspector = Mock()
    inspector.has_table.side_effect = lambda table, schema: (
        public_present and schema == "public" if table == "epidemic_record" else True
    )
    inspector.get_columns.side_effect = lambda table, **_kwargs: (
        epidemic_catalog(migration) if table == "epidemic_record" else []
    )
    inspector.get_pk_constraint.return_value = {
        "constrained_columns": list(migration.EPIDEMIC_PRIMARY_KEY)
    }
    monkeypatch.setenv("DB_SCHEMA_MODE", "split")
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: inspector)
    monkeypatch.setattr(migration, "op", Mock())
    migration.upgrade()
    assert migration.op.add_column.call_count == 23
    if public_present:
        migration.op.create_table.assert_not_called()
        statement = str(migration.op.execute.call_args.args[0])
        assert statement == 'ALTER TABLE "public"."epidemic_record" SET SCHEMA "cdm"'
    else:
        migration.op.execute.assert_not_called()
        call = migration.op.create_table.call_args
        assert call.args[0] == "epidemic_record" and call.kwargs["schema"] == "cdm"
        assert len(call.args[1:]) == 21


def test_058_refuses_malformed_legacy_epidemic_before_any_ddl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = load_migration()
    inspector = Mock()
    inspector.has_table.return_value = True
    inspector.get_columns.return_value = []
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: inspector)
    monkeypatch.setattr(migration, "op", Mock())
    with pytest.raises(RuntimeError, match="remaining_epidemic_contract_mismatch"):
        migration.upgrade()
    migration.op.add_column.assert_not_called()
    migration.op.create_table.assert_not_called()
    migration.op.execute.assert_not_called()
