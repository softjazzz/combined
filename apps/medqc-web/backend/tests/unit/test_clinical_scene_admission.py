"""候选筛选、任务场景和受控拒绝使用同一真实仓库；数据全为合成。"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import clinical_connection
from app.services.bundles import assembly
from app.services.case_identity import CaseRef
from app.services.qc_workspace import record_repository as repo_module


REF = CaseRef("SYNTHETIC_ORG", "SYNTHETIC_PATIENT", "SYNTHETIC_VISIT")
FILTERS = dict(scope="all", department=None, doctor=None, date_field="admission",
               start_date=None, end_date=None, keyword=None, record_refs=[REF])


@pytest.fixture
def source(monkeypatch):
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(clinical_connection, "get_engine", lambda: None)
    engine = create_engine("sqlite:///:memory:")
    for model in (repo_module.InpatRegistration, repo_module.AdmissionRecord, repo_module.DischargeRecord,
                  repo_module.HospitalizationStatusProjection):
        model.__table__.create(engine)
    with Session(engine) as session:
        session.add(repo_module.InpatRegistration(**REF.as_dict(), admission_datetime=datetime(2026, 1, 1)))
        session.commit()
    repository = repo_module.RecordRepository(session_factory=lambda: Session(engine))
    yield engine, repository
    engine.dispose()


def add_projection(engine, *, status="discharged", identity=REF, age=0, source="source_active_scope"):
    with Session(engine) as session:
        session.add(repo_module.HospitalizationStatusProjection(**identity.as_dict(), status=status,
            source=source, verified_at=datetime.now() - timedelta(days=age, seconds=1)))
        session.commit()


def test_no_discharge_is_unknown_not_evidence_of_current_inpatient(source):
    _, repository = source
    [row] = repository.collect_records(**FILTERS)
    assert row["scope"] == row["qc_scope"] == row["status"] == "unknown"
    assert row["qc_scene_reason"] == "discharge_state_unknown"
    assert row["qc_allowed_scopes"] == []
    for scope in ("running", "final"):
        assert repository.collect_records(**{**FILTERS, "scope": scope}) == []


def test_missing_optional_projection_never_requires_new_source_table(source):
    engine, repository = source
    repo_module.HospitalizationStatusProjection.__table__.drop(engine)
    [row] = repository.collect_records(**FILTERS)
    assert row["qc_scope"] == "unknown"


def test_legacy_projection_cannot_confirm_scene_or_introduce_new_read_dependency(source):
    engine, repository = source
    add_projection(engine, source="inpat_registration")

    def deny_projection(conn, cursor, statement, params, context, many):
        if statement.lstrip().startswith("SELECT") and "hospitalization_status_projection" in statement:
            raise OperationalError("synthetic access denied", {}, None)

    event.listen(engine, "before_cursor_execute", deny_projection)
    [row] = repository.collect_records(**FILTERS)
    assert row["qc_scope"] == "unknown"


def test_confirmed_discharge_without_time_is_final_with_missing_time_horizon(source):
    from app.routers.qc_sichuan import _build_workspace_record_scene_snapshot
    from app.services.luxian_0609.evaluation_horizon import build_record_evaluation_horizon_snapshot
    from app.services.clinical_scene_admission import resolve_scene
    from app.services.discharge_time import DischargeTime
    # 只验证纯合同：现有legacy投影没有可信状态依据，生产仓库不把它传入此参数。
    row = {**REF.as_dict(), "record_id": REF.visit_id, "scope": "final",
        "qc_admission_datetime": "2026-01-01", "qc_discharge_datetime": "", "discharge_datetime": "",
        "qc_scene_source": "synthetic_confirmed_state", "qc_scene_verified_at": "",
        **resolve_scene(discharge=DischargeTime(), document_present=True, document_invalid=False,
                        verified_status="discharged")}
    assert row["scope"] == row["qc_scope"] == "final"
    assert row["qc_discharge_state"] == "discharged"
    assert row["qc_discharge_time_status"] == "missing"
    assert row["discharge_datetime"] == row["qc_discharge_datetime"] == ""
    [scene] = _build_workspace_record_scene_snapshot([row], query_scope="all", primary_documents_only=True)
    assert scene["record_scene"] == scene["resolved_scene"] == "final"
    assert scene["scene_reason"] == "verified_discharge_state"
    assert scene["scene_source"] == "synthetic_confirmed_state" and scene["scene_verified_at"] == ""
    assert scene["discharge_snapshot"] == ""
    [horizon] = build_record_evaluation_horizon_snapshot([row], task_frozen_date="2026-11-16")
    assert horizon["evaluation_horizon"] == ""
    assert horizon["resolution_status"] == "authoritative_time_missing"


@pytest.mark.parametrize("status", [None, "Save", "删除"])
def test_structured_discharge_document_without_validity_confirmation_does_not_force_final(source, status):
    engine, repository = source
    with Session(engine) as session:
        session.add(repo_module.DischargeRecord(**REF.as_dict(), document_id="SYNTHETIC_D",
            document_status=status, treatment_course="合成诊疗经过", discharge_order="合成出院医嘱"))
        session.commit()
    [row] = repository.collect_records(**FILTERS)
    assert row["qc_scope"] == "unknown"
    assert row["qc_discharge_state"] == "unknown" and row["qc_discharge_datetime"] == ""
    assert row["qc_scene_reason"] == "discharge_document_unconfirmed"


@pytest.mark.parametrize("age,status,identity,source_name", [
    (2, "inpatient", REF, "source_active_scope"),
    (0, "inpatient", CaseRef("OTHER_ORG", "SYNTHETIC_PATIENT", "SYNTHETIC_VISIT"), "source_active_scope"),
    (0, "inpatient", CaseRef("SYNTHETIC_ORG", "OTHER_PATIENT", "SYNTHETIC_VISIT"), "source_active_scope"),
    (0, "inpatient", CaseRef("SYNTHETIC_ORG", "SYNTHETIC_PATIENT", "OTHER_VISIT"), "source_active_scope"),
    (0, "inpatient", REF, ""),
    (0, "unknown", REF, "source_active_scope"),
])
def test_stale_cross_identity_or_unproven_projection_never_confirms_scene(source, age, status, identity, source_name):
    engine, repository = source
    add_projection(engine, age=age, status=status, identity=identity, source=source_name)
    [row] = repository.collect_records(**FILTERS)
    assert row["qc_scope"] == "unknown"


def test_confirmed_inpatient_contract_does_not_hide_positive_discharge_conflict():
    from app.services.clinical_scene_admission import resolve_scene
    from app.services.discharge_time import DischargeTime
    row = resolve_scene(discharge=DischargeTime(), document_present=False,
                        document_invalid=False, verified_status="inpatient")
    assert row["qc_scope"] == "running"
    row = resolve_scene(discharge=DischargeTime(datetime(2026, 1, 3), "inpat_registration.discharge_datetime"),
                        document_present=False, document_invalid=False, verified_status="inpatient")
    assert row["qc_scope"] == "unknown" and row["qc_scene_reason"] == "discharge_state_conflict"


def test_old_frozen_scene_is_not_reclassified_using_new_source_policy():
    from copy import deepcopy
    from app.services.luxian_0609.clinical_material_policy import (
        CLINICAL_MATERIAL_POLICY_VERSION, apply_frozen_clinical_scene,
    )
    frozen = {**REF.as_dict(), "clinical_material_policy": CLINICAL_MATERIAL_POLICY_VERSION, "record_scene": "running"}
    original = deepcopy(frozen)
    record = {**REF.as_dict(), "qc_scope": "final", "qc_admission_datetime": "2026-01-01"}
    assert apply_frozen_clinical_scene(record, frozen)["scope"] == "running"
    assert frozen == original


def test_filter_based_creation_without_explicit_refs_uses_same_admission(source, monkeypatch):
    from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
    engine, repository = source
    with Session(engine) as session:
        session.query(repo_module.InpatRegistration).update({"discharge_datetime": datetime(2026, 1, 3)})
        session.commit()
    owner = CustomQCWorkspaceService.__new__(CustomQCWorkspaceService)
    monkeypatch.setattr(owner, "_record_repository", lambda: repository)
    records, rejected = owner.collect_records_for_admission(**{**FILTERS, "scope": "final", "record_refs": None})
    assert len(records) == 1 and records[0]["qc_scope"] == "final" and rejected == []


def test_filter_based_final_selection_does_not_admit_or_reject_unselected_unknown_cases(source, monkeypatch):
    from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
    engine, repository = source
    with Session(engine) as session:
        session.query(repo_module.InpatRegistration).update({"discharge_datetime": datetime(2026, 1, 3)})
        session.commit()
    with Session(engine) as session:
        session.add(repo_module.InpatRegistration(institute_id="SYNTHETIC_ORG", patient_id="UNSELECTED",
            visit_id="UNSELECTED", admission_datetime=datetime(2026, 1, 1)))
        session.commit()
    owner = CustomQCWorkspaceService.__new__(CustomQCWorkspaceService)
    monkeypatch.setattr(owner, "_record_repository", lambda: repository)
    records, rejected = owner.collect_records_for_admission(**{**FILTERS, "scope": "final", "record_refs": None})
    assert [CaseRef.from_mapping(record) for record in records] == [REF]
    assert rejected == []


@pytest.mark.asyncio
@pytest.mark.parametrize("scope,confirmed,allowed", [("final", True, True), ("running", True, False),
                                                   ("final", False, False), ("all", False, False)])
async def test_creation_uses_same_admission_as_candidates_and_freezes_reason(source, monkeypatch, scope, confirmed, allowed):
    from fastapi import HTTPException
    from app.routers import qc_sichuan
    from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
    from tests.unit.test_qc_sichuan_batch_throughput import _WorkspaceStub, _ServiceStub, _luxian_native_settings
    engine, repository = source
    if confirmed:
        with Session(engine) as session:
            session.query(repo_module.InpatRegistration).update({"discharge_datetime": datetime(2026, 1, 3)})
            session.commit()
    owner = CustomQCWorkspaceService.__new__(CustomQCWorkspaceService)
    monkeypatch.setattr(owner, "_record_repository", lambda: repository)
    workspace = _WorkspaceStub()
    workspace.collect_records_for_admission = owner.collect_records_for_admission
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "get_settings", _luxian_native_settings)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *args: pytest.fail("测试不得启动worker"))
    monkeypatch.setattr(qc_sichuan, "_dispatch_sichuan_workspace_batch_job", lambda **kwargs: None, raising=False)
    from app.services import saved_result_access
    monkeypatch.setattr(saved_result_access, "saved_result_institute_scope", lambda _actor_id: None)
    args = dict(request=SimpleNamespace(state=SimpleNamespace()),
        payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
            rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY, scope=scope, record_refs=[REF.as_dict()]),
        qc_service=_ServiceStub(), current_user={"id": "synthetic-user", "role": "super_admin"})
    if allowed:
        # 只验证创建投影，创建之后的派发替身不执行规则。
        monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *args: None)
        result = await qc_sichuan.create_workspace_batch_job(**args)
        assert result["success"]
        [scene] = workspace.created_job["filters"]["record_scene_snapshot"]
        assert scene["resolved_scene"] == "final" and scene["discharge_snapshot"] == "2026-01-03 00:00:00"
    else:
        with pytest.raises(HTTPException) as error:
            await qc_sichuan.create_workspace_batch_job(**args)
        assert error.value.status_code == 422
        assert error.value.detail["code"] == "case_scene_admission_failed"
        assert error.value.detail["cases"][0]["selection_index"] == 0
        assert "SYNTHETIC_PATIENT" not in str(error.value.detail)
        assert workspace.created_job is None


def test_valid_death_record_confirms_final_scene_without_discharge_record(source):
    engine, repository = source
    repo_module.DeathRecord.__table__.create(engine)
    with Session(engine) as session:
        session.add(repo_module.DeathRecord(
            **REF.as_dict(),
            document_id="SYNTHETIC_DEATH",
            document_status="Save",
            death_datetime=datetime(2026, 7, 29, 14, 34),
        ))
        session.commit()
    [row] = repository.collect_records(**FILTERS)
    assert row["scope"] == row["qc_scope"] == "final"
    assert row["qc_discharge_state"] == "discharged"
    assert row["qc_scene_reason"] == "discharge_business_time"
    assert row["qc_scene_source"] == "death_record.death_datetime"
    assert row["qc_discharge_datetime"] == "2026-07-29 14:34:00"


def test_invalid_death_record_does_not_confirm_final_scene(source):
    engine, repository = source
    repo_module.DeathRecord.__table__.create(engine)
    with Session(engine) as session:
        session.add(repo_module.DeathRecord(
            **REF.as_dict(),
            document_id="SYNTHETIC_DEATH_VOID",
            document_status="作废",
            death_datetime=datetime(2026, 7, 29, 14, 34),
        ))
        session.commit()
    [row] = repository.collect_records(**FILTERS)
    assert row["qc_scope"] == "unknown"
    assert row["qc_discharge_state"] == "unknown"
    assert row["qc_discharge_time_status"] == "conflict"


def test_valid_death_record_recovers_empty_discharge_record(source):
    engine, repository = source
    repo_module.DeathRecord.__table__.create(engine)
    with Session(engine) as session:
        session.add(repo_module.DischargeRecord(**REF.as_dict(), document_id="SYNTHETIC_EMPTY_DISC"))
        session.add(repo_module.DeathRecord(
            **REF.as_dict(),
            document_id="SYNTHETIC_DEATH",
            document_status="Save",
            death_datetime=datetime(2026, 1, 1, 17, 16),
        ))
        session.commit()
    [row] = repository.collect_records(**FILTERS)
    assert row["qc_scope"] == "final"
    assert row["qc_scene_source"] == "death_record.death_datetime"
    assert row["qc_discharge_datetime"] == "2026-01-01 17:16:00"
