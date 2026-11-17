"""四类材料纯合成边界，不访问数据库、不执行医学规则。"""
from copy import deepcopy
from contextlib import nullcontext
from types import SimpleNamespace

import pytest


KINDS = ("daily_course_record", "presurg_summary", "surgery_record", "postsurg_firstcourse_record")


@pytest.fixture(autouse=True)
def _isolated_material_runtime(monkeypatch):
    """在导入应用前禁用配置文件和网络，所有批准/连接均由合成fixture提供。"""
    import dotenv
    from pydantic_settings.sources import DotEnvSettingsSource
    import socket
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **kw: False)
    monkeypatch.setattr(DotEnvSettingsSource, "_load_env_vars", lambda self: {})
    monkeypatch.setattr(DotEnvSettingsSource, "__call__", lambda self: {})
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **kw: pytest.fail("材料单测禁止网络"))
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("JWT_SECRET", "synthetic-material-only-jwt-key-000000000000000")
    monkeypatch.delenv("QC_PRIMARY_FOUR_MATERIAL_ENABLED", raising=False)
    monkeypatch.delenv("QC_DAILY_MATERIAL_ENABLED", raising=False)


def synthetic_manifest():
    materials, items = [], []
    for kind in KINDS:
        for source in ("clinical", "cache"):
            version = kind + "-" + source
            materials.append({
                "version_id": version, "record_identity": "identity-" + version,
                "document_type": kind, "source_namespace": source,
                "native_key": ["I", "P", "V", "D"], "body": source + " body " + kind,
                "title": kind, "source_status": None, "record_status": None,
                "times": {"record_time": "2026-11-01T10:00:00+08:00", "surgery_begin_time": None},
                "time_availability": {"record_time": "EXPLICIT_OFFSET", "surgery_begin_time": "MISSING"},
                "time_role_status": {role: "UNCONFIRMED" for role in ("record_time", "submit_time", "modified_time", "surgery_begin_time", "surgery_end_time")},
                "source_times": {"surgery_begin_time": {"value": "original time", "business_semantics_approved": False}},
                "native_fields": {"zero": 0, "flag": False, "surgery_begin_time": "must not infer"},
                "target_payload": {"record_content": None if kind == "surgery_record" else source + " body " + kind,
                                   "surgery_process": source + " body " + kind if kind == "surgery_record" else None,
                                   "surgery_begin_time": "must not infer", "surgeon": "合成医生"},
                "publication": {"interface": ("web." if source == "cache" else "clinical.public.") + kind},
            })
        items.append({"document_type": kind, "association_key": kind, "selected_version": kind + "-cache",
                      "selection_reason": "CACHE_FALLBACK", "relation": "ALTERNATIVE_HELD",
                      "uncertain_fields": ["record_time"], "alternatives": [kind + "-clinical"],
                      "exclusions": {kind + "-clinical": ["CLINICAL_LIFECYCLE_HELD"]}})
    return {"contract": "clinical-primary-four-v1", "selection_id": "synthetic-selection",
            "policy_hash": "synthetic-policy", "case_id": "synthetic-case", "materials": materials,
            "items": items, "coverage": {kind: {"state": "BLOCKED"} for kind in KINDS},
            "absence_is_clinical_missing": False}


def state(value):
    return {"identity": ["I", "P", "V"], "binding": "", "schema": "cdm", "queries": {},
            "columns": {}, "tables": {}, "primary_material_manifest": value}


@pytest.mark.parametrize("kind", KINDS)
def test_selected_whole_version_across_reader_and_bundle_entrances(monkeypatch, kind):
    from app.database import clinical_connection as clinical
    from app.services import case_material_snapshot as material, primary_material_projection as primary
    from app.services.bundles import assembly
    from app.services.luxian_0609 import source_evidence_reader as reader
    value = synthetic_manifest()
    monkeypatch.setattr(assembly, "_source_engine", lambda *a: pytest.fail("selection bypassed"))
    args = dict(institute_id="I", patient_id="P", visit_id="V", source_schema="cdm")
    captured = state(value)
    captured["connection"] = SimpleNamespace(begin_nested=nullcontext)
    with clinical.selected({"id": "legacy_pg", "binding": ""}), material.recording(captured):
        bundle = assembly._select_records(schema="cdm", table=kind, institute_id="I", patient_id="P", visit_id="V")
        direct = assembly._material_rows(material_snapshot=SimpleNamespace(rows_for=lambda **kw: pytest.fail("unattested snapshot")),
                                         source_schema="cdm", table=kind, institute_id="I", patient_id="P", visit_id="V", limit=10)
        snapshot = reader.read_luxian_0609_snapshot_source_rows(source_key=kind, **args)
        native = reader.read_luxian_0609_native_source_rows(source_key=kind, **args)
        assert bundle[0]["version_id"] == direct[0]["version_id"] == snapshot.rows[0]["version_id"] == native[0]["version_id"] == kind + "-cache"
        assert snapshot.material_scope["status"] == "available"
        assert not snapshot.material_scope["can_judge_clinical_absence"]
        if kind in ("surgery_record", "presurg_summary"):
            runtime = reader.read_luxian_0609_runtime_source_rows(source_key=kind, **args)
            assert runtime[0]["version_id"] == kind + "-cache"
        assert primary.scope(kind)["coverage"] == {"state": "BLOCKED"}


def test_render_keeps_original_fields_and_held_versions_but_rule_times_are_not_inferred():
    from app.services import primary_material_projection as primary
    value = synthetic_manifest()
    surgery = primary.project_rows(value, "surgery_record")[0]
    assert surgery["record_content"] is None
    assert surgery["surgery_process"] == "cache body surgery_record"
    assert surgery.get("surgery_begin_time") is None
    assert surgery.get("record_datetime") is None
    docs = primary.project_documents(value)
    surgery_doc = next(doc for doc in docs if doc["version_id"] == "surgery_record-cache")
    assert surgery_doc["primary_material"]["native_fields"]["surgery_begin_time"] == "must not infer"
    assert len(docs) == 8
    assert sum(doc["material_rule_usable"] for doc in docs) == 4
    assert "cache body surgery_record" in next(doc["content"] for doc in docs if doc["version_id"] == "surgery_record-cache")
    assert len({doc["doc_key"] for doc in docs}) == 8


def test_held_empty_and_old_snapshot_are_distinct(monkeypatch):
    from app.services import case_material_snapshot as material, primary_material_projection as primary
    monkeypatch.setenv("QC_PRIMARY_FOUR_MATERIAL_ENABLED", "true")
    with pytest.raises(material.MaterialSnapshotError, match="capture_required"):
        primary.manifest(("I", "P", "V"))
    assert primary.manifest(("I", "pdfp_P", "pdfv_V")) is None
    with material.activate({"protocol": material.PROTOCOL}):
        assert primary.manifest() is None
    value = synthetic_manifest()
    value["items"][0].update(selected_version=None, selection_reason="HELD")
    assert primary.project_rows(value, "daily_course_record") == []
    assert primary.scope_from_manifest(value, "daily_course_record")["status"] == "held"
    assert primary.display_scope(value)["kinds"]["daily_course_record"]["held_count"] == 1


def test_programmatic_inventory_cannot_reintroduce_alternatives(monkeypatch):
    from app.database import clinical_connection as clinical
    from app.services import case_material_snapshot as material, sample_programmatic_evidence as programmatic
    captured = state(synthetic_manifest())
    captured["columns"] = {name: () for name in (*programmatic._SOURCE_TABLES, "inpat_registration")}
    with clinical.selected({"id": "legacy_pg", "binding": ""}), material.recording(captured):
        sources = programmatic.capture_programmatic_sources(captured, lambda: None)
    captured.update(protocol=material.PROTOCOL, programmatic_sources=sources)
    inventory = [{"source_table": kind, "document_id": "alternative", "content": "excluded"} for kind in KINDS]
    with clinical.selected({"id": "legacy_pg", "binding": ""}), material.activate(captured):
        payload = programmatic.build_programmatic_evidence_payload(bundle={"institute_id": "I", "patient_id": "P", "visit_id": "V", "source_documents": inventory})
    for kind in KINDS:
        docs = payload["programmatic_timeline"]["documents"][kind]
        assert len(docs) == 1
        assert docs[0]["content"] == "cache body " + kind
        assert "alternative" not in docs[0]["document_id"]


def test_scope_overrides_missing_base_table_without_automatic_metadata():
    from app.services import case_material_snapshot as material, automatic_material_scope as automatic
    with material.recording(state(synthetic_manifest())):
        assert automatic.source_scope("surgery_record")["status"] == "available"


def test_corrupt_selected_reference_is_not_an_empty_success():
    from app.services import primary_material_projection as primary, case_material_snapshot as material
    value = synthetic_manifest()
    value["items"][0]["selected_version"] = "missing"
    with pytest.raises(material.MaterialSnapshotError, match="manifest_invalid"):
        primary.project_rows(value, "daily_course_record")


def test_live_programmatic_sources_borrow_capture_instead_of_business_engine(monkeypatch):
    from app.database import clinical_connection as clinical
    from app.services import case_material_snapshot as material, sample_programmatic_evidence as programmatic
    from app.services.bundles import assembly
    captured = state(synthetic_manifest())
    monkeypatch.setattr(programmatic, "engine", SimpleNamespace(connect=lambda: pytest.fail("business engine bypass")))
    monkeypatch.setattr(assembly, "_get_table_columns", lambda *args: ())
    payload = {"institute_id": "I", "patient_id": "P", "visit_id": "V"}
    with clinical.selected({"id": "legacy_pg", "binding": ""}), material.recording(captured):
        items, _ = programmatic._fetch_source_table_fallback_items(payload)
    assert len(items) == 4
    assert set(payload["_material_scope"]) == set(KINDS)


def test_body_conflict_does_not_reappear_via_title_or_structured_body_aliases():
    from app.services import primary_material_projection as primary
    from app.services import sample_programmatic_evidence as programmatic
    value = synthetic_manifest()
    value["items"][0].update(relation="VERSION_DIFFERENCE", uncertain_fields=["body"])
    rows = primary.project_rows(value, "daily_course_record")
    assert rows[0]["record_content"] is None
    assert "body" not in rows[0]["primary_material"]
    assert "native_fields" not in rows[0]["primary_material"]
    assert "target_payload" not in rows[0]["primary_material"]
    assert programmatic._project_fallback_rows("daily_course_record", rows)[0]["content"] == ""
    assert "cache body daily_course_record" in primary.project_documents(value)[1]["content"]


def test_cache_explicit_time_without_additive_role_status_keeps_selector_meaning():
    from app.services import primary_material_projection as primary
    value = synthetic_manifest()
    entry = value["materials"][1]
    entry.pop("time_role_status")
    value["items"][0]["uncertain_fields"] = []
    row = primary.project_rows(value, "daily_course_record")[0]
    assert row["record_datetime"] == entry["times"]["record_time"]
    assert row["surgery_begin_time"] is None
    value["items"][0]["uncertain_fields"] = ["record_time"]
    assert primary.project_rows(value, "daily_course_record")[0]["record_datetime"] is None
    value["items"][0]["uncertain_fields"] = []
    entry["time_role_status"] = {"record_time": "UNCONFIRMED"}
    assert primary.project_rows(value, "daily_course_record")[0]["record_datetime"] is None
    value["items"][0].update(selected_version="daily_course_record-clinical", selection_reason="CLINICAL_PRIMARY")
    assert primary.project_rows(value, "daily_course_record")[0]["record_datetime"] is None
