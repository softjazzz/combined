"""medical_records 域 - AI 首页历史快照服务。"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Callable

from sqlalchemy.orm import Session

from ...database.connection import engine
from ...database.models.cdm import (
    AIFrontpageCostSnapshot,
    AIFrontpageDiagnosisSnapshot,
    AIFrontpageSnapshot,
    AIFrontpageSurgerySnapshot,
    AiFrontpageDraft,
    FrontpageExtractionAudit,
)
from .errors import MedicalRecordsNotFoundError, MedicalRecordsValidationError



def _session_factory() -> Session:
    return Session(engine)



def _ensure_ai_frontpage_snapshot_tables() -> None:
    AIFrontpageSnapshot.__table__.create(bind=engine, checkfirst=True)
    AIFrontpageDiagnosisSnapshot.__table__.create(bind=engine, checkfirst=True)
    AIFrontpageSurgerySnapshot.__table__.create(bind=engine, checkfirst=True)
    AIFrontpageCostSnapshot.__table__.create(bind=engine, checkfirst=True)



def _parse_date(value: Any) -> date | None:
    if value in (None, ''):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d'):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None



def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace('T', ' ')
    for fmt in (
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d %H:%M',
        '%Y-%m-%d',
        '%Y/%m/%d',
    ):
        try:
            return datetime.strptime(normalized[:19], fmt)
        except ValueError:
            continue
    return None



def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None



def _diagnosis_rows_from_draft(draft: dict[str, Any]) -> list[dict[str, Any]]:
    diagnoses = draft.get('diagnoses') or {}
    rows: list[dict[str, Any]] = []
    main_name = _string(diagnoses.get('discharge_main_diagnosis_text'))
    main_code = _string(diagnoses.get('discharge_main_icd'))
    if main_name or main_code:
        rows.append(
            {
                'seq_no': 1,
                'diagnosis_type': '出院主要诊断',
                'diagnosis_no': '1',
                'diagnosis_name': main_name,
                'diagnosis_code': main_code,
                'admission_condition': _string(diagnoses.get('admission_condition')),
                'discharge_condition': _string(diagnoses.get('discharge_condition')),
                'pathology_id': _string((draft.get('other_medical_info') or {}).get('pathology_no')),
                'is_main': True,
            }
        )

    other_names = diagnoses.get('discharge_other_diagnoses_texts') or []
    other_codes = diagnoses.get('discharge_other_icds') or []
    max_len = max(len(other_names), len(other_codes))
    for idx in range(max_len):
        name = _string(other_names[idx]) if idx < len(other_names) else None
        code = _string(other_codes[idx]) if idx < len(other_codes) else None
        if not name and not code:
            continue
        rows.append(
            {
                'seq_no': idx + 2,
                'diagnosis_type': '出院其他诊断',
                'diagnosis_no': str(idx + 2),
                'diagnosis_name': name,
                'diagnosis_code': code,
                'admission_condition': None,
                'discharge_condition': None,
                'pathology_id': None,
                'is_main': False,
            }
        )
    return rows



def _surgery_rows_from_draft(draft: dict[str, Any]) -> list[dict[str, Any]]:
    procedures = draft.get('procedures') or {}
    rows: list[dict[str, Any]] = []
    main_name = _string(procedures.get('main_procedure_text'))
    main_code = _string(procedures.get('main_procedure_code'))
    if main_name or main_code:
        rows.append(
            {
                'seq_no': 1,
                'surgery_name': main_name,
                'surgery_code': main_code,
                'surgical_level': _string(procedures.get('main_procedure_level')),
                'surgery_begin_datetime': _parse_datetime(procedures.get('main_procedure_date')),
                'surgeon': _string(procedures.get('surgeon_name')),
                'first_assistant': _string(procedures.get('assistant1_name')),
                'second_assistant': _string(procedures.get('assistant2_name')),
                'anesthesia_method': _string(procedures.get('anesthesia_method')),
                'anesthesiologist': _string(procedures.get('anesthetist_name')),
                'surgial_incision_level': _string(procedures.get('incision_grade')),
                'surgical_incisionheal_level': _string(procedures.get('incision_healing_grade')),
                'is_main': True,
            }
        )

    others = procedures.get('other_procedures') or []
    if not others:
        other_names = procedures.get('other_procedure_texts') or []
        other_codes = procedures.get('other_procedure_codes') or []
        for idx in range(max(len(other_names), len(other_codes))):
            others.append(
                {
                    'text': other_names[idx] if idx < len(other_names) else None,
                    'code': other_codes[idx] if idx < len(other_codes) else None,
                }
            )
    for idx, item in enumerate(others, start=2):
        name = _string(item.get('text') or item.get('name')) if isinstance(item, dict) else _string(item)
        code = _string(item.get('code')) if isinstance(item, dict) else None
        if not name and not code:
            continue
        rows.append(
            {
                'seq_no': idx,
                'surgery_name': name,
                'surgery_code': code,
                'surgical_level': _string(item.get('level')) if isinstance(item, dict) else None,
                'surgery_begin_datetime': _parse_datetime(item.get('date')) if isinstance(item, dict) else None,
                'surgeon': _string(item.get('surgeon')) if isinstance(item, dict) else None,
                'first_assistant': _string(item.get('assistant1')) if isinstance(item, dict) else None,
                'second_assistant': _string(item.get('assistant2')) if isinstance(item, dict) else None,
                'anesthesia_method': _string(item.get('anesthesia_method')) if isinstance(item, dict) else None,
                'anesthesiologist': _string(item.get('anesthetist_name')) if isinstance(item, dict) else None,
                'surgial_incision_level': _string(item.get('incision_grade')) if isinstance(item, dict) else None,
                'surgical_incisionheal_level': _string(item.get('incision_healing_grade')) if isinstance(item, dict) else None,
                'is_main': False,
            }
        )
    return rows



def _cost_row_from_draft(draft: dict[str, Any]) -> dict[str, Any] | None:
    costs = draft.get('costs') or {}
    categories = costs.get('categories') or {}
    values = {
        'total_cost': _string(costs.get('total_cost')),
        'self_pay': _string(costs.get('self_paid')),
        'general_medical_service_fee': _string(categories.get('general_medical_service')),
        'general_treatment_fee': _string(categories.get('general_treatment')),
        'nursing_care_fee': _string(categories.get('nursing_care')),
        'other_service_fee': _string(categories.get('other_service')),
        'pathological_diagnostic_fee': _string(categories.get('pathological_diagnostic')),
        'laboratory_diagnostic_fee': _string(categories.get('laboratory_diagnostic')),
        'imaging_diagnostic_fee': _string(categories.get('imaging_diagnostic')),
        'clinical_diagnostic_fee': _string(categories.get('clinical_diagnostic')),
        'nonsurgical_treatment_fee': _string(categories.get('nonsurgical_treatment')),
        'clinical_physical_therapy_fee': _string(categories.get('clinical_physical_therapy')),
        'surgery_treatment_fee': _string(categories.get('surgery_treatment')),
        'anesthesia_fee': _string(categories.get('anesthesia_fee')),
        'surgery_fee': _string(categories.get('surgery_fee')),
        'rehabilitation_fee': _string(categories.get('rehabilitation_fee')),
        'western_medicine_fee': _string(categories.get('western_medicine')),
        'antibacterial_drug_fee': _string(categories.get('antibacterial_drug')),
        'chinese_patent_medcine_fee': _string(categories.get('chinese_patent_medicine')),
        'chinese_herbal_medicine_fee': _string(categories.get('chinese_herbal_medicine')),
        'blood_fee': _string(categories.get('blood_fee')),
        'treat_disposable_mat_fee': _string(categories.get('treat_disposable_mat')),
        'exam_disposable_mat_fee': _string(categories.get('exam_disposable_mat')),
        'surgery_disposable_mat_fee': _string(categories.get('surgery_disposable_mat')),
        'other_fee': _string(categories.get('other_fee')),
    }
    return values if any(values.values()) else None



def save_frontpage_snapshot(
    data: dict[str, Any],
    session_factory: Callable[[], Any] | None = None,
    ensure_tables: Callable[[], None] | None = None,
) -> dict[str, Any]:
    frontpage = data.get('frontpage') or data.get('draft') or data
    patient_id = _string(data.get('patient_id') or frontpage.get('patient_id'))
    visit_id = _string(data.get('visit_id') or frontpage.get('visit_id'))
    institute_id = _string(data.get('institute_id'))
    if not patient_id or not visit_id:
        raise MedicalRecordsValidationError('patient_id 和 visit_id 不能为空')
    if not isinstance(frontpage, dict):
        raise MedicalRecordsValidationError('frontpage 必须是有效对象')

    session_factory = session_factory or _session_factory
    ensure_tables = ensure_tables or _ensure_ai_frontpage_snapshot_tables
    snapshot_version = _string(data.get('snapshot_version')) or 'v1'
    status = _string(data.get('status')) or 'confirmed'
    generated_by = _string(data.get('generated_by'))
    confirmed_by = _string(data.get('confirmed_by'))

    basic_info = frontpage.get('basic_info') or {}
    hospitalization = frontpage.get('hospitalization') or {}
    other_medical_info = frontpage.get('other_medical_info') or {}
    staff = frontpage.get('staff') or {}

    ensure_tables()
    with session_factory() as session:
        draft = session.query(AiFrontpageDraft).filter_by(visit_id=visit_id).first()
        audit = (
            session.query(FrontpageExtractionAudit)
            .filter_by(visit_id=visit_id, frontpage_version='v1')
            .order_by(FrontpageExtractionAudit.updated_at.desc())
            .first()
        )
        existing = (
            session.query(AIFrontpageSnapshot)
            .filter_by(visit_id=visit_id, snapshot_version=snapshot_version)
            .first()
        )
        now = datetime.utcnow()
        snapshot_data = {
            'institute_id': institute_id or (draft.institute_id if draft else None),
            'patient_id': patient_id,
            'visit_id': visit_id,
            'snapshot_version': snapshot_version,
            'status': status,
            'draft_id': draft.id if draft else None,
            'audit_id': audit.id if audit else None,
            'generated_by': generated_by,
            'confirmed_by': confirmed_by,
            'generated_at': existing.generated_at if existing and existing.generated_at else now,
            'confirmed_at': now if status == 'confirmed' else None,
            'institute_code': _string(hospitalization.get('organization_code')),
            'institute_county_desc': _string(hospitalization.get('hospital_name')),
            'medical_payment_method': _string(hospitalization.get('payment_method_text')),
            'visit_cnt': _string(hospitalization.get('admission_times_in_hospital')),
            'name': _string(basic_info.get('patient_name')),
            'sex': _string(basic_info.get('gender') or basic_info.get('gender_text')),
            'age': _string(basic_info.get('age') or basic_info.get('age_years')),
            'age_year': _string(basic_info.get('age_years')),
            'id_card_no': _string(basic_info.get('id_number')),
            'birthday': _parse_date(basic_info.get('birth_date')),
            'nationality': _string(basic_info.get('nationality')),
            'ethnicity': _string(basic_info.get('ethnicity')),
            'marital_status': _string(basic_info.get('marital_status') or basic_info.get('marital_status_text')),
            'occupation_category': _string(basic_info.get('occupation')),
            'nativeplace': _string(basic_info.get('nativeplace')),
            'currentaddress': _string(basic_info.get('current_address')),
            'work_unit': _string(basic_info.get('work_unit')),
            'contact_name': _string(basic_info.get('contact_name')),
            'contact_relationship': _string(basic_info.get('contact_relation')),
            'contact_address': _string(basic_info.get('contact_address')),
            'contact_telephone': _string(basic_info.get('contact_phone')),
            'mr_no': _string(hospitalization.get('medical_record_no')),
            'admission_route': _string(hospitalization.get('admission_way_text')),
            'admission_datetime': _parse_datetime(hospitalization.get('admission_datetime')),
            'admission_dept_name': _string(hospitalization.get('admission_dept')),
            'admission_ward_name': _string(hospitalization.get('admission_ward')),
            'transfer_dept_name': _string(hospitalization.get('transfer_dept')),
            'discharge_datetime': _parse_datetime(hospitalization.get('discharge_datetime')),
            'discharge_dept_name': _string(hospitalization.get('discharge_dept')),
            'discharge_ward_name': _string(hospitalization.get('discharge_ward')),
            'hospital_duration': _string(hospitalization.get('actual_hospital_days')),
            'leaving_hospital_way': _string(hospitalization.get('leaving_hospital_way')),
            'rehospital_with_month': _string(hospitalization.get('rehospital_within_month')),
            'pathology_id': _string(other_medical_info.get('pathology_no')),
            'allergy_sign': _string(other_medical_info.get('drug_allergy_flag')),
            'allergy_history': _string(other_medical_info.get('drug_allergy_drugs')),
            'abo_blood_code': _string(other_medical_info.get('abo_blood_type')),
            'rh_blood_code': _string(other_medical_info.get('rh_blood_type') or other_medical_info.get('rh_blood_type_text')),
            'deptdirector_sign': _string(staff.get('dept_director')),
            'chief_physician_sign': _string(staff.get('chief_physician')),
            'attending_physician_sign': _string(staff.get('attending_physician')),
            'resident_physician_sign': _string(staff.get('resident_physician')),
            'responsible_nurse_sign': _string(staff.get('responsible_nurse')),
            'coder_sign': _string(staff.get('coder')),
            'medicalrecord_quality': _string(staff.get('medical_record_quality')),
        }

        if existing:
            snapshot = existing
            for key, value in snapshot_data.items():
                setattr(snapshot, key, value)
            snapshot.updated_at = now
            action = 'updated'
        else:
            snapshot = AIFrontpageSnapshot(id=str(uuid.uuid4()), created_at=now, updated_at=now, **snapshot_data)
            session.add(snapshot)
            session.flush()
            action = 'created'

        session.query(AIFrontpageDiagnosisSnapshot).filter_by(snapshot_id=snapshot.id).delete(synchronize_session=False)
        session.query(AIFrontpageSurgerySnapshot).filter_by(snapshot_id=snapshot.id).delete(synchronize_session=False)
        session.query(AIFrontpageCostSnapshot).filter_by(snapshot_id=snapshot.id).delete(synchronize_session=False)

        for row in _diagnosis_rows_from_draft(frontpage):
            session.add(
                AIFrontpageDiagnosisSnapshot(
                    id=str(uuid.uuid4()),
                    snapshot_id=snapshot.id,
                    institute_id=snapshot.institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    created_at=now,
                    updated_at=now,
                    **row,
                )
            )

        for row in _surgery_rows_from_draft(frontpage):
            session.add(
                AIFrontpageSurgerySnapshot(
                    id=str(uuid.uuid4()),
                    snapshot_id=snapshot.id,
                    institute_id=snapshot.institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    created_at=now,
                    updated_at=now,
                    **row,
                )
            )

        cost_row = _cost_row_from_draft(frontpage)
        if cost_row:
            session.add(
                AIFrontpageCostSnapshot(
                    id=str(uuid.uuid4()),
                    snapshot_id=snapshot.id,
                    institute_id=snapshot.institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    created_at=now,
                    updated_at=now,
                    **cost_row,
                )
            )
        session.commit()
        return {
            'action': action,
            'snapshot': {
                'id': snapshot.id,
                'visit_id': snapshot.visit_id,
                'patient_id': snapshot.patient_id,
                'snapshot_version': snapshot.snapshot_version,
                'status': snapshot.status,
            },
        }



def get_frontpage_snapshot(
    visit_id: str,
    snapshot_version: str | None = None,
    session_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    session_factory = session_factory or _session_factory
    with session_factory() as session:
        query = session.query(AIFrontpageSnapshot).filter_by(visit_id=visit_id)
        if snapshot_version:
            query = query.filter_by(snapshot_version=snapshot_version)
        else:
            query = query.order_by(AIFrontpageSnapshot.updated_at.desc(), AIFrontpageSnapshot.created_at.desc())
        snapshot = query.first()
        if not snapshot:
            raise MedicalRecordsNotFoundError('未找到 AI 首页历史快照')

        diagnoses = (
            session.query(AIFrontpageDiagnosisSnapshot)
            .filter_by(snapshot_id=snapshot.id)
            .order_by(AIFrontpageDiagnosisSnapshot.seq_no.asc())
            .all()
        )
        surgeries = (
            session.query(AIFrontpageSurgerySnapshot)
            .filter_by(snapshot_id=snapshot.id)
            .order_by(AIFrontpageSurgerySnapshot.seq_no.asc())
            .all()
        )
        cost = session.query(AIFrontpageCostSnapshot).filter_by(snapshot_id=snapshot.id).first()

    main_diag = next((item for item in diagnoses if item.is_main), diagnoses[0] if diagnoses else None)
    other_diags = [item for item in diagnoses if not item.is_main]
    main_proc = next((item for item in surgeries if item.is_main), surgeries[0] if surgeries else None)
    other_procs = [item for item in surgeries if not item.is_main]

    frontpage = {
        'basic_info': {
            'patient_name': snapshot.name,
            'gender': snapshot.sex,
            'gender_text': snapshot.sex,
            'birth_date': snapshot.birthday.isoformat() if snapshot.birthday else None,
            'age_years': snapshot.age_year or snapshot.age,
            'id_number': snapshot.id_card_no,
            'marital_status': snapshot.marital_status,
            'marital_status_text': snapshot.marital_status,
            'nationality': snapshot.nationality,
            'ethnicity': snapshot.ethnicity,
            'occupation': snapshot.occupation_category,
            'nativeplace': snapshot.nativeplace,
            'current_address': snapshot.currentaddress,
            'work_unit': snapshot.work_unit,
            'contact_name': snapshot.contact_name,
            'contact_relation': snapshot.contact_relationship,
            'contact_phone': snapshot.contact_telephone,
            'contact_address': snapshot.contact_address,
        },
        'hospitalization': {
            'hospital_name': snapshot.institute_county_desc,
            'organization_code': snapshot.institute_code,
            'medical_record_no': snapshot.mr_no,
            'admission_times_in_hospital': snapshot.visit_cnt,
            'payment_method_text': snapshot.medical_payment_method,
            'admission_way_text': snapshot.admission_route,
            'admission_dept': snapshot.admission_dept_name,
            'discharge_dept': snapshot.discharge_dept_name,
            'admission_ward': snapshot.admission_ward_name,
            'discharge_ward': snapshot.discharge_ward_name,
            'transfer_dept': snapshot.transfer_dept_name,
            'admission_datetime': snapshot.admission_datetime.isoformat(sep=' ') if snapshot.admission_datetime else None,
            'discharge_datetime': snapshot.discharge_datetime.isoformat(sep=' ') if snapshot.discharge_datetime else None,
            'actual_hospital_days': snapshot.hospital_duration,
            'leaving_hospital_way': snapshot.leaving_hospital_way,
            'rehospital_within_month': snapshot.rehospital_with_month,
        },
        'diagnoses': {
            'discharge_main_diagnosis_text': main_diag.diagnosis_name if main_diag else None,
            'discharge_main_icd': main_diag.diagnosis_code if main_diag else None,
            'admission_condition': main_diag.admission_condition if main_diag else None,
            'discharge_condition': main_diag.discharge_condition if main_diag else None,
            'discharge_other_diagnoses_texts': [item.diagnosis_name for item in other_diags if item.diagnosis_name],
            'discharge_other_icds': [item.diagnosis_code for item in other_diags if item.diagnosis_code],
        },
        'procedures': {
            'main_procedure_text': main_proc.surgery_name if main_proc else None,
            'main_procedure_code': main_proc.surgery_code if main_proc else None,
            'main_procedure_date': main_proc.surgery_begin_datetime.isoformat(sep=' ') if main_proc and main_proc.surgery_begin_datetime else None,
            'main_procedure_level': main_proc.surgical_level if main_proc else None,
            'surgeon_name': main_proc.surgeon if main_proc else None,
            'assistant1_name': main_proc.first_assistant if main_proc else None,
            'assistant2_name': main_proc.second_assistant if main_proc else None,
            'anesthesia_method': main_proc.anesthesia_method if main_proc else None,
            'anesthetist_name': main_proc.anesthesiologist if main_proc else None,
            'incision_grade': main_proc.surgial_incision_level if main_proc else None,
            'incision_healing_grade': main_proc.surgical_incisionheal_level if main_proc else None,
            'other_procedures': [
                {
                    'text': item.surgery_name,
                    'code': item.surgery_code,
                    'date': item.surgery_begin_datetime.isoformat(sep=' ') if item.surgery_begin_datetime else None,
                }
                for item in other_procs
            ],
            'other_procedure_texts': [item.surgery_name for item in other_procs if item.surgery_name],
            'other_procedure_codes': [item.surgery_code for item in other_procs if item.surgery_code],
        },
        'other_medical_info': {
            'pathology_no': snapshot.pathology_id,
            'drug_allergy_flag': snapshot.allergy_sign,
            'drug_allergy_drugs': snapshot.allergy_history,
            'abo_blood_type': snapshot.abo_blood_code,
            'rh_blood_type': snapshot.rh_blood_code,
            'rh_blood_type_text': snapshot.rh_blood_code,
        },
        'staff': {
            'dept_director': snapshot.deptdirector_sign,
            'chief_physician': snapshot.chief_physician_sign,
            'attending_physician': snapshot.attending_physician_sign,
            'resident_physician': snapshot.resident_physician_sign,
            'responsible_nurse': snapshot.responsible_nurse_sign,
            'coder': snapshot.coder_sign,
            'medical_record_quality': snapshot.medicalrecord_quality,
        },
        'costs': {
            'total_cost': cost.total_cost if cost else None,
            'self_paid': cost.self_pay if cost else None,
            'categories': {
                'general_medical_service': cost.general_medical_service_fee if cost else None,
                'general_treatment': cost.general_treatment_fee if cost else None,
                'nursing_care': cost.nursing_care_fee if cost else None,
                'other_service': cost.other_service_fee if cost else None,
                'pathological_diagnostic': cost.pathological_diagnostic_fee if cost else None,
                'laboratory_diagnostic': cost.laboratory_diagnostic_fee if cost else None,
                'imaging_diagnostic': cost.imaging_diagnostic_fee if cost else None,
                'clinical_diagnostic': cost.clinical_diagnostic_fee if cost else None,
                'nonsurgical_treatment': cost.nonsurgical_treatment_fee if cost else None,
                'clinical_physical_therapy': cost.clinical_physical_therapy_fee if cost else None,
                'surgery_treatment': cost.surgery_treatment_fee if cost else None,
                'anesthesia_fee': cost.anesthesia_fee if cost else None,
                'surgery_fee': cost.surgery_fee if cost else None,
                'rehabilitation_fee': cost.rehabilitation_fee if cost else None,
                'western_medicine': cost.western_medicine_fee if cost else None,
                'antibacterial_drug': cost.antibacterial_drug_fee if cost else None,
                'chinese_patent_medicine': cost.chinese_patent_medcine_fee if cost else None,
                'chinese_herbal_medicine': cost.chinese_herbal_medicine_fee if cost else None,
                'blood_fee': cost.blood_fee if cost else None,
                'treat_disposable_mat': cost.treat_disposable_mat_fee if cost else None,
                'exam_disposable_mat': cost.exam_disposable_mat_fee if cost else None,
                'surgery_disposable_mat': cost.surgery_disposable_mat_fee if cost else None,
                'other_fee': cost.other_fee if cost else None,
            },
        },
        'snapshot_meta': {
            'snapshot_id': snapshot.id,
            'snapshot_version': snapshot.snapshot_version,
            'status': snapshot.status,
            'generated_at': snapshot.generated_at.isoformat() if snapshot.generated_at else None,
            'confirmed_at': snapshot.confirmed_at.isoformat() if snapshot.confirmed_at else None,
        },
    }
    return {
        'visit_id': snapshot.visit_id,
        'patient_id': snapshot.patient_id,
        'snapshot_version': snapshot.snapshot_version,
        'status': snapshot.status,
        'frontpage': frontpage,
    }
