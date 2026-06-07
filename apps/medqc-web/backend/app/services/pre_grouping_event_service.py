from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .pre_grouping_diff_service import PreGroupingDiffService


ExtractPreGroupFn = Callable[[str], Awaitable[Dict[str, Any]]]


_SIMULATION_STORE: Dict[str, List[Dict[str, Any]]] = {}


def _utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _input_hash(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _text(value: object) -> str:
    return str(value or "").strip()


def _first_non_empty(*values: object) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _normalize_gender(value: object) -> str:
    text = _text(value).upper()
    if text in {"2", "F", "女", "FEMALE"}:
        return "F"
    return "M"


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value))
    except Exception:
        return default


async def _default_extract_pre_group(medical_text: str) -> Dict[str, Any]:
    from app.routers.case_front_page import ExtractRequest, extract_for_pre_group

    response = await extract_for_pre_group(ExtractRequest(medical_text=medical_text))
    data = response.get("data") if isinstance(response, dict) else None
    return data if isinstance(data, dict) else {}


class PreGroupingEventService:
    """入院记录完成后的只读预入组事件服务。"""

    def __init__(
        self,
        *,
        extract_pre_group: Optional[ExtractPreGroupFn] = None,
        dip_service: Any | None = None,
        drg_service: Any | None = None,
    ) -> None:
        self._extract_pre_group = extract_pre_group or _default_extract_pre_group
        self._dip_service = dip_service
        self._drg_service = drg_service

    async def on_admission_note_completed(
        self,
        *,
        visit_id: str,
        document_id: str,
        medical_text: str,
        patient_id: str = "",
    ) -> Dict[str, Any]:
        if not _text(visit_id):
            raise ValueError("visit_id 不能为空")
        if not _text(document_id):
            raise ValueError("document_id 不能为空")
        if not _text(medical_text):
            raise ValueError("medical_text 不能为空")

        extracted = await self._extract_pre_group(medical_text)
        diagnoses = extracted.get("diagnoses") if isinstance(extracted.get("diagnoses"), dict) else {}
        procedures = extracted.get("procedures") if isinstance(extracted.get("procedures"), dict) else {}
        basic_info = extracted.get("basic_info") if isinstance(extracted.get("basic_info"), dict) else {}
        costs = extracted.get("costs") if isinstance(extracted.get("costs"), dict) else {}

        pdx_code = _first_non_empty(
            diagnoses.get("admission_main_icd"),
            diagnoses.get("discharge_main_icd"),
        )
        adx_codes = [
            _text(code)
            for code in (
                diagnoses.get("admission_other_icds")
                or diagnoses.get("discharge_other_icds")
                or []
            )
            if _text(code)
        ]
        proc_code = _first_non_empty(procedures.get("main_procedure_code"))
        patient_age = _safe_int(basic_info.get("age_years"), 50)
        patient_gender = _normalize_gender(basic_info.get("gender") or basic_info.get("gender_text"))
        los = _safe_int(basic_info.get("actual_los") or extracted.get("los"), 7)
        total_fee = _safe_float(costs.get("total_cost") or costs.get("total_fee"), 0.0)

        grouping = await self._run_grouping(
            pdx_code=pdx_code,
            adx_codes=adx_codes,
            proc_code=proc_code,
            patient_age=patient_age,
            patient_gender=patient_gender,
            los=los,
            total_fee=total_fee,
        )

        history = _SIMULATION_STORE.setdefault(visit_id, [])
        previous_result = history[-1] if history else None
        version = len(history) + 1
        result = {
            "visit_id": visit_id,
            "patient_id": _text(patient_id),
            "document_id": document_id,
            "simulation_id": f"pregrp-{visit_id}-{version}",
            "version": version,
            "created_at": _utc_now_iso(),
            "status": "simulation",
            "read_only": True,
            "writes_formal_tables": False,
            "input_hash": _input_hash(medical_text),
            "input_summary": {
                "pdx_code": pdx_code,
                "adx_count": len(adx_codes),
                "procedure_count": 1 if proc_code else 0,
                "patient_age": patient_age,
                "patient_gender": patient_gender,
                "los": los,
                "total_fee": total_fee,
            },
            "extraction": {
                "admission_id": _text(extracted.get("admission_id")),
                "diagnoses": diagnoses,
                "procedures": procedures,
                "basic_info": basic_info,
            },
            "grouping": grouping,
            "safety": {
                "message": "该结果仅用于事前模拟入组，不写入病案首页、医保结算清单或正式 DRG/DIP 结果。",
                "formal_write": False,
            },
        }
        result["change_tracking"] = PreGroupingDiffService().build_change_tracking(
            previous_result=previous_result,
            current_result=result,
        )
        history.append(result)
        return result

    async def _run_grouping(
        self,
        *,
        pdx_code: str,
        adx_codes: List[str],
        proc_code: str,
        patient_age: int,
        patient_gender: str,
        los: int,
        total_fee: float,
    ) -> Dict[str, Any]:
        warnings: List[str] = []
        dip_result: Dict[str, Any] = {"success": False, "error": "缺少主诊断编码，未执行 DIP 模拟"}
        drg_result: Dict[str, Any] = {"success": False, "error": "缺少主诊断编码，未执行 DRG 模拟"}

        if pdx_code:
            dip_service = self._dip_service
            if dip_service is None:
                from app.services.dip_grouping_service import DIPGrouperService

                dip_service = DIPGrouperService()
            try:
                dip_result = await dip_service.group_dip(
                    city_name="泸州市",
                    pdx_code=pdx_code,
                    adx_code=",".join(adx_codes),
                    proc_code=proc_code,
                    patient_gender=patient_gender,
                    patient_age=patient_age,
                    los=los,
                    total_fee=total_fee,
                )
            except Exception as exc:
                warnings.append(f"DIP 模拟失败: {type(exc).__name__}")
                dip_result = {"success": False, "error": str(exc)}

            drg_service = self._drg_service
            if drg_service is None:
                from app.services.drg_grouping_service import DRGGroupingService

                drg_service = DRGGroupingService()
            try:
                drg_result = await drg_service.group_drg(
                    primary_diagnosis=pdx_code,
                    secondary_diagnoses=adx_codes,
                    procedures=[proc_code] if proc_code else [],
                    patient_age=patient_age,
                    patient_gender=patient_gender,
                    los=los,
                    city_name="四川省",
                    total_fee=total_fee,
                )
            except Exception as exc:
                warnings.append(f"DRG 模拟失败: {type(exc).__name__}")
                drg_result = {"success": False, "error": str(exc), "fallback": True}

        return {
            "mode": "simulation",
            "dip": dip_result,
            "drg": drg_result,
            "warnings": warnings,
        }


def get_pre_grouping_history(visit_id: str) -> List[Dict[str, Any]]:
    return list(_SIMULATION_STORE.get(visit_id, []))


def clear_pre_grouping_history() -> None:
    _SIMULATION_STORE.clear()
