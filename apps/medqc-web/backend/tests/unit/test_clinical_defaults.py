from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.database import clinical_connection, connection
from app.routers import clinical_sources as source_router
from app.services import case_material_snapshot, clinical_sources, document_segmenter, etl_sync
from app.services import saved_result_access
from app.services.cdm_publication_evidence import target_hash
from app.services.frontpage_extraction_service import FrontPageExtractionService


@pytest.mark.parametrize(
    ("name", "case_institute"),
    [(None, "机构号"), ("新区医院", "CDM-SITE-B")],
)
def test_saved_result_proof_only_applies_to_configured_institute_pair(monkeypatch, name, case_institute):
    monkeypatch.delenv("MEDQC_HOSPITAL_NAME", raising=False)
    monkeypatch.delenv("MEDQC_SAVED_RESULT_CASE_INSTITUTE", raising=False)
    if name is not None:
        monkeypatch.setenv("MEDQC_HOSPITAL_NAME", name)
        monkeypatch.setenv("MEDQC_SAVED_RESULT_CASE_INSTITUTE", case_institute)
        with pytest.raises(HTTPException) as error:
            saved_result_access.scope_needs_donghua_result_proof("泸县人民医院", "机构号")
        assert error.value.status_code == 403

    assert saved_result_access.scope_needs_donghua_result_proof(name or "泸县人民医院", case_institute)
    assert not saved_result_access.scope_needs_donghua_result_proof("另一家医院", "另一家医院")
    monkeypatch.setenv("MEDQC_SAVED_RESULT_CASE_INSTITUTE", name or "泸县人民医院")
    assert not saved_result_access.scope_needs_donghua_result_proof(name or "泸县人民医院", name or "泸县人民医院")


def test_frozen_result_requires_configured_epoch_and_binding(monkeypatch):
    identity = ("CDM-SITE-B", "synthetic-patient", "synthetic-visit")
    epoch = "13709ad1-cd73-40f7-8b13-39b3f067d16d"
    binding = clinical_connection.build_source_binding("new.example", 5432, "cdm", "reader")
    other_binding = clinical_connection.build_source_binding("other.example", 5432, "cdm", "reader")
    monkeypatch.setenv("MEDQC_SAVED_RESULT_CASE_INSTITUTE", identity[0])
    monkeypatch.setenv("MEDQC_SAVED_RESULT_SOURCE_EPOCH", epoch)
    monkeypatch.setenv("MEDQC_SAVED_RESULT_SOURCE_BINDING", binding)

    key = target_hash(dict(zip(("institute_id", "patient_id", "visit_id"), identity)))
    entry = {"status": "receipt_verified", "target_key_hash": key,
             "receipt": {"source_epoch": epoch, "target_key_hash": key},
             "operation": {"source_epoch": epoch, "interface_name": "web.admission_record"}}
    state = {"schema": "cdm", "identity": list(identity), "binding": binding,
             "automatic_material": {"publication": {"status": "metadata_available",
                 "rows": {"admission_record": [entry]}}}}
    monkeypatch.setattr(case_material_snapshot, "load", lambda *_: state)
    assert saved_result_access.require_donghua_frozen_result("job", identity, binding) is state

    state["binding"] = other_binding
    with pytest.raises(HTTPException) as error:
        saved_result_access.require_donghua_frozen_result("job", identity, other_binding)
    assert error.value.status_code == 403

    state["binding"] = binding
    entry["operation"]["source_epoch"] = "7cecd40f-047d-4458-b964-8741d0ea7399"
    with pytest.raises(HTTPException) as error:
        saved_result_access.require_donghua_frozen_result("job", identity, binding)
    assert error.value.status_code == 403

    monkeypatch.delenv("MEDQC_SAVED_RESULT_SOURCE_EPOCH")
    entry["receipt"]["source_epoch"] = entry["operation"]["source_epoch"]
    with pytest.raises(HTTPException) as error:
        saved_result_access.require_donghua_frozen_result("job", identity, binding)
    assert error.value.status_code == 403


def test_old_snapshot_receipt_proof_uses_configured_database_scope(monkeypatch):
    ref = {"institute_id": "CDM-SITE-B", "patient_id": "synthetic-patient", "visit_id": "synthetic-visit"}
    identity = (ref["institute_id"], ref["patient_id"], ref["visit_id"])
    epoch = "13709ad1-cd73-40f7-8b13-39b3f067d16d"
    binding = clinical_connection.build_source_binding("new.example", 5432, "cdm", "reader")
    monkeypatch.setenv("MEDQC_SAVED_RESULT_CASE_INSTITUTE", ref["institute_id"])
    monkeypatch.setenv("MEDQC_SAVED_RESULT_SOURCE_EPOCH", epoch)
    monkeypatch.setenv("MEDQC_SAVED_RESULT_SOURCE_BINDING", binding)

    state = {"schema": "cdm", "identity": list(identity), "binding": binding,
             "automatic_material": {"publication": {"status": "metadata_permission_unconfirmed", "rows": {}}},
             "tables": {"admission_record": [ref]}}
    monkeypatch.setattr(case_material_snapshot, "load", lambda *_: state)
    engine = MagicMock()
    monkeypatch.setattr(clinical_connection, "get_engine", lambda: engine)
    conn = engine.connect.return_value.execution_options.return_value.__enter__.return_value
    receipt = {"interface_name": "web.admission_record", "source_epoch": epoch,
               "matches_contract": True, "generation": 3}
    conn.execute.return_value.mappings.return_value.all.return_value = [receipt]

    with clinical_connection.selected({"binding": binding}):
        assert saved_result_access.require_donghua_frozen_result("job", identity, binding) is state
        receipt["source_epoch"] = "7cecd40f-047d-4458-b964-8741d0ea7399"
        with pytest.raises(HTTPException) as error:
            saved_result_access.require_donghua_frozen_result("job", identity, binding)
        assert error.value.status_code == 403

    receipt["source_epoch"] = epoch
    with clinical_connection.selected({"binding": "old-binding"}):
        with pytest.raises(HTTPException) as error:
            saved_result_access.require_donghua_frozen_result("job", identity, binding)
        assert error.value.status_code == 403


@pytest.mark.parametrize(("name", "label"), [(None, "东华CDM"), ("新区临床源", "新区临床源")])
def test_fixed_source_options_use_configured_label(monkeypatch, name, label):
    monkeypatch.delenv("MEDQC_CLINICAL_SOURCE_MODE", raising=False)
    monkeypatch.delenv("MEDQC_CDM_SOURCE_NAME", raising=False)
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setattr(connection, "SessionLocal", None)
    if name is not None:
        monkeypatch.setenv("MEDQC_CDM_SOURCE_NAME", name)
    assert source_router.options({})["data"] == {
        "mode": "fixed_donghua_cdm",
        "default_source": "independent_cdm",
        "sources": [{"id": "independent_cdm", "name": label, "enabled": False}],
    }


def test_compat_source_default_does_not_rebind_saved_or_explicit_sources(monkeypatch):
    monkeypatch.setenv("MEDQC_DEFAULT_CLINICAL_SOURCE", "independent_cdm")
    assert clinical_sources.SourceSettings().default_source == "independent_cdm"
    assert clinical_sources.SourceSettings(default_source="legacy_pg").default_source == "legacy_pg"
    assert clinical_sources.saved_snapshot({})["id"] == "legacy_pg"


@pytest.mark.parametrize("name", [None, "新区医院（东院）"])
def test_document_segmenter_filters_configured_hospital_header(monkeypatch, name):
    monkeypatch.delenv("MEDQC_HOSPITAL_NAME", raising=False)
    if name is not None:
        monkeypatch.setenv("MEDQC_HOSPITAL_NAME", name)
    header = name or "泸县人民医院"
    sections = document_segmenter.split_document(f"入院记录\n{header}\n正文")
    assert [section.content for section in sections] == ["入院记录\n正文"]


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "label"), [(None, "泸县人民医院（示例）"), ("新区医院", "新区医院（示例）")])
async def test_frontpage_demo_fallback_uses_configured_hospital_label(monkeypatch, name, label):
    monkeypatch.delenv("MEDQC_HOSPITAL_NAME", raising=False)
    if name is not None:
        monkeypatch.setenv("MEDQC_HOSPITAL_NAME", name)
    service = FrontPageExtractionService(llm_config={"model": "offline-test"})
    draft = await service.extract_from_text("")
    assert draft.hospitalization.hospital_name == label


def test_sync_config_uses_deployment_institute_only_as_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(etl_sync, "_CONFIG_FILE", tmp_path / "absent.json")
    monkeypatch.setattr(etl_sync, "_pg_required_in_current_env", lambda: False)
    stored = {}
    monkeypatch.setattr(etl_sync, "get_config", lambda *_: stored.copy())
    monkeypatch.delenv("MEDQC_DEFAULT_INSTITUTE_ID", raising=False)
    assert etl_sync.load_db_config()["default_institute_id"] == "LOCAL-HOSPITAL"

    monkeypatch.setenv("MEDQC_DEFAULT_INSTITUTE_ID", "SITE-B")
    assert etl_sync.load_db_config()["default_institute_id"] == "SITE-B"
    stored["default_institute_id"] = "SITE-C"
    assert etl_sync.load_db_config()["default_institute_id"] == "SITE-C"
