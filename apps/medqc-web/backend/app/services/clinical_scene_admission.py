"""新任务的临床场景合同；不以时间空值、首页或查询范围推断仍在院。"""
from datetime import date, datetime
from typing import Any, Mapping

from .discharge_time import DischargeTime

SCENE_POLICY = "clinical-scene-admission-v1"


def resolve_scene(*, discharge: DischargeTime, document_present: bool,
                  document_invalid: bool, verified_status: str = "") -> dict[str, Any]:
    """出院状态与时间完整性独立；调用者先按来源、三坐标及核验时效过滤投影。"""
    time_status = "conflict" if discharge.conflict else "present" if discharge.value else "missing"
    time_proves_discharge = isinstance(discharge.value, (date, datetime)) and not (
        (document_invalid and discharge.source.startswith("discharge_record."))
        or (discharge.conflict and discharge.source.startswith("death_record."))
    )
    if verified_status == "inpatient" and time_proves_discharge:
        scene, state, reason = "unknown", "unknown", "discharge_state_conflict"
    elif verified_status == "discharged":
        scene, state, reason = "final", "discharged", "verified_discharge_state"
    elif time_proves_discharge:
        scene, state, reason = "final", "discharged", "discharge_business_time"
    elif verified_status == "inpatient":
        scene, state, reason = "running", "inpatient", "verified_inpatient_state"
    else:
        scene, state = "unknown", "unknown"
        reason = "discharge_document_unconfirmed" if document_present else "discharge_state_unknown"
    return {"qc_scene_policy": SCENE_POLICY, "qc_scope": scene, "qc_scene_reason": reason,
            "qc_discharge_state": state, "qc_discharge_time_status": time_status,
            "qc_allowed_scopes": ["all", scene] if scene != "unknown" else []}


def scene_rejection(record: Mapping[str, Any], requested_scope: str) -> str | None:
    """创建入口与候选目录消费同一决策；all 不会强制改成 final/running。"""
    from .luxian_0609.clinical_material_policy import clinical_record_scene
    scene = clinical_record_scene(record)
    if scene not in {"running", "final"}:
        return "case_scene_unknown"
    if requested_scope not in {"all", scene}:
        return "case_scene_scope_mismatch"
    return None
