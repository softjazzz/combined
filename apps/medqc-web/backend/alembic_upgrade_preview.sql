BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 20260315_000001

CREATE TABLE patient_information (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    birthday DATE, 
    id_card_type VARCHAR(100), 
    id_card_no VARCHAR(100), 
    ethnicity VARCHAR(100), 
    nationality VARCHAR(100), 
    marital_status VARCHAR(100), 
    contact_number VARCHAR(100), 
    occupation_category VARCHAR(100), 
    work_unit VARCHAR(100), 
    nativeplace TEXT, 
    birthplace TEXT, 
    currentaddress TEXT, 
    workplace TEXT, 
    contact_name VARCHAR(100), 
    contact_relationship VARCHAR(100), 
    contact_address VARCHAR(100), 
    contact_telephone VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id)
);

CREATE INDEX ix_patient_information_id_card_no ON patient_information (id_card_no);
CREATE TABLE inpat_registration (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    visit_cnt VARCHAR(100), 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    birthday DATE, 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    id_card_type VARCHAR(100), 
    id_card_no VARCHAR(100), 
    charge_type VARCHAR(100), 
    insurance_type VARCHAR(100), 
    insurance_no VARCHAR(100), 
    admission_dept_name VARCHAR(100), 
    admission_reason VARCHAR(100), 
    discharge_dept_name VARCHAR(100), 
    admission_datetime TIMESTAMP WITHOUT TIME ZONE, 
    discharge_datetime TIMESTAMP WITHOUT TIME ZONE, 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id)
);

CREATE INDEX ix_inpat_registration_mr_no ON inpat_registration (mr_no);

CREATE INDEX ix_inpat_registration_admission_datetime ON inpat_registration (admission_datetime);

CREATE INDEX ix_inpat_registration_inpat_no ON inpat_registration (inpat_no);

CREATE INDEX ix_inpat_registration_discharge_datetime ON inpat_registration (discharge_datetime);
CREATE TABLE mr (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    document_id VARCHAR(100), 
    institute_code VARCHAR(100), 
    institute_county_desc VARCHAR(100), 
    medical_payment_method VARCHAR(100), 
    insurance_type VARCHAR(100), 
    insurance_no VARCHAR(100), 
    visit_cnt VARCHAR(100), 
    id_card_type VARCHAR(100), 
    id_card_no VARCHAR(100), 
    birthday DATE, 
    nationality VARCHAR(100), 
    ethnicity VARCHAR(100), 
    marital_status VARCHAR(100), 
    occupation_category VARCHAR(100), 
    nativeplace TEXT, 
    currentaddress TEXT, 
    contact_number VARCHAR(100), 
    contact_name VARCHAR(100), 
    contact_relationship VARCHAR(100), 
    contact_address VARCHAR(100), 
    contact_telephone VARCHAR(100), 
    work_unit VARCHAR(100), 
    admission_route VARCHAR(100), 
    admission_datetime TIMESTAMP WITHOUT TIME ZONE, 
    admission_condition VARCHAR(100), 
    admission_dept_name VARCHAR(100), 
    admission_ward_name VARCHAR(100), 
    diagnosis_date DATE, 
    transfer_dept_name VARCHAR(100), 
    discharge_datetime TIMESTAMP WITHOUT TIME ZONE, 
    discharge_dept_name VARCHAR(100), 
    discharge_ward_name VARCHAR(100), 
    hospital_duration VARCHAR(100), 
    pathology_id VARCHAR(100), 
    allergy_sign VARCHAR(100), 
    allergy_history VARCHAR(100), 
    abo_blood_code VARCHAR(100), 
    rh_blood_code VARCHAR(100), 
    death_autopsy_sign VARCHAR(100), 
    deptdirector_sign VARCHAR(100), 
    chief_physician_sign VARCHAR(100), 
    attending_physician_sign VARCHAR(100), 
    resident_physician_sign VARCHAR(100), 
    responsible_nurse_sign VARCHAR(100), 
    coder_sign VARCHAR(100), 
    "QC_physician_sign" VARCHAR(100), 
    "QC_nurse_sign" VARCHAR(100), 
    "QC_date" DATE, 
    medicalrecord_quality VARCHAR(100), 
    leaving_hospital_way VARCHAR(100), 
    planned_transder_to VARCHAR(100), 
    rehospital_with_month VARCHAR(100), 
    rehospital_with_month_purpose VARCHAR(100), 
    rbc VARCHAR(100), 
    platet_volume VARCHAR(100), 
    plasma_volume VARCHAR(100), 
    whole_blood_volume VARCHAR(100), 
    autoblood_trans VARCHAR(100), 
    clinical_pathway VARCHAR(100), 
    archive_sign VARCHAR(100), 
    mr_datetime TIMESTAMP WITHOUT TIME ZONE, 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id)
);

CREATE INDEX ix_mr_discharge ON mr (discharge_datetime);

CREATE INDEX ix_mr_dept ON mr (discharge_dept_name);

CREATE INDEX ix_mr_admission ON mr (admission_datetime);
CREATE TABLE mr_surgery (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    document_id VARCHAR(100), 
    surgery_id VARCHAR(100) NOT NULL, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    surgery_name VARCHAR(100), 
    surgery_code VARCHAR(100), 
    surgical_level VARCHAR(100), 
    surgial_incision_level VARCHAR(100), 
    surgical_incisionheal_level VARCHAR(100), 
    anesthesia_method VARCHAR(100), 
    anesthesia_level VARCHAR(100), 
    surgery_begin_datetime TIMESTAMP WITHOUT TIME ZONE, 
    surgery_end_datetime TIMESTAMP WITHOUT TIME ZONE, 
    surgery_duration VARCHAR(100), 
    surgeon VARCHAR(100), 
    surgeon_physician_code VARCHAR(100), 
    first_assistant VARCHAR(100), 
    second_assistant VARCHAR(100), 
    anesthesiologist VARCHAR(100), 
    anesthesiologist_code VARCHAR(100), 
    main_surgery_sign VARCHAR(100), 
    unplanned_reoperation VARCHAR(100), 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, surgery_id)
);

CREATE INDEX ix_mr_surgery_surgery_code ON mr_surgery (surgery_code);
CREATE TABLE mr_cost (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    document_id VARCHAR(100), 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    total_cost VARCHAR(100), 
    self_pay VARCHAR(100), 
    general_medical_service_fee VARCHAR(100), 
    general_treatment_fee VARCHAR(100), 
    nursing_care_fee VARCHAR(100), 
    other_service_fee VARCHAR(100), 
    pathological_diagnostic_fee VARCHAR(100), 
    laboratory_diagnostic_fee VARCHAR(100), 
    imaging_diagnostic_fee VARCHAR(100), 
    clinical_diagnostic_fee VARCHAR(100), 
    nonsurgical_treatment_fee VARCHAR(100), 
    clinical_physical_therapy_fee VARCHAR(100), 
    surgery_treatment_fee VARCHAR(100), 
    anesthesia_fee VARCHAR(100), 
    surgery_fee VARCHAR(100), 
    rehabilitation_fee VARCHAR(100), 
    western_medicine_fee VARCHAR(100), 
    antibacterial_drug_fee VARCHAR(100), 
    chinese_patent_medcine_fee VARCHAR(100), 
    chinese_herbal_medicine_fee VARCHAR(100), 
    blood_fee VARCHAR(100), 
    treat_disposable_mat_fee VARCHAR(100), 
    exam_disposable_mat_fee VARCHAR(100), 
    surgery_disposable_mat_fee VARCHAR(100), 
    other_fee VARCHAR(100), 
    settle_datetime TIMESTAMP WITHOUT TIME ZONE, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id)
);
CREATE TABLE diagnosis (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    document_id VARCHAR(100), 
    diagnosis_id VARCHAR(100) NOT NULL, 
    inpat_no VARCHAR(100), 
    dept_name VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    diagnosis_type VARCHAR(100), 
    diagnosis_no VARCHAR(100), 
    diagnosis_name VARCHAR(100), 
    diagnosis_code VARCHAR(100), 
    pathology_id VARCHAR(100), 
    admission_condition VARCHAR(100), 
    discharge_condition VARCHAR(100), 
    diagnosis_source VARCHAR(100), 
    diagnosis_datetime TIMESTAMP WITHOUT TIME ZONE, 
    diagnosis_updatetime TIMESTAMP WITHOUT TIME ZONE, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, diagnosis_id)
);

CREATE INDEX ix_diag_type ON diagnosis (diagnosis_type);

CREATE INDEX ix_diag_visit ON diagnosis (institute_id, patient_id, visit_id);

CREATE INDEX ix_diagnosis_diagnosis_type ON diagnosis (diagnosis_type);

CREATE INDEX ix_diagnosis_diagnosis_code ON diagnosis (diagnosis_code);

CREATE INDEX ix_diag_code ON diagnosis (diagnosis_code);
CREATE TABLE admission_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    admission_datetime TIMESTAMP WITHOUT TIME ZONE, 
    admission_route VARCHAR(100), 
    dept_name VARCHAR(100), 
    ward_name VARCHAR(100), 
    ward_no VARCHAR(100), 
    bed_no VARCHAR(100), 
    admission_reason VARCHAR(100), 
    chief_complaint TEXT, 
    history_of_present_illness TEXT, 
    past_history TEXT, 
    allergy_history TEXT, 
    personal_history TEXT, 
    family_history TEXT, 
    checkup TEXT, 
    checkup_temperature VARCHAR(100), 
    checkup_heartrate VARCHAR(100), 
    checkup_respiratoryrate VARCHAR(100), 
    checkup_systolicpressure VARCHAR(100), 
    checkup_diastolicpressure VARCHAR(100), 
    checkup_height VARCHAR(100), 
    checkup_weight VARCHAR(100), 
    assist_exam TEXT, 
    record_content TEXT, 
    resident_physician_sign VARCHAR(100), 
    attending_physician_sign VARCHAR(100), 
    chief_physician_sign VARCHAR(100), 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_id VARCHAR(100), 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id)
);
CREATE TABLE discharge_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    dept_name VARCHAR(100), 
    ward_name VARCHAR(100), 
    admission_date DATE, 
    discharge_date DATE, 
    inpatient_duration VARCHAR(100), 
    admission_condition TEXT, 
    positive_assist_exam TEXT, 
    treatment_course TEXT, 
    discharge_condition TEXT, 
    discharge_order TEXT, 
    condition_transform VARCHAR(100), 
    record_content TEXT, 
    resident_physician_sign VARCHAR(100), 
    attending_physician_sign VARCHAR(100), 
    chief_physician_sign VARCHAR(100), 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_id VARCHAR(100), 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id)
);
CREATE TABLE qc_result (
    id SERIAL NOT NULL, 
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    qc_type VARCHAR(50) NOT NULL, 
    rule_id VARCHAR(100), 
    rule_name VARCHAR(200), 
    severity VARCHAR(20) NOT NULL, 
    category VARCHAR(100), 
    description TEXT, 
    suggestion TEXT, 
    field_path VARCHAR(200), 
    status VARCHAR(20), 
    resolved_by VARCHAR(100), 
    resolved_at TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE, 
    updated_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_qc_visit ON qc_result (institute_id, patient_id, visit_id);

CREATE INDEX ix_qc_type ON qc_result (qc_type, severity);
CREATE TABLE first_course_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE daily_course_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE senior_course_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE postsurg_firstcourse_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE consultation_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE rescue_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE transfer_in_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE transfer_out_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE surgery_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE labtest_item_report (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE exam_item_report (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE diffcase_discussion_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE death_discussion (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE death_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE handoff_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE handover_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE summary_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE presurg_summary (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE presurg_discussion (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE surgery_safecheck_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE surgery_risk_assessment (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE anesthesia_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE newborn_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE bloodtrans_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE nursing_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE medical_insurance_settlement (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    document_id VARCHAR(100), 
    designated_medical_institution VARCHAR(100), 
    medical_insurance_record_dept VARCHAR(100), 
    medical_insurance_recorder VARCHAR(100), 
    medinsur_serial_no VARCHAR(100), 
    business_serial_no VARCHAR(100), 
    medinsur_receipt_id VARCHAR(100), 
    ticket_code VARCHAR(100), 
    ticket_no VARCHAR(100), 
    settlement_method VARCHAR(100), 
    patient_insurance_no VARCHAR(100), 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    nationality VARCHAR(100), 
    occupation_category VARCHAR(100), 
    currentaddress_province VARCHAR(100), 
    currentaddress_city VARCHAR(100), 
    currentaddress_county VARCHAR(100), 
    currentaddress_town VARCHAR(100), 
    currentaddress_village VARCHAR(100), 
    currentaddress_detail VARCHAR(100), 
    currentaddress TEXT, 
    currentaddress_postcode VARCHAR(100), 
    currentaddress_phone VARCHAR(100), 
    work_unit VARCHAR(100), 
    workplace_province VARCHAR(100), 
    workplace_city VARCHAR(100), 
    workplace_county VARCHAR(100), 
    workplace_town VARCHAR(100), 
    workplace_village VARCHAR(100), 
    workplace_detail VARCHAR(100), 
    workplace TEXT, 
    workplace_postcode VARCHAR(100), 
    work_telephone VARCHAR(100), 
    contact_name VARCHAR(100), 
    contact_relationship VARCHAR(100), 
    contact_address VARCHAR(100), 
    contact_telephone VARCHAR(100), 
    newborn_admission_type VARCHAR(100), 
    newborn_birthweight VARCHAR(100), 
    newborn_admitweigth VARCHAR(100), 
    newborn_birth_weight VARCHAR(100), 
    newborn_admission_weight VARCHAR(100), 
    admission_route VARCHAR(100), 
    special_personnel_type VARCHAR(100), 
    admission_datetime TIMESTAMP WITHOUT TIME ZONE, 
    admission_dept_name VARCHAR(100), 
    transfer_dept_name VARCHAR(100), 
    discharge_datetime TIMESTAMP WITHOUT TIME ZONE, 
    discharge_dept_name VARCHAR(100), 
    leaving_hospital_way VARCHAR(100), 
    receiving_institution_name VARCHAR(100), 
    receiving_institution_code VARCHAR(100), 
    rehospital_with_month VARCHAR(100), 
    rehospital_with_month_purpose VARCHAR(100), 
    insurance_no VARCHAR(100), 
    declaration_time TIMESTAMP WITHOUT TIME ZONE, 
    inpat_type VARCHAR(100), 
    therapy_type VARCHAR(100), 
    diagnosis_code_cnt VARCHAR(100), 
    surgery_code_cnt VARCHAR(100), 
    ventilator_usetime VARCHAR(100), 
    coma_timebefadm_d VARCHAR(100), 
    coma_timebefadm_h VARCHAR(100), 
    coma_timebefadm_min VARCHAR(100), 
    coma_timeaftadm_d VARCHAR(100), 
    coma_timeaftadm_h VARCHAR(100), 
    coma_timeaftadm_min VARCHAR(100), 
    primary_care_days VARCHAR(100), 
    secondary_care_days VARCHAR(100), 
    tertiary_care_days VARCHAR(100), 
    intensive_care_days VARCHAR(100), 
    insured_place VARCHAR(100), 
    out_of_pocket_advance VARCHAR(100), 
    out_of_pocket_amount VARCHAR(100), 
    personal_account_expend VARCHAR(100), 
    cash_payment_amount VARCHAR(100), 
    insurance_type VARCHAR(100), 
    medical_insurance_institution VARCHAR(100), 
    medical_insurance_agent VARCHAR(100), 
    medical_insurance_agent_code VARCHAR(100), 
    outp_chronic_department VARCHAR(100), 
    outp_chronic_date TIMESTAMP WITHOUT TIME ZONE, 
    attending_physician_code VARCHAR(100), 
    responsible_nurse_code VARCHAR(100), 
    settlement_status VARCHAR(100), 
    start_date TIMESTAMP WITHOUT TIME ZONE, 
    end_date TIMESTAMP WITHOUT TIME ZONE, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id)
);
CREATE TABLE medical_insurance_settlement_cost (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    document_id VARCHAR(100), 
    medinsur_serial_no VARCHAR(100), 
    medinsur_serial_item_id VARCHAR(100) NOT NULL, 
    charge VARCHAR(100), 
    type_of_medicalcharge VARCHAR(100), 
    charge_item_level VARCHAR(100), 
    item_class_a_amount VARCHAR(100), 
    item_class_b_amount VARCHAR(100), 
    item_own_pay_amount VARCHAR(100), 
    item_other_amount VARCHAR(100), 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, medinsur_serial_item_id)
);
CREATE TABLE inpat_drug_order (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    order_id VARCHAR(100) NOT NULL, 
    inpat_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    dept_name VARCHAR(100), 
    group_id VARCHAR(100), 
    repeat_indicator VARCHAR(100), 
    drug_type VARCHAR(100), 
    brand_name VARCHAR(100), 
    drug_code VARCHAR(100), 
    generic_name VARCHAR(100), 
    cfda_id VARCHAR(100), 
    firm VARCHAR(100), 
    drug_specification VARCHAR(100), 
    drug_frequency VARCHAR(100), 
    drug_apply_method VARCHAR(100), 
    single_dose VARCHAR(100), 
    single_dose_unit VARCHAR(100), 
    dose_form VARCHAR(100), 
    medication_duration VARCHAR(100), 
    prescribed_datetime TIMESTAMP WITHOUT TIME ZONE, 
    prescribed_doctor VARCHAR(100), 
    order_status VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, order_id)
);
CREATE TABLE inpat_nondrug_order (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    order_id VARCHAR(100) NOT NULL, 
    inpat_no VARCHAR(100), 
    application_id VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    dept_name VARCHAR(100), 
    group_id VARCHAR(100), 
    repeat_indicator VARCHAR(100), 
    order_type VARCHAR(100), 
    order_name VARCHAR(100), 
    quantity VARCHAR(100), 
    quantity_unit VARCHAR(100), 
    frequency VARCHAR(100), 
    prescribed_datetime TIMESTAMP WITHOUT TIME ZONE, 
    prescribed_doctor VARCHAR(100), 
    order_status VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, order_id)
);
CREATE TABLE inpat_bill_item (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    bill_item_id VARCHAR(100) NOT NULL, 
    receipt_id VARCHAR(100), 
    inpat_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    order_id VARCHAR(100), 
    item_type VARCHAR(100), 
    medical_catalog_code VARCHAR(100), 
    medical_catalog_name VARCHAR(100), 
    medinsur_catalog_code VARCHAR(100), 
    medinsur_catalog_name VARCHAR(100), 
    item_specification VARCHAR(100), 
    firm VARCHAR(100), 
    unit_price VARCHAR(100), 
    quantity VARCHAR(100), 
    quantity_unit VARCHAR(100), 
    cost VARCHAR(100), 
    charge VARCHAR(100), 
    insurance_category VARCHAR(100), 
    charge_item_level VARCHAR(100), 
    billing_datetime TIMESTAMP WITHOUT TIME ZONE, 
    order_dept_name VARCHAR(100), 
    executive_dept_name VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, bill_item_id)
);
CREATE TABLE labtest_master (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    test_id VARCHAR(100) NOT NULL, 
    order_id VARCHAR(100), 
    inpat_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    labtest_subject VARCHAR(100), 
    labtest_cause VARCHAR(100), 
    specimen VARCHAR(100), 
    request_dept VARCHAR(100), 
    request_physician VARCHAR(100), 
    request_datetime TIMESTAMP WITHOUT TIME ZONE, 
    report_datetime TIMESTAMP WITHOUT TIME ZONE, 
    reporter VARCHAR(100), 
    verifier VARCHAR(100), 
    labtest_result_status VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, test_id)
);
CREATE TABLE labtest_item (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    test_id VARCHAR(100) NOT NULL, 
    test_item_id VARCHAR(100) NOT NULL, 
    item_name VARCHAR(100), 
    item_code VARCHAR(100), 
    report_datetime TIMESTAMP WITHOUT TIME ZONE, 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, test_id, test_item_id)
);
CREATE TABLE mr_bloodtrans (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    document_id VARCHAR(100), 
    bloodtrans_id VARCHAR(100) NOT NULL, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    transfuse_variety VARCHAR(100), 
    bloodbag_id VARCHAR(100), 
    blood_transfusion_volume VARCHAR(100), 
    blood_transfusion_unit VARCHAR(100), 
    transblood_reaction_sign VARCHAR(100), 
    transblood_reaction_type VARCHAR(100), 
    transfution_datetime TIMESTAMP WITHOUT TIME ZONE, 
    transfusion_reason VARCHAR(100), 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, bloodtrans_id)
);
CREATE TABLE mr_icu (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    document_id VARCHAR(100), 
    icu_id VARCHAR(100) NOT NULL, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    icu_type VARCHAR(100), 
    icu_name VARCHAR(100), 
    icu_start_datetime TIMESTAMP WITHOUT TIME ZONE, 
    icu_end_datetime TIMESTAMP WITHOUT TIME ZONE, 
    icu_period VARCHAR(100), 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, icu_id)
);
CREATE TABLE mr_customize (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    document_id VARCHAR(100), 
    mr_no VARCHAR(100), 
    "T_stage" VARCHAR(100), 
    "N_stage" VARCHAR(100), 
    "M_stage" VARCHAR(100), 
    tumor_stage VARCHAR(100), 
    transferin_org_name VARCHAR(100), 
    discharge_condition VARCHAR(100), 
    living_ability_admission_score VARCHAR(100), 
    living_ability_discharge_score VARCHAR(100), 
    rescue_no VARCHAR(100), 
    rescue_success_no VARCHAR(100), 
    criticalcare_record_sign VARCHAR(100), 
    difficult_record_sign VARCHAR(100), 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id)
);
CREATE TABLE medinsur_receipt (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    medinsur_receipt_id VARCHAR(100) NOT NULL, 
    outpat_no VARCHAR(100), 
    inpat_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    ethnicity VARCHAR(100), 
    birthday DATE, 
    age_year VARCHAR(100), 
    insurance_type VARCHAR(100), 
    insurance_no VARCHAR(100), 
    settlement_method VARCHAR(100), 
    total_charge VARCHAR(100), 
    personnel_payment VARCHAR(100), 
    fund_payment_amount VARCHAR(100), 
    personal_account_expend VARCHAR(100), 
    cash_payment_amount VARCHAR(100), 
    start_date TIMESTAMP WITHOUT TIME ZONE, 
    end_date TIMESTAMP WITHOUT TIME ZONE, 
    settle_datetime TIMESTAMP WITHOUT TIME ZONE, 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, medinsur_receipt_id)
);
CREATE TABLE pathology_exam_master (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    pathology_exam_id VARCHAR(100) NOT NULL, 
    pathology_id VARCHAR(100), 
    inpat_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    clinical_history VARCHAR(100), 
    surgery_name VARCHAR(100), 
    specimen_name VARCHAR(100), 
    request_dept VARCHAR(100), 
    request_physician VARCHAR(100), 
    request_datetime TIMESTAMP WITHOUT TIME ZONE, 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, pathology_exam_id)
);
CREATE TABLE pathology_exam_report (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    pathology_exam_id VARCHAR(100) NOT NULL, 
    pathology_id VARCHAR(100), 
    specimen_name VARCHAR(100), 
    eye_findings VARCHAR(100), 
    microscope_findings VARCHAR(100), 
    diagnosis TEXT, 
    report_status VARCHAR(100), 
    report_datetime TIMESTAMP WITHOUT TIME ZONE, 
    reporter VARCHAR(100), 
    review_datetime TIMESTAMP WITHOUT TIME ZONE, 
    reviewer VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, pathology_exam_id)
);
CREATE TABLE epidemic_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    dept_name VARCHAR(100), 
    inpat_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    record_content TEXT, 
    record_datetime TIMESTAMP WITHOUT TIME ZONE, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE outpat_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    dept_name VARCHAR(100), 
    outpat_no VARCHAR(100), 
    visit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    chief_complaint TEXT, 
    history_of_present_illness TEXT, 
    past_history TEXT, 
    checkup TEXT, 
    assist_exam TEXT, 
    treatment_advice VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE surgery_application (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    application_id VARCHAR(100) NOT NULL, 
    order_id VARCHAR(100), 
    dept_name VARCHAR(100), 
    surgery_name VARCHAR(100), 
    surgery_code VARCHAR(100), 
    surgery_level VARCHAR(100), 
    anesthesia_method VARCHAR(100), 
    surgeon VARCHAR(100), 
    request_physician VARCHAR(100), 
    request_surgery_datetime TIMESTAMP WITHOUT TIME ZONE, 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, application_id)
);
CREATE TABLE docpat_commu_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    dept_name VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    pat_doc_comm_type VARCHAR(100), 
    record_content TEXT, 
    record_datetime TIMESTAMP WITHOUT TIME ZONE, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE daily_admission_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    dept_name VARCHAR(100), 
    admission_datetime TIMESTAMP WITHOUT TIME ZONE, 
    discharge_datetime TIMESTAMP WITHOUT TIME ZONE, 
    chief_complaint TEXT, 
    admission_condition TEXT, 
    treatment_course TEXT, 
    discharge_condition TEXT, 
    discharge_order TEXT, 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE daily_death_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    dept_name VARCHAR(100), 
    admission_condition TEXT, 
    treatment_course TEXT, 
    death_reason VARCHAR(100), 
    death_datetime TIMESTAMP WITHOUT TIME ZONE, 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE preane_surveil_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    dept_name VARCHAR(100), 
    condition_summary TEXT, 
    planned_anesthesia_method VARCHAR(100), 
    "ASA_level" VARCHAR(100), 
    record_content TEXT, 
    anesthetist_sign VARCHAR(100), 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE postane_surveil_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    dept_name VARCHAR(100), 
    surgery_name VARCHAR(100), 
    anesthesia_method VARCHAR(100), 
    resume_descirption VARCHAR(100), 
    record_content TEXT, 
    anesthetist_sign VARCHAR(100), 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE surgery_inform_consent (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    dept_name VARCHAR(100), 
    planned_operation_name VARCHAR(100), 
    planned_operation_code VARCHAR(100), 
    planned_anesthesia_method VARCHAR(100), 
    surgery_risk_description TEXT, 
    record_content TEXT, 
    patient_sign VARCHAR(100), 
    surgeon_sign VARCHAR(100), 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE crisis_value_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    dept_name VARCHAR(100), 
    record_content TEXT, 
    record_datetime TIMESTAMP WITHOUT TIME ZONE, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE blood_application (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    application_id VARCHAR(100) NOT NULL, 
    inpat_no VARCHAR(100), 
    dept_name VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    patient_bloodtype_abo VARCHAR(100), 
    patient_bloodtype_rhd VARCHAR(100), 
    transfuse_variety VARCHAR(100), 
    transfuse_volume VARCHAR(100), 
    transfuse_volume_unit VARCHAR(100), 
    request_datetime TIMESTAMP WITHOUT TIME ZONE, 
    physician_name VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id, application_id)
);
CREATE TABLE surgery_inventory_record (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    document_id VARCHAR(100) NOT NULL, 
    visit_type VARCHAR(100), 
    dept_name VARCHAR(100), 
    surgery_room_name VARCHAR(100), 
    surgery_date DATE, 
    surgery_name VARCHAR(100), 
    record_content TEXT, 
    last_modifier VARCHAR(100), 
    last_modifier_id VARCHAR(100), 
    last_modified_datetime TIMESTAMP WITHOUT TIME ZONE, 
    update_time TIMESTAMP WITHOUT TIME ZONE, 
    document_title VARCHAR(100), 
    document_status VARCHAR(100), 
    submitter VARCHAR(100), 
    submitter_id VARCHAR(100), 
    submit_datetime TIMESTAMP WITHOUT TIME ZONE, 
    inpat_no VARCHAR(100), 
    mr_no VARCHAR(100), 
    name VARCHAR(100), 
    sex VARCHAR(100), 
    age_year VARCHAR(100), 
    age_month VARCHAR(100), 
    age VARCHAR(100), 
    PRIMARY KEY (institute_id, patient_id, visit_id, document_id)
);
CREATE TABLE sys_users (
    id VARCHAR(36) NOT NULL, 
    username VARCHAR(50) NOT NULL, 
    email VARCHAR(100), 
    password_hash TEXT, 
    display_name VARCHAR(100) NOT NULL, 
    department VARCHAR(100), 
    role VARCHAR(50), 
    roles_json TEXT, 
    is_active BOOLEAN NOT NULL, 
    last_login_at TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (username), 
    UNIQUE (email)
);

CREATE INDEX ix_sys_users_role ON sys_users (role);

CREATE INDEX ix_sys_users_email ON sys_users (email);
CREATE TABLE sys_departments (
    id VARCHAR(36) NOT NULL, 
    code VARCHAR(20) NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    category VARCHAR(50), 
    is_active BOOLEAN NOT NULL, 
    sort_order INTEGER NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code)
);

CREATE TABLE qc_results (
    id VARCHAR(36) NOT NULL, 
    record_id VARCHAR(100) NOT NULL, 
    rule_set VARCHAR(100), 
    overall_score FLOAT, 
    grade VARCHAR(10), 
    defect_count INTEGER NOT NULL, 
    analysis_engine VARCHAR(30), 
    analysis_date TIMESTAMP WITHOUT TIME ZONE, 
    raw_output TEXT, 
    created_by VARCHAR(36), 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_qc_results_created_by ON qc_results (created_by);

CREATE INDEX ix_qc_results_created_at ON qc_results (created_at);

CREATE INDEX ix_qc_results_record ON qc_results (record_id);
CREATE TABLE qc_defects (
    id VARCHAR(36) NOT NULL, 
    result_id VARCHAR(36), 
    record_id VARCHAR(100) NOT NULL, 
    department VARCHAR(100), 
    rule_code VARCHAR(100), 
    rule_name VARCHAR(200), 
    description TEXT, 
    severity VARCHAR(20) NOT NULL, 
    category VARCHAR(100), 
    deduct_score FLOAT NOT NULL, 
    location VARCHAR(300), 
    evidence TEXT, 
    suggestion TEXT, 
    status VARCHAR(20) NOT NULL, 
    urged_at TIMESTAMP WITHOUT TIME ZONE, 
    urged_by VARCHAR(36), 
    urged_message TEXT, 
    urged_deadline VARCHAR(20), 
    remediated_at TIMESTAMP WITHOUT TIME ZONE, 
    remediated_by VARCHAR(36), 
    remediation_note TEXT, 
    remediation_evidence TEXT, 
    approved_at TIMESTAMP WITHOUT TIME ZONE, 
    approved_by VARCHAR(36), 
    approve_comment TEXT, 
    rejected_at TIMESTAMP WITHOUT TIME ZONE, 
    rejected_by VARCHAR(36), 
    reject_reason TEXT, 
    reject_suggestion TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_qc_defects_status ON qc_defects (status);

CREATE INDEX ix_qc_defects_severity ON qc_defects (severity);

CREATE INDEX ix_qc_defects_category ON qc_defects (category);

CREATE INDEX ix_qc_defects_department ON qc_defects (department);

CREATE INDEX ix_qc_defects_created_at ON qc_defects (created_at);

CREATE INDEX ix_qc_defects_record ON qc_defects (record_id);

CREATE INDEX ix_qc_defects_result ON qc_defects (result_id);
CREATE TABLE qc_defect_history (
    id VARCHAR(36) NOT NULL, 
    defect_id VARCHAR(36) NOT NULL, 
    action VARCHAR(40) NOT NULL, 
    actor_id VARCHAR(36), 
    actor_name VARCHAR(100), 
    details TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_qc_defect_history_created_at ON qc_defect_history (created_at);

CREATE INDEX ix_qc_defect_history_action ON qc_defect_history (action);

CREATE INDEX ix_qc_defect_history_defect ON qc_defect_history (defect_id);
CREATE TABLE qc_tasks (
    id VARCHAR(36) NOT NULL, 
    task_number VARCHAR(40) NOT NULL, 
    task_name VARCHAR(200) NOT NULL, 
    task_type VARCHAR(20) NOT NULL, 
    schedule_config TEXT, 
    date_range TEXT, 
    department_filter TEXT, 
    record_ids TEXT, 
    sampling_method VARCHAR(20), 
    sampling_config TEXT, 
    assign_method VARCHAR(30), 
    assignee_config TEXT, 
    status VARCHAR(20) NOT NULL, 
    progress FLOAT NOT NULL, 
    total_records INTEGER NOT NULL, 
    completed_records INTEGER NOT NULL, 
    creator_id VARCHAR(36), 
    creator_name VARCHAR(100), 
    deadline VARCHAR(32), 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (task_number)
);

CREATE INDEX ix_qc_tasks_created_at ON qc_tasks (created_at);

CREATE INDEX ix_qc_tasks_creator ON qc_tasks (creator_id);

CREATE INDEX ix_qc_tasks_status ON qc_tasks (status);
CREATE TABLE qc_task_records (
    id VARCHAR(36) NOT NULL, 
    task_id VARCHAR(36) NOT NULL, 
    record_id VARCHAR(100) NOT NULL, 
    assignee_id VARCHAR(36), 
    assignee_name VARCHAR(100), 
    status VARCHAR(20) NOT NULL, 
    score FLOAT, 
    defect_count INTEGER NOT NULL, 
    completed_at TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_qc_task_records_task ON qc_task_records (task_id);

CREATE UNIQUE INDEX uq_qc_task_record_unique ON qc_task_records (task_id, record_id);

CREATE INDEX ix_qc_task_records_status ON qc_task_records (status);

CREATE INDEX ix_qc_task_records_assignee ON qc_task_records (assignee_id);

CREATE INDEX ix_qc_task_records_record ON qc_task_records (record_id);

CREATE TABLE qc_appeals (
    id VARCHAR(36) NOT NULL, 
    appeal_number VARCHAR(40), 
    qc_result_id VARCHAR(36) NOT NULL, 
    record_id VARCHAR(36) NOT NULL, 
    appeal_type VARCHAR(20) NOT NULL, 
    defect_item VARCHAR(200), 
    reason TEXT NOT NULL, 
    evidence TEXT, 
    priority VARCHAR(20) NOT NULL, 
    appellant_id VARCHAR(36) NOT NULL, 
    appellant_name VARCHAR(100) NOT NULL, 
    appellant_department VARCHAR(100), 
    reviewer_id VARCHAR(36), 
    reviewer_name VARCHAR(100), 
    review_result TEXT, 
    review_date TIMESTAMP WITHOUT TIME ZONE, 
    resolution TEXT, 
    resolution_date TIMESTAMP WITHOUT TIME ZONE, 
    notes TEXT, 
    status VARCHAR(20) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (appeal_number)
);

CREATE INDEX ix_qc_appeals_priority ON qc_appeals (priority);

CREATE INDEX ix_qc_appeals_status ON qc_appeals (status);

CREATE INDEX ix_qc_appeals_type ON qc_appeals (appeal_type);

CREATE INDEX ix_qc_appeals_record ON qc_appeals (record_id);

CREATE INDEX ix_qc_appeals_created_at ON qc_appeals (created_at);
CREATE TABLE qc_appeal_reviews (
    id VARCHAR(36) NOT NULL, 
    appeal_id VARCHAR(36) NOT NULL, 
    reviewer_id VARCHAR(36) NOT NULL, 
    reviewer_name VARCHAR(100) NOT NULL, 
    reviewer_role VARCHAR(50), 
    action VARCHAR(30) NOT NULL, 
    comment TEXT, 
    metadata TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_qc_appeal_reviews_created_at ON qc_appeal_reviews (created_at);

CREATE INDEX ix_qc_appeal_reviews_reviewer ON qc_appeal_reviews (reviewer_id);

CREATE INDEX ix_qc_appeal_reviews_appeal ON qc_appeal_reviews (appeal_id);
CREATE TABLE qc_remediation_tasks (
    id VARCHAR(36) NOT NULL, 
    task_number VARCHAR(40), 
    qc_result_id VARCHAR(36) NOT NULL, 
    record_id VARCHAR(36) NOT NULL, 
    defect_type VARCHAR(100) NOT NULL, 
    defect_description TEXT NOT NULL, 
    defect_location VARCHAR(300), 
    severity VARCHAR(20) NOT NULL, 
    remediation_requirement TEXT NOT NULL, 
    deadline TIMESTAMP WITHOUT TIME ZONE, 
    assignee_id VARCHAR(36) NOT NULL, 
    assignee_name VARCHAR(100) NOT NULL, 
    assignee_department VARCHAR(100), 
    status VARCHAR(20) NOT NULL, 
    remediation_description TEXT, 
    remediation_evidence TEXT, 
    submitted_at TIMESTAMP WITHOUT TIME ZONE, 
    reviewer_id VARCHAR(36), 
    reviewer_name VARCHAR(100), 
    review_comment TEXT, 
    reviewed_at TIMESTAMP WITHOUT TIME ZONE, 
    notes TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    closed_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id), 
    UNIQUE (task_number)
);

CREATE INDEX ix_qc_remediation_tasks_created_at ON qc_remediation_tasks (created_at);

CREATE INDEX ix_qc_remediation_tasks_status ON qc_remediation_tasks (status);

CREATE INDEX ix_qc_remediation_tasks_assignee ON qc_remediation_tasks (assignee_id);

CREATE INDEX ix_qc_remediation_tasks_severity ON qc_remediation_tasks (severity);

CREATE INDEX ix_qc_remediation_tasks_defect_type ON qc_remediation_tasks (defect_type);

CREATE INDEX ix_qc_remediation_tasks_deadline ON qc_remediation_tasks (deadline);
CREATE TABLE qc_remediation_history (
    id VARCHAR(36) NOT NULL, 
    task_id VARCHAR(36) NOT NULL, 
    action VARCHAR(30) NOT NULL, 
    actor_id VARCHAR(36) NOT NULL, 
    actor_name VARCHAR(100) NOT NULL, 
    old_status VARCHAR(20), 
    new_status VARCHAR(20), 
    comment TEXT, 
    metadata TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_qc_remediation_history_actor ON qc_remediation_history (actor_id);

CREATE INDEX ix_qc_remediation_history_action ON qc_remediation_history (action);

CREATE INDEX ix_qc_remediation_history_created_at ON qc_remediation_history (created_at);

CREATE INDEX ix_qc_remediation_history_task ON qc_remediation_history (task_id);
CREATE TABLE qc_rules (
    id VARCHAR(36) NOT NULL, 
    rule_code VARCHAR(50) NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    description TEXT, 
    category VARCHAR(50) NOT NULL, 
    severity VARCHAR(20), 
    scope VARCHAR(20), 
    department_id VARCHAR(36), 
    parent_rule_id VARCHAR(36), 
    override_action VARCHAR(20), 
    override_config TEXT, 
    priority INTEGER, 
    status VARCHAR(20), 
    version VARCHAR(20), 
    effective_from TIMESTAMP WITHOUT TIME ZONE, 
    effective_to TIMESTAMP WITHOUT TIME ZONE, 
    check_logic TEXT, 
    scoring_config TEXT, 
    applicable_documents TEXT, 
    primary_document_category VARCHAR(50), 
    is_active BOOLEAN NOT NULL, 
    metadata TEXT, 
    approved_by VARCHAR(36), 
    approved_at TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (rule_code)
);

CREATE INDEX ix_qc_rules_department ON qc_rules (department_id);

CREATE INDEX ix_qc_rules_is_active ON qc_rules (is_active);

CREATE INDEX ix_qc_rules_status ON qc_rules (status);

CREATE INDEX ix_qc_rules_scope ON qc_rules (scope);

CREATE INDEX ix_qc_rules_category ON qc_rules (category);
CREATE TABLE qc_coder_workload_daily (
    id VARCHAR(36) NOT NULL, 
    stat_date DATE NOT NULL, 
    coder_id VARCHAR(36) NOT NULL, 
    coder_name VARCHAR(50) NOT NULL, 
    department_id VARCHAR(36), 
    department_name VARCHAR(50), 
    qc_count INTEGER NOT NULL, 
    recheck_count INTEGER NOT NULL, 
    defect_found INTEGER NOT NULL, 
    passed_count INTEGER NOT NULL, 
    warning_count INTEGER NOT NULL, 
    failed_count INTEGER NOT NULL, 
    avg_handle_seconds FLOAT NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_qc_coder_workload_coder ON qc_coder_workload_daily (coder_id);

CREATE UNIQUE INDEX uq_qc_coder_workload_daily ON qc_coder_workload_daily (stat_date, coder_id);

CREATE INDEX ix_qc_coder_workload_stat_date ON qc_coder_workload_daily (stat_date);
CREATE TABLE medical_documents (
    id VARCHAR(36) NOT NULL, 
    record_id VARCHAR(100) NOT NULL, 
    document_type VARCHAR(50), 
    content TEXT, 
    qc_status VARCHAR(20) NOT NULL, 
    qc_score FLOAT, 
    qc_last_analyzed TIMESTAMP WITHOUT TIME ZONE, 
    status VARCHAR(20) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_medical_documents_qc_status ON medical_documents (qc_status);

CREATE INDEX ix_medical_documents_record ON medical_documents (record_id);

CREATE INDEX ix_medical_documents_status ON medical_documents (status);

CREATE TABLE scoring_rules (
    id VARCHAR(36) NOT NULL, 
    sort_order INTEGER NOT NULL, 
    category VARCHAR(100) NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    description TEXT, 
    deduction FLOAT NOT NULL, 
    max_deduction FLOAT NOT NULL, 
    veto BOOLEAN NOT NULL, 
    severity VARCHAR(20) NOT NULL, 
    enabled BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_scoring_rules_category ON scoring_rules (category);

CREATE INDEX ix_scoring_rules_enabled ON scoring_rules (enabled);

CREATE INDEX ix_scoring_rules_sort_order ON scoring_rules (sort_order);

CREATE TABLE scoring_config (
    id VARCHAR(36) NOT NULL, 
    config_key VARCHAR(100) NOT NULL, 
    config_value TEXT NOT NULL, 
    description TEXT, 
    updated_by VARCHAR(36), 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (config_key)
);
CREATE TABLE notifications (
    id VARCHAR(36) NOT NULL, 
    type VARCHAR(30) NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    content TEXT, 
    record_id VARCHAR(100), 
    severity VARCHAR(20), 
    sender_id VARCHAR(36), 
    recipient_id VARCHAR(36), 
    related_type VARCHAR(30), 
    related_id VARCHAR(36), 
    is_read BOOLEAN NOT NULL, 
    read_at TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_notifications_is_read ON notifications (is_read);

CREATE INDEX ix_notifications_created_at ON notifications (created_at);

CREATE INDEX ix_notifications_recipient ON notifications (recipient_id);

CREATE INDEX ix_notifications_type ON notifications (type);

CREATE TABLE sync_visit_status (
    institute_id VARCHAR(100) NOT NULL, 
    patient_id VARCHAR(100) NOT NULL, 
    visit_id VARCHAR(100) NOT NULL, 
    sync_status VARCHAR(20) NOT NULL, 
    discharge_date TIMESTAMP WITHOUT TIME ZONE, 
    department VARCHAR(100), 
    mongo_update_time TIMESTAMP WITHOUT TIME ZONE, 
    local_synced_at TIMESTAMP WITHOUT TIME ZONE, 
    tier1_at TIMESTAMP WITHOUT TIME ZONE, 
    tier2_at TIMESTAMP WITHOUT TIME ZONE, 
    tier3_at TIMESTAMP WITHOUT TIME ZONE, 
    retry_count INTEGER, 
    last_error TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE, 
    updated_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (institute_id, patient_id, visit_id)
);

CREATE INDEX ix_svs_department ON sync_visit_status (department);

CREATE INDEX ix_svs_discharge ON sync_visit_status (discharge_date);

CREATE INDEX ix_svs_status ON sync_visit_status (sync_status);
CREATE TABLE sync_watermarks (
    collection_name VARCHAR(100) NOT NULL, 
    source_type VARCHAR(20) NOT NULL, 
    last_sync_cursor TIMESTAMP WITHOUT TIME ZONE, 
    last_sync_id VARCHAR(100), 
    last_sync_status VARCHAR(20), 
    last_record_count INTEGER, 
    last_sync_at TIMESTAMP WITHOUT TIME ZONE, 
    last_error TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE, 
    updated_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (collection_name)
);
-- QC business views aligned with current router expectations.
-- Apply after base tables are created.

DROP VIEW IF EXISTS v_qc_task_progress;

CREATE VIEW v_qc_task_progress AS
SELECT
    t.id AS task_id,
    t.task_name AS task_name,
    COUNT(r.id) AS total_records,
    SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) AS completed_records,
    CASE
        WHEN COUNT(r.id) = 0 THEN 0
        ELSE ROUND(SUM(CASE WHEN r.status = 'completed' THEN 1.0 ELSE 0 END) * 100.0 / COUNT(r.id), 1)
    END AS progress_pct,
    SUM(CASE WHEN r.status = 'pending' THEN 1 ELSE 0 END) AS pending_count,
    SUM(CASE WHEN r.status = 'in_progress' THEN 1 ELSE 0 END) AS working_count,
    SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) AS done_count,
    AVG(r.score) AS avg_score,
    SUM(COALESCE(r.defect_count, 0)) AS total_defects
FROM qc_tasks t
LEFT JOIN qc_task_records r ON r.task_id = t.id
GROUP BY t.id, t.task_name;

DROP VIEW IF EXISTS qc_appeals_statistics;

CREATE VIEW qc_appeals_statistics AS
SELECT
    status,
    appeal_type,
    priority,
    COUNT(*) AS count,
    0.0 AS avg_resolution_time_seconds
FROM qc_appeals
GROUP BY status, appeal_type, priority;

DROP VIEW IF EXISTS qc_remediation_statistics;

CREATE VIEW qc_remediation_statistics AS
SELECT
    status,
    severity,
    defect_type,
    COUNT(*) AS count,
    0.0 AS avg_completion_time_seconds
FROM qc_remediation_tasks
GROUP BY status, severity, defect_type;

DROP VIEW IF EXISTS qc_assignee_workload;

CREATE VIEW qc_assignee_workload AS
SELECT
    assignee_id,
    assignee_name,
    assignee_department,
    COUNT(*) AS total_tasks,
    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending_tasks,
    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress_tasks,
    SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) AS overdue_tasks,
    0.0 AS avg_completion_days
FROM qc_remediation_tasks
WHERE assignee_id IS NOT NULL AND assignee_id <> ''
GROUP BY assignee_id, assignee_name, assignee_department;

DROP VIEW IF EXISTS qc_statistics_view;

CREATE VIEW qc_statistics_view AS
SELECT
    d.record_id,
    COUNT(d.id) AS total_documents,
    COUNT(*) FILTER (WHERE d.qc_status = 'passed') AS passed_count,
    COUNT(*) FILTER (WHERE d.qc_status = 'warning') AS warning_count,
    COUNT(*) FILTER (WHERE d.qc_status = 'failed') AS failed_count,
    COUNT(*) FILTER (WHERE d.qc_status = 'pending') AS pending_count,
    ROUND(AVG(d.qc_score)::numeric, 2) AS avg_qc_score,
    MAX(d.qc_last_analyzed) AS last_analyzed_time
FROM medical_documents d
WHERE d.status = 'active'
GROUP BY d.record_id;

DROP VIEW IF EXISTS v_qc_coder_ranking;

CREATE VIEW v_qc_coder_ranking AS
SELECT
    coder_id AS user_id,
    coder_name AS name,
    department_name AS department,
    SUM(qc_count) AS qc_count,
    SUM(recheck_count) AS recheck_count,
    SUM(defect_found) AS defect_found,
    ROUND(
      CASE WHEN SUM(qc_count) = 0 THEN 0
      ELSE SUM(passed_count)::numeric * 100.0 / SUM(qc_count)
      END, 1
    ) AS pass_rate,
    ROUND(SUM(qc_count)::numeric / GREATEST(COUNT(DISTINCT stat_date), 1), 1) AS avg_daily
FROM qc_coder_workload_daily
WHERE stat_date >= CURRENT_DATE - INTERVAL '30 day'
GROUP BY coder_id, coder_name, department_name;

INSERT INTO alembic_version (version_num) VALUES ('20260315_000001') RETURNING alembic_version.version_num;

-- Running upgrade 20260315_000001 -> 20260315_000002

CREATE SCHEMA IF NOT EXISTS "qc";

CREATE SCHEMA IF NOT EXISTS "sys";

CREATE SCHEMA IF NOT EXISTS "cdm";

CREATE SCHEMA IF NOT EXISTS "legacy";

ALTER TABLE IF EXISTS public."qc_tasks" SET SCHEMA qc;

ALTER TABLE IF EXISTS public."qc_task_records" SET SCHEMA qc;

ALTER TABLE IF EXISTS public."qc_results" SET SCHEMA qc;

ALTER TABLE IF EXISTS public."qc_defects" SET SCHEMA qc;

ALTER TABLE IF EXISTS public."qc_defect_history" SET SCHEMA qc;

ALTER TABLE IF EXISTS public."qc_appeals" SET SCHEMA qc;

ALTER TABLE IF EXISTS public."qc_appeal_reviews" SET SCHEMA qc;

ALTER TABLE IF EXISTS public."qc_remediation_tasks" SET SCHEMA qc;

ALTER TABLE IF EXISTS public."qc_remediation_history" SET SCHEMA qc;

ALTER TABLE IF EXISTS public."qc_rules" SET SCHEMA qc;

ALTER TABLE IF EXISTS public."scoring_rules" SET SCHEMA qc;

ALTER TABLE IF EXISTS public."scoring_config" SET SCHEMA qc;

ALTER TABLE IF EXISTS public."notifications" SET SCHEMA qc;

ALTER TABLE IF EXISTS public."qc_coder_workload_daily" SET SCHEMA qc;

ALTER TABLE IF EXISTS public."sys_users" SET SCHEMA sys;

ALTER TABLE IF EXISTS public."sys_departments" SET SCHEMA sys;

ALTER TABLE IF EXISTS public."sys_roles" SET SCHEMA sys;

ALTER TABLE IF EXISTS public."sys_role_permissions" SET SCHEMA sys;

ALTER TABLE IF EXISTS public."medical_records" SET SCHEMA cdm;

ALTER TABLE IF EXISTS public."medical_documents" SET SCHEMA cdm;

ALTER VIEW IF EXISTS public."v_qc_task_progress" SET SCHEMA qc;

ALTER VIEW IF EXISTS public."qc_appeals_statistics" SET SCHEMA qc;

ALTER VIEW IF EXISTS public."qc_remediation_statistics" SET SCHEMA qc;

ALTER VIEW IF EXISTS public."qc_assignee_workload" SET SCHEMA qc;

ALTER VIEW IF EXISTS public."qc_statistics_view" SET SCHEMA qc;

ALTER VIEW IF EXISTS public."v_qc_coder_ranking" SET SCHEMA qc;

UPDATE alembic_version SET version_num='20260315_000002' WHERE alembic_version.version_num = '20260315_000001';


-- Auto-generated English column comments
COMMENT ON COLUMN alembic_version.version_num IS 'Alembic Version Version Number';
COMMENT ON COLUMN patient_information.institute_id IS 'Patient Information Institute ID';
COMMENT ON COLUMN patient_information.patient_id IS 'Patient Information Patient ID';
COMMENT ON COLUMN patient_information.name IS 'Patient Information Name';
COMMENT ON COLUMN patient_information.sex IS 'Patient Information Sex';
COMMENT ON COLUMN patient_information.birthday IS 'Patient Information Birthday';
COMMENT ON COLUMN patient_information.id_card_type IS 'Patient Information ID Card Type';
COMMENT ON COLUMN patient_information.id_card_no IS 'Patient Information ID Card No';
COMMENT ON COLUMN patient_information.ethnicity IS 'Patient Information Ethnicity';
COMMENT ON COLUMN patient_information.nationality IS 'Patient Information Nationality';
COMMENT ON COLUMN patient_information.marital_status IS 'Patient Information Marital Status';
COMMENT ON COLUMN patient_information.contact_number IS 'Patient Information Contact Number';
COMMENT ON COLUMN patient_information.occupation_category IS 'Patient Information Occupation Category';
COMMENT ON COLUMN patient_information.work_unit IS 'Patient Information Work Unit';
COMMENT ON COLUMN patient_information.nativeplace IS 'Patient Information Native place';
COMMENT ON COLUMN patient_information.birthplace IS 'Patient Information Birth place';
COMMENT ON COLUMN patient_information.currentaddress IS 'Patient Information Current address';
COMMENT ON COLUMN patient_information.workplace IS 'Patient Information Workplace';
COMMENT ON COLUMN patient_information.contact_name IS 'Patient Information Contact Name';
COMMENT ON COLUMN patient_information.contact_relationship IS 'Patient Information Contact Relationship';
COMMENT ON COLUMN patient_information.contact_address IS 'Patient Information Contact Address';
COMMENT ON COLUMN patient_information.contact_telephone IS 'Patient Information Contact Telephone';
COMMENT ON COLUMN patient_information.record_content IS 'Patient Information Record Content';
COMMENT ON COLUMN patient_information.last_modifier IS 'Patient Information Last Modifier';
COMMENT ON COLUMN patient_information.last_modifier_id IS 'Patient Information Last Modifier ID';
COMMENT ON COLUMN patient_information.last_modified_datetime IS 'Patient Information Last Modified Date time';
COMMENT ON COLUMN patient_information.update_time IS 'Patient Information Update Time';
COMMENT ON COLUMN inpat_registration.institute_id IS 'Inpatient Registration Institute ID';
COMMENT ON COLUMN inpat_registration.patient_id IS 'Inpatient Registration Patient ID';
COMMENT ON COLUMN inpat_registration.visit_id IS 'Inpatient Registration Visit ID';
COMMENT ON COLUMN inpat_registration.visit_type IS 'Inpatient Registration Visit Type';
COMMENT ON COLUMN inpat_registration.visit_cnt IS 'Inpatient Registration Visit Count';
COMMENT ON COLUMN inpat_registration.inpat_no IS 'Inpatient Registration Inpatient No';
COMMENT ON COLUMN inpat_registration.mr_no IS 'Inpatient Registration MR No';
COMMENT ON COLUMN inpat_registration.name IS 'Inpatient Registration Name';
COMMENT ON COLUMN inpat_registration.sex IS 'Inpatient Registration Sex';
COMMENT ON COLUMN inpat_registration.birthday IS 'Inpatient Registration Birthday';
COMMENT ON COLUMN inpat_registration.age_year IS 'Inpatient Registration Age Year';
COMMENT ON COLUMN inpat_registration.age_month IS 'Inpatient Registration Age Month';
COMMENT ON COLUMN inpat_registration.age IS 'Inpatient Registration Age';
COMMENT ON COLUMN inpat_registration.id_card_type IS 'Inpatient Registration ID Card Type';
COMMENT ON COLUMN inpat_registration.id_card_no IS 'Inpatient Registration ID Card No';
COMMENT ON COLUMN inpat_registration.charge_type IS 'Inpatient Registration Charge Type';
COMMENT ON COLUMN inpat_registration.insurance_type IS 'Inpatient Registration Insurance Type';
COMMENT ON COLUMN inpat_registration.insurance_no IS 'Inpatient Registration Insurance No';
COMMENT ON COLUMN inpat_registration.admission_dept_name IS 'Inpatient Registration Admission Department Name';
COMMENT ON COLUMN inpat_registration.admission_reason IS 'Inpatient Registration Admission Reason';
COMMENT ON COLUMN inpat_registration.discharge_dept_name IS 'Inpatient Registration Discharge Department Name';
COMMENT ON COLUMN inpat_registration.admission_datetime IS 'Inpatient Registration Admission Date time';
COMMENT ON COLUMN inpat_registration.discharge_datetime IS 'Inpatient Registration Discharge Date time';
COMMENT ON COLUMN inpat_registration.record_content IS 'Inpatient Registration Record Content';
COMMENT ON COLUMN inpat_registration.last_modifier IS 'Inpatient Registration Last Modifier';
COMMENT ON COLUMN inpat_registration.last_modifier_id IS 'Inpatient Registration Last Modifier ID';
COMMENT ON COLUMN inpat_registration.last_modified_datetime IS 'Inpatient Registration Last Modified Date time';
COMMENT ON COLUMN inpat_registration.update_time IS 'Inpatient Registration Update Time';
COMMENT ON COLUMN mr.institute_id IS 'MR Institute ID';
COMMENT ON COLUMN mr.patient_id IS 'MR Patient ID';
COMMENT ON COLUMN mr.visit_id IS 'MR Visit ID';
COMMENT ON COLUMN mr.visit_type IS 'MR Visit Type';
COMMENT ON COLUMN mr.document_id IS 'MR Document ID';
COMMENT ON COLUMN mr.institute_code IS 'MR Institute Code';
COMMENT ON COLUMN mr.institute_county_desc IS 'MR Institute County Desc';
COMMENT ON COLUMN mr.medical_payment_method IS 'MR Medical Payment Method';
COMMENT ON COLUMN mr.insurance_type IS 'MR Insurance Type';
COMMENT ON COLUMN mr.insurance_no IS 'MR Insurance No';
COMMENT ON COLUMN mr.visit_cnt IS 'MR Visit Count';
COMMENT ON COLUMN mr.id_card_type IS 'MR ID Card Type';
COMMENT ON COLUMN mr.id_card_no IS 'MR ID Card No';
COMMENT ON COLUMN mr.birthday IS 'MR Birthday';
COMMENT ON COLUMN mr.nationality IS 'MR Nationality';
COMMENT ON COLUMN mr.ethnicity IS 'MR Ethnicity';
COMMENT ON COLUMN mr.marital_status IS 'MR Marital Status';
COMMENT ON COLUMN mr.occupation_category IS 'MR Occupation Category';
COMMENT ON COLUMN mr.nativeplace IS 'MR Native place';
COMMENT ON COLUMN mr.currentaddress IS 'MR Current address';
COMMENT ON COLUMN mr.contact_number IS 'MR Contact Number';
COMMENT ON COLUMN mr.contact_name IS 'MR Contact Name';
COMMENT ON COLUMN mr.contact_relationship IS 'MR Contact Relationship';
COMMENT ON COLUMN mr.contact_address IS 'MR Contact Address';
COMMENT ON COLUMN mr.contact_telephone IS 'MR Contact Telephone';
COMMENT ON COLUMN mr.work_unit IS 'MR Work Unit';
COMMENT ON COLUMN mr.admission_route IS 'MR Admission Route';
COMMENT ON COLUMN mr.admission_datetime IS 'MR Admission Date time';
COMMENT ON COLUMN mr.admission_condition IS 'MR Admission Condition';
COMMENT ON COLUMN mr.admission_dept_name IS 'MR Admission Department Name';
COMMENT ON COLUMN mr.admission_ward_name IS 'MR Admission Ward Name';
COMMENT ON COLUMN mr.diagnosis_date IS 'MR Diagnosis Date';
COMMENT ON COLUMN mr.transfer_dept_name IS 'MR Transfer Department Name';
COMMENT ON COLUMN mr.discharge_datetime IS 'MR Discharge Date time';
COMMENT ON COLUMN mr.discharge_dept_name IS 'MR Discharge Department Name';
COMMENT ON COLUMN mr.discharge_ward_name IS 'MR Discharge Ward Name';
COMMENT ON COLUMN mr.hospital_duration IS 'MR Hospital Duration';
COMMENT ON COLUMN mr.pathology_id IS 'MR Pathology ID';
COMMENT ON COLUMN mr.allergy_sign IS 'MR Allergy Signature';
COMMENT ON COLUMN mr.allergy_history IS 'MR Allergy History';
COMMENT ON COLUMN mr.abo_blood_code IS 'MR ABO Blood Code';
COMMENT ON COLUMN mr.rh_blood_code IS 'MR Rh Blood Code';
COMMENT ON COLUMN mr.death_autopsy_sign IS 'MR Death Autopsy Signature';
COMMENT ON COLUMN mr.deptdirector_sign IS 'MR Deptdirector Signature';
COMMENT ON COLUMN mr.chief_physician_sign IS 'MR Chief Physician Signature';
COMMENT ON COLUMN mr.attending_physician_sign IS 'MR Attending Physician Signature';
COMMENT ON COLUMN mr.resident_physician_sign IS 'MR Resident Physician Signature';
COMMENT ON COLUMN mr.responsible_nurse_sign IS 'MR Responsible Nurse Signature';
COMMENT ON COLUMN mr.coder_sign IS 'MR Coder Signature';
COMMENT ON COLUMN mr.QC_physician_sign IS 'MR QC Physician Signature';
COMMENT ON COLUMN mr.QC_nurse_sign IS 'MR QC Nurse Signature';
COMMENT ON COLUMN mr.QC_date IS 'MR QC Date';
COMMENT ON COLUMN mr.medicalrecord_quality IS 'MR Medicalrecord Quality';
COMMENT ON COLUMN mr.leaving_hospital_way IS 'MR Leaving Hospital Way';
COMMENT ON COLUMN mr.planned_transder_to IS 'MR Planned Transfer TO';
COMMENT ON COLUMN mr.rehospital_with_month IS 'MR Rehospital With Month';
COMMENT ON COLUMN mr.rehospital_with_month_purpose IS 'MR Rehospital With Month Purpose';
COMMENT ON COLUMN mr.rbc IS 'MR RBC';
COMMENT ON COLUMN mr.platet_volume IS 'MR Platelet Volume';
COMMENT ON COLUMN mr.plasma_volume IS 'MR Plasma Volume';
COMMENT ON COLUMN mr.whole_blood_volume IS 'MR Whole Blood Volume';
COMMENT ON COLUMN mr.autoblood_trans IS 'MR Autoblood Transfusion';
COMMENT ON COLUMN mr.clinical_pathway IS 'MR Clinical Pathway';
COMMENT ON COLUMN mr.archive_sign IS 'MR Archive Signature';
COMMENT ON COLUMN mr.mr_datetime IS 'MR MR Date time';
COMMENT ON COLUMN mr.record_content IS 'MR Record Content';
COMMENT ON COLUMN mr.last_modifier IS 'MR Last Modifier';
COMMENT ON COLUMN mr.last_modifier_id IS 'MR Last Modifier ID';
COMMENT ON COLUMN mr.last_modified_datetime IS 'MR Last Modified Date time';
COMMENT ON COLUMN mr.update_time IS 'MR Update Time';
COMMENT ON COLUMN mr.inpat_no IS 'MR Inpatient No';
COMMENT ON COLUMN mr.mr_no IS 'MR MR No';
COMMENT ON COLUMN mr.name IS 'MR Name';
COMMENT ON COLUMN mr.sex IS 'MR Sex';
COMMENT ON COLUMN mr.age_year IS 'MR Age Year';
COMMENT ON COLUMN mr.age_month IS 'MR Age Month';
COMMENT ON COLUMN mr.age IS 'MR Age';
COMMENT ON COLUMN mr_surgery.institute_id IS 'MR Surgery Institute ID';
COMMENT ON COLUMN mr_surgery.patient_id IS 'MR Surgery Patient ID';
COMMENT ON COLUMN mr_surgery.visit_id IS 'MR Surgery Visit ID';
COMMENT ON COLUMN mr_surgery.visit_type IS 'MR Surgery Visit Type';
COMMENT ON COLUMN mr_surgery.document_id IS 'MR Surgery Document ID';
COMMENT ON COLUMN mr_surgery.surgery_id IS 'MR Surgery Surgery ID';
COMMENT ON COLUMN mr_surgery.inpat_no IS 'MR Surgery Inpatient No';
COMMENT ON COLUMN mr_surgery.mr_no IS 'MR Surgery MR No';
COMMENT ON COLUMN mr_surgery.surgery_name IS 'MR Surgery Surgery Name';
COMMENT ON COLUMN mr_surgery.surgery_code IS 'MR Surgery Surgery Code';
COMMENT ON COLUMN mr_surgery.surgical_level IS 'MR Surgery Surgical Level';
COMMENT ON COLUMN mr_surgery.surgial_incision_level IS 'MR Surgery Surgical Incision Level';
COMMENT ON COLUMN mr_surgery.surgical_incisionheal_level IS 'MR Surgery Surgical Incision healing Level';
COMMENT ON COLUMN mr_surgery.anesthesia_method IS 'MR Surgery Anesthesia Method';
COMMENT ON COLUMN mr_surgery.anesthesia_level IS 'MR Surgery Anesthesia Level';
COMMENT ON COLUMN mr_surgery.surgery_begin_datetime IS 'MR Surgery Surgery Begin Date time';
COMMENT ON COLUMN mr_surgery.surgery_end_datetime IS 'MR Surgery Surgery End Date time';
COMMENT ON COLUMN mr_surgery.surgery_duration IS 'MR Surgery Surgery Duration';
COMMENT ON COLUMN mr_surgery.surgeon IS 'MR Surgery Surgeon';
COMMENT ON COLUMN mr_surgery.surgeon_physician_code IS 'MR Surgery Surgeon Physician Code';
COMMENT ON COLUMN mr_surgery.first_assistant IS 'MR Surgery First Assistant';
COMMENT ON COLUMN mr_surgery.second_assistant IS 'MR Surgery Second Assistant';
COMMENT ON COLUMN mr_surgery.anesthesiologist IS 'MR Surgery Anesthesiologist';
COMMENT ON COLUMN mr_surgery.anesthesiologist_code IS 'MR Surgery Anesthesiologist Code';
COMMENT ON COLUMN mr_surgery.main_surgery_sign IS 'MR Surgery Main Surgery Signature';
COMMENT ON COLUMN mr_surgery.unplanned_reoperation IS 'MR Surgery Unplanned Reoperation';
COMMENT ON COLUMN mr_surgery.last_modifier IS 'MR Surgery Last Modifier';
COMMENT ON COLUMN mr_surgery.last_modifier_id IS 'MR Surgery Last Modifier ID';
COMMENT ON COLUMN mr_surgery.last_modified_datetime IS 'MR Surgery Last Modified Date time';
COMMENT ON COLUMN mr_surgery.update_time IS 'MR Surgery Update Time';
COMMENT ON COLUMN mr_cost.institute_id IS 'MR Cost Institute ID';
COMMENT ON COLUMN mr_cost.patient_id IS 'MR Cost Patient ID';
COMMENT ON COLUMN mr_cost.visit_id IS 'MR Cost Visit ID';
COMMENT ON COLUMN mr_cost.visit_type IS 'MR Cost Visit Type';
COMMENT ON COLUMN mr_cost.document_id IS 'MR Cost Document ID';
COMMENT ON COLUMN mr_cost.inpat_no IS 'MR Cost Inpatient No';
COMMENT ON COLUMN mr_cost.mr_no IS 'MR Cost MR No';
COMMENT ON COLUMN mr_cost.total_cost IS 'MR Cost Total Cost';
COMMENT ON COLUMN mr_cost.self_pay IS 'MR Cost Self Pay';
COMMENT ON COLUMN mr_cost.general_medical_service_fee IS 'MR Cost General Medical Service Fee';
COMMENT ON COLUMN mr_cost.general_treatment_fee IS 'MR Cost General Treatment Fee';
COMMENT ON COLUMN mr_cost.nursing_care_fee IS 'MR Cost Nursing Care Fee';
COMMENT ON COLUMN mr_cost.other_service_fee IS 'MR Cost Other Service Fee';
COMMENT ON COLUMN mr_cost.pathological_diagnostic_fee IS 'MR Cost Pathological Diagnostic Fee';
COMMENT ON COLUMN mr_cost.laboratory_diagnostic_fee IS 'MR Cost Laboratory Diagnostic Fee';
COMMENT ON COLUMN mr_cost.imaging_diagnostic_fee IS 'MR Cost Imaging Diagnostic Fee';
COMMENT ON COLUMN mr_cost.clinical_diagnostic_fee IS 'MR Cost Clinical Diagnostic Fee';
COMMENT ON COLUMN mr_cost.nonsurgical_treatment_fee IS 'MR Cost Nonsurgical Treatment Fee';
COMMENT ON COLUMN mr_cost.clinical_physical_therapy_fee IS 'MR Cost Clinical Physical Therapy Fee';
COMMENT ON COLUMN mr_cost.surgery_treatment_fee IS 'MR Cost Surgery Treatment Fee';
COMMENT ON COLUMN mr_cost.anesthesia_fee IS 'MR Cost Anesthesia Fee';
COMMENT ON COLUMN mr_cost.surgery_fee IS 'MR Cost Surgery Fee';
COMMENT ON COLUMN mr_cost.rehabilitation_fee IS 'MR Cost Rehabilitation Fee';
COMMENT ON COLUMN mr_cost.western_medicine_fee IS 'MR Cost Western Medicine Fee';
COMMENT ON COLUMN mr_cost.antibacterial_drug_fee IS 'MR Cost Antibacterial Drug Fee';
COMMENT ON COLUMN mr_cost.chinese_patent_medcine_fee IS 'MR Cost Chinese Patent Medcine Fee';
COMMENT ON COLUMN mr_cost.chinese_herbal_medicine_fee IS 'MR Cost Chinese Herbal Medicine Fee';
COMMENT ON COLUMN mr_cost.blood_fee IS 'MR Cost Blood Fee';
COMMENT ON COLUMN mr_cost.treat_disposable_mat_fee IS 'MR Cost Treat Disposable Mat Fee';
COMMENT ON COLUMN mr_cost.exam_disposable_mat_fee IS 'MR Cost Exam Disposable Mat Fee';
COMMENT ON COLUMN mr_cost.surgery_disposable_mat_fee IS 'MR Cost Surgery Disposable Mat Fee';
COMMENT ON COLUMN mr_cost.other_fee IS 'MR Cost Other Fee';
COMMENT ON COLUMN mr_cost.settle_datetime IS 'MR Cost Settle Date time';
COMMENT ON COLUMN mr_cost.last_modifier IS 'MR Cost Last Modifier';
COMMENT ON COLUMN mr_cost.last_modifier_id IS 'MR Cost Last Modifier ID';
COMMENT ON COLUMN mr_cost.last_modified_datetime IS 'MR Cost Last Modified Date time';
COMMENT ON COLUMN mr_cost.update_time IS 'MR Cost Update Time';
COMMENT ON COLUMN diagnosis.institute_id IS 'Diagnosis Institute ID';
COMMENT ON COLUMN diagnosis.patient_id IS 'Diagnosis Patient ID';
COMMENT ON COLUMN diagnosis.visit_id IS 'Diagnosis Visit ID';
COMMENT ON COLUMN diagnosis.visit_type IS 'Diagnosis Visit Type';
COMMENT ON COLUMN diagnosis.document_id IS 'Diagnosis Document ID';
COMMENT ON COLUMN diagnosis.diagnosis_id IS 'Diagnosis Diagnosis ID';
COMMENT ON COLUMN diagnosis.inpat_no IS 'Diagnosis Inpatient No';
COMMENT ON COLUMN diagnosis.dept_name IS 'Diagnosis Department Name';
COMMENT ON COLUMN diagnosis.name IS 'Diagnosis Name';
COMMENT ON COLUMN diagnosis.sex IS 'Diagnosis Sex';
COMMENT ON COLUMN diagnosis.diagnosis_type IS 'Diagnosis Diagnosis Type';
COMMENT ON COLUMN diagnosis.diagnosis_no IS 'Diagnosis Diagnosis No';
COMMENT ON COLUMN diagnosis.diagnosis_name IS 'Diagnosis Diagnosis Name';
COMMENT ON COLUMN diagnosis.diagnosis_code IS 'Diagnosis Diagnosis Code';
COMMENT ON COLUMN diagnosis.pathology_id IS 'Diagnosis Pathology ID';
COMMENT ON COLUMN diagnosis.admission_condition IS 'Diagnosis Admission Condition';
COMMENT ON COLUMN diagnosis.discharge_condition IS 'Diagnosis Discharge Condition';
COMMENT ON COLUMN diagnosis.diagnosis_source IS 'Diagnosis Diagnosis Source';
COMMENT ON COLUMN diagnosis.diagnosis_datetime IS 'Diagnosis Diagnosis Date time';
COMMENT ON COLUMN diagnosis.diagnosis_updatetime IS 'Diagnosis Diagnosis Updatetime';
COMMENT ON COLUMN diagnosis.last_modifier IS 'Diagnosis Last Modifier';
COMMENT ON COLUMN diagnosis.last_modifier_id IS 'Diagnosis Last Modifier ID';
COMMENT ON COLUMN diagnosis.last_modified_datetime IS 'Diagnosis Last Modified Date time';
COMMENT ON COLUMN diagnosis.update_time IS 'Diagnosis Update Time';
COMMENT ON COLUMN admission_record.institute_id IS 'Admission Record Institute ID';
COMMENT ON COLUMN admission_record.patient_id IS 'Admission Record Patient ID';
COMMENT ON COLUMN admission_record.visit_id IS 'Admission Record Visit ID';
COMMENT ON COLUMN admission_record.visit_type IS 'Admission Record Visit Type';
COMMENT ON COLUMN admission_record.admission_datetime IS 'Admission Record Admission Date time';
COMMENT ON COLUMN admission_record.admission_route IS 'Admission Record Admission Route';
COMMENT ON COLUMN admission_record.dept_name IS 'Admission Record Department Name';
COMMENT ON COLUMN admission_record.ward_name IS 'Admission Record Ward Name';
COMMENT ON COLUMN admission_record.ward_no IS 'Admission Record Ward No';
COMMENT ON COLUMN admission_record.bed_no IS 'Admission Record Bed No';
COMMENT ON COLUMN admission_record.admission_reason IS 'Admission Record Admission Reason';
COMMENT ON COLUMN admission_record.chief_complaint IS 'Admission Record Chief Complaint';
COMMENT ON COLUMN admission_record.history_of_present_illness IS 'Admission Record History OF Present Illness';
COMMENT ON COLUMN admission_record.past_history IS 'Admission Record Past History';
COMMENT ON COLUMN admission_record.allergy_history IS 'Admission Record Allergy History';
COMMENT ON COLUMN admission_record.personal_history IS 'Admission Record Personal History';
COMMENT ON COLUMN admission_record.family_history IS 'Admission Record Family History';
COMMENT ON COLUMN admission_record.checkup IS 'Admission Record Checkup';
COMMENT ON COLUMN admission_record.checkup_temperature IS 'Admission Record Checkup Temperature';
COMMENT ON COLUMN admission_record.checkup_heartrate IS 'Admission Record Checkup Heartrate';
COMMENT ON COLUMN admission_record.checkup_respiratoryrate IS 'Admission Record Checkup Respiratoryrate';
COMMENT ON COLUMN admission_record.checkup_systolicpressure IS 'Admission Record Checkup Systolicpressure';
COMMENT ON COLUMN admission_record.checkup_diastolicpressure IS 'Admission Record Checkup Diastolicpressure';
COMMENT ON COLUMN admission_record.checkup_height IS 'Admission Record Checkup Height';
COMMENT ON COLUMN admission_record.checkup_weight IS 'Admission Record Checkup Weight';
COMMENT ON COLUMN admission_record.assist_exam IS 'Admission Record Assist Exam';
COMMENT ON COLUMN admission_record.record_content IS 'Admission Record Record Content';
COMMENT ON COLUMN admission_record.resident_physician_sign IS 'Admission Record Resident Physician Signature';
COMMENT ON COLUMN admission_record.attending_physician_sign IS 'Admission Record Attending Physician Signature';
COMMENT ON COLUMN admission_record.chief_physician_sign IS 'Admission Record Chief Physician Signature';
COMMENT ON COLUMN admission_record.last_modifier IS 'Admission Record Last Modifier';
COMMENT ON COLUMN admission_record.last_modifier_id IS 'Admission Record Last Modifier ID';
COMMENT ON COLUMN admission_record.last_modified_datetime IS 'Admission Record Last Modified Date time';
COMMENT ON COLUMN admission_record.update_time IS 'Admission Record Update Time';
COMMENT ON COLUMN admission_record.document_id IS 'Admission Record Document ID';
COMMENT ON COLUMN admission_record.document_title IS 'Admission Record Document Title';
COMMENT ON COLUMN admission_record.document_status IS 'Admission Record Document Status';
COMMENT ON COLUMN admission_record.submitter IS 'Admission Record Submitter';
COMMENT ON COLUMN admission_record.submitter_id IS 'Admission Record Submitter ID';
COMMENT ON COLUMN admission_record.submit_datetime IS 'Admission Record Submit Date time';
COMMENT ON COLUMN admission_record.inpat_no IS 'Admission Record Inpatient No';
COMMENT ON COLUMN admission_record.mr_no IS 'Admission Record MR No';
COMMENT ON COLUMN admission_record.name IS 'Admission Record Name';
COMMENT ON COLUMN admission_record.sex IS 'Admission Record Sex';
COMMENT ON COLUMN admission_record.age_year IS 'Admission Record Age Year';
COMMENT ON COLUMN admission_record.age_month IS 'Admission Record Age Month';
COMMENT ON COLUMN admission_record.age IS 'Admission Record Age';
COMMENT ON COLUMN discharge_record.institute_id IS 'Discharge Record Institute ID';
COMMENT ON COLUMN discharge_record.patient_id IS 'Discharge Record Patient ID';
COMMENT ON COLUMN discharge_record.visit_id IS 'Discharge Record Visit ID';
COMMENT ON COLUMN discharge_record.visit_type IS 'Discharge Record Visit Type';
COMMENT ON COLUMN discharge_record.dept_name IS 'Discharge Record Department Name';
COMMENT ON COLUMN discharge_record.ward_name IS 'Discharge Record Ward Name';
COMMENT ON COLUMN discharge_record.admission_date IS 'Discharge Record Admission Date';
COMMENT ON COLUMN discharge_record.discharge_date IS 'Discharge Record Discharge Date';
COMMENT ON COLUMN discharge_record.inpatient_duration IS 'Discharge Record Inpatient Duration';
COMMENT ON COLUMN discharge_record.admission_condition IS 'Discharge Record Admission Condition';
COMMENT ON COLUMN discharge_record.positive_assist_exam IS 'Discharge Record Positive Assist Exam';
COMMENT ON COLUMN discharge_record.treatment_course IS 'Discharge Record Treatment Course';
COMMENT ON COLUMN discharge_record.discharge_condition IS 'Discharge Record Discharge Condition';
COMMENT ON COLUMN discharge_record.discharge_order IS 'Discharge Record Discharge Order';
COMMENT ON COLUMN discharge_record.condition_transform IS 'Discharge Record Condition Transform';
COMMENT ON COLUMN discharge_record.record_content IS 'Discharge Record Record Content';
COMMENT ON COLUMN discharge_record.resident_physician_sign IS 'Discharge Record Resident Physician Signature';
COMMENT ON COLUMN discharge_record.attending_physician_sign IS 'Discharge Record Attending Physician Signature';
COMMENT ON COLUMN discharge_record.chief_physician_sign IS 'Discharge Record Chief Physician Signature';
COMMENT ON COLUMN discharge_record.last_modifier IS 'Discharge Record Last Modifier';
COMMENT ON COLUMN discharge_record.last_modifier_id IS 'Discharge Record Last Modifier ID';
COMMENT ON COLUMN discharge_record.last_modified_datetime IS 'Discharge Record Last Modified Date time';
COMMENT ON COLUMN discharge_record.update_time IS 'Discharge Record Update Time';
COMMENT ON COLUMN discharge_record.document_id IS 'Discharge Record Document ID';
COMMENT ON COLUMN discharge_record.document_title IS 'Discharge Record Document Title';
COMMENT ON COLUMN discharge_record.document_status IS 'Discharge Record Document Status';
COMMENT ON COLUMN discharge_record.submitter IS 'Discharge Record Submitter';
COMMENT ON COLUMN discharge_record.submitter_id IS 'Discharge Record Submitter ID';
COMMENT ON COLUMN discharge_record.submit_datetime IS 'Discharge Record Submit Date time';
COMMENT ON COLUMN discharge_record.inpat_no IS 'Discharge Record Inpatient No';
COMMENT ON COLUMN discharge_record.mr_no IS 'Discharge Record MR No';
COMMENT ON COLUMN discharge_record.name IS 'Discharge Record Name';
COMMENT ON COLUMN discharge_record.sex IS 'Discharge Record Sex';
COMMENT ON COLUMN discharge_record.age_year IS 'Discharge Record Age Year';
COMMENT ON COLUMN discharge_record.age_month IS 'Discharge Record Age Month';
COMMENT ON COLUMN discharge_record.age IS 'Discharge Record Age';
COMMENT ON COLUMN qc_result.id IS 'QC Result ID';
COMMENT ON COLUMN qc_result.institute_id IS 'QC Result Institute ID';
COMMENT ON COLUMN qc_result.patient_id IS 'QC Result Patient ID';
COMMENT ON COLUMN qc_result.visit_id IS 'QC Result Visit ID';
COMMENT ON COLUMN qc_result.qc_type IS 'QC Result QC Type';
COMMENT ON COLUMN qc_result.rule_id IS 'QC Result Rule ID';
COMMENT ON COLUMN qc_result.rule_name IS 'QC Result Rule Name';
COMMENT ON COLUMN qc_result.severity IS 'QC Result Severity';
COMMENT ON COLUMN qc_result.category IS 'QC Result Category';
COMMENT ON COLUMN qc_result.description IS 'QC Result Description';
COMMENT ON COLUMN qc_result.suggestion IS 'QC Result Suggestion';
COMMENT ON COLUMN qc_result.field_path IS 'QC Result Field Path';
COMMENT ON COLUMN qc_result.status IS 'QC Result Status';
COMMENT ON COLUMN qc_result.resolved_by IS 'QC Result Resolved BY';
COMMENT ON COLUMN qc_result.resolved_at IS 'QC Result Resolved AT';
COMMENT ON COLUMN qc_result.created_at IS 'QC Result Created AT';
COMMENT ON COLUMN qc_result.updated_at IS 'QC Result Updated AT';
COMMENT ON COLUMN first_course_record.institute_id IS 'First Course Record Institute ID';
COMMENT ON COLUMN first_course_record.patient_id IS 'First Course Record Patient ID';
COMMENT ON COLUMN first_course_record.visit_id IS 'First Course Record Visit ID';
COMMENT ON COLUMN first_course_record.document_id IS 'First Course Record Document ID';
COMMENT ON COLUMN first_course_record.visit_type IS 'First Course Record Visit Type';
COMMENT ON COLUMN first_course_record.record_content IS 'First Course Record Record Content';
COMMENT ON COLUMN first_course_record.last_modifier IS 'First Course Record Last Modifier';
COMMENT ON COLUMN first_course_record.last_modifier_id IS 'First Course Record Last Modifier ID';
COMMENT ON COLUMN first_course_record.last_modified_datetime IS 'First Course Record Last Modified Date time';
COMMENT ON COLUMN first_course_record.update_time IS 'First Course Record Update Time';
COMMENT ON COLUMN first_course_record.document_title IS 'First Course Record Document Title';
COMMENT ON COLUMN first_course_record.document_status IS 'First Course Record Document Status';
COMMENT ON COLUMN first_course_record.submitter IS 'First Course Record Submitter';
COMMENT ON COLUMN first_course_record.submitter_id IS 'First Course Record Submitter ID';
COMMENT ON COLUMN first_course_record.submit_datetime IS 'First Course Record Submit Date time';
COMMENT ON COLUMN first_course_record.inpat_no IS 'First Course Record Inpatient No';
COMMENT ON COLUMN first_course_record.mr_no IS 'First Course Record MR No';
COMMENT ON COLUMN first_course_record.name IS 'First Course Record Name';
COMMENT ON COLUMN first_course_record.sex IS 'First Course Record Sex';
COMMENT ON COLUMN first_course_record.age_year IS 'First Course Record Age Year';
COMMENT ON COLUMN first_course_record.age_month IS 'First Course Record Age Month';
COMMENT ON COLUMN first_course_record.age IS 'First Course Record Age';
COMMENT ON COLUMN daily_course_record.institute_id IS 'Daily Course Record Institute ID';
COMMENT ON COLUMN daily_course_record.patient_id IS 'Daily Course Record Patient ID';
COMMENT ON COLUMN daily_course_record.visit_id IS 'Daily Course Record Visit ID';
COMMENT ON COLUMN daily_course_record.document_id IS 'Daily Course Record Document ID';
COMMENT ON COLUMN daily_course_record.visit_type IS 'Daily Course Record Visit Type';
COMMENT ON COLUMN daily_course_record.record_content IS 'Daily Course Record Record Content';
COMMENT ON COLUMN daily_course_record.last_modifier IS 'Daily Course Record Last Modifier';
COMMENT ON COLUMN daily_course_record.last_modifier_id IS 'Daily Course Record Last Modifier ID';
COMMENT ON COLUMN daily_course_record.last_modified_datetime IS 'Daily Course Record Last Modified Date time';
COMMENT ON COLUMN daily_course_record.update_time IS 'Daily Course Record Update Time';
COMMENT ON COLUMN daily_course_record.document_title IS 'Daily Course Record Document Title';
COMMENT ON COLUMN daily_course_record.document_status IS 'Daily Course Record Document Status';
COMMENT ON COLUMN daily_course_record.submitter IS 'Daily Course Record Submitter';
COMMENT ON COLUMN daily_course_record.submitter_id IS 'Daily Course Record Submitter ID';
COMMENT ON COLUMN daily_course_record.submit_datetime IS 'Daily Course Record Submit Date time';
COMMENT ON COLUMN daily_course_record.inpat_no IS 'Daily Course Record Inpatient No';
COMMENT ON COLUMN daily_course_record.mr_no IS 'Daily Course Record MR No';
COMMENT ON COLUMN daily_course_record.name IS 'Daily Course Record Name';
COMMENT ON COLUMN daily_course_record.sex IS 'Daily Course Record Sex';
COMMENT ON COLUMN daily_course_record.age_year IS 'Daily Course Record Age Year';
COMMENT ON COLUMN daily_course_record.age_month IS 'Daily Course Record Age Month';
COMMENT ON COLUMN daily_course_record.age IS 'Daily Course Record Age';
COMMENT ON COLUMN senior_course_record.institute_id IS 'Senior Course Record Institute ID';
COMMENT ON COLUMN senior_course_record.patient_id IS 'Senior Course Record Patient ID';
COMMENT ON COLUMN senior_course_record.visit_id IS 'Senior Course Record Visit ID';
COMMENT ON COLUMN senior_course_record.document_id IS 'Senior Course Record Document ID';
COMMENT ON COLUMN senior_course_record.visit_type IS 'Senior Course Record Visit Type';
COMMENT ON COLUMN senior_course_record.record_content IS 'Senior Course Record Record Content';
COMMENT ON COLUMN senior_course_record.last_modifier IS 'Senior Course Record Last Modifier';
COMMENT ON COLUMN senior_course_record.last_modifier_id IS 'Senior Course Record Last Modifier ID';
COMMENT ON COLUMN senior_course_record.last_modified_datetime IS 'Senior Course Record Last Modified Date time';
COMMENT ON COLUMN senior_course_record.update_time IS 'Senior Course Record Update Time';
COMMENT ON COLUMN senior_course_record.document_title IS 'Senior Course Record Document Title';
COMMENT ON COLUMN senior_course_record.document_status IS 'Senior Course Record Document Status';
COMMENT ON COLUMN senior_course_record.submitter IS 'Senior Course Record Submitter';
COMMENT ON COLUMN senior_course_record.submitter_id IS 'Senior Course Record Submitter ID';
COMMENT ON COLUMN senior_course_record.submit_datetime IS 'Senior Course Record Submit Date time';
COMMENT ON COLUMN senior_course_record.inpat_no IS 'Senior Course Record Inpatient No';
COMMENT ON COLUMN senior_course_record.mr_no IS 'Senior Course Record MR No';
COMMENT ON COLUMN senior_course_record.name IS 'Senior Course Record Name';
COMMENT ON COLUMN senior_course_record.sex IS 'Senior Course Record Sex';
COMMENT ON COLUMN senior_course_record.age_year IS 'Senior Course Record Age Year';
COMMENT ON COLUMN senior_course_record.age_month IS 'Senior Course Record Age Month';
COMMENT ON COLUMN senior_course_record.age IS 'Senior Course Record Age';
COMMENT ON COLUMN postsurg_firstcourse_record.institute_id IS 'Postsurg Firstcourse Record Institute ID';
COMMENT ON COLUMN postsurg_firstcourse_record.patient_id IS 'Postsurg Firstcourse Record Patient ID';
COMMENT ON COLUMN postsurg_firstcourse_record.visit_id IS 'Postsurg Firstcourse Record Visit ID';
COMMENT ON COLUMN postsurg_firstcourse_record.document_id IS 'Postsurg Firstcourse Record Document ID';
COMMENT ON COLUMN postsurg_firstcourse_record.visit_type IS 'Postsurg Firstcourse Record Visit Type';
COMMENT ON COLUMN postsurg_firstcourse_record.record_content IS 'Postsurg Firstcourse Record Record Content';
COMMENT ON COLUMN postsurg_firstcourse_record.last_modifier IS 'Postsurg Firstcourse Record Last Modifier';
COMMENT ON COLUMN postsurg_firstcourse_record.last_modifier_id IS 'Postsurg Firstcourse Record Last Modifier ID';
COMMENT ON COLUMN postsurg_firstcourse_record.last_modified_datetime IS 'Postsurg Firstcourse Record Last Modified Date time';
COMMENT ON COLUMN postsurg_firstcourse_record.update_time IS 'Postsurg Firstcourse Record Update Time';
COMMENT ON COLUMN postsurg_firstcourse_record.document_title IS 'Postsurg Firstcourse Record Document Title';
COMMENT ON COLUMN postsurg_firstcourse_record.document_status IS 'Postsurg Firstcourse Record Document Status';
COMMENT ON COLUMN postsurg_firstcourse_record.submitter IS 'Postsurg Firstcourse Record Submitter';
COMMENT ON COLUMN postsurg_firstcourse_record.submitter_id IS 'Postsurg Firstcourse Record Submitter ID';
COMMENT ON COLUMN postsurg_firstcourse_record.submit_datetime IS 'Postsurg Firstcourse Record Submit Date time';
COMMENT ON COLUMN postsurg_firstcourse_record.inpat_no IS 'Postsurg Firstcourse Record Inpatient No';
COMMENT ON COLUMN postsurg_firstcourse_record.mr_no IS 'Postsurg Firstcourse Record MR No';
COMMENT ON COLUMN postsurg_firstcourse_record.name IS 'Postsurg Firstcourse Record Name';
COMMENT ON COLUMN postsurg_firstcourse_record.sex IS 'Postsurg Firstcourse Record Sex';
COMMENT ON COLUMN postsurg_firstcourse_record.age_year IS 'Postsurg Firstcourse Record Age Year';
COMMENT ON COLUMN postsurg_firstcourse_record.age_month IS 'Postsurg Firstcourse Record Age Month';
COMMENT ON COLUMN postsurg_firstcourse_record.age IS 'Postsurg Firstcourse Record Age';
COMMENT ON COLUMN consultation_record.institute_id IS 'Consultation Record Institute ID';
COMMENT ON COLUMN consultation_record.patient_id IS 'Consultation Record Patient ID';
COMMENT ON COLUMN consultation_record.visit_id IS 'Consultation Record Visit ID';
COMMENT ON COLUMN consultation_record.document_id IS 'Consultation Record Document ID';
COMMENT ON COLUMN consultation_record.visit_type IS 'Consultation Record Visit Type';
COMMENT ON COLUMN consultation_record.record_content IS 'Consultation Record Record Content';
COMMENT ON COLUMN consultation_record.last_modifier IS 'Consultation Record Last Modifier';
COMMENT ON COLUMN consultation_record.last_modifier_id IS 'Consultation Record Last Modifier ID';
COMMENT ON COLUMN consultation_record.last_modified_datetime IS 'Consultation Record Last Modified Date time';
COMMENT ON COLUMN consultation_record.update_time IS 'Consultation Record Update Time';
COMMENT ON COLUMN consultation_record.document_title IS 'Consultation Record Document Title';
COMMENT ON COLUMN consultation_record.document_status IS 'Consultation Record Document Status';
COMMENT ON COLUMN consultation_record.submitter IS 'Consultation Record Submitter';
COMMENT ON COLUMN consultation_record.submitter_id IS 'Consultation Record Submitter ID';
COMMENT ON COLUMN consultation_record.submit_datetime IS 'Consultation Record Submit Date time';
COMMENT ON COLUMN consultation_record.inpat_no IS 'Consultation Record Inpatient No';
COMMENT ON COLUMN consultation_record.mr_no IS 'Consultation Record MR No';
COMMENT ON COLUMN consultation_record.name IS 'Consultation Record Name';
COMMENT ON COLUMN consultation_record.sex IS 'Consultation Record Sex';
COMMENT ON COLUMN consultation_record.age_year IS 'Consultation Record Age Year';
COMMENT ON COLUMN consultation_record.age_month IS 'Consultation Record Age Month';
COMMENT ON COLUMN consultation_record.age IS 'Consultation Record Age';
COMMENT ON COLUMN rescue_record.institute_id IS 'Rescue Record Institute ID';
COMMENT ON COLUMN rescue_record.patient_id IS 'Rescue Record Patient ID';
COMMENT ON COLUMN rescue_record.visit_id IS 'Rescue Record Visit ID';
COMMENT ON COLUMN rescue_record.document_id IS 'Rescue Record Document ID';
COMMENT ON COLUMN rescue_record.visit_type IS 'Rescue Record Visit Type';
COMMENT ON COLUMN rescue_record.record_content IS 'Rescue Record Record Content';
COMMENT ON COLUMN rescue_record.last_modifier IS 'Rescue Record Last Modifier';
COMMENT ON COLUMN rescue_record.last_modifier_id IS 'Rescue Record Last Modifier ID';
COMMENT ON COLUMN rescue_record.last_modified_datetime IS 'Rescue Record Last Modified Date time';
COMMENT ON COLUMN rescue_record.update_time IS 'Rescue Record Update Time';
COMMENT ON COLUMN rescue_record.document_title IS 'Rescue Record Document Title';
COMMENT ON COLUMN rescue_record.document_status IS 'Rescue Record Document Status';
COMMENT ON COLUMN rescue_record.submitter IS 'Rescue Record Submitter';
COMMENT ON COLUMN rescue_record.submitter_id IS 'Rescue Record Submitter ID';
COMMENT ON COLUMN rescue_record.submit_datetime IS 'Rescue Record Submit Date time';
COMMENT ON COLUMN rescue_record.inpat_no IS 'Rescue Record Inpatient No';
COMMENT ON COLUMN rescue_record.mr_no IS 'Rescue Record MR No';
COMMENT ON COLUMN rescue_record.name IS 'Rescue Record Name';
COMMENT ON COLUMN rescue_record.sex IS 'Rescue Record Sex';
COMMENT ON COLUMN rescue_record.age_year IS 'Rescue Record Age Year';
COMMENT ON COLUMN rescue_record.age_month IS 'Rescue Record Age Month';
COMMENT ON COLUMN rescue_record.age IS 'Rescue Record Age';
COMMENT ON COLUMN transfer_in_record.institute_id IS 'Transfer IN Record Institute ID';
COMMENT ON COLUMN transfer_in_record.patient_id IS 'Transfer IN Record Patient ID';
COMMENT ON COLUMN transfer_in_record.visit_id IS 'Transfer IN Record Visit ID';
COMMENT ON COLUMN transfer_in_record.document_id IS 'Transfer IN Record Document ID';
COMMENT ON COLUMN transfer_in_record.visit_type IS 'Transfer IN Record Visit Type';
COMMENT ON COLUMN transfer_in_record.record_content IS 'Transfer IN Record Record Content';
COMMENT ON COLUMN transfer_in_record.last_modifier IS 'Transfer IN Record Last Modifier';
COMMENT ON COLUMN transfer_in_record.last_modifier_id IS 'Transfer IN Record Last Modifier ID';
COMMENT ON COLUMN transfer_in_record.last_modified_datetime IS 'Transfer IN Record Last Modified Date time';
COMMENT ON COLUMN transfer_in_record.update_time IS 'Transfer IN Record Update Time';
COMMENT ON COLUMN transfer_in_record.document_title IS 'Transfer IN Record Document Title';
COMMENT ON COLUMN transfer_in_record.document_status IS 'Transfer IN Record Document Status';
COMMENT ON COLUMN transfer_in_record.submitter IS 'Transfer IN Record Submitter';
COMMENT ON COLUMN transfer_in_record.submitter_id IS 'Transfer IN Record Submitter ID';
COMMENT ON COLUMN transfer_in_record.submit_datetime IS 'Transfer IN Record Submit Date time';
COMMENT ON COLUMN transfer_in_record.inpat_no IS 'Transfer IN Record Inpatient No';
COMMENT ON COLUMN transfer_in_record.mr_no IS 'Transfer IN Record MR No';
COMMENT ON COLUMN transfer_in_record.name IS 'Transfer IN Record Name';
COMMENT ON COLUMN transfer_in_record.sex IS 'Transfer IN Record Sex';
COMMENT ON COLUMN transfer_in_record.age_year IS 'Transfer IN Record Age Year';
COMMENT ON COLUMN transfer_in_record.age_month IS 'Transfer IN Record Age Month';
COMMENT ON COLUMN transfer_in_record.age IS 'Transfer IN Record Age';
COMMENT ON COLUMN transfer_out_record.institute_id IS 'Transfer Out Record Institute ID';
COMMENT ON COLUMN transfer_out_record.patient_id IS 'Transfer Out Record Patient ID';
COMMENT ON COLUMN transfer_out_record.visit_id IS 'Transfer Out Record Visit ID';
COMMENT ON COLUMN transfer_out_record.document_id IS 'Transfer Out Record Document ID';
COMMENT ON COLUMN transfer_out_record.visit_type IS 'Transfer Out Record Visit Type';
COMMENT ON COLUMN transfer_out_record.record_content IS 'Transfer Out Record Record Content';
COMMENT ON COLUMN transfer_out_record.last_modifier IS 'Transfer Out Record Last Modifier';
COMMENT ON COLUMN transfer_out_record.last_modifier_id IS 'Transfer Out Record Last Modifier ID';
COMMENT ON COLUMN transfer_out_record.last_modified_datetime IS 'Transfer Out Record Last Modified Date time';
COMMENT ON COLUMN transfer_out_record.update_time IS 'Transfer Out Record Update Time';
COMMENT ON COLUMN transfer_out_record.document_title IS 'Transfer Out Record Document Title';
COMMENT ON COLUMN transfer_out_record.document_status IS 'Transfer Out Record Document Status';
COMMENT ON COLUMN transfer_out_record.submitter IS 'Transfer Out Record Submitter';
COMMENT ON COLUMN transfer_out_record.submitter_id IS 'Transfer Out Record Submitter ID';
COMMENT ON COLUMN transfer_out_record.submit_datetime IS 'Transfer Out Record Submit Date time';
COMMENT ON COLUMN transfer_out_record.inpat_no IS 'Transfer Out Record Inpatient No';
COMMENT ON COLUMN transfer_out_record.mr_no IS 'Transfer Out Record MR No';
COMMENT ON COLUMN transfer_out_record.name IS 'Transfer Out Record Name';
COMMENT ON COLUMN transfer_out_record.sex IS 'Transfer Out Record Sex';
COMMENT ON COLUMN transfer_out_record.age_year IS 'Transfer Out Record Age Year';
COMMENT ON COLUMN transfer_out_record.age_month IS 'Transfer Out Record Age Month';
COMMENT ON COLUMN transfer_out_record.age IS 'Transfer Out Record Age';
COMMENT ON COLUMN surgery_record.institute_id IS 'Surgery Record Institute ID';
COMMENT ON COLUMN surgery_record.patient_id IS 'Surgery Record Patient ID';
COMMENT ON COLUMN surgery_record.visit_id IS 'Surgery Record Visit ID';
COMMENT ON COLUMN surgery_record.document_id IS 'Surgery Record Document ID';
COMMENT ON COLUMN surgery_record.visit_type IS 'Surgery Record Visit Type';
COMMENT ON COLUMN surgery_record.record_content IS 'Surgery Record Record Content';
COMMENT ON COLUMN surgery_record.last_modifier IS 'Surgery Record Last Modifier';
COMMENT ON COLUMN surgery_record.last_modifier_id IS 'Surgery Record Last Modifier ID';
COMMENT ON COLUMN surgery_record.last_modified_datetime IS 'Surgery Record Last Modified Date time';
COMMENT ON COLUMN surgery_record.update_time IS 'Surgery Record Update Time';
COMMENT ON COLUMN surgery_record.document_title IS 'Surgery Record Document Title';
COMMENT ON COLUMN surgery_record.document_status IS 'Surgery Record Document Status';
COMMENT ON COLUMN surgery_record.submitter IS 'Surgery Record Submitter';
COMMENT ON COLUMN surgery_record.submitter_id IS 'Surgery Record Submitter ID';
COMMENT ON COLUMN surgery_record.submit_datetime IS 'Surgery Record Submit Date time';
COMMENT ON COLUMN surgery_record.inpat_no IS 'Surgery Record Inpatient No';
COMMENT ON COLUMN surgery_record.mr_no IS 'Surgery Record MR No';
COMMENT ON COLUMN surgery_record.name IS 'Surgery Record Name';
COMMENT ON COLUMN surgery_record.sex IS 'Surgery Record Sex';
COMMENT ON COLUMN surgery_record.age_year IS 'Surgery Record Age Year';
COMMENT ON COLUMN surgery_record.age_month IS 'Surgery Record Age Month';
COMMENT ON COLUMN surgery_record.age IS 'Surgery Record Age';
COMMENT ON COLUMN labtest_item_report.institute_id IS 'Labtest Item Report Institute ID';
COMMENT ON COLUMN labtest_item_report.patient_id IS 'Labtest Item Report Patient ID';
COMMENT ON COLUMN labtest_item_report.visit_id IS 'Labtest Item Report Visit ID';
COMMENT ON COLUMN labtest_item_report.document_id IS 'Labtest Item Report Document ID';
COMMENT ON COLUMN labtest_item_report.visit_type IS 'Labtest Item Report Visit Type';
COMMENT ON COLUMN labtest_item_report.record_content IS 'Labtest Item Report Record Content';
COMMENT ON COLUMN labtest_item_report.last_modifier IS 'Labtest Item Report Last Modifier';
COMMENT ON COLUMN labtest_item_report.last_modifier_id IS 'Labtest Item Report Last Modifier ID';
COMMENT ON COLUMN labtest_item_report.last_modified_datetime IS 'Labtest Item Report Last Modified Date time';
COMMENT ON COLUMN labtest_item_report.update_time IS 'Labtest Item Report Update Time';
COMMENT ON COLUMN labtest_item_report.document_title IS 'Labtest Item Report Document Title';
COMMENT ON COLUMN labtest_item_report.document_status IS 'Labtest Item Report Document Status';
COMMENT ON COLUMN labtest_item_report.submitter IS 'Labtest Item Report Submitter';
COMMENT ON COLUMN labtest_item_report.submitter_id IS 'Labtest Item Report Submitter ID';
COMMENT ON COLUMN labtest_item_report.submit_datetime IS 'Labtest Item Report Submit Date time';
COMMENT ON COLUMN labtest_item_report.inpat_no IS 'Labtest Item Report Inpatient No';
COMMENT ON COLUMN labtest_item_report.mr_no IS 'Labtest Item Report MR No';
COMMENT ON COLUMN labtest_item_report.name IS 'Labtest Item Report Name';
COMMENT ON COLUMN labtest_item_report.sex IS 'Labtest Item Report Sex';
COMMENT ON COLUMN labtest_item_report.age_year IS 'Labtest Item Report Age Year';
COMMENT ON COLUMN labtest_item_report.age_month IS 'Labtest Item Report Age Month';
COMMENT ON COLUMN labtest_item_report.age IS 'Labtest Item Report Age';
COMMENT ON COLUMN exam_item_report.institute_id IS 'Exam Item Report Institute ID';
COMMENT ON COLUMN exam_item_report.patient_id IS 'Exam Item Report Patient ID';
COMMENT ON COLUMN exam_item_report.visit_id IS 'Exam Item Report Visit ID';
COMMENT ON COLUMN exam_item_report.document_id IS 'Exam Item Report Document ID';
COMMENT ON COLUMN exam_item_report.visit_type IS 'Exam Item Report Visit Type';
COMMENT ON COLUMN exam_item_report.record_content IS 'Exam Item Report Record Content';
COMMENT ON COLUMN exam_item_report.last_modifier IS 'Exam Item Report Last Modifier';
COMMENT ON COLUMN exam_item_report.last_modifier_id IS 'Exam Item Report Last Modifier ID';
COMMENT ON COLUMN exam_item_report.last_modified_datetime IS 'Exam Item Report Last Modified Date time';
COMMENT ON COLUMN exam_item_report.update_time IS 'Exam Item Report Update Time';
COMMENT ON COLUMN exam_item_report.document_title IS 'Exam Item Report Document Title';
COMMENT ON COLUMN exam_item_report.document_status IS 'Exam Item Report Document Status';
COMMENT ON COLUMN exam_item_report.submitter IS 'Exam Item Report Submitter';
COMMENT ON COLUMN exam_item_report.submitter_id IS 'Exam Item Report Submitter ID';
COMMENT ON COLUMN exam_item_report.submit_datetime IS 'Exam Item Report Submit Date time';
COMMENT ON COLUMN exam_item_report.inpat_no IS 'Exam Item Report Inpatient No';
COMMENT ON COLUMN exam_item_report.mr_no IS 'Exam Item Report MR No';
COMMENT ON COLUMN exam_item_report.name IS 'Exam Item Report Name';
COMMENT ON COLUMN exam_item_report.sex IS 'Exam Item Report Sex';
COMMENT ON COLUMN exam_item_report.age_year IS 'Exam Item Report Age Year';
COMMENT ON COLUMN exam_item_report.age_month IS 'Exam Item Report Age Month';
COMMENT ON COLUMN exam_item_report.age IS 'Exam Item Report Age';
COMMENT ON COLUMN diffcase_discussion_record.institute_id IS 'Diffcase Discussion Record Institute ID';
COMMENT ON COLUMN diffcase_discussion_record.patient_id IS 'Diffcase Discussion Record Patient ID';
COMMENT ON COLUMN diffcase_discussion_record.visit_id IS 'Diffcase Discussion Record Visit ID';
COMMENT ON COLUMN diffcase_discussion_record.document_id IS 'Diffcase Discussion Record Document ID';
COMMENT ON COLUMN diffcase_discussion_record.visit_type IS 'Diffcase Discussion Record Visit Type';
COMMENT ON COLUMN diffcase_discussion_record.record_content IS 'Diffcase Discussion Record Record Content';
COMMENT ON COLUMN diffcase_discussion_record.last_modifier IS 'Diffcase Discussion Record Last Modifier';
COMMENT ON COLUMN diffcase_discussion_record.last_modifier_id IS 'Diffcase Discussion Record Last Modifier ID';
COMMENT ON COLUMN diffcase_discussion_record.last_modified_datetime IS 'Diffcase Discussion Record Last Modified Date time';
COMMENT ON COLUMN diffcase_discussion_record.update_time IS 'Diffcase Discussion Record Update Time';
COMMENT ON COLUMN diffcase_discussion_record.document_title IS 'Diffcase Discussion Record Document Title';
COMMENT ON COLUMN diffcase_discussion_record.document_status IS 'Diffcase Discussion Record Document Status';
COMMENT ON COLUMN diffcase_discussion_record.submitter IS 'Diffcase Discussion Record Submitter';
COMMENT ON COLUMN diffcase_discussion_record.submitter_id IS 'Diffcase Discussion Record Submitter ID';
COMMENT ON COLUMN diffcase_discussion_record.submit_datetime IS 'Diffcase Discussion Record Submit Date time';
COMMENT ON COLUMN diffcase_discussion_record.inpat_no IS 'Diffcase Discussion Record Inpatient No';
COMMENT ON COLUMN diffcase_discussion_record.mr_no IS 'Diffcase Discussion Record MR No';
COMMENT ON COLUMN diffcase_discussion_record.name IS 'Diffcase Discussion Record Name';
COMMENT ON COLUMN diffcase_discussion_record.sex IS 'Diffcase Discussion Record Sex';
COMMENT ON COLUMN diffcase_discussion_record.age_year IS 'Diffcase Discussion Record Age Year';
COMMENT ON COLUMN diffcase_discussion_record.age_month IS 'Diffcase Discussion Record Age Month';
COMMENT ON COLUMN diffcase_discussion_record.age IS 'Diffcase Discussion Record Age';
COMMENT ON COLUMN death_discussion.institute_id IS 'Death Discussion Institute ID';
COMMENT ON COLUMN death_discussion.patient_id IS 'Death Discussion Patient ID';
COMMENT ON COLUMN death_discussion.visit_id IS 'Death Discussion Visit ID';
COMMENT ON COLUMN death_discussion.document_id IS 'Death Discussion Document ID';
COMMENT ON COLUMN death_discussion.visit_type IS 'Death Discussion Visit Type';
COMMENT ON COLUMN death_discussion.record_content IS 'Death Discussion Record Content';
COMMENT ON COLUMN death_discussion.last_modifier IS 'Death Discussion Last Modifier';
COMMENT ON COLUMN death_discussion.last_modifier_id IS 'Death Discussion Last Modifier ID';
COMMENT ON COLUMN death_discussion.last_modified_datetime IS 'Death Discussion Last Modified Date time';
COMMENT ON COLUMN death_discussion.update_time IS 'Death Discussion Update Time';
COMMENT ON COLUMN death_discussion.document_title IS 'Death Discussion Document Title';
COMMENT ON COLUMN death_discussion.document_status IS 'Death Discussion Document Status';
COMMENT ON COLUMN death_discussion.submitter IS 'Death Discussion Submitter';
COMMENT ON COLUMN death_discussion.submitter_id IS 'Death Discussion Submitter ID';
COMMENT ON COLUMN death_discussion.submit_datetime IS 'Death Discussion Submit Date time';
COMMENT ON COLUMN death_discussion.inpat_no IS 'Death Discussion Inpatient No';
COMMENT ON COLUMN death_discussion.mr_no IS 'Death Discussion MR No';
COMMENT ON COLUMN death_discussion.name IS 'Death Discussion Name';
COMMENT ON COLUMN death_discussion.sex IS 'Death Discussion Sex';
COMMENT ON COLUMN death_discussion.age_year IS 'Death Discussion Age Year';
COMMENT ON COLUMN death_discussion.age_month IS 'Death Discussion Age Month';
COMMENT ON COLUMN death_discussion.age IS 'Death Discussion Age';
COMMENT ON COLUMN death_record.institute_id IS 'Death Record Institute ID';
COMMENT ON COLUMN death_record.patient_id IS 'Death Record Patient ID';
COMMENT ON COLUMN death_record.visit_id IS 'Death Record Visit ID';
COMMENT ON COLUMN death_record.document_id IS 'Death Record Document ID';
COMMENT ON COLUMN death_record.visit_type IS 'Death Record Visit Type';
COMMENT ON COLUMN death_record.record_content IS 'Death Record Record Content';
COMMENT ON COLUMN death_record.last_modifier IS 'Death Record Last Modifier';
COMMENT ON COLUMN death_record.last_modifier_id IS 'Death Record Last Modifier ID';
COMMENT ON COLUMN death_record.last_modified_datetime IS 'Death Record Last Modified Date time';
COMMENT ON COLUMN death_record.update_time IS 'Death Record Update Time';
COMMENT ON COLUMN death_record.document_title IS 'Death Record Document Title';
COMMENT ON COLUMN death_record.document_status IS 'Death Record Document Status';
COMMENT ON COLUMN death_record.submitter IS 'Death Record Submitter';
COMMENT ON COLUMN death_record.submitter_id IS 'Death Record Submitter ID';
COMMENT ON COLUMN death_record.submit_datetime IS 'Death Record Submit Date time';
COMMENT ON COLUMN death_record.inpat_no IS 'Death Record Inpatient No';
COMMENT ON COLUMN death_record.mr_no IS 'Death Record MR No';
COMMENT ON COLUMN death_record.name IS 'Death Record Name';
COMMENT ON COLUMN death_record.sex IS 'Death Record Sex';
COMMENT ON COLUMN death_record.age_year IS 'Death Record Age Year';
COMMENT ON COLUMN death_record.age_month IS 'Death Record Age Month';
COMMENT ON COLUMN death_record.age IS 'Death Record Age';
COMMENT ON COLUMN handoff_record.institute_id IS 'Handoff Record Institute ID';
COMMENT ON COLUMN handoff_record.patient_id IS 'Handoff Record Patient ID';
COMMENT ON COLUMN handoff_record.visit_id IS 'Handoff Record Visit ID';
COMMENT ON COLUMN handoff_record.document_id IS 'Handoff Record Document ID';
COMMENT ON COLUMN handoff_record.visit_type IS 'Handoff Record Visit Type';
COMMENT ON COLUMN handoff_record.record_content IS 'Handoff Record Record Content';
COMMENT ON COLUMN handoff_record.last_modifier IS 'Handoff Record Last Modifier';
COMMENT ON COLUMN handoff_record.last_modifier_id IS 'Handoff Record Last Modifier ID';
COMMENT ON COLUMN handoff_record.last_modified_datetime IS 'Handoff Record Last Modified Date time';
COMMENT ON COLUMN handoff_record.update_time IS 'Handoff Record Update Time';
COMMENT ON COLUMN handoff_record.document_title IS 'Handoff Record Document Title';
COMMENT ON COLUMN handoff_record.document_status IS 'Handoff Record Document Status';
COMMENT ON COLUMN handoff_record.submitter IS 'Handoff Record Submitter';
COMMENT ON COLUMN handoff_record.submitter_id IS 'Handoff Record Submitter ID';
COMMENT ON COLUMN handoff_record.submit_datetime IS 'Handoff Record Submit Date time';
COMMENT ON COLUMN handoff_record.inpat_no IS 'Handoff Record Inpatient No';
COMMENT ON COLUMN handoff_record.mr_no IS 'Handoff Record MR No';
COMMENT ON COLUMN handoff_record.name IS 'Handoff Record Name';
COMMENT ON COLUMN handoff_record.sex IS 'Handoff Record Sex';
COMMENT ON COLUMN handoff_record.age_year IS 'Handoff Record Age Year';
COMMENT ON COLUMN handoff_record.age_month IS 'Handoff Record Age Month';
COMMENT ON COLUMN handoff_record.age IS 'Handoff Record Age';
COMMENT ON COLUMN handover_record.institute_id IS 'Handover Record Institute ID';
COMMENT ON COLUMN handover_record.patient_id IS 'Handover Record Patient ID';
COMMENT ON COLUMN handover_record.visit_id IS 'Handover Record Visit ID';
COMMENT ON COLUMN handover_record.document_id IS 'Handover Record Document ID';
COMMENT ON COLUMN handover_record.visit_type IS 'Handover Record Visit Type';
COMMENT ON COLUMN handover_record.record_content IS 'Handover Record Record Content';
COMMENT ON COLUMN handover_record.last_modifier IS 'Handover Record Last Modifier';
COMMENT ON COLUMN handover_record.last_modifier_id IS 'Handover Record Last Modifier ID';
COMMENT ON COLUMN handover_record.last_modified_datetime IS 'Handover Record Last Modified Date time';
COMMENT ON COLUMN handover_record.update_time IS 'Handover Record Update Time';
COMMENT ON COLUMN handover_record.document_title IS 'Handover Record Document Title';
COMMENT ON COLUMN handover_record.document_status IS 'Handover Record Document Status';
COMMENT ON COLUMN handover_record.submitter IS 'Handover Record Submitter';
COMMENT ON COLUMN handover_record.submitter_id IS 'Handover Record Submitter ID';
COMMENT ON COLUMN handover_record.submit_datetime IS 'Handover Record Submit Date time';
COMMENT ON COLUMN handover_record.inpat_no IS 'Handover Record Inpatient No';
COMMENT ON COLUMN handover_record.mr_no IS 'Handover Record MR No';
COMMENT ON COLUMN handover_record.name IS 'Handover Record Name';
COMMENT ON COLUMN handover_record.sex IS 'Handover Record Sex';
COMMENT ON COLUMN handover_record.age_year IS 'Handover Record Age Year';
COMMENT ON COLUMN handover_record.age_month IS 'Handover Record Age Month';
COMMENT ON COLUMN handover_record.age IS 'Handover Record Age';
COMMENT ON COLUMN summary_record.institute_id IS 'Summary Record Institute ID';
COMMENT ON COLUMN summary_record.patient_id IS 'Summary Record Patient ID';
COMMENT ON COLUMN summary_record.visit_id IS 'Summary Record Visit ID';
COMMENT ON COLUMN summary_record.document_id IS 'Summary Record Document ID';
COMMENT ON COLUMN summary_record.visit_type IS 'Summary Record Visit Type';
COMMENT ON COLUMN summary_record.record_content IS 'Summary Record Record Content';
COMMENT ON COLUMN summary_record.last_modifier IS 'Summary Record Last Modifier';
COMMENT ON COLUMN summary_record.last_modifier_id IS 'Summary Record Last Modifier ID';
COMMENT ON COLUMN summary_record.last_modified_datetime IS 'Summary Record Last Modified Date time';
COMMENT ON COLUMN summary_record.update_time IS 'Summary Record Update Time';
COMMENT ON COLUMN summary_record.document_title IS 'Summary Record Document Title';
COMMENT ON COLUMN summary_record.document_status IS 'Summary Record Document Status';
COMMENT ON COLUMN summary_record.submitter IS 'Summary Record Submitter';
COMMENT ON COLUMN summary_record.submitter_id IS 'Summary Record Submitter ID';
COMMENT ON COLUMN summary_record.submit_datetime IS 'Summary Record Submit Date time';
COMMENT ON COLUMN summary_record.inpat_no IS 'Summary Record Inpatient No';
COMMENT ON COLUMN summary_record.mr_no IS 'Summary Record MR No';
COMMENT ON COLUMN summary_record.name IS 'Summary Record Name';
COMMENT ON COLUMN summary_record.sex IS 'Summary Record Sex';
COMMENT ON COLUMN summary_record.age_year IS 'Summary Record Age Year';
COMMENT ON COLUMN summary_record.age_month IS 'Summary Record Age Month';
COMMENT ON COLUMN summary_record.age IS 'Summary Record Age';
COMMENT ON COLUMN presurg_summary.institute_id IS 'Presurg Summary Institute ID';
COMMENT ON COLUMN presurg_summary.patient_id IS 'Presurg Summary Patient ID';
COMMENT ON COLUMN presurg_summary.visit_id IS 'Presurg Summary Visit ID';
COMMENT ON COLUMN presurg_summary.document_id IS 'Presurg Summary Document ID';
COMMENT ON COLUMN presurg_summary.visit_type IS 'Presurg Summary Visit Type';
COMMENT ON COLUMN presurg_summary.record_content IS 'Presurg Summary Record Content';
COMMENT ON COLUMN presurg_summary.last_modifier IS 'Presurg Summary Last Modifier';
COMMENT ON COLUMN presurg_summary.last_modifier_id IS 'Presurg Summary Last Modifier ID';
COMMENT ON COLUMN presurg_summary.last_modified_datetime IS 'Presurg Summary Last Modified Date time';
COMMENT ON COLUMN presurg_summary.update_time IS 'Presurg Summary Update Time';
COMMENT ON COLUMN presurg_summary.document_title IS 'Presurg Summary Document Title';
COMMENT ON COLUMN presurg_summary.document_status IS 'Presurg Summary Document Status';
COMMENT ON COLUMN presurg_summary.submitter IS 'Presurg Summary Submitter';
COMMENT ON COLUMN presurg_summary.submitter_id IS 'Presurg Summary Submitter ID';
COMMENT ON COLUMN presurg_summary.submit_datetime IS 'Presurg Summary Submit Date time';
COMMENT ON COLUMN presurg_summary.inpat_no IS 'Presurg Summary Inpatient No';
COMMENT ON COLUMN presurg_summary.mr_no IS 'Presurg Summary MR No';
COMMENT ON COLUMN presurg_summary.name IS 'Presurg Summary Name';
COMMENT ON COLUMN presurg_summary.sex IS 'Presurg Summary Sex';
COMMENT ON COLUMN presurg_summary.age_year IS 'Presurg Summary Age Year';
COMMENT ON COLUMN presurg_summary.age_month IS 'Presurg Summary Age Month';
COMMENT ON COLUMN presurg_summary.age IS 'Presurg Summary Age';
COMMENT ON COLUMN presurg_discussion.institute_id IS 'Presurg Discussion Institute ID';
COMMENT ON COLUMN presurg_discussion.patient_id IS 'Presurg Discussion Patient ID';
COMMENT ON COLUMN presurg_discussion.visit_id IS 'Presurg Discussion Visit ID';
COMMENT ON COLUMN presurg_discussion.document_id IS 'Presurg Discussion Document ID';
COMMENT ON COLUMN presurg_discussion.visit_type IS 'Presurg Discussion Visit Type';
COMMENT ON COLUMN presurg_discussion.record_content IS 'Presurg Discussion Record Content';
COMMENT ON COLUMN presurg_discussion.last_modifier IS 'Presurg Discussion Last Modifier';
COMMENT ON COLUMN presurg_discussion.last_modifier_id IS 'Presurg Discussion Last Modifier ID';
COMMENT ON COLUMN presurg_discussion.last_modified_datetime IS 'Presurg Discussion Last Modified Date time';
COMMENT ON COLUMN presurg_discussion.update_time IS 'Presurg Discussion Update Time';
COMMENT ON COLUMN presurg_discussion.document_title IS 'Presurg Discussion Document Title';
COMMENT ON COLUMN presurg_discussion.document_status IS 'Presurg Discussion Document Status';
COMMENT ON COLUMN presurg_discussion.submitter IS 'Presurg Discussion Submitter';
COMMENT ON COLUMN presurg_discussion.submitter_id IS 'Presurg Discussion Submitter ID';
COMMENT ON COLUMN presurg_discussion.submit_datetime IS 'Presurg Discussion Submit Date time';
COMMENT ON COLUMN presurg_discussion.inpat_no IS 'Presurg Discussion Inpatient No';
COMMENT ON COLUMN presurg_discussion.mr_no IS 'Presurg Discussion MR No';
COMMENT ON COLUMN presurg_discussion.name IS 'Presurg Discussion Name';
COMMENT ON COLUMN presurg_discussion.sex IS 'Presurg Discussion Sex';
COMMENT ON COLUMN presurg_discussion.age_year IS 'Presurg Discussion Age Year';
COMMENT ON COLUMN presurg_discussion.age_month IS 'Presurg Discussion Age Month';
COMMENT ON COLUMN presurg_discussion.age IS 'Presurg Discussion Age';
COMMENT ON COLUMN surgery_safecheck_record.institute_id IS 'Surgery Safecheck Record Institute ID';
COMMENT ON COLUMN surgery_safecheck_record.patient_id IS 'Surgery Safecheck Record Patient ID';
COMMENT ON COLUMN surgery_safecheck_record.visit_id IS 'Surgery Safecheck Record Visit ID';
COMMENT ON COLUMN surgery_safecheck_record.document_id IS 'Surgery Safecheck Record Document ID';
COMMENT ON COLUMN surgery_safecheck_record.visit_type IS 'Surgery Safecheck Record Visit Type';
COMMENT ON COLUMN surgery_safecheck_record.record_content IS 'Surgery Safecheck Record Record Content';
COMMENT ON COLUMN surgery_safecheck_record.last_modifier IS 'Surgery Safecheck Record Last Modifier';
COMMENT ON COLUMN surgery_safecheck_record.last_modifier_id IS 'Surgery Safecheck Record Last Modifier ID';
COMMENT ON COLUMN surgery_safecheck_record.last_modified_datetime IS 'Surgery Safecheck Record Last Modified Date time';
COMMENT ON COLUMN surgery_safecheck_record.update_time IS 'Surgery Safecheck Record Update Time';
COMMENT ON COLUMN surgery_safecheck_record.document_title IS 'Surgery Safecheck Record Document Title';
COMMENT ON COLUMN surgery_safecheck_record.document_status IS 'Surgery Safecheck Record Document Status';
COMMENT ON COLUMN surgery_safecheck_record.submitter IS 'Surgery Safecheck Record Submitter';
COMMENT ON COLUMN surgery_safecheck_record.submitter_id IS 'Surgery Safecheck Record Submitter ID';
COMMENT ON COLUMN surgery_safecheck_record.submit_datetime IS 'Surgery Safecheck Record Submit Date time';
COMMENT ON COLUMN surgery_safecheck_record.inpat_no IS 'Surgery Safecheck Record Inpatient No';
COMMENT ON COLUMN surgery_safecheck_record.mr_no IS 'Surgery Safecheck Record MR No';
COMMENT ON COLUMN surgery_safecheck_record.name IS 'Surgery Safecheck Record Name';
COMMENT ON COLUMN surgery_safecheck_record.sex IS 'Surgery Safecheck Record Sex';
COMMENT ON COLUMN surgery_safecheck_record.age_year IS 'Surgery Safecheck Record Age Year';
COMMENT ON COLUMN surgery_safecheck_record.age_month IS 'Surgery Safecheck Record Age Month';
COMMENT ON COLUMN surgery_safecheck_record.age IS 'Surgery Safecheck Record Age';
COMMENT ON COLUMN surgery_risk_assessment.institute_id IS 'Surgery Risk Assessment Institute ID';
COMMENT ON COLUMN surgery_risk_assessment.patient_id IS 'Surgery Risk Assessment Patient ID';
COMMENT ON COLUMN surgery_risk_assessment.visit_id IS 'Surgery Risk Assessment Visit ID';
COMMENT ON COLUMN surgery_risk_assessment.document_id IS 'Surgery Risk Assessment Document ID';
COMMENT ON COLUMN surgery_risk_assessment.visit_type IS 'Surgery Risk Assessment Visit Type';
COMMENT ON COLUMN surgery_risk_assessment.record_content IS 'Surgery Risk Assessment Record Content';
COMMENT ON COLUMN surgery_risk_assessment.last_modifier IS 'Surgery Risk Assessment Last Modifier';
COMMENT ON COLUMN surgery_risk_assessment.last_modifier_id IS 'Surgery Risk Assessment Last Modifier ID';
COMMENT ON COLUMN surgery_risk_assessment.last_modified_datetime IS 'Surgery Risk Assessment Last Modified Date time';
COMMENT ON COLUMN surgery_risk_assessment.update_time IS 'Surgery Risk Assessment Update Time';
COMMENT ON COLUMN surgery_risk_assessment.document_title IS 'Surgery Risk Assessment Document Title';
COMMENT ON COLUMN surgery_risk_assessment.document_status IS 'Surgery Risk Assessment Document Status';
COMMENT ON COLUMN surgery_risk_assessment.submitter IS 'Surgery Risk Assessment Submitter';
COMMENT ON COLUMN surgery_risk_assessment.submitter_id IS 'Surgery Risk Assessment Submitter ID';
COMMENT ON COLUMN surgery_risk_assessment.submit_datetime IS 'Surgery Risk Assessment Submit Date time';
COMMENT ON COLUMN surgery_risk_assessment.inpat_no IS 'Surgery Risk Assessment Inpatient No';
COMMENT ON COLUMN surgery_risk_assessment.mr_no IS 'Surgery Risk Assessment MR No';
COMMENT ON COLUMN surgery_risk_assessment.name IS 'Surgery Risk Assessment Name';
COMMENT ON COLUMN surgery_risk_assessment.sex IS 'Surgery Risk Assessment Sex';
COMMENT ON COLUMN surgery_risk_assessment.age_year IS 'Surgery Risk Assessment Age Year';
COMMENT ON COLUMN surgery_risk_assessment.age_month IS 'Surgery Risk Assessment Age Month';
COMMENT ON COLUMN surgery_risk_assessment.age IS 'Surgery Risk Assessment Age';
COMMENT ON COLUMN anesthesia_record.institute_id IS 'Anesthesia Record Institute ID';
COMMENT ON COLUMN anesthesia_record.patient_id IS 'Anesthesia Record Patient ID';
COMMENT ON COLUMN anesthesia_record.visit_id IS 'Anesthesia Record Visit ID';
COMMENT ON COLUMN anesthesia_record.document_id IS 'Anesthesia Record Document ID';
COMMENT ON COLUMN anesthesia_record.visit_type IS 'Anesthesia Record Visit Type';
COMMENT ON COLUMN anesthesia_record.record_content IS 'Anesthesia Record Record Content';
COMMENT ON COLUMN anesthesia_record.last_modifier IS 'Anesthesia Record Last Modifier';
COMMENT ON COLUMN anesthesia_record.last_modifier_id IS 'Anesthesia Record Last Modifier ID';
COMMENT ON COLUMN anesthesia_record.last_modified_datetime IS 'Anesthesia Record Last Modified Date time';
COMMENT ON COLUMN anesthesia_record.update_time IS 'Anesthesia Record Update Time';
COMMENT ON COLUMN anesthesia_record.document_title IS 'Anesthesia Record Document Title';
COMMENT ON COLUMN anesthesia_record.document_status IS 'Anesthesia Record Document Status';
COMMENT ON COLUMN anesthesia_record.submitter IS 'Anesthesia Record Submitter';
COMMENT ON COLUMN anesthesia_record.submitter_id IS 'Anesthesia Record Submitter ID';
COMMENT ON COLUMN anesthesia_record.submit_datetime IS 'Anesthesia Record Submit Date time';
COMMENT ON COLUMN anesthesia_record.inpat_no IS 'Anesthesia Record Inpatient No';
COMMENT ON COLUMN anesthesia_record.mr_no IS 'Anesthesia Record MR No';
COMMENT ON COLUMN anesthesia_record.name IS 'Anesthesia Record Name';
COMMENT ON COLUMN anesthesia_record.sex IS 'Anesthesia Record Sex';
COMMENT ON COLUMN anesthesia_record.age_year IS 'Anesthesia Record Age Year';
COMMENT ON COLUMN anesthesia_record.age_month IS 'Anesthesia Record Age Month';
COMMENT ON COLUMN anesthesia_record.age IS 'Anesthesia Record Age';
COMMENT ON COLUMN newborn_record.institute_id IS 'Newborn Record Institute ID';
COMMENT ON COLUMN newborn_record.patient_id IS 'Newborn Record Patient ID';
COMMENT ON COLUMN newborn_record.visit_id IS 'Newborn Record Visit ID';
COMMENT ON COLUMN newborn_record.document_id IS 'Newborn Record Document ID';
COMMENT ON COLUMN newborn_record.visit_type IS 'Newborn Record Visit Type';
COMMENT ON COLUMN newborn_record.record_content IS 'Newborn Record Record Content';
COMMENT ON COLUMN newborn_record.last_modifier IS 'Newborn Record Last Modifier';
COMMENT ON COLUMN newborn_record.last_modifier_id IS 'Newborn Record Last Modifier ID';
COMMENT ON COLUMN newborn_record.last_modified_datetime IS 'Newborn Record Last Modified Date time';
COMMENT ON COLUMN newborn_record.update_time IS 'Newborn Record Update Time';
COMMENT ON COLUMN newborn_record.document_title IS 'Newborn Record Document Title';
COMMENT ON COLUMN newborn_record.document_status IS 'Newborn Record Document Status';
COMMENT ON COLUMN newborn_record.submitter IS 'Newborn Record Submitter';
COMMENT ON COLUMN newborn_record.submitter_id IS 'Newborn Record Submitter ID';
COMMENT ON COLUMN newborn_record.submit_datetime IS 'Newborn Record Submit Date time';
COMMENT ON COLUMN newborn_record.inpat_no IS 'Newborn Record Inpatient No';
COMMENT ON COLUMN newborn_record.mr_no IS 'Newborn Record MR No';
COMMENT ON COLUMN newborn_record.name IS 'Newborn Record Name';
COMMENT ON COLUMN newborn_record.sex IS 'Newborn Record Sex';
COMMENT ON COLUMN newborn_record.age_year IS 'Newborn Record Age Year';
COMMENT ON COLUMN newborn_record.age_month IS 'Newborn Record Age Month';
COMMENT ON COLUMN newborn_record.age IS 'Newborn Record Age';
COMMENT ON COLUMN bloodtrans_record.institute_id IS 'Bloodtrans Record Institute ID';
COMMENT ON COLUMN bloodtrans_record.patient_id IS 'Bloodtrans Record Patient ID';
COMMENT ON COLUMN bloodtrans_record.visit_id IS 'Bloodtrans Record Visit ID';
COMMENT ON COLUMN bloodtrans_record.document_id IS 'Bloodtrans Record Document ID';
COMMENT ON COLUMN bloodtrans_record.visit_type IS 'Bloodtrans Record Visit Type';
COMMENT ON COLUMN bloodtrans_record.record_content IS 'Bloodtrans Record Record Content';
COMMENT ON COLUMN bloodtrans_record.last_modifier IS 'Bloodtrans Record Last Modifier';
COMMENT ON COLUMN bloodtrans_record.last_modifier_id IS 'Bloodtrans Record Last Modifier ID';
COMMENT ON COLUMN bloodtrans_record.last_modified_datetime IS 'Bloodtrans Record Last Modified Date time';
COMMENT ON COLUMN bloodtrans_record.update_time IS 'Bloodtrans Record Update Time';
COMMENT ON COLUMN bloodtrans_record.document_title IS 'Bloodtrans Record Document Title';
COMMENT ON COLUMN bloodtrans_record.document_status IS 'Bloodtrans Record Document Status';
COMMENT ON COLUMN bloodtrans_record.submitter IS 'Bloodtrans Record Submitter';
COMMENT ON COLUMN bloodtrans_record.submitter_id IS 'Bloodtrans Record Submitter ID';
COMMENT ON COLUMN bloodtrans_record.submit_datetime IS 'Bloodtrans Record Submit Date time';
COMMENT ON COLUMN bloodtrans_record.inpat_no IS 'Bloodtrans Record Inpatient No';
COMMENT ON COLUMN bloodtrans_record.mr_no IS 'Bloodtrans Record MR No';
COMMENT ON COLUMN bloodtrans_record.name IS 'Bloodtrans Record Name';
COMMENT ON COLUMN bloodtrans_record.sex IS 'Bloodtrans Record Sex';
COMMENT ON COLUMN bloodtrans_record.age_year IS 'Bloodtrans Record Age Year';
COMMENT ON COLUMN bloodtrans_record.age_month IS 'Bloodtrans Record Age Month';
COMMENT ON COLUMN bloodtrans_record.age IS 'Bloodtrans Record Age';
COMMENT ON COLUMN nursing_record.institute_id IS 'Nursing Record Institute ID';
COMMENT ON COLUMN nursing_record.patient_id IS 'Nursing Record Patient ID';
COMMENT ON COLUMN nursing_record.visit_id IS 'Nursing Record Visit ID';
COMMENT ON COLUMN nursing_record.document_id IS 'Nursing Record Document ID';
COMMENT ON COLUMN nursing_record.visit_type IS 'Nursing Record Visit Type';
COMMENT ON COLUMN nursing_record.record_content IS 'Nursing Record Record Content';
COMMENT ON COLUMN nursing_record.last_modifier IS 'Nursing Record Last Modifier';
COMMENT ON COLUMN nursing_record.last_modifier_id IS 'Nursing Record Last Modifier ID';
COMMENT ON COLUMN nursing_record.last_modified_datetime IS 'Nursing Record Last Modified Date time';
COMMENT ON COLUMN nursing_record.update_time IS 'Nursing Record Update Time';
COMMENT ON COLUMN nursing_record.document_title IS 'Nursing Record Document Title';
COMMENT ON COLUMN nursing_record.document_status IS 'Nursing Record Document Status';
COMMENT ON COLUMN nursing_record.submitter IS 'Nursing Record Submitter';
COMMENT ON COLUMN nursing_record.submitter_id IS 'Nursing Record Submitter ID';
COMMENT ON COLUMN nursing_record.submit_datetime IS 'Nursing Record Submit Date time';
COMMENT ON COLUMN nursing_record.inpat_no IS 'Nursing Record Inpatient No';
COMMENT ON COLUMN nursing_record.mr_no IS 'Nursing Record MR No';
COMMENT ON COLUMN nursing_record.name IS 'Nursing Record Name';
COMMENT ON COLUMN nursing_record.sex IS 'Nursing Record Sex';
COMMENT ON COLUMN nursing_record.age_year IS 'Nursing Record Age Year';
COMMENT ON COLUMN nursing_record.age_month IS 'Nursing Record Age Month';
COMMENT ON COLUMN nursing_record.age IS 'Nursing Record Age';
COMMENT ON COLUMN medical_insurance_settlement.institute_id IS 'Medical Insurance Settlement Institute ID';
COMMENT ON COLUMN medical_insurance_settlement.patient_id IS 'Medical Insurance Settlement Patient ID';
COMMENT ON COLUMN medical_insurance_settlement.visit_id IS 'Medical Insurance Settlement Visit ID';
COMMENT ON COLUMN medical_insurance_settlement.visit_type IS 'Medical Insurance Settlement Visit Type';
COMMENT ON COLUMN medical_insurance_settlement.document_id IS 'Medical Insurance Settlement Document ID';
COMMENT ON COLUMN medical_insurance_settlement.designated_medical_institution IS 'Medical Insurance Settlement Designated Medical Institution';
COMMENT ON COLUMN medical_insurance_settlement.medical_insurance_record_dept IS 'Medical Insurance Settlement Medical Insurance Record Department';
COMMENT ON COLUMN medical_insurance_settlement.medical_insurance_recorder IS 'Medical Insurance Settlement Medical Insurance Recorder';
COMMENT ON COLUMN medical_insurance_settlement.medinsur_serial_no IS 'Medical Insurance Settlement Medinsur Serial No';
COMMENT ON COLUMN medical_insurance_settlement.business_serial_no IS 'Medical Insurance Settlement Business Serial No';
COMMENT ON COLUMN medical_insurance_settlement.medinsur_receipt_id IS 'Medical Insurance Settlement Medinsur Receipt ID';
COMMENT ON COLUMN medical_insurance_settlement.ticket_code IS 'Medical Insurance Settlement Ticket Code';
COMMENT ON COLUMN medical_insurance_settlement.ticket_no IS 'Medical Insurance Settlement Ticket No';
COMMENT ON COLUMN medical_insurance_settlement.settlement_method IS 'Medical Insurance Settlement Settlement Method';
COMMENT ON COLUMN medical_insurance_settlement.patient_insurance_no IS 'Medical Insurance Settlement Patient Insurance No';
COMMENT ON COLUMN medical_insurance_settlement.inpat_no IS 'Medical Insurance Settlement Inpatient No';
COMMENT ON COLUMN medical_insurance_settlement.mr_no IS 'Medical Insurance Settlement MR No';
COMMENT ON COLUMN medical_insurance_settlement.nationality IS 'Medical Insurance Settlement Nationality';
COMMENT ON COLUMN medical_insurance_settlement.occupation_category IS 'Medical Insurance Settlement Occupation Category';
COMMENT ON COLUMN medical_insurance_settlement.currentaddress_province IS 'Medical Insurance Settlement Current address Province';
COMMENT ON COLUMN medical_insurance_settlement.currentaddress_city IS 'Medical Insurance Settlement Current address City';
COMMENT ON COLUMN medical_insurance_settlement.currentaddress_county IS 'Medical Insurance Settlement Current address County';
COMMENT ON COLUMN medical_insurance_settlement.currentaddress_town IS 'Medical Insurance Settlement Current address Town';
COMMENT ON COLUMN medical_insurance_settlement.currentaddress_village IS 'Medical Insurance Settlement Current address Village';
COMMENT ON COLUMN medical_insurance_settlement.currentaddress_detail IS 'Medical Insurance Settlement Current address Detail';
COMMENT ON COLUMN medical_insurance_settlement.currentaddress IS 'Medical Insurance Settlement Current address';
COMMENT ON COLUMN medical_insurance_settlement.currentaddress_postcode IS 'Medical Insurance Settlement Current address Postcode';
COMMENT ON COLUMN medical_insurance_settlement.currentaddress_phone IS 'Medical Insurance Settlement Current address Phone';
COMMENT ON COLUMN medical_insurance_settlement.work_unit IS 'Medical Insurance Settlement Work Unit';
COMMENT ON COLUMN medical_insurance_settlement.workplace_province IS 'Medical Insurance Settlement Workplace Province';
COMMENT ON COLUMN medical_insurance_settlement.workplace_city IS 'Medical Insurance Settlement Workplace City';
COMMENT ON COLUMN medical_insurance_settlement.workplace_county IS 'Medical Insurance Settlement Workplace County';
COMMENT ON COLUMN medical_insurance_settlement.workplace_town IS 'Medical Insurance Settlement Workplace Town';
COMMENT ON COLUMN medical_insurance_settlement.workplace_village IS 'Medical Insurance Settlement Workplace Village';
COMMENT ON COLUMN medical_insurance_settlement.workplace_detail IS 'Medical Insurance Settlement Workplace Detail';
COMMENT ON COLUMN medical_insurance_settlement.workplace IS 'Medical Insurance Settlement Workplace';
COMMENT ON COLUMN medical_insurance_settlement.workplace_postcode IS 'Medical Insurance Settlement Workplace Postcode';
COMMENT ON COLUMN medical_insurance_settlement.work_telephone IS 'Medical Insurance Settlement Work Telephone';
COMMENT ON COLUMN medical_insurance_settlement.contact_name IS 'Medical Insurance Settlement Contact Name';
COMMENT ON COLUMN medical_insurance_settlement.contact_relationship IS 'Medical Insurance Settlement Contact Relationship';
COMMENT ON COLUMN medical_insurance_settlement.contact_address IS 'Medical Insurance Settlement Contact Address';
COMMENT ON COLUMN medical_insurance_settlement.contact_telephone IS 'Medical Insurance Settlement Contact Telephone';
COMMENT ON COLUMN medical_insurance_settlement.newborn_admission_type IS 'Medical Insurance Settlement Newborn Admission Type';
COMMENT ON COLUMN medical_insurance_settlement.newborn_birthweight IS 'Medical Insurance Settlement Newborn Birthweight';
COMMENT ON COLUMN medical_insurance_settlement.newborn_admitweigth IS 'Medical Insurance Settlement Newborn Admitweigth';
COMMENT ON COLUMN medical_insurance_settlement.newborn_birth_weight IS 'Medical Insurance Settlement Newborn Birth Weight';
COMMENT ON COLUMN medical_insurance_settlement.newborn_admission_weight IS 'Medical Insurance Settlement Newborn Admission Weight';
COMMENT ON COLUMN medical_insurance_settlement.admission_route IS 'Medical Insurance Settlement Admission Route';
COMMENT ON COLUMN medical_insurance_settlement.special_personnel_type IS 'Medical Insurance Settlement Special Personnel Type';
COMMENT ON COLUMN medical_insurance_settlement.admission_datetime IS 'Medical Insurance Settlement Admission Date time';
COMMENT ON COLUMN medical_insurance_settlement.admission_dept_name IS 'Medical Insurance Settlement Admission Department Name';
COMMENT ON COLUMN medical_insurance_settlement.transfer_dept_name IS 'Medical Insurance Settlement Transfer Department Name';
COMMENT ON COLUMN medical_insurance_settlement.discharge_datetime IS 'Medical Insurance Settlement Discharge Date time';
COMMENT ON COLUMN medical_insurance_settlement.discharge_dept_name IS 'Medical Insurance Settlement Discharge Department Name';
COMMENT ON COLUMN medical_insurance_settlement.leaving_hospital_way IS 'Medical Insurance Settlement Leaving Hospital Way';
COMMENT ON COLUMN medical_insurance_settlement.receiving_institution_name IS 'Medical Insurance Settlement Receiving Institution Name';
COMMENT ON COLUMN medical_insurance_settlement.receiving_institution_code IS 'Medical Insurance Settlement Receiving Institution Code';
COMMENT ON COLUMN medical_insurance_settlement.rehospital_with_month IS 'Medical Insurance Settlement Rehospital With Month';
COMMENT ON COLUMN medical_insurance_settlement.rehospital_with_month_purpose IS 'Medical Insurance Settlement Rehospital With Month Purpose';
COMMENT ON COLUMN medical_insurance_settlement.insurance_no IS 'Medical Insurance Settlement Insurance No';
COMMENT ON COLUMN medical_insurance_settlement.declaration_time IS 'Medical Insurance Settlement Declaration Time';
COMMENT ON COLUMN medical_insurance_settlement.inpat_type IS 'Medical Insurance Settlement Inpatient Type';
COMMENT ON COLUMN medical_insurance_settlement.therapy_type IS 'Medical Insurance Settlement Therapy Type';
COMMENT ON COLUMN medical_insurance_settlement.diagnosis_code_cnt IS 'Medical Insurance Settlement Diagnosis Code Count';
COMMENT ON COLUMN medical_insurance_settlement.surgery_code_cnt IS 'Medical Insurance Settlement Surgery Code Count';
COMMENT ON COLUMN medical_insurance_settlement.ventilator_usetime IS 'Medical Insurance Settlement Ventilator Usetime';
COMMENT ON COLUMN medical_insurance_settlement.coma_timebefadm_d IS 'Medical Insurance Settlement Coma Timebefadm D';
COMMENT ON COLUMN medical_insurance_settlement.coma_timebefadm_h IS 'Medical Insurance Settlement Coma Timebefadm H';
COMMENT ON COLUMN medical_insurance_settlement.coma_timebefadm_min IS 'Medical Insurance Settlement Coma Timebefadm Min';
COMMENT ON COLUMN medical_insurance_settlement.coma_timeaftadm_d IS 'Medical Insurance Settlement Coma Timeaftadm D';
COMMENT ON COLUMN medical_insurance_settlement.coma_timeaftadm_h IS 'Medical Insurance Settlement Coma Timeaftadm H';
COMMENT ON COLUMN medical_insurance_settlement.coma_timeaftadm_min IS 'Medical Insurance Settlement Coma Timeaftadm Min';
COMMENT ON COLUMN medical_insurance_settlement.primary_care_days IS 'Medical Insurance Settlement Primary Care Days';
COMMENT ON COLUMN medical_insurance_settlement.secondary_care_days IS 'Medical Insurance Settlement Secondary Care Days';
COMMENT ON COLUMN medical_insurance_settlement.tertiary_care_days IS 'Medical Insurance Settlement Tertiary Care Days';
COMMENT ON COLUMN medical_insurance_settlement.intensive_care_days IS 'Medical Insurance Settlement Intensive Care Days';
COMMENT ON COLUMN medical_insurance_settlement.insured_place IS 'Medical Insurance Settlement Insured Place';
COMMENT ON COLUMN medical_insurance_settlement.out_of_pocket_advance IS 'Medical Insurance Settlement Out OF Pocket Advance';
COMMENT ON COLUMN medical_insurance_settlement.out_of_pocket_amount IS 'Medical Insurance Settlement Out OF Pocket Amount';
COMMENT ON COLUMN medical_insurance_settlement.personal_account_expend IS 'Medical Insurance Settlement Personal Account Expend';
COMMENT ON COLUMN medical_insurance_settlement.cash_payment_amount IS 'Medical Insurance Settlement Cash Payment Amount';
COMMENT ON COLUMN medical_insurance_settlement.insurance_type IS 'Medical Insurance Settlement Insurance Type';
COMMENT ON COLUMN medical_insurance_settlement.medical_insurance_institution IS 'Medical Insurance Settlement Medical Insurance Institution';
COMMENT ON COLUMN medical_insurance_settlement.medical_insurance_agent IS 'Medical Insurance Settlement Medical Insurance Agent';
COMMENT ON COLUMN medical_insurance_settlement.medical_insurance_agent_code IS 'Medical Insurance Settlement Medical Insurance Agent Code';
COMMENT ON COLUMN medical_insurance_settlement.outp_chronic_department IS 'Medical Insurance Settlement Outp Chronic Department';
COMMENT ON COLUMN medical_insurance_settlement.outp_chronic_date IS 'Medical Insurance Settlement Outp Chronic Date';
COMMENT ON COLUMN medical_insurance_settlement.attending_physician_code IS 'Medical Insurance Settlement Attending Physician Code';
COMMENT ON COLUMN medical_insurance_settlement.responsible_nurse_code IS 'Medical Insurance Settlement Responsible Nurse Code';
COMMENT ON COLUMN medical_insurance_settlement.settlement_status IS 'Medical Insurance Settlement Settlement Status';
COMMENT ON COLUMN medical_insurance_settlement.start_date IS 'Medical Insurance Settlement Start Date';
COMMENT ON COLUMN medical_insurance_settlement.end_date IS 'Medical Insurance Settlement End Date';
COMMENT ON COLUMN medical_insurance_settlement.last_modifier IS 'Medical Insurance Settlement Last Modifier';
COMMENT ON COLUMN medical_insurance_settlement.last_modifier_id IS 'Medical Insurance Settlement Last Modifier ID';
COMMENT ON COLUMN medical_insurance_settlement.last_modified_datetime IS 'Medical Insurance Settlement Last Modified Date time';
COMMENT ON COLUMN medical_insurance_settlement.update_time IS 'Medical Insurance Settlement Update Time';
COMMENT ON COLUMN medical_insurance_settlement_cost.institute_id IS 'Medical Insurance Settlement Cost Institute ID';
COMMENT ON COLUMN medical_insurance_settlement_cost.patient_id IS 'Medical Insurance Settlement Cost Patient ID';
COMMENT ON COLUMN medical_insurance_settlement_cost.visit_id IS 'Medical Insurance Settlement Cost Visit ID';
COMMENT ON COLUMN medical_insurance_settlement_cost.visit_type IS 'Medical Insurance Settlement Cost Visit Type';
COMMENT ON COLUMN medical_insurance_settlement_cost.document_id IS 'Medical Insurance Settlement Cost Document ID';
COMMENT ON COLUMN medical_insurance_settlement_cost.medinsur_serial_no IS 'Medical Insurance Settlement Cost Medinsur Serial No';
COMMENT ON COLUMN medical_insurance_settlement_cost.medinsur_serial_item_id IS 'Medical Insurance Settlement Cost Medinsur Serial Item ID';
COMMENT ON COLUMN medical_insurance_settlement_cost.charge IS 'Medical Insurance Settlement Cost Charge';
COMMENT ON COLUMN medical_insurance_settlement_cost.type_of_medicalcharge IS 'Medical Insurance Settlement Cost Type OF Medicalcharge';
COMMENT ON COLUMN medical_insurance_settlement_cost.charge_item_level IS 'Medical Insurance Settlement Cost Charge Item Level';
COMMENT ON COLUMN medical_insurance_settlement_cost.item_class_a_amount IS 'Medical Insurance Settlement Cost Item Class A Amount';
COMMENT ON COLUMN medical_insurance_settlement_cost.item_class_b_amount IS 'Medical Insurance Settlement Cost Item Class B Amount';
COMMENT ON COLUMN medical_insurance_settlement_cost.item_own_pay_amount IS 'Medical Insurance Settlement Cost Item Own Pay Amount';
COMMENT ON COLUMN medical_insurance_settlement_cost.item_other_amount IS 'Medical Insurance Settlement Cost Item Other Amount';
COMMENT ON COLUMN medical_insurance_settlement_cost.last_modifier IS 'Medical Insurance Settlement Cost Last Modifier';
COMMENT ON COLUMN medical_insurance_settlement_cost.last_modifier_id IS 'Medical Insurance Settlement Cost Last Modifier ID';
COMMENT ON COLUMN medical_insurance_settlement_cost.last_modified_datetime IS 'Medical Insurance Settlement Cost Last Modified Date time';
COMMENT ON COLUMN medical_insurance_settlement_cost.update_time IS 'Medical Insurance Settlement Cost Update Time';
COMMENT ON COLUMN inpat_drug_order.institute_id IS 'Inpatient Drug Order Institute ID';
COMMENT ON COLUMN inpat_drug_order.patient_id IS 'Inpatient Drug Order Patient ID';
COMMENT ON COLUMN inpat_drug_order.visit_id IS 'Inpatient Drug Order Visit ID';
COMMENT ON COLUMN inpat_drug_order.visit_type IS 'Inpatient Drug Order Visit Type';
COMMENT ON COLUMN inpat_drug_order.order_id IS 'Inpatient Drug Order Order ID';
COMMENT ON COLUMN inpat_drug_order.inpat_no IS 'Inpatient Drug Order Inpatient No';
COMMENT ON COLUMN inpat_drug_order.name IS 'Inpatient Drug Order Name';
COMMENT ON COLUMN inpat_drug_order.sex IS 'Inpatient Drug Order Sex';
COMMENT ON COLUMN inpat_drug_order.age_year IS 'Inpatient Drug Order Age Year';
COMMENT ON COLUMN inpat_drug_order.age_month IS 'Inpatient Drug Order Age Month';
COMMENT ON COLUMN inpat_drug_order.age IS 'Inpatient Drug Order Age';
COMMENT ON COLUMN inpat_drug_order.dept_name IS 'Inpatient Drug Order Department Name';
COMMENT ON COLUMN inpat_drug_order.group_id IS 'Inpatient Drug Order Group ID';
COMMENT ON COLUMN inpat_drug_order.repeat_indicator IS 'Inpatient Drug Order Repeat Indicator';
COMMENT ON COLUMN inpat_drug_order.drug_type IS 'Inpatient Drug Order Drug Type';
COMMENT ON COLUMN inpat_drug_order.brand_name IS 'Inpatient Drug Order Brand Name';
COMMENT ON COLUMN inpat_drug_order.drug_code IS 'Inpatient Drug Order Drug Code';
COMMENT ON COLUMN inpat_drug_order.generic_name IS 'Inpatient Drug Order Generic Name';
COMMENT ON COLUMN inpat_drug_order.cfda_id IS 'Inpatient Drug Order Cfda ID';
COMMENT ON COLUMN inpat_drug_order.firm IS 'Inpatient Drug Order Firm';
COMMENT ON COLUMN inpat_drug_order.drug_specification IS 'Inpatient Drug Order Drug Specification';
COMMENT ON COLUMN inpat_drug_order.drug_frequency IS 'Inpatient Drug Order Drug Frequency';
COMMENT ON COLUMN inpat_drug_order.drug_apply_method IS 'Inpatient Drug Order Drug Apply Method';
COMMENT ON COLUMN inpat_drug_order.single_dose IS 'Inpatient Drug Order Single Dose';
COMMENT ON COLUMN inpat_drug_order.single_dose_unit IS 'Inpatient Drug Order Single Dose Unit';
COMMENT ON COLUMN inpat_drug_order.dose_form IS 'Inpatient Drug Order Dose Form';
COMMENT ON COLUMN inpat_drug_order.medication_duration IS 'Inpatient Drug Order Medication Duration';
COMMENT ON COLUMN inpat_drug_order.prescribed_datetime IS 'Inpatient Drug Order Prescribed Date time';
COMMENT ON COLUMN inpat_drug_order.prescribed_doctor IS 'Inpatient Drug Order Prescribed Doctor';
COMMENT ON COLUMN inpat_drug_order.order_status IS 'Inpatient Drug Order Order Status';
COMMENT ON COLUMN inpat_drug_order.record_content IS 'Inpatient Drug Order Record Content';
COMMENT ON COLUMN inpat_drug_order.last_modifier IS 'Inpatient Drug Order Last Modifier';
COMMENT ON COLUMN inpat_drug_order.last_modifier_id IS 'Inpatient Drug Order Last Modifier ID';
COMMENT ON COLUMN inpat_drug_order.last_modified_datetime IS 'Inpatient Drug Order Last Modified Date time';
COMMENT ON COLUMN inpat_drug_order.update_time IS 'Inpatient Drug Order Update Time';
COMMENT ON COLUMN inpat_nondrug_order.institute_id IS 'Inpatient Nondrug Order Institute ID';
COMMENT ON COLUMN inpat_nondrug_order.patient_id IS 'Inpatient Nondrug Order Patient ID';
COMMENT ON COLUMN inpat_nondrug_order.visit_id IS 'Inpatient Nondrug Order Visit ID';
COMMENT ON COLUMN inpat_nondrug_order.visit_type IS 'Inpatient Nondrug Order Visit Type';
COMMENT ON COLUMN inpat_nondrug_order.order_id IS 'Inpatient Nondrug Order Order ID';
COMMENT ON COLUMN inpat_nondrug_order.inpat_no IS 'Inpatient Nondrug Order Inpatient No';
COMMENT ON COLUMN inpat_nondrug_order.application_id IS 'Inpatient Nondrug Order Application ID';
COMMENT ON COLUMN inpat_nondrug_order.name IS 'Inpatient Nondrug Order Name';
COMMENT ON COLUMN inpat_nondrug_order.sex IS 'Inpatient Nondrug Order Sex';
COMMENT ON COLUMN inpat_nondrug_order.age_year IS 'Inpatient Nondrug Order Age Year';
COMMENT ON COLUMN inpat_nondrug_order.age_month IS 'Inpatient Nondrug Order Age Month';
COMMENT ON COLUMN inpat_nondrug_order.age IS 'Inpatient Nondrug Order Age';
COMMENT ON COLUMN inpat_nondrug_order.dept_name IS 'Inpatient Nondrug Order Department Name';
COMMENT ON COLUMN inpat_nondrug_order.group_id IS 'Inpatient Nondrug Order Group ID';
COMMENT ON COLUMN inpat_nondrug_order.repeat_indicator IS 'Inpatient Nondrug Order Repeat Indicator';
COMMENT ON COLUMN inpat_nondrug_order.order_type IS 'Inpatient Nondrug Order Order Type';
COMMENT ON COLUMN inpat_nondrug_order.order_name IS 'Inpatient Nondrug Order Order Name';
COMMENT ON COLUMN inpat_nondrug_order.quantity IS 'Inpatient Nondrug Order Quantity';
COMMENT ON COLUMN inpat_nondrug_order.quantity_unit IS 'Inpatient Nondrug Order Quantity Unit';
COMMENT ON COLUMN inpat_nondrug_order.frequency IS 'Inpatient Nondrug Order Frequency';
COMMENT ON COLUMN inpat_nondrug_order.prescribed_datetime IS 'Inpatient Nondrug Order Prescribed Date time';
COMMENT ON COLUMN inpat_nondrug_order.prescribed_doctor IS 'Inpatient Nondrug Order Prescribed Doctor';
COMMENT ON COLUMN inpat_nondrug_order.order_status IS 'Inpatient Nondrug Order Order Status';
COMMENT ON COLUMN inpat_nondrug_order.record_content IS 'Inpatient Nondrug Order Record Content';
COMMENT ON COLUMN inpat_nondrug_order.last_modifier IS 'Inpatient Nondrug Order Last Modifier';
COMMENT ON COLUMN inpat_nondrug_order.last_modifier_id IS 'Inpatient Nondrug Order Last Modifier ID';
COMMENT ON COLUMN inpat_nondrug_order.last_modified_datetime IS 'Inpatient Nondrug Order Last Modified Date time';
COMMENT ON COLUMN inpat_nondrug_order.update_time IS 'Inpatient Nondrug Order Update Time';
COMMENT ON COLUMN inpat_bill_item.institute_id IS 'Inpatient Bill Item Institute ID';
COMMENT ON COLUMN inpat_bill_item.patient_id IS 'Inpatient Bill Item Patient ID';
COMMENT ON COLUMN inpat_bill_item.visit_id IS 'Inpatient Bill Item Visit ID';
COMMENT ON COLUMN inpat_bill_item.visit_type IS 'Inpatient Bill Item Visit Type';
COMMENT ON COLUMN inpat_bill_item.bill_item_id IS 'Inpatient Bill Item Bill Item ID';
COMMENT ON COLUMN inpat_bill_item.receipt_id IS 'Inpatient Bill Item Receipt ID';
COMMENT ON COLUMN inpat_bill_item.inpat_no IS 'Inpatient Bill Item Inpatient No';
COMMENT ON COLUMN inpat_bill_item.name IS 'Inpatient Bill Item Name';
COMMENT ON COLUMN inpat_bill_item.sex IS 'Inpatient Bill Item Sex';
COMMENT ON COLUMN inpat_bill_item.age_year IS 'Inpatient Bill Item Age Year';
COMMENT ON COLUMN inpat_bill_item.order_id IS 'Inpatient Bill Item Order ID';
COMMENT ON COLUMN inpat_bill_item.item_type IS 'Inpatient Bill Item Item Type';
COMMENT ON COLUMN inpat_bill_item.medical_catalog_code IS 'Inpatient Bill Item Medical Catalog Code';
COMMENT ON COLUMN inpat_bill_item.medical_catalog_name IS 'Inpatient Bill Item Medical Catalog Name';
COMMENT ON COLUMN inpat_bill_item.medinsur_catalog_code IS 'Inpatient Bill Item Medinsur Catalog Code';
COMMENT ON COLUMN inpat_bill_item.medinsur_catalog_name IS 'Inpatient Bill Item Medinsur Catalog Name';
COMMENT ON COLUMN inpat_bill_item.item_specification IS 'Inpatient Bill Item Item Specification';
COMMENT ON COLUMN inpat_bill_item.firm IS 'Inpatient Bill Item Firm';
COMMENT ON COLUMN inpat_bill_item.unit_price IS 'Inpatient Bill Item Unit Price';
COMMENT ON COLUMN inpat_bill_item.quantity IS 'Inpatient Bill Item Quantity';
COMMENT ON COLUMN inpat_bill_item.quantity_unit IS 'Inpatient Bill Item Quantity Unit';
COMMENT ON COLUMN inpat_bill_item.cost IS 'Inpatient Bill Item Cost';
COMMENT ON COLUMN inpat_bill_item.charge IS 'Inpatient Bill Item Charge';
COMMENT ON COLUMN inpat_bill_item.insurance_category IS 'Inpatient Bill Item Insurance Category';
COMMENT ON COLUMN inpat_bill_item.charge_item_level IS 'Inpatient Bill Item Charge Item Level';
COMMENT ON COLUMN inpat_bill_item.billing_datetime IS 'Inpatient Bill Item Billing Date time';
COMMENT ON COLUMN inpat_bill_item.order_dept_name IS 'Inpatient Bill Item Order Department Name';
COMMENT ON COLUMN inpat_bill_item.executive_dept_name IS 'Inpatient Bill Item Executive Department Name';
COMMENT ON COLUMN inpat_bill_item.record_content IS 'Inpatient Bill Item Record Content';
COMMENT ON COLUMN inpat_bill_item.last_modifier IS 'Inpatient Bill Item Last Modifier';
COMMENT ON COLUMN inpat_bill_item.last_modifier_id IS 'Inpatient Bill Item Last Modifier ID';
COMMENT ON COLUMN inpat_bill_item.last_modified_datetime IS 'Inpatient Bill Item Last Modified Date time';
COMMENT ON COLUMN inpat_bill_item.update_time IS 'Inpatient Bill Item Update Time';
COMMENT ON COLUMN labtest_master.institute_id IS 'Labtest Master Institute ID';
COMMENT ON COLUMN labtest_master.patient_id IS 'Labtest Master Patient ID';
COMMENT ON COLUMN labtest_master.visit_id IS 'Labtest Master Visit ID';
COMMENT ON COLUMN labtest_master.visit_type IS 'Labtest Master Visit Type';
COMMENT ON COLUMN labtest_master.test_id IS 'Labtest Master Test ID';
COMMENT ON COLUMN labtest_master.order_id IS 'Labtest Master Order ID';
COMMENT ON COLUMN labtest_master.inpat_no IS 'Labtest Master Inpatient No';
COMMENT ON COLUMN labtest_master.name IS 'Labtest Master Name';
COMMENT ON COLUMN labtest_master.sex IS 'Labtest Master Sex';
COMMENT ON COLUMN labtest_master.age_year IS 'Labtest Master Age Year';
COMMENT ON COLUMN labtest_master.labtest_subject IS 'Labtest Master Labtest Subject';
COMMENT ON COLUMN labtest_master.labtest_cause IS 'Labtest Master Labtest Cause';
COMMENT ON COLUMN labtest_master.specimen IS 'Labtest Master Specimen';
COMMENT ON COLUMN labtest_master.request_dept IS 'Labtest Master Request Department';
COMMENT ON COLUMN labtest_master.request_physician IS 'Labtest Master Request Physician';
COMMENT ON COLUMN labtest_master.request_datetime IS 'Labtest Master Request Date time';
COMMENT ON COLUMN labtest_master.report_datetime IS 'Labtest Master Report Date time';
COMMENT ON COLUMN labtest_master.reporter IS 'Labtest Master Reporter';
COMMENT ON COLUMN labtest_master.verifier IS 'Labtest Master Verifier';
COMMENT ON COLUMN labtest_master.labtest_result_status IS 'Labtest Master Labtest Result Status';
COMMENT ON COLUMN labtest_master.record_content IS 'Labtest Master Record Content';
COMMENT ON COLUMN labtest_master.last_modifier IS 'Labtest Master Last Modifier';
COMMENT ON COLUMN labtest_master.last_modifier_id IS 'Labtest Master Last Modifier ID';
COMMENT ON COLUMN labtest_master.last_modified_datetime IS 'Labtest Master Last Modified Date time';
COMMENT ON COLUMN labtest_master.update_time IS 'Labtest Master Update Time';
COMMENT ON COLUMN labtest_item.institute_id IS 'Labtest Item Institute ID';
COMMENT ON COLUMN labtest_item.patient_id IS 'Labtest Item Patient ID';
COMMENT ON COLUMN labtest_item.visit_id IS 'Labtest Item Visit ID';
COMMENT ON COLUMN labtest_item.visit_type IS 'Labtest Item Visit Type';
COMMENT ON COLUMN labtest_item.test_id IS 'Labtest Item Test ID';
COMMENT ON COLUMN labtest_item.test_item_id IS 'Labtest Item Test Item ID';
COMMENT ON COLUMN labtest_item.item_name IS 'Labtest Item Item Name';
COMMENT ON COLUMN labtest_item.item_code IS 'Labtest Item Item Code';
COMMENT ON COLUMN labtest_item.report_datetime IS 'Labtest Item Report Date time';
COMMENT ON COLUMN labtest_item.record_content IS 'Labtest Item Record Content';
COMMENT ON COLUMN labtest_item.last_modifier IS 'Labtest Item Last Modifier';
COMMENT ON COLUMN labtest_item.last_modifier_id IS 'Labtest Item Last Modifier ID';
COMMENT ON COLUMN labtest_item.last_modified_datetime IS 'Labtest Item Last Modified Date time';
COMMENT ON COLUMN labtest_item.update_time IS 'Labtest Item Update Time';
COMMENT ON COLUMN mr_bloodtrans.institute_id IS 'MR Bloodtrans Institute ID';
COMMENT ON COLUMN mr_bloodtrans.patient_id IS 'MR Bloodtrans Patient ID';
COMMENT ON COLUMN mr_bloodtrans.visit_id IS 'MR Bloodtrans Visit ID';
COMMENT ON COLUMN mr_bloodtrans.visit_type IS 'MR Bloodtrans Visit Type';
COMMENT ON COLUMN mr_bloodtrans.document_id IS 'MR Bloodtrans Document ID';
COMMENT ON COLUMN mr_bloodtrans.bloodtrans_id IS 'MR Bloodtrans Bloodtrans ID';
COMMENT ON COLUMN mr_bloodtrans.inpat_no IS 'MR Bloodtrans Inpatient No';
COMMENT ON COLUMN mr_bloodtrans.mr_no IS 'MR Bloodtrans MR No';
COMMENT ON COLUMN mr_bloodtrans.transfuse_variety IS 'MR Bloodtrans Transfuse Variety';
COMMENT ON COLUMN mr_bloodtrans.bloodbag_id IS 'MR Bloodtrans Bloodbag ID';
COMMENT ON COLUMN mr_bloodtrans.blood_transfusion_volume IS 'MR Bloodtrans Blood Transfusion Volume';
COMMENT ON COLUMN mr_bloodtrans.blood_transfusion_unit IS 'MR Bloodtrans Blood Transfusion Unit';
COMMENT ON COLUMN mr_bloodtrans.transblood_reaction_sign IS 'MR Bloodtrans Transblood Reaction Signature';
COMMENT ON COLUMN mr_bloodtrans.transblood_reaction_type IS 'MR Bloodtrans Transblood Reaction Type';
COMMENT ON COLUMN mr_bloodtrans.transfution_datetime IS 'MR Bloodtrans Transfution Date time';
COMMENT ON COLUMN mr_bloodtrans.transfusion_reason IS 'MR Bloodtrans Transfusion Reason';
COMMENT ON COLUMN mr_bloodtrans.last_modifier IS 'MR Bloodtrans Last Modifier';
COMMENT ON COLUMN mr_bloodtrans.last_modifier_id IS 'MR Bloodtrans Last Modifier ID';
COMMENT ON COLUMN mr_bloodtrans.last_modified_datetime IS 'MR Bloodtrans Last Modified Date time';
COMMENT ON COLUMN mr_bloodtrans.update_time IS 'MR Bloodtrans Update Time';
COMMENT ON COLUMN mr_icu.institute_id IS 'MR Icu Institute ID';
COMMENT ON COLUMN mr_icu.patient_id IS 'MR Icu Patient ID';
COMMENT ON COLUMN mr_icu.visit_id IS 'MR Icu Visit ID';
COMMENT ON COLUMN mr_icu.visit_type IS 'MR Icu Visit Type';
COMMENT ON COLUMN mr_icu.document_id IS 'MR Icu Document ID';
COMMENT ON COLUMN mr_icu.icu_id IS 'MR Icu Icu ID';
COMMENT ON COLUMN mr_icu.inpat_no IS 'MR Icu Inpatient No';
COMMENT ON COLUMN mr_icu.mr_no IS 'MR Icu MR No';
COMMENT ON COLUMN mr_icu.icu_type IS 'MR Icu Icu Type';
COMMENT ON COLUMN mr_icu.icu_name IS 'MR Icu Icu Name';
COMMENT ON COLUMN mr_icu.icu_start_datetime IS 'MR Icu Icu Start Date time';
COMMENT ON COLUMN mr_icu.icu_end_datetime IS 'MR Icu Icu End Date time';
COMMENT ON COLUMN mr_icu.icu_period IS 'MR Icu Icu Period';
COMMENT ON COLUMN mr_icu.last_modifier IS 'MR Icu Last Modifier';
COMMENT ON COLUMN mr_icu.last_modifier_id IS 'MR Icu Last Modifier ID';
COMMENT ON COLUMN mr_icu.last_modified_datetime IS 'MR Icu Last Modified Date time';
COMMENT ON COLUMN mr_icu.update_time IS 'MR Icu Update Time';
COMMENT ON COLUMN mr_customize.institute_id IS 'MR Customize Institute ID';
COMMENT ON COLUMN mr_customize.patient_id IS 'MR Customize Patient ID';
COMMENT ON COLUMN mr_customize.visit_id IS 'MR Customize Visit ID';
COMMENT ON COLUMN mr_customize.visit_type IS 'MR Customize Visit Type';
COMMENT ON COLUMN mr_customize.document_id IS 'MR Customize Document ID';
COMMENT ON COLUMN mr_customize.mr_no IS 'MR Customize MR No';
COMMENT ON COLUMN mr_customize.T_stage IS 'MR Customize T Stage';
COMMENT ON COLUMN mr_customize.N_stage IS 'MR Customize N Stage';
COMMENT ON COLUMN mr_customize.M_stage IS 'MR Customize M Stage';
COMMENT ON COLUMN mr_customize.tumor_stage IS 'MR Customize Tumor Stage';
COMMENT ON COLUMN mr_customize.transferin_org_name IS 'MR Customize Transferin Org Name';
COMMENT ON COLUMN mr_customize.discharge_condition IS 'MR Customize Discharge Condition';
COMMENT ON COLUMN mr_customize.living_ability_admission_score IS 'MR Customize Living Ability Admission Score';
COMMENT ON COLUMN mr_customize.living_ability_discharge_score IS 'MR Customize Living Ability Discharge Score';
COMMENT ON COLUMN mr_customize.rescue_no IS 'MR Customize Rescue No';
COMMENT ON COLUMN mr_customize.rescue_success_no IS 'MR Customize Rescue Success No';
COMMENT ON COLUMN mr_customize.criticalcare_record_sign IS 'MR Customize Criticalcare Record Signature';
COMMENT ON COLUMN mr_customize.difficult_record_sign IS 'MR Customize Difficult Record Signature';
COMMENT ON COLUMN mr_customize.last_modifier IS 'MR Customize Last Modifier';
COMMENT ON COLUMN mr_customize.last_modifier_id IS 'MR Customize Last Modifier ID';
COMMENT ON COLUMN mr_customize.last_modified_datetime IS 'MR Customize Last Modified Date time';
COMMENT ON COLUMN mr_customize.update_time IS 'MR Customize Update Time';
COMMENT ON COLUMN medinsur_receipt.institute_id IS 'Medinsur Receipt Institute ID';
COMMENT ON COLUMN medinsur_receipt.patient_id IS 'Medinsur Receipt Patient ID';
COMMENT ON COLUMN medinsur_receipt.visit_id IS 'Medinsur Receipt Visit ID';
COMMENT ON COLUMN medinsur_receipt.visit_type IS 'Medinsur Receipt Visit Type';
COMMENT ON COLUMN medinsur_receipt.medinsur_receipt_id IS 'Medinsur Receipt Medinsur Receipt ID';
COMMENT ON COLUMN medinsur_receipt.outpat_no IS 'Medinsur Receipt Outpat No';
COMMENT ON COLUMN medinsur_receipt.inpat_no IS 'Medinsur Receipt Inpatient No';
COMMENT ON COLUMN medinsur_receipt.name IS 'Medinsur Receipt Name';
COMMENT ON COLUMN medinsur_receipt.sex IS 'Medinsur Receipt Sex';
COMMENT ON COLUMN medinsur_receipt.ethnicity IS 'Medinsur Receipt Ethnicity';
COMMENT ON COLUMN medinsur_receipt.birthday IS 'Medinsur Receipt Birthday';
COMMENT ON COLUMN medinsur_receipt.age_year IS 'Medinsur Receipt Age Year';
COMMENT ON COLUMN medinsur_receipt.insurance_type IS 'Medinsur Receipt Insurance Type';
COMMENT ON COLUMN medinsur_receipt.insurance_no IS 'Medinsur Receipt Insurance No';
COMMENT ON COLUMN medinsur_receipt.settlement_method IS 'Medinsur Receipt Settlement Method';
COMMENT ON COLUMN medinsur_receipt.total_charge IS 'Medinsur Receipt Total Charge';
COMMENT ON COLUMN medinsur_receipt.personnel_payment IS 'Medinsur Receipt Personnel Payment';
COMMENT ON COLUMN medinsur_receipt.fund_payment_amount IS 'Medinsur Receipt Fund Payment Amount';
COMMENT ON COLUMN medinsur_receipt.personal_account_expend IS 'Medinsur Receipt Personal Account Expend';
COMMENT ON COLUMN medinsur_receipt.cash_payment_amount IS 'Medinsur Receipt Cash Payment Amount';
COMMENT ON COLUMN medinsur_receipt.start_date IS 'Medinsur Receipt Start Date';
COMMENT ON COLUMN medinsur_receipt.end_date IS 'Medinsur Receipt End Date';
COMMENT ON COLUMN medinsur_receipt.settle_datetime IS 'Medinsur Receipt Settle Date time';
COMMENT ON COLUMN medinsur_receipt.record_content IS 'Medinsur Receipt Record Content';
COMMENT ON COLUMN medinsur_receipt.last_modifier IS 'Medinsur Receipt Last Modifier';
COMMENT ON COLUMN medinsur_receipt.last_modifier_id IS 'Medinsur Receipt Last Modifier ID';
COMMENT ON COLUMN medinsur_receipt.last_modified_datetime IS 'Medinsur Receipt Last Modified Date time';
COMMENT ON COLUMN medinsur_receipt.update_time IS 'Medinsur Receipt Update Time';
COMMENT ON COLUMN pathology_exam_master.institute_id IS 'Pathology Exam Master Institute ID';
COMMENT ON COLUMN pathology_exam_master.patient_id IS 'Pathology Exam Master Patient ID';
COMMENT ON COLUMN pathology_exam_master.visit_id IS 'Pathology Exam Master Visit ID';
COMMENT ON COLUMN pathology_exam_master.visit_type IS 'Pathology Exam Master Visit Type';
COMMENT ON COLUMN pathology_exam_master.pathology_exam_id IS 'Pathology Exam Master Pathology Exam ID';
COMMENT ON COLUMN pathology_exam_master.pathology_id IS 'Pathology Exam Master Pathology ID';
COMMENT ON COLUMN pathology_exam_master.inpat_no IS 'Pathology Exam Master Inpatient No';
COMMENT ON COLUMN pathology_exam_master.name IS 'Pathology Exam Master Name';
COMMENT ON COLUMN pathology_exam_master.sex IS 'Pathology Exam Master Sex';
COMMENT ON COLUMN pathology_exam_master.age_year IS 'Pathology Exam Master Age Year';
COMMENT ON COLUMN pathology_exam_master.clinical_history IS 'Pathology Exam Master Clinical History';
COMMENT ON COLUMN pathology_exam_master.surgery_name IS 'Pathology Exam Master Surgery Name';
COMMENT ON COLUMN pathology_exam_master.specimen_name IS 'Pathology Exam Master Specimen Name';
COMMENT ON COLUMN pathology_exam_master.request_dept IS 'Pathology Exam Master Request Department';
COMMENT ON COLUMN pathology_exam_master.request_physician IS 'Pathology Exam Master Request Physician';
COMMENT ON COLUMN pathology_exam_master.request_datetime IS 'Pathology Exam Master Request Date time';
COMMENT ON COLUMN pathology_exam_master.record_content IS 'Pathology Exam Master Record Content';
COMMENT ON COLUMN pathology_exam_master.last_modifier IS 'Pathology Exam Master Last Modifier';
COMMENT ON COLUMN pathology_exam_master.last_modifier_id IS 'Pathology Exam Master Last Modifier ID';
COMMENT ON COLUMN pathology_exam_master.last_modified_datetime IS 'Pathology Exam Master Last Modified Date time';
COMMENT ON COLUMN pathology_exam_master.update_time IS 'Pathology Exam Master Update Time';
COMMENT ON COLUMN pathology_exam_report.institute_id IS 'Pathology Exam Report Institute ID';
COMMENT ON COLUMN pathology_exam_report.patient_id IS 'Pathology Exam Report Patient ID';
COMMENT ON COLUMN pathology_exam_report.visit_id IS 'Pathology Exam Report Visit ID';
COMMENT ON COLUMN pathology_exam_report.visit_type IS 'Pathology Exam Report Visit Type';
COMMENT ON COLUMN pathology_exam_report.pathology_exam_id IS 'Pathology Exam Report Pathology Exam ID';
COMMENT ON COLUMN pathology_exam_report.pathology_id IS 'Pathology Exam Report Pathology ID';
COMMENT ON COLUMN pathology_exam_report.specimen_name IS 'Pathology Exam Report Specimen Name';
COMMENT ON COLUMN pathology_exam_report.eye_findings IS 'Pathology Exam Report Eye Findings';
COMMENT ON COLUMN pathology_exam_report.microscope_findings IS 'Pathology Exam Report Microscope Findings';
COMMENT ON COLUMN pathology_exam_report.diagnosis IS 'Pathology Exam Report Diagnosis';
COMMENT ON COLUMN pathology_exam_report.report_status IS 'Pathology Exam Report Report Status';
COMMENT ON COLUMN pathology_exam_report.report_datetime IS 'Pathology Exam Report Report Date time';
COMMENT ON COLUMN pathology_exam_report.reporter IS 'Pathology Exam Report Reporter';
COMMENT ON COLUMN pathology_exam_report.review_datetime IS 'Pathology Exam Report Review Date time';
COMMENT ON COLUMN pathology_exam_report.reviewer IS 'Pathology Exam Report Reviewer';
COMMENT ON COLUMN pathology_exam_report.record_content IS 'Pathology Exam Report Record Content';
COMMENT ON COLUMN pathology_exam_report.last_modifier IS 'Pathology Exam Report Last Modifier';
COMMENT ON COLUMN pathology_exam_report.last_modifier_id IS 'Pathology Exam Report Last Modifier ID';
COMMENT ON COLUMN pathology_exam_report.last_modified_datetime IS 'Pathology Exam Report Last Modified Date time';
COMMENT ON COLUMN pathology_exam_report.update_time IS 'Pathology Exam Report Update Time';
COMMENT ON COLUMN epidemic_record.institute_id IS 'Epidemic Record Institute ID';
COMMENT ON COLUMN epidemic_record.patient_id IS 'Epidemic Record Patient ID';
COMMENT ON COLUMN epidemic_record.visit_id IS 'Epidemic Record Visit ID';
COMMENT ON COLUMN epidemic_record.document_id IS 'Epidemic Record Document ID';
COMMENT ON COLUMN epidemic_record.visit_type IS 'Epidemic Record Visit Type';
COMMENT ON COLUMN epidemic_record.dept_name IS 'Epidemic Record Department Name';
COMMENT ON COLUMN epidemic_record.inpat_no IS 'Epidemic Record Inpatient No';
COMMENT ON COLUMN epidemic_record.name IS 'Epidemic Record Name';
COMMENT ON COLUMN epidemic_record.sex IS 'Epidemic Record Sex';
COMMENT ON COLUMN epidemic_record.age_year IS 'Epidemic Record Age Year';
COMMENT ON COLUMN epidemic_record.record_content IS 'Epidemic Record Record Content';
COMMENT ON COLUMN epidemic_record.record_datetime IS 'Epidemic Record Record Date time';
COMMENT ON COLUMN epidemic_record.last_modifier IS 'Epidemic Record Last Modifier';
COMMENT ON COLUMN epidemic_record.last_modifier_id IS 'Epidemic Record Last Modifier ID';
COMMENT ON COLUMN epidemic_record.last_modified_datetime IS 'Epidemic Record Last Modified Date time';
COMMENT ON COLUMN epidemic_record.update_time IS 'Epidemic Record Update Time';
COMMENT ON COLUMN epidemic_record.document_title IS 'Epidemic Record Document Title';
COMMENT ON COLUMN epidemic_record.document_status IS 'Epidemic Record Document Status';
COMMENT ON COLUMN epidemic_record.submitter IS 'Epidemic Record Submitter';
COMMENT ON COLUMN epidemic_record.submitter_id IS 'Epidemic Record Submitter ID';
COMMENT ON COLUMN epidemic_record.submit_datetime IS 'Epidemic Record Submit Date time';
COMMENT ON COLUMN outpat_record.institute_id IS 'Outpat Record Institute ID';
COMMENT ON COLUMN outpat_record.patient_id IS 'Outpat Record Patient ID';
COMMENT ON COLUMN outpat_record.visit_id IS 'Outpat Record Visit ID';
COMMENT ON COLUMN outpat_record.document_id IS 'Outpat Record Document ID';
COMMENT ON COLUMN outpat_record.visit_type IS 'Outpat Record Visit Type';
COMMENT ON COLUMN outpat_record.dept_name IS 'Outpat Record Department Name';
COMMENT ON COLUMN outpat_record.outpat_no IS 'Outpat Record Outpat No';
COMMENT ON COLUMN outpat_record.visit_datetime IS 'Outpat Record Visit Date time';
COMMENT ON COLUMN outpat_record.chief_complaint IS 'Outpat Record Chief Complaint';
COMMENT ON COLUMN outpat_record.history_of_present_illness IS 'Outpat Record History OF Present Illness';
COMMENT ON COLUMN outpat_record.past_history IS 'Outpat Record Past History';
COMMENT ON COLUMN outpat_record.checkup IS 'Outpat Record Checkup';
COMMENT ON COLUMN outpat_record.assist_exam IS 'Outpat Record Assist Exam';
COMMENT ON COLUMN outpat_record.treatment_advice IS 'Outpat Record Treatment Advice';
COMMENT ON COLUMN outpat_record.record_content IS 'Outpat Record Record Content';
COMMENT ON COLUMN outpat_record.last_modifier IS 'Outpat Record Last Modifier';
COMMENT ON COLUMN outpat_record.last_modifier_id IS 'Outpat Record Last Modifier ID';
COMMENT ON COLUMN outpat_record.last_modified_datetime IS 'Outpat Record Last Modified Date time';
COMMENT ON COLUMN outpat_record.update_time IS 'Outpat Record Update Time';
COMMENT ON COLUMN outpat_record.document_title IS 'Outpat Record Document Title';
COMMENT ON COLUMN outpat_record.document_status IS 'Outpat Record Document Status';
COMMENT ON COLUMN outpat_record.submitter IS 'Outpat Record Submitter';
COMMENT ON COLUMN outpat_record.submitter_id IS 'Outpat Record Submitter ID';
COMMENT ON COLUMN outpat_record.submit_datetime IS 'Outpat Record Submit Date time';
COMMENT ON COLUMN outpat_record.inpat_no IS 'Outpat Record Inpatient No';
COMMENT ON COLUMN outpat_record.mr_no IS 'Outpat Record MR No';
COMMENT ON COLUMN outpat_record.name IS 'Outpat Record Name';
COMMENT ON COLUMN outpat_record.sex IS 'Outpat Record Sex';
COMMENT ON COLUMN outpat_record.age_year IS 'Outpat Record Age Year';
COMMENT ON COLUMN outpat_record.age_month IS 'Outpat Record Age Month';
COMMENT ON COLUMN outpat_record.age IS 'Outpat Record Age';
COMMENT ON COLUMN surgery_application.institute_id IS 'Surgery Application Institute ID';
COMMENT ON COLUMN surgery_application.patient_id IS 'Surgery Application Patient ID';
COMMENT ON COLUMN surgery_application.visit_id IS 'Surgery Application Visit ID';
COMMENT ON COLUMN surgery_application.visit_type IS 'Surgery Application Visit Type';
COMMENT ON COLUMN surgery_application.application_id IS 'Surgery Application Application ID';
COMMENT ON COLUMN surgery_application.order_id IS 'Surgery Application Order ID';
COMMENT ON COLUMN surgery_application.dept_name IS 'Surgery Application Department Name';
COMMENT ON COLUMN surgery_application.surgery_name IS 'Surgery Application Surgery Name';
COMMENT ON COLUMN surgery_application.surgery_code IS 'Surgery Application Surgery Code';
COMMENT ON COLUMN surgery_application.surgery_level IS 'Surgery Application Surgery Level';
COMMENT ON COLUMN surgery_application.anesthesia_method IS 'Surgery Application Anesthesia Method';
COMMENT ON COLUMN surgery_application.surgeon IS 'Surgery Application Surgeon';
COMMENT ON COLUMN surgery_application.request_physician IS 'Surgery Application Request Physician';
COMMENT ON COLUMN surgery_application.request_surgery_datetime IS 'Surgery Application Request Surgery Date time';
COMMENT ON COLUMN surgery_application.record_content IS 'Surgery Application Record Content';
COMMENT ON COLUMN surgery_application.last_modifier IS 'Surgery Application Last Modifier';
COMMENT ON COLUMN surgery_application.last_modifier_id IS 'Surgery Application Last Modifier ID';
COMMENT ON COLUMN surgery_application.last_modified_datetime IS 'Surgery Application Last Modified Date time';
COMMENT ON COLUMN surgery_application.update_time IS 'Surgery Application Update Time';
COMMENT ON COLUMN surgery_application.inpat_no IS 'Surgery Application Inpatient No';
COMMENT ON COLUMN surgery_application.mr_no IS 'Surgery Application MR No';
COMMENT ON COLUMN surgery_application.name IS 'Surgery Application Name';
COMMENT ON COLUMN surgery_application.sex IS 'Surgery Application Sex';
COMMENT ON COLUMN surgery_application.age_year IS 'Surgery Application Age Year';
COMMENT ON COLUMN surgery_application.age_month IS 'Surgery Application Age Month';
COMMENT ON COLUMN surgery_application.age IS 'Surgery Application Age';
COMMENT ON COLUMN docpat_commu_record.institute_id IS 'Docpat Commu Record Institute ID';
COMMENT ON COLUMN docpat_commu_record.patient_id IS 'Docpat Commu Record Patient ID';
COMMENT ON COLUMN docpat_commu_record.visit_id IS 'Docpat Commu Record Visit ID';
COMMENT ON COLUMN docpat_commu_record.document_id IS 'Docpat Commu Record Document ID';
COMMENT ON COLUMN docpat_commu_record.visit_type IS 'Docpat Commu Record Visit Type';
COMMENT ON COLUMN docpat_commu_record.dept_name IS 'Docpat Commu Record Department Name';
COMMENT ON COLUMN docpat_commu_record.name IS 'Docpat Commu Record Name';
COMMENT ON COLUMN docpat_commu_record.sex IS 'Docpat Commu Record Sex';
COMMENT ON COLUMN docpat_commu_record.age_year IS 'Docpat Commu Record Age Year';
COMMENT ON COLUMN docpat_commu_record.pat_doc_comm_type IS 'Docpat Commu Record Pat Doc Comm Type';
COMMENT ON COLUMN docpat_commu_record.record_content IS 'Docpat Commu Record Record Content';
COMMENT ON COLUMN docpat_commu_record.record_datetime IS 'Docpat Commu Record Record Date time';
COMMENT ON COLUMN docpat_commu_record.last_modifier IS 'Docpat Commu Record Last Modifier';
COMMENT ON COLUMN docpat_commu_record.last_modifier_id IS 'Docpat Commu Record Last Modifier ID';
COMMENT ON COLUMN docpat_commu_record.last_modified_datetime IS 'Docpat Commu Record Last Modified Date time';
COMMENT ON COLUMN docpat_commu_record.update_time IS 'Docpat Commu Record Update Time';
COMMENT ON COLUMN docpat_commu_record.document_title IS 'Docpat Commu Record Document Title';
COMMENT ON COLUMN docpat_commu_record.document_status IS 'Docpat Commu Record Document Status';
COMMENT ON COLUMN docpat_commu_record.submitter IS 'Docpat Commu Record Submitter';
COMMENT ON COLUMN docpat_commu_record.submitter_id IS 'Docpat Commu Record Submitter ID';
COMMENT ON COLUMN docpat_commu_record.submit_datetime IS 'Docpat Commu Record Submit Date time';
COMMENT ON COLUMN daily_admission_record.institute_id IS 'Daily Admission Record Institute ID';
COMMENT ON COLUMN daily_admission_record.patient_id IS 'Daily Admission Record Patient ID';
COMMENT ON COLUMN daily_admission_record.visit_id IS 'Daily Admission Record Visit ID';
COMMENT ON COLUMN daily_admission_record.document_id IS 'Daily Admission Record Document ID';
COMMENT ON COLUMN daily_admission_record.visit_type IS 'Daily Admission Record Visit Type';
COMMENT ON COLUMN daily_admission_record.dept_name IS 'Daily Admission Record Department Name';
COMMENT ON COLUMN daily_admission_record.admission_datetime IS 'Daily Admission Record Admission Date time';
COMMENT ON COLUMN daily_admission_record.discharge_datetime IS 'Daily Admission Record Discharge Date time';
COMMENT ON COLUMN daily_admission_record.chief_complaint IS 'Daily Admission Record Chief Complaint';
COMMENT ON COLUMN daily_admission_record.admission_condition IS 'Daily Admission Record Admission Condition';
COMMENT ON COLUMN daily_admission_record.treatment_course IS 'Daily Admission Record Treatment Course';
COMMENT ON COLUMN daily_admission_record.discharge_condition IS 'Daily Admission Record Discharge Condition';
COMMENT ON COLUMN daily_admission_record.discharge_order IS 'Daily Admission Record Discharge Order';
COMMENT ON COLUMN daily_admission_record.record_content IS 'Daily Admission Record Record Content';
COMMENT ON COLUMN daily_admission_record.last_modifier IS 'Daily Admission Record Last Modifier';
COMMENT ON COLUMN daily_admission_record.last_modifier_id IS 'Daily Admission Record Last Modifier ID';
COMMENT ON COLUMN daily_admission_record.last_modified_datetime IS 'Daily Admission Record Last Modified Date time';
COMMENT ON COLUMN daily_admission_record.update_time IS 'Daily Admission Record Update Time';
COMMENT ON COLUMN daily_admission_record.document_title IS 'Daily Admission Record Document Title';
COMMENT ON COLUMN daily_admission_record.document_status IS 'Daily Admission Record Document Status';
COMMENT ON COLUMN daily_admission_record.submitter IS 'Daily Admission Record Submitter';
COMMENT ON COLUMN daily_admission_record.submitter_id IS 'Daily Admission Record Submitter ID';
COMMENT ON COLUMN daily_admission_record.submit_datetime IS 'Daily Admission Record Submit Date time';
COMMENT ON COLUMN daily_admission_record.inpat_no IS 'Daily Admission Record Inpatient No';
COMMENT ON COLUMN daily_admission_record.mr_no IS 'Daily Admission Record MR No';
COMMENT ON COLUMN daily_admission_record.name IS 'Daily Admission Record Name';
COMMENT ON COLUMN daily_admission_record.sex IS 'Daily Admission Record Sex';
COMMENT ON COLUMN daily_admission_record.age_year IS 'Daily Admission Record Age Year';
COMMENT ON COLUMN daily_admission_record.age_month IS 'Daily Admission Record Age Month';
COMMENT ON COLUMN daily_admission_record.age IS 'Daily Admission Record Age';
COMMENT ON COLUMN daily_death_record.institute_id IS 'Daily Death Record Institute ID';
COMMENT ON COLUMN daily_death_record.patient_id IS 'Daily Death Record Patient ID';
COMMENT ON COLUMN daily_death_record.visit_id IS 'Daily Death Record Visit ID';
COMMENT ON COLUMN daily_death_record.document_id IS 'Daily Death Record Document ID';
COMMENT ON COLUMN daily_death_record.visit_type IS 'Daily Death Record Visit Type';
COMMENT ON COLUMN daily_death_record.dept_name IS 'Daily Death Record Department Name';
COMMENT ON COLUMN daily_death_record.admission_condition IS 'Daily Death Record Admission Condition';
COMMENT ON COLUMN daily_death_record.treatment_course IS 'Daily Death Record Treatment Course';
COMMENT ON COLUMN daily_death_record.death_reason IS 'Daily Death Record Death Reason';
COMMENT ON COLUMN daily_death_record.death_datetime IS 'Daily Death Record Death Date time';
COMMENT ON COLUMN daily_death_record.record_content IS 'Daily Death Record Record Content';
COMMENT ON COLUMN daily_death_record.last_modifier IS 'Daily Death Record Last Modifier';
COMMENT ON COLUMN daily_death_record.last_modifier_id IS 'Daily Death Record Last Modifier ID';
COMMENT ON COLUMN daily_death_record.last_modified_datetime IS 'Daily Death Record Last Modified Date time';
COMMENT ON COLUMN daily_death_record.update_time IS 'Daily Death Record Update Time';
COMMENT ON COLUMN daily_death_record.document_title IS 'Daily Death Record Document Title';
COMMENT ON COLUMN daily_death_record.document_status IS 'Daily Death Record Document Status';
COMMENT ON COLUMN daily_death_record.submitter IS 'Daily Death Record Submitter';
COMMENT ON COLUMN daily_death_record.submitter_id IS 'Daily Death Record Submitter ID';
COMMENT ON COLUMN daily_death_record.submit_datetime IS 'Daily Death Record Submit Date time';
COMMENT ON COLUMN daily_death_record.inpat_no IS 'Daily Death Record Inpatient No';
COMMENT ON COLUMN daily_death_record.mr_no IS 'Daily Death Record MR No';
COMMENT ON COLUMN daily_death_record.name IS 'Daily Death Record Name';
COMMENT ON COLUMN daily_death_record.sex IS 'Daily Death Record Sex';
COMMENT ON COLUMN daily_death_record.age_year IS 'Daily Death Record Age Year';
COMMENT ON COLUMN daily_death_record.age_month IS 'Daily Death Record Age Month';
COMMENT ON COLUMN daily_death_record.age IS 'Daily Death Record Age';
COMMENT ON COLUMN preane_surveil_record.institute_id IS 'Preane Surveil Record Institute ID';
COMMENT ON COLUMN preane_surveil_record.patient_id IS 'Preane Surveil Record Patient ID';
COMMENT ON COLUMN preane_surveil_record.visit_id IS 'Preane Surveil Record Visit ID';
COMMENT ON COLUMN preane_surveil_record.document_id IS 'Preane Surveil Record Document ID';
COMMENT ON COLUMN preane_surveil_record.visit_type IS 'Preane Surveil Record Visit Type';
COMMENT ON COLUMN preane_surveil_record.dept_name IS 'Preane Surveil Record Department Name';
COMMENT ON COLUMN preane_surveil_record.condition_summary IS 'Preane Surveil Record Condition Summary';
COMMENT ON COLUMN preane_surveil_record.planned_anesthesia_method IS 'Preane Surveil Record Planned Anesthesia Method';
COMMENT ON COLUMN preane_surveil_record.ASA_level IS 'Preane Surveil Record ASA Level';
COMMENT ON COLUMN preane_surveil_record.record_content IS 'Preane Surveil Record Record Content';
COMMENT ON COLUMN preane_surveil_record.anesthetist_sign IS 'Preane Surveil Record Anesthetist Signature';
COMMENT ON COLUMN preane_surveil_record.last_modifier IS 'Preane Surveil Record Last Modifier';
COMMENT ON COLUMN preane_surveil_record.last_modifier_id IS 'Preane Surveil Record Last Modifier ID';
COMMENT ON COLUMN preane_surveil_record.last_modified_datetime IS 'Preane Surveil Record Last Modified Date time';
COMMENT ON COLUMN preane_surveil_record.update_time IS 'Preane Surveil Record Update Time';
COMMENT ON COLUMN preane_surveil_record.document_title IS 'Preane Surveil Record Document Title';
COMMENT ON COLUMN preane_surveil_record.document_status IS 'Preane Surveil Record Document Status';
COMMENT ON COLUMN preane_surveil_record.submitter IS 'Preane Surveil Record Submitter';
COMMENT ON COLUMN preane_surveil_record.submitter_id IS 'Preane Surveil Record Submitter ID';
COMMENT ON COLUMN preane_surveil_record.submit_datetime IS 'Preane Surveil Record Submit Date time';
COMMENT ON COLUMN preane_surveil_record.inpat_no IS 'Preane Surveil Record Inpatient No';
COMMENT ON COLUMN preane_surveil_record.mr_no IS 'Preane Surveil Record MR No';
COMMENT ON COLUMN preane_surveil_record.name IS 'Preane Surveil Record Name';
COMMENT ON COLUMN preane_surveil_record.sex IS 'Preane Surveil Record Sex';
COMMENT ON COLUMN preane_surveil_record.age_year IS 'Preane Surveil Record Age Year';
COMMENT ON COLUMN preane_surveil_record.age_month IS 'Preane Surveil Record Age Month';
COMMENT ON COLUMN preane_surveil_record.age IS 'Preane Surveil Record Age';
COMMENT ON COLUMN postane_surveil_record.institute_id IS 'Postane Surveil Record Institute ID';
COMMENT ON COLUMN postane_surveil_record.patient_id IS 'Postane Surveil Record Patient ID';
COMMENT ON COLUMN postane_surveil_record.visit_id IS 'Postane Surveil Record Visit ID';
COMMENT ON COLUMN postane_surveil_record.document_id IS 'Postane Surveil Record Document ID';
COMMENT ON COLUMN postane_surveil_record.visit_type IS 'Postane Surveil Record Visit Type';
COMMENT ON COLUMN postane_surveil_record.dept_name IS 'Postane Surveil Record Department Name';
COMMENT ON COLUMN postane_surveil_record.surgery_name IS 'Postane Surveil Record Surgery Name';
COMMENT ON COLUMN postane_surveil_record.anesthesia_method IS 'Postane Surveil Record Anesthesia Method';
COMMENT ON COLUMN postane_surveil_record.resume_descirption IS 'Postane Surveil Record Resume Descirption';
COMMENT ON COLUMN postane_surveil_record.record_content IS 'Postane Surveil Record Record Content';
COMMENT ON COLUMN postane_surveil_record.anesthetist_sign IS 'Postane Surveil Record Anesthetist Signature';
COMMENT ON COLUMN postane_surveil_record.last_modifier IS 'Postane Surveil Record Last Modifier';
COMMENT ON COLUMN postane_surveil_record.last_modifier_id IS 'Postane Surveil Record Last Modifier ID';
COMMENT ON COLUMN postane_surveil_record.last_modified_datetime IS 'Postane Surveil Record Last Modified Date time';
COMMENT ON COLUMN postane_surveil_record.update_time IS 'Postane Surveil Record Update Time';
COMMENT ON COLUMN postane_surveil_record.document_title IS 'Postane Surveil Record Document Title';
COMMENT ON COLUMN postane_surveil_record.document_status IS 'Postane Surveil Record Document Status';
COMMENT ON COLUMN postane_surveil_record.submitter IS 'Postane Surveil Record Submitter';
COMMENT ON COLUMN postane_surveil_record.submitter_id IS 'Postane Surveil Record Submitter ID';
COMMENT ON COLUMN postane_surveil_record.submit_datetime IS 'Postane Surveil Record Submit Date time';
COMMENT ON COLUMN postane_surveil_record.inpat_no IS 'Postane Surveil Record Inpatient No';
COMMENT ON COLUMN postane_surveil_record.mr_no IS 'Postane Surveil Record MR No';
COMMENT ON COLUMN postane_surveil_record.name IS 'Postane Surveil Record Name';
COMMENT ON COLUMN postane_surveil_record.sex IS 'Postane Surveil Record Sex';
COMMENT ON COLUMN postane_surveil_record.age_year IS 'Postane Surveil Record Age Year';
COMMENT ON COLUMN postane_surveil_record.age_month IS 'Postane Surveil Record Age Month';
COMMENT ON COLUMN postane_surveil_record.age IS 'Postane Surveil Record Age';
COMMENT ON COLUMN surgery_inform_consent.institute_id IS 'Surgery Inform Consent Institute ID';
COMMENT ON COLUMN surgery_inform_consent.patient_id IS 'Surgery Inform Consent Patient ID';
COMMENT ON COLUMN surgery_inform_consent.visit_id IS 'Surgery Inform Consent Visit ID';
COMMENT ON COLUMN surgery_inform_consent.document_id IS 'Surgery Inform Consent Document ID';
COMMENT ON COLUMN surgery_inform_consent.visit_type IS 'Surgery Inform Consent Visit Type';
COMMENT ON COLUMN surgery_inform_consent.dept_name IS 'Surgery Inform Consent Department Name';
COMMENT ON COLUMN surgery_inform_consent.planned_operation_name IS 'Surgery Inform Consent Planned Operation Name';
COMMENT ON COLUMN surgery_inform_consent.planned_operation_code IS 'Surgery Inform Consent Planned Operation Code';
COMMENT ON COLUMN surgery_inform_consent.planned_anesthesia_method IS 'Surgery Inform Consent Planned Anesthesia Method';
COMMENT ON COLUMN surgery_inform_consent.surgery_risk_description IS 'Surgery Inform Consent Surgery Risk Description';
COMMENT ON COLUMN surgery_inform_consent.record_content IS 'Surgery Inform Consent Record Content';
COMMENT ON COLUMN surgery_inform_consent.patient_sign IS 'Surgery Inform Consent Patient Signature';
COMMENT ON COLUMN surgery_inform_consent.surgeon_sign IS 'Surgery Inform Consent Surgeon Signature';
COMMENT ON COLUMN surgery_inform_consent.last_modifier IS 'Surgery Inform Consent Last Modifier';
COMMENT ON COLUMN surgery_inform_consent.last_modifier_id IS 'Surgery Inform Consent Last Modifier ID';
COMMENT ON COLUMN surgery_inform_consent.last_modified_datetime IS 'Surgery Inform Consent Last Modified Date time';
COMMENT ON COLUMN surgery_inform_consent.update_time IS 'Surgery Inform Consent Update Time';
COMMENT ON COLUMN surgery_inform_consent.document_title IS 'Surgery Inform Consent Document Title';
COMMENT ON COLUMN surgery_inform_consent.document_status IS 'Surgery Inform Consent Document Status';
COMMENT ON COLUMN surgery_inform_consent.submitter IS 'Surgery Inform Consent Submitter';
COMMENT ON COLUMN surgery_inform_consent.submitter_id IS 'Surgery Inform Consent Submitter ID';
COMMENT ON COLUMN surgery_inform_consent.submit_datetime IS 'Surgery Inform Consent Submit Date time';
COMMENT ON COLUMN surgery_inform_consent.inpat_no IS 'Surgery Inform Consent Inpatient No';
COMMENT ON COLUMN surgery_inform_consent.mr_no IS 'Surgery Inform Consent MR No';
COMMENT ON COLUMN surgery_inform_consent.name IS 'Surgery Inform Consent Name';
COMMENT ON COLUMN surgery_inform_consent.sex IS 'Surgery Inform Consent Sex';
COMMENT ON COLUMN surgery_inform_consent.age_year IS 'Surgery Inform Consent Age Year';
COMMENT ON COLUMN surgery_inform_consent.age_month IS 'Surgery Inform Consent Age Month';
COMMENT ON COLUMN surgery_inform_consent.age IS 'Surgery Inform Consent Age';
COMMENT ON COLUMN crisis_value_record.institute_id IS 'Crisis Value Record Institute ID';
COMMENT ON COLUMN crisis_value_record.patient_id IS 'Crisis Value Record Patient ID';
COMMENT ON COLUMN crisis_value_record.visit_id IS 'Crisis Value Record Visit ID';
COMMENT ON COLUMN crisis_value_record.document_id IS 'Crisis Value Record Document ID';
COMMENT ON COLUMN crisis_value_record.visit_type IS 'Crisis Value Record Visit Type';
COMMENT ON COLUMN crisis_value_record.dept_name IS 'Crisis Value Record Department Name';
COMMENT ON COLUMN crisis_value_record.record_content IS 'Crisis Value Record Record Content';
COMMENT ON COLUMN crisis_value_record.record_datetime IS 'Crisis Value Record Record Date time';
COMMENT ON COLUMN crisis_value_record.last_modifier IS 'Crisis Value Record Last Modifier';
COMMENT ON COLUMN crisis_value_record.last_modifier_id IS 'Crisis Value Record Last Modifier ID';
COMMENT ON COLUMN crisis_value_record.last_modified_datetime IS 'Crisis Value Record Last Modified Date time';
COMMENT ON COLUMN crisis_value_record.update_time IS 'Crisis Value Record Update Time';
COMMENT ON COLUMN crisis_value_record.document_title IS 'Crisis Value Record Document Title';
COMMENT ON COLUMN crisis_value_record.document_status IS 'Crisis Value Record Document Status';
COMMENT ON COLUMN crisis_value_record.submitter IS 'Crisis Value Record Submitter';
COMMENT ON COLUMN crisis_value_record.submitter_id IS 'Crisis Value Record Submitter ID';
COMMENT ON COLUMN crisis_value_record.submit_datetime IS 'Crisis Value Record Submit Date time';
COMMENT ON COLUMN crisis_value_record.inpat_no IS 'Crisis Value Record Inpatient No';
COMMENT ON COLUMN crisis_value_record.mr_no IS 'Crisis Value Record MR No';
COMMENT ON COLUMN crisis_value_record.name IS 'Crisis Value Record Name';
COMMENT ON COLUMN crisis_value_record.sex IS 'Crisis Value Record Sex';
COMMENT ON COLUMN crisis_value_record.age_year IS 'Crisis Value Record Age Year';
COMMENT ON COLUMN crisis_value_record.age_month IS 'Crisis Value Record Age Month';
COMMENT ON COLUMN crisis_value_record.age IS 'Crisis Value Record Age';
COMMENT ON COLUMN blood_application.institute_id IS 'Blood Application Institute ID';
COMMENT ON COLUMN blood_application.patient_id IS 'Blood Application Patient ID';
COMMENT ON COLUMN blood_application.visit_id IS 'Blood Application Visit ID';
COMMENT ON COLUMN blood_application.visit_type IS 'Blood Application Visit Type';
COMMENT ON COLUMN blood_application.application_id IS 'Blood Application Application ID';
COMMENT ON COLUMN blood_application.inpat_no IS 'Blood Application Inpatient No';
COMMENT ON COLUMN blood_application.dept_name IS 'Blood Application Department Name';
COMMENT ON COLUMN blood_application.name IS 'Blood Application Name';
COMMENT ON COLUMN blood_application.sex IS 'Blood Application Sex';
COMMENT ON COLUMN blood_application.age_year IS 'Blood Application Age Year';
COMMENT ON COLUMN blood_application.patient_bloodtype_abo IS 'Blood Application Patient Bloodtype ABO';
COMMENT ON COLUMN blood_application.patient_bloodtype_rhd IS 'Blood Application Patient Bloodtype Rhd';
COMMENT ON COLUMN blood_application.transfuse_variety IS 'Blood Application Transfuse Variety';
COMMENT ON COLUMN blood_application.transfuse_volume IS 'Blood Application Transfuse Volume';
COMMENT ON COLUMN blood_application.transfuse_volume_unit IS 'Blood Application Transfuse Volume Unit';
COMMENT ON COLUMN blood_application.request_datetime IS 'Blood Application Request Date time';
COMMENT ON COLUMN blood_application.physician_name IS 'Blood Application Physician Name';
COMMENT ON COLUMN blood_application.record_content IS 'Blood Application Record Content';
COMMENT ON COLUMN blood_application.last_modifier IS 'Blood Application Last Modifier';
COMMENT ON COLUMN blood_application.last_modifier_id IS 'Blood Application Last Modifier ID';
COMMENT ON COLUMN blood_application.last_modified_datetime IS 'Blood Application Last Modified Date time';
COMMENT ON COLUMN blood_application.update_time IS 'Blood Application Update Time';
COMMENT ON COLUMN surgery_inventory_record.institute_id IS 'Surgery Inventory Record Institute ID';
COMMENT ON COLUMN surgery_inventory_record.patient_id IS 'Surgery Inventory Record Patient ID';
COMMENT ON COLUMN surgery_inventory_record.visit_id IS 'Surgery Inventory Record Visit ID';
COMMENT ON COLUMN surgery_inventory_record.document_id IS 'Surgery Inventory Record Document ID';
COMMENT ON COLUMN surgery_inventory_record.visit_type IS 'Surgery Inventory Record Visit Type';
COMMENT ON COLUMN surgery_inventory_record.dept_name IS 'Surgery Inventory Record Department Name';
COMMENT ON COLUMN surgery_inventory_record.surgery_room_name IS 'Surgery Inventory Record Surgery Room Name';
COMMENT ON COLUMN surgery_inventory_record.surgery_date IS 'Surgery Inventory Record Surgery Date';
COMMENT ON COLUMN surgery_inventory_record.surgery_name IS 'Surgery Inventory Record Surgery Name';
COMMENT ON COLUMN surgery_inventory_record.record_content IS 'Surgery Inventory Record Record Content';
COMMENT ON COLUMN surgery_inventory_record.last_modifier IS 'Surgery Inventory Record Last Modifier';
COMMENT ON COLUMN surgery_inventory_record.last_modifier_id IS 'Surgery Inventory Record Last Modifier ID';
COMMENT ON COLUMN surgery_inventory_record.last_modified_datetime IS 'Surgery Inventory Record Last Modified Date time';
COMMENT ON COLUMN surgery_inventory_record.update_time IS 'Surgery Inventory Record Update Time';
COMMENT ON COLUMN surgery_inventory_record.document_title IS 'Surgery Inventory Record Document Title';
COMMENT ON COLUMN surgery_inventory_record.document_status IS 'Surgery Inventory Record Document Status';
COMMENT ON COLUMN surgery_inventory_record.submitter IS 'Surgery Inventory Record Submitter';
COMMENT ON COLUMN surgery_inventory_record.submitter_id IS 'Surgery Inventory Record Submitter ID';
COMMENT ON COLUMN surgery_inventory_record.submit_datetime IS 'Surgery Inventory Record Submit Date time';
COMMENT ON COLUMN surgery_inventory_record.inpat_no IS 'Surgery Inventory Record Inpatient No';
COMMENT ON COLUMN surgery_inventory_record.mr_no IS 'Surgery Inventory Record MR No';
COMMENT ON COLUMN surgery_inventory_record.name IS 'Surgery Inventory Record Name';
COMMENT ON COLUMN surgery_inventory_record.sex IS 'Surgery Inventory Record Sex';
COMMENT ON COLUMN surgery_inventory_record.age_year IS 'Surgery Inventory Record Age Year';
COMMENT ON COLUMN surgery_inventory_record.age_month IS 'Surgery Inventory Record Age Month';
COMMENT ON COLUMN surgery_inventory_record.age IS 'Surgery Inventory Record Age';
COMMENT ON COLUMN sys_users.id IS 'Sys Users ID';
COMMENT ON COLUMN sys_users.username IS 'Sys Users Username';
COMMENT ON COLUMN sys_users.email IS 'Sys Users Email';
COMMENT ON COLUMN sys_users.password_hash IS 'Sys Users Password Hash';
COMMENT ON COLUMN sys_users.display_name IS 'Sys Users Display Name';
COMMENT ON COLUMN sys_users.department IS 'Sys Users Department';
COMMENT ON COLUMN sys_users.role IS 'Sys Users Role';
COMMENT ON COLUMN sys_users.roles_json IS 'Sys Users Roles Json';
COMMENT ON COLUMN sys_users.is_active IS 'Sys Users IS Active';
COMMENT ON COLUMN sys_users.last_login_at IS 'Sys Users Last Login AT';
COMMENT ON COLUMN sys_users.created_at IS 'Sys Users Created AT';
COMMENT ON COLUMN sys_users.updated_at IS 'Sys Users Updated AT';
COMMENT ON COLUMN sys_departments.id IS 'Sys Departments ID';
COMMENT ON COLUMN sys_departments.code IS 'Sys Departments Code';
COMMENT ON COLUMN sys_departments.name IS 'Sys Departments Name';
COMMENT ON COLUMN sys_departments.category IS 'Sys Departments Category';
COMMENT ON COLUMN sys_departments.is_active IS 'Sys Departments IS Active';
COMMENT ON COLUMN sys_departments.sort_order IS 'Sys Departments Sort Order';
COMMENT ON COLUMN sys_departments.created_at IS 'Sys Departments Created AT';
COMMENT ON COLUMN sys_departments.updated_at IS 'Sys Departments Updated AT';
COMMENT ON COLUMN qc_results.id IS 'QC Results ID';
COMMENT ON COLUMN qc_results.record_id IS 'QC Results Record ID';
COMMENT ON COLUMN qc_results.rule_set IS 'QC Results Rule Set';
COMMENT ON COLUMN qc_results.overall_score IS 'QC Results Overall Score';
COMMENT ON COLUMN qc_results.grade IS 'QC Results Grade';
COMMENT ON COLUMN qc_results.defect_count IS 'QC Results Defect Count';
COMMENT ON COLUMN qc_results.analysis_engine IS 'QC Results Analysis Engine';
COMMENT ON COLUMN qc_results.analysis_date IS 'QC Results Analysis Date';
COMMENT ON COLUMN qc_results.raw_output IS 'QC Results Raw Output';
COMMENT ON COLUMN qc_results.created_by IS 'QC Results Created BY';
COMMENT ON COLUMN qc_results.created_at IS 'QC Results Created AT';
COMMENT ON COLUMN qc_results.updated_at IS 'QC Results Updated AT';
COMMENT ON COLUMN qc_defects.id IS 'QC Defects ID';
COMMENT ON COLUMN qc_defects.result_id IS 'QC Defects Result ID';
COMMENT ON COLUMN qc_defects.record_id IS 'QC Defects Record ID';
COMMENT ON COLUMN qc_defects.department IS 'QC Defects Department';
COMMENT ON COLUMN qc_defects.rule_code IS 'QC Defects Rule Code';
COMMENT ON COLUMN qc_defects.rule_name IS 'QC Defects Rule Name';
COMMENT ON COLUMN qc_defects.description IS 'QC Defects Description';
COMMENT ON COLUMN qc_defects.severity IS 'QC Defects Severity';
COMMENT ON COLUMN qc_defects.category IS 'QC Defects Category';
COMMENT ON COLUMN qc_defects.deduct_score IS 'QC Defects Deduct Score';
COMMENT ON COLUMN qc_defects.location IS 'QC Defects Location';
COMMENT ON COLUMN qc_defects.evidence IS 'QC Defects Evidence';
COMMENT ON COLUMN qc_defects.suggestion IS 'QC Defects Suggestion';
COMMENT ON COLUMN qc_defects.status IS 'QC Defects Status';
COMMENT ON COLUMN qc_defects.urged_at IS 'QC Defects Urged AT';
COMMENT ON COLUMN qc_defects.urged_by IS 'QC Defects Urged BY';
COMMENT ON COLUMN qc_defects.urged_message IS 'QC Defects Urged Message';
COMMENT ON COLUMN qc_defects.urged_deadline IS 'QC Defects Urged Deadline';
COMMENT ON COLUMN qc_defects.remediated_at IS 'QC Defects Remediated AT';
COMMENT ON COLUMN qc_defects.remediated_by IS 'QC Defects Remediated BY';
COMMENT ON COLUMN qc_defects.remediation_note IS 'QC Defects Remediation Note';
COMMENT ON COLUMN qc_defects.remediation_evidence IS 'QC Defects Remediation Evidence';
COMMENT ON COLUMN qc_defects.approved_at IS 'QC Defects Approved AT';
COMMENT ON COLUMN qc_defects.approved_by IS 'QC Defects Approved BY';
COMMENT ON COLUMN qc_defects.approve_comment IS 'QC Defects Approve Comment';
COMMENT ON COLUMN qc_defects.rejected_at IS 'QC Defects Rejected AT';
COMMENT ON COLUMN qc_defects.rejected_by IS 'QC Defects Rejected BY';
COMMENT ON COLUMN qc_defects.reject_reason IS 'QC Defects Reject Reason';
COMMENT ON COLUMN qc_defects.reject_suggestion IS 'QC Defects Reject Suggestion';
COMMENT ON COLUMN qc_defects.created_at IS 'QC Defects Created AT';
COMMENT ON COLUMN qc_defects.updated_at IS 'QC Defects Updated AT';
COMMENT ON COLUMN qc_defect_history.id IS 'QC Defect History ID';
COMMENT ON COLUMN qc_defect_history.defect_id IS 'QC Defect History Defect ID';
COMMENT ON COLUMN qc_defect_history.action IS 'QC Defect History Action';
COMMENT ON COLUMN qc_defect_history.actor_id IS 'QC Defect History Actor ID';
COMMENT ON COLUMN qc_defect_history.actor_name IS 'QC Defect History Actor Name';
COMMENT ON COLUMN qc_defect_history.details IS 'QC Defect History Details';
COMMENT ON COLUMN qc_defect_history.created_at IS 'QC Defect History Created AT';
COMMENT ON COLUMN qc_tasks.id IS 'QC Tasks ID';
COMMENT ON COLUMN qc_tasks.task_number IS 'QC Tasks Task Number';
COMMENT ON COLUMN qc_tasks.task_name IS 'QC Tasks Task Name';
COMMENT ON COLUMN qc_tasks.task_type IS 'QC Tasks Task Type';
COMMENT ON COLUMN qc_tasks.schedule_config IS 'QC Tasks Schedule Config';
COMMENT ON COLUMN qc_tasks.date_range IS 'QC Tasks Date Range';
COMMENT ON COLUMN qc_tasks.department_filter IS 'QC Tasks Department Filter';
COMMENT ON COLUMN qc_tasks.record_ids IS 'QC Tasks Record Ids';
COMMENT ON COLUMN qc_tasks.sampling_method IS 'QC Tasks Sampling Method';
COMMENT ON COLUMN qc_tasks.sampling_config IS 'QC Tasks Sampling Config';
COMMENT ON COLUMN qc_tasks.assign_method IS 'QC Tasks Assign Method';
COMMENT ON COLUMN qc_tasks.assignee_config IS 'QC Tasks Assignee Config';
COMMENT ON COLUMN qc_tasks.status IS 'QC Tasks Status';
COMMENT ON COLUMN qc_tasks.progress IS 'QC Tasks Progress';
COMMENT ON COLUMN qc_tasks.total_records IS 'QC Tasks Total Records';
COMMENT ON COLUMN qc_tasks.completed_records IS 'QC Tasks Completed Records';
COMMENT ON COLUMN qc_tasks.creator_id IS 'QC Tasks Creator ID';
COMMENT ON COLUMN qc_tasks.creator_name IS 'QC Tasks Creator Name';
COMMENT ON COLUMN qc_tasks.deadline IS 'QC Tasks Deadline';
COMMENT ON COLUMN qc_tasks.created_at IS 'QC Tasks Created AT';
COMMENT ON COLUMN qc_tasks.updated_at IS 'QC Tasks Updated AT';
COMMENT ON COLUMN qc_task_records.id IS 'QC Task Records ID';
COMMENT ON COLUMN qc_task_records.task_id IS 'QC Task Records Task ID';
COMMENT ON COLUMN qc_task_records.record_id IS 'QC Task Records Record ID';
COMMENT ON COLUMN qc_task_records.assignee_id IS 'QC Task Records Assignee ID';
COMMENT ON COLUMN qc_task_records.assignee_name IS 'QC Task Records Assignee Name';
COMMENT ON COLUMN qc_task_records.status IS 'QC Task Records Status';
COMMENT ON COLUMN qc_task_records.score IS 'QC Task Records Score';
COMMENT ON COLUMN qc_task_records.defect_count IS 'QC Task Records Defect Count';
COMMENT ON COLUMN qc_task_records.completed_at IS 'QC Task Records Completed AT';
COMMENT ON COLUMN qc_task_records.created_at IS 'QC Task Records Created AT';
COMMENT ON COLUMN qc_appeals.id IS 'QC Appeals ID';
COMMENT ON COLUMN qc_appeals.appeal_number IS 'QC Appeals Appeal Number';
COMMENT ON COLUMN qc_appeals.qc_result_id IS 'QC Appeals QC Result ID';
COMMENT ON COLUMN qc_appeals.record_id IS 'QC Appeals Record ID';
COMMENT ON COLUMN qc_appeals.appeal_type IS 'QC Appeals Appeal Type';
COMMENT ON COLUMN qc_appeals.defect_item IS 'QC Appeals Defect Item';
COMMENT ON COLUMN qc_appeals.reason IS 'QC Appeals Reason';
COMMENT ON COLUMN qc_appeals.evidence IS 'QC Appeals Evidence';
COMMENT ON COLUMN qc_appeals.priority IS 'QC Appeals Priority';
COMMENT ON COLUMN qc_appeals.appellant_id IS 'QC Appeals Appellant ID';
COMMENT ON COLUMN qc_appeals.appellant_name IS 'QC Appeals Appellant Name';
COMMENT ON COLUMN qc_appeals.appellant_department IS 'QC Appeals Appellant Department';
COMMENT ON COLUMN qc_appeals.reviewer_id IS 'QC Appeals Reviewer ID';
COMMENT ON COLUMN qc_appeals.reviewer_name IS 'QC Appeals Reviewer Name';
COMMENT ON COLUMN qc_appeals.review_result IS 'QC Appeals Review Result';
COMMENT ON COLUMN qc_appeals.review_date IS 'QC Appeals Review Date';
COMMENT ON COLUMN qc_appeals.resolution IS 'QC Appeals Resolution';
COMMENT ON COLUMN qc_appeals.resolution_date IS 'QC Appeals Resolution Date';
COMMENT ON COLUMN qc_appeals.notes IS 'QC Appeals Notes';
COMMENT ON COLUMN qc_appeals.status IS 'QC Appeals Status';
COMMENT ON COLUMN qc_appeals.created_at IS 'QC Appeals Created AT';
COMMENT ON COLUMN qc_appeals.updated_at IS 'QC Appeals Updated AT';
COMMENT ON COLUMN qc_appeal_reviews.id IS 'QC Appeal Reviews ID';
COMMENT ON COLUMN qc_appeal_reviews.appeal_id IS 'QC Appeal Reviews Appeal ID';
COMMENT ON COLUMN qc_appeal_reviews.reviewer_id IS 'QC Appeal Reviews Reviewer ID';
COMMENT ON COLUMN qc_appeal_reviews.reviewer_name IS 'QC Appeal Reviews Reviewer Name';
COMMENT ON COLUMN qc_appeal_reviews.reviewer_role IS 'QC Appeal Reviews Reviewer Role';
COMMENT ON COLUMN qc_appeal_reviews.action IS 'QC Appeal Reviews Action';
COMMENT ON COLUMN qc_appeal_reviews.comment IS 'QC Appeal Reviews Comment';
COMMENT ON COLUMN qc_appeal_reviews.metadata IS 'QC Appeal Reviews Metadata';
COMMENT ON COLUMN qc_appeal_reviews.created_at IS 'QC Appeal Reviews Created AT';
COMMENT ON COLUMN qc_remediation_tasks.id IS 'QC Remediation Tasks ID';
COMMENT ON COLUMN qc_remediation_tasks.task_number IS 'QC Remediation Tasks Task Number';
COMMENT ON COLUMN qc_remediation_tasks.qc_result_id IS 'QC Remediation Tasks QC Result ID';
COMMENT ON COLUMN qc_remediation_tasks.record_id IS 'QC Remediation Tasks Record ID';
COMMENT ON COLUMN qc_remediation_tasks.defect_type IS 'QC Remediation Tasks Defect Type';
COMMENT ON COLUMN qc_remediation_tasks.defect_description IS 'QC Remediation Tasks Defect Description';
COMMENT ON COLUMN qc_remediation_tasks.defect_location IS 'QC Remediation Tasks Defect Location';
COMMENT ON COLUMN qc_remediation_tasks.severity IS 'QC Remediation Tasks Severity';
COMMENT ON COLUMN qc_remediation_tasks.remediation_requirement IS 'QC Remediation Tasks Remediation Requirement';
COMMENT ON COLUMN qc_remediation_tasks.deadline IS 'QC Remediation Tasks Deadline';
COMMENT ON COLUMN qc_remediation_tasks.assignee_id IS 'QC Remediation Tasks Assignee ID';
COMMENT ON COLUMN qc_remediation_tasks.assignee_name IS 'QC Remediation Tasks Assignee Name';
COMMENT ON COLUMN qc_remediation_tasks.assignee_department IS 'QC Remediation Tasks Assignee Department';
COMMENT ON COLUMN qc_remediation_tasks.status IS 'QC Remediation Tasks Status';
COMMENT ON COLUMN qc_remediation_tasks.remediation_description IS 'QC Remediation Tasks Remediation Description';
COMMENT ON COLUMN qc_remediation_tasks.remediation_evidence IS 'QC Remediation Tasks Remediation Evidence';
COMMENT ON COLUMN qc_remediation_tasks.submitted_at IS 'QC Remediation Tasks Submitted AT';
COMMENT ON COLUMN qc_remediation_tasks.reviewer_id IS 'QC Remediation Tasks Reviewer ID';
COMMENT ON COLUMN qc_remediation_tasks.reviewer_name IS 'QC Remediation Tasks Reviewer Name';
COMMENT ON COLUMN qc_remediation_tasks.review_comment IS 'QC Remediation Tasks Review Comment';
COMMENT ON COLUMN qc_remediation_tasks.reviewed_at IS 'QC Remediation Tasks Reviewed AT';
COMMENT ON COLUMN qc_remediation_tasks.notes IS 'QC Remediation Tasks Notes';
COMMENT ON COLUMN qc_remediation_tasks.created_at IS 'QC Remediation Tasks Created AT';
COMMENT ON COLUMN qc_remediation_tasks.updated_at IS 'QC Remediation Tasks Updated AT';
COMMENT ON COLUMN qc_remediation_tasks.closed_at IS 'QC Remediation Tasks Closed AT';
COMMENT ON COLUMN qc_remediation_history.id IS 'QC Remediation History ID';
COMMENT ON COLUMN qc_remediation_history.task_id IS 'QC Remediation History Task ID';
COMMENT ON COLUMN qc_remediation_history.action IS 'QC Remediation History Action';
COMMENT ON COLUMN qc_remediation_history.actor_id IS 'QC Remediation History Actor ID';
COMMENT ON COLUMN qc_remediation_history.actor_name IS 'QC Remediation History Actor Name';
COMMENT ON COLUMN qc_remediation_history.old_status IS 'QC Remediation History Old Status';
COMMENT ON COLUMN qc_remediation_history.new_status IS 'QC Remediation History New Status';
COMMENT ON COLUMN qc_remediation_history.comment IS 'QC Remediation History Comment';
COMMENT ON COLUMN qc_remediation_history.metadata IS 'QC Remediation History Metadata';
COMMENT ON COLUMN qc_remediation_history.created_at IS 'QC Remediation History Created AT';
COMMENT ON COLUMN qc_rules.id IS 'QC Rules ID';
COMMENT ON COLUMN qc_rules.rule_code IS 'QC Rules Rule Code';
COMMENT ON COLUMN qc_rules.name IS 'QC Rules Name';
COMMENT ON COLUMN qc_rules.description IS 'QC Rules Description';
COMMENT ON COLUMN qc_rules.category IS 'QC Rules Category';
COMMENT ON COLUMN qc_rules.severity IS 'QC Rules Severity';
COMMENT ON COLUMN qc_rules.scope IS 'QC Rules Scope';
COMMENT ON COLUMN qc_rules.department_id IS 'QC Rules Department ID';
COMMENT ON COLUMN qc_rules.parent_rule_id IS 'QC Rules Parent Rule ID';
COMMENT ON COLUMN qc_rules.override_action IS 'QC Rules Override Action';
COMMENT ON COLUMN qc_rules.override_config IS 'QC Rules Override Config';
COMMENT ON COLUMN qc_rules.priority IS 'QC Rules Priority';
COMMENT ON COLUMN qc_rules.status IS 'QC Rules Status';
COMMENT ON COLUMN qc_rules.version IS 'QC Rules Version';
COMMENT ON COLUMN qc_rules.effective_from IS 'QC Rules Effective From';
COMMENT ON COLUMN qc_rules.effective_to IS 'QC Rules Effective TO';
COMMENT ON COLUMN qc_rules.check_logic IS 'QC Rules Check Logic';
COMMENT ON COLUMN qc_rules.scoring_config IS 'QC Rules Scoring Config';
COMMENT ON COLUMN qc_rules.applicable_documents IS 'QC Rules Applicable Documents';
COMMENT ON COLUMN qc_rules.primary_document_category IS 'QC Rules Primary Document Category';
COMMENT ON COLUMN qc_rules.is_active IS 'QC Rules IS Active';
COMMENT ON COLUMN qc_rules.metadata IS 'QC Rules Metadata';
COMMENT ON COLUMN qc_rules.approved_by IS 'QC Rules Approved BY';
COMMENT ON COLUMN qc_rules.approved_at IS 'QC Rules Approved AT';
COMMENT ON COLUMN qc_rules.created_at IS 'QC Rules Created AT';
COMMENT ON COLUMN qc_rules.updated_at IS 'QC Rules Updated AT';
COMMENT ON COLUMN qc_coder_workload_daily.id IS 'QC Coder Workload Daily ID';
COMMENT ON COLUMN qc_coder_workload_daily.stat_date IS 'QC Coder Workload Daily Stat Date';
COMMENT ON COLUMN qc_coder_workload_daily.coder_id IS 'QC Coder Workload Daily Coder ID';
COMMENT ON COLUMN qc_coder_workload_daily.coder_name IS 'QC Coder Workload Daily Coder Name';
COMMENT ON COLUMN qc_coder_workload_daily.department_id IS 'QC Coder Workload Daily Department ID';
COMMENT ON COLUMN qc_coder_workload_daily.department_name IS 'QC Coder Workload Daily Department Name';
COMMENT ON COLUMN qc_coder_workload_daily.qc_count IS 'QC Coder Workload Daily QC Count';
COMMENT ON COLUMN qc_coder_workload_daily.recheck_count IS 'QC Coder Workload Daily Recheck Count';
COMMENT ON COLUMN qc_coder_workload_daily.defect_found IS 'QC Coder Workload Daily Defect Found';
COMMENT ON COLUMN qc_coder_workload_daily.passed_count IS 'QC Coder Workload Daily Passed Count';
COMMENT ON COLUMN qc_coder_workload_daily.warning_count IS 'QC Coder Workload Daily Warning Count';
COMMENT ON COLUMN qc_coder_workload_daily.failed_count IS 'QC Coder Workload Daily Failed Count';
COMMENT ON COLUMN qc_coder_workload_daily.avg_handle_seconds IS 'QC Coder Workload Daily Avg Handle Seconds';
COMMENT ON COLUMN qc_coder_workload_daily.created_at IS 'QC Coder Workload Daily Created AT';
COMMENT ON COLUMN qc_coder_workload_daily.updated_at IS 'QC Coder Workload Daily Updated AT';
COMMENT ON COLUMN medical_documents.id IS 'Medical Documents ID';
COMMENT ON COLUMN medical_documents.record_id IS 'Medical Documents Record ID';
COMMENT ON COLUMN medical_documents.document_type IS 'Medical Documents Document Type';
COMMENT ON COLUMN medical_documents.content IS 'Medical Documents Content';
COMMENT ON COLUMN medical_documents.qc_status IS 'Medical Documents QC Status';
COMMENT ON COLUMN medical_documents.qc_score IS 'Medical Documents QC Score';
COMMENT ON COLUMN medical_documents.qc_last_analyzed IS 'Medical Documents QC Last Analyzed';
COMMENT ON COLUMN medical_documents.status IS 'Medical Documents Status';
COMMENT ON COLUMN medical_documents.created_at IS 'Medical Documents Created AT';
COMMENT ON COLUMN medical_documents.updated_at IS 'Medical Documents Updated AT';
COMMENT ON COLUMN scoring_rules.id IS 'Scoring Rules ID';
COMMENT ON COLUMN scoring_rules.sort_order IS 'Scoring Rules Sort Order';
COMMENT ON COLUMN scoring_rules.category IS 'Scoring Rules Category';
COMMENT ON COLUMN scoring_rules.name IS 'Scoring Rules Name';
COMMENT ON COLUMN scoring_rules.description IS 'Scoring Rules Description';
COMMENT ON COLUMN scoring_rules.deduction IS 'Scoring Rules Deduction';
COMMENT ON COLUMN scoring_rules.max_deduction IS 'Scoring Rules Max Deduction';
COMMENT ON COLUMN scoring_rules.veto IS 'Scoring Rules Veto';
COMMENT ON COLUMN scoring_rules.severity IS 'Scoring Rules Severity';
COMMENT ON COLUMN scoring_rules.enabled IS 'Scoring Rules Enabled';
COMMENT ON COLUMN scoring_rules.created_at IS 'Scoring Rules Created AT';
COMMENT ON COLUMN scoring_rules.updated_at IS 'Scoring Rules Updated AT';
COMMENT ON COLUMN scoring_config.id IS 'Scoring Config ID';
COMMENT ON COLUMN scoring_config.config_key IS 'Scoring Config Config Key';
COMMENT ON COLUMN scoring_config.config_value IS 'Scoring Config Config Value';
COMMENT ON COLUMN scoring_config.description IS 'Scoring Config Description';
COMMENT ON COLUMN scoring_config.updated_by IS 'Scoring Config Updated BY';
COMMENT ON COLUMN scoring_config.updated_at IS 'Scoring Config Updated AT';
COMMENT ON COLUMN notifications.id IS 'Notifications ID';
COMMENT ON COLUMN notifications.type IS 'Notifications Type';
COMMENT ON COLUMN notifications.title IS 'Notifications Title';
COMMENT ON COLUMN notifications.content IS 'Notifications Content';
COMMENT ON COLUMN notifications.record_id IS 'Notifications Record ID';
COMMENT ON COLUMN notifications.severity IS 'Notifications Severity';
COMMENT ON COLUMN notifications.sender_id IS 'Notifications Sender ID';
COMMENT ON COLUMN notifications.recipient_id IS 'Notifications Recipient ID';
COMMENT ON COLUMN notifications.related_type IS 'Notifications Related Type';
COMMENT ON COLUMN notifications.related_id IS 'Notifications Related ID';
COMMENT ON COLUMN notifications.is_read IS 'Notifications IS Read';
COMMENT ON COLUMN notifications.read_at IS 'Notifications Read AT';
COMMENT ON COLUMN notifications.created_at IS 'Notifications Created AT';
COMMENT ON COLUMN sync_visit_status.institute_id IS 'Sync Visit Status Institute ID';
COMMENT ON COLUMN sync_visit_status.patient_id IS 'Sync Visit Status Patient ID';
COMMENT ON COLUMN sync_visit_status.visit_id IS 'Sync Visit Status Visit ID';
COMMENT ON COLUMN sync_visit_status.sync_status IS 'Sync Visit Status Sync Status';
COMMENT ON COLUMN sync_visit_status.discharge_date IS 'Sync Visit Status Discharge Date';
COMMENT ON COLUMN sync_visit_status.department IS 'Sync Visit Status Department';
COMMENT ON COLUMN sync_visit_status.mongo_update_time IS 'Sync Visit Status Mongo Update Time';
COMMENT ON COLUMN sync_visit_status.local_synced_at IS 'Sync Visit Status Local Synced AT';
COMMENT ON COLUMN sync_visit_status.tier1_at IS 'Sync Visit Status Tier1 AT';
COMMENT ON COLUMN sync_visit_status.tier2_at IS 'Sync Visit Status Tier2 AT';
COMMENT ON COLUMN sync_visit_status.tier3_at IS 'Sync Visit Status Tier3 AT';
COMMENT ON COLUMN sync_visit_status.retry_count IS 'Sync Visit Status Retry Count';
COMMENT ON COLUMN sync_visit_status.last_error IS 'Sync Visit Status Last Error';
COMMENT ON COLUMN sync_visit_status.created_at IS 'Sync Visit Status Created AT';
COMMENT ON COLUMN sync_visit_status.updated_at IS 'Sync Visit Status Updated AT';
COMMENT ON COLUMN sync_watermarks.collection_name IS 'Sync Watermarks Collection Name';
COMMENT ON COLUMN sync_watermarks.source_type IS 'Sync Watermarks Source Type';
COMMENT ON COLUMN sync_watermarks.last_sync_cursor IS 'Sync Watermarks Last Sync Cursor';
COMMENT ON COLUMN sync_watermarks.last_sync_id IS 'Sync Watermarks Last Sync ID';
COMMENT ON COLUMN sync_watermarks.last_sync_status IS 'Sync Watermarks Last Sync Status';
COMMENT ON COLUMN sync_watermarks.last_record_count IS 'Sync Watermarks Last Record Count';
COMMENT ON COLUMN sync_watermarks.last_sync_at IS 'Sync Watermarks Last Sync AT';
COMMENT ON COLUMN sync_watermarks.last_error IS 'Sync Watermarks Last Error';
COMMENT ON COLUMN sync_watermarks.created_at IS 'Sync Watermarks Created AT';
COMMENT ON COLUMN sync_watermarks.updated_at IS 'Sync Watermarks Updated AT';

COMMIT;
