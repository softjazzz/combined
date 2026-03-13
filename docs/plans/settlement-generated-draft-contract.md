# Generated Settlement Draft Contract (v1)

## Source Markers
- `data_source`: `"generated_from_frontpage"` — indicates data assembled from LLM extraction + CDM SQL
- `is_draft`: `true` — indicates draft status, not from settlement table

## Canonical Output Key Names

All output keys MUST match `SettlementSheet.vue` `v()` field names exactly.

### Naming Fixes Applied
| Location | Wrong Key | Correct Key |
|---|---|---|
| `settlement_formal_qc.py` L373 | `treatment_type` | `therapy_type` |

### Coma Fields (Flat Keys)
Settlement output uses flat CDM column names:
- `coma_timebefadm_d`, `coma_timebefadm_h`, `coma_timebefadm_min`
- `coma_timeaftadm_d`, `coma_timeaftadm_h`, `coma_timeaftadm_min`

FrontPageDraft uses nested `brain_injury_coma_in` dict:
- `{"before": {"days": N, "hours": N, "minutes": N}, "after": {...}}`

Assembly service must flatten nested → flat keys.

### Other Key Mappings
| FrontPageDraft Path | Settlement Output Key |
|---|---|
| `hospitalization.receiving_institution` | `receiving_institution_name` |
| `hospitalization.therapy_type` | `therapy_type` |
| `hospitalization.inpat_type` | `inpat_type` |
| `basic_info.patient_name` | `patient_name` |
| `basic_info.birth_date` | `patient_birthday` |
| `basic_info.age_years` | `patient_age` |
| `basic_info.id_number` | `patient_id_card` |
| `basic_info.ethnicity` | `patient_ethnicity` |
| `basic_info.nationality` | `nationality` |
| `hospitalization.admission_datetime` | `admission_datetime` |
| `hospitalization.discharge_datetime` | `discharge_datetime` |
| `hospitalization.admission_dept` | `admission_dept_name` |
| `hospitalization.discharge_dept` | `discharge_dept_name` |
| `hospitalization.actual_hospital_days` | `hospital_duration` |
| `hospitalization.admission_way_text` | `admission_route` |
| `hospitalization.leaving_hospital_way` | `leaving_hospital_way` |
| `hospitalization.rehospital_within_month` | `rehospital_with_month` |
| `hospitalization.rehospital_purpose` | `rehospital_with_month_purpose` |
| `hospitalization.medical_record_no` | `mr_no` |
| `hospitalization.hospital_name` | `designated_medical_institution` |
| `hospitalization.organization_code` | `institution_code` |
| `hospitalization.payment_method_text` | `patient_insurance_type` |
| `staff.attending_physician` | `attending_physician` |
| `staff.responsible_nurse` | `responsible_nurse` |
| `other_medical_info.ventilation_hours` | `ventilator_usetime` |
