from __future__ import annotations

from typing import Any, Dict, List, Optional


class DRGCaseNotFoundError(LookupError):
    """Raised when a demo case cannot be found."""


def _build_result_payload(result: Dict[str, Any], total_cost: float) -> Dict[str, Any]:
    baseline_payment = result.get("baseline_payment", 0)
    profit_margin = round((baseline_payment - total_cost) / baseline_payment, 4) if baseline_payment else 0.0
    result["actual_cost"] = total_cost
    result["profit_margin"] = profit_margin
    return result


async def predict_realtime(
    grouping_service,
    *,
    primary_diagnosis_code: str,
    secondary_diagnosis_codes: Optional[List[str]],
    procedure_codes: Optional[List[str]],
    patient_age: int,
    patient_gender: str,
    los: int,
    region: str,
    total_cost: float,
) -> Dict[str, Any]:
    result = await grouping_service.group_drg(
        primary_diagnosis=primary_diagnosis_code,
        secondary_diagnoses=secondary_diagnosis_codes or [],
        procedures=procedure_codes or [],
        patient_age=patient_age,
        patient_gender=patient_gender,
        los=los,
        city_name=region,
        total_fee=total_cost,
    )
    result = _build_result_payload(result, total_cost)
    return {"data": result, "message": "分组成功" if result.get("success") else "分组失败（降级模式）"}


async def predict_from_case(
    store,
    grouping_service,
    *,
    admission_id: str,
    region: Optional[str],
) -> Dict[str, Any]:
    case = store.get_case_detail(admission_id)
    if not case:
        raise DRGCaseNotFoundError(admission_id)

    primary_diagnosis = case.get("principal_diagnosis_code", "I10.x00")
    secondary_diagnoses = case.get("secondary_diagnosis_codes", [])
    procedures = case.get("procedure_codes", [])
    patient_age = case.get("patient_age", 58)
    patient_gender = case.get("patient_gender", "M")
    los = case.get("hospital_days", 7)
    total_cost = float(case.get("total_cost") or 0.0)

    result = await grouping_service.group_drg(
        primary_diagnosis=primary_diagnosis,
        secondary_diagnoses=secondary_diagnoses,
        procedures=procedures,
        patient_age=patient_age,
        patient_gender=patient_gender,
        los=los,
        city_name=region or "四川省",
        total_fee=total_cost,
    )
    result = _build_result_payload(result, total_cost)
    store.append_grouping_history(admission_id, result)
    return {"data": result, "message": "分组成功" if result.get("success") else "分组失败（降级模式）"}


def get_grouping_history(store, *, admission_id: str) -> Dict[str, Any]:
    history = store.get_grouping_history(admission_id)
    return {"history": history, "total": len(history)}


def list_suggestions(
    store,
    *,
    admission_id: Optional[str],
    status: Optional[str],
    limit: int,
) -> Dict[str, Any]:
    items = store.list_suggestions(admission_id=admission_id, status=status, limit=limit)
    return {"suggestions": items, "total": len(items)}


def handle_suggestion(store, *, suggestion_id: int, action: str) -> Dict[str, Any]:
    new_status = "accepted" if action == "accept" else "rejected"
    ok = store.update_suggestion_status(suggestion_id, new_status)
    if not ok:
        raise DRGCaseNotFoundError(str(suggestion_id))
    return {"success": True, "message": "建议已处理"}


def list_alerts(
    store,
    *,
    admission_id: Optional[str],
    alert_level: Optional[str],
    status: Optional[str],
    limit: int,
) -> Dict[str, Any]:
    items = store.list_alerts(admission_id=admission_id, alert_level=alert_level, status=status, limit=limit)
    return {"alerts": items, "total": len(items)}


def handle_alert(store, *, alert_id: int, action: str) -> Dict[str, Any]:
    new_status = "acknowledged" if action == "acknowledge" else "resolved"
    ok = store.update_alert_status(alert_id, new_status)
    if not ok:
        raise DRGCaseNotFoundError(str(alert_id))
    return {"success": True, "message": "预警已处理"}


def get_demo_story_cases(store) -> Dict[str, Any]:
    cases = store.story_cases
    if not cases:
        return {"cases": []}
    return {
        "cases": [
            {"name": "高风险亏损", "admission_id": cases.high_risk_loss},
            {"name": "编码冲突", "admission_id": cases.coding_conflict},
            {"name": "高费用预警", "admission_id": cases.high_cost_alert},
        ]
    }

