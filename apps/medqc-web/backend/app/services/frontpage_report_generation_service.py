from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from ..database.connection import engine
from ..schemas.frontpage import FrontPageDraft
from .frontpage_extraction_service import FrontPageExtractionService, default_frontpage_service
from .settlement_assembly_service import SettlementAssemblyService


REPORT_SCENES = {"nhc_frontpage", "insurance_settlement", "combined"}

ADMISSION_CONDITION_TEXT = {
    "1": "有",
    "2": "临床未确定",
    "3": "情况不明",
    "4": "无",
}


class FrontPageReportInputError(ValueError):
    """统一报告草稿生成的输入错误。"""


@dataclass(frozen=True)
class CoverageRequirement:
    group: str
    field: str
    path: str
    message: str = ""


COVERAGE_REQUIREMENTS: tuple[CoverageRequirement, ...] = (
    CoverageRequirement("患者基本信息", "患者姓名", "frontpage.basic_info.patient_name"),
    CoverageRequirement("患者基本信息", "性别", "frontpage.basic_info.gender_text"),
    CoverageRequirement("患者基本信息", "出生日期", "frontpage.basic_info.birth_date"),
    CoverageRequirement("患者基本信息", "身份证号", "frontpage.basic_info.id_number"),
    CoverageRequirement("住院相关信息", "病案号", "frontpage.hospitalization.medical_record_no"),
    CoverageRequirement("住院相关信息", "入院时间", "frontpage.hospitalization.admission_datetime"),
    CoverageRequirement("住院相关信息", "出院时间", "frontpage.hospitalization.discharge_datetime"),
    CoverageRequirement("住院相关信息", "入院科室", "frontpage.hospitalization.admission_dept"),
    CoverageRequirement("住院相关信息", "出院科室", "frontpage.hospitalization.discharge_dept"),
    CoverageRequirement("诊断及手术", "门急诊诊断", "frontpage.diagnoses.ed_diagnoses"),
    CoverageRequirement("诊断及手术", "出院主要诊断", "frontpage.diagnoses.discharge_main_diagnosis"),
    CoverageRequirement("诊断及手术", "出院其他诊断", "frontpage.diagnoses.discharge_other_diagnoses"),
    CoverageRequirement("诊断及手术", "主要手术及操作", "frontpage.procedures.main_procedure"),
    CoverageRequirement("诊断及手术", "其他手术及操作", "frontpage.procedures.other_procedures_structured"),
    CoverageRequirement("其他住院医疗信息", "损伤中毒外因", "frontpage.other_medical_info.injury_poison"),
    CoverageRequirement("其他住院医疗信息", "病理诊断", "frontpage.other_medical_info.pathology"),
    CoverageRequirement("其他住院医疗信息", "药物过敏", "frontpage.other_medical_info.allergy"),
    CoverageRequirement("其他住院医疗信息", "ABO/Rh 血型", "frontpage.other_medical_info.blood_type"),
    CoverageRequirement("其他住院医疗信息", "呼吸机使用时间", "frontpage.other_medical_info.ventilation"),
    CoverageRequirement("其他住院医疗信息", "ICU 信息", "frontpage.other_medical_info.icu"),
    CoverageRequirement("其他住院医疗信息", "颅脑损伤昏迷时间", "frontpage.other_medical_info.coma"),
    CoverageRequirement("人员信息", "主治医师", "frontpage.staff.attending_physician"),
    CoverageRequirement("人员信息", "责任护士", "frontpage.staff.responsible_nurse"),
    CoverageRequirement("费用信息", "住院总费用", "frontpage.costs.total_cost"),
    CoverageRequirement("医保结算清单", "结算清单草稿", "settlement"),
)


def normalize_report_scene(scene: Optional[str]) -> str:
    normalized = (scene or "nhc_frontpage").strip().lower()
    if normalized in {"frontpage", "nhc", "health"}:
        return "nhc_frontpage"
    if normalized in {"settlement", "insurance", "insurance_settlement"}:
        return "insurance_settlement"
    if normalized in {"combined", "all", "both"}:
        return "combined"
    if normalized not in REPORT_SCENES:
        raise FrontPageReportInputError(f"不支持的生成场景: {scene}")
    return normalized


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_is_present(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_is_present(item) for item in value)
    return True


def _get_path(data: Dict[str, Any], dotted_path: str) -> Any:
    value: Any = data
    for part in dotted_path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _candidate_items(value: Any) -> List[Dict[str, Any]]:
    items = value if isinstance(value, list) else []
    out: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            code = _safe_text(item.get("code"))
            name = _safe_text(item.get("name"))
        else:
            code = ""
            name = _safe_text(item)
        if code or name:
            out.append({"code": code or None, "name": name or None, "source": "legacy"})
    return out


def _condition_detail_map(details: Any) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    if not isinstance(details, list):
        return result
    for item in details:
        if not isinstance(item, dict):
            continue
        diagnosis = _safe_text(item.get("diagnosis"))
        if not diagnosis:
            continue
        compact = diagnosis.replace("主要诊断:", "").replace("其他诊断:", "").strip()
        result[compact] = item
    return result


def _diagnosis_item(
    *,
    diagnosis_type: str,
    name: str,
    code: Optional[str] = None,
    candidates: Optional[List[Dict[str, Any]]] = None,
    condition_detail: Optional[Dict[str, Any]] = None,
    fallback_condition: Optional[str] = None,
    outcome: Optional[str] = None,
) -> Dict[str, Any]:
    condition_code = _safe_text(
        (condition_detail or {}).get("admission_condition") or fallback_condition
    ) or None
    return {
        "diagnosis_type": diagnosis_type,
        "name": name,
        "code": code or None,
        "candidates": candidates or [],
        "confidence": None,
        "admission_condition": condition_code,
        "admission_condition_text": ADMISSION_CONDITION_TEXT.get(condition_code or ""),
        "admission_condition_reason": (condition_detail or {}).get("reasoning"),
        "outcome": outcome or None,
        "is_tcm": (
            "中医" in diagnosis_type
            or "证" in name
            or _safe_text(code).upper().startswith(("BNG", "ZZ"))
        ),
        "evidence": [],
    }


def augment_frontpage_for_report(frontpage: Dict[str, Any]) -> Dict[str, Any]:
    """在旧 FrontPageDraft 字段基础上补齐招标场景的结构化兼容字段。"""
    fp = dict(frontpage or {})
    diagnoses = dict(fp.get("diagnoses") or {})
    procedures = dict(fp.get("procedures") or {})
    other = dict(fp.get("other_medical_info") or {})

    details = _condition_detail_map(
        diagnoses.get("admission_condition_details")
        or diagnoses.get("_admission_condition_details")
    )
    fallback_condition = diagnoses.get("admission_condition")

    ed_texts = diagnoses.get("ed_diagnosis_texts") if isinstance(diagnoses.get("ed_diagnosis_texts"), list) else []
    ed_codes = diagnoses.get("ed_diagnosis_codes") if isinstance(diagnoses.get("ed_diagnosis_codes"), list) else []
    diagnoses["ed_diagnoses"] = [
        _diagnosis_item(
            diagnosis_type="门急诊诊断",
            name=_safe_text(name),
            code=_safe_text(ed_codes[idx]) if idx < len(ed_codes) else None,
        )
        for idx, name in enumerate(ed_texts)
        if _safe_text(name)
    ]

    main_name = _safe_text(diagnoses.get("discharge_main_diagnosis_text"))
    if main_name:
        main_candidates = _candidate_items(diagnoses.get("discharge_main_icd_suggestions"))
        diagnoses["discharge_main_diagnosis"] = _diagnosis_item(
            diagnosis_type="出院主要诊断",
            name=main_name,
            code=_safe_text(diagnoses.get("discharge_main_icd")) or None,
            candidates=main_candidates,
            condition_detail=details.get(main_name),
            fallback_condition=fallback_condition,
            outcome=_safe_text(diagnoses.get("discharge_main_outcome")) or None,
        )
    else:
        diagnoses["discharge_main_diagnosis"] = None

    other_texts = diagnoses.get("discharge_other_diagnoses_texts") if isinstance(diagnoses.get("discharge_other_diagnoses_texts"), list) else []
    other_codes = diagnoses.get("discharge_other_icds") if isinstance(diagnoses.get("discharge_other_icds"), list) else []
    other_outcomes = diagnoses.get("discharge_other_outcomes") if isinstance(diagnoses.get("discharge_other_outcomes"), list) else []
    other_suggestions = diagnoses.get("discharge_other_icd_suggestions") if isinstance(diagnoses.get("discharge_other_icd_suggestions"), list) else []
    structured_others = []
    for idx, raw_name in enumerate(other_texts):
        name = _safe_text(raw_name)
        if not name:
            continue
        suggestions = other_suggestions[idx] if idx < len(other_suggestions) else []
        structured_others.append(
            _diagnosis_item(
                diagnosis_type="出院其他诊断",
                name=name,
                code=_safe_text(other_codes[idx]) if idx < len(other_codes) else None,
                candidates=_candidate_items(suggestions),
                condition_detail=details.get(name),
                fallback_condition=None,
                outcome=_safe_text(other_outcomes[idx]) if idx < len(other_outcomes) else None,
            )
        )
    diagnoses["discharge_other_diagnoses"] = structured_others
    diagnoses["tcm_diagnoses"] = [
        item for item in [*diagnoses["ed_diagnoses"], *structured_others]
        if item.get("is_tcm")
    ]

    main_proc_name = _safe_text(procedures.get("main_procedure_text"))
    if main_proc_name:
        procedures["main_procedure"] = {
            "procedure_type": "主要手术及操作",
            "name": main_proc_name,
            "code": _safe_text(procedures.get("main_procedure_code")) or None,
            "candidates": _candidate_items(procedures.get("main_procedure_code_suggestions")),
            "confidence": None,
            "date": _safe_text(procedures.get("main_procedure_date")) or None,
            "level": _safe_text(procedures.get("main_procedure_level")) or None,
            "start_time": _safe_text(procedures.get("main_procedure_start_time")) or None,
            "end_time": _safe_text(procedures.get("main_procedure_end_time")) or None,
            "surgeon_name": _safe_text(procedures.get("surgeon_name")) or None,
            "surgeon_code": _safe_text(procedures.get("surgeon_code")) or None,
            "assistant1_name": _safe_text(procedures.get("assistant1_name")) or None,
            "assistant1_code": _safe_text(procedures.get("assistant1_code")) or None,
            "assistant2_name": _safe_text(procedures.get("assistant2_name")) or None,
            "assistant2_code": _safe_text(procedures.get("assistant2_code")) or None,
            "incision_grade": _safe_text(procedures.get("incision_grade")) or None,
            "incision_healing_grade": _safe_text(procedures.get("incision_healing_grade")) or None,
            "anesthesia_method": _safe_text(procedures.get("anesthesia_method")) or None,
            "anesthesia_grade": _safe_text(procedures.get("anesthesia_grade")) or None,
            "anesthetist_name": _safe_text(procedures.get("anesthetist_name")) or None,
            "anesthetist_code": _safe_text(procedures.get("anesthetist_code")) or None,
            "evidence": [],
        }
    else:
        procedures["main_procedure"] = None

    other_proc_texts = procedures.get("other_procedures_texts") if isinstance(procedures.get("other_procedures_texts"), list) else []
    other_proc_codes = procedures.get("other_procedure_codes") if isinstance(procedures.get("other_procedure_codes"), list) else []
    other_proc_objects = procedures.get("other_procedures") if isinstance(procedures.get("other_procedures"), list) else []
    structured_procs: List[Dict[str, Any]] = []
    for idx, item in enumerate(other_proc_objects):
        if isinstance(item, dict):
            name = _safe_text(item.get("text") or item.get("name"))
            code = _safe_text(item.get("code"))
            date = _safe_text(item.get("date"))
            level = _safe_text(item.get("level"))
        else:
            name = _safe_text(item)
            code = ""
            date = ""
            level = ""
        if not name:
            continue
        structured_procs.append({
            "procedure_type": "其他手术及操作",
            "name": name,
            "code": code or None,
            "date": date or None,
            "level": level or None,
            "evidence": [],
        })
    for idx, raw_name in enumerate(other_proc_texts):
        name = _safe_text(raw_name)
        if not name or any(existing.get("name") == name for existing in structured_procs):
            continue
        structured_procs.append({
            "procedure_type": "其他手术及操作",
            "name": name,
            "code": _safe_text(other_proc_codes[idx]) if idx < len(other_proc_codes) else None,
            "evidence": [],
        })
    procedures["other_procedures_structured"] = structured_procs

    other["pathology"] = {
        "text": _safe_text(other.get("pathology_text")) or None,
        "code": _safe_text(other.get("pathology_icd")) or None,
        "pathology_no": _safe_text(other.get("pathology_no")) or None,
        "candidates": _candidate_items(other.get("pathology_icd_suggestions")),
        "evidence": [],
    }
    other["injury_poison"] = {
        "flag": _safe_text(other.get("injury_poison_flag")) or None,
        "cause_text": _safe_text(other.get("injury_poison_cause_text")) or None,
        "cause_code": _safe_text(other.get("injury_poison_cause_icd")) or None,
        "candidates": _candidate_items(other.get("injury_poison_cause_suggestions")),
        "evidence": [],
    }
    other["allergy"] = {
        "flag": _safe_text(other.get("drug_allergy_flag")) or None,
        "flag_text": _safe_text(other.get("drug_allergy_flag_text")) or None,
        "drugs": other.get("drug_allergy_drugs") if isinstance(other.get("drug_allergy_drugs"), list) else [],
    }
    other["blood_type"] = {
        "abo": _safe_text(other.get("abo_blood_type")) or None,
        "rh": _safe_text(other.get("rh_blood_type")) or None,
        "rh_text": _safe_text(other.get("rh_blood_type_text")) or None,
    }
    other["ventilation"] = {"hours": other.get("ventilation_hours")}
    other["icu"] = {
        "type": _safe_text(other.get("icu_type")) or None,
        "enter_time": _safe_text(other.get("icu_enter_time")) or None,
        "leave_time": _safe_text(other.get("icu_leave_time")) or None,
        "transfer_status": _safe_text(other.get("icu_transfer_status")) or None,
    }
    other["coma"] = {
        "before_admission": other.get("coma_before_admission") or {
            "days": other.get("brain_injury_before_admission_days"),
            "hours": other.get("brain_injury_before_admission_hours"),
            "minutes": other.get("brain_injury_before_admission_minutes"),
        },
        "after_admission": other.get("coma_after_admission") or {
            "days": other.get("brain_injury_after_admission_days"),
            "hours": other.get("brain_injury_after_admission_hours"),
            "minutes": other.get("brain_injury_after_admission_minutes"),
        },
    }

    fp["diagnoses"] = diagnoses
    fp["procedures"] = procedures
    fp["other_medical_info"] = other
    return fp


def build_frontpage_coverage(
    *,
    scene: str,
    frontpage: Dict[str, Any],
    settlement: Optional[Dict[str, Any]],
    extra_warnings: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    payload = {"frontpage": frontpage, "settlement": settlement}
    fields: List[Dict[str, Any]] = []
    warnings = [item for item in list(extra_warnings or []) if item]
    present = 0
    partial = 0

    for requirement in COVERAGE_REQUIREMENTS:
        if requirement.path == "settlement" and scene == "nhc_frontpage":
            status = "partial"
            message = "当前场景不要求生成医保结算清单"
            partial += 1
        else:
            value = _get_path(payload, requirement.path)
            status = "present" if _is_present(value) else "missing"
            message = requirement.message if status == "missing" else ""
            if status == "present":
                present += 1
            else:
                warnings.append(f"{requirement.group}-{requirement.field}缺失")

        fields.append({
            "group": requirement.group,
            "field": requirement.field,
            "path": requirement.path,
            "status": status,
            "message": message,
        })

    total = len(fields)
    missing = len([item for item in fields if item["status"] == "missing"])
    text_fields = [item for item in fields if item["path"].startswith("frontpage.")]
    text_present = len([item for item in text_fields if item["status"] == "present"])
    text_missing = len([item for item in text_fields if item["status"] == "missing"])
    settlement_fields = [item for item in fields if item["path"].startswith("settlement")]
    settlement_present = len([item for item in settlement_fields if item["status"] == "present"])
    overall_status = "complete" if missing == 0 else "partial"
    return {
        "scene": scene,
        "status": overall_status,
        "total": total,
        "present": present,
        "partial": partial,
        "missing": missing,
        "text_extraction": {
            "total": len(text_fields),
            "present": text_present,
            "missing": text_missing,
            "rate": round(text_present / len(text_fields), 4) if text_fields else 0,
        },
        "settlement_from_frontpage": {
            "total": len(settlement_fields),
            "present": settlement_present,
            "missing": len(settlement_fields) - settlement_present,
            "generated": _is_present(settlement),
        },
        "fields": fields,
        "warnings": list(dict.fromkeys(warnings)),
    }


TEXT_SIGNAL_REQUIREMENTS = [
    ("费用信息", [r"总费用", r"自付费用", r"西药费", r"手术治疗费", r"实验室诊断费"], "frontpage.costs.total_cost"),
    ("ICU信息", [r"ICU", r"EICU", r"重症监护"], "frontpage.other_medical_info.icu"),
    ("呼吸机使用时间", [r"呼吸机", r"机械通气", r"辅助通气"], "frontpage.other_medical_info.ventilation.hours"),
    ("颅脑损伤昏迷时间", [r"昏迷", r"颅脑损伤"], "frontpage.other_medical_info.coma"),
    ("病理诊断", [r"病理诊断", r"病理号"], "frontpage.other_medical_info.pathology"),
    ("损伤中毒外部原因", [r"外伤中毒", r"损伤", r"中毒", r"外部原因", r"交通事故"], "frontpage.other_medical_info.injury_poison"),
    ("药物过敏", [r"药物过敏", r"过敏"], "frontpage.other_medical_info.allergy"),
    ("血型", [r"血型", r"ABO", r"Rh"], "frontpage.other_medical_info.blood_type"),
]


def _text_signal_warnings(medical_text: str, frontpage: Dict[str, Any]) -> List[str]:
    text = medical_text or ""
    payload = {"frontpage": frontpage}
    warnings: List[str] = []
    for label, patterns, path in TEXT_SIGNAL_REQUIREMENTS:
        if not any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
            continue
        if not _is_present(_get_path(payload, path)):
            warnings.append(f"病历文本出现{label}线索，但未抽取到 {path}")
    return warnings


class FrontPageReportGenerationService:
    def __init__(
        self,
        *,
        extraction_service: FrontPageExtractionService = default_frontpage_service,
        settlement_service: SettlementAssemblyService | None = None,
    ) -> None:
        self.extraction_service = extraction_service
        self.settlement_service = settlement_service or SettlementAssemblyService()

    async def build_medical_text(
        self,
        *,
        medical_text: Optional[str] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
        visit_id: Optional[str] = None,
    ) -> str:
        if medical_text and medical_text.strip():
            return medical_text.strip()

        visit_text = ""
        if visit_id:
            text = await self.extraction_service._get_llm_context_text(visit_id)
            if text and text.strip():
                visit_text = text.strip()
            elif not documents:
                raise FrontPageReportInputError(f"visit_id={visit_id} 缺少可用于生成的病历文书")

        if documents:
            parts = []
            if visit_text:
                parts.append(visit_text)
            for doc in documents:
                content = _safe_text(doc.get("content"))
                if not content:
                    continue
                parts.append(f"【{doc.get('type') or '未知文书'}】\n{content}")
            if parts:
                return "\n\n".join(parts)

        if visit_text:
            return visit_text

        raise FrontPageReportInputError("medical_text、documents、visit_id 至少需要提供一个")

    async def generate(
        self,
        *,
        scene: Optional[str],
        medical_text: Optional[str] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
        visit_id: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_scene = normalize_report_scene(scene)
        text = await self.build_medical_text(
            medical_text=medical_text,
            documents=documents,
            visit_id=visit_id,
        )
        draft: FrontPageDraft = await self.extraction_service.extract_from_text(
            text,
            context_strategy="full",
        )
        frontpage = augment_frontpage_for_report(draft.model_dump())

        settlement = None
        if normalized_scene in {"insurance_settlement", "combined"}:
            with Session(engine) as db:
                settlement = self.settlement_service.generate(
                    patient_id=patient_id or "",
                    visit_id=visit_id or "",
                    frontpage_draft=frontpage,
                    db=db if visit_id and patient_id else None,
                )

        warnings = []
        if not frontpage.get("diagnoses", {}).get("discharge_main_diagnosis"):
            warnings.append("未抽取到出院主要诊断，结果为 partial")
        if normalized_scene in {"insurance_settlement", "combined"} and not settlement:
            warnings.append("未生成医保结算清单")
        warnings.extend(_text_signal_warnings(text, frontpage))

        coverage = build_frontpage_coverage(
            scene=normalized_scene,
            frontpage=frontpage,
            settlement=settlement,
            extra_warnings=warnings,
        )
        return {
            "scene": normalized_scene,
            "frontpage": frontpage,
            "settlement": settlement,
            "coverage": coverage,
            "warnings": coverage.get("warnings") or warnings,
        }


default_frontpage_report_generation_service = FrontPageReportGenerationService()
