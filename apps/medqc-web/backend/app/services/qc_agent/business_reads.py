"""在授权病例范围内复用正式读取服务；不拥有结果或统计判定。"""
from __future__ import annotations

from fastapi import HTTPException

from .business_access import BusinessAccess


def scoped_records(*, institute_id: str, department: str, doctor: str | None, hospital_status: str) -> list[dict[str, str]]:
    from app.services.workstation.luxian_0609_result_analysis_service import _load_current_workstation_records
    rows = _load_current_workstation_records(department=department, doctor=doctor, hospital_status=hospital_status)
    # 在加载任何 Canonical 结果与计算正式指标之前限定机构；同名科室不能跨院。
    return [row for row in rows if row.get("institute_id") == institute_id and row.get("department") == department]


def require_record(access: BusinessAccess, user: dict, identity: dict[str, str], view: str, department: str | None) -> None:
    if view == "doctor":
        access.require_case(user, identity)
        return
    access.require_department(user, identity["institute_id"], department)
    rows = scoped_records(institute_id=identity["institute_id"], department=department, doctor=None, hospital_status="all")
    if not any(all(row.get(key) == value for key, value in identity.items()) for row in rows):
        raise HTTPException(403, "该病例当前不属于已授权机构和科室")


def saved_record(identity: dict[str, str]) -> dict:
    from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
    result = CustomQCWorkspaceService(readonly=True).get_latest_luxian_0609_record_result(**identity)
    if result.get("state") == "not_found":
        raise HTTPException(404, "该病例暂无可读取的保存结果")
    return result


def department_analysis(*, institute_id: str, department: str, **filters) -> dict:
    from app.services.workstation.luxian_0609_result_analysis_service import Luxian0609ResultAnalysisService
    from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
    def load_scope(**kwargs):
        return scoped_records(institute_id=institute_id, **kwargs)
    def load_results(record_refs):
        return CustomQCWorkspaceService(readonly=True).build_luxian_0609_completed_record_result_summaries(record_refs=record_refs, include_items=True)
    return Luxian0609ResultAnalysisService(record_scope_loader=load_scope, result_loader=load_results).get_analysis(department=department, **filters)
