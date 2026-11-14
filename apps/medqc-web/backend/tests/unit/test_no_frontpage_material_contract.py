"""首页不参与新任务依赖；旧证据版本仍可被严格识别。"""
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import source_registry as registry
from app.services.luxian_0609.clinical_material_policy import FRONTPAGE_SOURCE_KEYS
from app.services.luxian_0609.phase_scope import (
    partition_luxian_0609_rule_scope, build_luxian_0609_pending_definition_result,
)


def test_current_rule_dependencies_do_not_require_frontpage():
    ids = tuple(item.rule_id for item in registry.load_luxian_0609_rule_contracts())
    executable, _ = partition_luxian_0609_rule_scope(ids)
    entries = registry.resolve_luxian_0609_rule_sources(executable)
    for rules in entries.values():
        for entry in rules:
            assert not FRONTPAGE_SOURCE_KEYS.intersection(entry.source_keys)
    assert not FRONTPAGE_SOURCE_KEYS.intersection(
        registry.resolve_luxian_0609_decision_support_source_keys(executable)
    )


def test_frontpage_comparison_is_pending_not_data_gap():
    executed, withheld = partition_luxian_0609_rule_scope(("LX0609-08-01-03",))
    assert executed == () and withheld == ("LX0609-08-01-03",)
    result = build_luxian_0609_pending_definition_result(withheld[0])
    assert result["status"] == "not_executed"
    assert result["reason_code"] == "policy_definition_pending"
    assert result["is_compliant"] is None


def test_saved_frontpage_source_versions_are_not_rewritten():
    assert registry.source_key_accepts_query_version("mr_surgery", "snapshot-provider-surgery_record-v2")
    assert registry.source_key_accepts_query_version("mr_bloodtrans", "snapshot-provider-bloodtrans_record-v2")
    assert registry.source_key_accepts_query_version("inpat_registration", "snapshot-provider-inpat_registration-v2")
    assert not registry.source_key_accepts_query_version("mr_surgery", "forged-v1")


@pytest.mark.parametrize("key", sorted(FRONTPAGE_SOURCE_KEYS))
def test_frontpage_cannot_be_explicitly_added_to_new_physical_session(key):
    with pytest.raises(ValueError, match="not uniquely registered"):
        registry.resolve_luxian_0609_physical_source_entry(key)


def test_current_capture_does_not_read_frontpage_tables_or_native_queries(monkeypatch):
    from app.services import case_material_capture as capture, daily_material_projection, sample_programmatic_evidence
    from app.services.bundles import assembly, current_view
    from app.services.luxian_0609 import source_evidence_reader as reader
    from app.services.luxian_0609.clinical_material_policy import CLINICAL_MATERIAL_POLICY_VERSION

    class Connection:
        def execution_options(self, **_):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def begin(self):
            return nullcontext()

        def exec_driver_sql(self, statement):
            assert statement.startswith("SET ")

    connection = Connection()
    monkeypatch.setattr(assembly, "_source_engine", lambda _: SimpleNamespace(connect=lambda: connection))
    monkeypatch.setattr(capture.clinical, "configured", lambda: False)
    monkeypatch.setattr(daily_material_projection, "enabled", lambda: False)
    read_keys = []

    def read_table(**kwargs):
        key = kwargs["table"]
        assert key not in FRONTPAGE_SOURCE_KEYS
        read_keys.append(key)
        return []

    def has_table(table, **_):
        assert table not in FRONTPAGE_SOURCE_KEYS
        return False

    monkeypatch.setattr(capture, "inspect", lambda _: SimpleNamespace(has_table=has_table))
    monkeypatch.setattr(assembly, "_select_records", read_table)
    monkeypatch.setattr(sample_programmatic_evidence, "capture_programmatic_sources", lambda *_: {})
    monkeypatch.setattr(current_view, "_assemble_current_documents", lambda **_: {"documents": []})
    for name in ("read_luxian_0609_course_round_timeline", "has_luxian_0609_current_visit_unstable_order",
                 "read_luxian_0609_severity_order_rows", "read_luxian_0609_exam_lab_order_rows",
                 "read_luxian_0609_rescue_order_rows", "read_luxian_0609_discharge_horizon_rows"):
        monkeypatch.setattr(reader, name, lambda **_: ())

    def read_native(**kwargs):
        key = kwargs["source_key"]
        assert key not in FRONTPAGE_SOURCE_KEYS
        read_keys.append(key)
        return ()

    for name in ("read_luxian_0609_snapshot_source_rows", "read_luxian_0609_native_source_rows", "read_luxian_0609_runtime_source_rows"):
        monkeypatch.setattr(reader, name, read_native)
    state = capture.capture(identity=("synthetic-I", "synthetic-P", "synthetic-V"))
    assert state["clinical_material_policy"] == CLINICAL_MATERIAL_POLICY_VERSION
    assert "surgery_record" in read_keys and "bloodtrans_record" in read_keys
    assert not FRONTPAGE_SOURCE_KEYS.intersection(state["tables"])


def test_qc_profile_and_snapshot_exclude_frontpage_but_view_profile_remains(monkeypatch):
    from app.services import case_material_snapshot as material
    from app.services.bundles import assembly
    from app.services.luxian_0609.clinical_material_policy import CLINICAL_MATERIAL_POLICY_VERSION

    reads = []

    def rows(**kwargs):
        reads.append(kwargs["table"])
        return [{"name": "合成患者"}] if kwargs["table"] == "mr" else []

    monkeypatch.setattr(assembly, "_material_rows", rows)
    coordinates = dict(source_schema="cdm", institute_id="I", patient_id="P", visit_id="V")
    assert assembly._fetch_patient_profile(**coordinates)["patient_name"] == "合成患者"
    reads.clear()
    with material.activate({"clinical_material_policy": CLINICAL_MATERIAL_POLICY_VERSION}):
        assert assembly._fetch_patient_profile(**coordinates)["patient_name"] == ""
    assert reads == ["patient_information"]


def test_task_horizon_never_restores_frontpage_time_when_original_time_missing():
    from app.services.luxian_0609.evaluation_horizon import build_record_evaluation_horizon_snapshot
    record = dict(record_id="V", institute_id="I", patient_id="P", visit_id="V", scope="final",
                  admission_datetime="2026-01-01 08:00:00", discharge_datetime="2026-01-05 08:00:00",
                  qc_admission_datetime=None, qc_discharge_datetime=None)
    [frozen] = build_record_evaluation_horizon_snapshot([record], task_frozen_date="2026-01-10")
    assert frozen["admission_datetime"] == frozen["discharge_datetime"] == ""
    assert frozen["resolution_status"] == "scene_uncertain"


def test_legacy_frontpage_timeline_cannot_supply_trusted_admission_time():
    from app.services.sample_programmatic_evidence import _resolve_admission_time
    value, _, trusted = _resolve_admission_time(structured={}, bundle_payload={}, fallback_meta={},
        timeline_facts=[{"source_table": "mr", "field": "admission_datetime", "value": "2026-01-01 08:00:00"}],
        documents={}, medical_text="")
    assert not value and trusted is False


def test_frontpage_discharge_does_not_make_original_inpatient_task_final():
    from datetime import datetime
    from app.services.qc_workspace.record_repository import RecordRepository, MedicalRecordFrontpage
    from app.services.luxian_0609.evaluation_horizon import build_record_evaluation_horizon_snapshot
    admission = datetime(2026, 1, 1, 8)
    frontpage_discharge = datetime(2026, 1, 5, 8)
    frontpage = MedicalRecordFrontpage(institute_id="I", patient_id="P", visit_id="V",
        admission_datetime=admission, discharge_datetime=frontpage_discharge)
    row = RecordRepository(session_factory=lambda: pytest.fail("不允许连接数据库"))._serialize_record_row((frontpage, frontpage_discharge, admission,
        None, None, None, None, admission, admission))
    assert row["scope"] == "final"  # 既有病历池展示不改写。
    assert row["qc_scope"] == "running"
    [frozen] = build_record_evaluation_horizon_snapshot([row], task_frozen_date="2026-01-10")
    assert frozen["record_scene"] == "running"
    assert frozen["evaluation_basis"] == "task_frozen_date"
    assert frozen["evaluation_horizon"] == "2026-01-10"
    assert frozen["discharge_datetime"] == ""


@pytest.mark.parametrize("has_frontpage", [False, True])
def test_scene_freeze_and_worker_input_share_original_scene_and_keep_old_path(has_frontpage):
    from app.routers.qc_sichuan import _build_workspace_record_scene_snapshot
    from app.services.luxian_0609.evaluation_horizon import build_record_evaluation_horizon_snapshot
    from app.services.sichuan_workspace_batch_worker import apply_frozen_clinical_scene, frozen_clinical_scene
    record = dict(record_id="V", institute_id="I", patient_id="P", visit_id="V", scope="running",
                  admission_datetime="2026-01-01 08:00:00", discharge_datetime="")
    if has_frontpage:
        record.update(scope="final", discharge_datetime="2026-01-05 08:00:00",
                      qc_scope="running", qc_admission_datetime="2026-01-01 08:00:00", qc_discharge_datetime="")
    [scene] = _build_workspace_record_scene_snapshot([record], query_scope="final", primary_documents_only=True)
    [frozen] = build_record_evaluation_horizon_snapshot([record], task_frozen_date="2026-01-10")
    assert scene["record_scene"] == scene["resolved_scene"] == frozen["record_scene"] == "running"
    assert scene["discharge_snapshot"] == ""
    assert apply_frozen_clinical_scene(record, frozen)["scope"] == frozen_clinical_scene(frozen) == "running"
    assert apply_frozen_clinical_scene(record, {"record_scene": "final"}) == record
    assert frozen_clinical_scene({"record_scene": "final"}) is None
    with pytest.raises(ValueError, match="identity mismatch"):
        apply_frozen_clinical_scene({**record, "patient_id": "other"}, frozen)
