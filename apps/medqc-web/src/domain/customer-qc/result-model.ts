export type CustomerQcDecisionStatus =
  | 'compliant'
  | 'non_compliant'
  | 'not_applicable'
  | 'data_gap'
  | 'evaluation_unknown'
  | 'technical_error'

export type CustomerQcEvidenceAvailability = 'available' | 'missing' | 'unavailable' | 'unknown'

export type CustomerQcEvidenceKind =
  | 'admission_record'
  | 'surgery_record'
  | 'pre_surgery_summary'
  | 'surgery_safecheck_record'
  | 'discharge_record'
  | 'other'

export interface CustomerQcEvidenceSource {
  kind: CustomerQcEvidenceKind
  label: string
  /** 仅允许受控结构化字段名，用于病历章节定位；不得承载原文。 */
  fieldPath?: string
}

export interface CustomerQcDisplay {
  statusLabel: string
  statusTone: 'success' | 'danger' | 'warning' | 'muted' | 'info'
  summary: string
  detail?: string
  requirement?: string
  actualValue?: string
  evidenceSources: CustomerQcEvidenceSource[]
  suggestion: string
}

/**
 * 客户展示专用领域模型。
 *
 * 此模型只能包含状态、受控原因码和白名单事实；不得保留原始病历正文、模型输入输出或内部追踪数据。
 */
export interface CustomerQcResult {
  ruleId: string
  decisionStatus: CustomerQcDecisionStatus
  evidenceAvailability: CustomerQcEvidenceAvailability
  reasonCode?: string
  display: CustomerQcDisplay
}

/** 原始接口结果的最小读取契约；规范化后不会向客户展示保留该对象。 */
export interface RawCustomerQcResult {
  schema_version?: unknown
  explanation_contract_version?: unknown
  rule_id?: unknown
  rule_code?: unknown
  qc_point_id?: unknown
  status?: unknown
  result_status?: unknown
  canonical_status?: unknown
  display_status?: unknown
  reason_code?: unknown
  criterion_results?: unknown
  customer_display_facts?: Record<string, unknown> | null
  conclusion?: unknown
  detail?: unknown
  requirement?: unknown
  evidence_problem_type?: unknown
  findings?: unknown
  evidence?: unknown
  suggestion?: unknown
  metadata?: Record<string, unknown> | null
  decision?: Record<string, unknown> | null
  evidence_payload?: unknown
  medical_text?: unknown
  raw_response?: unknown
  prompt?: unknown
  [key: string]: unknown
}

export interface CustomerDisplayFacts {
  complaintLength?: number
  primaryDiagnosisAvailable?: boolean
  diagnosticRelationState?: 'supported' | 'unsupported' | 'mismatch' | 'unknown'
  diagnosticReasonDimensions?: Array<
    'anatomic_site' | 'laterality' | 'symptom_pattern' | 'disease_course' | 'disease_direction'
  >
  diagnosticRationaleCode?:
    | 'symptom_only'
    | 'site_symptom_not_specific'
    | 'diagnosis_mismatch'
    | 'insufficient_information'
    | 'supported'
  lengthState?: 'satisfied' | 'violated' | 'unknown'
  missingFields?: Array<
    | 'implant_name'
    | 'implant_type'
    | 'implant_specification'
    | 'implant_material'
    | 'implant_quantity'
  >
  implantEvents?: Array<{
    eventPosition: number
    missingFields: Array<
      | 'implant_name'
      | 'implant_type'
      | 'implant_specification'
      | 'implant_material'
      | 'implant_quantity'
    >
    implantNames: string[]
  }>
  implantVerification?: {
    state: 'complete' | 'not_used'
    checkedFields?: Array<
      | 'implant_name'
      | 'implant_type'
      | 'implant_specification'
      | 'implant_material'
      | 'implant_quantity'
    >
  }
  copySimilarity?: number
  copySimilarityThreshold?: number
  copyDocuments?: Array<{
    source: 'daily_course_record' | 'senior_course_record'
    recordTime: string
  }>
  courseInterval?: {
    startSource: 'daily_course_record' | 'senior_course_record'
    endSource: 'daily_course_record' | 'senior_course_record'
    startTime: string
    endTime: string
    hours: number
    thresholdHours: number
  }
  pathologySampling?: {
    triggerSources: Array<'pathology_exam_master' | 'pathology_exam_report'>
    checkedSources: Array<{
      source: 'surgery_record' | 'daily_course_record'
      state: 'present' | 'empty'
    }>
  }
  lymphNodeDocumentation?: {
    checkedSources: Array<'surgery_record' | 'pathology_exam_master' | 'pathology_exam_report'>
  }
  prophylaxisDuration?: {
    failureKind: 'prophylaxis_duration_over_48h' | 'prophylaxis_extension_reason_missing'
    incisionClass: 'I' | 'II'
    startTime: string
    endTime: string
    durationHours: number
    thresholdHours: 24 | 48
  }
  anesthesiaDocumentation?: {
    failureKind?:
      | 'anesthesia_consent_missing'
      | 'anesthesia_consent_incomplete'
      | 'anesthesia_visit_missing'
      | 'anesthesia_record_missing'
      | 'preop_discussion_missing'
      | 'surgeon_not_in_preop_discussion'
    verificationKind?:
      | 'anesthesia_consent_present'
      | 'anesthesia_consent_complete'
      | 'anesthesia_visits_present'
      | 'anesthesia_record_present'
      | 'preop_discussion_surgeon_participation_confirmed'
    performedEventConfirmed: true
    missingSources?: Array<
      | 'consent_form'
      | 'preane_surveil_record'
      | 'postane_surveil_record'
      | 'anesthesia_record'
      | 'presurg_discussion'
    >
    checkedSources?: Array<
      | 'consent_form'
      | 'preane_surveil_record'
      | 'postane_surveil_record'
      | 'anesthesia_record'
      | 'presurg_discussion'
    >
    missingFields?: Array<
      | 'patient_signature'
      | 'physician_signature'
      | 'patient_signature_time'
      | 'physician_signature_time'
    >
    emergencyRescueExceptionAbsent?: true
    surgeonParticipationState?: 'confirmed' | 'absent'
  }
  surgeryDocument?: {
    target: 'presurg_summary' | 'surgery_record' | 'surgery_safecheck_record'
    state: 'present' | 'missing' | 'blank'
  }
  surgerySignature?: {
    state: 'confirmed' | 'not_qualified'
    firstAssistantExceptionUsed?: boolean
  }
  timeliness?: {
    target:
      | 'admission_record'
      | 'first_course_record'
      | 'rescue_record'
      | 'attending_course_record'
      | 'senior_course_record'
    state: 'missing' | 'late'
    thresholdHours: number
    anchorTime?: string
    anchorDate?: string
    observedTime?: string
    elapsedHours?: number
    sourceLabel: string
  }
  surgeryTimeliness?: {
    state: 'within' | 'late'
    surgeryEndTime: string
    recordTime: string
    elapsedHours: number
    thresholdHours: 24
  }
  surgeryMdt?: {
    procedureKind: 'surgery' | 'non_surgical_operation' | 'none' | 'unknown'
    effectiveLevel?: '一级' | '二级' | '三级' | '四级'
    levelSource?: 'hospital_performance' | 'national_catalog' | 'structured_field'
    discussionState?: 'completed' | 'missing' | 'unknown'
    procedureCode?: string
    procedureName?: string
  }
  surgeryConsent?: {
    state: 'complete' | 'missing' | 'blank' | 'signature_missing' | 'source_unproven'
    missingSignatureRoles?: Array<'patient' | 'surgeon'>
  }
  severityCourseGap?: {
    severity: 'serious'
    anchorDate: string
    horizonDate: string
    gapStartDate: string
    gapEndDate: string
    gapDays: number
    thresholdDays: 2
  }
  criticalDailyCoverage?: {
    anchorDate?: string
    horizonDate?: string
    missingDates: string[]
    missingCount: number
    missingFirstDate: string
    missingLastDate: string
  }
  examLab?: {
    subject: 'ct_mri' | 'culture_susceptibility'
    requirement:
      | 'reason_before_order'
      | 'result_recording_within_24h'
      | 'positive_result_analysis_within_24h'
    eventPhase: 'order' | 'report'
    checkedSources: Array<'exam_lab_order' | 'exam_lab_report' | 'course_record'>
  }
  transfusion?: {
    requirement:
      | 'pretransfusion_assessment'
      | 'purpose_or_indication'
      | 'posttransfusion_evaluation'
      | 'postop_first_course_transfusion'
    checkedSources: Array<
      | 'bloodtrans_record'
      | 'blood_application'
      | 'course_record'
      | 'surgery_record'
      | 'postsurg_firstcourse_record'
    >
  }
  standard?: string
  failureKind?: string
  source?: CustomerQcEvidenceSource
}
