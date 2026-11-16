"""固定选择器的离线合同测试：仅合成 DBAPI 游标，不加载应用配置。"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.fixtures.primary_material_fixtures import policy, synthetic_material, selection_fixture


def module():
    name = "app.services.primary_material_readonly"
    assert importlib.util.find_spec(name) is not None, "需要固定的四类只读闭包"
    return importlib.import_module(name)




class Cursor:
    def __init__(self, db):
        self.db = db
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.db.cursors_closed += 1

    def execute(self, sql, params=()):
        self.db.statements.append((sql, params))
        assert sql.startswith("SELECT ") and "SELECT *" not in sql
        if self.db.failure:
            raise self.db.failure
        if "current_database()" in sql:
            self.rows = [self.db.identity]
        elif "to_regclass" in sql:
            self.rows = [(None if params[0] in self.db.missing else params[0],)]
        elif "FROM sync_material.primary_policy" in sql:
            self.rows = [(self.db.registered_hash,)]
        elif "primary_manifest" in sql:
            self.rows = [(copy.deepcopy(self.db.manifest),)] if self.db.manifest else []
        elif "primary_coverage" in sql:
            self.rows = [({"publication_health": {"state": "READY_FOR_INSPECTION"}},)]
        elif "sync_delivery.receipt" in sql:
            ref = next(v["publication"] for v in self.db.manifest["materials"]
                       if v["publication"]["interface"] == params[0]
                       and v["publication"]["source_key_hash"] == params[1])
            self.rows = [(ref["source_epoch"], ref["generation"], ref["mapping_hash"], ref["activation"], "target-key")]
        elif "LIMIT 20001" in sql:
            table = sql.split(" FROM ")[1].split(" WHERE ")[0]
            self.rows = [tuple(v["native_key"]) for v in self.db.manifest["materials"]
                         if table == self.db.tables[v["version_id"]]]
            self.rows.extend(self.db.extra_keys.get(table, []))
        else:
            table = sql.split(" FROM ")[1].split(" WHERE ")[0]
            value = next(v for v in self.db.manifest["materials"]
                         if self.db.tables[v["version_id"]] == table
                         and tuple(v["native_key"]) == params)
            names = [part.strip('"') for part in sql.split(" FROM ")[0][7:].split(",")]
            self.rows = [tuple(value["target_payload"][name] for name in names)]

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def fetchmany(self, size):
        return self.rows[:size]


class Database:
    def __init__(self, p):
        self.identity = ("delivery_cdm_123456abcdef", "repeatable read", "on")
        self.registered_hash = p.policy_hash
        self.manifest = {"policy_hash": p.policy_hash, "materials": []}
        self.statements = []
        self.cursors_closed = 0
        self.missing = set()
        self.failure = None
        self.tables = {}
        self.extra_keys = {}

    def cursor(self):
        return Cursor(self)

    def commit(self):
        pytest.fail("不能提交调用者事务")

    rollback = close = commit


def sqlalchemy_connection(db):
    return SimpleNamespace(connection=SimpleNamespace(driver_connection=db))




def database_with_materials(m, p, materials):
    db = Database(p)
    db.manifest = m.select_materials(p, materials, {})
    for value in materials:
        spec = (m.real_contracts()[value["document_type"]].spec
                if value["source_namespace"] == "clinical" else m.cache_spec(value["document_type"]))
        db.tables[value["version_id"]] = '"' + spec.publish.schema + '"."' + spec.publish.table + '"'
    return db


def test_fixed_contracts_and_dependencies():
    m = module()
    assert m.SOURCE_COMMIT == "cb437e611e802c5117f212c1e9743d2748ec4127"
    assert m.CONTRACT == "clinical-primary-four-v1"
    assert m.METADATA_REVISION == "clinical-primary-real-fields-v2"
    contracts = m.real_contracts()
    assert [len(contracts[k].columns) for k in m.KINDS] == [36, 55, 59, 49]
    assert sum(len(c.columns) for c in contracts.values()) == 199
    assert all(c.native_primary_key == ("institute_id", "document_id") for c in contracts.values())
    assert contracts["surgery_record"].body_field == "surgery_process"
    for kind, contract in contracts.items():
        assert not hasattr(contract, "refresh_publication")
        assert not hasattr(contract, "validate_native_metadata")
        assert contract.spec.publish.table == m.TARGETS[kind]
        assert m.cache_spec(kind).publish.table == kind
    assert "record_datetime" not in m.cache_spec("postsurg_firstcourse_record").publish.target_columns
    assert "surgery_begin_time" in m.cache_spec("surgery_record").publish.target_columns
    assert "surgery_begin_datetime" not in m.cache_spec("surgery_record").publish.target_columns


def test_bridge_borrows_same_connection_without_transaction_ownership():
    m = module()
    p = policy(m)
    db = Database(p)
    conn = sqlalchemy_connection(db)
    assert m.primary_objects_available(conn) is True
    result = m.read_primary_in_transaction(conn, p, m.real_contracts())
    assert result["contract"] == m.CONTRACT and result["materials"] == []
    assert result["absence_is_clinical_missing"] is False
    assert db.cursors_closed == 2
    assert all(sql.startswith("SELECT ") for sql, _ in db.statements)
    assert not any("primary_attempt" in sql or "pg_attribute" in sql for sql, _ in db.statements)


def test_missing_optional_objects_are_probed_without_failing_transaction():
    m = module()
    db = Database(policy(m))
    db.missing.add("sync_material.primary_manifest")
    assert m.primary_objects_available(sqlalchemy_connection(db)) is False
    assert all("to_regclass" in sql for sql, _ in db.statements)
    assert db.cursors_closed == 1


@pytest.mark.parametrize("identity", [("clinical_data", "repeatable read", "on"),
                                      ("medqc_sync_cdm", "read committed", "on"),
                                      ("medqc_sync_cdm", "repeatable read", "off")])
def test_rejects_database_and_transaction_identity(identity):
    m = module()
    p = policy(m)
    db = Database(p)
    db.identity = identity
    with pytest.raises(m.IngestError, match="primary_same_transaction_required"):
        m.read_primary_in_transaction(sqlalchemy_connection(db), p, m.real_contracts())


def test_permission_structure_and_current_policy_failures_are_explicit():
    m = module()
    p = policy(m)
    db = Database(p)
    db.failure = PermissionError("synthetic privilege denied")
    with pytest.raises(PermissionError):
        m.primary_objects_available(sqlalchemy_connection(db))
    with pytest.raises(PermissionError):
        m.read_primary_in_transaction(sqlalchemy_connection(db), p, m.real_contracts())
    db.failure = None
    db.registered_hash = "other-policy"
    with pytest.raises(m.IngestError, match="primary_policy_not_current"):
        m.read_in_transaction(db, p, m.real_contracts())
    db.registered_hash = p.policy_hash
    db.manifest = None
    with pytest.raises(m.IngestError, match="primary_manifest_not_current"):
        m.read_in_transaction(db, p, m.real_contracts())
    with pytest.raises(m.IngestError, match="primary_contract_set"):
        m.read_in_transaction(db, p, {})


def test_missing_or_modified_json_refuses_contract(monkeypatch, tmp_path):
    m = module()
    monkeypatch.setattr(m, "CONTRACT_DIRECTORY", tmp_path)
    with pytest.raises((OSError, m.IngestError)):
        m.real_contracts()
    with pytest.raises((OSError, m.ControlError)):
        m.cache_spec("daily_course_record")
    with pytest.raises((OSError, m.IngestError)):
        m.cache_spec("surgery_record")
    (tmp_path / "clinical-primary-real-fields-v2.json").write_text("{}", encoding="utf-8")
    with pytest.raises(m.IngestError, match="clinical_real_metadata_hash"):
        m.real_contracts()


def test_four_material_payloads_and_receipts_use_explicit_columns_same_cursor():
    m = module()
    p = policy(m)
    materials = [synthetic_material(m, kind) for kind in m.KINDS]
    db = database_with_materials(m, p, materials)
    result = m.read_primary_in_transaction(sqlalchemy_connection(db), p, m.real_contracts())
    assert len(result["items"]) == 4
    assert all(item["selection_reason"] == "CLINICAL_PRIMARY" for item in result["items"])
    assert result["materials"] == sorted(materials, key=lambda value: value["version_id"])
    assert db.cursors_closed == 1
    payload_queries = [sql for sql, _ in db.statements if " WHERE \"institute_id\"=%s" in sql]
    for kind in m.KINDS:
        spec = m.real_contracts()[kind].spec
        expected = 'SELECT ' + ','.join('"' + name + '"' for name in spec.publish.target_columns)
        assert any(sql.startswith(expected + ' FROM "sync_material"."' + m.TARGETS[kind] + '"') for sql in payload_queries)
    assert all(not value.get("capture_refresh_required") for value in result["coverage"].values())


def test_held_clinical_uses_selected_whole_cache_version():
    m = module()
    p = policy(m)
    clinical = synthetic_material(m, "surgery_record", body=" ")
    cache = synthetic_material(m, "surgery_record", "cache", body="Caché完整手术过程")
    db = database_with_materials(m, p, [clinical, cache])
    result = m.read_in_transaction(db, p, m.real_contracts())
    item = result["items"][0]
    assert item["selected_version"] == cache["version_id"]
    assert item["selection_reason"] == "CACHE_FALLBACK"
    assert item["relation"] == "ALTERNATIVE_HELD"
    assert item["exclusions"][clinical["version_id"]] == ["BODY_EMPTY"]
    assert "body" not in item["uncertain_fields"]
    assert next(v for v in result["materials"] if v["version_id"] == item["selected_version"]) == cache


def test_stale_publication_is_held_and_new_keys_only_signal_refresh():
    m = module()
    p = policy(m)
    material = synthetic_material(m, "daily_course_record")
    material["publication"]["spec_hash"] = "wrong-contract-hash"
    db = database_with_materials(m, p, [material])
    result = m.read_in_transaction(db, p, m.real_contracts())
    assert result["items"][0]["selected_version"] is None
    assert result["items"][0]["exclusions"][material["version_id"]] == ["PUBLICATION_STALE"]
    # 已存版本对象缺失不会伪装为临床缺书；同一固定 selector 明确保持 HOLD。
    material["publication"]["spec_hash"] = m.digest(asdict(m.real_contracts()["daily_course_record"].spec))
    db = database_with_materials(m, p, [material])
    db.missing.add("sync_material.clinical_daily_current")
    result = m.read_in_transaction(db, p, m.real_contracts())
    assert result["items"][0]["selected_version"] is None
    assert result["absence_is_clinical_missing"] is False
    db = database_with_materials(m, p, [material])
    db.extra_keys['"sync_material"."clinical_daily_current"'] = [("i", "p", "v", "not-yet-captured")]
    result = m.read_in_transaction(db, p, m.real_contracts())
    assert result["coverage"]["daily_course_record"]["capture_refresh_required"] is True
    assert len(result["materials"]) == 1
    assert result["items"][0]["selected_version"] == material["version_id"]
    # 新版本只做坐标扫描，不读未冻结的新正文。
    assert all("not-yet-captured" not in str(params) for _, params in db.statements)


def test_fixture_contains_all_native_columns_and_full_source_payload():
    m = module()
    fixture = selection_fixture()
    clinical = [v for v in fixture["selection"]["materials"] if v["source_namespace"] == "clinical"]
    assert len(clinical) == 4
    for value in clinical:
        contract = fixture["contracts"][value["document_type"]]
        assert tuple(value["native_fields"]) == contract.columns
        original = json.loads(value["target_payload"]["source_payload"])
        assert original["columns"] == list(contract.columns)
        assert original["values"] == list(value["native_fields"].values())
        assert value["native_fields"][contract.body_field] == value["body"]
        assert value["source_times"]
    assert json.loads(json.dumps(fixture["selection"], ensure_ascii=False)) == fixture["selection"]


def test_fingerprints_cover_runtime_definitions_and_fixed_json():
    m = module()
    root = Path(m.__file__).resolve()
    source = root.read_text(encoding="utf-8")
    manifest = json.loads((m.CONTRACT_DIRECTORY / "READONLY_FINGERPRINTS.json").read_text(encoding="utf-8"))
    assert manifest["source_commit"] == m.SOURCE_COMMIT
    definitions = {node.name: node for node in ast.parse(source).body
                   if isinstance(node, (ast.ClassDef, ast.FunctionDef))}
    assert set(definitions) == set(manifest["runtime_definitions"])
    for name, node in definitions.items():
        assert hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest() == manifest["runtime_definitions"][name]["sha256"]
    for node in definitions.values():
        if isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, ast.FunctionDef):
                    info = manifest["runtime_methods"][node.name + "." + member.name]
                    actual = hashlib.sha256(ast.get_source_segment(source, member).encode()).hexdigest()
                    assert actual == info["sha256"]
                    if node.name != "AcceptedManualCatalog" or member.name != "__init__":
                        assert actual == info["source_sha256"]
    for name, expected in manifest["json_files"].items():
        assert hashlib.sha256((m.CONTRACT_DIRECTORY / name).read_bytes()).hexdigest() == expected
    for name in ("PrimaryContract", "MetadataContract", "ClinicalContract", "AcceptedManualCatalog"):
        assert manifest["runtime_definitions"][name]["adaptation"]
    assert manifest["runtime_definitions"]["read_in_transaction"]["sha256"] == "0735eabc647bec761ef22c6ebf247a9a4b63826479794cd076df7665aadf11c9"
    assert manifest["runtime_definitions"]["select_materials"]["sha256"] == "b99b66ef968e8f5bed61089cf26af27468d3b4b00cab33bbf4e99de073191514"
    assert "PrimaryContract.refresh_publication" not in manifest["runtime_methods"]
    assert "MetadataContract.validate_native_metadata" not in manifest["runtime_methods"]
    assert "PrimaryContract.refresh_publication" in manifest["source_files"]["clinical_primary.py"]["class_methods"]
    assert "MetadataContract.validate_native_metadata" in manifest["source_files"]["primary_metadata.py"]["class_methods"]
    assert not any(word in source for word in ("import medqc_ingest", "frozen_replay", "def poll(", "def extract("))
