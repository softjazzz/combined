from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.database.models.cdm import (
    AdmissionRecord,
    BloodApplication,
    ConsultationRecord,
    ExamMaster,
    FirstCourseRecord,
    HandoffRecord,
    HandoverRecord,
    InpatDrugOrder,
    InpatNondrugOrder,
    SurgeryRecord,
)
from app.services import etl_sync, mongo_sync, sync_run_history
from app.services.case_identity import CaseRef
from app.services.case_scope_service import HospitalizationScopeResult
from app.services.case_set_sync_service import CaseSetSyncResult
from app.services.luxian_0609.exam_lab_fact_extraction import _row_text
from app.services.luxian_0609.source_evidence_reader import _SNAPSHOT_SOURCE_FIELDS


def _load_migration_module(filename: str):
    path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(f"test_migration_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_estimate_pg_sync_impact_uses_running_case_refs_without_mr_no(monkeypatch):
    calls = []

    class _ScopeService:
        def resolve_hospitalization_scope(self, **kwargs):
            calls.append(kwargs)
            return HospitalizationScopeResult(
                case_refs=(CaseRef("H1", "P1", "V1"),),
                selected=(
                    {
                        "institute_id": "H1",
                        "patient_id": "P1",
                        "visit_id": "V1",
                        "mr_no": "",
                        "source_table": "inpat_registration",
                    },
                ),
                all_selected=(),
                sources_used=("inpat_registration",),
                source_status="ready",
                warnings=(),
            )

    monkeypatch.setattr(etl_sync, "load_sync_policy", lambda: {})
    monkeypatch.setattr(etl_sync, "_create_case_scope_service", lambda: _ScopeService())
    monkeypatch.setattr(
        etl_sync, "_current_hospital_date", lambda: date(2026, 8, 14), raising=False
    )

    result = etl_sync.estimate_pg_sync_impact(
        scene="running",
        date_window=None,
        target_departments=["重症医学科(ICU)"],
    )

    assert result["estimated_impact"] == 1
    assert result["estimate_basis"] == "case_ref_count"
    assert result["sources_used"] == ["inpat_registration"]
    assert calls == [
        {
            "scope_mode": "active",
            "as_of_date": date(2026, 8, 14),
            "admission_start_date": date(2026, 2, 15),
            "discharge_start_date": None,
            "discharge_end_date": None,
            "departments": ["重症医学科(ICU)"],
        }
    ]
    assert result["date_window"] == {"start": "", "end": "2026-08-14"}


def test_estimate_pg_sync_impact_explicit_all_hospital_ignores_saved_departments(
    monkeypatch,
):
    calls = []

    class _ScopeService:
        def resolve_hospitalization_scope(self, **kwargs):
            calls.append(kwargs)
            return HospitalizationScopeResult(
                case_refs=(CaseRef("H1", "P1", "V1"),),
                selected=(),
                all_selected=(),
                sources_used=("discharge_record",),
                source_status="ready",
                warnings=(),
            )

    monkeypatch.setattr(
        etl_sync,
        "load_sync_policy",
        lambda: {"target_departments": ["历史保存科室"]},
    )
    monkeypatch.setattr(etl_sync, "_create_case_scope_service", lambda: _ScopeService())

    result = etl_sync.estimate_pg_sync_impact(
        scene="final",
        date_window={"start": "2026-08-07", "end": "2026-08-13"},
        target_departments=["*"],
    )

    assert result["target_departments"] == ["*"]
    assert calls[0]["departments"] == []


def test_estimate_pg_sync_impact_rejects_placeholder_institute(monkeypatch):
    class _ScopeService:
        def resolve_hospitalization_scope(self, **_kwargs):
            return HospitalizationScopeResult(
                case_refs=(CaseRef("LOCAL-HOSPITAL", "P1", "V1"),),
                selected=(),
                all_selected=(),
                sources_used=("inpat_registration",),
                source_status="ready",
                warnings=(),
            )

    monkeypatch.setattr(etl_sync, "load_sync_policy", lambda: {})
    monkeypatch.setattr(etl_sync, "_create_case_scope_service", lambda: _ScopeService())

    with pytest.raises(ValueError, match="稳定机构标识"):
        etl_sync.estimate_pg_sync_impact(
            scene="running",
            date_window={"start": "2026-07-01", "end": "2026-07-31"},
        )


def test_list_remote_departments_uses_discharge_department_field(monkeypatch):
    executed: list[tuple[str, tuple]] = []

    class _FakeCursor:
        def execute(self, sql, params=None):
            executed.append((str(sql), tuple(params or ())))

        def fetchall(self):
            return [
                {"dept_name": "骨科"},
                {"dept_name": "普通外科"},
                {"dept_name": ""},
            ]

        def close(self):
            return None

    class _FakeConn:
        def cursor(self, cursor_factory=None):
            return _FakeCursor()

        def close(self):
            return None

    monkeypatch.setattr(etl_sync, "get_remote_db_url", lambda: "postgresql://source")
    monkeypatch.setattr(etl_sync, "load_db_config", lambda: {"remote_schema": "public"})
    monkeypatch.setattr(etl_sync, "_remote_table_exists", lambda *_args: True)
    monkeypatch.setattr(
        etl_sync,
        "_remote_column_exists",
        lambda _cursor, _schema, _table, column: column == "discharge_dept_name",
    )
    monkeypatch.setattr(etl_sync.psycopg2, "connect", lambda *_args, **_kwargs: _FakeConn())

    result = etl_sync.list_remote_departments(limit=100)

    assert result["items"] == ["骨科", "普通外科"]
    assert result["source_column"] == "discharge_dept_name"
    assert "discharge_dept_name" in executed[0][0]


def test_split_schema_cdm_sync_tables_prefer_cdm_over_public(monkeypatch):
    monkeypatch.setattr(etl_sync, "DB_SCHEMA_MODE", "split")
    monkeypatch.setattr(etl_sync, "_LOCAL_TARGET_SCHEMAS", ("public", "cdm"))

    assert etl_sync._resolve_local_table_schema_priority("labtest_item_report")[0] == "cdm"
    assert etl_sync._resolve_local_table_schema_priority("blood_application")[0] == "cdm"


def test_single_schema_keeps_configured_local_schema_order(monkeypatch):
    monkeypatch.setattr(etl_sync, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(etl_sync, "_LOCAL_TARGET_SCHEMAS", ("public", "cdm"))

    assert etl_sync._resolve_local_table_schema_priority("labtest_item_report") == ("public", "cdm")


def test_resolve_local_table_schema_chooses_cdm_when_duplicate_cdm_table_exists(monkeypatch):
    class _FakeResult:
        def fetchall(self):
            return [("public",), ("cdm",)]

    class _FakeSession:
        def execute(self, stmt, params=None):
            return _FakeResult()

    monkeypatch.setattr(etl_sync, "DB_SCHEMA_MODE", "split")
    monkeypatch.setattr(etl_sync, "_LOCAL_TARGET_SCHEMAS", ("public", "cdm"))

    assert etl_sync._resolve_local_table_schema(_FakeSession(), "labtest_item_report") == "cdm"
    assert etl_sync._resolve_local_table_schema(_FakeSession(), "blood_application") == "cdm"


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


def test_run_sync_rejects_when_advisory_lock_not_acquired(monkeypatch):
    class _FakeConn:
        def execute(self, stmt, params=None):
            sql = str(stmt)
            if "pg_try_advisory_lock" in sql:
                return _ScalarResult(False)
            raise AssertionError(f"unexpected SQL: {sql}")

        def close(self):
            return None

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    monkeypatch.setattr(etl_sync, "engine", _FakeEngine())
    monkeypatch.setattr(etl_sync, "_upsert_sync_job_state", lambda _state: None)
    result = etl_sync.run_sync(sync_date="2026-03-25", tables=["mr", "admission_record", "discharge_record"])
    assert result["success"] is False
    assert "同步正在进行中" in result["error"]


def test_run_sync_running_delegates_once_to_public_case_services(monkeypatch):
    progress_events: list[dict] = []
    scope_calls: list[dict] = []
    sync_calls: list[dict] = []
    case_refs = (
        CaseRef("H1", "P1", "SAME-VISIT"),
        CaseRef("H2", "P2", "SAME-VISIT"),
    )

    class _FakeConn:
        def execute(self, stmt, params=None):
            sql = str(stmt)
            if "pg_try_advisory_lock" in sql or "pg_advisory_unlock" in sql:
                return _ScalarResult(True)
            raise AssertionError(f"unexpected SQL: {sql}")

        def close(self):
            return None

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    class _ScopeService:
        def resolve_hospitalization_scope(self, **kwargs):
            scope_calls.append(kwargs)
            rows = tuple(
                {
                    **case_ref.as_dict(),
                    "hospitalization_status": "active",
                    "admission_time": "2026-08-01 08:00:00",
                    "authoritative_time": "2026-08-01 08:00:00",
                    "department": "重症医学科（ICU）",
                    "department_basis": "current_department",
                    "source_table": "inpat_registration",
                }
                for case_ref in case_refs
            )
            return HospitalizationScopeResult(
                case_refs=case_refs,
                selected=rows,
                all_selected=rows,
                sources_used=("inpat_registration",),
                source_status="ready",
                warnings=(),
            )

    class _SyncService:
        def sync_case_set(self, **kwargs):
            sync_calls.append(kwargs)
            callback = kwargs["progress_callback"]
            callback(
                {
                    "step_key": "primary_visible",
                    "current_table": "",
                    "processed_tables": 1,
                    "total_tables": 4,
                }
            )
            callback(
                {
                    "step_key": "bundle_refresh",
                    "current_table": "",
                    "processed_tables": 4,
                    "total_tables": 4,
                    "bundle_progress": {
                        "total": 2,
                        "completed": 1,
                        "remaining": 1,
                    },
                }
            )
            callback(
                {
                    "step_key": "completed",
                    "current_table": "",
                    "processed_tables": 4,
                    "total_tables": 4,
                }
            )
            return CaseSetSyncResult(
                case_refs=case_refs,
                primary_visible=True,
                visible_case_refs=case_refs,
                missing_primary_case_refs=(),
                synced_tables=(
                    {
                        "table_name": "mr",
                        "rows_pulled": 2,
                        "rows_upserted": 2,
                        "sync_status": "synced",
                    },
                    {
                        "table_name": "daily_course_record",
                        "rows_pulled": 1,
                        "rows_upserted": 1,
                        "sync_status": "synced",
                    },
                ),
                source_rows_by_table={},
                total_rows_pulled=3,
                total_rows_upserted=3,
                bundle_refresh={"scenes": {}, "domains": {}},
            )

    target_tables = [
        {"name": name, "source_table": name, "label": name}
        for name in ("mr", "admission_record", "discharge_record", "daily_course_record")
    ]
    monkeypatch.setattr(etl_sync, "engine", _FakeEngine())
    monkeypatch.setattr(etl_sync, "_upsert_sync_job_state", lambda _state: None)
    monkeypatch.setattr(etl_sync, "get_remote_db_url", lambda: "postgresql://source")
    monkeypatch.setattr(
        etl_sync,
        "load_db_config",
        lambda: {
            "remote_schema": "public",
            "sync_mode": "table",
            "default_institute_id": "HOSPITAL-A",
        },
    )
    monkeypatch.setattr(
        etl_sync,
        "_resolve_target_tables",
        lambda _tables: (list(target_tables), []),
    )
    monkeypatch.setattr(
        etl_sync,
        "validate_pg_sync_plan",
        lambda **_kwargs: {
            "executable": True,
            "remote_schema": "public",
            "table_validations": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(etl_sync, "load_sync_policy", lambda: {})
    monkeypatch.setattr(
        etl_sync,
        "_create_case_scope_service",
        lambda: _ScopeService(),
        raising=False,
    )
    monkeypatch.setattr(
        etl_sync,
        "_create_case_set_sync_service",
        lambda: _SyncService(),
        raising=False,
    )
    monkeypatch.setattr(
        etl_sync, "_current_hospital_date", lambda: date(2026, 8, 14), raising=False
    )

    def _legacy_path_used(*_args, **_kwargs):
        raise AssertionError("旧二坐标/逐表同步入口不得再被 run_sync 调用")

    for legacy_name in (
        "collect_visit_keys_by_policy",
        "fetch_remote_rows_by_visit_keys",
        "upsert_to_local",
        "_refresh_all_bundle_variants_after_sync",
    ):
        monkeypatch.setattr(etl_sync, legacy_name, _legacy_path_used)

    result = etl_sync.run_sync(
        sync_date="2026-08-10",
        tables=[item["name"] for item in target_tables],
        scene="running",
        date_window={"start": "2026-08-01", "end": "2026-08-10"},
        target_departments=["重症医学科（ICU）"],
        policy_version="global-case-set-v1",
        progress_callback=progress_events.append,
    )

    assert result["success"] is True
    assert result["status"] == "success"
    assert result["case_ref_count"] == 2
    assert result["eligible_visit_count"] == 2
    assert result["total_records"] == 3
    assert len(scope_calls) == 1
    assert scope_calls[0] == {
        "scope_mode": "active",
        "as_of_date": date(2026, 8, 14),
        "admission_start_date": date(2026, 2, 15),
        "discharge_start_date": None,
        "discharge_end_date": None,
        "departments": ["重症医学科（ICU）"],
    }
    assert len(sync_calls) == 1
    assert tuple(sync_calls[0]["case_refs"]) == case_refs
    assert tuple(sync_calls[0]["table_names"]) == tuple(
        item["name"] for item in target_tables
    )
    assert sync_calls[0]["sync_scene"] == "running"
    bundle_progress = next(
        event for event in progress_events if event.get("stage") == "bundle_refresh"
    )
    assert bundle_progress["bundle_progress"] == {
        "total": 2,
        "completed": 1,
        "remaining": 1,
    }
    final_progress = progress_events[-1]
    assert final_progress["status"] == "success"
    assert final_progress["stage"] == "completed"
    assert final_progress["visit_progress"]["total"] == 2
    assert final_progress["visit_progress"]["completed"] == 2


def _install_public_run_sync_fakes(
    monkeypatch,
    *,
    scope_result: HospitalizationScopeResult | Exception,
    sync_action,
):
    calls = {"lock": [], "scope": [], "sync": [], "state": []}
    target_names = (
        "mr",
        "admission_record",
        "discharge_record",
        "daily_course_record",
    )
    target_tables = [
        {"name": name, "source_table": name, "label": name}
        for name in target_names
    ]

    class _FakeConn:
        def execute(self, stmt, params=None):
            sql = str(stmt)
            calls["lock"].append(sql)
            if "pg_try_advisory_lock" in sql or "pg_advisory_unlock" in sql:
                return _ScalarResult(True)
            raise AssertionError(f"unexpected SQL: {sql}")

        def close(self):
            calls["lock"].append("close")

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    class _ScopeService:
        def resolve_hospitalization_scope(self, **kwargs):
            calls["scope"].append(kwargs)
            if isinstance(scope_result, Exception):
                raise scope_result
            return scope_result

    class _SyncService:
        def sync_case_set(self, **kwargs):
            calls["sync"].append(kwargs)
            return sync_action(kwargs)

    def _capture_state(state):
        calls["state"].append(
            {
                "is_running": state.is_running,
                "last_sync_status": state.last_sync_status,
                "total_records_synced": state.total_records_synced,
            }
        )

    def _legacy_path_used(*_args, **_kwargs):
        raise AssertionError("旧二坐标/逐表同步入口不得再被 run_sync 调用")

    monkeypatch.setattr(etl_sync, "engine", _FakeEngine())
    monkeypatch.setattr(etl_sync, "_upsert_sync_job_state", _capture_state)
    monkeypatch.setattr(etl_sync, "get_remote_db_url", lambda: "postgresql://source")
    monkeypatch.setattr(
        etl_sync,
        "load_db_config",
        lambda: {"remote_schema": "public", "sync_mode": "table"},
    )
    monkeypatch.setattr(
        etl_sync,
        "_resolve_target_tables",
        lambda _tables: (list(target_tables), []),
    )
    monkeypatch.setattr(
        etl_sync,
        "validate_pg_sync_plan",
        lambda **_kwargs: {
            "executable": True,
            "remote_schema": "public",
            "table_validations": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(etl_sync, "load_sync_policy", lambda: {})
    monkeypatch.setattr(
        etl_sync,
        "_create_case_scope_service",
        lambda: _ScopeService(),
    )
    monkeypatch.setattr(
        etl_sync,
        "_create_case_set_sync_service",
        lambda: _SyncService(),
    )
    for legacy_name in (
        "collect_visit_keys_by_policy",
        "fetch_remote_rows_by_visit_keys",
        "upsert_to_local",
        "_refresh_all_bundle_variants_after_sync",
    ):
        monkeypatch.setattr(etl_sync, legacy_name, _legacy_path_used)
    return calls, target_names


def _hospitalization_scope_result(
    case_refs: tuple[CaseRef, ...],
    *,
    warnings: tuple[str, ...] = (),
) -> HospitalizationScopeResult:
    selected = tuple(
        {
            **case_ref.as_dict(),
            "hospitalization_status": "discharged",
            "authoritative_time": "2026-08-10 09:00:00",
            "department": "重症医学科（ICU）",
            "department_basis": "discharge_department",
            "source_table": "discharge_record",
        }
        for case_ref in case_refs
    )
    return HospitalizationScopeResult(
        case_refs=case_refs,
        selected=selected,
        all_selected=selected,
        sources_used=("inpat_registration", "discharge_record"),
        source_status="ready",
        warnings=warnings,
    )


def _successful_case_set_result(
    case_refs: tuple[CaseRef, ...],
    *,
    visible_case_refs: tuple[CaseRef, ...] | None = None,
    missing_primary_case_refs: tuple[CaseRef, ...] = (),
    synced_tables: tuple[dict, ...] | None = None,
) -> CaseSetSyncResult:
    visible = case_refs if visible_case_refs is None else visible_case_refs
    tables = synced_tables or (
        {
            "table_name": "mr",
            "rows_pulled": len(visible),
            "rows_upserted": len(visible),
            "sync_status": "synced",
        },
    )
    return CaseSetSyncResult(
        case_refs=case_refs,
        primary_visible=bool(visible),
        visible_case_refs=visible,
        missing_primary_case_refs=missing_primary_case_refs,
        synced_tables=tables,
        source_rows_by_table={},
        total_rows_pulled=sum(int(item.get("rows_pulled") or 0) for item in tables),
        total_rows_upserted=sum(
            int(item.get("rows_upserted") or 0) for item in tables
        ),
        bundle_refresh={"scenes": {}, "domains": {}},
    )


def test_run_sync_both_uses_combined_scope_and_preserves_state_contract(monkeypatch):
    case_refs = (CaseRef("H1", "P1", "V1"),)
    synced_tables = (
        {
            "table_name": "mr",
            "rows_pulled": 1,
            "rows_upserted": 1,
            "sync_status": "synced",
        },
        {
            "table_name": "daily_course_record",
            "rows_pulled": 0,
            "rows_upserted": 0,
            "sync_status": "source_table_unavailable",
            "skip_reason": "该类资料暂未从源系统提供，本次同步已跳过。",
        },
    )
    scope_result = _hospitalization_scope_result(
        case_refs,
        warnings=("出院来源按优先级合并",),
    )
    calls, target_names = _install_public_run_sync_fakes(
        monkeypatch,
        scope_result=scope_result,
        sync_action=lambda _kwargs: _successful_case_set_result(
            case_refs,
            synced_tables=synced_tables,
        ),
    )
    monkeypatch.setattr(
        etl_sync, "_current_hospital_date", lambda: date(2026, 8, 14), raising=False
    )

    result = etl_sync.run_sync(
        sync_date="2026-08-10",
        tables=list(target_names),
        scene="both",
        date_window={"start": "2026-08-01", "end": "2026-08-10"},
        target_departments=["重症医学科（ICU）"],
        include_internal_case_refs=True,
    )

    assert result["success"] is False
    assert result["status"] == "partial"
    assert result["date_window"] == {"start": "2026-08-01", "end": "2026-08-10"}
    assert result["target_departments"] == ["重症医学科（ICU）"]
    assert result["case_ref_count"] == result["eligible_visit_count"] == 1
    assert calls["scope"] == [
        {
            "scope_mode": "active_and_discharged",
            "as_of_date": date(2026, 8, 14),
            "admission_start_date": date(2026, 2, 15),
            "discharge_start_date": date(2026, 8, 1),
            "discharge_end_date": date(2026, 8, 10),
            "departments": ["重症医学科（ICU）"],
        }
    ]
    assert len(calls["sync"]) == 1
    assert any("pg_advisory_unlock" in item for item in calls["lock"])
    assert calls["state"][-1] == {
        "is_running": False,
        "last_sync_status": "partial",
        "total_records_synced": 1,
    }
    assert any("出院来源按优先级合并" in item for item in result["warnings"])
    assert any("daily_course_record" in item for item in result["warnings"])
    assert result["_internal_synced_case_refs"] == [case_refs[0].as_dict()]


def test_run_sync_internal_transition_refs_exclude_patients_still_in_hospital(monkeypatch):
    active_ref = CaseRef("H1", "P1", "V1")
    discharged_ref = CaseRef("H1", "P2", "V2")
    case_refs = (active_ref, discharged_ref)
    selected = (
        {
            **active_ref.as_dict(),
            "hospitalization_status": "active",
            "authoritative_time": "2026-08-14 09:00:00",
            "department": "重症医学科（ICU）",
        },
        {
            **discharged_ref.as_dict(),
            "hospitalization_status": "discharged",
            "authoritative_time": "2026-08-13 09:00:00",
            "department": "重症医学科（ICU）",
        },
    )
    scope_result = HospitalizationScopeResult(
        case_refs=case_refs,
        selected=selected,
        all_selected=selected,
        sources_used=("inpat_registration", "discharge_record"),
        source_status="ready",
        warnings=(),
    )
    _calls, target_names = _install_public_run_sync_fakes(
        monkeypatch,
        scope_result=scope_result,
        sync_action=lambda _kwargs: _successful_case_set_result(case_refs),
    )

    result = etl_sync.run_sync(
        tables=list(target_names),
        scene="both",
        date_window={"start": "2026-08-13", "end": "2026-08-14"},
        include_internal_case_refs=True,
    )

    assert result["_internal_synced_case_refs"] == [discharged_ref.as_dict()]


def test_run_sync_internal_running_refs_include_visible_active_cases(monkeypatch):
    active_ref = CaseRef("H1", "P1", "V1")
    selected = (
        {
            **active_ref.as_dict(),
            "hospitalization_status": "active",
            "authoritative_time": "2026-08-14 09:00:00",
            "department": "重症医学科（ICU）",
        },
    )
    scope_result = HospitalizationScopeResult(
        case_refs=(active_ref,),
        selected=selected,
        all_selected=selected,
        sources_used=("inpat_registration",),
        source_status="ready",
        warnings=(),
    )
    _calls, target_names = _install_public_run_sync_fakes(
        monkeypatch,
        scope_result=scope_result,
        sync_action=lambda _kwargs: _successful_case_set_result((active_ref,)),
    )

    result = etl_sync.run_sync(
        tables=list(target_names),
        scene="running",
        include_internal_case_refs=True,
    )

    assert result["_internal_synced_case_refs"] == [active_ref.as_dict()]


def test_run_sync_explicit_all_hospital_ignores_saved_departments(monkeypatch):
    case_refs = (CaseRef("H1", "P1", "V1"),)
    calls, target_names = _install_public_run_sync_fakes(
        monkeypatch,
        scope_result=_hospitalization_scope_result(case_refs),
        sync_action=lambda _kwargs: _successful_case_set_result(case_refs),
    )
    monkeypatch.setattr(
        etl_sync,
        "load_sync_policy",
        lambda: {"target_departments": ["历史保存科室"]},
    )

    result = etl_sync.run_sync(
        sync_date="2026-08-13",
        tables=list(target_names),
        scene="final",
        date_window={"start": "2026-08-07", "end": "2026-08-13"},
        target_departments=["*"],
    )

    assert result["status"] == "success"
    assert result["target_departments"] == ["*"]
    assert calls["scope"][0]["departments"] == []


def test_run_sync_rejects_placeholder_institute_before_scope_or_sync(monkeypatch):
    case_refs = (CaseRef("LOCAL-HOSPITAL", "P1", "V1"),)
    calls, target_names = _install_public_run_sync_fakes(
        monkeypatch,
        scope_result=_hospitalization_scope_result(case_refs),
        sync_action=lambda _kwargs: _successful_case_set_result(case_refs),
    )
    monkeypatch.setattr(
        etl_sync,
        "load_db_config",
        lambda: {
            "remote_schema": "public",
            "sync_mode": "table",
            "default_institute_id": "LOCAL-HOSPITAL",
        },
    )

    result = etl_sync.run_sync(
        sync_date="2026-08-10",
        tables=list(target_names),
        scene="final",
        date_window={"start": "2026-08-10", "end": "2026-08-10"},
    )

    assert result["success"] is False
    assert result["status"] == "rejected"
    assert result["error"] == "请先配置本院稳定机构标识后再执行同步"
    assert len(calls["scope"]) == 1
    assert calls["sync"] == []


def test_run_sync_missing_primary_fails_closed_by_full_case_ref(monkeypatch):
    visible_ref = CaseRef("H1", "P1", "SAME-VISIT")
    missing_ref = CaseRef("H2", "P2", "SAME-VISIT")
    case_refs = (visible_ref, missing_ref)
    progress_events: list[dict] = []

    def _sync_action(kwargs):
        kwargs["progress_callback"](
            {
                "step_key": "completed",
                "current_table": "",
                "processed_tables": 4,
                "total_tables": 4,
            }
        )
        return _successful_case_set_result(
            case_refs,
            visible_case_refs=(visible_ref,),
            missing_primary_case_refs=(missing_ref,),
        )

    calls, target_names = _install_public_run_sync_fakes(
        monkeypatch,
        scope_result=_hospitalization_scope_result(case_refs),
        sync_action=_sync_action,
    )
    result = etl_sync.run_sync(
        sync_date="2026-08-10",
        tables=list(target_names),
        scene="both",
        date_window={"start": "2026-08-10", "end": "2026-08-10"},
        progress_callback=progress_events.append,
    )

    assert result["success"] is False
    assert result["status"] == "partial"
    assert result["case_ref_count"] == 2
    assert result["visible_case_ref_count"] == 1
    assert result["missing_primary_case_refs"] == [missing_ref.as_dict()]
    assert len(calls["sync"]) == 1
    assert progress_events[-1]["stage"] == "primary_unavailable"
    assert progress_events[-1]["visit_progress"]["total"] == 2
    assert progress_events[-1]["visit_progress"]["completed"] == 1
    assert progress_events[-2]["stage"] == "finalizing"
    assert not any(event.get("stage") == "completed" for event in progress_events)


def test_run_sync_rejects_empty_scope_without_case_set_or_false_completion(monkeypatch):
    progress_events: list[dict] = []
    calls, target_names = _install_public_run_sync_fakes(
        monkeypatch,
        scope_result=_hospitalization_scope_result(()),
        sync_action=lambda _kwargs: (_ for _ in ()).throw(
            AssertionError("空病例范围不得调用 CaseSetSyncService")
        ),
    )
    result = etl_sync.run_sync(
        sync_date="2026-08-10",
        tables=list(target_names),
        scene="final",
        date_window={"start": "2026-08-10", "end": "2026-08-10"},
        progress_callback=progress_events.append,
    )

    assert result["success"] is False
    assert result["status"] == "rejected"
    assert result["case_ref_count"] == 0
    assert result["total_records"] == 0
    assert calls["sync"] == []
    assert progress_events[-1]["status"] == "rejected"
    assert progress_events[-1]["stage"] == "rejected"
    assert progress_events[-1]["visit_progress"]["completed"] == 0
    assert not any(event.get("stage") == "completed" for event in progress_events)


def test_run_sync_case_set_hard_failure_never_reports_completed(monkeypatch, caplog):
    case_refs = (CaseRef("H1", "P1", "V1"),)
    progress_events: list[dict] = []

    def _raise_after_primary(kwargs):
        kwargs["progress_callback"](
            {
                "step_key": "primary_visible",
                "current_table": "",
                "processed_tables": 1,
                "total_tables": 4,
            }
        )
        raise RuntimeError("SECRET-SQL SELECT * FROM patient")

    calls, target_names = _install_public_run_sync_fakes(
        monkeypatch,
        scope_result=_hospitalization_scope_result(case_refs),
        sync_action=_raise_after_primary,
    )
    result = etl_sync.run_sync(
        sync_date="2026-08-10",
        tables=list(target_names),
        scene="final",
        date_window={"start": "2026-08-10", "end": "2026-08-10"},
        progress_callback=progress_events.append,
    )

    assert result["success"] is False
    assert result["status"] == "failed"
    assert result["case_ref_count"] == 1
    assert result["error"] == "病例资料同步失败，请稍后重试；如持续失败请联系管理员"
    assert "SECRET-SQL" not in result["error"]
    assert "SECRET-SQL" not in caplog.text
    assert len(calls["scope"]) == len(calls["sync"]) == 1
    assert calls["sync"][0]["sync_scene"] == "final"
    assert progress_events[-1]["status"] == "failed"
    assert progress_events[-1]["stage"] == "failed"
    assert progress_events[-1]["visit_progress"]["completed"] == 0
    assert not any(event.get("stage") == "completed" for event in progress_events)


def test_run_sync_scope_failure_does_not_expose_source_error(monkeypatch, caplog):
    progress_events: list[dict] = []
    calls, target_names = _install_public_run_sync_fakes(
        monkeypatch,
        scope_result=RuntimeError("SECRET-SQL password=do-not-return"),
        sync_action=lambda _kwargs: (_ for _ in ()).throw(
            AssertionError("范围解析失败后不得调用 CaseSetSyncService")
        ),
    )
    result = etl_sync.run_sync(
        sync_date="2026-08-10",
        tables=list(target_names),
        scene="final",
        date_window={"start": "2026-08-10", "end": "2026-08-10"},
        progress_callback=progress_events.append,
    )

    assert result["success"] is False
    assert result["status"] == "failed"
    assert result["error"] == "病例范围解析失败，请检查同步配置后重试"
    assert "SECRET-SQL" not in result["error"]
    assert "SECRET-SQL" not in caplog.text
    assert calls["sync"] == []
    assert progress_events[-1]["stage"] == "scope_resolution"


def test_upsert_to_local_uses_real_local_primary_keys(monkeypatch):
    executed_sql: list[str] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_sql.append(str(stmt))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: ("cdm", ["institute_id", "patient_id", "visit_id", "name"], ["institute_id", "patient_id", "visit_id"]),
    )

    count = etl_sync.upsert_to_local(
        table_name="mr",
        records=[
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "name": "张三",
            }
        ],
        primary_keys=["patient_id", "visit_id"],
    )

    assert count == 1
    assert len(executed_sql) == 1
    assert "ON CONFLICT (institute_id, patient_id, visit_id)" in executed_sql[0]


def test_upsert_to_local_replaces_exact_case_snapshot_before_insert(monkeypatch):
    executed: list[tuple[str, object]] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed.append((str(stmt), params))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            ["institute_id", "patient_id", "visit_id", "document_id"],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="daily_course_record",
        records=[
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "document_id": "D1",
            }
        ],
        primary_keys=["document_id"],
        replace_case_refs=(CaseRef("H1", "P1", "V1"),),
    )

    assert count == 1
    assert executed[0][0].startswith("DELETE FROM cdm.daily_course_record")
    assert executed[0][1] == {
        "institute_id": "H1",
        "patient_id": "P1",
        "visit_id": "V1",
    }
    assert executed[1][0].startswith("INSERT INTO cdm.daily_course_record")


def test_upsert_to_local_empty_full_reload_removes_withdrawn_rows(monkeypatch):
    executed: list[tuple[str, object]] = []
    commits = 0

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed.append((str(stmt), params))
            return None

        def commit(self):
            nonlocal commits
            commits += 1

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            ["institute_id", "patient_id", "visit_id", "document_id"],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="daily_course_record",
        records=[],
        primary_keys=["document_id"],
        replace_case_refs=(CaseRef("H1", "P1", "V1"),),
    )

    assert count == 0
    assert len(executed) == 1
    assert executed[0][0].startswith("DELETE FROM cdm.daily_course_record")
    assert commits == 1


def test_upsert_to_local_replacement_requires_full_case_identity_columns(monkeypatch):
    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            ["patient_id", "visit_id", "document_id"],
            ["patient_id", "visit_id", "document_id"],
        ),
    )

    with pytest.raises(ValueError, match="三坐标字段"):
        etl_sync.upsert_to_local(
            table_name="daily_course_record",
            records=[],
            primary_keys=["document_id"],
            replace_case_refs=(CaseRef("H1", "P1", "V1"),),
        )


def test_upsert_to_local_does_not_commit_deleted_snapshot_when_insert_fails(
    monkeypatch,
):
    execute_calls = 0
    commits = 0

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, _stmt, _params=None):
            nonlocal execute_calls
            execute_calls += 1
            if execute_calls == 2:
                raise RuntimeError("insert failed")
            return None

        def commit(self):
            nonlocal commits
            commits += 1

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            ["institute_id", "patient_id", "visit_id", "document_id"],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    with pytest.raises(RuntimeError, match="insert failed"):
        etl_sync.upsert_to_local(
            table_name="daily_course_record",
            records=[
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "document_id": "D1",
                }
            ],
            primary_keys=["document_id"],
            replace_case_refs=(CaseRef("H1", "P1", "V1"),),
        )

    assert execute_calls == 2
    assert commits == 0


def test_upsert_to_local_batches_rows_with_the_same_column_shape(monkeypatch):
    executed_params = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, _stmt, params=None):
            executed_params.append(params)
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            ["institute_id", "patient_id", "visit_id", "name"],
            ["institute_id", "patient_id", "visit_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="mr",
        records=[
            {"institute_id": "A", "patient_id": "P1", "visit_id": "V1", "name": "甲"},
            {"institute_id": "A", "patient_id": "P2", "visit_id": "V2", "name": "乙"},
            {"institute_id": "A", "patient_id": "P3", "visit_id": "V3", "name": "丙"},
        ],
        primary_keys=["patient_id", "visit_id"],
        batch_size=500,
    )

    assert count == 3
    assert len(executed_params) == 1
    assert isinstance(executed_params[0], list)
    assert [row["visit_id"] for row in executed_params[0]] == ["V1", "V2", "V3"]


def test_upsert_to_local_derives_labtest_document_id_from_source_keys(monkeypatch):
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "document_id",
                "test_no",
                "item_no",
                "item_name",
                "result",
                "unit",
                "record_content",
            ],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="labtest_item_report",
        records=[
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "test_no": "T100",
                "item_no": "I2",
                "item_name": "白细胞计数",
                "result": "12.5",
                "unit": "10^9/L",
            }
        ],
        primary_keys=["patient_id", "visit_id", "test_no", "item_no"],
    )

    assert count == 1
    assert executed_params[0]["document_id"] == "lab:T100:I2"
    assert executed_params[0]["record_content"] == "白细胞计数：12.5 10^9/L"


def test_upsert_to_local_derives_exam_document_id_from_source_keys(monkeypatch):
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "document_id",
                "exam_no",
                "item_no",
                "exam_name",
                "exam_conclusion",
                "record_content",
            ],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="exam_item_report",
        records=[
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "exam_no": "E100",
                "item_no": "1",
                "exam_name": "胸部CT",
                "exam_conclusion": "双肺炎症",
            }
        ],
        primary_keys=["patient_id", "visit_id", "exam_no", "item_no"],
    )

    assert count == 1
    assert executed_params[0]["document_id"] == "exam:E100:1"
    assert executed_params[0]["record_content"] == "双肺炎症"


def test_upsert_to_local_preserves_complete_surgery_record_fields(monkeypatch):
    """手术结构化内容必须与源端一起落库，不能只保留摘要正文。"""
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    local_columns = [column.name for column in SurgeryRecord.__table__.columns]
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "public",
            local_columns,
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="surgery_record",
        records=[
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "document_id": "S1",
                "surgery_name": "腹腔镜下经腹膜前腹股沟疝补片修补术(TAPP)",
                "surgery_begin_time": "2026-08-18T09:05:00+08:00",
                "surgery_end_time": "2026-08-18T11:25:00+08:00",
                "preoperative_diagnosis": "腹股沟疝",
                "postoperative_diagnosis": "左侧腹股沟斜疝",
                "surgery_process": "1. 插管全麻。\n2. 完成补片修补。",
                "blood_loss": "10ml",
                "record_content": "无特殊。",
            }
        ],
        primary_keys=["patient_id", "visit_id", "document_id"],
    )

    assert count == 1
    saved = executed_params[0]
    assert saved["surgery_begin_time"] == "2026-08-18T09:05:00+08:00"
    assert saved["surgery_end_time"] == "2026-08-18T11:25:00+08:00"
    assert saved["preoperative_diagnosis"] == "腹股沟疝"
    assert saved["postoperative_diagnosis"] == "左侧腹股沟斜疝"
    assert saved["surgery_process"] == "1. 插管全麻。\n2. 完成补片修补。"
    assert saved["blood_loss"] == "10ml"


@pytest.mark.parametrize(
    ("table_name", "model", "source_row", "expected"),
    [
        (
            "admission_record",
            AdmissionRecord,
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "sys_index_id": 101,
                "record_time": "2026-08-16T22:20:29+08:00",
                "admission_time": "2026-08-16T20:00:00+08:00",
            },
            {
                "document_id": 101,
                "record_datetime": "2026-08-16T22:20:29+08:00",
                "admission_datetime": "2026-08-16T20:00:00+08:00",
            },
        ),
        (
            "first_course_record",
            FirstCourseRecord,
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "sys_index_id": 102,
                "record_time": "2026-08-16T22:38:08+08:00",
                "case_characteristic": "患者为31岁男性。",
            },
            {
                "document_id": 102,
                "record_datetime": "2026-08-16T22:38:08+08:00",
            },
        ),
        (
            "consultation_record",
            ConsultationRecord,
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "sys_index_id": 103,
                "record_time": "2026-08-16T23:00:00+08:00",
            },
            {
                "document_id": 103,
                "submit_datetime": "2026-08-16T23:00:00+08:00",
            },
        ),
    ],
)
def test_upsert_to_local_maps_customer_document_identity_and_record_time(
    monkeypatch, table_name, model, source_row, expected
):
    """001/002 读取的文书身份和时间必须保留在同一条本地记录。"""
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "public",
            [column.name for column in model.__table__.columns],
            ["institute_id", "patient_id", "visit_id"],
        ),
    )

    assert etl_sync.upsert_to_local(
        table_name=table_name,
        records=[source_row],
        primary_keys=["patient_id", "visit_id"],
    ) == 1
    assert {key: executed_params[0][key] for key in expected} == expected


def test_document_field_preservation_rejects_time_or_identity_loss():
    """源端已有定位信息时，不得过滤后悄然留下不可核对文书。"""

    with pytest.raises(ValueError, match="文书标识未保留"):
        etl_sync._validate_document_field_preservation(
            table_name="consultation_record",
            normalized={"sys_index_id": "doc-103"},
            existing_columns={"document_id"},
        )
    with pytest.raises(ValueError, match="文书权威时间未保留"):
        etl_sync._validate_document_field_preservation(
            table_name="consultation_record",
            normalized={"record_time": "2026-08-16 23:00:00"},
            existing_columns={"submit_datetime"},
        )


def test_upsert_to_local_derives_presurg_summary_content_without_overwriting_source_content(monkeypatch):
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            ["institute_id", "patient_id", "visit_id", "document_id", "record_content"],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="presurg_summary",
        records=[
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "document_id": "D1",
                "preoperative_diagnosis": "急性硬膜下血肿",
                "planned_surgery_name": "开颅血肿清除术",
                "planned_surgery_time": "今日急诊",
                "planned_anesthesia_method": "气管插管全麻",
                "surgery_preparation": "备血并完善术前检查",
            },
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "document_id": "D2",
                "record_content": "源端已提供完整正文",
                "planned_surgery_name": "不应覆盖",
            },
        ],
        primary_keys=["patient_id", "visit_id", "document_id"],
    )

    assert count == 2
    assert executed_params[0]["record_content"] == (
        "术前诊断：急性硬膜下血肿\n"
        "拟实施手术：开颅血肿清除术\n"
        "手术时间：今日急诊\n"
        "麻醉方式：气管插管全麻\n"
        "术前准备：备血并完善术前检查"
    )
    assert executed_params[1]["record_content"] == "源端已提供完整正文"


def test_upsert_to_local_derives_surgery_safecheck_content(monkeypatch):
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            ["institute_id", "patient_id", "visit_id", "document_id", "record_content"],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="surgery_safecheck_record",
        records=[
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "document_id": "D1",
                "surgery_begin_time": "2026-07-07 16:14:26",
                "surgery_method": "开颅血肿清除术",
                "surgeon": "张医生",
                "anesthesia_method": "全麻",
                "before_incision_surgeon_sign": "张医生",
                "surgeon_statement": "确认手术部位与患者身份",
            }
        ],
        primary_keys=["patient_id", "visit_id", "document_id"],
    )

    assert count == 1
    assert executed_params[0]["record_content"] == (
        "手术时间：2026-07-07 16:14:26\n"
        "手术方式：开颅血肿清除术\n"
        "手术医师：张医生\n"
        "麻醉方式：全麻\n"
        "切皮前手术医师签名：张医生\n"
        "手术医师陈述：确认手术部位与患者身份"
    )


def test_upsert_to_local_derives_anesthesia_record_content(monkeypatch):
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            ["institute_id", "patient_id", "visit_id", "document_id", "record_content"],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="anesthesia_record",
        records=[
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "document_id": "D1",
                "planned_surgery": "颅内血肿清除术",
                "surgery_name": "开颅血肿清除术",
                "surgery_code": "01.2300",
                "surgery_bodypost": "仰卧位",
                "anesthesia_method": "气管插管全麻",
                "ASA_level": "III",
                "surgery_begin_datetime": "2026-07-07 16:14:26",
                "surgery_end_datetime": "2026-07-07 18:14:26",
                "anesthesia_begin_datetime": "2026-07-07 16:00:00",
                "anesthesia_end_datetime": "2026-07-07 18:20:00",
                "leave_operateroom_datetime": "2026-07-07 18:30:00",
                "bleed_volume": "200ml",
                "urine_volume": "300ml",
                "patient_whereabout": "ICU",
                "conscious_status": "昏睡",
                "preanes_sbp": "120",
                "preanes_dbp": "80",
                "preanes_temperature": "36.5",
                "preanes_hr": "88",
                "preanes_rr": "18",
                "preanes_spo": "99",
                "anesthesia_management_measures": "维持循环稳定",
                "respiratory_management": "气管插管机械通气",
                "anesthesia_summary": "麻醉过程平稳",
                "anesthetist_sign": "麻醉医师甲",
                "preanes_medication_generic_name": "丙泊酚注射液",
                "single_dose": "20",
                "single_dose_unit": "mg",
                "dosage": "200",
                "dosage_unit": "mg",
                "drug_apply_method": "静脉注射",
                "name": "不得输出患者姓名",
                "dept_name": "不得输出科室",
            }
        ],
        primary_keys=["patient_id", "visit_id", "document_id"],
    )

    assert count == 1
    content = executed_params[0]["record_content"]
    assert "拟实施手术：颅内血肿清除术" in content
    assert "手术名称：开颅血肿清除术" in content
    assert "手术编码：01.2300" in content
    assert "手术开始时间：2026-07-07 16:14:26" in content
    assert "离室时间：2026-07-07 18:30:00" in content
    assert "麻醉前收缩压：120" in content
    assert "麻醉前血氧饱和度：99" in content
    assert "麻醉中处理措施：维持循环稳定" in content
    assert "呼吸管理：气管插管机械通气" in content
    assert "麻醉总结：麻醉过程平稳" in content
    assert "麻醉医师签名：麻醉医师甲" in content
    assert "药物名称：丙泊酚注射液" in content
    assert "给药途径：静脉注射" in content
    assert "不得输出患者姓名" not in content
    assert "不得输出科室" not in content


def test_upsert_to_local_keeps_first_course_structured_fields(monkeypatch):
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "document_id",
                "case_characteristic",
                "diagnose_based_on",
                "differential_diagnosis",
                "treatment_plan",
                "record_content",
                "record_datetime",
                "submit_datetime",
                "physician_sign_datetime",
                "last_modified_datetime",
            ],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="first_course_record",
        records=[
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "document_id": "F1",
                "case_characteristic": "病例特点原文",
                "diagnose_based_on": "诊断依据原文",
                "differential_diagnosis": "鉴别诊断原文",
                "treatment_plan": "诊疗计划原文",
                "record_time": "2026-06-02 10:00:00+08",
                "submit_time": "2026-06-02 10:06:00+08",
                "physician_sign_time": "2026-06-02 10:05:00+08",
                "last_modified_time": "2026-06-02 10:07:00+08",
                "source_only_column": "不应落库",
            }
        ],
        primary_keys=["patient_id", "visit_id", "document_id"],
    )

    assert count == 1
    assert executed_params[0]["case_characteristic"] == "病例特点原文"
    assert executed_params[0]["diagnose_based_on"] == "诊断依据原文"
    assert executed_params[0]["differential_diagnosis"] == "鉴别诊断原文"
    assert executed_params[0]["treatment_plan"] == "诊疗计划原文"
    assert executed_params[0]["record_datetime"] == "2026-06-02 10:00:00+08"
    assert executed_params[0]["submit_datetime"] == "2026-06-02 10:06:00+08"
    assert executed_params[0]["physician_sign_datetime"] == "2026-06-02 10:05:00+08"
    assert executed_params[0]["last_modified_datetime"] == "2026-06-02 10:07:00+08"
    assert "source_only_column" not in executed_params[0]


def test_upsert_to_local_maps_first_course_submit_time_to_record_datetime_when_record_time_empty(monkeypatch):
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "document_id",
                "record_datetime",
                "submit_datetime",
                "update_time",
            ],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="first_course_record",
        records=[
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "document_id": "F1",
                "record_time": "",
                "submit_time": "2026-05-29 03:45:59+00",
                "update_time": "2026-06-10 00:26:37+00",
            }
        ],
        primary_keys=["patient_id", "visit_id", "document_id"],
    )

    assert count == 1
    assert executed_params[0]["record_datetime"] == "2026-05-29 03:45:59+00"
    assert executed_params[0]["submit_datetime"] == "2026-05-29 03:45:59+00"


def test_upsert_to_local_maps_generic_time_aliases(monkeypatch):
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "admission_datetime",
                "discharge_datetime",
                "mr_datetime",
                "last_modified_datetime",
            ],
            ["institute_id", "patient_id", "visit_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="mr",
        records=[
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "admission_time": "2026-06-01 08:00:00+08",
                "discharge_time": "2026-06-05 10:00:00+08",
                "mr_time": "2026-06-06 09:00:00+08",
                "last_modified_time": "2026-06-06 09:30:00+08",
            }
        ],
        primary_keys=["patient_id", "visit_id"],
    )

    assert count == 1
    assert executed_params[0]["admission_datetime"] == "2026-06-01 08:00:00+08"
    assert executed_params[0]["discharge_datetime"] == "2026-06-05 10:00:00+08"
    assert executed_params[0]["mr_datetime"] == "2026-06-06 09:00:00+08"
    assert executed_params[0]["last_modified_datetime"] == "2026-06-06 09:30:00+08"


def test_upsert_to_local_derives_senior_round_title_from_structured_type(monkeypatch):
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "document_id",
                "document_title",
                "record_content",
            ],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="senior_course_record",
        records=[
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "document_id": "S1",
                "document_title": "",
                "ward_round_type": "上级医师查房",
                "record_content": "今日随彭中主任医师联合普外科医师查房。",
            },
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "document_id": "S2",
                "document_title": "彭中主任医师首次查房记录",
                "ward_round_type": "上级医师查房",
                "record_content": "彭中主任医师首次查房。",
            },
        ],
        primary_keys=["patient_id", "visit_id", "document_id"],
    )

    assert count == 2
    assert executed_params[0]["document_title"] == "上级医师查房记录"
    assert executed_params[0]["record_content"].startswith("今日随彭中主任医师")
    assert executed_params[1]["document_title"] == "彭中主任医师首次查房记录"


def test_upsert_to_local_maps_inpatient_order_aliases(monkeypatch):
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "order_id",
                "prescribed_datetime",
                "planned_start_datetime",
                "order_status",
                "generic_name",
                "drug_specification",
                "drug_frequency",
                "drug_apply_method",
                "single_dose",
                "single_dose_unit",
            ],
            ["institute_id", "patient_id", "visit_id", "order_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="inpat_drug_order",
        records=[
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "order_id": "O1",
                "prescribed_time": "2026-06-02 10:00:00+08",
                "planned_start_time": "2026-06-02 12:00:00+08",
                "start_time": "2026-06-02 13:00:00+08",
                "status": "新开",
                "drug_name": "头孢曲松钠",
                "specification": "1g",
                "frequency": "bid",
                "route": "静滴",
                "dose": "1",
                "dose_unit": "g",
            }
        ],
        primary_keys=["patient_id", "visit_id", "order_id"],
    )

    assert count == 1
    assert executed_params[0]["prescribed_datetime"] == "2026-06-02 10:00:00+08"
    assert executed_params[0]["planned_start_datetime"] == "2026-06-02 12:00:00+08"
    assert executed_params[0]["order_status"] == "新开"
    assert executed_params[0]["generic_name"] == "头孢曲松钠"
    assert executed_params[0]["drug_specification"] == "1g"
    assert executed_params[0]["drug_frequency"] == "bid"
    assert executed_params[0]["drug_apply_method"] == "静滴"
    assert executed_params[0]["single_dose"] == "1"
    assert executed_params[0]["single_dose_unit"] == "g"


def test_upsert_to_local_does_not_treat_generic_start_time_as_prescribed_time(monkeypatch):
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "order_id",
                "prescribed_datetime",
                "planned_start_datetime",
            ],
            ["institute_id", "patient_id", "visit_id", "order_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="inpat_drug_order",
        records=[{
            "institute_id": "A",
            "patient_id": "P1",
            "visit_id": "V1",
            "order_id": "O1",
            "start_time": "2026-06-02 13:00:00+08",
        }],
        primary_keys=["patient_id", "visit_id", "order_id"],
    )

    assert count == 1
    assert "prescribed_datetime" not in executed_params[0]
    assert "planned_start_datetime" not in executed_params[0]


def test_inpatient_drug_order_preserves_planned_start_separately_from_prescribed_time():
    columns = InpatDrugOrder.__table__.columns

    assert "prescribed_datetime" in columns
    assert "planned_start_datetime" in columns
    assert columns["planned_start_datetime"].comment == "计划开始/启用时间（非实际给药时间）"


def test_upsert_to_local_preserves_nondrug_order_lifecycle_times(monkeypatch):
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "order_id",
                "prescribed_datetime",
                "planned_start_datetime",
                "planned_end_datetime",
                "order_status",
                "order_name",
            ],
            ["institute_id", "patient_id", "visit_id", "order_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="inpat_nondrug_order",
        records=[{
            "institute_id": "A",
            "patient_id": "P1",
            "visit_id": "V1",
            "order_id": "O1",
            "prescribed_time": "2026-08-11 12:30:51+08",
            "planned_start_time": "2026-08-11 12:29:14+08",
            "planned_end_time": "2026-08-13 09:10:00+08",
            "order_status": "停止",
            "order_name": "病危",
        }],
        primary_keys=["patient_id", "visit_id", "order_id"],
    )

    assert count == 1
    assert executed_params[0]["prescribed_datetime"] == "2026-08-11 12:30:51+08"
    assert executed_params[0]["planned_start_datetime"] == "2026-08-11 12:29:14+08"
    assert executed_params[0]["planned_end_datetime"] == "2026-08-13 09:10:00+08"


def test_inpatient_nondrug_order_preserves_lifecycle_times():
    columns = InpatNondrugOrder.__table__.columns

    assert "prescribed_datetime" in columns
    assert "planned_start_datetime" in columns
    assert "planned_end_datetime" in columns


def test_upsert_to_local_keeps_transfer_record_structured_fields(monkeypatch):
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "document_id",
                "transfer_purpose",
                "treatment_course",
                "transfer_treatment_plan",
                "current_situation",
                "record_content",
            ],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="transfer_in_record",
        records=[
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "document_id": "T1",
                "transfer_purpose": "转科目的原文",
                "treatment_course": "诊疗经过原文",
                "transfer_treatment_plan": "转入诊疗计划原文",
                "current_situation": "目前情况原文",
            }
        ],
        primary_keys=["patient_id", "visit_id", "document_id"],
    )

    assert count == 1
    assert executed_params[0]["transfer_purpose"] == "转科目的原文"
    assert executed_params[0]["treatment_course"] == "诊疗经过原文"
    assert executed_params[0]["transfer_treatment_plan"] == "转入诊疗计划原文"
    assert executed_params[0]["current_situation"] == "目前情况原文"


def test_upsert_to_local_raises_when_records_cannot_match_local_primary_keys(monkeypatch):
    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            raise AssertionError("missing primary key rows must not be inserted")

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            ["institute_id", "patient_id", "visit_id", "document_id", "record_content"],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    with pytest.raises(ValueError, match="缺少本地主键字段"):
        etl_sync.upsert_to_local(
            table_name="daily_course_record",
            records=[
                {
                    "institute_id": "A",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "record_content": "有正文但缺 document_id",
                }
            ],
            primary_keys=["patient_id", "visit_id", "document_id"],
        )


def test_sync_table_candidate_fields_do_not_enable_incremental_strategy():
    tables = etl_sync.list_sync_tables()

    assert tables
    assert all(
        table["incremental_strategy"] == "full_visit_reload"
        for table in tables
    )
    assert all("watermark_columns" in table for table in tables)
    assert all("schema_version" in table for table in tables)


def test_all_managed_sync_tables_are_enabled_by_default():
    tables = etl_sync.list_sync_tables()

    assert len(tables) > 8
    assert all(table["enabled"] is True for table in tables)


def test_luxian_0609_formal_sync_group_covers_verified_quality_sources():
    """一键质控必须显式选择正式资料集，不能受旧 enabled 覆盖配置影响。"""

    groups = {
        str(group["id"]): tuple(group["table_names"])
        for group in etl_sync.list_sync_table_groups()
    }

    formal_tables = groups["luxian_0609_formal"]
    assert "inpat_registration" in formal_tables
    assert "consultation_record" in formal_tables
    assert "exam_master" in formal_tables
    assert "exam_item_report" in formal_tables
    assert "labtest_master" in formal_tables
    assert "labtest_item_report" in formal_tables
    assert "blood_application" in formal_tables
    assert "consent_form" in formal_tables


def test_sync_catalog_uses_customer_verified_exam_and_lab_identity_fields():
    entries = {
        str(item["name"]): list(item["key_fields"])
        for item in etl_sync.list_sync_tables()
    }

    assert entries["exam_master"] == ["patient_id", "visit_id", "exam_id"]
    assert entries["exam_item_report"] == ["patient_id", "visit_id", "exam_id", "item_id"]
    assert entries["labtest_master"] == ["patient_id", "visit_id", "test_id"]
    assert entries["labtest_item_report"] == [
        "patient_id",
        "visit_id",
        "test_id",
        "print_order_id",
    ]


def test_upsert_to_local_external_session_does_not_commit(monkeypatch):
    class _ExternalSession:
        def __init__(self):
            self.commit_calls = 0
            self.execute_calls = 0

        def execute(self, _stmt, _params=None):
            self.execute_calls += 1

        def commit(self):
            self.commit_calls += 1

    external = _ExternalSession()
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table: (
            "cdm",
            ["institute_id", "patient_id", "visit_id"],
            ["institute_id", "patient_id", "visit_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        "mr",
        [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}],
        ["patient_id", "visit_id"],
        session=external,
    )

    assert count == 1
    assert external.execute_calls == 1
    assert external.commit_calls == 0


def test_fetch_remote_rows_by_visit_keys_applies_explicit_watermark(monkeypatch):
    executed = []

    class _Cursor:
        def execute(self, sql, params=None):
            executed.append((str(sql), list(params or [])))

        def fetchall(self):
            return []

        def close(self):
            return None

    class _Connection:
        def cursor(self, cursor_factory=None):
            return _Cursor()

        def close(self):
            return None

    monkeypatch.setattr(
        etl_sync.psycopg2,
        "connect",
        lambda *_args, **_kwargs: _Connection(),
    )
    monkeypatch.setattr(etl_sync, "_remote_column_exists", lambda *_args: True)
    watermark = __import__("datetime").datetime(2026, 7, 31, 8, 0)

    etl_sync.fetch_remote_rows_by_visit_keys(
        remote_url="postgresql://source",
        remote_schema="public",
        source_table="daily_course_record",
        visit_keys=[("P1", "V1")],
        watermark_column="update_time",
        watermark_after=watermark,
    )

    assert "update_time >= %s" in executed[0][0]
    assert executed[0][1][-1] == watermark


def test_fetch_remote_rows_by_visit_keys_full_reload_has_no_time_condition(monkeypatch):
    executed = []

    class _Cursor:
        def execute(self, sql, params=None):
            executed.append(str(sql))

        def fetchall(self):
            return []

        def close(self):
            return None

    class _Connection:
        def cursor(self, cursor_factory=None):
            return _Cursor()

        def close(self):
            return None

    monkeypatch.setattr(
        etl_sync.psycopg2,
        "connect",
        lambda *_args, **_kwargs: _Connection(),
    )
    monkeypatch.setattr(etl_sync, "_remote_column_exists", lambda *_args: True)

    etl_sync.fetch_remote_rows_by_visit_keys(
        remote_url="postgresql://source",
        remote_schema="public",
        source_table="daily_course_record",
        visit_keys=[("P1", "V1")],
    )

    assert " >= %s" not in executed[0]


def test_fetch_remote_rows_by_case_refs_without_institute_column_uses_fixed_identity(
    monkeypatch,
):
    executed: list[tuple[str, list[str]]] = []

    class _Cursor:
        def execute(self, sql, params=None):
            executed.append((str(sql), list(params or [])))

        def fetchall(self):
            return [{"patient_id": "P1", "visit_id": "V1", "record_content": "正文"}]

        def close(self):
            return None

    class _Connection:
        def cursor(self, cursor_factory=None):
            return _Cursor()

        def close(self):
            return None

    monkeypatch.setattr(etl_sync.psycopg2, "connect", lambda *_args, **_kwargs: _Connection())
    monkeypatch.setattr(
        etl_sync,
        "_remote_column_exists",
        lambda _cursor, _schema, _table, column: column != "institute_id",
    )

    rows = etl_sync.fetch_remote_rows_by_case_refs(
        remote_url="postgresql://source",
        remote_schema="public",
        source_table="daily_course_record",
        case_refs=[CaseRef("LOCAL-HOSPITAL", "P1", "V1")],
        default_institute_id="LOCAL-HOSPITAL",
    )

    assert "(patient_id::text, visit_id::text)" in executed[0][0]
    assert "institute_id::text" not in executed[0][0]
    assert executed[0][1] == ["P1", "V1"]
    assert rows == [
        {
            "institute_id": "LOCAL-HOSPITAL",
            "patient_id": "P1",
            "visit_id": "V1",
            "record_content": "正文",
        }
    ]


def test_fetch_remote_rows_by_case_refs_without_institute_column_rejects_other_scope(
    monkeypatch,
):
    class _Cursor:
        def close(self):
            return None

    class _Connection:
        def cursor(self, cursor_factory=None):
            return _Cursor()

        def close(self):
            return None

    monkeypatch.setattr(etl_sync.psycopg2, "connect", lambda *_args, **_kwargs: _Connection())
    monkeypatch.setattr(
        etl_sync,
        "_remote_column_exists",
        lambda _cursor, _schema, _table, column: column != "institute_id",
    )

    with pytest.raises(ValueError, match="固定机构标识不一致"):
        etl_sync.fetch_remote_rows_by_case_refs(
            remote_url="postgresql://source",
            remote_schema="public",
            source_table="daily_course_record",
            case_refs=[CaseRef("OTHER-HOSPITAL", "P1", "V1")],
            default_institute_id="LOCAL-HOSPITAL",
        )


def test_sync_run_history_persists_and_caps_records(monkeypatch):
    db_engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    monkeypatch.setattr(sync_run_history, "engine", db_engine)

    for idx in range(3):
        sync_run_history.append_sync_run_record(
            {
                "id": f"run-{idx}",
                "source": "pg",
                "tier": "all",
                "tables": ["mr"],
                "status": "success",
                "started_at": f"2026-03-25T10:0{idx}:00+00:00",
                "finished_at": f"2026-03-25T10:0{idx}:10+00:00",
                "duration_ms": 1000,
                "total_records": 10 + idx,
                "error": "",
                "operator": {"email": "admin@medqc.com"},
            },
            max_items=2,
        )

    listed = sync_run_history.list_sync_run_records(source="pg", tier="all", limit=10)
    assert listed["total"] == 2
    assert listed["limit"] == 10
    assert len(listed["items"]) == 2
    returned_ids = {item["id"] for item in listed["items"]}
    assert returned_ids.issubset({"run-0", "run-1", "run-2"})


def test_sync_health_stats_aggregates_failure_rate_and_lag(monkeypatch):
    db_engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    monkeypatch.setattr(sync_run_history, "engine", db_engine)

    sync_run_history.append_sync_run_record(
        {
            "id": "run-success",
            "source": "pg",
            "tier": "all",
            "tables": ["mr"],
            "status": "success",
            "started_at": "2026-03-25T10:00:00+00:00",
            "finished_at": "2026-03-25T10:00:20+00:00",
            "duration_ms": 20000,
            "total_records": 100,
            "error": "",
            "operator": {"email": "admin@medqc.com"},
        },
        max_items=10,
    )
    sync_run_history.append_sync_run_record(
        {
            "id": "run-failed",
            "source": "pg",
            "tier": "all",
            "tables": ["mr"],
            "status": "failed",
            "started_at": "2026-03-25T10:05:00+00:00",
            "finished_at": "2026-03-25T10:05:10+00:00",
            "duration_ms": 10000,
            "total_records": 0,
            "error": "boom",
            "operator": {"email": "admin@medqc.com"},
        },
        max_items=10,
    )

    stats = sync_run_history.get_sync_health_stats(window_minutes=60 * 24 * 365 * 2, sample_limit=50)
    assert stats["window_total_runs"] == 2
    assert stats["window_failed_runs"] == 1
    assert stats["window_failure_rate"] == 0.5
    assert stats["last_run_at"] is not None
    assert stats["last_success_at"] is not None
    assert stats["last_run_lag_seconds"] >= 0
    assert stats["last_success_lag_seconds"] >= 0


def test_run_mongo_sync_rejects_when_advisory_lock_not_acquired(monkeypatch):
    class _Cfg:
        enabled = True
        mongo_uri = "mongodb://127.0.0.1:27017/admin"
        mongo_database = "admin"
        read_preference = "secondaryPreferred"
        max_concurrent = 2
        query_timeout_s = 5
        connect_timeout_ms = 1000

    class _FakeConn:
        def execute(self, stmt, params=None):
            sql = str(stmt)
            if "pg_try_advisory_lock" in sql:
                return _ScalarResult(False)
            raise AssertionError(f"unexpected SQL: {sql}")

        def close(self):
            return None

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    monkeypatch.setattr("app.services.etl_config.load_mongo_config", lambda: _Cfg())
    monkeypatch.setattr(mongo_sync, "engine", _FakeEngine())
    monkeypatch.setattr(mongo_sync, "_upsert_mongo_sync_state", lambda _state: None)
    result = mongo_sync.run_mongo_sync("tier1")
    assert result["success"] is False
    assert "同步正在进行中" in result["error"]


def test_run_mongo_sync_unlocks_on_early_failure(monkeypatch):
    calls: list[str] = []

    class _Cfg:
        enabled = True
        mongo_uri = "mongodb://127.0.0.1:27017/admin"
        mongo_database = "admin"
        read_preference = "secondaryPreferred"
        max_concurrent = 2
        query_timeout_s = 5
        connect_timeout_ms = 1000

    class _FakeConn:
        def execute(self, stmt, params=None):
            sql = str(stmt)
            calls.append(sql)
            if "pg_try_advisory_lock" in sql:
                return _ScalarResult(True)
            if "pg_advisory_unlock" in sql:
                return _ScalarResult(True)
            raise AssertionError(f"unexpected SQL: {sql}")

        def close(self):
            calls.append("close")
            return None

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    class _FakeConnector:
        def __init__(self, *args, **kwargs):
            pass

        def test_connection(self):
            return {"connected": False, "error": "mongo down"}

        def close(self):
            calls.append("connector.close")
            return None

    monkeypatch.setattr("app.services.etl_config.load_mongo_config", lambda: _Cfg())
    monkeypatch.setattr(mongo_sync, "engine", _FakeEngine())
    monkeypatch.setattr(mongo_sync, "MongoConnector", _FakeConnector)
    monkeypatch.setattr(mongo_sync, "_upsert_mongo_sync_state", lambda _state: None)

    result = mongo_sync.run_mongo_sync("tier1")
    assert result["success"] is False
    assert result["error"] == "mongo down"
    assert any("pg_try_advisory_lock" in item for item in calls)
    assert any("pg_advisory_unlock" in item for item in calls)
    assert "connector.close" in calls


def test_mongo_sync_state_persisted_in_database(monkeypatch):
    db_engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    monkeypatch.setattr(mongo_sync, "engine", db_engine)

    state = mongo_sync.MongoSyncState(
        is_running=True,
        last_sync_time="2026-03-26T10:00:00Z",
        last_sync_status="success",
        connected=True,
        connection_error="",
        tier1_last_run="2026-03-26T10:00:00Z",
        tier1_discovered=11,
        tier2_last_run="2026-03-26T10:05:00Z",
        tier2_synced=7,
        tier3_last_run="2026-03-26T10:10:00Z",
        tier3_synced=5,
        logs=[{"event": "ok"}],
    )
    mongo_sync._upsert_mongo_sync_state(state)
    loaded = mongo_sync.get_mongo_sync_state()
    assert loaded["is_running"] is True
    assert loaded["last_sync_status"] == "success"
    assert loaded["tier1_discovered"] == 11
    assert loaded["tier2_synced"] == 7
    assert loaded["tier3_synced"] == 5


def test_pg_sync_state_persists_and_reads_progress_json(monkeypatch):
    persisted: dict[str, object] = {}
    stored_row = {
        "is_running": True,
        "last_sync_time": None,
        "last_sync_status": "running",
        "total_records_synced": 0,
        "logs_json": [],
        "progress_json": {
            "run_id": "sync-progress-1",
            "stage": "syncing_table",
            "tables_done": 3,
            "tables_total": 8,
        },
        "remote_connected": True,
        "local_connected": True,
    }

    class _Result:
        def __init__(self, *, first=None, mapping=None):
            self._first = first
            self._mapping = mapping

        def first(self):
            return self._first

        def mappings(self):
            return self

    class _Session:
        def __init__(self, _engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, statement, params=None):
            sql = str(statement)
            if "information_schema.tables" in sql:
                return _Result(first=(1,))
            if "INSERT INTO qc.sync_job_state" in sql:
                persisted.update(params or {})
                return _Result()
            if "FROM qc.sync_job_state" in sql:
                return _Result(first=stored_row, mapping=stored_row)
            raise AssertionError(f"unexpected SQL: {sql}")

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "engine", object())
    monkeypatch.setattr(etl_sync, "Session", _Session)
    state = etl_sync.SyncState(
        is_running=True,
        last_sync_status="running",
        progress={
            "run_id": "sync-progress-1",
            "stage": "syncing_table",
            "tables_done": 3,
            "tables_total": 8,
        },
        remote_connected=True,
        local_connected=True,
    )

    etl_sync._upsert_sync_job_state(state)
    loaded = etl_sync.get_sync_state()

    assert json.loads(str(persisted["progress_json"]))["tables_done"] == 3
    assert loaded["is_running"] is True
    assert loaded["progress"]["run_id"] == "sync-progress-1"
    assert loaded["progress"]["tables_total"] == 8


def test_upsert_to_local_preserves_structured_transfusion_consent_facts(monkeypatch):
    """042 不能因结构化同意书字段在同步时被过滤而误判。"""

    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "document_id",
                "consent_type",
                "name",
                "diagnosis",
                "transfusion_reason",
                "blood_component",
                "risk_description",
                "alternative_plan",
                "agent_sign",
                "patient_sign_datetime",
                "physician_sign",
                "physician_sign_datetime",
                "record_content",
            ],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="consent_form",
        records=[
            {
                "institute_id": "I",
                "patient_id": "P",
                "visit_id": "V",
                "document_id": "C1",
                "patient_name": "张三",
                "diagnosis": "贫血",
                "transfution_indication": "纠正贫血",
                "transfuse_variety": "红细胞",
                "risk_description": "已告知输血风险",
                "replace_scheme": "已告知替代方案",
                "agent_sign": "家属签名",
                "patient_agentsign_datetime": "2026-08-19 10:05:00+08",
                "physician_sign": "医师签名",
                "physician_sign_time": "2026-08-19 10:06:00+08",
            }
        ],
        primary_keys=["patient_id", "visit_id", "document_id"],
    )

    assert count == 1
    saved = executed_params[0]
    assert saved["name"] == "张三"
    # 标准《输血治疗同意书》源表没有通用 consent_type；不能因标题为空而被
    # 041/042 当作非输血同意书过滤掉。
    assert saved["consent_type"] == "blood_transfusion"
    assert saved["diagnosis"] == "贫血"
    assert saved["transfusion_reason"] == "纠正贫血"
    assert saved["blood_component"] == "红细胞"
    assert saved["risk_description"] == "已告知输血风险"
    assert saved["alternative_plan"] == "已告知替代方案"
    assert saved["agent_sign"] == "家属签名"
    assert saved["patient_sign_datetime"] == "2026-08-19 10:05:00+08"
    assert saved["physician_sign_datetime"] == "2026-08-19 10:06:00+08"


def test_upsert_to_local_maps_blood_application_source_identity_and_facts(monkeypatch):
    """输血申请单必须保留源端真实主键及 044 所需的结构化事实。"""

    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "application_id",
                "patient_bloodtype_abo",
                "transfuse_variety",
                "transfuse_volume",
                "transfuse_volume_unit",
                "request_datetime",
                "physician_name",
                "reason_for_blood",
                "hemoglobin",
                "hematocrit",
                "rbc",
                "prothrombin_time",
                "partial_thromboplastin_time",
                "fibrinogen",
                "albumin",
                "teg",
                "platelet_antibody",
                "rbc_antibody",
                "record_content",
            ],
            ["institute_id", "patient_id", "visit_id", "application_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="blood_application",
        records=[
            {
                "institute_id": "I",
                "patient_id": "P",
                "visit_id": "V",
                "apply_no": "BA-001",
                "blood_type": "A",
                "blood_component": "血小板",
                "blood_amount": "2",
                "blood_unit": "U",
                "apply_datetime": "2026-08-19 09:00:00+08",
                "apply_doctor": "李医生",
                "reason_for_blood": "纠正贫血",
                "hemoglobin": "68",
                "fibrinogen": "1.2",
            }
        ],
        primary_keys=["patient_id", "visit_id", "application_id"],
    )

    assert count == 1
    saved = executed_params[0]
    assert saved["application_id"] == "BA-001"
    assert saved["patient_bloodtype_abo"] == "A"
    assert saved["transfuse_variety"] == "血小板"
    assert saved["transfuse_volume"] == "2"
    assert saved["transfuse_volume_unit"] == "U"
    assert saved["request_datetime"] == "2026-08-19 09:00:00+08"
    assert saved["physician_name"] == "李医生"
    assert saved["reason_for_blood"] == "纠正贫血"
    assert saved["hemoglobin"] == "68"
    assert saved["fibrinogen"] == "1.2"


def test_blood_application_model_and_migration_preserve_044_assessment_facts():
    required = {
        "reason_for_blood",
        "hemoglobin",
        "hematocrit",
        "rbc",
        "prothrombin_time",
        "partial_thromboplastin_time",
        "fibrinogen",
        "albumin",
        "teg",
        "platelet_antibody",
        "rbc_antibody",
    }
    assert required.issubset(BloodApplication.__table__.columns.keys())
    assert required.issubset(set(_SNAPSHOT_SOURCE_FIELDS["blood_application"]))

    migration = _load_migration_module(
        "20260827_000039_preserve_pretransfusion_assessment_facts.py"
    )
    assert migration.revision == "20260827_000039"
    assert migration.down_revision == "20260824_000038"
    assert {name for name, _ in migration._ASSESSMENT_COLUMNS} == required


def test_exam_master_sync_uses_the_actual_exam_id_contract():
    entry = next(item for item in etl_sync.SYNC_TABLES if item["name"] == "exam_master")

    assert entry["key_fields"] == ["patient_id", "visit_id", "exam_id"]
    assert {"institute_id", "exam_id"}.issubset(ExamMaster.__table__.columns.keys())
    assert {
        "description",
        "impression",
        "recommendation",
        "abnormal_sign",
        "report_status",
    }.issubset(ExamMaster.__table__.columns.keys())


def test_consent_sync_maps_the_customer_transfusion_consent_source_to_logical_target():
    entry = next(item for item in etl_sync.SYNC_TABLES if item["name"] == "consent_form")

    assert entry["source_table"] == "bloodtrans_inform_consent"
    assert entry["procedure"] == "web.bloodtrans_inform_consent"


@pytest.mark.parametrize(
    ("table_name", "source_time_field"),
    (("handoff_record", "handoff_time"), ("handover_record", "handover_time")),
)
def test_upsert_to_local_preserves_handoff_authoritative_time(
    monkeypatch, table_name, source_time_field
):
    """071 的交接窗口不能因专用时间字段在同步时被丢弃而变成资料不足。"""

    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            list(
                (HandoffRecord if table_name == "handoff_record" else HandoverRecord)
                .__table__.columns.keys()
            ),
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name=table_name,
        records=[
            {
                "institute_id": "I",
                "patient_id": "P",
                "visit_id": "V",
                "document_id": "H1",
                source_time_field: "2026-08-19 10:05:00+08",
                "record_content": "已完成医师交接。",
            }
        ],
        primary_keys=["patient_id", "visit_id", "document_id"],
    )

    assert count == 1
    assert executed_params[0]["record_time"] == "2026-08-19 10:05:00+08"


def test_upsert_to_local_preserves_customer_consultation_event_times(monkeypatch):
    """069 必须保留客户源会诊申请、完成和文书时间，不能退化成全文猜测。"""

    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            list(ConsultationRecord.__table__.columns.keys()),
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="consultation_record",
        records=[
            {
                "institute_id": "I",
                "patient_id": "P",
                "visit_id": "V",
                "document_id": "C1",
                "consult_apply_time": "2026-08-19 08:00:00+08",
                "consultation_time": "2026-08-19 10:00:00+08",
                "record_time": "2026-08-19 10:05:00+08",
            }
        ],
        primary_keys=["patient_id", "visit_id", "document_id"],
    )

    assert count == 1
    assert executed_params[0]["request_time"] == "2026-08-19 08:00:00+08"
    assert executed_params[0]["consultation_time"] == "2026-08-19 10:00:00+08"
    assert executed_params[0]["record_time"] == "2026-08-19 10:05:00+08"


def test_customer_consultation_and_handoff_orm_types_match_audited_source() -> None:
    """同步合同按客户源真实类型保真，不依赖数据库隐式时间转换。"""

    assert ConsultationRecord.__table__.c.request_time.type.python_type is str
    assert ConsultationRecord.__table__.c.consultation_time.type.python_type.__name__ == "datetime"
    assert ConsultationRecord.__table__.c.record_time.type.python_type.__name__ == "datetime"
    assert HandoffRecord.__table__.c.shift_time.type.python_type.__name__ == "datetime"
    assert HandoffRecord.__table__.c.handoff_doctor.type.python_type is str
    assert HandoverRecord.__table__.c.shift_time.type.python_type.__name__ == "datetime"
    assert HandoverRecord.__table__.c.handover_doctor.type.python_type is str


@pytest.mark.parametrize(
    ("table_name", "source_fields"),
    (
        (
            "consultation_record",
            {
                "consult_apply_time": "2026-08-19 08:00:00+08",
                "consultation_time": "2026-08-19 10:00:00+08",
            },
        ),
        (
            "handoff_record",
            {"shift_time": "2026-08-19 11:00:00+08", "handoff_doctor": "张医生"},
        ),
        (
            "handover_record",
            {"shift_time": "2026-08-19 11:00:00+08", "handover_doctor": "李医生"},
        ),
    ),
)
def test_upsert_to_local_rejects_missing_consultation_handoff_contract_columns(
    monkeypatch, table_name, source_fields
):
    """客户未升级 037 时不得把 069/071 结构化事实静默过滤后继续同步。"""

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            raise AssertionError("合同校验失败前不得写数据库")

        def commit(self):
            raise AssertionError("合同校验失败前不得提交")

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            ["institute_id", "patient_id", "visit_id", "document_id"],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    with pytest.raises(ValueError, match="结构化字段未保留"):
        etl_sync.upsert_to_local(
            table_name=table_name,
            records=[
                {
                    "institute_id": "I",
                    "patient_id": "P",
                    "visit_id": "V",
                    "document_id": "DOC-1",
                    **source_fields,
                }
            ],
            primary_keys=["patient_id", "visit_id", "document_id"],
        )


@pytest.mark.parametrize(
    ("table_name", "model", "doctor_field"),
    (
        ("handoff_record", HandoffRecord, "handoff_doctor"),
        ("handover_record", HandoverRecord, "handover_doctor"),
    ),
)
def test_upsert_to_local_preserves_customer_handoff_shift_and_doctor(
    monkeypatch, table_name, model, doctor_field
):
    """071 的客户源 shift_time 和交接医生必须原样进入本地标准列。"""

    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            list(model.__table__.columns.keys()),
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name=table_name,
        records=[
            {
                "institute_id": "I",
                "patient_id": "P",
                "visit_id": "V",
                "document_id": "H1",
                "shift_time": "2026-08-19 11:00:00+08",
                doctor_field: "张医生",
            }
        ],
        primary_keys=["patient_id", "visit_id", "document_id"],
    )

    assert count == 1
    assert executed_params[0]["shift_time"] == "2026-08-19 11:00:00+08"
    assert executed_params[0][doctor_field] == "张医生"


def test_upsert_to_local_preserves_exam_master_structured_evidence(monkeypatch):
    """影像主表的描述、印象和报告状态必须进入本地证据快照。"""

    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, _stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            list(ExamMaster.__table__.columns.keys()),
            ["institute_id", "exam_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="exam_master",
        records=[
            {
                "institute_id": "I",
                "patient_id": "P",
                "visit_id": "V",
                "exam_id": "E-001",
                "description": "右肺见实性结节",
                "impression": "考虑恶性可能",
                "recommendation": "建议进一步检查",
                "abnormal_sign": "异常",
                "exam_result_status": "已审核",
                "exam_datetime": "2026-08-19 10:00:00+08",
                "report_datetime": "2026-08-19 11:00:00+08",
            }
        ],
        primary_keys=["patient_id", "visit_id", "exam_id"],
    )

    assert count == 1
    saved = executed_params[0]
    assert saved["description"] == "右肺见实性结节"
    assert saved["impression"] == "考虑恶性可能"
    assert saved["recommendation"] == "建议进一步检查"
    assert saved["abnormal_sign"] == "异常"
    assert saved["report_status"] == "已审核"
    assert saved["exam_time"] == "2026-08-19 10:00:00+08"
    assert saved["report_time"] == "2026-08-19 11:00:00+08"


def test_exam_master_description_and_impression_are_readable_as_rule_evidence():
    fields = _SNAPSHOT_SOURCE_FIELDS["exam_master"]

    assert {
        "description",
        "impression",
        "recommendation",
        "abnormal_sign",
        "report_status",
    }.issubset(fields)
    assert _row_text(
        {
            "description": "右肺实性结节",
            "impression": "考虑恶性可能",
            "report_status": "已审核",
        }
    ) == "右肺实性结节 考虑恶性可能"


def test_upsert_to_local_refuses_partial_full_visit_reload_before_delete(monkeypatch):
    """重载病例有任一源行缺主键时，旧快照必须原样保留。"""

    executed: list[tuple[str, object]] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed.append((str(stmt), params))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            ["institute_id", "patient_id", "visit_id", "document_id", "record_content"],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    with pytest.raises(ValueError, match="拒绝删除旧快照"):
        etl_sync.upsert_to_local(
            table_name="daily_course_record",
            records=[
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "document_id": "D1",
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "record_content": "缺文书主键",
                },
            ],
            primary_keys=["document_id"],
            replace_case_refs=(CaseRef("H1", "P1", "V1"),),
        )

    assert executed == []


@pytest.mark.parametrize(
    "filename",
    (
        "20260819_000035_extend_surgery_record_structured_fields.py",
        "20260819_000036_preserve_consent_and_exam_master_contracts.py",
        "20260821_000037_preserve_consultation_and_handoff_facts.py",
        "20260824_000038_preserve_drug_order_planned_start.py",
        "20260903_000043_preserve_nondrug_order_lifecycle_times.py",
    ),
)
def test_sync_contract_migrations_never_mutate_public_source_in_split_mode(monkeypatch, filename):
    class _Inspector:
        @staticmethod
        def get_schema_names():
            return ["public", "cdm"]

    monkeypatch.setenv("DB_SCHEMA_MODE", "split")
    migration = _load_migration_module(filename)

    assert migration._target_schemas(_Inspector()) == ["cdm"]


def test_consultation_handoff_migration_is_idempotent_and_cdm_only(monkeypatch):
    migration = _load_migration_module(
        "20260821_000037_preserve_consultation_and_handoff_facts.py"
    )
    existing: dict[str, set[str]] = {
        "consultation_record": set(),
        "handoff_record": set(),
        "handover_record": set(),
    }
    added: list[tuple[str, str, str]] = []

    class _Inspector:
        @staticmethod
        def get_schema_names():
            return ["public", "cdm"]

        @staticmethod
        def get_table_names(*, schema):
            assert schema == "cdm"
            return list(existing)

        @staticmethod
        def get_columns(table_name, *, schema):
            assert schema == "cdm"
            return [{"name": name} for name in existing[table_name]]

    def _add_column(table_name, column, *, schema):
        assert schema == "cdm"
        added.append((schema, table_name, column.name))
        existing[table_name].add(column.name)

    monkeypatch.setenv("DB_SCHEMA_MODE", "split")
    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: _Inspector())
    monkeypatch.setattr(migration.op, "add_column", _add_column)

    migration.upgrade()
    migration.upgrade()

    assert added == [
        ("cdm", "consultation_record", "request_time"),
        ("cdm", "consultation_record", "consultation_time"),
        ("cdm", "consultation_record", "record_time"),
        ("cdm", "handoff_record", "shift_time"),
        ("cdm", "handoff_record", "handoff_doctor"),
        ("cdm", "handover_record", "shift_time"),
        ("cdm", "handover_record", "handover_doctor"),
    ]


def test_drug_order_planned_start_migration_is_idempotent_and_cdm_only(monkeypatch):
    migration = _load_migration_module(
        "20260824_000038_preserve_drug_order_planned_start.py"
    )
    existing = {"inpat_drug_order": set()}
    added: list[tuple[str, str, str]] = []

    class _Inspector:
        @staticmethod
        def get_schema_names():
            return ["public", "cdm"]

        @staticmethod
        def get_table_names(*, schema):
            assert schema == "cdm"
            return list(existing)

        @staticmethod
        def get_columns(table_name, *, schema):
            assert schema == "cdm"
            return [{"name": name} for name in existing[table_name]]

    def _add_column(table_name, column, *, schema):
        assert schema == "cdm"
        added.append((schema, table_name, column.name))
        existing[table_name].add(column.name)

    monkeypatch.setenv("DB_SCHEMA_MODE", "split")
    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: _Inspector())
    monkeypatch.setattr(migration.op, "add_column", _add_column)

    migration.upgrade()
    migration.upgrade()

    assert added == [("cdm", "inpat_drug_order", "planned_start_datetime")]


def test_nondrug_order_lifecycle_migration_is_idempotent_and_cdm_only(monkeypatch):
    migration = _load_migration_module(
        "20260903_000043_preserve_nondrug_order_lifecycle_times.py"
    )
    existing = {"inpat_nondrug_order": set()}
    added: list[tuple[str, str, str]] = []

    class _Inspector:
        @staticmethod
        def get_schema_names():
            return ["public", "cdm"]

        @staticmethod
        def get_table_names(*, schema):
            assert schema == "cdm"
            return list(existing)

        @staticmethod
        def get_columns(table_name, *, schema):
            assert schema == "cdm"
            return [{"name": name} for name in existing[table_name]]

    def _add_column(table_name, column, *, schema):
        assert schema == "cdm"
        added.append((schema, table_name, column.name))
        existing[table_name].add(column.name)

    monkeypatch.setenv("DB_SCHEMA_MODE", "split")
    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: _Inspector())
    monkeypatch.setattr(migration.op, "add_column", _add_column)

    migration.upgrade()
    migration.upgrade()

    assert added == [
        ("cdm", "inpat_nondrug_order", "planned_start_datetime"),
        ("cdm", "inpat_nondrug_order", "planned_end_datetime"),
    ]
