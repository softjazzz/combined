"""独立报表后端的导入完整性及旧模型保护。"""

import importlib

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "record_quality_report_service",
        "frontpage_quality_report_service",
        "core_system_report_service",
        "special_record_report_service",
        "staff_work_analysis_service",
        "manual_quality_report_service",
        "record_remediation_report_service",
        "modern_case_qc_result_service",
        "scoring_standard_service",
        "rule_set_version_service",
        "report_case_scope",
    ],
)
def test_service_imports_without_database_or_runtime_initialization(module):
    importlib.import_module(f"app.services.{module}")


@pytest.mark.parametrize(
    "module",
    [
        "quality_reports",
        "staff_work_analysis",
        "core_system_reports",
        "special_record_reports",
        "manual_quality_reports",
    ],
)
def test_router_imports_without_database_or_legacy_ddl(module):
    importlib.import_module(f"app.routers.{module}")


def test_report_metadata_does_not_add_columns_to_legacy_models():
    from app.database.models import qc
    from app.database.models import v36_reports as report

    assert qc.SysUser.metadata is not report.SysUser.metadata
    assert "institute_id" not in qc.SysUser.__table__.c
    assert "institute_id" in report.SysUser.__table__.c
    assert "identity_version" not in qc.QCDefect.__table__.c
    assert "identity_version" in report.QCDefect.__table__.c


def test_builtin_report_version_uses_target_customer_scope_without_changing_catalog():
    from app.services.qc_rule_sets import get_sichuan_rule_set
    from app.services.rule_set_version_service import resolve_rule_set_version
    from app.services.sample_validation_rule_sets import (
        get_luxian_0609_customer_execution_scope,
    )

    catalog = get_sichuan_rule_set("luxian_0609_qc_v1")
    before = catalog.rule_ids
    active, paused = get_luxian_0609_customer_execution_scope()
    data = resolve_rule_set_version(catalog.key, catalog.version)
    assert tuple(data["active_rule_ids"]) == active
    assert tuple(data["paused_rule_ids"]) == paused
    assert catalog.rule_ids == before
