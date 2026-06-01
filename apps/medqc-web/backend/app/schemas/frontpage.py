from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_string_list(value: Any, allow_none: bool = False) -> Optional[List[str]]:
    if value is None:
        return None if allow_none else []
    items = value if isinstance(value, list) else [value]
    out: List[str] = []
    for item in items:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            out.append(text)
    if allow_none and not out:
        return None
    return out


class FrontPageBasicInfo(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    patient_name: Optional[str] = None
    gender: Optional[str] = None
    gender_text: Optional[str] = None
    birth_date: Optional[str] = None
    age_years: Optional[int] = None
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None
    marital_status: Optional[str] = None
    marital_status_text: Optional[str] = None
    id_number: Optional[str] = None
    occupation: Optional[str] = None
    birthplace: Optional[str] = None
    nativeplace: Optional[str] = None
    current_address: Optional[str] = None
    current_address_phone: Optional[str] = None
    current_address_zip: Optional[str] = None
    household_address: Optional[str] = None
    household_address_zip: Optional[str] = None
    work_unit: Optional[str] = None
    work_unit_address: Optional[str] = None
    work_unit_phone: Optional[str] = None
    work_unit_zip: Optional[str] = None
    contact_name: Optional[str] = None
    contact_relation: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_address: Optional[str] = None

    @field_validator("gender", "marital_status", mode="before")
    @classmethod
    def coerce_code_to_str(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, (int, float)):
            return str(int(value))
        return value


class FrontPageHospitalization(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    hospital_name: Optional[str] = None
    organization_code: Optional[str] = None
    admission_times_in_hospital: Optional[int] = None
    medical_record_no: Optional[str] = None
    payment_method: Optional[str] = None
    payment_method_text: Optional[str] = None
    admission_way: Optional[str] = None
    admission_way_text: Optional[str] = None
    admission_dept: Optional[str] = None
    admission_ward: Optional[str] = None
    admission_datetime: Optional[str] = None
    discharge_dept: Optional[str] = None
    discharge_ward: Optional[str] = None
    discharge_datetime: Optional[str] = None
    actual_hospital_days: Optional[int] = None
    leaving_hospital_way: Optional[str] = None
    rehospital_within_month: Optional[str] = None
    rehospital_purpose: Optional[str] = None
    inpat_type: Optional[str] = None
    therapy_type: Optional[str] = None
    receiving_institution: Optional[str] = None


class FrontPageDiagnoses(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    ed_diagnosis_texts: List[str] = Field(default_factory=list)
    discharge_main_diagnosis_text: Optional[str] = None
    discharge_other_diagnoses_texts: List[str] = Field(default_factory=list)

    ed_diagnosis_codes: Optional[List[str]] = None
    discharge_main_icd: Optional[str] = None
    discharge_other_icds: Optional[List[str]] = None

    # M2 semantic fallback candidate fields (for frontend display)
    discharge_main_icd_suggestions: Optional[List[Dict[str, Any]]] = None
    discharge_other_icd_suggestions: Optional[List[Dict[str, Any]]] = None

    # 招标场景结构化扩展：保留旧字段，同时提供逐条诊断承载编码、候选、入院病情与证据。
    ed_diagnoses: List[FrontPageDiagnosisItem] = Field(default_factory=list)
    discharge_main_diagnosis: Optional[FrontPageDiagnosisItem] = None
    discharge_other_diagnoses: List[FrontPageDiagnosisItem] = Field(default_factory=list)
    tcm_diagnoses: List[FrontPageDiagnosisItem] = Field(default_factory=list)
    admission_condition_details: List[Dict[str, Any]] = Field(default_factory=list)

    admission_condition: Optional[str] = None
    discharge_main_outcome: Optional[str] = None
    discharge_other_outcomes: Optional[List[str]] = None

    @field_validator("admission_condition", mode="before")
    @classmethod
    def coerce_code_to_str(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, (int, float)):
            return str(int(value))
        return value

    @field_validator("ed_diagnosis_texts", "discharge_other_diagnoses_texts", mode="before")
    @classmethod
    def normalize_required_list_fields(cls, value: Any) -> List[str]:
        return _normalize_string_list(value, allow_none=False) or []

    @field_validator("ed_diagnosis_codes", "discharge_other_icds", "discharge_other_outcomes", mode="before")
    @classmethod
    def normalize_optional_list_fields(cls, value: Any) -> Optional[List[str]]:
        return _normalize_string_list(value, allow_none=True)


class FrontPageProcedures(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    main_procedure_text: Optional[str] = None
    main_procedure_date: Optional[str] = None
    main_procedure_level: Optional[str] = None
    main_procedure_start_time: Optional[str] = None
    main_procedure_end_time: Optional[str] = None
    incision_grade: Optional[str] = None
    anesthesia_grade: Optional[str] = None
    is_main_surgery: Optional[str] = None
    unplanned_reoperation: Optional[str] = None
    surgeon_name: Optional[str] = None
    surgeon_code: Optional[str] = None
    assistant1_name: Optional[str] = None
    assistant1_code: Optional[str] = None
    assistant2_name: Optional[str] = None
    assistant2_code: Optional[str] = None
    anesthesia_method: Optional[str] = None
    anesthetist_name: Optional[str] = None
    anesthetist_code: Optional[str] = None
    incision_healing_grade: Optional[str] = None
    other_procedures: Optional[List[Dict[str, str]]] = None

    main_procedure_code: Optional[str] = None
    main_procedure: Optional[FrontPageProcedureItem] = None
    other_procedures_structured: List[FrontPageProcedureItem] = Field(default_factory=list)


class FrontPageOtherMedicalInfo(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    pathology_text: Optional[str] = None
    pathology_icd: Optional[str] = None
    pathology_no: Optional[str] = None

    drug_allergy_flag: Optional[str] = None
    drug_allergy_flag_text: Optional[str] = None
    drug_allergy_drugs: List[str] = Field(default_factory=list)

    abo_blood_type: Optional[str] = None
    rh_blood_type: Optional[str] = None
    rh_blood_type_text: Optional[str] = None

    ventilation_hours: Optional[float] = None

    icu_type: Optional[str] = None
    icu_enter_time: Optional[str] = None
    icu_leave_time: Optional[str] = None
    icu_transfer_status: Optional[str] = None

    injury_poison_flag: Optional[str] = None
    injury_poison_cause_text: Optional[str] = None
    injury_poison_cause_icd: Optional[str] = None
    injury_poison: Optional[FrontPageInjuryPoisonInfo] = None
    pathology: Optional[FrontPagePathologyInfo] = None
    allergy: Optional[Dict[str, Any]] = None
    blood_type: Optional[Dict[str, Any]] = None
    ventilation: Optional[Dict[str, Any]] = None
    icu: Optional[Dict[str, Any]] = None
    coma: Optional[Dict[str, Any]] = None

    brain_injury_coma_in: Optional[Dict[str, Any]] = None
    coma_before_admission: Optional[Dict[str, Any]] = None
    coma_after_admission: Optional[Dict[str, Any]] = None
    # 兼容 HIS 侧扁平字段
    brain_injury_before_admission_days: Optional[int] = None
    brain_injury_before_admission_hours: Optional[int] = None
    brain_injury_before_admission_minutes: Optional[int] = None
    brain_injury_after_admission_days: Optional[int] = None
    brain_injury_after_admission_hours: Optional[int] = None
    brain_injury_after_admission_minutes: Optional[int] = None

    @field_validator("drug_allergy_flag", "rh_blood_type", "injury_poison_flag", mode="before")
    @classmethod
    def coerce_code_to_str(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, (int, float)):
            return str(int(value))
        return value


class FrontPageStaff(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    dept_director: Optional[str] = None
    chief_physician: Optional[str] = None
    attending_physician: Optional[str] = None
    resident_physician: Optional[str] = None
    responsible_nurse: Optional[str] = None
    coder: Optional[str] = None
    qc_physician: Optional[str] = None
    qc_nurse: Optional[str] = None
    qc_date: Optional[str] = None
    medical_record_quality: Optional[str] = None


class FrontPageCosts(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    total_cost: Optional[float] = None
    self_paid: Optional[float] = None
    categories: Dict[str, float] = Field(default_factory=dict)

    @field_validator("categories", mode="before")
    @classmethod
    def normalize_categories(cls, value: Any) -> Dict[str, float]:
        if value is None or not isinstance(value, dict):
            return {}
        normalized: Dict[str, float] = {}
        for key, raw in value.items():
            if raw is None:
                continue
            if isinstance(raw, (int, float)):
                normalized[str(key)] = float(raw)
                continue
            text = str(raw).strip().replace(",", "")
            if not text:
                continue
            try:
                normalized[str(key)] = float(text)
            except Exception:
                continue
        return normalized


class FrontPageFieldEvidence(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    source_document: Optional[str] = None
    source_text: Optional[str] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None


class FrontPageCodingCandidate(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    code: Optional[str] = None
    name: Optional[str] = None
    score: Optional[float] = None
    source: Optional[str] = None


class FrontPageDiagnosisItem(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    diagnosis_type: Optional[str] = None
    name: Optional[str] = None
    code: Optional[str] = None
    candidates: List[FrontPageCodingCandidate] = Field(default_factory=list)
    confidence: Optional[float] = None
    admission_condition: Optional[str] = None
    admission_condition_text: Optional[str] = None
    admission_condition_reason: Optional[str] = None
    outcome: Optional[str] = None
    is_tcm: bool = False
    evidence: List[FrontPageFieldEvidence] = Field(default_factory=list)

    @field_validator("admission_condition", mode="before")
    @classmethod
    def coerce_admission_condition_to_str(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, (int, float)):
            return str(int(value))
        return value


class FrontPageProcedureItem(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    procedure_type: Optional[str] = None
    name: Optional[str] = None
    code: Optional[str] = None
    candidates: List[FrontPageCodingCandidate] = Field(default_factory=list)
    confidence: Optional[float] = None
    date: Optional[str] = None
    level: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    surgeon_name: Optional[str] = None
    surgeon_code: Optional[str] = None
    assistant1_name: Optional[str] = None
    assistant1_code: Optional[str] = None
    assistant2_name: Optional[str] = None
    assistant2_code: Optional[str] = None
    incision_grade: Optional[str] = None
    incision_healing_grade: Optional[str] = None
    anesthesia_method: Optional[str] = None
    anesthesia_grade: Optional[str] = None
    anesthetist_name: Optional[str] = None
    anesthetist_code: Optional[str] = None
    evidence: List[FrontPageFieldEvidence] = Field(default_factory=list)


class FrontPagePathologyInfo(BaseModel):
    text: Optional[str] = None
    code: Optional[str] = None
    pathology_no: Optional[str] = None
    candidates: List[FrontPageCodingCandidate] = Field(default_factory=list)
    confidence: Optional[float] = None
    evidence: List[FrontPageFieldEvidence] = Field(default_factory=list)


class FrontPageInjuryPoisonInfo(BaseModel):
    flag: Optional[str] = None
    cause_text: Optional[str] = None
    cause_code: Optional[str] = None
    candidates: List[FrontPageCodingCandidate] = Field(default_factory=list)
    confidence: Optional[float] = None
    evidence: List[FrontPageFieldEvidence] = Field(default_factory=list)


class FrontPageCoverageField(BaseModel):
    group: str
    field: str
    path: str
    status: str
    message: Optional[str] = None


class FrontPageCoverageReport(BaseModel):
    scene: str
    status: str
    total: int
    present: int
    partial: int = 0
    missing: int
    fields: List[FrontPageCoverageField] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class FrontPageDraft(BaseModel):
    basic_info: FrontPageBasicInfo
    hospitalization: FrontPageHospitalization
    diagnoses: FrontPageDiagnoses
    procedures: FrontPageProcedures
    other_medical_info: FrontPageOtherMedicalInfo
    staff: FrontPageStaff
    costs: FrontPageCosts
    evidence: Dict[str, Any] = Field(default_factory=dict)
    confidence: Dict[str, Any] = Field(default_factory=dict)


class FrontPageReportDraft(BaseModel):
    scene: str
    frontpage: FrontPageDraft
    settlement: Optional[Dict[str, Any]] = None
    coverage: FrontPageCoverageReport
    warnings: List[str] = Field(default_factory=list)
