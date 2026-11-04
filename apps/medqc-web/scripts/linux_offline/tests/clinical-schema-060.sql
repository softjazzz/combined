--
-- PostgreSQL database dump
--


-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: cdm; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA cdm;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: admission_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.admission_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    admission_datetime timestamp without time zone,
    record_datetime timestamp without time zone,
    admission_route character varying(100),
    dept_name character varying(100),
    ward_name character varying(100),
    ward_no character varying(100),
    bed_no character varying(100),
    admission_reason character varying(100),
    chief_complaint text,
    history_of_present_illness text,
    past_history text,
    allergy_history text,
    personal_history text,
    family_history text,
    checkup text,
    checkup_temperature character varying(100),
    checkup_heartrate character varying(100),
    checkup_respiratoryrate character varying(100),
    checkup_systolicpressure character varying(100),
    checkup_diastolicpressure character varying(100),
    checkup_height character varying(100),
    checkup_weight character varying(100),
    assist_exam text,
    record_content text,
    resident_physician_sign character varying(100),
    attending_physician_sign character varying(100),
    chief_physician_sign character varying(100),
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_id character varying(100),
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN admission_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.institute_id IS '机构号';


--
-- Name: COLUMN admission_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.patient_id IS '患者号';


--
-- Name: COLUMN admission_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.visit_id IS '就诊号';


--
-- Name: COLUMN admission_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.visit_type IS '就诊类型';


--
-- Name: COLUMN admission_record.admission_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.admission_datetime IS '入院时间';


--
-- Name: COLUMN admission_record.record_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.record_datetime IS '入院记录时间';


--
-- Name: COLUMN admission_record.admission_route; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.admission_route IS '入院途径';


--
-- Name: COLUMN admission_record.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.dept_name IS '入院科室';


--
-- Name: COLUMN admission_record.ward_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.ward_name IS '入院病区';


--
-- Name: COLUMN admission_record.ward_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.ward_no IS '病房号';


--
-- Name: COLUMN admission_record.bed_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.bed_no IS '病床号';


--
-- Name: COLUMN admission_record.admission_reason; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.admission_reason IS '入院原因';


--
-- Name: COLUMN admission_record.chief_complaint; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.chief_complaint IS '主诉';


--
-- Name: COLUMN admission_record.history_of_present_illness; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.history_of_present_illness IS '现病史';


--
-- Name: COLUMN admission_record.past_history; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.past_history IS '既往史';


--
-- Name: COLUMN admission_record.allergy_history; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.allergy_history IS '过敏史';


--
-- Name: COLUMN admission_record.personal_history; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.personal_history IS '个人史';


--
-- Name: COLUMN admission_record.family_history; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.family_history IS '家族史';


--
-- Name: COLUMN admission_record.checkup; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.checkup IS '体格检查-全文';


--
-- Name: COLUMN admission_record.checkup_temperature; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.checkup_temperature IS '体温';


--
-- Name: COLUMN admission_record.checkup_heartrate; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.checkup_heartrate IS '脉率';


--
-- Name: COLUMN admission_record.checkup_respiratoryrate; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.checkup_respiratoryrate IS '呼吸频率';


--
-- Name: COLUMN admission_record.checkup_systolicpressure; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.checkup_systolicpressure IS '收缩压';


--
-- Name: COLUMN admission_record.checkup_diastolicpressure; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.checkup_diastolicpressure IS '舒张压';


--
-- Name: COLUMN admission_record.checkup_height; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.checkup_height IS '身高';


--
-- Name: COLUMN admission_record.checkup_weight; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.checkup_weight IS '体重';


--
-- Name: COLUMN admission_record.assist_exam; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.assist_exam IS '辅助检查';


--
-- Name: COLUMN admission_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.record_content IS '非结构化全文';


--
-- Name: COLUMN admission_record.resident_physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.resident_physician_sign IS '住院医师签名';


--
-- Name: COLUMN admission_record.attending_physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.attending_physician_sign IS '主治医师签名';


--
-- Name: COLUMN admission_record.chief_physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.chief_physician_sign IS '主副主任医师签名';


--
-- Name: COLUMN admission_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN admission_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN admission_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN admission_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN admission_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.document_id IS '文档编号';


--
-- Name: COLUMN admission_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.document_title IS '文档标题';


--
-- Name: COLUMN admission_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.document_status IS '文档状态';


--
-- Name: COLUMN admission_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.submitter IS '文档提交人';


--
-- Name: COLUMN admission_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN admission_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN admission_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.inpat_no IS '住院号';


--
-- Name: COLUMN admission_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.mr_no IS '病案号';


--
-- Name: COLUMN admission_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.name IS '患者姓名';


--
-- Name: COLUMN admission_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.sex IS '患者性别';


--
-- Name: COLUMN admission_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.age_year IS '年龄(年)';


--
-- Name: COLUMN admission_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.age_month IS '年龄(月)';


--
-- Name: COLUMN admission_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.admission_record.age IS '年龄-非结构化';


--
-- Name: ai_diagnosis_snapshot; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.ai_diagnosis_snapshot (
    id character varying(36) NOT NULL,
    snapshot_id character varying(36) NOT NULL,
    institute_id character varying(100),
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    seq_no integer DEFAULT 1 NOT NULL,
    diagnosis_type character varying(100),
    diagnosis_no character varying(100),
    diagnosis_name character varying(100),
    diagnosis_code character varying(100),
    admission_condition character varying(100),
    discharge_condition character varying(100),
    pathology_id character varying(100),
    is_main boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN ai_diagnosis_snapshot.id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.id IS 'UUID主键';


--
-- Name: COLUMN ai_diagnosis_snapshot.snapshot_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.snapshot_id IS 'AI首页主快照ID';


--
-- Name: COLUMN ai_diagnosis_snapshot.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.institute_id IS '机构号';


--
-- Name: COLUMN ai_diagnosis_snapshot.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.patient_id IS '患者号';


--
-- Name: COLUMN ai_diagnosis_snapshot.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.visit_id IS '就诊号';


--
-- Name: COLUMN ai_diagnosis_snapshot.seq_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.seq_no IS '序号';


--
-- Name: COLUMN ai_diagnosis_snapshot.diagnosis_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.diagnosis_type IS '诊断类别';


--
-- Name: COLUMN ai_diagnosis_snapshot.diagnosis_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.diagnosis_no IS '诊断序号';


--
-- Name: COLUMN ai_diagnosis_snapshot.diagnosis_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.diagnosis_name IS '诊断名称';


--
-- Name: COLUMN ai_diagnosis_snapshot.diagnosis_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.diagnosis_code IS '诊断编码';


--
-- Name: COLUMN ai_diagnosis_snapshot.admission_condition; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.admission_condition IS '入院病情';


--
-- Name: COLUMN ai_diagnosis_snapshot.discharge_condition; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.discharge_condition IS '出院情况';


--
-- Name: COLUMN ai_diagnosis_snapshot.pathology_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.pathology_id IS '病理号';


--
-- Name: COLUMN ai_diagnosis_snapshot.is_main; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.is_main IS '是否主诊断';


--
-- Name: COLUMN ai_diagnosis_snapshot.created_at; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.created_at IS '创建时间';


--
-- Name: COLUMN ai_diagnosis_snapshot.updated_at; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_diagnosis_snapshot.updated_at IS '更新时间';


--
-- Name: ai_frontpage_draft; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.ai_frontpage_draft (
    id integer NOT NULL,
    institute_id character varying(100),
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    draft_json text NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: ai_frontpage_draft_id_seq; Type: SEQUENCE; Schema: cdm; Owner: -
--

CREATE SEQUENCE cdm.ai_frontpage_draft_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_frontpage_draft_id_seq; Type: SEQUENCE OWNED BY; Schema: cdm; Owner: -
--

ALTER SEQUENCE cdm.ai_frontpage_draft_id_seq OWNED BY cdm.ai_frontpage_draft.id;


--
-- Name: ai_mr_cost_snapshot; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.ai_mr_cost_snapshot (
    id character varying(36) NOT NULL,
    snapshot_id character varying(36) NOT NULL,
    institute_id character varying(100),
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    total_cost character varying(100),
    self_pay character varying(100),
    general_medical_service_fee character varying(100),
    general_treatment_fee character varying(100),
    nursing_care_fee character varying(100),
    other_service_fee character varying(100),
    pathological_diagnostic_fee character varying(100),
    laboratory_diagnostic_fee character varying(100),
    imaging_diagnostic_fee character varying(100),
    clinical_diagnostic_fee character varying(100),
    nonsurgical_treatment_fee character varying(100),
    clinical_physical_therapy_fee character varying(100),
    surgery_treatment_fee character varying(100),
    anesthesia_fee character varying(100),
    surgery_fee character varying(100),
    rehabilitation_fee character varying(100),
    western_medicine_fee character varying(100),
    antibacterial_drug_fee character varying(100),
    chinese_patent_medcine_fee character varying(100),
    chinese_herbal_medicine_fee character varying(100),
    blood_fee character varying(100),
    treat_disposable_mat_fee character varying(100),
    exam_disposable_mat_fee character varying(100),
    surgery_disposable_mat_fee character varying(100),
    other_fee character varying(100),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN ai_mr_cost_snapshot.id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.id IS 'UUID主键';


--
-- Name: COLUMN ai_mr_cost_snapshot.snapshot_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.snapshot_id IS 'AI首页主快照ID';


--
-- Name: COLUMN ai_mr_cost_snapshot.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.institute_id IS '机构号';


--
-- Name: COLUMN ai_mr_cost_snapshot.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.patient_id IS '患者号';


--
-- Name: COLUMN ai_mr_cost_snapshot.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.visit_id IS '就诊号';


--
-- Name: COLUMN ai_mr_cost_snapshot.total_cost; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.total_cost IS '应收总费用';


--
-- Name: COLUMN ai_mr_cost_snapshot.self_pay; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.self_pay IS '自付金额';


--
-- Name: COLUMN ai_mr_cost_snapshot.general_medical_service_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.general_medical_service_fee IS '一般医疗服务费';


--
-- Name: COLUMN ai_mr_cost_snapshot.general_treatment_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.general_treatment_fee IS '一般治疗操作费';


--
-- Name: COLUMN ai_mr_cost_snapshot.nursing_care_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.nursing_care_fee IS '护理费';


--
-- Name: COLUMN ai_mr_cost_snapshot.other_service_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.other_service_fee IS '其它服务费用';


--
-- Name: COLUMN ai_mr_cost_snapshot.pathological_diagnostic_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.pathological_diagnostic_fee IS '病理诊断费用';


--
-- Name: COLUMN ai_mr_cost_snapshot.laboratory_diagnostic_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.laboratory_diagnostic_fee IS '实验室诊断费';


--
-- Name: COLUMN ai_mr_cost_snapshot.imaging_diagnostic_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.imaging_diagnostic_fee IS '影像学诊断费';


--
-- Name: COLUMN ai_mr_cost_snapshot.clinical_diagnostic_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.clinical_diagnostic_fee IS '临床诊断费';


--
-- Name: COLUMN ai_mr_cost_snapshot.nonsurgical_treatment_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.nonsurgical_treatment_fee IS '非手术治疗项目费';


--
-- Name: COLUMN ai_mr_cost_snapshot.clinical_physical_therapy_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.clinical_physical_therapy_fee IS '临床物理治疗费';


--
-- Name: COLUMN ai_mr_cost_snapshot.surgery_treatment_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.surgery_treatment_fee IS '手术治疗费';


--
-- Name: COLUMN ai_mr_cost_snapshot.anesthesia_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.anesthesia_fee IS '麻醉费';


--
-- Name: COLUMN ai_mr_cost_snapshot.surgery_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.surgery_fee IS '手术费';


--
-- Name: COLUMN ai_mr_cost_snapshot.rehabilitation_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.rehabilitation_fee IS '康复费';


--
-- Name: COLUMN ai_mr_cost_snapshot.western_medicine_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.western_medicine_fee IS '西药费';


--
-- Name: COLUMN ai_mr_cost_snapshot.antibacterial_drug_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.antibacterial_drug_fee IS '抗菌药物费用';


--
-- Name: COLUMN ai_mr_cost_snapshot.chinese_patent_medcine_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.chinese_patent_medcine_fee IS '中成药费';


--
-- Name: COLUMN ai_mr_cost_snapshot.chinese_herbal_medicine_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.chinese_herbal_medicine_fee IS '中草药费';


--
-- Name: COLUMN ai_mr_cost_snapshot.blood_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.blood_fee IS '血费';


--
-- Name: COLUMN ai_mr_cost_snapshot.treat_disposable_mat_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.treat_disposable_mat_fee IS '治疗一次性医用材料费';


--
-- Name: COLUMN ai_mr_cost_snapshot.exam_disposable_mat_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.exam_disposable_mat_fee IS '检查一次性医用材料费';


--
-- Name: COLUMN ai_mr_cost_snapshot.surgery_disposable_mat_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.surgery_disposable_mat_fee IS '手术一次性医用材料费';


--
-- Name: COLUMN ai_mr_cost_snapshot.other_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.other_fee IS '其它费用';


--
-- Name: COLUMN ai_mr_cost_snapshot.created_at; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.created_at IS '创建时间';


--
-- Name: COLUMN ai_mr_cost_snapshot.updated_at; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_cost_snapshot.updated_at IS '更新时间';


--
-- Name: ai_mr_snapshot; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.ai_mr_snapshot (
    id character varying(36) NOT NULL,
    institute_id character varying(100),
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    snapshot_version character varying(50) DEFAULT 'v1'::character varying NOT NULL,
    status character varying(20) DEFAULT 'generated'::character varying NOT NULL,
    draft_id integer,
    audit_id character varying(36),
    generated_by character varying(100),
    confirmed_by character varying(100),
    generated_at timestamp without time zone DEFAULT now() NOT NULL,
    confirmed_at timestamp without time zone,
    institute_code character varying(100),
    institute_county_desc character varying(100),
    medical_payment_method character varying(100),
    visit_cnt character varying(100),
    name character varying(100),
    sex character varying(100),
    age character varying(100),
    age_year character varying(100),
    id_card_no character varying(100),
    birthday date,
    nationality character varying(100),
    ethnicity character varying(100),
    marital_status character varying(100),
    occupation_category character varying(100),
    nativeplace text,
    currentaddress text,
    work_unit character varying(100),
    contact_name character varying(100),
    contact_relationship character varying(100),
    contact_address character varying(100),
    contact_telephone character varying(100),
    mr_no character varying(100),
    admission_route character varying(100),
    admission_datetime timestamp without time zone,
    admission_dept_name character varying(100),
    admission_ward_name character varying(100),
    transfer_dept_name character varying(100),
    discharge_datetime timestamp without time zone,
    discharge_dept_name character varying(100),
    discharge_ward_name character varying(100),
    hospital_duration character varying(100),
    leaving_hospital_way character varying(100),
    rehospital_with_month character varying(100),
    pathology_id character varying(100),
    allergy_sign character varying(100),
    allergy_history character varying(100),
    abo_blood_code character varying(100),
    rh_blood_code character varying(100),
    deptdirector_sign character varying(100),
    chief_physician_sign character varying(100),
    attending_physician_sign character varying(100),
    resident_physician_sign character varying(100),
    responsible_nurse_sign character varying(100),
    coder_sign character varying(100),
    medicalrecord_quality character varying(100),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN ai_mr_snapshot.id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.id IS 'UUID主键';


--
-- Name: COLUMN ai_mr_snapshot.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.institute_id IS '机构号';


--
-- Name: COLUMN ai_mr_snapshot.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.patient_id IS '患者号';


--
-- Name: COLUMN ai_mr_snapshot.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.visit_id IS '就诊号';


--
-- Name: COLUMN ai_mr_snapshot.snapshot_version; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.snapshot_version IS '快照版本';


--
-- Name: COLUMN ai_mr_snapshot.status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.status IS '状态：generated/confirmed/superseded';


--
-- Name: COLUMN ai_mr_snapshot.draft_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.draft_id IS 'AI首页草稿ID';


--
-- Name: COLUMN ai_mr_snapshot.audit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.audit_id IS '首页审计ID';


--
-- Name: COLUMN ai_mr_snapshot.generated_by; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.generated_by IS '生成人';


--
-- Name: COLUMN ai_mr_snapshot.confirmed_by; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.confirmed_by IS '确认人';


--
-- Name: COLUMN ai_mr_snapshot.generated_at; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.generated_at IS '生成时间';


--
-- Name: COLUMN ai_mr_snapshot.confirmed_at; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.confirmed_at IS '确认时间';


--
-- Name: COLUMN ai_mr_snapshot.institute_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.institute_code IS '医疗机构组织机构代码';


--
-- Name: COLUMN ai_mr_snapshot.institute_county_desc; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.institute_county_desc IS '医疗机构名称';


--
-- Name: COLUMN ai_mr_snapshot.medical_payment_method; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.medical_payment_method IS '医疗付费方式';


--
-- Name: COLUMN ai_mr_snapshot.visit_cnt; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.visit_cnt IS '就诊次数';


--
-- Name: COLUMN ai_mr_snapshot.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.name IS '患者姓名';


--
-- Name: COLUMN ai_mr_snapshot.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.sex IS '患者性别';


--
-- Name: COLUMN ai_mr_snapshot.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.age IS '年龄';


--
-- Name: COLUMN ai_mr_snapshot.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.age_year IS '年龄(年)';


--
-- Name: COLUMN ai_mr_snapshot.id_card_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.id_card_no IS '身份证件号码';


--
-- Name: COLUMN ai_mr_snapshot.birthday; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.birthday IS '出生日期';


--
-- Name: COLUMN ai_mr_snapshot.nationality; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.nationality IS '国籍';


--
-- Name: COLUMN ai_mr_snapshot.ethnicity; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.ethnicity IS '民族';


--
-- Name: COLUMN ai_mr_snapshot.marital_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.marital_status IS '婚姻状况';


--
-- Name: COLUMN ai_mr_snapshot.occupation_category; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.occupation_category IS '职业类别';


--
-- Name: COLUMN ai_mr_snapshot.nativeplace; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.nativeplace IS '籍贯地址';


--
-- Name: COLUMN ai_mr_snapshot.currentaddress; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.currentaddress IS '现住址';


--
-- Name: COLUMN ai_mr_snapshot.work_unit; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.work_unit IS '工作单位';


--
-- Name: COLUMN ai_mr_snapshot.contact_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.contact_name IS '联系人姓名';


--
-- Name: COLUMN ai_mr_snapshot.contact_relationship; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.contact_relationship IS '联系人关系';


--
-- Name: COLUMN ai_mr_snapshot.contact_address; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.contact_address IS '联系人地址';


--
-- Name: COLUMN ai_mr_snapshot.contact_telephone; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.contact_telephone IS '联系人电话';


--
-- Name: COLUMN ai_mr_snapshot.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.mr_no IS '病案号';


--
-- Name: COLUMN ai_mr_snapshot.admission_route; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.admission_route IS '入院途径';


--
-- Name: COLUMN ai_mr_snapshot.admission_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.admission_datetime IS '入院时间';


--
-- Name: COLUMN ai_mr_snapshot.admission_dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.admission_dept_name IS '入院科室';


--
-- Name: COLUMN ai_mr_snapshot.admission_ward_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.admission_ward_name IS '入院病房';


--
-- Name: COLUMN ai_mr_snapshot.transfer_dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.transfer_dept_name IS '转科科室';


--
-- Name: COLUMN ai_mr_snapshot.discharge_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.discharge_datetime IS '出院时间';


--
-- Name: COLUMN ai_mr_snapshot.discharge_dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.discharge_dept_name IS '出院科室';


--
-- Name: COLUMN ai_mr_snapshot.discharge_ward_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.discharge_ward_name IS '出院病房';


--
-- Name: COLUMN ai_mr_snapshot.hospital_duration; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.hospital_duration IS '实际住院天数';


--
-- Name: COLUMN ai_mr_snapshot.leaving_hospital_way; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.leaving_hospital_way IS '离院方式';


--
-- Name: COLUMN ai_mr_snapshot.rehospital_with_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.rehospital_with_month IS '出院31天内再住院标志';


--
-- Name: COLUMN ai_mr_snapshot.pathology_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.pathology_id IS '病理号';


--
-- Name: COLUMN ai_mr_snapshot.allergy_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.allergy_sign IS '过敏史标志';


--
-- Name: COLUMN ai_mr_snapshot.allergy_history; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.allergy_history IS '过敏史';


--
-- Name: COLUMN ai_mr_snapshot.abo_blood_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.abo_blood_code IS 'ABO血型';


--
-- Name: COLUMN ai_mr_snapshot.rh_blood_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.rh_blood_code IS 'Rh血型';


--
-- Name: COLUMN ai_mr_snapshot.deptdirector_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.deptdirector_sign IS '科主任签名';


--
-- Name: COLUMN ai_mr_snapshot.chief_physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.chief_physician_sign IS '主副主任医师签名';


--
-- Name: COLUMN ai_mr_snapshot.attending_physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.attending_physician_sign IS '主治医师签名';


--
-- Name: COLUMN ai_mr_snapshot.resident_physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.resident_physician_sign IS '住院医师签名';


--
-- Name: COLUMN ai_mr_snapshot.responsible_nurse_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.responsible_nurse_sign IS '责任护士签名';


--
-- Name: COLUMN ai_mr_snapshot.coder_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.coder_sign IS '编码员签名';


--
-- Name: COLUMN ai_mr_snapshot.medicalrecord_quality; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.medicalrecord_quality IS '病案质量';


--
-- Name: COLUMN ai_mr_snapshot.created_at; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.created_at IS '创建时间';


--
-- Name: COLUMN ai_mr_snapshot.updated_at; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_snapshot.updated_at IS '更新时间';


--
-- Name: ai_mr_surgery_snapshot; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.ai_mr_surgery_snapshot (
    id character varying(36) NOT NULL,
    snapshot_id character varying(36) NOT NULL,
    institute_id character varying(100),
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    seq_no integer DEFAULT 1 NOT NULL,
    surgery_name character varying(100),
    surgery_code character varying(100),
    surgical_level character varying(100),
    surgery_begin_datetime timestamp without time zone,
    surgeon character varying(100),
    first_assistant character varying(100),
    second_assistant character varying(100),
    anesthesia_method character varying(100),
    anesthesiologist character varying(100),
    surgial_incision_level character varying(100),
    surgical_incisionheal_level character varying(100),
    is_main boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN ai_mr_surgery_snapshot.id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.id IS 'UUID主键';


--
-- Name: COLUMN ai_mr_surgery_snapshot.snapshot_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.snapshot_id IS 'AI首页主快照ID';


--
-- Name: COLUMN ai_mr_surgery_snapshot.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.institute_id IS '机构号';


--
-- Name: COLUMN ai_mr_surgery_snapshot.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.patient_id IS '患者号';


--
-- Name: COLUMN ai_mr_surgery_snapshot.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.visit_id IS '就诊号';


--
-- Name: COLUMN ai_mr_surgery_snapshot.seq_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.seq_no IS '序号';


--
-- Name: COLUMN ai_mr_surgery_snapshot.surgery_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.surgery_name IS '手术操作名称';


--
-- Name: COLUMN ai_mr_surgery_snapshot.surgery_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.surgery_code IS '手术操作编码';


--
-- Name: COLUMN ai_mr_surgery_snapshot.surgical_level; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.surgical_level IS '手术级别';


--
-- Name: COLUMN ai_mr_surgery_snapshot.surgery_begin_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.surgery_begin_datetime IS '手术开始时间';


--
-- Name: COLUMN ai_mr_surgery_snapshot.surgeon; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.surgeon IS '术者';


--
-- Name: COLUMN ai_mr_surgery_snapshot.first_assistant; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.first_assistant IS '一助';


--
-- Name: COLUMN ai_mr_surgery_snapshot.second_assistant; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.second_assistant IS '二助';


--
-- Name: COLUMN ai_mr_surgery_snapshot.anesthesia_method; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.anesthesia_method IS '麻醉方式';


--
-- Name: COLUMN ai_mr_surgery_snapshot.anesthesiologist; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.anesthesiologist IS '麻醉医师';


--
-- Name: COLUMN ai_mr_surgery_snapshot.surgial_incision_level; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.surgial_incision_level IS '手术切口分级';


--
-- Name: COLUMN ai_mr_surgery_snapshot.surgical_incisionheal_level; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.surgical_incisionheal_level IS '手术切口愈合分级';


--
-- Name: COLUMN ai_mr_surgery_snapshot.is_main; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.is_main IS '是否主手术';


--
-- Name: COLUMN ai_mr_surgery_snapshot.created_at; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.created_at IS '创建时间';


--
-- Name: COLUMN ai_mr_surgery_snapshot.updated_at; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.ai_mr_surgery_snapshot.updated_at IS '更新时间';


--
-- Name: anesthesia_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.anesthesia_record (
    surgery_begin_datetime timestamp without time zone,
    surgery_end_datetime timestamp without time zone,
    anesthesia_begin_datetime timestamp without time zone,
    anesthesia_end_datetime timestamp without time zone,
    leave_operateroom_datetime timestamp without time zone,
    anesthetist_sign text,
    anesthetist_sign_datetime timestamp with time zone,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN anesthesia_record.surgery_begin_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.surgery_begin_datetime IS 'Caché源字段 surgery_begin_datetime，独立保留原始语义';


--
-- Name: COLUMN anesthesia_record.surgery_end_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.surgery_end_datetime IS 'Caché源字段 surgery_end_datetime，独立保留原始语义';


--
-- Name: COLUMN anesthesia_record.anesthesia_begin_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.anesthesia_begin_datetime IS 'Caché源字段 anesthesia_begin_datetime，独立保留原始语义';


--
-- Name: COLUMN anesthesia_record.anesthesia_end_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.anesthesia_end_datetime IS 'Caché源字段 anesthesia_end_datetime，独立保留原始语义';


--
-- Name: COLUMN anesthesia_record.leave_operateroom_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.leave_operateroom_datetime IS 'Caché源字段 leave_operateroom_datetime，独立保留原始语义';


--
-- Name: COLUMN anesthesia_record.anesthetist_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.anesthetist_sign IS '源麻醉签署原值，不从提交人推断';


--
-- Name: COLUMN anesthesia_record.anesthetist_sign_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.anesthetist_sign_datetime IS 'Caché源字段 anesthetist_sign_datetime，独立保留原始语义';


--
-- Name: COLUMN anesthesia_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.institute_id IS '机构号';


--
-- Name: COLUMN anesthesia_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.patient_id IS '患者号';


--
-- Name: COLUMN anesthesia_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.visit_id IS '就诊号';


--
-- Name: COLUMN anesthesia_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.document_id IS '文档编号';


--
-- Name: COLUMN anesthesia_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.visit_type IS '就诊类型';


--
-- Name: COLUMN anesthesia_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.record_content IS '非结构化全文';


--
-- Name: COLUMN anesthesia_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN anesthesia_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN anesthesia_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN anesthesia_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN anesthesia_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.document_title IS '文档标题';


--
-- Name: COLUMN anesthesia_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.document_status IS '文档状态';


--
-- Name: COLUMN anesthesia_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.submitter IS '文档提交人';


--
-- Name: COLUMN anesthesia_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN anesthesia_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN anesthesia_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.inpat_no IS '住院号';


--
-- Name: COLUMN anesthesia_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.mr_no IS '病案号';


--
-- Name: COLUMN anesthesia_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.name IS '患者姓名';


--
-- Name: COLUMN anesthesia_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.sex IS '患者性别';


--
-- Name: COLUMN anesthesia_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.age_year IS '年龄(年)';


--
-- Name: COLUMN anesthesia_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.age_month IS '年龄(月)';


--
-- Name: COLUMN anesthesia_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.anesthesia_record.age IS '年龄-非结构化';


--
-- Name: blood_application; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.blood_application (
    transfution_datetime timestamp without time zone,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    application_id character varying(100) NOT NULL,
    inpat_no character varying(100),
    dept_name character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    patient_bloodtype_abo character varying(100),
    patient_bloodtype_rhd character varying(100),
    transfuse_variety character varying(100),
    transfuse_volume character varying(100),
    transfuse_volume_unit character varying(100),
    request_datetime timestamp without time zone,
    physician_name character varying(100),
    reason_for_blood text,
    hemoglobin character varying(100),
    hematocrit character varying(100),
    rbc character varying(100),
    prothrombin_time character varying(100),
    partial_thromboplastin_time character varying(100),
    fibrinogen character varying(100),
    albumin character varying(100),
    teg character varying(100),
    platelet_antibody character varying(100),
    rbc_antibody character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN blood_application.transfution_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.transfution_datetime IS '源输血申请接口字段，语义待确认；不能作为实际输血执行证据';


--
-- Name: COLUMN blood_application.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.institute_id IS '机构号';


--
-- Name: COLUMN blood_application.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.patient_id IS '患者号';


--
-- Name: COLUMN blood_application.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.visit_id IS '就诊号';


--
-- Name: COLUMN blood_application.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.visit_type IS '就诊类型';


--
-- Name: COLUMN blood_application.application_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.application_id IS '申请号';


--
-- Name: COLUMN blood_application.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.inpat_no IS '住院号';


--
-- Name: COLUMN blood_application.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.dept_name IS '科室名称';


--
-- Name: COLUMN blood_application.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.name IS '患者姓名';


--
-- Name: COLUMN blood_application.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.sex IS '患者性别';


--
-- Name: COLUMN blood_application.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.age_year IS '年龄(年)';


--
-- Name: COLUMN blood_application.patient_bloodtype_abo; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.patient_bloodtype_abo IS '患者ABO血型';


--
-- Name: COLUMN blood_application.patient_bloodtype_rhd; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.patient_bloodtype_rhd IS '患者RH血型';


--
-- Name: COLUMN blood_application.transfuse_variety; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.transfuse_variety IS '输血品种';


--
-- Name: COLUMN blood_application.transfuse_volume; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.transfuse_volume IS '输血剂量';


--
-- Name: COLUMN blood_application.transfuse_volume_unit; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.transfuse_volume_unit IS '输血剂量单位';


--
-- Name: COLUMN blood_application.request_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.request_datetime IS '申请时间';


--
-- Name: COLUMN blood_application.physician_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.physician_name IS '申请医师';


--
-- Name: COLUMN blood_application.reason_for_blood; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.reason_for_blood IS '输血申请理由';


--
-- Name: COLUMN blood_application.hemoglobin; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.hemoglobin IS '血红蛋白';


--
-- Name: COLUMN blood_application.hematocrit; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.hematocrit IS '红细胞压积';


--
-- Name: COLUMN blood_application.rbc; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.rbc IS '红细胞计数';


--
-- Name: COLUMN blood_application.prothrombin_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.prothrombin_time IS '凝血酶原时间';


--
-- Name: COLUMN blood_application.partial_thromboplastin_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.partial_thromboplastin_time IS '部分凝血活酶时间';


--
-- Name: COLUMN blood_application.fibrinogen; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.fibrinogen IS '纤维蛋白原';


--
-- Name: COLUMN blood_application.albumin; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.albumin IS '白蛋白';


--
-- Name: COLUMN blood_application.teg; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.teg IS '血栓弹力图';


--
-- Name: COLUMN blood_application.platelet_antibody; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.platelet_antibody IS '血小板抗体';


--
-- Name: COLUMN blood_application.rbc_antibody; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.rbc_antibody IS '红细胞抗体';


--
-- Name: COLUMN blood_application.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.record_content IS '记录内容';


--
-- Name: COLUMN blood_application.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.last_modifier IS '最新修改人';


--
-- Name: COLUMN blood_application.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN blood_application.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN blood_application.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.blood_application.update_time IS '数据更新时间，用于增量同步';


--
-- Name: bloodtrans_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.bloodtrans_record (
    record_datetime timestamp without time zone,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN bloodtrans_record.record_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.record_datetime IS 'Caché源字段 record_datetime，独立保留原始语义';


--
-- Name: COLUMN bloodtrans_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.institute_id IS '机构号';


--
-- Name: COLUMN bloodtrans_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.patient_id IS '患者号';


--
-- Name: COLUMN bloodtrans_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.visit_id IS '就诊号';


--
-- Name: COLUMN bloodtrans_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.document_id IS '文档编号';


--
-- Name: COLUMN bloodtrans_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.visit_type IS '就诊类型';


--
-- Name: COLUMN bloodtrans_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.record_content IS '非结构化全文';


--
-- Name: COLUMN bloodtrans_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN bloodtrans_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN bloodtrans_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN bloodtrans_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN bloodtrans_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.document_title IS '文档标题';


--
-- Name: COLUMN bloodtrans_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.document_status IS '文档状态';


--
-- Name: COLUMN bloodtrans_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.submitter IS '文档提交人';


--
-- Name: COLUMN bloodtrans_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN bloodtrans_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN bloodtrans_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.inpat_no IS '住院号';


--
-- Name: COLUMN bloodtrans_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.mr_no IS '病案号';


--
-- Name: COLUMN bloodtrans_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.name IS '患者姓名';


--
-- Name: COLUMN bloodtrans_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.sex IS '患者性别';


--
-- Name: COLUMN bloodtrans_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.age_year IS '年龄(年)';


--
-- Name: COLUMN bloodtrans_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.age_month IS '年龄(月)';


--
-- Name: COLUMN bloodtrans_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.bloodtrans_record.age IS '年龄-非结构化';


--
-- Name: consent_form; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.consent_form (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    consent_type character varying(100),
    dept_name character varying(100),
    record_content text,
    patient_sign character varying(100),
    physician_sign character varying(100),
    patient_sign_datetime timestamp without time zone,
    physician_sign_datetime timestamp without time zone,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100),
    record_time timestamp without time zone,
    diagnosis text,
    transfusion_reason text,
    blood_component character varying(100),
    risk_description text,
    alternative_plan text,
    agent_sign character varying(100),
    surgeon_sign character varying(100),
    planned_operation_name text,
    planned_operation_code character varying(100)
);


--
-- Name: consultation_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.consultation_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    request_time character varying(100),
    consultation_time timestamp with time zone,
    record_time timestamp with time zone,
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100),
    application_id character varying(100)
);


--
-- Name: COLUMN consultation_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.institute_id IS '机构号';


--
-- Name: COLUMN consultation_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.patient_id IS '患者号';


--
-- Name: COLUMN consultation_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.visit_id IS '就诊号';


--
-- Name: COLUMN consultation_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.document_id IS '文档编号';


--
-- Name: COLUMN consultation_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.visit_type IS '就诊类型';


--
-- Name: COLUMN consultation_record.request_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.request_time IS '会诊申请时间（源值）';


--
-- Name: COLUMN consultation_record.consultation_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.consultation_time IS '会诊完成时间';


--
-- Name: COLUMN consultation_record.record_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.record_time IS '会诊记录时间';


--
-- Name: COLUMN consultation_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.record_content IS '非结构化全文';


--
-- Name: COLUMN consultation_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN consultation_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN consultation_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN consultation_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN consultation_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.document_title IS '文档标题';


--
-- Name: COLUMN consultation_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.document_status IS '文档状态';


--
-- Name: COLUMN consultation_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.submitter IS '文档提交人';


--
-- Name: COLUMN consultation_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN consultation_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN consultation_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.inpat_no IS '住院号';


--
-- Name: COLUMN consultation_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.mr_no IS '病案号';


--
-- Name: COLUMN consultation_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.name IS '患者姓名';


--
-- Name: COLUMN consultation_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.sex IS '患者性别';


--
-- Name: COLUMN consultation_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.age_year IS '年龄(年)';


--
-- Name: COLUMN consultation_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.age_month IS '年龄(月)';


--
-- Name: COLUMN consultation_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.consultation_record.age IS '年龄-非结构化';


--
-- Name: crisis_value_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.crisis_value_record (
    physician_sign text,
    physician_sign_datetime timestamp without time zone,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    dept_name character varying(100),
    record_content text,
    record_datetime timestamp without time zone,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN crisis_value_record.physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.physician_sign IS 'Caché源字段 physician_sign，原值语义保留';


--
-- Name: COLUMN crisis_value_record.physician_sign_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.physician_sign_datetime IS 'Caché源字段 physician_sign_datetime，原值语义保留';


--
-- Name: COLUMN crisis_value_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.institute_id IS '机构号';


--
-- Name: COLUMN crisis_value_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.patient_id IS '患者号';


--
-- Name: COLUMN crisis_value_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.visit_id IS '就诊号';


--
-- Name: COLUMN crisis_value_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.document_id IS '文档编号';


--
-- Name: COLUMN crisis_value_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.visit_type IS '就诊类型';


--
-- Name: COLUMN crisis_value_record.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.dept_name IS '科室名称';


--
-- Name: COLUMN crisis_value_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.record_content IS '记录内容';


--
-- Name: COLUMN crisis_value_record.record_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.record_datetime IS '记录时间';


--
-- Name: COLUMN crisis_value_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN crisis_value_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN crisis_value_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN crisis_value_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN crisis_value_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.document_title IS '文档标题';


--
-- Name: COLUMN crisis_value_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.document_status IS '文档状态';


--
-- Name: COLUMN crisis_value_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.submitter IS '文档提交人';


--
-- Name: COLUMN crisis_value_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN crisis_value_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN crisis_value_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.inpat_no IS '住院号';


--
-- Name: COLUMN crisis_value_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.mr_no IS '病案号';


--
-- Name: COLUMN crisis_value_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.name IS '患者姓名';


--
-- Name: COLUMN crisis_value_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.sex IS '患者性别';


--
-- Name: COLUMN crisis_value_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.age_year IS '年龄(年)';


--
-- Name: COLUMN crisis_value_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.age_month IS '年龄(月)';


--
-- Name: COLUMN crisis_value_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.crisis_value_record.age IS '年龄-非结构化';


--
-- Name: daily_admission_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.daily_admission_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    dept_name character varying(100),
    admission_datetime timestamp without time zone,
    discharge_datetime timestamp without time zone,
    chief_complaint text,
    admission_condition text,
    treatment_course text,
    discharge_condition text,
    discharge_order text,
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN daily_admission_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.institute_id IS '机构号';


--
-- Name: COLUMN daily_admission_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.patient_id IS '患者号';


--
-- Name: COLUMN daily_admission_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.visit_id IS '就诊号';


--
-- Name: COLUMN daily_admission_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.document_id IS '文档编号';


--
-- Name: COLUMN daily_admission_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.visit_type IS '就诊类型';


--
-- Name: COLUMN daily_admission_record.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.dept_name IS '科室名称';


--
-- Name: COLUMN daily_admission_record.admission_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.admission_datetime IS '入院时间';


--
-- Name: COLUMN daily_admission_record.discharge_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.discharge_datetime IS '出院时间';


--
-- Name: COLUMN daily_admission_record.chief_complaint; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.chief_complaint IS '主诉';


--
-- Name: COLUMN daily_admission_record.admission_condition; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.admission_condition IS '入院情况';


--
-- Name: COLUMN daily_admission_record.treatment_course; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.treatment_course IS '诊疗经过';


--
-- Name: COLUMN daily_admission_record.discharge_condition; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.discharge_condition IS '出院情况';


--
-- Name: COLUMN daily_admission_record.discharge_order; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.discharge_order IS '出院医嘱';


--
-- Name: COLUMN daily_admission_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.record_content IS '记录内容';


--
-- Name: COLUMN daily_admission_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN daily_admission_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN daily_admission_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN daily_admission_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN daily_admission_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.document_title IS '文档标题';


--
-- Name: COLUMN daily_admission_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.document_status IS '文档状态';


--
-- Name: COLUMN daily_admission_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.submitter IS '文档提交人';


--
-- Name: COLUMN daily_admission_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN daily_admission_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN daily_admission_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.inpat_no IS '住院号';


--
-- Name: COLUMN daily_admission_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.mr_no IS '病案号';


--
-- Name: COLUMN daily_admission_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.name IS '患者姓名';


--
-- Name: COLUMN daily_admission_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.sex IS '患者性别';


--
-- Name: COLUMN daily_admission_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.age_year IS '年龄(年)';


--
-- Name: COLUMN daily_admission_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.age_month IS '年龄(月)';


--
-- Name: COLUMN daily_admission_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_admission_record.age IS '年龄-非结构化';


--
-- Name: daily_course_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.daily_course_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    record_datetime timestamp without time zone,
    physician_sign text,
    physician_sign_datetime timestamp with time zone,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN daily_course_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.institute_id IS '机构号';


--
-- Name: COLUMN daily_course_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.patient_id IS '患者号';


--
-- Name: COLUMN daily_course_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.visit_id IS '就诊号';


--
-- Name: COLUMN daily_course_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.document_id IS '文档编号';


--
-- Name: COLUMN daily_course_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.visit_type IS '就诊类型';


--
-- Name: COLUMN daily_course_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.record_content IS '非结构化全文';


--
-- Name: COLUMN daily_course_record.record_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.record_datetime IS '源文书记录时间，独立于提交、签署及修改时间';


--
-- Name: COLUMN daily_course_record.physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.physician_sign IS '医师签名（源值）';


--
-- Name: COLUMN daily_course_record.physician_sign_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.physician_sign_datetime IS '医师签名时间';


--
-- Name: COLUMN daily_course_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN daily_course_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN daily_course_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN daily_course_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN daily_course_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.document_title IS '文档标题';


--
-- Name: COLUMN daily_course_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.document_status IS '文档状态';


--
-- Name: COLUMN daily_course_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.submitter IS '文档提交人';


--
-- Name: COLUMN daily_course_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN daily_course_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN daily_course_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.inpat_no IS '住院号';


--
-- Name: COLUMN daily_course_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.mr_no IS '病案号';


--
-- Name: COLUMN daily_course_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.name IS '患者姓名';


--
-- Name: COLUMN daily_course_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.sex IS '患者性别';


--
-- Name: COLUMN daily_course_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.age_year IS '年龄(年)';


--
-- Name: COLUMN daily_course_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.age_month IS '年龄(月)';


--
-- Name: COLUMN daily_course_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_course_record.age IS '年龄-非结构化';


--
-- Name: daily_death_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.daily_death_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    dept_name character varying(100),
    admission_condition text,
    treatment_course text,
    death_reason character varying(100),
    death_datetime timestamp without time zone,
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN daily_death_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.institute_id IS '机构号';


--
-- Name: COLUMN daily_death_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.patient_id IS '患者号';


--
-- Name: COLUMN daily_death_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.visit_id IS '就诊号';


--
-- Name: COLUMN daily_death_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.document_id IS '文档编号';


--
-- Name: COLUMN daily_death_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.visit_type IS '就诊类型';


--
-- Name: COLUMN daily_death_record.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.dept_name IS '科室名称';


--
-- Name: COLUMN daily_death_record.admission_condition; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.admission_condition IS '入院情况';


--
-- Name: COLUMN daily_death_record.treatment_course; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.treatment_course IS '诊疗经过';


--
-- Name: COLUMN daily_death_record.death_reason; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.death_reason IS '死亡原因';


--
-- Name: COLUMN daily_death_record.death_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.death_datetime IS '死亡时间';


--
-- Name: COLUMN daily_death_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.record_content IS '记录内容';


--
-- Name: COLUMN daily_death_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN daily_death_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN daily_death_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN daily_death_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN daily_death_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.document_title IS '文档标题';


--
-- Name: COLUMN daily_death_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.document_status IS '文档状态';


--
-- Name: COLUMN daily_death_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.submitter IS '文档提交人';


--
-- Name: COLUMN daily_death_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN daily_death_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN daily_death_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.inpat_no IS '住院号';


--
-- Name: COLUMN daily_death_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.mr_no IS '病案号';


--
-- Name: COLUMN daily_death_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.name IS '患者姓名';


--
-- Name: COLUMN daily_death_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.sex IS '患者性别';


--
-- Name: COLUMN daily_death_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.age_year IS '年龄(年)';


--
-- Name: COLUMN daily_death_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.age_month IS '年龄(月)';


--
-- Name: COLUMN daily_death_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.daily_death_record.age IS '年龄-非结构化';


--
-- Name: death_discussion; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.death_discussion (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN death_discussion.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.institute_id IS '机构号';


--
-- Name: COLUMN death_discussion.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.patient_id IS '患者号';


--
-- Name: COLUMN death_discussion.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.visit_id IS '就诊号';


--
-- Name: COLUMN death_discussion.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.document_id IS '文档编号';


--
-- Name: COLUMN death_discussion.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.visit_type IS '就诊类型';


--
-- Name: COLUMN death_discussion.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.record_content IS '非结构化全文';


--
-- Name: COLUMN death_discussion.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.last_modifier IS '最新修改人';


--
-- Name: COLUMN death_discussion.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN death_discussion.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN death_discussion.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN death_discussion.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.document_title IS '文档标题';


--
-- Name: COLUMN death_discussion.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.document_status IS '文档状态';


--
-- Name: COLUMN death_discussion.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.submitter IS '文档提交人';


--
-- Name: COLUMN death_discussion.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN death_discussion.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN death_discussion.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.inpat_no IS '住院号';


--
-- Name: COLUMN death_discussion.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.mr_no IS '病案号';


--
-- Name: COLUMN death_discussion.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.name IS '患者姓名';


--
-- Name: COLUMN death_discussion.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.sex IS '患者性别';


--
-- Name: COLUMN death_discussion.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.age_year IS '年龄(年)';


--
-- Name: COLUMN death_discussion.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.age_month IS '年龄(月)';


--
-- Name: COLUMN death_discussion.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_discussion.age IS '年龄-非结构化';


--
-- Name: death_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.death_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    death_datetime timestamp with time zone,
    admission_condition text,
    treatment_course text,
    death_reason text,
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN death_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.institute_id IS '机构号';


--
-- Name: COLUMN death_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.patient_id IS '患者号';


--
-- Name: COLUMN death_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.visit_id IS '就诊号';


--
-- Name: COLUMN death_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.document_id IS '文档编号';


--
-- Name: COLUMN death_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.visit_type IS '就诊类型';


--
-- Name: COLUMN death_record.death_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.death_datetime IS '死亡时间，独立于文书记录及提交时间';


--
-- Name: COLUMN death_record.admission_condition; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.admission_condition IS '入院情况';


--
-- Name: COLUMN death_record.treatment_course; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.treatment_course IS '诊疗经过';


--
-- Name: COLUMN death_record.death_reason; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.death_reason IS '死亡原因';


--
-- Name: COLUMN death_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.record_content IS '非结构化全文';


--
-- Name: COLUMN death_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN death_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN death_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN death_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN death_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.document_title IS '文档标题';


--
-- Name: COLUMN death_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.document_status IS '文档状态';


--
-- Name: COLUMN death_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.submitter IS '文档提交人';


--
-- Name: COLUMN death_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN death_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN death_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.inpat_no IS '住院号';


--
-- Name: COLUMN death_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.mr_no IS '病案号';


--
-- Name: COLUMN death_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.name IS '患者姓名';


--
-- Name: COLUMN death_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.sex IS '患者性别';


--
-- Name: COLUMN death_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.age_year IS '年龄(年)';


--
-- Name: COLUMN death_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.age_month IS '年龄(月)';


--
-- Name: COLUMN death_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.death_record.age IS '年龄-非结构化';


--
-- Name: diagnosis; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.diagnosis (
    main_diag_flag text,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    document_id character varying(100),
    diagnosis_id character varying(100) NOT NULL,
    inpat_no character varying(100),
    dept_name character varying(100),
    name character varying(100),
    sex character varying(100),
    diagnosis_type character varying(100),
    diagnosis_no character varying(100),
    diagnosis_name text,
    diagnosis_code character varying(100),
    pathology_id character varying(100),
    admission_condition character varying(100),
    discharge_condition character varying(100),
    diagnosis_source character varying(100),
    diagnosis_datetime timestamp without time zone,
    diagnosis_updatetime timestamp without time zone,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN diagnosis.main_diag_flag; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.main_diag_flag IS 'Caché源 MainDiag_Flag 厂商代码原值，不解释真假';


--
-- Name: COLUMN diagnosis.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.institute_id IS '机构号';


--
-- Name: COLUMN diagnosis.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.patient_id IS '患者号';


--
-- Name: COLUMN diagnosis.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.visit_id IS '就诊号';


--
-- Name: COLUMN diagnosis.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.visit_type IS '就诊类型';


--
-- Name: COLUMN diagnosis.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.document_id IS '文档编号';


--
-- Name: COLUMN diagnosis.diagnosis_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.diagnosis_id IS '诊断号-唯一标识';


--
-- Name: COLUMN diagnosis.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.inpat_no IS '住院号';


--
-- Name: COLUMN diagnosis.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.dept_name IS '科室名称';


--
-- Name: COLUMN diagnosis.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.name IS '患者姓名';


--
-- Name: COLUMN diagnosis.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.sex IS '患者性别';


--
-- Name: COLUMN diagnosis.diagnosis_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.diagnosis_type IS '诊断类别(入院/出院主要/出院其他)';


--
-- Name: COLUMN diagnosis.diagnosis_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.diagnosis_no IS '诊断序号';


--
-- Name: COLUMN diagnosis.diagnosis_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.diagnosis_name IS '诊断名称';


--
-- Name: COLUMN diagnosis.diagnosis_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.diagnosis_code IS '诊断代码(ICD-10)';


--
-- Name: COLUMN diagnosis.pathology_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.pathology_id IS '病理号';


--
-- Name: COLUMN diagnosis.admission_condition; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.admission_condition IS '入院病情(1有/2临床未确定/3情况不明/4无)';


--
-- Name: COLUMN diagnosis.discharge_condition; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.discharge_condition IS '出院情况(治愈/好转/未愈/死亡等)';


--
-- Name: COLUMN diagnosis.diagnosis_source; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.diagnosis_source IS '诊断单据来源';


--
-- Name: COLUMN diagnosis.diagnosis_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.diagnosis_datetime IS '诊断创建时间';


--
-- Name: COLUMN diagnosis.diagnosis_updatetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.diagnosis_updatetime IS '诊断修改时间';


--
-- Name: COLUMN diagnosis.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.last_modifier IS '最新修改人';


--
-- Name: COLUMN diagnosis.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN diagnosis.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN diagnosis.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diagnosis.update_time IS '数据更新时间，用于增量同步';


--
-- Name: diffcase_discussion_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.diffcase_discussion_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN diffcase_discussion_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.institute_id IS '机构号';


--
-- Name: COLUMN diffcase_discussion_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.patient_id IS '患者号';


--
-- Name: COLUMN diffcase_discussion_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.visit_id IS '就诊号';


--
-- Name: COLUMN diffcase_discussion_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.document_id IS '文档编号';


--
-- Name: COLUMN diffcase_discussion_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.visit_type IS '就诊类型';


--
-- Name: COLUMN diffcase_discussion_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.record_content IS '非结构化全文';


--
-- Name: COLUMN diffcase_discussion_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN diffcase_discussion_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN diffcase_discussion_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN diffcase_discussion_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN diffcase_discussion_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.document_title IS '文档标题';


--
-- Name: COLUMN diffcase_discussion_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.document_status IS '文档状态';


--
-- Name: COLUMN diffcase_discussion_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.submitter IS '文档提交人';


--
-- Name: COLUMN diffcase_discussion_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN diffcase_discussion_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN diffcase_discussion_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.inpat_no IS '住院号';


--
-- Name: COLUMN diffcase_discussion_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.mr_no IS '病案号';


--
-- Name: COLUMN diffcase_discussion_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.name IS '患者姓名';


--
-- Name: COLUMN diffcase_discussion_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.sex IS '患者性别';


--
-- Name: COLUMN diffcase_discussion_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.age_year IS '年龄(年)';


--
-- Name: COLUMN diffcase_discussion_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.age_month IS '年龄(月)';


--
-- Name: COLUMN diffcase_discussion_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.diffcase_discussion_record.age IS '年龄-非结构化';


--
-- Name: discharge_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.discharge_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    dept_name character varying(100),
    ward_name character varying(100),
    admission_date date,
    discharge_date date,
    discharge_time timestamp without time zone,
    inpatient_duration character varying(100),
    admission_condition text,
    positive_assist_exam text,
    treatment_course text,
    discharge_condition text,
    discharge_order text,
    condition_transform character varying(100),
    record_content text,
    resident_physician_sign character varying(100),
    attending_physician_sign character varying(100),
    chief_physician_sign character varying(100),
    chief_physician_sign_datetime timestamp with time zone,
    v2_schema text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_id character varying(100),
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN discharge_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.institute_id IS '机构号';


--
-- Name: COLUMN discharge_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.patient_id IS '患者号';


--
-- Name: COLUMN discharge_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.visit_id IS '就诊号';


--
-- Name: COLUMN discharge_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.visit_type IS '就诊类型';


--
-- Name: COLUMN discharge_record.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.dept_name IS '科室名称';


--
-- Name: COLUMN discharge_record.ward_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.ward_name IS '病区名称';


--
-- Name: COLUMN discharge_record.admission_date; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.admission_date IS '入院日期';


--
-- Name: COLUMN discharge_record.discharge_date; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.discharge_date IS '出院日期';


--
-- Name: COLUMN discharge_record.discharge_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.discharge_time IS '出院时间';


--
-- Name: COLUMN discharge_record.inpatient_duration; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.inpatient_duration IS '住院天数';


--
-- Name: COLUMN discharge_record.admission_condition; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.admission_condition IS '入院情况';


--
-- Name: COLUMN discharge_record.positive_assist_exam; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.positive_assist_exam IS '阳性辅助检查结果';


--
-- Name: COLUMN discharge_record.treatment_course; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.treatment_course IS '诊疗经过';


--
-- Name: COLUMN discharge_record.discharge_condition; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.discharge_condition IS '出院情况';


--
-- Name: COLUMN discharge_record.discharge_order; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.discharge_order IS '出院医嘱';


--
-- Name: COLUMN discharge_record.condition_transform; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.condition_transform IS '病情转归';


--
-- Name: COLUMN discharge_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.record_content IS '非结构化全文';


--
-- Name: COLUMN discharge_record.resident_physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.resident_physician_sign IS '住院医师签名';


--
-- Name: COLUMN discharge_record.attending_physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.attending_physician_sign IS '主治医师签名';


--
-- Name: COLUMN discharge_record.chief_physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.chief_physician_sign IS '主副主任医师签名';


--
-- Name: COLUMN discharge_record.chief_physician_sign_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.chief_physician_sign_datetime IS '主副主任医师签署时间，独立于记录和提交时间';


--
-- Name: COLUMN discharge_record.v2_schema; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.v2_schema IS '源端完整二级结构化JSON，不截断或替代普通正文';


--
-- Name: COLUMN discharge_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN discharge_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN discharge_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN discharge_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN discharge_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.document_id IS '文档编号';


--
-- Name: COLUMN discharge_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.document_title IS '文档标题';


--
-- Name: COLUMN discharge_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.document_status IS '文档状态';


--
-- Name: COLUMN discharge_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.submitter IS '文档提交人';


--
-- Name: COLUMN discharge_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN discharge_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN discharge_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.inpat_no IS '住院号';


--
-- Name: COLUMN discharge_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.mr_no IS '病案号';


--
-- Name: COLUMN discharge_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.name IS '患者姓名';


--
-- Name: COLUMN discharge_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.sex IS '患者性别';


--
-- Name: COLUMN discharge_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.age_year IS '年龄(年)';


--
-- Name: COLUMN discharge_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.age_month IS '年龄(月)';


--
-- Name: COLUMN discharge_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.discharge_record.age IS '年龄-非结构化';


--
-- Name: docpat_commu_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.docpat_commu_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    dept_name character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    pat_doc_comm_type character varying(100),
    record_content text,
    record_datetime timestamp without time zone,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone
);


--
-- Name: COLUMN docpat_commu_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.institute_id IS '机构号';


--
-- Name: COLUMN docpat_commu_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.patient_id IS '患者号';


--
-- Name: COLUMN docpat_commu_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.visit_id IS '就诊号';


--
-- Name: COLUMN docpat_commu_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.document_id IS '文档编号';


--
-- Name: COLUMN docpat_commu_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.visit_type IS '就诊类型';


--
-- Name: COLUMN docpat_commu_record.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.dept_name IS '科室名称';


--
-- Name: COLUMN docpat_commu_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.name IS '患者姓名';


--
-- Name: COLUMN docpat_commu_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.sex IS '患者性别';


--
-- Name: COLUMN docpat_commu_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.age_year IS '年龄(年)';


--
-- Name: COLUMN docpat_commu_record.pat_doc_comm_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.pat_doc_comm_type IS '医患沟通记录类型';


--
-- Name: COLUMN docpat_commu_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.record_content IS '记录内容';


--
-- Name: COLUMN docpat_commu_record.record_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.record_datetime IS '记录时间';


--
-- Name: COLUMN docpat_commu_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN docpat_commu_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN docpat_commu_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN docpat_commu_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN docpat_commu_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.document_title IS '文档标题';


--
-- Name: COLUMN docpat_commu_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.document_status IS '文档状态';


--
-- Name: COLUMN docpat_commu_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.submitter IS '文档提交人';


--
-- Name: COLUMN docpat_commu_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN docpat_commu_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.docpat_commu_record.submit_datetime IS '文档提交时间';


--
-- Name: epidemic_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.epidemic_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    dept_name character varying(100),
    inpat_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    record_content text,
    record_datetime timestamp without time zone,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone
);


--
-- Name: COLUMN epidemic_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.institute_id IS '机构号';


--
-- Name: COLUMN epidemic_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.patient_id IS '患者号';


--
-- Name: COLUMN epidemic_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.visit_id IS '就诊号';


--
-- Name: COLUMN epidemic_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.document_id IS '文档编号';


--
-- Name: COLUMN epidemic_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.visit_type IS '就诊类型';


--
-- Name: COLUMN epidemic_record.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.dept_name IS '科室名称';


--
-- Name: COLUMN epidemic_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.inpat_no IS '住院号';


--
-- Name: COLUMN epidemic_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.name IS '患者姓名';


--
-- Name: COLUMN epidemic_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.sex IS '患者性别';


--
-- Name: COLUMN epidemic_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.age_year IS '年龄(年)';


--
-- Name: COLUMN epidemic_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.record_content IS '记录内容';


--
-- Name: COLUMN epidemic_record.record_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.record_datetime IS '记录时间';


--
-- Name: COLUMN epidemic_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN epidemic_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN epidemic_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN epidemic_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN epidemic_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.document_title IS '文档标题';


--
-- Name: COLUMN epidemic_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.document_status IS '文档状态';


--
-- Name: COLUMN epidemic_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.submitter IS '文档提交人';


--
-- Name: COLUMN epidemic_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN epidemic_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.epidemic_record.submit_datetime IS '文档提交时间';


--
-- Name: exam_item_report; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.exam_item_report (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    exam_no character varying(100),
    exam_id character varying(100),
    item_no character varying(100),
    item_id character varying(100),
    item_code character varying(100),
    item_name character varying(200),
    exam_name character varying(200),
    exam_item_name character varying(200),
    exam_type character varying(100),
    exam_result text,
    exam_impression text,
    exam_conclusion text,
    exam_findings text,
    findings text,
    impression text,
    conclusion text,
    diagnosis text,
    description text,
    summary_text text,
    report_time timestamp without time zone,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN exam_item_report.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.institute_id IS '机构号';


--
-- Name: COLUMN exam_item_report.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.patient_id IS '患者号';


--
-- Name: COLUMN exam_item_report.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.visit_id IS '就诊号';


--
-- Name: COLUMN exam_item_report.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.document_id IS '文档编号/报告单号';


--
-- Name: COLUMN exam_item_report.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.visit_type IS '就诊类型';


--
-- Name: COLUMN exam_item_report.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.record_content IS '非结构化全文';


--
-- Name: COLUMN exam_item_report.exam_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.exam_no IS '检查申请号';


--
-- Name: COLUMN exam_item_report.exam_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.exam_id IS '检查ID';


--
-- Name: COLUMN exam_item_report.item_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.item_no IS '检查项目序号';


--
-- Name: COLUMN exam_item_report.item_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.item_id IS '检查项目ID';


--
-- Name: COLUMN exam_item_report.item_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.item_code IS '检查项目编码';


--
-- Name: COLUMN exam_item_report.item_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.item_name IS '检查项目名称';


--
-- Name: COLUMN exam_item_report.exam_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.exam_name IS '检查名称';


--
-- Name: COLUMN exam_item_report.exam_item_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.exam_item_name IS '检查项目名称';


--
-- Name: COLUMN exam_item_report.exam_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.exam_type IS '检查类别';


--
-- Name: COLUMN exam_item_report.exam_result; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.exam_result IS '检查结果';


--
-- Name: COLUMN exam_item_report.exam_impression; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.exam_impression IS '检查印象';


--
-- Name: COLUMN exam_item_report.exam_conclusion; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.exam_conclusion IS '检查结论';


--
-- Name: COLUMN exam_item_report.exam_findings; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.exam_findings IS '检查所见';


--
-- Name: COLUMN exam_item_report.findings; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.findings IS '所见';


--
-- Name: COLUMN exam_item_report.impression; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.impression IS '印象';


--
-- Name: COLUMN exam_item_report.conclusion; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.conclusion IS '结论';


--
-- Name: COLUMN exam_item_report.diagnosis; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.diagnosis IS '诊断';


--
-- Name: COLUMN exam_item_report.description; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.description IS '描述';


--
-- Name: COLUMN exam_item_report.summary_text; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.summary_text IS '摘要';


--
-- Name: COLUMN exam_item_report.report_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.report_time IS '报告时间';


--
-- Name: COLUMN exam_item_report.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.last_modifier IS '最新修改人';


--
-- Name: COLUMN exam_item_report.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN exam_item_report.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN exam_item_report.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN exam_item_report.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.document_title IS '文档标题';


--
-- Name: COLUMN exam_item_report.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.document_status IS '文档状态';


--
-- Name: COLUMN exam_item_report.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.submitter IS '文档提交人';


--
-- Name: COLUMN exam_item_report.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN exam_item_report.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN exam_item_report.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.inpat_no IS '住院号';


--
-- Name: COLUMN exam_item_report.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.mr_no IS '病案号';


--
-- Name: COLUMN exam_item_report.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.name IS '患者姓名';


--
-- Name: COLUMN exam_item_report.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.sex IS '患者性别';


--
-- Name: COLUMN exam_item_report.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.age_year IS '年龄(年)';


--
-- Name: COLUMN exam_item_report.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.age_month IS '年龄(月)';


--
-- Name: COLUMN exam_item_report.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.exam_item_report.age IS '年龄-非结构化';


--
-- Name: first_course_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.first_course_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    dept_name character varying(100),
    ward_name character varying(100),
    ward_no character varying(100),
    bed_no character varying(100),
    case_characteristic text,
    diagnosis_discussion text,
    checkup text,
    assist_exam text,
    diagnose_based_on text,
    differential_diagnosis text,
    tcm_diagnosis_summary text,
    tcm_discriminate text,
    tcm_rule character varying(100),
    treatment_plan text,
    remark character varying(100),
    record_datetime timestamp without time zone,
    physician_sign character varying(100),
    physician_sign_datetime timestamp without time zone,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN first_course_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.institute_id IS '机构号';


--
-- Name: COLUMN first_course_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.patient_id IS '患者号';


--
-- Name: COLUMN first_course_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.visit_id IS '就诊号';


--
-- Name: COLUMN first_course_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.document_id IS '文档编号';


--
-- Name: COLUMN first_course_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.visit_type IS '就诊类型';


--
-- Name: COLUMN first_course_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.record_content IS '非结构化全文';


--
-- Name: COLUMN first_course_record.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.dept_name IS '科室名称';


--
-- Name: COLUMN first_course_record.ward_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.ward_name IS '病区名称';


--
-- Name: COLUMN first_course_record.ward_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.ward_no IS '病房号';


--
-- Name: COLUMN first_course_record.bed_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.bed_no IS '病床号';


--
-- Name: COLUMN first_course_record.case_characteristic; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.case_characteristic IS '病例特点';


--
-- Name: COLUMN first_course_record.diagnosis_discussion; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.diagnosis_discussion IS '拟诊讨论';


--
-- Name: COLUMN first_course_record.checkup; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.checkup IS '体格检查';


--
-- Name: COLUMN first_course_record.assist_exam; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.assist_exam IS '辅助检查';


--
-- Name: COLUMN first_course_record.diagnose_based_on; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.diagnose_based_on IS '诊断依据';


--
-- Name: COLUMN first_course_record.differential_diagnosis; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.differential_diagnosis IS '鉴别诊断';


--
-- Name: COLUMN first_course_record.tcm_diagnosis_summary; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.tcm_diagnosis_summary IS '中医四诊摘要';


--
-- Name: COLUMN first_course_record.tcm_discriminate; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.tcm_discriminate IS '中医辨病辨证依据';


--
-- Name: COLUMN first_course_record.tcm_rule; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.tcm_rule IS '中医治则治法';


--
-- Name: COLUMN first_course_record.treatment_plan; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.treatment_plan IS '诊疗计划';


--
-- Name: COLUMN first_course_record.remark; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.remark IS '备注';


--
-- Name: COLUMN first_course_record.record_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.record_datetime IS '记录时间';


--
-- Name: COLUMN first_course_record.physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.physician_sign IS '医师签名';


--
-- Name: COLUMN first_course_record.physician_sign_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.physician_sign_datetime IS '医师签名时间';


--
-- Name: COLUMN first_course_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN first_course_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN first_course_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN first_course_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN first_course_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.document_title IS '文档标题';


--
-- Name: COLUMN first_course_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.document_status IS '文档状态';


--
-- Name: COLUMN first_course_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.submitter IS '文档提交人';


--
-- Name: COLUMN first_course_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN first_course_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN first_course_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.inpat_no IS '住院号';


--
-- Name: COLUMN first_course_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.mr_no IS '病案号';


--
-- Name: COLUMN first_course_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.name IS '患者姓名';


--
-- Name: COLUMN first_course_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.sex IS '患者性别';


--
-- Name: COLUMN first_course_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.age_year IS '年龄(年)';


--
-- Name: COLUMN first_course_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.age_month IS '年龄(月)';


--
-- Name: COLUMN first_course_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.first_course_record.age IS '年龄-非结构化';


--
-- Name: frontpage_extracted_fields; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.frontpage_extracted_fields (
    id character varying(36) NOT NULL,
    institute_id character varying(100),
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    draft_id integer,
    frontpage_version character varying(50) DEFAULT 'v1'::character varying NOT NULL,
    module_name character varying(50) NOT NULL,
    field_path character varying(255) NOT NULL,
    field_key character varying(100) NOT NULL,
    field_label character varying(200),
    field_value text,
    value_type character varying(30),
    source_document_id character varying(100),
    source_text text,
    confidence double precision,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN frontpage_extracted_fields.id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.id IS 'UUID主键';


--
-- Name: COLUMN frontpage_extracted_fields.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.institute_id IS '机构号';


--
-- Name: COLUMN frontpage_extracted_fields.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.patient_id IS '患者号';


--
-- Name: COLUMN frontpage_extracted_fields.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.visit_id IS '就诊号';


--
-- Name: COLUMN frontpage_extracted_fields.draft_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.draft_id IS 'AI首页草稿ID';


--
-- Name: COLUMN frontpage_extracted_fields.frontpage_version; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.frontpage_version IS '首页版本';


--
-- Name: COLUMN frontpage_extracted_fields.module_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.module_name IS '模块名称';


--
-- Name: COLUMN frontpage_extracted_fields.field_path; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.field_path IS '字段路径';


--
-- Name: COLUMN frontpage_extracted_fields.field_key; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.field_key IS '字段键';


--
-- Name: COLUMN frontpage_extracted_fields.field_label; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.field_label IS '字段标签';


--
-- Name: COLUMN frontpage_extracted_fields.field_value; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.field_value IS '字段值';


--
-- Name: COLUMN frontpage_extracted_fields.value_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.value_type IS '值类型';


--
-- Name: COLUMN frontpage_extracted_fields.source_document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.source_document_id IS '来源文书ID';


--
-- Name: COLUMN frontpage_extracted_fields.source_text; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.source_text IS '来源文本';


--
-- Name: COLUMN frontpage_extracted_fields.confidence; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.confidence IS '置信度';


--
-- Name: COLUMN frontpage_extracted_fields.created_at; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.created_at IS '创建时间';


--
-- Name: COLUMN frontpage_extracted_fields.updated_at; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extracted_fields.updated_at IS '更新时间';


--
-- Name: frontpage_extraction_audit; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.frontpage_extraction_audit (
    id character varying(36) NOT NULL,
    institute_id character varying(100),
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    draft_id integer,
    frontpage_version character varying(50) DEFAULT 'v1'::character varying NOT NULL,
    status character varying(20) DEFAULT 'draft'::character varying NOT NULL,
    main_diagnosis_text text,
    main_diagnosis_code character varying(100),
    main_diagnosis_source character varying(50),
    main_diagnosis_confidence double precision,
    main_diagnosis_candidates_json text,
    guideline_rule_trace_json text,
    clinician_main_diagnosis_json text,
    coding_audit_llm_json text,
    evidence_json text,
    evidence_verified boolean DEFAULT false NOT NULL,
    evidence_summary text,
    evidence_source_documents_json text,
    evidence_spans_json text,
    evidence_page_judgement_json text,
    diagnoses_json text,
    procedures_json text,
    basic_info_json text,
    hospitalization_json text,
    costs_json text,
    generated_by character varying(100),
    confirmed_by character varying(100),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN frontpage_extraction_audit.id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.id IS 'UUID主键';


--
-- Name: COLUMN frontpage_extraction_audit.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.institute_id IS '机构号';


--
-- Name: COLUMN frontpage_extraction_audit.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.patient_id IS '患者号';


--
-- Name: COLUMN frontpage_extraction_audit.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.visit_id IS '就诊号';


--
-- Name: COLUMN frontpage_extraction_audit.draft_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.draft_id IS 'AI首页草稿ID';


--
-- Name: COLUMN frontpage_extraction_audit.frontpage_version; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.frontpage_version IS '首页版本';


--
-- Name: COLUMN frontpage_extraction_audit.status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.status IS '状态：draft/confirmed/superseded';


--
-- Name: COLUMN frontpage_extraction_audit.main_diagnosis_text; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.main_diagnosis_text IS '主诊断文本';


--
-- Name: COLUMN frontpage_extraction_audit.main_diagnosis_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.main_diagnosis_code IS '主诊断编码';


--
-- Name: COLUMN frontpage_extraction_audit.main_diagnosis_source; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.main_diagnosis_source IS '主诊断来源';


--
-- Name: COLUMN frontpage_extraction_audit.main_diagnosis_confidence; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.main_diagnosis_confidence IS '主诊断置信度';


--
-- Name: COLUMN frontpage_extraction_audit.main_diagnosis_candidates_json; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.main_diagnosis_candidates_json IS '主诊断候选JSON';


--
-- Name: COLUMN frontpage_extraction_audit.guideline_rule_trace_json; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.guideline_rule_trace_json IS '指南规则轨迹JSON';


--
-- Name: COLUMN frontpage_extraction_audit.clinician_main_diagnosis_json; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.clinician_main_diagnosis_json IS '临床主诊断JSON';


--
-- Name: COLUMN frontpage_extraction_audit.coding_audit_llm_json; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.coding_audit_llm_json IS '编码审核LLM JSON';


--
-- Name: COLUMN frontpage_extraction_audit.evidence_json; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.evidence_json IS '证据总包JSON';


--
-- Name: COLUMN frontpage_extraction_audit.evidence_verified; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.evidence_verified IS '证据是否通过校验';


--
-- Name: COLUMN frontpage_extraction_audit.evidence_summary; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.evidence_summary IS '证据摘要';


--
-- Name: COLUMN frontpage_extraction_audit.evidence_source_documents_json; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.evidence_source_documents_json IS '证据来源文书JSON';


--
-- Name: COLUMN frontpage_extraction_audit.evidence_spans_json; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.evidence_spans_json IS '证据片段JSON';


--
-- Name: COLUMN frontpage_extraction_audit.evidence_page_judgement_json; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.evidence_page_judgement_json IS '证据页判断JSON';


--
-- Name: COLUMN frontpage_extraction_audit.diagnoses_json; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.diagnoses_json IS '诊断结构JSON';


--
-- Name: COLUMN frontpage_extraction_audit.procedures_json; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.procedures_json IS '手术结构JSON';


--
-- Name: COLUMN frontpage_extraction_audit.basic_info_json; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.basic_info_json IS '基础信息JSON';


--
-- Name: COLUMN frontpage_extraction_audit.hospitalization_json; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.hospitalization_json IS '住院信息JSON';


--
-- Name: COLUMN frontpage_extraction_audit.costs_json; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.costs_json IS '费用信息JSON';


--
-- Name: COLUMN frontpage_extraction_audit.generated_by; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.generated_by IS '生成人';


--
-- Name: COLUMN frontpage_extraction_audit.confirmed_by; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.confirmed_by IS '确认人';


--
-- Name: COLUMN frontpage_extraction_audit.created_at; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.created_at IS '创建时间';


--
-- Name: COLUMN frontpage_extraction_audit.updated_at; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.frontpage_extraction_audit.updated_at IS '更新时间';


--
-- Name: handoff_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.handoff_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    shift_time timestamp with time zone,
    handoff_doctor character varying(100),
    record_time timestamp with time zone,
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN handoff_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.institute_id IS '机构号';


--
-- Name: COLUMN handoff_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.patient_id IS '患者号';


--
-- Name: COLUMN handoff_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.visit_id IS '就诊号';


--
-- Name: COLUMN handoff_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.document_id IS '文档编号';


--
-- Name: COLUMN handoff_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.visit_type IS '就诊类型';


--
-- Name: COLUMN handoff_record.shift_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.shift_time IS '交班时间';


--
-- Name: COLUMN handoff_record.handoff_doctor; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.handoff_doctor IS '交班医师';


--
-- Name: COLUMN handoff_record.record_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.record_time IS '交班记录时间';


--
-- Name: COLUMN handoff_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.record_content IS '非结构化全文';


--
-- Name: COLUMN handoff_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN handoff_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN handoff_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN handoff_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN handoff_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.document_title IS '文档标题';


--
-- Name: COLUMN handoff_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.document_status IS '文档状态';


--
-- Name: COLUMN handoff_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.submitter IS '文档提交人';


--
-- Name: COLUMN handoff_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN handoff_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN handoff_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.inpat_no IS '住院号';


--
-- Name: COLUMN handoff_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.mr_no IS '病案号';


--
-- Name: COLUMN handoff_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.name IS '患者姓名';


--
-- Name: COLUMN handoff_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.sex IS '患者性别';


--
-- Name: COLUMN handoff_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.age_year IS '年龄(年)';


--
-- Name: COLUMN handoff_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.age_month IS '年龄(月)';


--
-- Name: COLUMN handoff_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handoff_record.age IS '年龄-非结构化';


--
-- Name: handover_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.handover_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    shift_time timestamp with time zone,
    handover_doctor character varying(100),
    record_time timestamp with time zone,
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN handover_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.institute_id IS '机构号';


--
-- Name: COLUMN handover_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.patient_id IS '患者号';


--
-- Name: COLUMN handover_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.visit_id IS '就诊号';


--
-- Name: COLUMN handover_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.document_id IS '文档编号';


--
-- Name: COLUMN handover_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.visit_type IS '就诊类型';


--
-- Name: COLUMN handover_record.shift_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.shift_time IS '接班时间';


--
-- Name: COLUMN handover_record.handover_doctor; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.handover_doctor IS '接班医师';


--
-- Name: COLUMN handover_record.record_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.record_time IS '接班记录时间';


--
-- Name: COLUMN handover_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.record_content IS '非结构化全文';


--
-- Name: COLUMN handover_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN handover_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN handover_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN handover_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN handover_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.document_title IS '文档标题';


--
-- Name: COLUMN handover_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.document_status IS '文档状态';


--
-- Name: COLUMN handover_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.submitter IS '文档提交人';


--
-- Name: COLUMN handover_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN handover_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN handover_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.inpat_no IS '住院号';


--
-- Name: COLUMN handover_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.mr_no IS '病案号';


--
-- Name: COLUMN handover_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.name IS '患者姓名';


--
-- Name: COLUMN handover_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.sex IS '患者性别';


--
-- Name: COLUMN handover_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.age_year IS '年龄(年)';


--
-- Name: COLUMN handover_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.age_month IS '年龄(月)';


--
-- Name: COLUMN handover_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.handover_record.age IS '年龄-非结构化';


--
-- Name: hospitalization_status_projection; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.hospitalization_status_projection (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    status character varying(20) NOT NULL,
    verified_at timestamp without time zone NOT NULL,
    source character varying(100) NOT NULL,
    discharge_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: inpat_bill_item; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.inpat_bill_item (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    bill_item_id character varying(100) NOT NULL,
    receipt_id character varying(100),
    inpat_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    order_id character varying(100),
    item_type character varying(100),
    medical_catalog_code character varying(100),
    medical_catalog_name character varying(100),
    medinsur_catalog_code character varying(100),
    medinsur_catalog_name character varying(100),
    item_specification character varying(100),
    firm character varying(100),
    unit_price character varying(100),
    quantity character varying(100),
    quantity_unit character varying(100),
    cost character varying(100),
    charge character varying(100),
    insurance_category character varying(100),
    charge_item_level character varying(100),
    billing_datetime timestamp without time zone,
    order_dept_name character varying(100),
    executive_dept_name character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN inpat_bill_item.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.institute_id IS '机构号';


--
-- Name: COLUMN inpat_bill_item.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.patient_id IS '患者号';


--
-- Name: COLUMN inpat_bill_item.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.visit_id IS '就诊号';


--
-- Name: COLUMN inpat_bill_item.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.visit_type IS '就诊类型';


--
-- Name: COLUMN inpat_bill_item.bill_item_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.bill_item_id IS '费用明细号';


--
-- Name: COLUMN inpat_bill_item.receipt_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.receipt_id IS '费用结算号';


--
-- Name: COLUMN inpat_bill_item.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.inpat_no IS '住院号';


--
-- Name: COLUMN inpat_bill_item.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.name IS '患者姓名';


--
-- Name: COLUMN inpat_bill_item.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.sex IS '患者性别';


--
-- Name: COLUMN inpat_bill_item.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.age_year IS '年龄(年)';


--
-- Name: COLUMN inpat_bill_item.order_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.order_id IS '医嘱号';


--
-- Name: COLUMN inpat_bill_item.item_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.item_type IS '项目类别';


--
-- Name: COLUMN inpat_bill_item.medical_catalog_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.medical_catalog_code IS '医疗目录编码';


--
-- Name: COLUMN inpat_bill_item.medical_catalog_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.medical_catalog_name IS '医疗目录名称';


--
-- Name: COLUMN inpat_bill_item.medinsur_catalog_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.medinsur_catalog_code IS '医保目录编码';


--
-- Name: COLUMN inpat_bill_item.medinsur_catalog_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.medinsur_catalog_name IS '医保目录名称';


--
-- Name: COLUMN inpat_bill_item.item_specification; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.item_specification IS '项目规格';


--
-- Name: COLUMN inpat_bill_item.firm; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.firm IS '生产厂商';


--
-- Name: COLUMN inpat_bill_item.unit_price; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.unit_price IS '单价';


--
-- Name: COLUMN inpat_bill_item.quantity; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.quantity IS '数量';


--
-- Name: COLUMN inpat_bill_item.quantity_unit; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.quantity_unit IS '数量单位';


--
-- Name: COLUMN inpat_bill_item.cost; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.cost IS '应收金额';


--
-- Name: COLUMN inpat_bill_item.charge; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.charge IS '实收金额';


--
-- Name: COLUMN inpat_bill_item.insurance_category; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.insurance_category IS '医保分类';


--
-- Name: COLUMN inpat_bill_item.charge_item_level; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.charge_item_level IS '收费项目等级';


--
-- Name: COLUMN inpat_bill_item.billing_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.billing_datetime IS '费用发生时间';


--
-- Name: COLUMN inpat_bill_item.order_dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.order_dept_name IS '开单科室';


--
-- Name: COLUMN inpat_bill_item.executive_dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.executive_dept_name IS '执行科室';


--
-- Name: COLUMN inpat_bill_item.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.record_content IS '记录内容';


--
-- Name: COLUMN inpat_bill_item.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.last_modifier IS '最新修改人';


--
-- Name: COLUMN inpat_bill_item.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN inpat_bill_item.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN inpat_bill_item.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_bill_item.update_time IS '数据更新时间，用于增量同步';


--
-- Name: inpat_drug_order; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.inpat_drug_order (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    order_id character varying(100) NOT NULL,
    inpat_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100),
    dept_name character varying(100),
    group_id character varying(100),
    repeat_indicator character varying(100),
    drug_type character varying(100),
    brand_name character varying(100),
    drug_code character varying(100),
    generic_name character varying(100),
    cfda_id character varying(100),
    firm character varying(100),
    drug_specification character varying(100),
    drug_frequency character varying(100),
    drug_apply_method character varying(100),
    single_dose character varying(100),
    single_dose_unit character varying(100),
    dose_form character varying(100),
    medication_duration character varying(100),
    prescribed_datetime timestamp without time zone,
    planned_start_datetime timestamp with time zone,
    prescribed_doctor character varying(100),
    order_status character varying(100),
    planned_end_datetime timestamp with time zone,
    reviewed_datetime timestamp without time zone,
    carried_datetime timestamp without time zone,
    canceled_datetime timestamp without time zone,
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN inpat_drug_order.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.institute_id IS '机构号';


--
-- Name: COLUMN inpat_drug_order.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.patient_id IS '患者号';


--
-- Name: COLUMN inpat_drug_order.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.visit_id IS '就诊号';


--
-- Name: COLUMN inpat_drug_order.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.visit_type IS '就诊类型';


--
-- Name: COLUMN inpat_drug_order.order_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.order_id IS '医嘱号';


--
-- Name: COLUMN inpat_drug_order.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.inpat_no IS '住院号';


--
-- Name: COLUMN inpat_drug_order.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.name IS '患者姓名';


--
-- Name: COLUMN inpat_drug_order.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.sex IS '患者性别';


--
-- Name: COLUMN inpat_drug_order.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.age_year IS '年龄(年)';


--
-- Name: COLUMN inpat_drug_order.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.age_month IS '年龄(月)';


--
-- Name: COLUMN inpat_drug_order.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.age IS '年龄';


--
-- Name: COLUMN inpat_drug_order.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.dept_name IS '科室名称';


--
-- Name: COLUMN inpat_drug_order.group_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.group_id IS '医嘱组号';


--
-- Name: COLUMN inpat_drug_order.repeat_indicator; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.repeat_indicator IS '医嘱长临标识';


--
-- Name: COLUMN inpat_drug_order.drug_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.drug_type IS '药品类别';


--
-- Name: COLUMN inpat_drug_order.brand_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.brand_name IS '药品商品名';


--
-- Name: COLUMN inpat_drug_order.drug_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.drug_code IS '药品机构代码';


--
-- Name: COLUMN inpat_drug_order.generic_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.generic_name IS '药品通用名';


--
-- Name: COLUMN inpat_drug_order.cfda_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.cfda_id IS '国药准字号';


--
-- Name: COLUMN inpat_drug_order.firm; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.firm IS '药品生产厂商';


--
-- Name: COLUMN inpat_drug_order.drug_specification; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.drug_specification IS '药品规格';


--
-- Name: COLUMN inpat_drug_order.drug_frequency; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.drug_frequency IS '用药频次';


--
-- Name: COLUMN inpat_drug_order.drug_apply_method; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.drug_apply_method IS '用药途径';


--
-- Name: COLUMN inpat_drug_order.single_dose; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.single_dose IS '单次用药剂量';


--
-- Name: COLUMN inpat_drug_order.single_dose_unit; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.single_dose_unit IS '单次用药剂量单位';


--
-- Name: COLUMN inpat_drug_order.dose_form; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.dose_form IS '药品剂型';


--
-- Name: COLUMN inpat_drug_order.medication_duration; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.medication_duration IS '用药天数';


--
-- Name: COLUMN inpat_drug_order.prescribed_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.prescribed_datetime IS '开立时间';


--
-- Name: COLUMN inpat_drug_order.planned_start_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.planned_start_datetime IS '计划开始/启用时间（非实际给药时间）';


--
-- Name: COLUMN inpat_drug_order.prescribed_doctor; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.prescribed_doctor IS '开立医师姓名';


--
-- Name: COLUMN inpat_drug_order.order_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.order_status IS '医嘱状态';


--
-- Name: COLUMN inpat_drug_order.planned_end_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.planned_end_datetime IS '计划结束时间';


--
-- Name: COLUMN inpat_drug_order.reviewed_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.reviewed_datetime IS '源医嘱审核时间';


--
-- Name: COLUMN inpat_drug_order.carried_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.carried_datetime IS '源医嘱执行时间';


--
-- Name: COLUMN inpat_drug_order.canceled_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.canceled_datetime IS '源医嘱撤销时间';


--
-- Name: COLUMN inpat_drug_order.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.record_content IS '记录内容';


--
-- Name: COLUMN inpat_drug_order.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.last_modifier IS '最新修改人';


--
-- Name: COLUMN inpat_drug_order.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN inpat_drug_order.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN inpat_drug_order.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_drug_order.update_time IS '数据更新时间，用于增量同步';


--
-- Name: inpat_nondrug_order; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.inpat_nondrug_order (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    order_id character varying(100) NOT NULL,
    inpat_no character varying(100),
    application_id character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100),
    dept_name character varying(100),
    group_id character varying(100),
    repeat_indicator character varying(100),
    order_type character varying(100),
    order_name character varying(100),
    quantity character varying(100),
    quantity_unit character varying(100),
    frequency character varying(100),
    prescribed_datetime timestamp without time zone,
    planned_start_datetime timestamp with time zone,
    planned_end_datetime timestamp with time zone,
    prescribed_doctor character varying(100),
    order_status character varying(100),
    reviewed_datetime timestamp without time zone,
    carried_datetime timestamp without time zone,
    canceled_datetime timestamp without time zone,
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN inpat_nondrug_order.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.institute_id IS '机构号';


--
-- Name: COLUMN inpat_nondrug_order.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.patient_id IS '患者号';


--
-- Name: COLUMN inpat_nondrug_order.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.visit_id IS '就诊号';


--
-- Name: COLUMN inpat_nondrug_order.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.visit_type IS '就诊类型';


--
-- Name: COLUMN inpat_nondrug_order.order_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.order_id IS '医嘱号';


--
-- Name: COLUMN inpat_nondrug_order.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.inpat_no IS '住院号';


--
-- Name: COLUMN inpat_nondrug_order.application_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.application_id IS '申请号';


--
-- Name: COLUMN inpat_nondrug_order.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.name IS '患者姓名';


--
-- Name: COLUMN inpat_nondrug_order.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.sex IS '患者性别';


--
-- Name: COLUMN inpat_nondrug_order.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.age_year IS '年龄(年)';


--
-- Name: COLUMN inpat_nondrug_order.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.age_month IS '年龄(月)';


--
-- Name: COLUMN inpat_nondrug_order.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.age IS '年龄';


--
-- Name: COLUMN inpat_nondrug_order.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.dept_name IS '科室名称';


--
-- Name: COLUMN inpat_nondrug_order.group_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.group_id IS '医嘱组号';


--
-- Name: COLUMN inpat_nondrug_order.repeat_indicator; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.repeat_indicator IS '医嘱长临标识';


--
-- Name: COLUMN inpat_nondrug_order.order_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.order_type IS '医嘱类别';


--
-- Name: COLUMN inpat_nondrug_order.order_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.order_name IS '医嘱名称';


--
-- Name: COLUMN inpat_nondrug_order.quantity; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.quantity IS '数量';


--
-- Name: COLUMN inpat_nondrug_order.quantity_unit; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.quantity_unit IS '数量单位';


--
-- Name: COLUMN inpat_nondrug_order.frequency; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.frequency IS '频次';


--
-- Name: COLUMN inpat_nondrug_order.prescribed_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.prescribed_datetime IS '开立时间';


--
-- Name: COLUMN inpat_nondrug_order.planned_start_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.planned_start_datetime IS '计划开始/启用时间';


--
-- Name: COLUMN inpat_nondrug_order.planned_end_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.planned_end_datetime IS '计划结束/停止时间';


--
-- Name: COLUMN inpat_nondrug_order.prescribed_doctor; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.prescribed_doctor IS '开立医师姓名';


--
-- Name: COLUMN inpat_nondrug_order.order_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.order_status IS '医嘱状态';


--
-- Name: COLUMN inpat_nondrug_order.reviewed_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.reviewed_datetime IS '源医嘱审核时间';


--
-- Name: COLUMN inpat_nondrug_order.carried_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.carried_datetime IS '源医嘱执行时间';


--
-- Name: COLUMN inpat_nondrug_order.canceled_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.canceled_datetime IS '源医嘱撤销时间';


--
-- Name: COLUMN inpat_nondrug_order.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.record_content IS '记录内容';


--
-- Name: COLUMN inpat_nondrug_order.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.last_modifier IS '最新修改人';


--
-- Name: COLUMN inpat_nondrug_order.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN inpat_nondrug_order.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN inpat_nondrug_order.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_nondrug_order.update_time IS '数据更新时间，用于增量同步';


--
-- Name: inpat_registration; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.inpat_registration (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    visit_cnt character varying(100),
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    birthday date,
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100),
    id_card_type character varying(100),
    id_card_no character varying(100),
    charge_type character varying(100),
    insurance_type character varying(100),
    insurance_no character varying(100),
    admission_dept_name character varying(100),
    admission_reason character varying(100),
    discharge_dept_name character varying(100),
    admission_datetime timestamp without time zone,
    discharge_datetime timestamp without time zone,
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN inpat_registration.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.institute_id IS '机构号';


--
-- Name: COLUMN inpat_registration.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.patient_id IS '患者号';


--
-- Name: COLUMN inpat_registration.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.visit_id IS '就诊号';


--
-- Name: COLUMN inpat_registration.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.visit_type IS '就诊类型';


--
-- Name: COLUMN inpat_registration.visit_cnt; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.visit_cnt IS '就诊次数';


--
-- Name: COLUMN inpat_registration.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.inpat_no IS '住院号';


--
-- Name: COLUMN inpat_registration.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.mr_no IS '病案号';


--
-- Name: COLUMN inpat_registration.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.name IS '患者姓名';


--
-- Name: COLUMN inpat_registration.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.sex IS '患者性别';


--
-- Name: COLUMN inpat_registration.birthday; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.birthday IS '出生日期';


--
-- Name: COLUMN inpat_registration.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.age_year IS '年龄(年)';


--
-- Name: COLUMN inpat_registration.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.age_month IS '年龄(月)';


--
-- Name: COLUMN inpat_registration.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.age IS '年龄';


--
-- Name: COLUMN inpat_registration.id_card_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.id_card_type IS '身份证件类别';


--
-- Name: COLUMN inpat_registration.id_card_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.id_card_no IS '身份证件号码';


--
-- Name: COLUMN inpat_registration.charge_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.charge_type IS '费用类别';


--
-- Name: COLUMN inpat_registration.insurance_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.insurance_type IS '保险类别';


--
-- Name: COLUMN inpat_registration.insurance_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.insurance_no IS '医保号';


--
-- Name: COLUMN inpat_registration.admission_dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.admission_dept_name IS '入院科室';


--
-- Name: COLUMN inpat_registration.admission_reason; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.admission_reason IS '入院原因';


--
-- Name: COLUMN inpat_registration.discharge_dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.discharge_dept_name IS '出院科室';


--
-- Name: COLUMN inpat_registration.admission_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.admission_datetime IS '入院时间';


--
-- Name: COLUMN inpat_registration.discharge_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.discharge_datetime IS '出院时间';


--
-- Name: COLUMN inpat_registration.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.record_content IS '非结构化大段文档记录';


--
-- Name: COLUMN inpat_registration.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.last_modifier IS '最新修改人';


--
-- Name: COLUMN inpat_registration.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN inpat_registration.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN inpat_registration.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.inpat_registration.update_time IS '数据更新时间，用于增量同步';


--
-- Name: labtest_item; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.labtest_item (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    test_id character varying(100) NOT NULL,
    test_item_id character varying(100) NOT NULL,
    item_name character varying(100),
    item_code character varying(100),
    report_datetime timestamp without time zone,
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN labtest_item.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item.institute_id IS '机构号';


--
-- Name: COLUMN labtest_item.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item.patient_id IS '患者号';


--
-- Name: COLUMN labtest_item.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item.visit_id IS '就诊号';


--
-- Name: COLUMN labtest_item.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item.visit_type IS '就诊类型';


--
-- Name: COLUMN labtest_item.test_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item.test_id IS '申请序号';


--
-- Name: COLUMN labtest_item.test_item_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item.test_item_id IS '项目序号';


--
-- Name: COLUMN labtest_item.item_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item.item_name IS '项目名称';


--
-- Name: COLUMN labtest_item.item_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item.item_code IS '项目代码';


--
-- Name: COLUMN labtest_item.report_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item.report_datetime IS '报告时间';


--
-- Name: COLUMN labtest_item.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item.record_content IS '记录内容';


--
-- Name: COLUMN labtest_item.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item.last_modifier IS '最新修改人';


--
-- Name: COLUMN labtest_item.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN labtest_item.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN labtest_item.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item.update_time IS '数据更新时间，用于增量同步';


--
-- Name: labtest_item_report; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.labtest_item_report (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    test_no character varying(100),
    test_id character varying(100),
    item_no character varying(100),
    item_id character varying(100),
    item_code character varying(100),
    item_name character varying(200),
    item_abbreviation character varying(100),
    result character varying(500),
    unit character varying(100),
    abnormal_indicator character varying(100),
    reference_range character varying(200),
    referencevalue_min character varying(100),
    referencevalue_max character varying(100),
    report_time timestamp without time zone,
    report_status text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN labtest_item_report.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.institute_id IS '机构号';


--
-- Name: COLUMN labtest_item_report.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.patient_id IS '患者号';


--
-- Name: COLUMN labtest_item_report.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.visit_id IS '就诊号';


--
-- Name: COLUMN labtest_item_report.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.document_id IS '文档编号/报告单号';


--
-- Name: COLUMN labtest_item_report.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.visit_type IS '就诊类型';


--
-- Name: COLUMN labtest_item_report.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.record_content IS '非结构化全文';


--
-- Name: COLUMN labtest_item_report.test_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.test_no IS '检验申请号';


--
-- Name: COLUMN labtest_item_report.test_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.test_id IS '检验申请ID';


--
-- Name: COLUMN labtest_item_report.item_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.item_no IS '检验项目序号';


--
-- Name: COLUMN labtest_item_report.item_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.item_id IS '检验项目ID';


--
-- Name: COLUMN labtest_item_report.item_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.item_code IS '检验项目编码';


--
-- Name: COLUMN labtest_item_report.item_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.item_name IS '检验项目名称';


--
-- Name: COLUMN labtest_item_report.item_abbreviation; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.item_abbreviation IS '检验项目简称';


--
-- Name: COLUMN labtest_item_report.result; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.result IS '检验结果';


--
-- Name: COLUMN labtest_item_report.unit; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.unit IS '单位';


--
-- Name: COLUMN labtest_item_report.abnormal_indicator; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.abnormal_indicator IS '异常标志';


--
-- Name: COLUMN labtest_item_report.reference_range; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.reference_range IS '参考范围';


--
-- Name: COLUMN labtest_item_report.referencevalue_min; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.referencevalue_min IS '参考下限';


--
-- Name: COLUMN labtest_item_report.referencevalue_max; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.referencevalue_max IS '参考上限';


--
-- Name: COLUMN labtest_item_report.report_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.report_time IS '报告时间';


--
-- Name: COLUMN labtest_item_report.report_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.report_status IS '源检验报告状态';


--
-- Name: COLUMN labtest_item_report.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.last_modifier IS '最新修改人';


--
-- Name: COLUMN labtest_item_report.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN labtest_item_report.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN labtest_item_report.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN labtest_item_report.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.document_title IS '文档标题';


--
-- Name: COLUMN labtest_item_report.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.document_status IS '文档状态';


--
-- Name: COLUMN labtest_item_report.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.submitter IS '文档提交人';


--
-- Name: COLUMN labtest_item_report.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN labtest_item_report.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN labtest_item_report.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.inpat_no IS '住院号';


--
-- Name: COLUMN labtest_item_report.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.mr_no IS '病案号';


--
-- Name: COLUMN labtest_item_report.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.name IS '患者姓名';


--
-- Name: COLUMN labtest_item_report.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.sex IS '患者性别';


--
-- Name: COLUMN labtest_item_report.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.age_year IS '年龄(年)';


--
-- Name: COLUMN labtest_item_report.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.age_month IS '年龄(月)';


--
-- Name: COLUMN labtest_item_report.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_item_report.age IS '年龄-非结构化';


--
-- Name: labtest_master; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.labtest_master (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    test_id character varying(100) NOT NULL,
    order_id character varying(100),
    inpat_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    labtest_subject character varying(100),
    labtest_cause character varying(100),
    specimen character varying(100),
    request_dept character varying(100),
    request_physician character varying(100),
    request_datetime timestamp without time zone,
    report_datetime timestamp without time zone,
    reporter character varying(100),
    verifier character varying(100),
    labtest_result_status character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN labtest_master.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.institute_id IS '机构号';


--
-- Name: COLUMN labtest_master.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.patient_id IS '患者号';


--
-- Name: COLUMN labtest_master.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.visit_id IS '就诊号';


--
-- Name: COLUMN labtest_master.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.visit_type IS '就诊类型';


--
-- Name: COLUMN labtest_master.test_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.test_id IS '申请序号';


--
-- Name: COLUMN labtest_master.order_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.order_id IS '医嘱号';


--
-- Name: COLUMN labtest_master.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.inpat_no IS '住院号';


--
-- Name: COLUMN labtest_master.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.name IS '患者姓名';


--
-- Name: COLUMN labtest_master.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.sex IS '患者性别';


--
-- Name: COLUMN labtest_master.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.age_year IS '年龄(年)';


--
-- Name: COLUMN labtest_master.labtest_subject; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.labtest_subject IS '检验类别';


--
-- Name: COLUMN labtest_master.labtest_cause; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.labtest_cause IS '检验目的';


--
-- Name: COLUMN labtest_master.specimen; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.specimen IS '标本类型';


--
-- Name: COLUMN labtest_master.request_dept; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.request_dept IS '申请科室';


--
-- Name: COLUMN labtest_master.request_physician; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.request_physician IS '申请医师姓名';


--
-- Name: COLUMN labtest_master.request_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.request_datetime IS '申请时间';


--
-- Name: COLUMN labtest_master.report_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.report_datetime IS '报告时间';


--
-- Name: COLUMN labtest_master.reporter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.reporter IS '报告者';


--
-- Name: COLUMN labtest_master.verifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.verifier IS '审核者';


--
-- Name: COLUMN labtest_master.labtest_result_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.labtest_result_status IS '检验结果状态';


--
-- Name: COLUMN labtest_master.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.record_content IS '记录内容';


--
-- Name: COLUMN labtest_master.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.last_modifier IS '最新修改人';


--
-- Name: COLUMN labtest_master.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN labtest_master.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN labtest_master.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.labtest_master.update_time IS '数据更新时间，用于增量同步';


--
-- Name: medical_documents; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.medical_documents (
    id character varying(36) NOT NULL,
    record_id character varying(100) NOT NULL,
    document_type character varying(50),
    content text,
    qc_status character varying(20) NOT NULL,
    qc_score double precision,
    qc_last_analyzed timestamp without time zone,
    status character varying(20) NOT NULL,
    sort_order integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: medical_insurance_settlement; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.medical_insurance_settlement (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    document_id character varying(100),
    designated_medical_institution character varying(100),
    medical_insurance_record_dept character varying(100),
    medical_insurance_recorder character varying(100),
    medinsur_serial_no character varying(100),
    business_serial_no character varying(100),
    medinsur_receipt_id character varying(100),
    ticket_code character varying(100),
    ticket_no character varying(100),
    settlement_method character varying(100),
    patient_insurance_no character varying(100),
    inpat_no character varying(100),
    mr_no character varying(100),
    nationality character varying(100),
    occupation_category character varying(100),
    currentaddress_province character varying(100),
    currentaddress_city character varying(100),
    currentaddress_county character varying(100),
    currentaddress_town character varying(100),
    currentaddress_village character varying(100),
    currentaddress_detail character varying(100),
    currentaddress text,
    currentaddress_postcode character varying(100),
    currentaddress_phone character varying(100),
    work_unit character varying(100),
    workplace_province character varying(100),
    workplace_city character varying(100),
    workplace_county character varying(100),
    workplace_town character varying(100),
    workplace_village character varying(100),
    workplace_detail character varying(100),
    workplace text,
    workplace_postcode character varying(100),
    work_telephone character varying(100),
    contact_name character varying(100),
    contact_relationship character varying(100),
    contact_address character varying(100),
    contact_telephone character varying(100),
    newborn_admission_type character varying(100),
    newborn_birthweight character varying(100),
    newborn_admitweigth character varying(100),
    newborn_birth_weight character varying(100),
    newborn_admission_weight character varying(100),
    admission_route character varying(100),
    special_personnel_type character varying(100),
    admission_datetime timestamp without time zone,
    admission_dept_name character varying(100),
    transfer_dept_name character varying(100),
    discharge_datetime timestamp without time zone,
    discharge_dept_name character varying(100),
    leaving_hospital_way character varying(100),
    receiving_institution_name character varying(100),
    receiving_institution_code character varying(100),
    rehospital_with_month character varying(100),
    rehospital_with_month_purpose character varying(100),
    insurance_no character varying(100),
    declaration_time timestamp without time zone,
    inpat_type character varying(100),
    therapy_type character varying(100),
    diagnosis_code_cnt character varying(100),
    surgery_code_cnt character varying(100),
    ventilator_usetime character varying(100),
    coma_timebefadm_d character varying(100),
    coma_timebefadm_h character varying(100),
    coma_timebefadm_min character varying(100),
    coma_timeaftadm_d character varying(100),
    coma_timeaftadm_h character varying(100),
    coma_timeaftadm_min character varying(100),
    primary_care_days character varying(100),
    secondary_care_days character varying(100),
    tertiary_care_days character varying(100),
    intensive_care_days character varying(100),
    insured_place character varying(100),
    out_of_pocket_advance character varying(100),
    out_of_pocket_amount character varying(100),
    personal_account_expend character varying(100),
    cash_payment_amount character varying(100),
    insurance_type character varying(100),
    medical_insurance_institution character varying(100),
    medical_insurance_agent character varying(100),
    medical_insurance_agent_code character varying(100),
    outp_chronic_department character varying(100),
    outp_chronic_date timestamp without time zone,
    attending_physician_code character varying(100),
    responsible_nurse_code character varying(100),
    settlement_status character varying(100),
    start_date timestamp without time zone,
    end_date timestamp without time zone,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN medical_insurance_settlement.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.institute_id IS '机构号';


--
-- Name: COLUMN medical_insurance_settlement.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.patient_id IS '患者号';


--
-- Name: COLUMN medical_insurance_settlement.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.visit_id IS '就诊号';


--
-- Name: COLUMN medical_insurance_settlement.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.visit_type IS '就诊类型';


--
-- Name: COLUMN medical_insurance_settlement.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.document_id IS '文档编号';


--
-- Name: COLUMN medical_insurance_settlement.designated_medical_institution; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.designated_medical_institution IS '定点医疗机构代码';


--
-- Name: COLUMN medical_insurance_settlement.medical_insurance_record_dept; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.medical_insurance_record_dept IS '医疗机构填报部门';


--
-- Name: COLUMN medical_insurance_settlement.medical_insurance_recorder; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.medical_insurance_recorder IS '医疗机构填报人';


--
-- Name: COLUMN medical_insurance_settlement.medinsur_serial_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.medinsur_serial_no IS '清单流水号';


--
-- Name: COLUMN medical_insurance_settlement.business_serial_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.business_serial_no IS '业务流水号';


--
-- Name: COLUMN medical_insurance_settlement.medinsur_receipt_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.medinsur_receipt_id IS '医保结算号';


--
-- Name: COLUMN medical_insurance_settlement.ticket_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.ticket_code IS '票据代码';


--
-- Name: COLUMN medical_insurance_settlement.ticket_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.ticket_no IS '票据号码';


--
-- Name: COLUMN medical_insurance_settlement.settlement_method; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.settlement_method IS '清算方式';


--
-- Name: COLUMN medical_insurance_settlement.patient_insurance_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.patient_insurance_no IS '医保系统内人员编号';


--
-- Name: COLUMN medical_insurance_settlement.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.inpat_no IS '住院号';


--
-- Name: COLUMN medical_insurance_settlement.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.mr_no IS '病案号';


--
-- Name: COLUMN medical_insurance_settlement.nationality; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.nationality IS '国籍';


--
-- Name: COLUMN medical_insurance_settlement.occupation_category; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.occupation_category IS '职业类别';


--
-- Name: COLUMN medical_insurance_settlement.currentaddress_province; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.currentaddress_province IS '现住址-省名称';


--
-- Name: COLUMN medical_insurance_settlement.currentaddress_city; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.currentaddress_city IS '现住址-市名称';


--
-- Name: COLUMN medical_insurance_settlement.currentaddress_county; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.currentaddress_county IS '现住址-县名称';


--
-- Name: COLUMN medical_insurance_settlement.currentaddress_town; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.currentaddress_town IS '现住址-镇名称';


--
-- Name: COLUMN medical_insurance_settlement.currentaddress_village; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.currentaddress_village IS '现住址-村名称';


--
-- Name: COLUMN medical_insurance_settlement.currentaddress_detail; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.currentaddress_detail IS '现住址-具体地址';


--
-- Name: COLUMN medical_insurance_settlement.currentaddress; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.currentaddress IS '现住址';


--
-- Name: COLUMN medical_insurance_settlement.currentaddress_postcode; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.currentaddress_postcode IS '现住址邮编';


--
-- Name: COLUMN medical_insurance_settlement.currentaddress_phone; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.currentaddress_phone IS '现住址电话';


--
-- Name: COLUMN medical_insurance_settlement.work_unit; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.work_unit IS '工作单位';


--
-- Name: COLUMN medical_insurance_settlement.workplace_province; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.workplace_province IS '工作单位地址-省名称';


--
-- Name: COLUMN medical_insurance_settlement.workplace_city; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.workplace_city IS '工作单位地址-市名称';


--
-- Name: COLUMN medical_insurance_settlement.workplace_county; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.workplace_county IS '工作单位地址-县名称';


--
-- Name: COLUMN medical_insurance_settlement.workplace_town; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.workplace_town IS '工作单位地址-镇名称';


--
-- Name: COLUMN medical_insurance_settlement.workplace_village; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.workplace_village IS '工作单位地址-村名称';


--
-- Name: COLUMN medical_insurance_settlement.workplace_detail; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.workplace_detail IS '工作单位地址-具体地址';


--
-- Name: COLUMN medical_insurance_settlement.workplace; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.workplace IS '工作单位地址';


--
-- Name: COLUMN medical_insurance_settlement.workplace_postcode; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.workplace_postcode IS '工作单位地址邮编';


--
-- Name: COLUMN medical_insurance_settlement.work_telephone; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.work_telephone IS '工作电话';


--
-- Name: COLUMN medical_insurance_settlement.contact_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.contact_name IS '联系人姓名';


--
-- Name: COLUMN medical_insurance_settlement.contact_relationship; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.contact_relationship IS '联系人关系';


--
-- Name: COLUMN medical_insurance_settlement.contact_address; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.contact_address IS '联系人地址';


--
-- Name: COLUMN medical_insurance_settlement.contact_telephone; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.contact_telephone IS '联系人电话';


--
-- Name: COLUMN medical_insurance_settlement.newborn_admission_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.newborn_admission_type IS '新生儿入院类型';


--
-- Name: COLUMN medical_insurance_settlement.newborn_birthweight; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.newborn_birthweight IS '新生儿出生体重';


--
-- Name: COLUMN medical_insurance_settlement.newborn_admitweigth; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.newborn_admitweigth IS '新生儿入院体重';


--
-- Name: COLUMN medical_insurance_settlement.newborn_birth_weight; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.newborn_birth_weight IS '多新生儿出生体重（克）';


--
-- Name: COLUMN medical_insurance_settlement.newborn_admission_weight; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.newborn_admission_weight IS '多新生儿入院体重（克）';


--
-- Name: COLUMN medical_insurance_settlement.admission_route; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.admission_route IS '入院途径';


--
-- Name: COLUMN medical_insurance_settlement.special_personnel_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.special_personnel_type IS '特殊人员类型';


--
-- Name: COLUMN medical_insurance_settlement.admission_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.admission_datetime IS '入院时间';


--
-- Name: COLUMN medical_insurance_settlement.admission_dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.admission_dept_name IS '入院科室';


--
-- Name: COLUMN medical_insurance_settlement.transfer_dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.transfer_dept_name IS '转科科室';


--
-- Name: COLUMN medical_insurance_settlement.discharge_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.discharge_datetime IS '出院时间';


--
-- Name: COLUMN medical_insurance_settlement.discharge_dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.discharge_dept_name IS '出院科室';


--
-- Name: COLUMN medical_insurance_settlement.leaving_hospital_way; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.leaving_hospital_way IS '离院方式';


--
-- Name: COLUMN medical_insurance_settlement.receiving_institution_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.receiving_institution_name IS '拟接收机构名称';


--
-- Name: COLUMN medical_insurance_settlement.receiving_institution_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.receiving_institution_code IS '拟接收机构代码';


--
-- Name: COLUMN medical_insurance_settlement.rehospital_with_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.rehospital_with_month IS '出院31天内再住院标志';


--
-- Name: COLUMN medical_insurance_settlement.rehospital_with_month_purpose; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.rehospital_with_month_purpose IS '出院31天内再住院目的';


--
-- Name: COLUMN medical_insurance_settlement.insurance_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.insurance_no IS '医保编号';


--
-- Name: COLUMN medical_insurance_settlement.declaration_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.declaration_time IS '申报时间';


--
-- Name: COLUMN medical_insurance_settlement.inpat_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.inpat_type IS '住院医疗类型';


--
-- Name: COLUMN medical_insurance_settlement.therapy_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.therapy_type IS '治疗类别';


--
-- Name: COLUMN medical_insurance_settlement.diagnosis_code_cnt; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.diagnosis_code_cnt IS '诊断代码计数';


--
-- Name: COLUMN medical_insurance_settlement.surgery_code_cnt; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.surgery_code_cnt IS '手术操作代码计数';


--
-- Name: COLUMN medical_insurance_settlement.ventilator_usetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.ventilator_usetime IS '呼吸机使用时间';


--
-- Name: COLUMN medical_insurance_settlement.coma_timebefadm_d; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.coma_timebefadm_d IS '颅脑损伤患者入院前昏迷时间-d';


--
-- Name: COLUMN medical_insurance_settlement.coma_timebefadm_h; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.coma_timebefadm_h IS '颅脑损伤患者入院前昏迷时间-h';


--
-- Name: COLUMN medical_insurance_settlement.coma_timebefadm_min; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.coma_timebefadm_min IS '颅脑损伤患者入院前昏迷时间-min';


--
-- Name: COLUMN medical_insurance_settlement.coma_timeaftadm_d; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.coma_timeaftadm_d IS '颅脑损伤患者入院后昏迷时间-d';


--
-- Name: COLUMN medical_insurance_settlement.coma_timeaftadm_h; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.coma_timeaftadm_h IS '颅脑损伤患者入院后昏迷时间-h';


--
-- Name: COLUMN medical_insurance_settlement.coma_timeaftadm_min; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.coma_timeaftadm_min IS '颅脑损伤患者入院后昏迷时间-min';


--
-- Name: COLUMN medical_insurance_settlement.primary_care_days; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.primary_care_days IS '一级护理天数';


--
-- Name: COLUMN medical_insurance_settlement.secondary_care_days; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.secondary_care_days IS '二级护理天数';


--
-- Name: COLUMN medical_insurance_settlement.tertiary_care_days; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.tertiary_care_days IS '三级护理天数';


--
-- Name: COLUMN medical_insurance_settlement.intensive_care_days; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.intensive_care_days IS '特级护理天数';


--
-- Name: COLUMN medical_insurance_settlement.insured_place; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.insured_place IS '参保地';


--
-- Name: COLUMN medical_insurance_settlement.out_of_pocket_advance; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.out_of_pocket_advance IS '个人自付';


--
-- Name: COLUMN medical_insurance_settlement.out_of_pocket_amount; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.out_of_pocket_amount IS '个人自费';


--
-- Name: COLUMN medical_insurance_settlement.personal_account_expend; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.personal_account_expend IS '个人账户支付';


--
-- Name: COLUMN medical_insurance_settlement.cash_payment_amount; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.cash_payment_amount IS '个人现金支付';


--
-- Name: COLUMN medical_insurance_settlement.insurance_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.insurance_type IS '医保支付方式';


--
-- Name: COLUMN medical_insurance_settlement.medical_insurance_institution; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.medical_insurance_institution IS '医保机构';


--
-- Name: COLUMN medical_insurance_settlement.medical_insurance_agent; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.medical_insurance_agent IS '医保机构经办人';


--
-- Name: COLUMN medical_insurance_settlement.medical_insurance_agent_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.medical_insurance_agent_code IS '医保机构经办人员编码';


--
-- Name: COLUMN medical_insurance_settlement.outp_chronic_department; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.outp_chronic_department IS '门诊慢特病诊断科别';


--
-- Name: COLUMN medical_insurance_settlement.outp_chronic_date; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.outp_chronic_date IS '门诊慢特病就诊日期';


--
-- Name: COLUMN medical_insurance_settlement.attending_physician_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.attending_physician_code IS '主诊医师代码';


--
-- Name: COLUMN medical_insurance_settlement.responsible_nurse_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.responsible_nurse_code IS '责任护士代码';


--
-- Name: COLUMN medical_insurance_settlement.settlement_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.settlement_status IS '状态分类';


--
-- Name: COLUMN medical_insurance_settlement.start_date; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.start_date IS '结算开始日期';


--
-- Name: COLUMN medical_insurance_settlement.end_date; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.end_date IS '结算结束日期';


--
-- Name: COLUMN medical_insurance_settlement.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.last_modifier IS '最新修改人';


--
-- Name: COLUMN medical_insurance_settlement.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN medical_insurance_settlement.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN medical_insurance_settlement.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement.update_time IS '数据更新时间，用于增量同步';


--
-- Name: medical_insurance_settlement_cost; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.medical_insurance_settlement_cost (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    document_id character varying(100),
    medinsur_serial_no character varying(100),
    medinsur_serial_item_id character varying(100) CONSTRAINT medical_insurance_settlement_c_medinsur_serial_item_id_not_null NOT NULL,
    charge character varying(100),
    type_of_medicalcharge character varying(100),
    charge_item_level character varying(100),
    item_class_a_amount character varying(100),
    item_class_b_amount character varying(100),
    item_own_pay_amount character varying(100),
    item_other_amount character varying(100),
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN medical_insurance_settlement_cost.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.institute_id IS '机构号';


--
-- Name: COLUMN medical_insurance_settlement_cost.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.patient_id IS '患者号';


--
-- Name: COLUMN medical_insurance_settlement_cost.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.visit_id IS '就诊号';


--
-- Name: COLUMN medical_insurance_settlement_cost.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.visit_type IS '就诊类型';


--
-- Name: COLUMN medical_insurance_settlement_cost.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.document_id IS '文档编号';


--
-- Name: COLUMN medical_insurance_settlement_cost.medinsur_serial_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.medinsur_serial_no IS '清单流水号';


--
-- Name: COLUMN medical_insurance_settlement_cost.medinsur_serial_item_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.medinsur_serial_item_id IS '清单费用明细号';


--
-- Name: COLUMN medical_insurance_settlement_cost.charge; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.charge IS '实收金额';


--
-- Name: COLUMN medical_insurance_settlement_cost.type_of_medicalcharge; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.type_of_medicalcharge IS '医疗收费项目类别';


--
-- Name: COLUMN medical_insurance_settlement_cost.charge_item_level; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.charge_item_level IS '收费项目等级';


--
-- Name: COLUMN medical_insurance_settlement_cost.item_class_a_amount; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.item_class_a_amount IS '甲类金额';


--
-- Name: COLUMN medical_insurance_settlement_cost.item_class_b_amount; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.item_class_b_amount IS '乙类金额';


--
-- Name: COLUMN medical_insurance_settlement_cost.item_own_pay_amount; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.item_own_pay_amount IS '自费金额';


--
-- Name: COLUMN medical_insurance_settlement_cost.item_other_amount; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.item_other_amount IS '其他金额';


--
-- Name: COLUMN medical_insurance_settlement_cost.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.last_modifier IS '最新修改人';


--
-- Name: COLUMN medical_insurance_settlement_cost.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN medical_insurance_settlement_cost.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN medical_insurance_settlement_cost.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medical_insurance_settlement_cost.update_time IS '数据更新时间，用于增量同步';


--
-- Name: medinsur_receipt; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.medinsur_receipt (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    medinsur_receipt_id character varying(100) NOT NULL,
    outpat_no character varying(100),
    inpat_no character varying(100),
    name character varying(100),
    sex character varying(100),
    ethnicity character varying(100),
    birthday date,
    age_year character varying(100),
    insurance_type character varying(100),
    insurance_no character varying(100),
    settlement_method character varying(100),
    total_charge character varying(100),
    personnel_payment character varying(100),
    fund_payment_amount character varying(100),
    personal_account_expend character varying(100),
    cash_payment_amount character varying(100),
    start_date timestamp without time zone,
    end_date timestamp without time zone,
    settle_datetime timestamp without time zone,
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN medinsur_receipt.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.institute_id IS '机构号';


--
-- Name: COLUMN medinsur_receipt.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.patient_id IS '患者号';


--
-- Name: COLUMN medinsur_receipt.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.visit_id IS '就诊号';


--
-- Name: COLUMN medinsur_receipt.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.visit_type IS '就诊类型';


--
-- Name: COLUMN medinsur_receipt.medinsur_receipt_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.medinsur_receipt_id IS '医保结算号';


--
-- Name: COLUMN medinsur_receipt.outpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.outpat_no IS '门急诊号';


--
-- Name: COLUMN medinsur_receipt.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.inpat_no IS '住院号';


--
-- Name: COLUMN medinsur_receipt.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.name IS '患者姓名';


--
-- Name: COLUMN medinsur_receipt.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.sex IS '患者性别';


--
-- Name: COLUMN medinsur_receipt.ethnicity; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.ethnicity IS '民族';


--
-- Name: COLUMN medinsur_receipt.birthday; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.birthday IS '出生日期';


--
-- Name: COLUMN medinsur_receipt.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.age_year IS '年龄(年)';


--
-- Name: COLUMN medinsur_receipt.insurance_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.insurance_type IS '医保类别';


--
-- Name: COLUMN medinsur_receipt.insurance_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.insurance_no IS '医保号';


--
-- Name: COLUMN medinsur_receipt.settlement_method; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.settlement_method IS '清算方式';


--
-- Name: COLUMN medinsur_receipt.total_charge; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.total_charge IS '医疗费用总额';


--
-- Name: COLUMN medinsur_receipt.personnel_payment; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.personnel_payment IS '个人支付金额';


--
-- Name: COLUMN medinsur_receipt.fund_payment_amount; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.fund_payment_amount IS '基金支付金额';


--
-- Name: COLUMN medinsur_receipt.personal_account_expend; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.personal_account_expend IS '个人账户支出';


--
-- Name: COLUMN medinsur_receipt.cash_payment_amount; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.cash_payment_amount IS '现金支付金额';


--
-- Name: COLUMN medinsur_receipt.start_date; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.start_date IS '开始日期';


--
-- Name: COLUMN medinsur_receipt.end_date; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.end_date IS '结束日期';


--
-- Name: COLUMN medinsur_receipt.settle_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.settle_datetime IS '结算时间';


--
-- Name: COLUMN medinsur_receipt.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.record_content IS '记录内容';


--
-- Name: COLUMN medinsur_receipt.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.last_modifier IS '最新修改人';


--
-- Name: COLUMN medinsur_receipt.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN medinsur_receipt.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN medinsur_receipt.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.medinsur_receipt.update_time IS '数据更新时间，用于增量同步';


--
-- Name: mr; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.mr (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    document_id character varying(100),
    institute_code character varying(100),
    institute_county_desc character varying(100),
    medical_payment_method character varying(100),
    insurance_type character varying(100),
    insurance_no character varying(100),
    visit_cnt character varying(100),
    id_card_type character varying(100),
    id_card_no character varying(100),
    birthday date,
    nationality character varying(100),
    ethnicity character varying(100),
    marital_status character varying(100),
    occupation_category character varying(100),
    nativeplace text,
    currentaddress text,
    contact_number character varying(100),
    contact_name character varying(100),
    contact_relationship character varying(100),
    contact_address character varying(100),
    contact_telephone character varying(100),
    work_unit character varying(100),
    admission_route character varying(100),
    admission_datetime timestamp without time zone,
    admission_condition character varying(100),
    admission_dept_name character varying(100),
    admission_ward_name character varying(100),
    diagnosis_date date,
    transfer_dept_name character varying(100),
    discharge_datetime timestamp without time zone,
    discharge_dept_name character varying(100),
    discharge_ward_name character varying(100),
    hospital_duration character varying(100),
    pathology_id character varying(100),
    allergy_sign character varying(100),
    allergy_history character varying(100),
    abo_blood_code character varying(100),
    rh_blood_code character varying(100),
    death_autopsy_sign character varying(100),
    deptdirector_sign character varying(100),
    chief_physician_sign character varying(100),
    attending_physician_sign character varying(100),
    resident_physician_sign character varying(100),
    responsible_nurse_sign character varying(100),
    coder_sign character varying(100),
    "QC_physician_sign" character varying(100),
    "QC_nurse_sign" character varying(100),
    "QC_date" date,
    medicalrecord_quality character varying(100),
    leaving_hospital_way character varying(100),
    planned_transder_to character varying(100),
    rehospital_with_month character varying(100),
    rehospital_with_month_purpose character varying(100),
    rbc character varying(100),
    platet_volume character varying(100),
    plasma_volume character varying(100),
    whole_blood_volume character varying(100),
    autoblood_trans character varying(100),
    clinical_pathway character varying(100),
    archive_sign character varying(100),
    mr_datetime timestamp without time zone,
    local_sync_completed_at timestamp without time zone,
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN mr.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.institute_id IS '机构号';


--
-- Name: COLUMN mr.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.patient_id IS '患者号';


--
-- Name: COLUMN mr.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.visit_id IS '就诊号';


--
-- Name: COLUMN mr.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.visit_type IS '就诊类型';


--
-- Name: COLUMN mr.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.document_id IS '文档编号';


--
-- Name: COLUMN mr.institute_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.institute_code IS '医疗机构组织机构代码';


--
-- Name: COLUMN mr.institute_county_desc; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.institute_county_desc IS '医疗机构名称';


--
-- Name: COLUMN mr.medical_payment_method; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.medical_payment_method IS '医疗付费方式';


--
-- Name: COLUMN mr.insurance_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.insurance_type IS '医保类别';


--
-- Name: COLUMN mr.insurance_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.insurance_no IS '医保号';


--
-- Name: COLUMN mr.visit_cnt; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.visit_cnt IS '就诊次数';


--
-- Name: COLUMN mr.id_card_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.id_card_type IS '身份证件类别';


--
-- Name: COLUMN mr.id_card_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.id_card_no IS '身份证件号码';


--
-- Name: COLUMN mr.birthday; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.birthday IS '出生日期';


--
-- Name: COLUMN mr.nationality; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.nationality IS '国籍';


--
-- Name: COLUMN mr.ethnicity; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.ethnicity IS '民族';


--
-- Name: COLUMN mr.marital_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.marital_status IS '婚姻状况';


--
-- Name: COLUMN mr.occupation_category; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.occupation_category IS '职业类别';


--
-- Name: COLUMN mr.nativeplace; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.nativeplace IS '籍贯地址';


--
-- Name: COLUMN mr.currentaddress; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.currentaddress IS '现住址';


--
-- Name: COLUMN mr.contact_number; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.contact_number IS '联系电话';


--
-- Name: COLUMN mr.contact_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.contact_name IS '联系人姓名';


--
-- Name: COLUMN mr.contact_relationship; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.contact_relationship IS '联系人关系';


--
-- Name: COLUMN mr.contact_address; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.contact_address IS '联系人地址';


--
-- Name: COLUMN mr.contact_telephone; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.contact_telephone IS '联系人电话';


--
-- Name: COLUMN mr.work_unit; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.work_unit IS '工作单位';


--
-- Name: COLUMN mr.admission_route; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.admission_route IS '入院途径';


--
-- Name: COLUMN mr.admission_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.admission_datetime IS '入院时间';


--
-- Name: COLUMN mr.admission_condition; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.admission_condition IS '入院情况';


--
-- Name: COLUMN mr.admission_dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.admission_dept_name IS '入院科室';


--
-- Name: COLUMN mr.admission_ward_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.admission_ward_name IS '入院病房';


--
-- Name: COLUMN mr.diagnosis_date; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.diagnosis_date IS '入院后确诊日期';


--
-- Name: COLUMN mr.transfer_dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.transfer_dept_name IS '转科科室';


--
-- Name: COLUMN mr.discharge_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.discharge_datetime IS '出院时间';


--
-- Name: COLUMN mr.discharge_dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.discharge_dept_name IS '出院科室';


--
-- Name: COLUMN mr.discharge_ward_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.discharge_ward_name IS '出院病房';


--
-- Name: COLUMN mr.hospital_duration; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.hospital_duration IS '实际住院天数';


--
-- Name: COLUMN mr.pathology_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.pathology_id IS '病理号';


--
-- Name: COLUMN mr.allergy_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.allergy_sign IS '过敏史标志';


--
-- Name: COLUMN mr.allergy_history; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.allergy_history IS '过敏史';


--
-- Name: COLUMN mr.abo_blood_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.abo_blood_code IS 'ABO血型';


--
-- Name: COLUMN mr.rh_blood_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.rh_blood_code IS 'Rh血型';


--
-- Name: COLUMN mr.death_autopsy_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.death_autopsy_sign IS '死亡患者尸检标志';


--
-- Name: COLUMN mr.deptdirector_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.deptdirector_sign IS '科主任签名';


--
-- Name: COLUMN mr.chief_physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.chief_physician_sign IS '主副主任医师签名';


--
-- Name: COLUMN mr.attending_physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.attending_physician_sign IS '主治医师签名';


--
-- Name: COLUMN mr.resident_physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.resident_physician_sign IS '住院医师签名';


--
-- Name: COLUMN mr.responsible_nurse_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.responsible_nurse_sign IS '责任护士签名';


--
-- Name: COLUMN mr.coder_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.coder_sign IS '编码员签名';


--
-- Name: COLUMN mr."QC_physician_sign"; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr."QC_physician_sign" IS '质控医师签名';


--
-- Name: COLUMN mr."QC_nurse_sign"; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr."QC_nurse_sign" IS '质控护士签名';


--
-- Name: COLUMN mr."QC_date"; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr."QC_date" IS '质控日期';


--
-- Name: COLUMN mr.medicalrecord_quality; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.medicalrecord_quality IS '病案质量';


--
-- Name: COLUMN mr.leaving_hospital_way; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.leaving_hospital_way IS '离院方式';


--
-- Name: COLUMN mr.planned_transder_to; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.planned_transder_to IS '拟接受医疗机构名称';


--
-- Name: COLUMN mr.rehospital_with_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.rehospital_with_month IS '出院31天内再住院标志';


--
-- Name: COLUMN mr.rehospital_with_month_purpose; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.rehospital_with_month_purpose IS '出院31天内再住院目的';


--
-- Name: COLUMN mr.rbc; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.rbc IS '红细胞';


--
-- Name: COLUMN mr.platet_volume; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.platet_volume IS '血小板';


--
-- Name: COLUMN mr.plasma_volume; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.plasma_volume IS '血浆';


--
-- Name: COLUMN mr.whole_blood_volume; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.whole_blood_volume IS '全血';


--
-- Name: COLUMN mr.autoblood_trans; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.autoblood_trans IS '自体血回输';


--
-- Name: COLUMN mr.clinical_pathway; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.clinical_pathway IS '临床路径';


--
-- Name: COLUMN mr.archive_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.archive_sign IS '归档标志';


--
-- Name: COLUMN mr.mr_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.mr_datetime IS '病案提交时间';


--
-- Name: COLUMN mr.local_sync_completed_at; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.local_sync_completed_at IS '本地完整同步完成时间';


--
-- Name: COLUMN mr.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.record_content IS '非结构化全文';


--
-- Name: COLUMN mr.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.last_modifier IS '最新修改人';


--
-- Name: COLUMN mr.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN mr.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN mr.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN mr.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.inpat_no IS '住院号';


--
-- Name: COLUMN mr.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.mr_no IS '病案号';


--
-- Name: COLUMN mr.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.name IS '患者姓名';


--
-- Name: COLUMN mr.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.sex IS '患者性别';


--
-- Name: COLUMN mr.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.age_year IS '年龄(年)';


--
-- Name: COLUMN mr.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.age_month IS '年龄(月)';


--
-- Name: COLUMN mr.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr.age IS '年龄-非结构化';


--
-- Name: mr_bloodtrans; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.mr_bloodtrans (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    document_id character varying(100),
    bloodtrans_id character varying(100) NOT NULL,
    inpat_no character varying(100),
    mr_no character varying(100),
    transfuse_variety character varying(100),
    bloodbag_id character varying(100),
    blood_transfusion_volume character varying(100),
    blood_transfusion_unit character varying(100),
    transblood_reaction_sign character varying(100),
    transblood_reaction_type character varying(100),
    transfution_datetime timestamp without time zone,
    transfusion_reason character varying(100),
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN mr_bloodtrans.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.institute_id IS '机构号';


--
-- Name: COLUMN mr_bloodtrans.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.patient_id IS '患者号';


--
-- Name: COLUMN mr_bloodtrans.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.visit_id IS '就诊号';


--
-- Name: COLUMN mr_bloodtrans.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.visit_type IS '就诊类型';


--
-- Name: COLUMN mr_bloodtrans.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.document_id IS '文档编号';


--
-- Name: COLUMN mr_bloodtrans.bloodtrans_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.bloodtrans_id IS '输血记录号';


--
-- Name: COLUMN mr_bloodtrans.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.inpat_no IS '住院号';


--
-- Name: COLUMN mr_bloodtrans.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.mr_no IS '病案号';


--
-- Name: COLUMN mr_bloodtrans.transfuse_variety; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.transfuse_variety IS '输血品种';


--
-- Name: COLUMN mr_bloodtrans.bloodbag_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.bloodbag_id IS '血袋编码';


--
-- Name: COLUMN mr_bloodtrans.blood_transfusion_volume; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.blood_transfusion_volume IS '输血剂量';


--
-- Name: COLUMN mr_bloodtrans.blood_transfusion_unit; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.blood_transfusion_unit IS '输血量计量单位';


--
-- Name: COLUMN mr_bloodtrans.transblood_reaction_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.transblood_reaction_sign IS '输血反应标志';


--
-- Name: COLUMN mr_bloodtrans.transblood_reaction_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.transblood_reaction_type IS '输血反应类型';


--
-- Name: COLUMN mr_bloodtrans.transfution_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.transfution_datetime IS '输血时间';


--
-- Name: COLUMN mr_bloodtrans.transfusion_reason; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.transfusion_reason IS '输血原因';


--
-- Name: COLUMN mr_bloodtrans.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.last_modifier IS '最新修改人';


--
-- Name: COLUMN mr_bloodtrans.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN mr_bloodtrans.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN mr_bloodtrans.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_bloodtrans.update_time IS '数据更新时间，用于增量同步';


--
-- Name: mr_cost; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.mr_cost (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    document_id character varying(100),
    inpat_no character varying(100),
    mr_no character varying(100),
    total_cost character varying(100),
    self_pay character varying(100),
    general_medical_service_fee character varying(100),
    general_treatment_fee character varying(100),
    nursing_care_fee character varying(100),
    other_service_fee character varying(100),
    pathological_diagnostic_fee character varying(100),
    laboratory_diagnostic_fee character varying(100),
    imaging_diagnostic_fee character varying(100),
    clinical_diagnostic_fee character varying(100),
    nonsurgical_treatment_fee character varying(100),
    clinical_physical_therapy_fee character varying(100),
    surgery_treatment_fee character varying(100),
    anesthesia_fee character varying(100),
    surgery_fee character varying(100),
    rehabilitation_fee character varying(100),
    western_medicine_fee character varying(100),
    antibacterial_drug_fee character varying(100),
    chinese_patent_medcine_fee character varying(100),
    chinese_herbal_medicine_fee character varying(100),
    blood_fee character varying(100),
    treat_disposable_mat_fee character varying(100),
    exam_disposable_mat_fee character varying(100),
    surgery_disposable_mat_fee character varying(100),
    other_fee character varying(100),
    settle_datetime timestamp without time zone,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN mr_cost.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.institute_id IS '机构号';


--
-- Name: COLUMN mr_cost.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.patient_id IS '患者号';


--
-- Name: COLUMN mr_cost.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.visit_id IS '就诊号';


--
-- Name: COLUMN mr_cost.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.visit_type IS '就诊类型';


--
-- Name: COLUMN mr_cost.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.document_id IS '文档编号';


--
-- Name: COLUMN mr_cost.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.inpat_no IS '住院号';


--
-- Name: COLUMN mr_cost.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.mr_no IS '病案号';


--
-- Name: COLUMN mr_cost.total_cost; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.total_cost IS '应收总费用';


--
-- Name: COLUMN mr_cost.self_pay; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.self_pay IS '自付金额';


--
-- Name: COLUMN mr_cost.general_medical_service_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.general_medical_service_fee IS '一般医疗服务费';


--
-- Name: COLUMN mr_cost.general_treatment_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.general_treatment_fee IS '一般治疗操作费';


--
-- Name: COLUMN mr_cost.nursing_care_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.nursing_care_fee IS '护理费';


--
-- Name: COLUMN mr_cost.other_service_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.other_service_fee IS '其它服务费用';


--
-- Name: COLUMN mr_cost.pathological_diagnostic_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.pathological_diagnostic_fee IS '病理诊断费用';


--
-- Name: COLUMN mr_cost.laboratory_diagnostic_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.laboratory_diagnostic_fee IS '实验室诊断费';


--
-- Name: COLUMN mr_cost.imaging_diagnostic_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.imaging_diagnostic_fee IS '影像学诊断费';


--
-- Name: COLUMN mr_cost.clinical_diagnostic_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.clinical_diagnostic_fee IS '临床诊断费';


--
-- Name: COLUMN mr_cost.nonsurgical_treatment_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.nonsurgical_treatment_fee IS '非手术治疗项目费';


--
-- Name: COLUMN mr_cost.clinical_physical_therapy_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.clinical_physical_therapy_fee IS '临床物理治疗费';


--
-- Name: COLUMN mr_cost.surgery_treatment_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.surgery_treatment_fee IS '手术治疗费';


--
-- Name: COLUMN mr_cost.anesthesia_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.anesthesia_fee IS '麻醉费';


--
-- Name: COLUMN mr_cost.surgery_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.surgery_fee IS '手术费';


--
-- Name: COLUMN mr_cost.rehabilitation_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.rehabilitation_fee IS '康复费';


--
-- Name: COLUMN mr_cost.western_medicine_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.western_medicine_fee IS '西药费';


--
-- Name: COLUMN mr_cost.antibacterial_drug_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.antibacterial_drug_fee IS '抗菌药物费用';


--
-- Name: COLUMN mr_cost.chinese_patent_medcine_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.chinese_patent_medcine_fee IS '中成药费';


--
-- Name: COLUMN mr_cost.chinese_herbal_medicine_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.chinese_herbal_medicine_fee IS '中草药费';


--
-- Name: COLUMN mr_cost.blood_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.blood_fee IS '血费';


--
-- Name: COLUMN mr_cost.treat_disposable_mat_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.treat_disposable_mat_fee IS '治疗一次性医用材料费';


--
-- Name: COLUMN mr_cost.exam_disposable_mat_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.exam_disposable_mat_fee IS '检查一次性医用材料费';


--
-- Name: COLUMN mr_cost.surgery_disposable_mat_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.surgery_disposable_mat_fee IS '手术一次性医用材料费';


--
-- Name: COLUMN mr_cost.other_fee; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.other_fee IS '其它费用';


--
-- Name: COLUMN mr_cost.settle_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.settle_datetime IS '结算时间';


--
-- Name: COLUMN mr_cost.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.last_modifier IS '最新修改人';


--
-- Name: COLUMN mr_cost.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN mr_cost.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN mr_cost.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_cost.update_time IS '数据更新时间，用于增量同步';


--
-- Name: mr_customize; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.mr_customize (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    document_id character varying(100),
    mr_no character varying(100),
    "T_stage" character varying(100),
    "N_stage" character varying(100),
    "M_stage" character varying(100),
    tumor_stage character varying(100),
    transferin_org_name character varying(100),
    discharge_condition character varying(100),
    living_ability_admission_score character varying(100),
    living_ability_discharge_score character varying(100),
    rescue_no character varying(100),
    rescue_success_no character varying(100),
    criticalcare_record_sign character varying(100),
    difficult_record_sign character varying(100),
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN mr_customize.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.institute_id IS '机构号';


--
-- Name: COLUMN mr_customize.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.patient_id IS '患者号';


--
-- Name: COLUMN mr_customize.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.visit_id IS '就诊号';


--
-- Name: COLUMN mr_customize.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.visit_type IS '就诊类型';


--
-- Name: COLUMN mr_customize.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.document_id IS '文档编号';


--
-- Name: COLUMN mr_customize.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.mr_no IS '病案号';


--
-- Name: COLUMN mr_customize."T_stage"; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize."T_stage" IS 'T分期';


--
-- Name: COLUMN mr_customize."N_stage"; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize."N_stage" IS 'N分期';


--
-- Name: COLUMN mr_customize."M_stage"; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize."M_stage" IS 'M分期';


--
-- Name: COLUMN mr_customize.tumor_stage; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.tumor_stage IS '肿瘤分期';


--
-- Name: COLUMN mr_customize.transferin_org_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.transferin_org_name IS '转入医疗机构名称';


--
-- Name: COLUMN mr_customize.discharge_condition; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.discharge_condition IS '出院情况';


--
-- Name: COLUMN mr_customize.living_ability_admission_score; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.living_ability_admission_score IS '生活能力评定量表评分-入院';


--
-- Name: COLUMN mr_customize.living_ability_discharge_score; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.living_ability_discharge_score IS '生活能力评定量表评分-出院';


--
-- Name: COLUMN mr_customize.rescue_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.rescue_no IS '抢救次数';


--
-- Name: COLUMN mr_customize.rescue_success_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.rescue_success_no IS '抢救成功次数';


--
-- Name: COLUMN mr_customize.criticalcare_record_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.criticalcare_record_sign IS '危重病历标志';


--
-- Name: COLUMN mr_customize.difficult_record_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.difficult_record_sign IS '疑难病历标志';


--
-- Name: COLUMN mr_customize.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.last_modifier IS '最新修改人';


--
-- Name: COLUMN mr_customize.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN mr_customize.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN mr_customize.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_customize.update_time IS '数据更新时间，用于增量同步';


--
-- Name: mr_icu; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.mr_icu (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    document_id character varying(100),
    icu_id character varying(100) NOT NULL,
    inpat_no character varying(100),
    mr_no character varying(100),
    icu_type character varying(100),
    icu_name character varying(100),
    icu_start_datetime timestamp without time zone,
    icu_end_datetime timestamp without time zone,
    icu_period character varying(100),
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN mr_icu.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.institute_id IS '机构号';


--
-- Name: COLUMN mr_icu.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.patient_id IS '患者号';


--
-- Name: COLUMN mr_icu.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.visit_id IS '就诊号';


--
-- Name: COLUMN mr_icu.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.visit_type IS '就诊类型';


--
-- Name: COLUMN mr_icu.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.document_id IS '文档编号';


--
-- Name: COLUMN mr_icu.icu_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.icu_id IS '重症监护记录号';


--
-- Name: COLUMN mr_icu.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.inpat_no IS '住院号';


--
-- Name: COLUMN mr_icu.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.mr_no IS '病案号';


--
-- Name: COLUMN mr_icu.icu_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.icu_type IS '重症监护室病房类型';


--
-- Name: COLUMN mr_icu.icu_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.icu_name IS '重症监护室名称';


--
-- Name: COLUMN mr_icu.icu_start_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.icu_start_datetime IS '进重症监护室时间';


--
-- Name: COLUMN mr_icu.icu_end_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.icu_end_datetime IS '出重症监护室时间';


--
-- Name: COLUMN mr_icu.icu_period; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.icu_period IS '时间合计';


--
-- Name: COLUMN mr_icu.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.last_modifier IS '最新修改人';


--
-- Name: COLUMN mr_icu.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN mr_icu.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN mr_icu.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_icu.update_time IS '数据更新时间，用于增量同步';


--
-- Name: mr_surgery; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.mr_surgery (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    document_id character varying(100),
    surgery_id character varying(100) NOT NULL,
    inpat_no character varying(100),
    mr_no character varying(100),
    surgery_name character varying(100),
    surgery_code character varying(100),
    surgical_level character varying(100),
    surgial_incision_level character varying(100),
    surgical_incisionheal_level character varying(100),
    anesthesia_method character varying(100),
    anesthesia_level character varying(100),
    surgery_begin_datetime timestamp without time zone,
    surgery_end_datetime timestamp without time zone,
    surgery_duration character varying(100),
    surgeon character varying(100),
    surgeon_physician_code character varying(100),
    first_assistant character varying(100),
    second_assistant character varying(100),
    anesthesiologist character varying(100),
    anesthesiologist_code character varying(100),
    main_surgery_sign character varying(100),
    unplanned_reoperation character varying(100),
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN mr_surgery.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.institute_id IS '机构号';


--
-- Name: COLUMN mr_surgery.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.patient_id IS '患者号';


--
-- Name: COLUMN mr_surgery.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.visit_id IS '就诊号';


--
-- Name: COLUMN mr_surgery.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.visit_type IS '就诊类型';


--
-- Name: COLUMN mr_surgery.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.document_id IS '文档编号';


--
-- Name: COLUMN mr_surgery.surgery_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.surgery_id IS '手术操作记录号';


--
-- Name: COLUMN mr_surgery.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.inpat_no IS '住院号';


--
-- Name: COLUMN mr_surgery.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.mr_no IS '病案号';


--
-- Name: COLUMN mr_surgery.surgery_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.surgery_name IS '手术操作名称';


--
-- Name: COLUMN mr_surgery.surgery_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.surgery_code IS '手术操作编码(ICD-9-CM-3)';


--
-- Name: COLUMN mr_surgery.surgical_level; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.surgical_level IS '手术级别';


--
-- Name: COLUMN mr_surgery.surgial_incision_level; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.surgial_incision_level IS '手术切口分级';


--
-- Name: COLUMN mr_surgery.surgical_incisionheal_level; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.surgical_incisionheal_level IS '手术切口愈合分级';


--
-- Name: COLUMN mr_surgery.anesthesia_method; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.anesthesia_method IS '麻醉方法';


--
-- Name: COLUMN mr_surgery.anesthesia_level; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.anesthesia_level IS '麻醉分级(ASA)';


--
-- Name: COLUMN mr_surgery.surgery_begin_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.surgery_begin_datetime IS '手术开始时间';


--
-- Name: COLUMN mr_surgery.surgery_end_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.surgery_end_datetime IS '手术结束时间';


--
-- Name: COLUMN mr_surgery.surgery_duration; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.surgery_duration IS '手术持续时间';


--
-- Name: COLUMN mr_surgery.surgeon; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.surgeon IS '手术医师姓名';


--
-- Name: COLUMN mr_surgery.surgeon_physician_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.surgeon_physician_code IS '术者医师代码';


--
-- Name: COLUMN mr_surgery.first_assistant; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.first_assistant IS '手术助手1';


--
-- Name: COLUMN mr_surgery.second_assistant; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.second_assistant IS '手术助手2';


--
-- Name: COLUMN mr_surgery.anesthesiologist; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.anesthesiologist IS '麻醉医师姓名';


--
-- Name: COLUMN mr_surgery.anesthesiologist_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.anesthesiologist_code IS '麻醉医师代码';


--
-- Name: COLUMN mr_surgery.main_surgery_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.main_surgery_sign IS '主要手术操作标志';


--
-- Name: COLUMN mr_surgery.unplanned_reoperation; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.unplanned_reoperation IS '非计划的再次手术';


--
-- Name: COLUMN mr_surgery.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.last_modifier IS '最新修改人';


--
-- Name: COLUMN mr_surgery.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN mr_surgery.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN mr_surgery.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.mr_surgery.update_time IS '数据更新时间，用于增量同步';


--
-- Name: newborn_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.newborn_record (
    record_datetime timestamp without time zone,
    pregnant_weeks text,
    delivery_method text,
    infant_sex text,
    birthday text,
    birthweight text,
    birthheight text,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN newborn_record.record_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.record_datetime IS 'Caché源字段 record_datetime，原值语义保留';


--
-- Name: COLUMN newborn_record.pregnant_weeks; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.pregnant_weeks IS 'Caché源字段 pregnant_weeks，原值语义保留';


--
-- Name: COLUMN newborn_record.delivery_method; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.delivery_method IS 'Caché源字段 delivery_method，原值语义保留';


--
-- Name: COLUMN newborn_record.infant_sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.infant_sex IS 'Caché源字段 infant_sex，原值语义保留';


--
-- Name: COLUMN newborn_record.birthday; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.birthday IS 'Caché源字段 birthday，原值语义保留';


--
-- Name: COLUMN newborn_record.birthweight; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.birthweight IS 'Caché源字段 birthweight，原值语义保留';


--
-- Name: COLUMN newborn_record.birthheight; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.birthheight IS 'Caché源字段 birthheight，原值语义保留';


--
-- Name: COLUMN newborn_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.institute_id IS '机构号';


--
-- Name: COLUMN newborn_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.patient_id IS '患者号';


--
-- Name: COLUMN newborn_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.visit_id IS '就诊号';


--
-- Name: COLUMN newborn_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.document_id IS '文档编号';


--
-- Name: COLUMN newborn_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.visit_type IS '就诊类型';


--
-- Name: COLUMN newborn_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.record_content IS '非结构化全文';


--
-- Name: COLUMN newborn_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN newborn_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN newborn_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN newborn_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN newborn_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.document_title IS '文档标题';


--
-- Name: COLUMN newborn_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.document_status IS '文档状态';


--
-- Name: COLUMN newborn_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.submitter IS '文档提交人';


--
-- Name: COLUMN newborn_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN newborn_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN newborn_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.inpat_no IS '住院号';


--
-- Name: COLUMN newborn_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.mr_no IS '病案号';


--
-- Name: COLUMN newborn_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.name IS '患者姓名';


--
-- Name: COLUMN newborn_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.sex IS '患者性别';


--
-- Name: COLUMN newborn_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.age_year IS '年龄(年)';


--
-- Name: COLUMN newborn_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.age_month IS '年龄(月)';


--
-- Name: COLUMN newborn_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.newborn_record.age IS '年龄-非结构化';


--
-- Name: nursing_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.nursing_record (
    nurse_sign text,
    nurse_sign_datetime timestamp with time zone,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN nursing_record.nurse_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.nurse_sign IS '源护理签署原值，不从提交人推断';


--
-- Name: COLUMN nursing_record.nurse_sign_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.nurse_sign_datetime IS 'Caché源字段 nurse_sign_datetime，独立保留原始语义';


--
-- Name: COLUMN nursing_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.institute_id IS '机构号';


--
-- Name: COLUMN nursing_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.patient_id IS '患者号';


--
-- Name: COLUMN nursing_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.visit_id IS '就诊号';


--
-- Name: COLUMN nursing_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.document_id IS '文档编号';


--
-- Name: COLUMN nursing_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.visit_type IS '就诊类型';


--
-- Name: COLUMN nursing_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.record_content IS '非结构化全文';


--
-- Name: COLUMN nursing_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN nursing_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN nursing_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN nursing_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN nursing_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.document_title IS '文档标题';


--
-- Name: COLUMN nursing_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.document_status IS '文档状态';


--
-- Name: COLUMN nursing_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.submitter IS '文档提交人';


--
-- Name: COLUMN nursing_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN nursing_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN nursing_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.inpat_no IS '住院号';


--
-- Name: COLUMN nursing_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.mr_no IS '病案号';


--
-- Name: COLUMN nursing_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.name IS '患者姓名';


--
-- Name: COLUMN nursing_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.sex IS '患者性别';


--
-- Name: COLUMN nursing_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.age_year IS '年龄(年)';


--
-- Name: COLUMN nursing_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.age_month IS '年龄(月)';


--
-- Name: COLUMN nursing_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.nursing_record.age IS '年龄-非结构化';


--
-- Name: outpat_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.outpat_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    dept_name character varying(100),
    outpat_no character varying(100),
    visit_datetime timestamp without time zone,
    chief_complaint text,
    history_of_present_illness text,
    past_history text,
    checkup text,
    assist_exam text,
    treatment_advice character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN outpat_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.institute_id IS '机构号';


--
-- Name: COLUMN outpat_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.patient_id IS '患者号';


--
-- Name: COLUMN outpat_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.visit_id IS '就诊号';


--
-- Name: COLUMN outpat_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.document_id IS '文档编号';


--
-- Name: COLUMN outpat_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.visit_type IS '就诊类型';


--
-- Name: COLUMN outpat_record.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.dept_name IS '科室名称';


--
-- Name: COLUMN outpat_record.outpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.outpat_no IS '门急诊号';


--
-- Name: COLUMN outpat_record.visit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.visit_datetime IS '就诊时间';


--
-- Name: COLUMN outpat_record.chief_complaint; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.chief_complaint IS '主诉';


--
-- Name: COLUMN outpat_record.history_of_present_illness; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.history_of_present_illness IS '现病史';


--
-- Name: COLUMN outpat_record.past_history; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.past_history IS '既往史';


--
-- Name: COLUMN outpat_record.checkup; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.checkup IS '体格检查';


--
-- Name: COLUMN outpat_record.assist_exam; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.assist_exam IS '辅助检查';


--
-- Name: COLUMN outpat_record.treatment_advice; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.treatment_advice IS '诊疗意见';


--
-- Name: COLUMN outpat_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.record_content IS '记录内容';


--
-- Name: COLUMN outpat_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN outpat_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN outpat_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN outpat_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN outpat_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.document_title IS '文档标题';


--
-- Name: COLUMN outpat_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.document_status IS '文档状态';


--
-- Name: COLUMN outpat_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.submitter IS '文档提交人';


--
-- Name: COLUMN outpat_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN outpat_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN outpat_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.inpat_no IS '住院号';


--
-- Name: COLUMN outpat_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.mr_no IS '病案号';


--
-- Name: COLUMN outpat_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.name IS '患者姓名';


--
-- Name: COLUMN outpat_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.sex IS '患者性别';


--
-- Name: COLUMN outpat_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.age_year IS '年龄(年)';


--
-- Name: COLUMN outpat_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.age_month IS '年龄(月)';


--
-- Name: COLUMN outpat_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.outpat_record.age IS '年龄-非结构化';


--
-- Name: pathology_exam_master; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.pathology_exam_master (
    specimen_invitro_time timestamp without time zone,
    specimen_fixation_time timestamp without time zone,
    specimen_received_time timestamp without time zone,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    pathology_exam_id character varying(100) NOT NULL,
    pathology_id character varying(100),
    inpat_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    clinical_history character varying(100),
    surgery_name character varying(100),
    specimen_name character varying(100),
    request_dept character varying(100),
    request_physician character varying(100),
    request_datetime timestamp without time zone,
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN pathology_exam_master.specimen_invitro_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.specimen_invitro_time IS 'Caché源字段 specimen_invitro_time，原值语义保留';


--
-- Name: COLUMN pathology_exam_master.specimen_fixation_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.specimen_fixation_time IS 'Caché源字段 specimen_fixation_time，原值语义保留';


--
-- Name: COLUMN pathology_exam_master.specimen_received_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.specimen_received_time IS 'Caché源字段 specimen_received_time，原值语义保留';


--
-- Name: COLUMN pathology_exam_master.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.institute_id IS '机构号';


--
-- Name: COLUMN pathology_exam_master.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.patient_id IS '患者号';


--
-- Name: COLUMN pathology_exam_master.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.visit_id IS '就诊号';


--
-- Name: COLUMN pathology_exam_master.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.visit_type IS '就诊类型';


--
-- Name: COLUMN pathology_exam_master.pathology_exam_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.pathology_exam_id IS '申请序号';


--
-- Name: COLUMN pathology_exam_master.pathology_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.pathology_id IS '病理号';


--
-- Name: COLUMN pathology_exam_master.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.inpat_no IS '住院号';


--
-- Name: COLUMN pathology_exam_master.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.name IS '患者姓名';


--
-- Name: COLUMN pathology_exam_master.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.sex IS '患者性别';


--
-- Name: COLUMN pathology_exam_master.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.age_year IS '年龄(年)';


--
-- Name: COLUMN pathology_exam_master.clinical_history; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.clinical_history IS '临床病史';


--
-- Name: COLUMN pathology_exam_master.surgery_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.surgery_name IS '手术名称';


--
-- Name: COLUMN pathology_exam_master.specimen_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.specimen_name IS '送检标本名称';


--
-- Name: COLUMN pathology_exam_master.request_dept; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.request_dept IS '申请科室';


--
-- Name: COLUMN pathology_exam_master.request_physician; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.request_physician IS '申请医师';


--
-- Name: COLUMN pathology_exam_master.request_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.request_datetime IS '申请时间';


--
-- Name: COLUMN pathology_exam_master.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.record_content IS '记录内容';


--
-- Name: COLUMN pathology_exam_master.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.last_modifier IS '最新修改人';


--
-- Name: COLUMN pathology_exam_master.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN pathology_exam_master.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN pathology_exam_master.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_master.update_time IS '数据更新时间，用于增量同步';


--
-- Name: pathology_exam_report; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.pathology_exam_report (
    specimen_received_time timestamp without time zone,
    ihc_result text,
    material_type text,
    remark text,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    pathology_exam_id character varying(100) NOT NULL,
    pathology_id character varying(100),
    specimen_name text,
    eye_findings text,
    microscope_findings text,
    diagnosis text,
    report_status character varying(100),
    report_datetime timestamp without time zone,
    reporter character varying(100),
    review_datetime timestamp without time zone,
    reviewer character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN pathology_exam_report.specimen_received_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.specimen_received_time IS 'Caché源字段 specimen_received_time，原值语义保留';


--
-- Name: COLUMN pathology_exam_report.ihc_result; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.ihc_result IS 'Caché源字段 ihc_result，原值语义保留';


--
-- Name: COLUMN pathology_exam_report.material_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.material_type IS 'Caché源字段 material_type，原值语义保留';


--
-- Name: COLUMN pathology_exam_report.remark; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.remark IS 'Caché源字段 remark，原值语义保留';


--
-- Name: COLUMN pathology_exam_report.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.institute_id IS '机构号';


--
-- Name: COLUMN pathology_exam_report.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.patient_id IS '患者号';


--
-- Name: COLUMN pathology_exam_report.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.visit_id IS '就诊号';


--
-- Name: COLUMN pathology_exam_report.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.visit_type IS '就诊类型';


--
-- Name: COLUMN pathology_exam_report.pathology_exam_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.pathology_exam_id IS '申请序号';


--
-- Name: COLUMN pathology_exam_report.pathology_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.pathology_id IS '病理号';


--
-- Name: COLUMN pathology_exam_report.specimen_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.specimen_name IS '标本名称';


--
-- Name: COLUMN pathology_exam_report.eye_findings; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.eye_findings IS '肉眼观察所见';


--
-- Name: COLUMN pathology_exam_report.microscope_findings; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.microscope_findings IS '镜下所见';


--
-- Name: COLUMN pathology_exam_report.diagnosis; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.diagnosis IS '病理诊断';


--
-- Name: COLUMN pathology_exam_report.report_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.report_status IS '报告状态';


--
-- Name: COLUMN pathology_exam_report.report_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.report_datetime IS '报告时间';


--
-- Name: COLUMN pathology_exam_report.reporter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.reporter IS '报告者';


--
-- Name: COLUMN pathology_exam_report.review_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.review_datetime IS '审核时间';


--
-- Name: COLUMN pathology_exam_report.reviewer; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.reviewer IS '审核者';


--
-- Name: COLUMN pathology_exam_report.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.record_content IS '记录内容';


--
-- Name: COLUMN pathology_exam_report.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.last_modifier IS '最新修改人';


--
-- Name: COLUMN pathology_exam_report.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN pathology_exam_report.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN pathology_exam_report.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.pathology_exam_report.update_time IS '数据更新时间，用于增量同步';


--
-- Name: patient_information; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.patient_information (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    name character varying(100),
    sex character varying(100),
    birthday date,
    id_card_type character varying(100),
    id_card_no character varying(100),
    ethnicity character varying(100),
    nationality character varying(100),
    marital_status character varying(100),
    contact_number character varying(100),
    occupation_category character varying(100),
    work_unit character varying(100),
    nativeplace text,
    birthplace text,
    currentaddress text,
    workplace text,
    contact_name character varying(100),
    contact_relationship character varying(100),
    contact_address character varying(100),
    contact_telephone character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone
);


--
-- Name: COLUMN patient_information.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.institute_id IS '机构号';


--
-- Name: COLUMN patient_information.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.patient_id IS '患者号';


--
-- Name: COLUMN patient_information.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.name IS '患者姓名';


--
-- Name: COLUMN patient_information.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.sex IS '患者性别';


--
-- Name: COLUMN patient_information.birthday; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.birthday IS '出生日期';


--
-- Name: COLUMN patient_information.id_card_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.id_card_type IS '身份证件类别';


--
-- Name: COLUMN patient_information.id_card_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.id_card_no IS '身份证件号码';


--
-- Name: COLUMN patient_information.ethnicity; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.ethnicity IS '民族';


--
-- Name: COLUMN patient_information.nationality; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.nationality IS '国籍';


--
-- Name: COLUMN patient_information.marital_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.marital_status IS '婚姻状况';


--
-- Name: COLUMN patient_information.contact_number; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.contact_number IS '联系电话';


--
-- Name: COLUMN patient_information.occupation_category; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.occupation_category IS '职业类别';


--
-- Name: COLUMN patient_information.work_unit; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.work_unit IS '工作单位';


--
-- Name: COLUMN patient_information.nativeplace; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.nativeplace IS '籍贯地址';


--
-- Name: COLUMN patient_information.birthplace; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.birthplace IS '出生地址';


--
-- Name: COLUMN patient_information.currentaddress; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.currentaddress IS '现住址';


--
-- Name: COLUMN patient_information.workplace; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.workplace IS '工作单位地址';


--
-- Name: COLUMN patient_information.contact_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.contact_name IS '联系人姓名';


--
-- Name: COLUMN patient_information.contact_relationship; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.contact_relationship IS '联系人关系';


--
-- Name: COLUMN patient_information.contact_address; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.contact_address IS '联系人地址';


--
-- Name: COLUMN patient_information.contact_telephone; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.contact_telephone IS '联系人电话';


--
-- Name: COLUMN patient_information.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.record_content IS '非结构化大段文档记录';


--
-- Name: COLUMN patient_information.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.last_modifier IS '最新修改人';


--
-- Name: COLUMN patient_information.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN patient_information.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN patient_information.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.patient_information.update_time IS '数据更新时间，用于增量同步';


--
-- Name: postane_surveil_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.postane_surveil_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    dept_name character varying(100),
    surgery_name character varying(100),
    anesthesia_method character varying(100),
    resume_descirption character varying(100),
    record_content text,
    anesthetist_sign character varying(100),
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN postane_surveil_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.institute_id IS '机构号';


--
-- Name: COLUMN postane_surveil_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.patient_id IS '患者号';


--
-- Name: COLUMN postane_surveil_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.visit_id IS '就诊号';


--
-- Name: COLUMN postane_surveil_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.document_id IS '文档编号';


--
-- Name: COLUMN postane_surveil_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.visit_type IS '就诊类型';


--
-- Name: COLUMN postane_surveil_record.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.dept_name IS '科室名称';


--
-- Name: COLUMN postane_surveil_record.surgery_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.surgery_name IS '手术操作名称';


--
-- Name: COLUMN postane_surveil_record.anesthesia_method; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.anesthesia_method IS '麻醉方法';


--
-- Name: COLUMN postane_surveil_record.resume_descirption; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.resume_descirption IS '麻醉恢复情况';


--
-- Name: COLUMN postane_surveil_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.record_content IS '记录内容';


--
-- Name: COLUMN postane_surveil_record.anesthetist_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.anesthetist_sign IS '麻醉医师签名';


--
-- Name: COLUMN postane_surveil_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN postane_surveil_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN postane_surveil_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN postane_surveil_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN postane_surveil_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.document_title IS '文档标题';


--
-- Name: COLUMN postane_surveil_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.document_status IS '文档状态';


--
-- Name: COLUMN postane_surveil_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.submitter IS '文档提交人';


--
-- Name: COLUMN postane_surveil_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN postane_surveil_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN postane_surveil_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.inpat_no IS '住院号';


--
-- Name: COLUMN postane_surveil_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.mr_no IS '病案号';


--
-- Name: COLUMN postane_surveil_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.name IS '患者姓名';


--
-- Name: COLUMN postane_surveil_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.sex IS '患者性别';


--
-- Name: COLUMN postane_surveil_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.age_year IS '年龄(年)';


--
-- Name: COLUMN postane_surveil_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.age_month IS '年龄(月)';


--
-- Name: COLUMN postane_surveil_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postane_surveil_record.age IS '年龄-非结构化';


--
-- Name: postsurg_firstcourse_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.postsurg_firstcourse_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    physician_sign text,
    physician_sign_datetime timestamp with time zone,
    surgeon_sign text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN postsurg_firstcourse_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.institute_id IS '机构号';


--
-- Name: COLUMN postsurg_firstcourse_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.patient_id IS '患者号';


--
-- Name: COLUMN postsurg_firstcourse_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.visit_id IS '就诊号';


--
-- Name: COLUMN postsurg_firstcourse_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.document_id IS '文档编号';


--
-- Name: COLUMN postsurg_firstcourse_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.visit_type IS '就诊类型';


--
-- Name: COLUMN postsurg_firstcourse_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.record_content IS '非结构化全文';


--
-- Name: COLUMN postsurg_firstcourse_record.physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.physician_sign IS '医师签名（源值）';


--
-- Name: COLUMN postsurg_firstcourse_record.physician_sign_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.physician_sign_datetime IS '医师签名时间';


--
-- Name: COLUMN postsurg_firstcourse_record.surgeon_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.surgeon_sign IS '术者签名（独立于记录医师）';


--
-- Name: COLUMN postsurg_firstcourse_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN postsurg_firstcourse_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN postsurg_firstcourse_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN postsurg_firstcourse_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN postsurg_firstcourse_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.document_title IS '文档标题';


--
-- Name: COLUMN postsurg_firstcourse_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.document_status IS '文档状态';


--
-- Name: COLUMN postsurg_firstcourse_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.submitter IS '文档提交人';


--
-- Name: COLUMN postsurg_firstcourse_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN postsurg_firstcourse_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN postsurg_firstcourse_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.inpat_no IS '住院号';


--
-- Name: COLUMN postsurg_firstcourse_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.mr_no IS '病案号';


--
-- Name: COLUMN postsurg_firstcourse_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.name IS '患者姓名';


--
-- Name: COLUMN postsurg_firstcourse_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.sex IS '患者性别';


--
-- Name: COLUMN postsurg_firstcourse_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.age_year IS '年龄(年)';


--
-- Name: COLUMN postsurg_firstcourse_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.age_month IS '年龄(月)';


--
-- Name: COLUMN postsurg_firstcourse_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.postsurg_firstcourse_record.age IS '年龄-非结构化';


--
-- Name: preane_surveil_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.preane_surveil_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    dept_name character varying(100),
    condition_summary text,
    planned_anesthesia_method character varying(100),
    "ASA_level" character varying(100),
    record_content text,
    anesthetist_sign character varying(100),
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN preane_surveil_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.institute_id IS '机构号';


--
-- Name: COLUMN preane_surveil_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.patient_id IS '患者号';


--
-- Name: COLUMN preane_surveil_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.visit_id IS '就诊号';


--
-- Name: COLUMN preane_surveil_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.document_id IS '文档编号';


--
-- Name: COLUMN preane_surveil_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.visit_type IS '就诊类型';


--
-- Name: COLUMN preane_surveil_record.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.dept_name IS '科室名称';


--
-- Name: COLUMN preane_surveil_record.condition_summary; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.condition_summary IS '病情摘要';


--
-- Name: COLUMN preane_surveil_record.planned_anesthesia_method; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.planned_anesthesia_method IS '拟实施麻醉方法';


--
-- Name: COLUMN preane_surveil_record."ASA_level"; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record."ASA_level" IS 'ASA分级';


--
-- Name: COLUMN preane_surveil_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.record_content IS '记录内容';


--
-- Name: COLUMN preane_surveil_record.anesthetist_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.anesthetist_sign IS '麻醉医师签名';


--
-- Name: COLUMN preane_surveil_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN preane_surveil_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN preane_surveil_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN preane_surveil_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN preane_surveil_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.document_title IS '文档标题';


--
-- Name: COLUMN preane_surveil_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.document_status IS '文档状态';


--
-- Name: COLUMN preane_surveil_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.submitter IS '文档提交人';


--
-- Name: COLUMN preane_surveil_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN preane_surveil_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN preane_surveil_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.inpat_no IS '住院号';


--
-- Name: COLUMN preane_surveil_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.mr_no IS '病案号';


--
-- Name: COLUMN preane_surveil_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.name IS '患者姓名';


--
-- Name: COLUMN preane_surveil_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.sex IS '患者性别';


--
-- Name: COLUMN preane_surveil_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.age_year IS '年龄(年)';


--
-- Name: COLUMN preane_surveil_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.age_month IS '年龄(月)';


--
-- Name: COLUMN preane_surveil_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.preane_surveil_record.age IS '年龄-非结构化';


--
-- Name: presurg_discussion; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.presurg_discussion (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN presurg_discussion.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.institute_id IS '机构号';


--
-- Name: COLUMN presurg_discussion.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.patient_id IS '患者号';


--
-- Name: COLUMN presurg_discussion.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.visit_id IS '就诊号';


--
-- Name: COLUMN presurg_discussion.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.document_id IS '文档编号';


--
-- Name: COLUMN presurg_discussion.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.visit_type IS '就诊类型';


--
-- Name: COLUMN presurg_discussion.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.record_content IS '非结构化全文';


--
-- Name: COLUMN presurg_discussion.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.last_modifier IS '最新修改人';


--
-- Name: COLUMN presurg_discussion.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN presurg_discussion.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN presurg_discussion.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN presurg_discussion.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.document_title IS '文档标题';


--
-- Name: COLUMN presurg_discussion.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.document_status IS '文档状态';


--
-- Name: COLUMN presurg_discussion.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.submitter IS '文档提交人';


--
-- Name: COLUMN presurg_discussion.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN presurg_discussion.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN presurg_discussion.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.inpat_no IS '住院号';


--
-- Name: COLUMN presurg_discussion.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.mr_no IS '病案号';


--
-- Name: COLUMN presurg_discussion.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.name IS '患者姓名';


--
-- Name: COLUMN presurg_discussion.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.sex IS '患者性别';


--
-- Name: COLUMN presurg_discussion.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.age_year IS '年龄(年)';


--
-- Name: COLUMN presurg_discussion.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.age_month IS '年龄(月)';


--
-- Name: COLUMN presurg_discussion.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_discussion.age IS '年龄-非结构化';


--
-- Name: presurg_summary; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.presurg_summary (
    record_datetime timestamp without time zone,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN presurg_summary.record_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.record_datetime IS 'Caché源字段 record_datetime，独立保留原始语义';


--
-- Name: COLUMN presurg_summary.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.institute_id IS '机构号';


--
-- Name: COLUMN presurg_summary.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.patient_id IS '患者号';


--
-- Name: COLUMN presurg_summary.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.visit_id IS '就诊号';


--
-- Name: COLUMN presurg_summary.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.document_id IS '文档编号';


--
-- Name: COLUMN presurg_summary.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.visit_type IS '就诊类型';


--
-- Name: COLUMN presurg_summary.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.record_content IS '非结构化全文';


--
-- Name: COLUMN presurg_summary.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.last_modifier IS '最新修改人';


--
-- Name: COLUMN presurg_summary.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN presurg_summary.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN presurg_summary.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN presurg_summary.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.document_title IS '文档标题';


--
-- Name: COLUMN presurg_summary.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.document_status IS '文档状态';


--
-- Name: COLUMN presurg_summary.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.submitter IS '文档提交人';


--
-- Name: COLUMN presurg_summary.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN presurg_summary.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN presurg_summary.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.inpat_no IS '住院号';


--
-- Name: COLUMN presurg_summary.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.mr_no IS '病案号';


--
-- Name: COLUMN presurg_summary.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.name IS '患者姓名';


--
-- Name: COLUMN presurg_summary.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.sex IS '患者性别';


--
-- Name: COLUMN presurg_summary.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.age_year IS '年龄(年)';


--
-- Name: COLUMN presurg_summary.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.age_month IS '年龄(月)';


--
-- Name: COLUMN presurg_summary.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.presurg_summary.age IS '年龄-非结构化';


--
-- Name: rescue_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.rescue_record (
    record_datetime timestamp without time zone,
    physician_sign text,
    physician_sign_datetime timestamp without time zone,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN rescue_record.record_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.record_datetime IS 'Caché源字段 record_datetime，原值语义保留';


--
-- Name: COLUMN rescue_record.physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.physician_sign IS 'Caché源字段 physician_sign，原值语义保留';


--
-- Name: COLUMN rescue_record.physician_sign_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.physician_sign_datetime IS 'Caché源字段 physician_sign_datetime，原值语义保留';


--
-- Name: COLUMN rescue_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.institute_id IS '机构号';


--
-- Name: COLUMN rescue_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.patient_id IS '患者号';


--
-- Name: COLUMN rescue_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.visit_id IS '就诊号';


--
-- Name: COLUMN rescue_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.document_id IS '文档编号';


--
-- Name: COLUMN rescue_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.visit_type IS '就诊类型';


--
-- Name: COLUMN rescue_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.record_content IS '非结构化全文';


--
-- Name: COLUMN rescue_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN rescue_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN rescue_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN rescue_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN rescue_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.document_title IS '文档标题';


--
-- Name: COLUMN rescue_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.document_status IS '文档状态';


--
-- Name: COLUMN rescue_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.submitter IS '文档提交人';


--
-- Name: COLUMN rescue_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN rescue_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN rescue_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.inpat_no IS '住院号';


--
-- Name: COLUMN rescue_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.mr_no IS '病案号';


--
-- Name: COLUMN rescue_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.name IS '患者姓名';


--
-- Name: COLUMN rescue_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.sex IS '患者性别';


--
-- Name: COLUMN rescue_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.age_year IS '年龄(年)';


--
-- Name: COLUMN rescue_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.age_month IS '年龄(月)';


--
-- Name: COLUMN rescue_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.rescue_record.age IS '年龄-非结构化';


--
-- Name: senior_course_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.senior_course_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    physician_sign text,
    physician_sign_datetime timestamp with time zone,
    recorder_sign text,
    attending_physician_sign text,
    senior_physician_sign text,
    seniorphy_sign_datetime timestamp with time zone,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN senior_course_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.institute_id IS '机构号';


--
-- Name: COLUMN senior_course_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.patient_id IS '患者号';


--
-- Name: COLUMN senior_course_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.visit_id IS '就诊号';


--
-- Name: COLUMN senior_course_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.document_id IS '文档编号';


--
-- Name: COLUMN senior_course_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.visit_type IS '就诊类型';


--
-- Name: COLUMN senior_course_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.record_content IS '非结构化全文';


--
-- Name: COLUMN senior_course_record.physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.physician_sign IS '医师签名（源值，不以其他角色补值）';


--
-- Name: COLUMN senior_course_record.physician_sign_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.physician_sign_datetime IS '医师签名时间';


--
-- Name: COLUMN senior_course_record.recorder_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.recorder_sign IS '记录人签名';


--
-- Name: COLUMN senior_course_record.attending_physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.attending_physician_sign IS '主治医师签名';


--
-- Name: COLUMN senior_course_record.senior_physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.senior_physician_sign IS '上级医师签名';


--
-- Name: COLUMN senior_course_record.seniorphy_sign_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.seniorphy_sign_datetime IS '上级医师签名时间';


--
-- Name: COLUMN senior_course_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN senior_course_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN senior_course_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN senior_course_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN senior_course_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.document_title IS '文档标题';


--
-- Name: COLUMN senior_course_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.document_status IS '文档状态';


--
-- Name: COLUMN senior_course_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.submitter IS '文档提交人';


--
-- Name: COLUMN senior_course_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN senior_course_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN senior_course_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.inpat_no IS '住院号';


--
-- Name: COLUMN senior_course_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.mr_no IS '病案号';


--
-- Name: COLUMN senior_course_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.name IS '患者姓名';


--
-- Name: COLUMN senior_course_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.sex IS '患者性别';


--
-- Name: COLUMN senior_course_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.age_year IS '年龄(年)';


--
-- Name: COLUMN senior_course_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.age_month IS '年龄(月)';


--
-- Name: COLUMN senior_course_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.senior_course_record.age IS '年龄-非结构化';


--
-- Name: summary_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.summary_record (
    record_datetime timestamp without time zone,
    physician_sign text,
    physician_sign_datetime timestamp without time zone,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN summary_record.record_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.record_datetime IS 'Caché源字段 record_datetime，原值语义保留';


--
-- Name: COLUMN summary_record.physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.physician_sign IS 'Caché源字段 physician_sign，原值语义保留';


--
-- Name: COLUMN summary_record.physician_sign_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.physician_sign_datetime IS 'Caché源字段 physician_sign_datetime，原值语义保留';


--
-- Name: COLUMN summary_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.institute_id IS '机构号';


--
-- Name: COLUMN summary_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.patient_id IS '患者号';


--
-- Name: COLUMN summary_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.visit_id IS '就诊号';


--
-- Name: COLUMN summary_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.document_id IS '文档编号';


--
-- Name: COLUMN summary_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.visit_type IS '就诊类型';


--
-- Name: COLUMN summary_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.record_content IS '非结构化全文';


--
-- Name: COLUMN summary_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN summary_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN summary_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN summary_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN summary_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.document_title IS '文档标题';


--
-- Name: COLUMN summary_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.document_status IS '文档状态';


--
-- Name: COLUMN summary_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.submitter IS '文档提交人';


--
-- Name: COLUMN summary_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN summary_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN summary_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.inpat_no IS '住院号';


--
-- Name: COLUMN summary_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.mr_no IS '病案号';


--
-- Name: COLUMN summary_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.name IS '患者姓名';


--
-- Name: COLUMN summary_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.sex IS '患者性别';


--
-- Name: COLUMN summary_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.age_year IS '年龄(年)';


--
-- Name: COLUMN summary_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.age_month IS '年龄(月)';


--
-- Name: COLUMN summary_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.summary_record.age IS '年龄-非结构化';


--
-- Name: surgery_application; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.surgery_application (
    request_datetime timestamp without time zone,
    record_datetime timestamp without time zone,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    visit_type character varying(100),
    application_id character varying(100) NOT NULL,
    order_id character varying(100),
    dept_name character varying(100),
    surgery_name character varying(100),
    surgery_code character varying(100),
    surgery_level character varying(100),
    anesthesia_method character varying(100),
    surgeon character varying(100),
    request_physician character varying(100),
    request_surgery_datetime timestamp without time zone,
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN surgery_application.request_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.request_datetime IS 'Caché源字段 request_datetime，独立保留原始语义';


--
-- Name: COLUMN surgery_application.record_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.record_datetime IS 'Caché源字段 record_datetime，独立保留原始语义';


--
-- Name: COLUMN surgery_application.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.institute_id IS '机构号';


--
-- Name: COLUMN surgery_application.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.patient_id IS '患者号';


--
-- Name: COLUMN surgery_application.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.visit_id IS '就诊号';


--
-- Name: COLUMN surgery_application.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.visit_type IS '就诊类型';


--
-- Name: COLUMN surgery_application.application_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.application_id IS '申请号';


--
-- Name: COLUMN surgery_application.order_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.order_id IS '医嘱号';


--
-- Name: COLUMN surgery_application.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.dept_name IS '科室名称';


--
-- Name: COLUMN surgery_application.surgery_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.surgery_name IS '手术操作名称';


--
-- Name: COLUMN surgery_application.surgery_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.surgery_code IS '手术操作编码';


--
-- Name: COLUMN surgery_application.surgery_level; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.surgery_level IS '手术级别';


--
-- Name: COLUMN surgery_application.anesthesia_method; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.anesthesia_method IS '麻醉方法';


--
-- Name: COLUMN surgery_application.surgeon; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.surgeon IS '手术医师姓名';


--
-- Name: COLUMN surgery_application.request_physician; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.request_physician IS '申请医师姓名';


--
-- Name: COLUMN surgery_application.request_surgery_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.request_surgery_datetime IS '申请手术时间';


--
-- Name: COLUMN surgery_application.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.record_content IS '记录内容';


--
-- Name: COLUMN surgery_application.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.last_modifier IS '最新修改人';


--
-- Name: COLUMN surgery_application.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN surgery_application.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN surgery_application.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN surgery_application.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.inpat_no IS '住院号';


--
-- Name: COLUMN surgery_application.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.mr_no IS '病案号';


--
-- Name: COLUMN surgery_application.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.name IS '患者姓名';


--
-- Name: COLUMN surgery_application.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.sex IS '患者性别';


--
-- Name: COLUMN surgery_application.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.age_year IS '年龄(年)';


--
-- Name: COLUMN surgery_application.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.age_month IS '年龄(月)';


--
-- Name: COLUMN surgery_application.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_application.age IS '年龄-非结构化';


--
-- Name: surgery_inform_consent; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.surgery_inform_consent (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    dept_name character varying(100),
    planned_operation_name character varying(100),
    planned_operation_code character varying(100),
    planned_anesthesia_method character varying(100),
    surgery_risk_description text,
    record_content text,
    patient_sign character varying(100),
    surgeon_sign character varying(100),
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN surgery_inform_consent.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.institute_id IS '机构号';


--
-- Name: COLUMN surgery_inform_consent.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.patient_id IS '患者号';


--
-- Name: COLUMN surgery_inform_consent.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.visit_id IS '就诊号';


--
-- Name: COLUMN surgery_inform_consent.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.document_id IS '文档编号';


--
-- Name: COLUMN surgery_inform_consent.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.visit_type IS '就诊类型';


--
-- Name: COLUMN surgery_inform_consent.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.dept_name IS '科室名称';


--
-- Name: COLUMN surgery_inform_consent.planned_operation_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.planned_operation_name IS '拟实施手术操作名称';


--
-- Name: COLUMN surgery_inform_consent.planned_operation_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.planned_operation_code IS '拟实施手术操作编码';


--
-- Name: COLUMN surgery_inform_consent.planned_anesthesia_method; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.planned_anesthesia_method IS '拟实施麻醉方法';


--
-- Name: COLUMN surgery_inform_consent.surgery_risk_description; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.surgery_risk_description IS '手术中可能出现的意外及风险';


--
-- Name: COLUMN surgery_inform_consent.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.record_content IS '记录内容';


--
-- Name: COLUMN surgery_inform_consent.patient_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.patient_sign IS '患者签名';


--
-- Name: COLUMN surgery_inform_consent.surgeon_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.surgeon_sign IS '手术医师签名';


--
-- Name: COLUMN surgery_inform_consent.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.last_modifier IS '最新修改人';


--
-- Name: COLUMN surgery_inform_consent.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN surgery_inform_consent.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN surgery_inform_consent.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN surgery_inform_consent.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.document_title IS '文档标题';


--
-- Name: COLUMN surgery_inform_consent.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.document_status IS '文档状态';


--
-- Name: COLUMN surgery_inform_consent.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.submitter IS '文档提交人';


--
-- Name: COLUMN surgery_inform_consent.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN surgery_inform_consent.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN surgery_inform_consent.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.inpat_no IS '住院号';


--
-- Name: COLUMN surgery_inform_consent.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.mr_no IS '病案号';


--
-- Name: COLUMN surgery_inform_consent.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.name IS '患者姓名';


--
-- Name: COLUMN surgery_inform_consent.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.sex IS '患者性别';


--
-- Name: COLUMN surgery_inform_consent.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.age_year IS '年龄(年)';


--
-- Name: COLUMN surgery_inform_consent.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.age_month IS '年龄(月)';


--
-- Name: COLUMN surgery_inform_consent.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inform_consent.age IS '年龄-非结构化';


--
-- Name: surgery_inventory_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.surgery_inventory_record (
    surgery_room_enter_time timestamp without time zone,
    surgery_room_leave_time timestamp without time zone,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    dept_name character varying(100),
    surgery_room_name character varying(100),
    surgery_date date,
    surgery_name character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN surgery_inventory_record.surgery_room_enter_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.surgery_room_enter_time IS 'Caché源字段 surgery_room_enter_time，独立保留原始语义';


--
-- Name: COLUMN surgery_inventory_record.surgery_room_leave_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.surgery_room_leave_time IS 'Caché源字段 surgery_room_leave_time，独立保留原始语义';


--
-- Name: COLUMN surgery_inventory_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.institute_id IS '机构号';


--
-- Name: COLUMN surgery_inventory_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.patient_id IS '患者号';


--
-- Name: COLUMN surgery_inventory_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.visit_id IS '就诊号';


--
-- Name: COLUMN surgery_inventory_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.document_id IS '文档编号';


--
-- Name: COLUMN surgery_inventory_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.visit_type IS '就诊类型';


--
-- Name: COLUMN surgery_inventory_record.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.dept_name IS '科室名称';


--
-- Name: COLUMN surgery_inventory_record.surgery_room_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.surgery_room_name IS '手术间';


--
-- Name: COLUMN surgery_inventory_record.surgery_date; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.surgery_date IS '手术日期';


--
-- Name: COLUMN surgery_inventory_record.surgery_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.surgery_name IS '手术名称';


--
-- Name: COLUMN surgery_inventory_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.record_content IS '记录内容';


--
-- Name: COLUMN surgery_inventory_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN surgery_inventory_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN surgery_inventory_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN surgery_inventory_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN surgery_inventory_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.document_title IS '文档标题';


--
-- Name: COLUMN surgery_inventory_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.document_status IS '文档状态';


--
-- Name: COLUMN surgery_inventory_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.submitter IS '文档提交人';


--
-- Name: COLUMN surgery_inventory_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN surgery_inventory_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN surgery_inventory_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.inpat_no IS '住院号';


--
-- Name: COLUMN surgery_inventory_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.mr_no IS '病案号';


--
-- Name: COLUMN surgery_inventory_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.name IS '患者姓名';


--
-- Name: COLUMN surgery_inventory_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.sex IS '患者性别';


--
-- Name: COLUMN surgery_inventory_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.age_year IS '年龄(年)';


--
-- Name: COLUMN surgery_inventory_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.age_month IS '年龄(月)';


--
-- Name: COLUMN surgery_inventory_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_inventory_record.age IS '年龄-非结构化';


--
-- Name: surgery_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.surgery_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    dept_name character varying(100),
    ward_name character varying(100),
    submitter character varying(100),
    surgeon_sign character varying(100),
    presurg_summary text,
    surgery_name text,
    surgery_code character varying(100),
    surgery_level character varying(50),
    surgical_level character varying(50),
    surgeon character varying(100),
    first_assistant character varying(100),
    second_assistant character varying(100),
    anesthesiologist character varying(100),
    anesthesia_method character varying(100),
    preoperative_diagnosis text,
    intraoperative_diagnosis text,
    postoperative_diagnosis text,
    surgery_process text,
    surgical_incisionheal_level character varying(100),
    surgery_begin_time timestamp with time zone,
    surgery_end_time timestamp with time zone,
    blood_loss character varying(100),
    other_content text,
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN surgery_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.institute_id IS '机构号';


--
-- Name: COLUMN surgery_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.patient_id IS '患者号';


--
-- Name: COLUMN surgery_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.visit_id IS '就诊号';


--
-- Name: COLUMN surgery_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.document_id IS '文档编号/单号';


--
-- Name: COLUMN surgery_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.visit_type IS '就诊类型';


--
-- Name: COLUMN surgery_record.dept_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.dept_name IS '科室名称';


--
-- Name: COLUMN surgery_record.ward_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.ward_name IS '病房名称';


--
-- Name: COLUMN surgery_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.submitter IS '记录者';


--
-- Name: COLUMN surgery_record.surgeon_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.surgeon_sign IS '手术医师签名';


--
-- Name: COLUMN surgery_record.presurg_summary; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.presurg_summary IS '术前小结';


--
-- Name: COLUMN surgery_record.surgery_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.surgery_name IS '手术项目';


--
-- Name: COLUMN surgery_record.surgery_code; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.surgery_code IS '手术编码';


--
-- Name: COLUMN surgery_record.surgery_level; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.surgery_level IS '手术等级';


--
-- Name: COLUMN surgery_record.surgical_level; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.surgical_level IS '手术等级（兼容来源字段）';


--
-- Name: COLUMN surgery_record.surgeon; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.surgeon IS '手术医师';


--
-- Name: COLUMN surgery_record.first_assistant; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.first_assistant IS '手术第一助手';


--
-- Name: COLUMN surgery_record.second_assistant; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.second_assistant IS '手术第二助手';


--
-- Name: COLUMN surgery_record.anesthesiologist; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.anesthesiologist IS '麻醉医师';


--
-- Name: COLUMN surgery_record.anesthesia_method; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.anesthesia_method IS '麻醉方式';


--
-- Name: COLUMN surgery_record.preoperative_diagnosis; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.preoperative_diagnosis IS '术前诊断';


--
-- Name: COLUMN surgery_record.intraoperative_diagnosis; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.intraoperative_diagnosis IS '术中诊断';


--
-- Name: COLUMN surgery_record.postoperative_diagnosis; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.postoperative_diagnosis IS '术后诊断';


--
-- Name: COLUMN surgery_record.surgery_process; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.surgery_process IS '手术经过';


--
-- Name: COLUMN surgery_record.surgical_incisionheal_level; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.surgical_incisionheal_level IS '切口愈合等级';


--
-- Name: COLUMN surgery_record.surgery_begin_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.surgery_begin_time IS '手术开始时间';


--
-- Name: COLUMN surgery_record.surgery_end_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.surgery_end_time IS '手术结束时间';


--
-- Name: COLUMN surgery_record.blood_loss; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.blood_loss IS '失血量';


--
-- Name: COLUMN surgery_record.other_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.other_content IS '其他内容';


--
-- Name: COLUMN surgery_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.record_content IS '非结构化全文';


--
-- Name: COLUMN surgery_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN surgery_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN surgery_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN surgery_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN surgery_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.document_title IS '文档标题';


--
-- Name: COLUMN surgery_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.document_status IS '文档状态';


--
-- Name: COLUMN surgery_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN surgery_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN surgery_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.inpat_no IS '住院号';


--
-- Name: COLUMN surgery_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.mr_no IS '病案号';


--
-- Name: COLUMN surgery_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.name IS '患者姓名';


--
-- Name: COLUMN surgery_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.sex IS '患者性别';


--
-- Name: COLUMN surgery_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.age_year IS '年龄(年)';


--
-- Name: COLUMN surgery_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.age_month IS '年龄(月)';


--
-- Name: COLUMN surgery_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_record.age IS '年龄-非结构化';


--
-- Name: surgery_risk_assessment; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.surgery_risk_assessment (
    application_id character varying(100),
    assessment_datetime timestamp without time zone,
    surgeon_assess_date timestamp without time zone,
    anesthesiologist_assess_date timestamp without time zone,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN surgery_risk_assessment.application_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.application_id IS 'Caché源字段 application_id，独立保留原始语义';


--
-- Name: COLUMN surgery_risk_assessment.assessment_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.assessment_datetime IS 'Caché源字段 assessment_datetime，独立保留原始语义';


--
-- Name: COLUMN surgery_risk_assessment.surgeon_assess_date; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.surgeon_assess_date IS 'Caché源字段 surgeon_assess_date，独立保留原始语义';


--
-- Name: COLUMN surgery_risk_assessment.anesthesiologist_assess_date; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.anesthesiologist_assess_date IS 'Caché源字段 anesthesiologist_assess_date，独立保留原始语义';


--
-- Name: COLUMN surgery_risk_assessment.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.institute_id IS '机构号';


--
-- Name: COLUMN surgery_risk_assessment.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.patient_id IS '患者号';


--
-- Name: COLUMN surgery_risk_assessment.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.visit_id IS '就诊号';


--
-- Name: COLUMN surgery_risk_assessment.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.document_id IS '文档编号';


--
-- Name: COLUMN surgery_risk_assessment.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.visit_type IS '就诊类型';


--
-- Name: COLUMN surgery_risk_assessment.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.record_content IS '非结构化全文';


--
-- Name: COLUMN surgery_risk_assessment.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.last_modifier IS '最新修改人';


--
-- Name: COLUMN surgery_risk_assessment.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN surgery_risk_assessment.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN surgery_risk_assessment.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN surgery_risk_assessment.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.document_title IS '文档标题';


--
-- Name: COLUMN surgery_risk_assessment.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.document_status IS '文档状态';


--
-- Name: COLUMN surgery_risk_assessment.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.submitter IS '文档提交人';


--
-- Name: COLUMN surgery_risk_assessment.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN surgery_risk_assessment.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN surgery_risk_assessment.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.inpat_no IS '住院号';


--
-- Name: COLUMN surgery_risk_assessment.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.mr_no IS '病案号';


--
-- Name: COLUMN surgery_risk_assessment.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.name IS '患者姓名';


--
-- Name: COLUMN surgery_risk_assessment.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.sex IS '患者性别';


--
-- Name: COLUMN surgery_risk_assessment.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.age_year IS '年龄(年)';


--
-- Name: COLUMN surgery_risk_assessment.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.age_month IS '年龄(月)';


--
-- Name: COLUMN surgery_risk_assessment.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_risk_assessment.age IS '年龄-非结构化';


--
-- Name: surgery_safecheck_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.surgery_safecheck_record (
    record_datetime timestamp without time zone,
    surgery_begin_datetime timestamp without time zone,
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN surgery_safecheck_record.record_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.record_datetime IS 'Caché源字段 record_datetime，独立保留原始语义';


--
-- Name: COLUMN surgery_safecheck_record.surgery_begin_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.surgery_begin_datetime IS 'Caché源字段 surgery_begin_datetime，独立保留原始语义';


--
-- Name: COLUMN surgery_safecheck_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.institute_id IS '机构号';


--
-- Name: COLUMN surgery_safecheck_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.patient_id IS '患者号';


--
-- Name: COLUMN surgery_safecheck_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.visit_id IS '就诊号';


--
-- Name: COLUMN surgery_safecheck_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.document_id IS '文档编号';


--
-- Name: COLUMN surgery_safecheck_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.visit_type IS '就诊类型';


--
-- Name: COLUMN surgery_safecheck_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.record_content IS '非结构化全文';


--
-- Name: COLUMN surgery_safecheck_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN surgery_safecheck_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN surgery_safecheck_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN surgery_safecheck_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN surgery_safecheck_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.document_title IS '文档标题';


--
-- Name: COLUMN surgery_safecheck_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.document_status IS '文档状态';


--
-- Name: COLUMN surgery_safecheck_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.submitter IS '文档提交人';


--
-- Name: COLUMN surgery_safecheck_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN surgery_safecheck_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN surgery_safecheck_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.inpat_no IS '住院号';


--
-- Name: COLUMN surgery_safecheck_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.mr_no IS '病案号';


--
-- Name: COLUMN surgery_safecheck_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.name IS '患者姓名';


--
-- Name: COLUMN surgery_safecheck_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.sex IS '患者性别';


--
-- Name: COLUMN surgery_safecheck_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.age_year IS '年龄(年)';


--
-- Name: COLUMN surgery_safecheck_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.age_month IS '年龄(月)';


--
-- Name: COLUMN surgery_safecheck_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.surgery_safecheck_record.age IS '年龄-非结构化';


--
-- Name: transfer_in_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.transfer_in_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    patient_name character varying(100),
    remark character varying(100),
    admission_date date,
    transferout_department character varying(100),
    transferin_department character varying(100),
    transfer_date character varying(100),
    transfer_purpose text,
    admission_condition text,
    chief_complaint text,
    treatment_course text,
    transfer_treatment_plan text,
    current_situation text,
    note text,
    record_datetime timestamp without time zone,
    physician_sign character varying(100),
    physician_sign_datetime timestamp without time zone,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN transfer_in_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.institute_id IS '机构号';


--
-- Name: COLUMN transfer_in_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.patient_id IS '患者号';


--
-- Name: COLUMN transfer_in_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.visit_id IS '就诊号';


--
-- Name: COLUMN transfer_in_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.document_id IS '文档编号';


--
-- Name: COLUMN transfer_in_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.visit_type IS '就诊类型';


--
-- Name: COLUMN transfer_in_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.record_content IS '非结构化全文';


--
-- Name: COLUMN transfer_in_record.patient_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.patient_name IS '患者姓名';


--
-- Name: COLUMN transfer_in_record.remark; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.remark IS '备注';


--
-- Name: COLUMN transfer_in_record.admission_date; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.admission_date IS '入院日期';


--
-- Name: COLUMN transfer_in_record.transferout_department; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.transferout_department IS '转出科室';


--
-- Name: COLUMN transfer_in_record.transferin_department; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.transferin_department IS '转入科室';


--
-- Name: COLUMN transfer_in_record.transfer_date; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.transfer_date IS '转科日期';


--
-- Name: COLUMN transfer_in_record.transfer_purpose; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.transfer_purpose IS '转科目的';


--
-- Name: COLUMN transfer_in_record.admission_condition; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.admission_condition IS '入院情况';


--
-- Name: COLUMN transfer_in_record.chief_complaint; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.chief_complaint IS '主诉';


--
-- Name: COLUMN transfer_in_record.treatment_course; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.treatment_course IS '诊疗经过';


--
-- Name: COLUMN transfer_in_record.transfer_treatment_plan; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.transfer_treatment_plan IS '转入诊疗计划';


--
-- Name: COLUMN transfer_in_record.current_situation; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.current_situation IS '目前情况';


--
-- Name: COLUMN transfer_in_record.note; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.note IS '注意事项';


--
-- Name: COLUMN transfer_in_record.record_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.record_datetime IS '记录时间';


--
-- Name: COLUMN transfer_in_record.physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.physician_sign IS '医师签名';


--
-- Name: COLUMN transfer_in_record.physician_sign_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.physician_sign_datetime IS '医师签名时间';


--
-- Name: COLUMN transfer_in_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN transfer_in_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN transfer_in_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN transfer_in_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN transfer_in_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.document_title IS '文档标题';


--
-- Name: COLUMN transfer_in_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.document_status IS '文档状态';


--
-- Name: COLUMN transfer_in_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.submitter IS '文档提交人';


--
-- Name: COLUMN transfer_in_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN transfer_in_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN transfer_in_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.inpat_no IS '住院号';


--
-- Name: COLUMN transfer_in_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.mr_no IS '病案号';


--
-- Name: COLUMN transfer_in_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.name IS '患者姓名';


--
-- Name: COLUMN transfer_in_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.sex IS '患者性别';


--
-- Name: COLUMN transfer_in_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.age_year IS '年龄(年)';


--
-- Name: COLUMN transfer_in_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.age_month IS '年龄(月)';


--
-- Name: COLUMN transfer_in_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_in_record.age IS '年龄-非结构化';


--
-- Name: transfer_out_record; Type: TABLE; Schema: cdm; Owner: -
--

CREATE TABLE cdm.transfer_out_record (
    institute_id character varying(100) NOT NULL,
    patient_id character varying(100) NOT NULL,
    visit_id character varying(100) NOT NULL,
    document_id character varying(100) NOT NULL,
    visit_type character varying(100),
    record_content text,
    patient_name character varying(100),
    remark character varying(100),
    admission_date date,
    transferout_department character varying(100),
    transferin_department character varying(100),
    transfer_date character varying(100),
    transfer_purpose text,
    admission_condition text,
    chief_complaint text,
    treatment_course text,
    current_situation text,
    note text,
    record_datetime timestamp without time zone,
    physician_sign character varying(100),
    physician_sign_datetime timestamp without time zone,
    last_modifier character varying(100),
    last_modifier_id character varying(100),
    last_modified_datetime timestamp without time zone,
    update_time timestamp without time zone,
    document_title character varying(100),
    document_status character varying(100),
    submitter character varying(100),
    submitter_id character varying(100),
    submit_datetime timestamp without time zone,
    inpat_no character varying(100),
    mr_no character varying(100),
    name character varying(100),
    sex character varying(100),
    age_year character varying(100),
    age_month character varying(100),
    age character varying(100)
);


--
-- Name: COLUMN transfer_out_record.institute_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.institute_id IS '机构号';


--
-- Name: COLUMN transfer_out_record.patient_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.patient_id IS '患者号';


--
-- Name: COLUMN transfer_out_record.visit_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.visit_id IS '就诊号';


--
-- Name: COLUMN transfer_out_record.document_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.document_id IS '文档编号';


--
-- Name: COLUMN transfer_out_record.visit_type; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.visit_type IS '就诊类型';


--
-- Name: COLUMN transfer_out_record.record_content; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.record_content IS '非结构化全文';


--
-- Name: COLUMN transfer_out_record.patient_name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.patient_name IS '患者姓名';


--
-- Name: COLUMN transfer_out_record.remark; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.remark IS '备注';


--
-- Name: COLUMN transfer_out_record.admission_date; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.admission_date IS '入院日期';


--
-- Name: COLUMN transfer_out_record.transferout_department; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.transferout_department IS '转出科室';


--
-- Name: COLUMN transfer_out_record.transferin_department; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.transferin_department IS '转入科室';


--
-- Name: COLUMN transfer_out_record.transfer_date; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.transfer_date IS '转科日期';


--
-- Name: COLUMN transfer_out_record.transfer_purpose; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.transfer_purpose IS '转科目的';


--
-- Name: COLUMN transfer_out_record.admission_condition; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.admission_condition IS '入院情况';


--
-- Name: COLUMN transfer_out_record.chief_complaint; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.chief_complaint IS '主诉';


--
-- Name: COLUMN transfer_out_record.treatment_course; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.treatment_course IS '诊疗经过';


--
-- Name: COLUMN transfer_out_record.current_situation; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.current_situation IS '目前情况';


--
-- Name: COLUMN transfer_out_record.note; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.note IS '注意事项';


--
-- Name: COLUMN transfer_out_record.record_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.record_datetime IS '记录时间';


--
-- Name: COLUMN transfer_out_record.physician_sign; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.physician_sign IS '医师签名';


--
-- Name: COLUMN transfer_out_record.physician_sign_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.physician_sign_datetime IS '医师签名时间';


--
-- Name: COLUMN transfer_out_record.last_modifier; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.last_modifier IS '最新修改人';


--
-- Name: COLUMN transfer_out_record.last_modifier_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.last_modifier_id IS '最新修改人id';


--
-- Name: COLUMN transfer_out_record.last_modified_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.last_modified_datetime IS '最新修改时间';


--
-- Name: COLUMN transfer_out_record.update_time; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.update_time IS '数据更新时间，用于增量同步';


--
-- Name: COLUMN transfer_out_record.document_title; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.document_title IS '文档标题';


--
-- Name: COLUMN transfer_out_record.document_status; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.document_status IS '文档状态';


--
-- Name: COLUMN transfer_out_record.submitter; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.submitter IS '文档提交人';


--
-- Name: COLUMN transfer_out_record.submitter_id; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.submitter_id IS '文档提交人ID';


--
-- Name: COLUMN transfer_out_record.submit_datetime; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.submit_datetime IS '文档提交时间';


--
-- Name: COLUMN transfer_out_record.inpat_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.inpat_no IS '住院号';


--
-- Name: COLUMN transfer_out_record.mr_no; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.mr_no IS '病案号';


--
-- Name: COLUMN transfer_out_record.name; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.name IS '患者姓名';


--
-- Name: COLUMN transfer_out_record.sex; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.sex IS '患者性别';


--
-- Name: COLUMN transfer_out_record.age_year; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.age_year IS '年龄(年)';


--
-- Name: COLUMN transfer_out_record.age_month; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.age_month IS '年龄(月)';


--
-- Name: COLUMN transfer_out_record.age; Type: COMMENT; Schema: cdm; Owner: -
--

COMMENT ON COLUMN cdm.transfer_out_record.age IS '年龄-非结构化';


--
-- Name: ai_frontpage_draft id; Type: DEFAULT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.ai_frontpage_draft ALTER COLUMN id SET DEFAULT nextval('cdm.ai_frontpage_draft_id_seq'::regclass);


--
-- Name: admission_record admission_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.admission_record
    ADD CONSTRAINT admission_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id);


--
-- Name: ai_diagnosis_snapshot ai_diagnosis_snapshot_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.ai_diagnosis_snapshot
    ADD CONSTRAINT ai_diagnosis_snapshot_pkey PRIMARY KEY (id);


--
-- Name: ai_frontpage_draft ai_frontpage_draft_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.ai_frontpage_draft
    ADD CONSTRAINT ai_frontpage_draft_pkey PRIMARY KEY (id);


--
-- Name: ai_mr_cost_snapshot ai_mr_cost_snapshot_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.ai_mr_cost_snapshot
    ADD CONSTRAINT ai_mr_cost_snapshot_pkey PRIMARY KEY (id);


--
-- Name: ai_mr_snapshot ai_mr_snapshot_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.ai_mr_snapshot
    ADD CONSTRAINT ai_mr_snapshot_pkey PRIMARY KEY (id);


--
-- Name: ai_mr_surgery_snapshot ai_mr_surgery_snapshot_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.ai_mr_surgery_snapshot
    ADD CONSTRAINT ai_mr_surgery_snapshot_pkey PRIMARY KEY (id);


--
-- Name: anesthesia_record anesthesia_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.anesthesia_record
    ADD CONSTRAINT anesthesia_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: blood_application blood_application_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.blood_application
    ADD CONSTRAINT blood_application_pkey PRIMARY KEY (institute_id, patient_id, visit_id, application_id);


--
-- Name: bloodtrans_record bloodtrans_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.bloodtrans_record
    ADD CONSTRAINT bloodtrans_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: consent_form consent_form_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.consent_form
    ADD CONSTRAINT consent_form_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: consultation_record consultation_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.consultation_record
    ADD CONSTRAINT consultation_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: crisis_value_record crisis_value_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.crisis_value_record
    ADD CONSTRAINT crisis_value_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: daily_admission_record daily_admission_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.daily_admission_record
    ADD CONSTRAINT daily_admission_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: daily_course_record daily_course_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.daily_course_record
    ADD CONSTRAINT daily_course_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: daily_death_record daily_death_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.daily_death_record
    ADD CONSTRAINT daily_death_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: death_discussion death_discussion_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.death_discussion
    ADD CONSTRAINT death_discussion_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: death_record death_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.death_record
    ADD CONSTRAINT death_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: diagnosis diagnosis_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.diagnosis
    ADD CONSTRAINT diagnosis_pkey PRIMARY KEY (institute_id, patient_id, visit_id, diagnosis_id);


--
-- Name: diffcase_discussion_record diffcase_discussion_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.diffcase_discussion_record
    ADD CONSTRAINT diffcase_discussion_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: discharge_record discharge_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.discharge_record
    ADD CONSTRAINT discharge_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id);


--
-- Name: docpat_commu_record docpat_commu_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.docpat_commu_record
    ADD CONSTRAINT docpat_commu_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: epidemic_record epidemic_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.epidemic_record
    ADD CONSTRAINT epidemic_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: exam_item_report exam_item_report_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.exam_item_report
    ADD CONSTRAINT exam_item_report_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: first_course_record first_course_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.first_course_record
    ADD CONSTRAINT first_course_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: frontpage_extracted_fields frontpage_extracted_fields_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.frontpage_extracted_fields
    ADD CONSTRAINT frontpage_extracted_fields_pkey PRIMARY KEY (id);


--
-- Name: frontpage_extraction_audit frontpage_extraction_audit_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.frontpage_extraction_audit
    ADD CONSTRAINT frontpage_extraction_audit_pkey PRIMARY KEY (id);


--
-- Name: handoff_record handoff_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.handoff_record
    ADD CONSTRAINT handoff_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: handover_record handover_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.handover_record
    ADD CONSTRAINT handover_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: hospitalization_status_projection hospitalization_status_projection_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.hospitalization_status_projection
    ADD CONSTRAINT hospitalization_status_projection_pkey PRIMARY KEY (institute_id, patient_id, visit_id);


--
-- Name: inpat_bill_item inpat_bill_item_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.inpat_bill_item
    ADD CONSTRAINT inpat_bill_item_pkey PRIMARY KEY (institute_id, patient_id, visit_id, bill_item_id);


--
-- Name: inpat_drug_order inpat_drug_order_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.inpat_drug_order
    ADD CONSTRAINT inpat_drug_order_pkey PRIMARY KEY (institute_id, patient_id, visit_id, order_id);


--
-- Name: inpat_nondrug_order inpat_nondrug_order_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.inpat_nondrug_order
    ADD CONSTRAINT inpat_nondrug_order_pkey PRIMARY KEY (institute_id, patient_id, visit_id, order_id);


--
-- Name: inpat_registration inpat_registration_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.inpat_registration
    ADD CONSTRAINT inpat_registration_pkey PRIMARY KEY (institute_id, patient_id, visit_id);


--
-- Name: labtest_item labtest_item_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.labtest_item
    ADD CONSTRAINT labtest_item_pkey PRIMARY KEY (institute_id, patient_id, visit_id, test_id, test_item_id);


--
-- Name: labtest_item_report labtest_item_report_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.labtest_item_report
    ADD CONSTRAINT labtest_item_report_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: labtest_master labtest_master_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.labtest_master
    ADD CONSTRAINT labtest_master_pkey PRIMARY KEY (institute_id, patient_id, visit_id, test_id);


--
-- Name: medical_documents medical_documents_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.medical_documents
    ADD CONSTRAINT medical_documents_pkey PRIMARY KEY (id);


--
-- Name: medical_insurance_settlement_cost medical_insurance_settlement_cost_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.medical_insurance_settlement_cost
    ADD CONSTRAINT medical_insurance_settlement_cost_pkey PRIMARY KEY (institute_id, patient_id, visit_id, medinsur_serial_item_id);


--
-- Name: medical_insurance_settlement medical_insurance_settlement_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.medical_insurance_settlement
    ADD CONSTRAINT medical_insurance_settlement_pkey PRIMARY KEY (institute_id, patient_id, visit_id);


--
-- Name: medinsur_receipt medinsur_receipt_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.medinsur_receipt
    ADD CONSTRAINT medinsur_receipt_pkey PRIMARY KEY (institute_id, patient_id, visit_id, medinsur_receipt_id);


--
-- Name: mr_bloodtrans mr_bloodtrans_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.mr_bloodtrans
    ADD CONSTRAINT mr_bloodtrans_pkey PRIMARY KEY (institute_id, patient_id, visit_id, bloodtrans_id);


--
-- Name: mr_cost mr_cost_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.mr_cost
    ADD CONSTRAINT mr_cost_pkey PRIMARY KEY (institute_id, patient_id, visit_id);


--
-- Name: mr_customize mr_customize_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.mr_customize
    ADD CONSTRAINT mr_customize_pkey PRIMARY KEY (institute_id, patient_id, visit_id);


--
-- Name: mr_icu mr_icu_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.mr_icu
    ADD CONSTRAINT mr_icu_pkey PRIMARY KEY (institute_id, patient_id, visit_id, icu_id);


--
-- Name: mr mr_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.mr
    ADD CONSTRAINT mr_pkey PRIMARY KEY (institute_id, patient_id, visit_id);


--
-- Name: mr_surgery mr_surgery_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.mr_surgery
    ADD CONSTRAINT mr_surgery_pkey PRIMARY KEY (institute_id, patient_id, visit_id, surgery_id);


--
-- Name: newborn_record newborn_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.newborn_record
    ADD CONSTRAINT newborn_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: nursing_record nursing_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.nursing_record
    ADD CONSTRAINT nursing_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: outpat_record outpat_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.outpat_record
    ADD CONSTRAINT outpat_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: pathology_exam_master pathology_exam_master_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.pathology_exam_master
    ADD CONSTRAINT pathology_exam_master_pkey PRIMARY KEY (institute_id, patient_id, visit_id, pathology_exam_id);


--
-- Name: pathology_exam_report pathology_exam_report_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.pathology_exam_report
    ADD CONSTRAINT pathology_exam_report_pkey PRIMARY KEY (institute_id, patient_id, visit_id, pathology_exam_id);


--
-- Name: patient_information patient_information_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.patient_information
    ADD CONSTRAINT patient_information_pkey PRIMARY KEY (institute_id, patient_id);


--
-- Name: postane_surveil_record postane_surveil_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.postane_surveil_record
    ADD CONSTRAINT postane_surveil_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: postsurg_firstcourse_record postsurg_firstcourse_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.postsurg_firstcourse_record
    ADD CONSTRAINT postsurg_firstcourse_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: preane_surveil_record preane_surveil_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.preane_surveil_record
    ADD CONSTRAINT preane_surveil_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: presurg_discussion presurg_discussion_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.presurg_discussion
    ADD CONSTRAINT presurg_discussion_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: presurg_summary presurg_summary_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.presurg_summary
    ADD CONSTRAINT presurg_summary_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: rescue_record rescue_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.rescue_record
    ADD CONSTRAINT rescue_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: senior_course_record senior_course_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.senior_course_record
    ADD CONSTRAINT senior_course_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: summary_record summary_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.summary_record
    ADD CONSTRAINT summary_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: surgery_application surgery_application_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.surgery_application
    ADD CONSTRAINT surgery_application_pkey PRIMARY KEY (institute_id, patient_id, visit_id, application_id);


--
-- Name: surgery_inform_consent surgery_inform_consent_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.surgery_inform_consent
    ADD CONSTRAINT surgery_inform_consent_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: surgery_inventory_record surgery_inventory_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.surgery_inventory_record
    ADD CONSTRAINT surgery_inventory_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: surgery_record surgery_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.surgery_record
    ADD CONSTRAINT surgery_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: surgery_risk_assessment surgery_risk_assessment_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.surgery_risk_assessment
    ADD CONSTRAINT surgery_risk_assessment_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: surgery_safecheck_record surgery_safecheck_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.surgery_safecheck_record
    ADD CONSTRAINT surgery_safecheck_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: transfer_in_record transfer_in_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.transfer_in_record
    ADD CONSTRAINT transfer_in_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: transfer_out_record transfer_out_record_pkey; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.transfer_out_record
    ADD CONSTRAINT transfer_out_record_pkey PRIMARY KEY (institute_id, patient_id, visit_id, document_id);


--
-- Name: ai_mr_cost_snapshot uq_ai_cost_snapshot_visit; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.ai_mr_cost_snapshot
    ADD CONSTRAINT uq_ai_cost_snapshot_visit UNIQUE (visit_id);


--
-- Name: ai_mr_snapshot uq_ai_mr_snapshot_visit_version; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.ai_mr_snapshot
    ADD CONSTRAINT uq_ai_mr_snapshot_visit_version UNIQUE (visit_id, snapshot_version);


--
-- Name: frontpage_extraction_audit uq_frontpage_audit_visit_version; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.frontpage_extraction_audit
    ADD CONSTRAINT uq_frontpage_audit_visit_version UNIQUE (visit_id, frontpage_version);


--
-- Name: frontpage_extracted_fields uq_frontpage_field_visit_version_path; Type: CONSTRAINT; Schema: cdm; Owner: -
--

ALTER TABLE ONLY cdm.frontpage_extracted_fields
    ADD CONSTRAINT uq_frontpage_field_visit_version_path UNIQUE (visit_id, frontpage_version, field_path);


--
-- Name: ix_ai_cost_snapshot_snapshot; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_ai_cost_snapshot_snapshot ON cdm.ai_mr_cost_snapshot USING btree (snapshot_id);


--
-- Name: ix_ai_diag_snapshot_main; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_ai_diag_snapshot_main ON cdm.ai_diagnosis_snapshot USING btree (is_main);


--
-- Name: ix_ai_diag_snapshot_snapshot; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_ai_diag_snapshot_snapshot ON cdm.ai_diagnosis_snapshot USING btree (snapshot_id);


--
-- Name: ix_ai_diag_snapshot_visit; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_ai_diag_snapshot_visit ON cdm.ai_diagnosis_snapshot USING btree (visit_id);


--
-- Name: ix_ai_draft_patient; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_ai_draft_patient ON cdm.ai_frontpage_draft USING btree (patient_id);


--
-- Name: ix_ai_draft_visit; Type: INDEX; Schema: cdm; Owner: -
--

CREATE UNIQUE INDEX ix_ai_draft_visit ON cdm.ai_frontpage_draft USING btree (visit_id);


--
-- Name: ix_ai_mr_snapshot_created_at; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_ai_mr_snapshot_created_at ON cdm.ai_mr_snapshot USING btree (created_at);


--
-- Name: ix_ai_mr_snapshot_patient; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_ai_mr_snapshot_patient ON cdm.ai_mr_snapshot USING btree (patient_id);


--
-- Name: ix_ai_mr_snapshot_status; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_ai_mr_snapshot_status ON cdm.ai_mr_snapshot USING btree (status);


--
-- Name: ix_ai_surgery_snapshot_main; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_ai_surgery_snapshot_main ON cdm.ai_mr_surgery_snapshot USING btree (is_main);


--
-- Name: ix_ai_surgery_snapshot_snapshot; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_ai_surgery_snapshot_snapshot ON cdm.ai_mr_surgery_snapshot USING btree (snapshot_id);


--
-- Name: ix_ai_surgery_snapshot_visit; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_ai_surgery_snapshot_visit ON cdm.ai_mr_surgery_snapshot USING btree (visit_id);


--
-- Name: ix_consent_form_visit_type; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_consent_form_visit_type ON cdm.consent_form USING btree (institute_id, patient_id, visit_id, consent_type);


--
-- Name: ix_diag_code; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_diag_code ON cdm.diagnosis USING btree (diagnosis_code);


--
-- Name: ix_diag_type; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_diag_type ON cdm.diagnosis USING btree (diagnosis_type);


--
-- Name: ix_diag_visit; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_diag_visit ON cdm.diagnosis USING btree (institute_id, patient_id, visit_id);


--
-- Name: ix_diagnosis_diagnosis_code; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_diagnosis_diagnosis_code ON cdm.diagnosis USING btree (diagnosis_code);


--
-- Name: ix_diagnosis_diagnosis_type; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_diagnosis_diagnosis_type ON cdm.diagnosis USING btree (diagnosis_type);


--
-- Name: ix_frontpage_audit_created_at; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_frontpage_audit_created_at ON cdm.frontpage_extraction_audit USING btree (created_at);


--
-- Name: ix_frontpage_audit_draft; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_frontpage_audit_draft ON cdm.frontpage_extraction_audit USING btree (draft_id);


--
-- Name: ix_frontpage_audit_patient; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_frontpage_audit_patient ON cdm.frontpage_extraction_audit USING btree (patient_id);


--
-- Name: ix_frontpage_audit_status; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_frontpage_audit_status ON cdm.frontpage_extraction_audit USING btree (status);


--
-- Name: ix_frontpage_field_created_at; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_frontpage_field_created_at ON cdm.frontpage_extracted_fields USING btree (created_at);


--
-- Name: ix_frontpage_field_key; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_frontpage_field_key ON cdm.frontpage_extracted_fields USING btree (field_key);


--
-- Name: ix_frontpage_field_module; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_frontpage_field_module ON cdm.frontpage_extracted_fields USING btree (module_name);


--
-- Name: ix_frontpage_field_patient; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_frontpage_field_patient ON cdm.frontpage_extracted_fields USING btree (patient_id);


--
-- Name: ix_hospitalization_status_verified; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_hospitalization_status_verified ON cdm.hospitalization_status_projection USING btree (status, verified_at);


--
-- Name: ix_inpat_registration_admission_datetime; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_inpat_registration_admission_datetime ON cdm.inpat_registration USING btree (admission_datetime);


--
-- Name: ix_inpat_registration_discharge_datetime; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_inpat_registration_discharge_datetime ON cdm.inpat_registration USING btree (discharge_datetime);


--
-- Name: ix_inpat_registration_inpat_no; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_inpat_registration_inpat_no ON cdm.inpat_registration USING btree (inpat_no);


--
-- Name: ix_inpat_registration_mr_no; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_inpat_registration_mr_no ON cdm.inpat_registration USING btree (mr_no);


--
-- Name: ix_medical_documents_qc_status; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_medical_documents_qc_status ON cdm.medical_documents USING btree (qc_status);


--
-- Name: ix_medical_documents_record; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_medical_documents_record ON cdm.medical_documents USING btree (record_id);


--
-- Name: ix_medical_documents_status; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_medical_documents_status ON cdm.medical_documents USING btree (status);


--
-- Name: ix_mr_admission; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_mr_admission ON cdm.mr USING btree (admission_datetime);


--
-- Name: ix_mr_dept; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_mr_dept ON cdm.mr USING btree (discharge_dept_name);


--
-- Name: ix_mr_discharge; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_mr_discharge ON cdm.mr USING btree (discharge_datetime);


--
-- Name: ix_mr_local_sync_completed_at; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_mr_local_sync_completed_at ON cdm.mr USING btree (local_sync_completed_at);


--
-- Name: ix_mr_surgery_surgery_code; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_mr_surgery_surgery_code ON cdm.mr_surgery USING btree (surgery_code);


--
-- Name: ix_patient_information_id_card_no; Type: INDEX; Schema: cdm; Owner: -
--

CREATE INDEX ix_patient_information_id_card_no ON cdm.patient_information USING btree (id_card_no);


--
-- PostgreSQL database dump complete
--
