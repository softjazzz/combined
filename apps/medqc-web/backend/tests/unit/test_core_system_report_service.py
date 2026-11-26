from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from app.database.models.v36_reports import SysUser
from app.services.core_system_report_service import (
    CoreSystemReportService,
    csv_export,
    reference,
)
from app.services.defect_rectification_service import RectificationError
from app.services.record_quality_report_service import (
    RecordQualityReportInvalid,
    RecordQualityReportTooLarge,
)
from app.services.rule_set_version_service import RuleSetVersionNotFound
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def env():
    engine = create_engine("sqlite://")
    SysUser.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions.begin() as session:
        session.add_all(
            [
                SysUser(
                    id="admin",
                    username="admin",
                    display_name="合成管理员",
                    password_hash="synthetic",
                    role="admin",
                    is_active=True,
                ),
                SysUser(
                    id="manager",
                    username="manager",
                    display_name="合成质控员",
                    password_hash="synthetic",
                    role="qc_manager",
                    institute_id="H1",
                    is_active=True,
                ),
                SysUser(
                    id="disabled",
                    username="disabled",
                    display_name="合成失活用户",
                    password_hash="synthetic",
                    role="admin",
                    is_active=False,
                ),
                SysUser(
                    id="doctor",
                    username="doctor",
                    display_name="合成医生",
                    password_hash="synthetic",
                    role="doctor",
                    institute_id="H1",
                    is_active=True,
                ),
            ]
        )
    records = [
        dict(
            institute_id="H1",
            patient_id="P1",
            visit_id="V1",
            patient_name="合成患者",
            department="内科",
            attending_physician="合成医师",
        ),
        dict(
            institute_id="H2",
            patient_id="P1",
            visit_id="V1",
            patient_name="跨院合成患者",
            department="内科",
            attending_physician="合成医师",
        ),
    ]
    result = {
        "status": "ready",
        "completed_at": "2026-10-01T02:00:00Z",
        "root_job_id": "J1",
        "envelope_id": "E1",
        "rule_set_key": "synthetic",
        "rule_set_version": "v1",
        "items": [
            {
                "rule_id": "R1",
                "rule_name": "合成质控点1",
                "status": "defect",
                "is_confirmed_issue": True,
            },
            {
                "rule_id": "R2",
                "rule_name": "合成质控点2",
                "status": "compliant",
                "is_confirmed_issue": False,
            },
        ],
    }
    results = {
        ("H1", "P1", "V1"): deepcopy(result),
        ("H2", "P1", "V1"): {
            **deepcopy(result),
            "rule_set_version": "v2",
            "root_job_id": "J2",
            "envelope_id": "E2",
        },
    }
    versions = {
        "v1": {
            "entries": [
                {"rule_id": "R1", "core_system_ids": ["CORE-01"]},
                {"rule_id": "R2", "core_system_ids": ["CORE-01", "CORE-02"]},
            ]
        },
        "v2": {
            "entries": [
                {"rule_id": "R1", "core_system_ids": ["CORE-02"]},
                {"rule_id": "R2", "core_system_ids": []},
            ]
        },
    }
    scope = Mock(side_effect=lambda **kwargs: records)
    loader = Mock(
        side_effect=lambda refs: {
            tuple(
                ref[key] for key in ("institute_id", "patient_id", "visit_id")
            ): results[
                tuple(ref[key] for key in ("institute_id", "patient_id", "visit_id"))
            ]
            for ref in refs
        }
    )
    resolver = Mock(side_effect=lambda key, version: versions[version])
    service = CoreSystemReportService(
        sessions, scope, loader, lambda items: items, resolver
    )
    yield service, records, results, versions, loader, resolver, sessions
    engine.dispose()


def test_deduplicates_case_points_and_frozen_version_changes(env):
    service, _, _, _, loader, resolver, _ = env
    data = service.report("admin")
    first, second, empty = data["systems"][:3]
    assert (first["record_count"], first["problem_records"], first["problem_rate"]) == (
        1,
        1,
        1,
    )
    assert (
        second["record_count"],
        second["problem_records"],
        second["problem_rate"],
    ) == (2, 1, 0.5)
    assert (empty["record_count"], empty["problem_records"], empty["problem_rate"]) == (
        None,
        None,
        None,
    )
    assert loader.call_count == 1 and resolver.call_count == 2
    assert {row["institute_id"] for row in data["items"]} == {"H1", "H2"}
    assert data["summary"]["unknown_records"] == 0


def test_unknown_null_distinct_from_explicit_noncore_and_real_zero(env):
    service, _, results, versions, *_ = env
    versions["v1"]["entries"][0]["core_system_ids"] = None
    versions["v2"]["entries"][0]["core_system_ids"] = []
    data = service.report("admin")
    assert data["summary"]["unknown_records"] == 1
    assert data["summary"]["unknown_points"] == 1
    assert data["systems"][0]["problem_records"] == 0
    assert data["systems"][0]["problem_rate"] == 0
    assert data["systems"][0]["defect_total"] == 0
    assert data["systems"][2]["problem_rate"] is None
    assert data["systems"][2]["defect_total"] is None
    unknown = service.report("admin", system_id="unknown")
    assert unknown["total"] == 1 and unknown["items"][0]["points"][0]["rule_id"] == "R1"
    results[("H1", "P1", "V1")]["rule_set_version"] = None
    assert service.report("admin")["summary"]["unknown_points"] == 2


def test_persistent_institute_scope_before_batch_read(env):
    service, _, _, _, loader, *_ = env
    data = service.report("manager", institute_id="H1", department="内科")
    assert data["total"] == 1
    assert loader.call_args.args[0] == [
        {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}
    ]
    with pytest.raises(RectificationError):
        service.report("manager", institute_id="H2")
    assert loader.call_count == 1
    for actor in ("disabled", "doctor", "missing"):
        with pytest.raises(RectificationError):
            service.report(actor)


def test_department_pair_and_dates_and_pagination(env):
    service, *_ = env
    with pytest.raises(RecordQualityReportInvalid):
        service.report("admin", department="内科")
    with pytest.raises(RecordQualityReportInvalid):
        service.report(
            "admin",
            completed_from=datetime(2026, 10, 2),
            completed_to=datetime(2026, 10, 1),
        )
    data = service.report(
        "admin",
        completed_from=datetime(2026, 10, 1, 2, tzinfo=timezone.utc),
        completed_to=datetime(2026, 10, 1, 2, tzinfo=timezone.utc),
        system_id="CORE-02",
        page=2,
        page_size=1,
    )
    assert data["total"] == 2 and len(data["items"]) == 1
    assert len(data["_export_rows"]) == 2
    assert (
        service.report(
            "admin", completed_from=datetime(2026, 10, 1, 3, tzinfo=timezone.utc)
        )["total"]
        == 0
    )


def test_source_failure_not_empty_and_unknown_unavailable(env):
    service, _, results, _, loader, resolver, _ = env
    loader.side_effect = RuntimeError("synthetic source down")
    with pytest.raises(RuntimeError):
        service.report("admin")
    loader.side_effect = lambda refs: results
    resolver.side_effect = RuntimeError("synthetic classification down")
    with pytest.raises(RuntimeError):
        service.report("admin")
    results[("H1", "P1", "V1")] = {"status": "technical_error"}
    resolver.side_effect = lambda key, version: {"entries": []}
    data = service.report("admin", system_id="unknown")
    assert data["summary"]["unavailable_records"] == 1 and data["total"] == 2


def test_missing_version_has_unknown_classification_not_current_fallback(env):
    service, _, _, _, _, resolver, _ = env
    resolver.side_effect = RuleSetVersionNotFound("合成版本不存在")
    data = service.report("admin")
    assert data["summary"]["unknown_records"] == 2
    assert data["summary"]["unknown_points"] == 4
    assert data["summary"]["unknown_defects"] == 2
    assert all(row["record_count"] is None for row in data["systems"])
    assert resolver.call_args_list[0].args == ("synthetic", "v1")
    assert resolver.call_args_list[1].args == ("synthetic", "v2")


def test_limit_and_duplicate_points_fail_closed(env):
    service, records, results, *_ = env
    results[("H1", "P1", "V1")]["items"].append(
        deepcopy(results[("H1", "P1", "V1")]["items"][0])
    )
    with pytest.raises(RuntimeError):
        service.report("admin")
    records[:] = [{**records[0], "patient_id": str(i)} for i in range(5001)]
    with pytest.raises(RecordQualityReportTooLarge):
        service.report("admin")


def test_version_cache_and_full_reference_and_csv_guard(env):
    service, records, results, _, _, resolver, _ = env
    records[0]["patient_name"] = "=synthetic()"
    records.append({**records[0], "patient_id": "P2"})
    results[("H1", "P2", "V1")] = deepcopy(results[("H1", "P1", "V1")])
    data = service.report("admin", system_id="CORE-01", problems_only=True)
    assert resolver.call_count == 2
    assert data["total"] == 2
    text = csv_export(data)
    assert "'=synthetic()" in text and "H1,P1,V1" in text and "冻结版本" in text
    ref = reference()
    assert len(ref["systems"]) == 18
    assert all(
        "（一）定义" in row["text"] and "（二）基本要求" in row["text"]
        for row in ref["systems"]
    )
    assert ref["reference_date"] == "2018-04-18"


def test_core_defect_distribution_counts_points_not_cases_and_exports_same_scope(env):
    service, _, results, versions, *_ = env
    results[("H1", "P1", "V1")]["items"][1]["is_confirmed_issue"] = True
    data = service.report("admin", problems_only=True)
    assert data["systems"][0]["defect_total"] == 2
    assert data["systems"][0]["problem_records"] == 1
    assert data["top_systems"][0]["defect_total"] == 2
    assert data["summary"]["unknown_defects"] == 0
    assert "确认缺陷数" in csv_export(data)
    assert "未知分类确认缺陷,0" in csv_export(data)
    selected = service.report("admin", system_id="CORE-01", problems_only=True)
    assert selected["total"] == 1
    assert sum(p["is_confirmed_issue"] for p in selected["items"][0]["points"]) == 2
    versions["v1"]["entries"][0]["core_system_ids"] = None
    unknown = service.report("admin")
    assert unknown["summary"]["unknown_defects"] == 1
    assert unknown["systems"][0]["defect_total"] == 1


def test_sync_admin_and_super_admin_with_bound_institute_can_filter_department(env):
    service, _, _, _, loader, _, sessions = env
    with sessions.begin() as session:
        session.add_all(
            [
                SysUser(
                    id="sync-bound",
                    username="sync-bound",
                    display_name="绑定院区同步管理员",
                    password_hash="synthetic",
                    role="sync_admin",
                    roles_json='["sync_admin", "super_admin", "admin"]',
                    institute_id="H1",
                    is_active=True,
                ),
                SysUser(
                    id="super-bound",
                    username="super-bound",
                    display_name="绑定院区超管",
                    password_hash="synthetic",
                    role="super_admin",
                    roles_json='["super_admin"]',
                    institute_id="H1",
                    is_active=True,
                ),
            ]
        )
    # 绑定院区的 sync_admin / super_admin 按科室筛选不再 422，默认收敛至绑定院区 H1
    data_sync = service.report("sync-bound", department="内科")
    assert data_sync["total"] == 1
    assert data_sync["items"][0]["institute_id"] == "H1"

    data_super = service.report("super-bound", department="内科")
    assert data_super["total"] == 1
    assert data_super["items"][0]["institute_id"] == "H1"

    # sync_admin 仍可显式切换至其他院区 H2
    data_h2 = service.report("sync-bound", institute_id="H2", department="内科")
    assert data_h2["total"] == 1
    assert data_h2["items"][0]["institute_id"] == "H2"
    assert loader.call_count == 3
