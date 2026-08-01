import {
  buildCustomerDisplay,
  resolveCustomerReason,
  type CustomerReasonDescriptor,
} from './reason-catalog'
import type {
  CustomerDisplayFacts,
  CustomerQcEvidenceSource,
  CustomerQcResult,
  RawCustomerQcResult,
} from './result-model'
import { resolveCustomerQcStatus, resolveEvidenceAvailability } from './status-policy'

const SAFE_RESULT_SCHEMA = 'customer-qc-result-v1'
const SAFE_EXPLANATION_CONTRACT = 'lx0609-customer-explanation-v1'
const FORBIDDEN_PLACEHOLDERS = new Set([
  '发现该质控点对应的明确问题。',
  '请按质控要求补充或修正。',
  '发现质控问题',
  '受控证据表明本次记录未满足质控要求。',
])

const SAFE_SOURCE_LABELS: Record<string, CustomerQcEvidenceSource> = {
  '入院记录—主诉': {
    kind: 'admission_record',
    label: '入院记录—主诉',
    fieldPath: 'chief_complaint',
  },
  '入院记录—主诉字段': {
    kind: 'admission_record',
    label: '入院记录—主诉字段',
    fieldPath: 'chief_complaint',
  },
  手术记录: { kind: 'surgery_record', label: '手术记录' },
  术前小结: { kind: 'pre_surgery_summary', label: '术前小结' },
  出院记录: { kind: 'discharge_record', label: '出院记录' },
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined
}

function asSafeInteger(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= 10000
    ? value
    : undefined
}

function sourceFromLabel(value: unknown): CustomerQcEvidenceSource | undefined {
  const label = asString(value)
  return label ? SAFE_SOURCE_LABELS[label] : undefined
}

const COPY_DOCUMENT_LABELS = {
  daily_course_record: '日常病程记录',
  senior_course_record: '上级医师查房记录',
} as const

const PATHOLOGY_SOURCE_LABELS = {
  pathology_exam_master: '病理检查主表',
  pathology_exam_report: '病理检查报告',
  surgery_record: '手术记录',
  daily_course_record: '日常病程记录',
} as const

const EXAM_LAB_SOURCE_LABELS = {
  exam_lab_order: '检查/检验医嘱',
  exam_lab_report: '检查/检验报告',
  course_record: '日常病程记录及上级医师查房记录',
} as const

const TRANSFUSION_SOURCE_LABELS = {
  bloodtrans_record: '输血记录',
  blood_application: '输血申请/评估文书',
  course_record: '日常病程记录及上级医师查房记录',
  surgery_record: '手术记录',
  postsurg_firstcourse_record: '术后首次病程记录',
} as const

const ANESTHESIA_SOURCE_LABELS = {
  consent_form: '麻醉知情同意书',
  preane_surveil_record: '麻醉术前访视记录',
  postane_surveil_record: '麻醉术后访视记录',
  presurg_discussion: '术前讨论记录',
} as const

const TIMELINESS_TARGET_LABELS = {
  admission_record: '入院记录',
  first_course_record: '首次病程记录',
  rescue_record: '抢救记录',
  attending_course_record: '主治医师及以上首次查房记录',
  senior_course_record: '副主任医师或主任医师首次查房记录',
} as const

function asSafeDateTime(value: unknown): string | undefined {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(value)
    ? value
    : undefined
}

function asSafeDate(value: unknown): string | undefined {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : undefined
}

function extractTimeliness(facts: Record<string, unknown>): CustomerDisplayFacts['timeliness'] {
  const target = facts.target_document
  const state = facts.timeliness_state
  const thresholdHours = facts.threshold_hours
  const sourceLabel = asString(facts.source_label)
  if (
    facts.failure_kind !== 'timeliness_requirement_not_met' ||
    (target !== 'admission_record' &&
      target !== 'first_course_record' &&
      target !== 'rescue_record' &&
      target !== 'attending_course_record' &&
      target !== 'senior_course_record') ||
    (state !== 'missing' && state !== 'late') ||
    typeof thresholdHours !== 'number' ||
    !Number.isInteger(thresholdHours) ||
    thresholdHours <= 0 ||
    !sourceLabel
  )
    return undefined
  const anchorTime = asSafeDateTime(facts.anchor_time)
  const anchorDate = asSafeDate(facts.anchor_date)
  const observedTime = asSafeDateTime(facts.observed_time)
  const elapsedHours =
    typeof facts.elapsed_hours === 'number' &&
    Number.isFinite(facts.elapsed_hours) &&
    facts.elapsed_hours >= 0
      ? facts.elapsed_hours
      : undefined
  if (
    state === 'late' &&
    ((!anchorTime && !anchorDate) || !observedTime || elapsedHours === undefined)
  ) {
    return undefined
  }
  return {
    target,
    state,
    thresholdHours,
    sourceLabel,
    ...(anchorTime ? { anchorTime } : {}),
    ...(anchorDate ? { anchorDate } : {}),
    ...(observedTime ? { observedTime } : {}),
    ...(elapsedHours === undefined ? {} : { elapsedHours }),
  }
}

function extractSurgeryTimeliness(
  facts: Record<string, unknown>,
): CustomerDisplayFacts['surgeryTimeliness'] {
  const surgeryEndTime = asSafeDateTime(facts.surgery_end_time)
  const recordTime = asSafeDateTime(facts.record_time)
  const elapsedHours =
    typeof facts.elapsed_hours === 'number' &&
    Number.isFinite(facts.elapsed_hours) &&
    facts.elapsed_hours > 24
      ? facts.elapsed_hours
      : undefined
  if (
    facts.failure_kind !== 'surgery_record_late' ||
    facts.performed_surgery_confirmed !== true ||
    !surgeryEndTime ||
    !recordTime ||
    elapsedHours === undefined ||
    facts.threshold_hours !== 24
  )
    return undefined
  return { surgeryEndTime, recordTime, elapsedHours, thresholdHours: 24 }
}

function extractSurgeryConsent(
  facts: Record<string, unknown>,
): CustomerDisplayFacts['surgeryConsent'] {
  const state = facts.consent_state
  if (
    state !== 'missing' &&
    state !== 'blank' &&
    state !== 'signature_missing' &&
    state !== 'source_unproven'
  )
    return undefined
  const valid =
    (facts.failure_kind === 'surgery_consent_document_missing' && state === 'missing') ||
    (facts.failure_kind === 'surgery_consent_body_missing' && state === 'blank') ||
    (facts.failure_kind === 'surgery_consent_signature_missing' && state === 'signature_missing') ||
    (facts.failure_kind === 'surgery_consent_source_unproven' && state === 'source_unproven')
  if (!valid || facts.performed_surgery_confirmed !== true) return undefined
  const missingSignatureRoles = Array.isArray(facts.missing_signature_roles)
    ? facts.missing_signature_roles.filter(
        (value): value is 'patient' | 'surgeon' => value === 'patient' || value === 'surgeon',
      )
    : undefined
  if (state === 'signature_missing' && !missingSignatureRoles?.length) return undefined
  return {
    state,
    ...(missingSignatureRoles?.length ? { missingSignatureRoles } : {}),
  }
}

function extractSeverityCourseGap(
  facts: Record<string, unknown>,
): CustomerDisplayFacts['severityCourseGap'] {
  const anchorDate = asSafeDate(facts.anchor_date)
  const horizonDate = asSafeDate(facts.horizon_date)
  const gapStartDate = asSafeDate(facts.gap_start_date)
  const gapEndDate = asSafeDate(facts.gap_end_date)
  const gapDays = facts.gap_days
  if (
    facts.failure_kind !== 'severity_course_gap_exceeded' ||
    facts.severity !== 'serious' ||
    facts.threshold_days !== 2 ||
    !anchorDate ||
    !horizonDate ||
    !gapStartDate ||
    !gapEndDate ||
    typeof gapDays !== 'number' ||
    !Number.isInteger(gapDays) ||
    gapDays <= 2
  )
    return undefined
  return {
    anchorDate,
    horizonDate,
    gapStartDate,
    gapEndDate,
    gapDays,
    thresholdDays: 2,
    severity: 'serious',
  }
}

function extractCriticalDailyCoverage(
  facts: Record<string, unknown>,
): CustomerDisplayFacts['criticalDailyCoverage'] {
  const missingDates = Array.isArray(facts.missing_dates)
    ? facts.missing_dates.filter((value): value is string => asSafeDate(value) !== undefined)
    : []
  const missingCount = facts.missing_count
  const missingFirstDate = asSafeDate(facts.missing_first_date)
  const missingLastDate = asSafeDate(facts.missing_last_date)
  if (
    facts.failure_kind !== 'critical_daily_record_missing' ||
    facts.severity !== 'critical' ||
    !missingDates.length ||
    missingDates.length > 7 ||
    typeof missingCount !== 'number' ||
    !Number.isInteger(missingCount) ||
    missingCount < missingDates.length ||
    !missingFirstDate ||
    !missingLastDate
  )
    return undefined
  const anchorDate = asSafeDate(facts.anchor_date)
  const horizonDate = asSafeDate(facts.horizon_date)
  return {
    missingDates,
    missingCount,
    missingFirstDate,
    missingLastDate,
    ...(anchorDate ? { anchorDate } : {}),
    ...(horizonDate ? { horizonDate } : {}),
  }
}

function extractCopyDocuments(
  facts: Record<string, unknown>,
): CustomerDisplayFacts['copyDocuments'] {
  const sources = facts.copy_document_sources
  const recordTimes = facts.copy_document_record_times
  if (
    !Array.isArray(sources) ||
    !Array.isArray(recordTimes) ||
    sources.length !== 2 ||
    recordTimes.length !== 2
  ) {
    return undefined
  }
  const documents = sources.flatMap((source, index) => {
    if (
      (source !== 'daily_course_record' && source !== 'senior_course_record') ||
      typeof recordTimes[index] !== 'string' ||
      !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(recordTimes[index])
    )
      return []
    return [{ source, recordTime: recordTimes[index] }]
  })
  return documents.length === 2 ? documents : undefined
}

function extractCourseInterval(
  facts: Record<string, unknown>,
): CustomerDisplayFacts['courseInterval'] {
  const startSource = facts.interval_start_source
  const endSource = facts.interval_end_source
  const startTime = facts.interval_start_time
  const endTime = facts.interval_end_time
  const hours = facts.interval_hours
  const thresholdHours = facts.threshold_hours
  if (
    (startSource !== 'daily_course_record' && startSource !== 'senior_course_record') ||
    (endSource !== 'daily_course_record' && endSource !== 'senior_course_record') ||
    typeof startTime !== 'string' ||
    typeof endTime !== 'string' ||
    !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(startTime) ||
    !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(endTime) ||
    typeof hours !== 'number' ||
    !Number.isFinite(hours) ||
    hours <= 72 ||
    thresholdHours !== 72
  )
    return undefined
  return { startSource, endSource, startTime, endTime, hours, thresholdHours }
}

function extractPathologySampling(
  facts: Record<string, unknown>,
): CustomerDisplayFacts['pathologySampling'] {
  const triggers = facts.pathology_trigger_sources
  const checked = facts.checked_target_sources
  if (!Array.isArray(triggers) || !Array.isArray(checked) || checked.length !== 2) return undefined
  const triggerSources = triggers.filter(
    (source): source is 'pathology_exam_master' | 'pathology_exam_report' =>
      source === 'pathology_exam_master' || source === 'pathology_exam_report',
  )
  const checkedSources = checked.flatMap(
    (candidate): NonNullable<CustomerDisplayFacts['pathologySampling']>['checkedSources'] => {
      if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) return []
      const row = candidate as Record<string, unknown>
      if (
        (row.source !== 'surgery_record' && row.source !== 'daily_course_record') ||
        (row.state !== 'present' && row.state !== 'empty')
      )
        return []
      return [{ source: row.source, state: row.state }]
    },
  )
  if (!triggerSources.length || checkedSources.length !== 2) return undefined
  return { triggerSources, checkedSources }
}

function extractExamLab(facts: Record<string, unknown>): CustomerDisplayFacts['examLab'] {
  const subject = facts.subject
  const requirement = facts.requirement
  const eventPhase = facts.event_phase
  const checkedSources = Array.isArray(facts.checked_sources)
    ? facts.checked_sources.filter(
        (value): value is 'exam_lab_order' | 'exam_lab_report' | 'course_record' =>
          value === 'exam_lab_order' || value === 'exam_lab_report' || value === 'course_record',
      )
    : []
  if (
    facts.failure_kind !== 'exam_lab_requirement_not_documented' ||
    (subject !== 'ct_mri' && subject !== 'culture_susceptibility') ||
    (requirement !== 'reason_before_order' &&
      requirement !== 'result_recording_within_24h' &&
      requirement !== 'positive_result_analysis_within_24h') ||
    (eventPhase !== 'order' && eventPhase !== 'report') ||
    checkedSources.length !== 2
  )
    return undefined
  return { subject, requirement, eventPhase, checkedSources }
}

function extractTransfusion(facts: Record<string, unknown>): CustomerDisplayFacts['transfusion'] {
  const requirement = facts.requirement
  const checkedSources = Array.isArray(facts.checked_sources)
    ? facts.checked_sources.filter(
        (
          value,
        ): value is NonNullable<CustomerDisplayFacts['transfusion']>['checkedSources'][number] =>
          value === 'bloodtrans_record' ||
          value === 'blood_application' ||
          value === 'course_record' ||
          value === 'surgery_record' ||
          value === 'postsurg_firstcourse_record',
      )
    : []
  if (
    facts.failure_kind !== 'transfusion_requirement_not_documented' ||
    (requirement !== 'pretransfusion_assessment' &&
      requirement !== 'purpose_or_indication' &&
      requirement !== 'posttransfusion_evaluation' &&
      requirement !== 'postop_first_course_transfusion') ||
    !checkedSources.length
  )
    return undefined
  return { requirement, checkedSources }
}

function extractLymphNodeDocumentation(
  facts: Record<string, unknown>,
): CustomerDisplayFacts['lymphNodeDocumentation'] {
  const checkedSources = Array.isArray(facts.checked_sources)
    ? facts.checked_sources.filter(
        (value): value is 'surgery_record' | 'pathology_exam_master' | 'pathology_exam_report' =>
          value === 'surgery_record' ||
          value === 'pathology_exam_master' ||
          value === 'pathology_exam_report',
      )
    : []
  if (
    facts.failure_kind !== 'lymph_node_dissection_not_documented' ||
    facts.performed_surgery_confirmed !== true ||
    facts.malignant_surgery_confirmed !== true ||
    !checkedSources.length
  )
    return undefined
  return { checkedSources }
}

function extractProphylaxisDuration(
  facts: Record<string, unknown>,
): CustomerDisplayFacts['prophylaxisDuration'] {
  const failureKind = facts.failure_kind
  const incisionClass = facts.incision_class
  const startTime = asSafeDateTime(facts.start_time)
  const endTime = asSafeDateTime(facts.end_time)
  const durationHours = facts.duration_hours
  const thresholdHours = facts.threshold_hours
  if (
    (failureKind !== 'prophylaxis_duration_over_48h' &&
      failureKind !== 'prophylaxis_extension_reason_missing') ||
    (incisionClass !== 'I' && incisionClass !== 'II') ||
    !startTime ||
    !endTime ||
    typeof durationHours !== 'number' ||
    !Number.isFinite(durationHours) ||
    durationHours <= 24 ||
    (thresholdHours !== 24 && thresholdHours !== 48)
  )
    return undefined
  if (
    (failureKind === 'prophylaxis_duration_over_48h' &&
      (thresholdHours !== 48 || durationHours <= 48)) ||
    (failureKind === 'prophylaxis_extension_reason_missing' &&
      (thresholdHours !== 24 || durationHours > 48))
  )
    return undefined
  return {
    failureKind,
    incisionClass,
    startTime,
    endTime,
    durationHours,
    thresholdHours,
  }
}

function extractAnesthesiaDocumentation(
  facts: Record<string, unknown>,
): CustomerDisplayFacts['anesthesiaDocumentation'] {
  const failureKind = facts.failure_kind
  if (failureKind === 'anesthesia_consent_missing') {
    if (
      facts.performed_anesthesia_confirmed !== true ||
      facts.consent_state !== 'missing' ||
      !Array.isArray(facts.checked_sources) ||
      facts.checked_sources.length !== 1 ||
      facts.checked_sources[0] !== 'consent_form'
    )
      return undefined
    return {
      failureKind,
      performedEventConfirmed: true,
      missingSources: ['consent_form'],
    }
  }
  if (failureKind === 'anesthesia_visit_missing') {
    const missingSources = Array.isArray(facts.missing_visit_sources)
      ? facts.missing_visit_sources.filter(
          (value): value is 'preane_surveil_record' | 'postane_surveil_record' =>
            value === 'preane_surveil_record' || value === 'postane_surveil_record',
        )
      : []
    if (facts.performed_anesthesia_confirmed !== true || !missingSources.length) return undefined
    return { failureKind, performedEventConfirmed: true, missingSources }
  }
  if (failureKind === 'preop_discussion_missing') {
    if (
      facts.performed_surgery_confirmed !== true ||
      facts.emergency_rescue_exception_absent !== true ||
      !Array.isArray(facts.checked_sources) ||
      facts.checked_sources.length !== 1 ||
      facts.checked_sources[0] !== 'presurg_discussion'
    )
      return undefined
    return {
      failureKind,
      performedEventConfirmed: true,
      missingSources: ['presurg_discussion'],
      emergencyRescueExceptionAbsent: true,
    }
  }
  return undefined
}

/**
 * 只读取后端显式提供的 customer_display_facts 白名单字段。
 * 任何 findings、evidence、prompt、模型原文或自由文本均不得穿透领域边界。
 */
function extractCustomerDisplayFacts(raw: RawCustomerQcResult): CustomerDisplayFacts {
  const candidate = raw.customer_display_facts
  if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) return {}

  const facts = candidate as Record<string, unknown>
  const failureKind = asString(facts.failure_kind)
  const diagnosticRelationState = asString(facts.diagnostic_relation_state)
  const diagnosticReasonDimensions = Array.isArray(facts.diagnostic_reason_dimensions)
    ? facts.diagnostic_reason_dimensions.filter(
        (value): value is NonNullable<CustomerDisplayFacts['diagnosticReasonDimensions']>[number] =>
          value === 'anatomic_site' ||
          value === 'laterality' ||
          value === 'symptom_pattern' ||
          value === 'disease_course' ||
          value === 'disease_direction',
      )
    : undefined
  const lengthState = asString(facts.length_state)
  const diagnosticRationaleCode = asString(facts.diagnostic_rationale_code)
  const missingFields = Array.isArray(facts.missing_fields)
    ? facts.missing_fields.filter(
        (value): value is NonNullable<CustomerDisplayFacts['missingFields']>[number] =>
          value === 'implant_name' ||
          value === 'implant_type' ||
          value === 'implant_specification' ||
          value === 'implant_material' ||
          value === 'implant_quantity' ||
          value === 'implant_barcode',
      )
    : undefined
  const targetDocument = asString(facts.target_document)
  const surgeryDocument =
    (failureKind === 'surgery_document_missing' || failureKind === 'surgery_document_blank') &&
    facts.performed_surgery_confirmed === true &&
    (targetDocument === 'presurg_summary' ||
      targetDocument === 'surgery_record' ||
      targetDocument === 'surgery_safecheck_record')
      ? ({
          target: targetDocument,
          state: failureKind === 'surgery_document_blank' ? 'blank' : 'missing',
        } as const)
      : undefined
  return {
    complaintLength: asSafeInteger(facts.complaint_length),
    primaryDiagnosisAvailable:
      typeof facts.primary_diagnosis_available === 'boolean'
        ? facts.primary_diagnosis_available
        : undefined,
    diagnosticRelationState:
      diagnosticRelationState === 'supported' ||
      diagnosticRelationState === 'unsupported' ||
      diagnosticRelationState === 'mismatch' ||
      diagnosticRelationState === 'unknown'
        ? diagnosticRelationState
        : failureKind === 'complaint_primary_diagnosis_mismatch'
          ? 'mismatch'
          : failureKind === 'complaint_lacks_diagnostic_clue'
            ? 'unsupported'
            : undefined,
    diagnosticReasonDimensions,
    surgeryDocument,
    diagnosticRationaleCode:
      diagnosticRationaleCode === 'symptom_only' ||
      diagnosticRationaleCode === 'site_symptom_not_specific' ||
      diagnosticRationaleCode === 'diagnosis_mismatch' ||
      diagnosticRationaleCode === 'insufficient_information' ||
      diagnosticRationaleCode === 'supported'
        ? diagnosticRationaleCode
        : undefined,
    lengthState:
      lengthState === 'satisfied' || lengthState === 'violated' || lengthState === 'unknown'
        ? lengthState
        : undefined,
    missingFields,
    copySimilarity:
      typeof facts.copy_similarity === 'number' &&
      facts.copy_similarity >= 0 &&
      facts.copy_similarity <= 1
        ? facts.copy_similarity
        : undefined,
    copySimilarityThreshold:
      typeof facts.copy_similarity_threshold === 'number' &&
      facts.copy_similarity_threshold >= 0 &&
      facts.copy_similarity_threshold <= 1
        ? facts.copy_similarity_threshold
        : undefined,
    copyDocuments: extractCopyDocuments(facts),
    courseInterval: extractCourseInterval(facts),
    pathologySampling: extractPathologySampling(facts),
    lymphNodeDocumentation: extractLymphNodeDocumentation(facts),
    prophylaxisDuration: extractProphylaxisDuration(facts),
    anesthesiaDocumentation: extractAnesthesiaDocumentation(facts),
    examLab: extractExamLab(facts),
    transfusion: extractTransfusion(facts),
    timeliness: extractTimeliness(facts),
    surgeryTimeliness: extractSurgeryTimeliness(facts),
    surgeryConsent: extractSurgeryConsent(facts),
    severityCourseGap: extractSeverityCourseGap(facts),
    criticalDailyCoverage: extractCriticalDailyCoverage(facts),
    standard: asString(facts.standard),
    failureKind,
    source: sourceFromLabel(facts.source_label),
  }
}

const DIAGNOSTIC_DIMENSION_LABELS = {
  anatomic_site: '解剖部位',
  laterality: '侧别',
  symptom_pattern: '症状特征',
  disease_course: '病程',
  disease_direction: '疾病指向',
} as const

const IMPLANT_FIELD_LABELS = {
  implant_name: '植入物名称',
  implant_type: '种类',
  implant_specification: '规格/型号',
  implant_material: '材质',
  implant_quantity: '数量',
  implant_barcode: '条码/批号',
} as const

interface SafeCriterionResult {
  criterionId: string
  kind: 'text_length' | 'semantic_relation'
  status: 'passed' | 'failed' | 'unknown'
  reasonCode: string
  actualValue?: number | string | boolean
  expectedValue?: number | string | boolean
  operator?: string
  unit?: string
  sourceFact?: string
  leftFact?: string
  rightFact?: string
  rationaleCode?: string
  dimensions: Array<keyof typeof DIAGNOSTIC_DIMENSION_LABELS>
  medicalAnalysis?: string
}

function legacyLx018Criteria(raw: RawCustomerQcResult): SafeCriterionResult[] {
  if (resolveRuleId(raw) !== 'LX0609-018') return []
  const facts = extractCustomerDisplayFacts(raw)
  const criteria: SafeCriterionResult[] = []
  if (facts.complaintLength !== undefined) {
    const status =
      facts.lengthState === 'violated' ||
      facts.failureKind === 'complaint_too_long' ||
      facts.complaintLength > 20
        ? 'failed'
        : facts.lengthState === 'satisfied'
          ? 'passed'
          : 'unknown'
    criteria.push({
      criterionId: 'chief_complaint_length',
      kind: 'text_length',
      status,
      reasonCode: status === 'failed' ? 'complaint_too_long' : 'requirement_satisfied',
      actualValue: facts.complaintLength,
      expectedValue: 20,
      operator: 'lte',
      unit: 'character',
      sourceFact: 'admission_record.chief_complaint',
      dimensions: [],
    })
  }
  if (facts.diagnosticRelationState) {
    criteria.push({
      criterionId: 'diagnostic_direction',
      kind: 'semantic_relation',
      status:
        facts.diagnosticRelationState === 'supported'
          ? 'passed'
          : facts.diagnosticRelationState === 'unknown'
            ? 'unknown'
            : 'failed',
      reasonCode:
        facts.diagnosticRelationState === 'supported'
          ? 'requirement_satisfied'
          : facts.failureKind || 'complaint_primary_diagnosis_mismatch',
      actualValue: facts.diagnosticRelationState,
      leftFact: 'admission_record.chief_complaint',
      rightFact: 'admission_record.first_diagnosis',
      rationaleCode: facts.diagnosticRationaleCode,
      dimensions: facts.diagnosticReasonDimensions || [],
    })
  }
  return criteria
}

function effectiveCriteria(raw: RawCustomerQcResult): SafeCriterionResult[] {
  const explicit = extractCriterionResults(raw)
  return explicit.length ? explicit : legacyLx018Criteria(raw)
}

function extractCriterionResults(raw: RawCustomerQcResult): SafeCriterionResult[] {
  if (!Array.isArray(raw.criterion_results)) return []
  return raw.criterion_results.flatMap((candidate) => {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) return []
    const row = candidate as Record<string, unknown>
    const criterionId = asString(row.criterion_id)
    const kind = asString(row.kind)
    const status = asString(row.status)
    const reasonCode = asString(row.reason_code)
    if (
      !criterionId ||
      (kind !== 'text_length' && kind !== 'semantic_relation') ||
      (status !== 'passed' && status !== 'failed' && status !== 'unknown') ||
      !reasonCode
    )
      return []
    const scalar = (value: unknown): number | string | boolean | undefined =>
      typeof value === 'number' || typeof value === 'string' || typeof value === 'boolean'
        ? value
        : undefined
    const dimensions = Array.isArray(row.dimensions)
      ? row.dimensions.filter(
          (value): value is keyof typeof DIAGNOSTIC_DIMENSION_LABELS =>
            typeof value === 'string' && value in DIAGNOSTIC_DIMENSION_LABELS,
        )
      : []
    return [
      {
        criterionId,
        kind,
        status,
        reasonCode,
        actualValue: scalar(row.actual_value),
        expectedValue: scalar(row.expected_value),
        operator: asString(row.operator),
        unit: asString(row.unit),
        sourceFact: asString(row.source_fact),
        leftFact: asString(row.left_fact),
        rightFact: asString(row.right_fact),
        rationaleCode: asString(row.rationale_code),
        dimensions,
        medicalAnalysis: asString(row.medical_analysis),
      },
    ]
  })
}

function criterionDescriptor(
  criteria: SafeCriterionResult[],
  primaryDiagnosisAvailable?: boolean,
):
  | {
      descriptor: CustomerReasonDescriptor
      actualValue?: string
      evidenceSources: CustomerQcEvidenceSource[]
      reasonCode?: string
    }
  | undefined {
  const length = criteria.find((item) => item.kind === 'text_length')
  const relation = criteria.find((item) => item.kind === 'semantic_relation')
  if (!length && !relation) return undefined

  const expected = typeof length?.expectedValue === 'number' ? length.expectedValue : undefined
  const actual = typeof length?.actualValue === 'number' ? length.actualValue : undefined
  const lengthRequirement =
    expected === undefined ? '按规则目录配置的字数上限' : `不超过${expected}字`
  const lengthText = !length
    ? ''
    : actual === undefined
      ? '1. 主诉书写规范性：未取得可核对的主诉字数。'
      : length.status === 'passed'
        ? `1. 主诉书写规范性：主诉共${actual}字，符合${lengthRequirement}的要求。`
        : length.status === 'failed' && expected !== undefined
          ? `1. 主诉书写规范性：主诉共${actual}字，超过${expected}字上限。`
          : length.status === 'failed'
            ? `1. 主诉书写规范性：主诉共${actual}字，不符合字数要求。`
            : `1. 主诉书写规范性：主诉共${actual}字，本次未形成确定子结论。`

  const relationState = typeof relation?.actualValue === 'string' ? relation.actualValue : 'unknown'
  const dimensions = (relation?.dimensions || [])
    .map((value) => DIAGNOSTIC_DIMENSION_LABELS[value])
    .join('、')
  const relationText = !relation
    ? '2. 诊断指向性：本次语义核对未形成可靠子结论，需人工确认。'
    : {
        supported: `2. 诊断指向性：主诉与第一诊断的${
          dimensions || '部位、症状特征及疾病指向'
        }能够对应，诊断指向子项通过。`,
        unsupported: `2. 诊断指向性：主诉未提供足以支持第一诊断的${
          dimensions || '疾病指向信息'
        }，诊断指向子项未通过。`,
        mismatch: `2. 诊断指向性：主诉与第一诊断在${
          dimensions || '部位、侧别或症状特征'
        }上不一致，诊断指向子项未通过。`,
        unknown: '2. 诊断指向性：本次语义核对未形成可靠子结论，需人工确认。',
      }[relationState] || '2. 诊断指向性：本次语义核对未形成可靠子结论，需人工确认。'

  const lengthSummary =
    length?.status === 'passed'
      ? '主诉字数符合要求'
      : length?.status === 'failed'
        ? expected === undefined
          ? '主诉字数不符合要求'
          : `主诉超过${expected}字上限`
        : '主诉字数待确认'
  const relationSummary =
    relation?.status === 'passed'
      ? '诊断指向子项通过'
      : relation?.status === 'failed'
        ? '诊断指向子项未通过'
        : '诊断指向子项待确认'
  const relationActualSummary =
    relationState === 'mismatch'
      ? '与第一诊断不一致'
      : relationState === 'unsupported'
        ? '缺少第一诊断指向'
        : relationSummary
  const generatedMedicalAnalysis =
    relation && !relation.medicalAnalysis
      ? relationState === 'supported'
        ? '主诉中的部位、症状特征或病程信息能够支持第一诊断。'
        : relationState === 'mismatch'
          ? '主诉描述与第一诊断在关键临床信息上不一致。'
          : '主诉未提供支持第一诊断所需的特异性临床信息。'
      : ''
  const analysis =
    relation?.medicalAnalysis || generatedMedicalAnalysis
      ? `\n\n${relation?.medicalAnalysis ? 'AI医学分析' : '医学判断'}：${
          relation?.medicalAnalysis || generatedMedicalAnalysis
        }`
      : ''
  const detail = [lengthText, relationText].filter(Boolean).join('\n')
  const failed = criteria.find((item) => item.status === 'failed')
  const sourceFact = length?.sourceFact || relation?.leftFact
  const evidenceSources: CustomerQcEvidenceSource[] =
    sourceFact === 'admission_record.chief_complaint'
      ? [
          {
            kind: 'admission_record',
            label: '入院记录—主诉',
            fieldPath: 'chief_complaint',
          },
        ]
      : []

  return {
    descriptor: {
      summary: `${lengthSummary}；${relationSummary}。`,
      detail: `${detail}${analysis}`,
      requirement: `主诉应${lengthRequirement}；同时应能从主诉的部位、症状特征、病程等信息导出第一诊断。`,
      suggestion: '请针对未通过的子项精简或修正主诉，并确保主诉与第一诊断的医学指向一致。',
    },
    actualValue:
      actual === undefined
        ? undefined
        : `实际值：${actual}字；标准：${lengthRequirement}；${
            primaryDiagnosisAvailable === undefined
              ? ''
              : `第一诊断：${primaryDiagnosisAvailable ? '已找到' : '未找到'}；`
          }诊断指向：${relationActualSummary}。`,
    evidenceSources,
    reasonCode: failed?.reasonCode,
  }
}

function lx025Descriptor(facts: CustomerDisplayFacts): CustomerReasonDescriptor | undefined {
  if (!facts.missingFields?.length) return undefined
  const missingLabels = facts.missingFields.map((value) => IMPLANT_FIELD_LABELS[value])
  const missingText = missingLabels.join('、')
  return {
    summary: `已确认本次手术使用植入物；手术记录未记录：${missingText}（共${missingLabels.length}项）。`,
    detail: `本次不合规的直接原因：手术记录未记录${missingText}。已按必填字段逐项核对；未列为缺失的字段不等于已完整记录，仍应结合原文复核。`,
    requirement: '手术记录应完整记录植入物名称、种类、规格/型号、材质及数量等信息。',
    suggestion: `请在本次手术记录中补录植入物${missingText}。`,
  }
}

const SURGERY_DOCUMENT_LABELS = {
  presurg_summary: '术前小结',
  surgery_record: '手术记录',
  surgery_safecheck_record: '手术安全核查记录',
} as const

function surgeryDocumentDescriptor(
  facts: CustomerDisplayFacts,
): CustomerReasonDescriptor | undefined {
  const document = facts.surgeryDocument
  if (!document) return undefined
  const label = SURGERY_DOCUMENT_LABELS[document.target]
  const issue =
    document.state === 'blank' ? `已找到${label}，但正文为空或仅为占位内容` : `未找到${label}`
  return {
    summary: `已确认本次住院存在已实施手术；${issue}。`,
    detail: `本项仅核对${label}是否存在且具有可用正文。${issue}，因此不能满足本质控点的文书要求。`,
    requirement: `已实施手术时，应形成完整、可用的${label}。`,
    suggestion: `请补充或同步本次手术对应的${label}。`,
  }
}

function timelinessDescriptor(facts: CustomerDisplayFacts): CustomerReasonDescriptor | undefined {
  const timeliness = facts.timeliness
  if (!timeliness) return undefined
  const documentLabel = TIMELINESS_TARGET_LABELS[timeliness.target]
  if (timeliness.target === 'rescue_record') {
    if (
      timeliness.state !== 'late' ||
      !timeliness.anchorTime ||
      !timeliness.observedTime ||
      timeliness.elapsedHours === undefined
    )
      return undefined
    return {
      summary: `抢救结束时间为${timeliness.anchorTime}；抢救记录形成于${timeliness.observedTime}，间隔${timeliness.elapsedHours}小时，超过${timeliness.thresholdHours}小时要求。`,
      detail: `本项以抢救记录中的明确“抢救结束时间”为起点，仅核对该次抢救记录的权威记录时间；两者间隔超过${timeliness.thresholdHours}小时。`,
      requirement: `抢救结束后${timeliness.thresholdHours}小时内应完成抢救记录。`,
      suggestion: `请在抢救结束后${timeliness.thresholdHours}小时内完成并签署抢救记录。`,
    }
  }
  if (timeliness.state === 'missing') {
    return {
      summary: `以入院时间为锚点核对后，未找到可计入本项的${documentLabel}。`,
      detail: `本项要求在入院后${timeliness.thresholdHours}小时内形成${documentLabel}；本次已核对对应受控来源，未找到满足文书类型与角色要求的记录。`,
      requirement: `入院后${timeliness.thresholdHours}小时内应完成${documentLabel}。`,
      suggestion: `请补充或同步入院后${timeliness.thresholdHours}小时内的${documentLabel}。`,
    }
  }
  const elapsed = Number.isInteger(timeliness.elapsedHours)
    ? `${timeliness.elapsedHours}`
    : String(timeliness.elapsedHours)
  const anchorDescription = timeliness.anchorTime
    ? `入院时间为${timeliness.anchorTime}`
    : `入院日期为${timeliness.anchorDate}（未取得具体时分秒）`
  return {
    summary: `${anchorDescription}；首次可计入的${documentLabel}时间为${timeliness.observedTime}，间隔${elapsed}小时，超过${timeliness.thresholdHours}小时要求。`,
    detail: `${
      timeliness.anchorTime
        ? '本项以住院登记或入院记录中的权威入院时间为锚点'
        : '本项仅有权威入院日期，已按全天区间确认仍超过时限'
    }；仅计入符合文书类型与角色要求的记录；上述首次可计入记录已超过规定时限。`,
    requirement: `入院后${timeliness.thresholdHours}小时内应完成${documentLabel}。`,
    suggestion: `请在规定时限内补充${documentLabel}，并核对入院时间与文书记录时间。`,
  }
}

function surgeryTimelinessDescriptor(
  facts: CustomerDisplayFacts,
): CustomerReasonDescriptor | undefined {
  const timeliness = facts.surgeryTimeliness
  if (!timeliness) return undefined
  const elapsed = Number.isInteger(timeliness.elapsedHours)
    ? `${timeliness.elapsedHours}`
    : timeliness.elapsedHours.toFixed(2)
  return {
    summary: `本次手术于${timeliness.surgeryEndTime}结束；手术记录形成于${timeliness.recordTime}，间隔${elapsed}小时，超过术后${timeliness.thresholdHours}小时要求。`,
    detail:
      '本项只采用已用于判定的权威手术结束时间与手术记录时间计算间隔；未使用正文、标题或推测时间。',
    requirement: `手术记录应在手术结束后${timeliness.thresholdHours}小时内完成。`,
    suggestion: '请在规定时限内完成并提交手术记录，并核对手术结束时间与文书记录时间。',
  }
}

function surgeryConsentDescriptor(
  facts: CustomerDisplayFacts,
): CustomerReasonDescriptor | undefined {
  const consent = facts.surgeryConsent
  if (!consent) return undefined
  if (consent.state === 'missing') {
    return {
      summary: '已确认本次住院存在已实施手术；在已证明完整的手术知情同意书来源中未找到对应文书。',
      detail: '本项只在手术已确认且同意书来源完整时作出缺失结论；本次未找到可用的手术知情同意书。',
      requirement: '已实施手术应具有完整的手术知情同意书。',
      suggestion: '请补充或同步本次手术对应的手术知情同意书。',
    }
  }
  if (consent.state === 'blank') {
    return {
      summary: '已确认本次住院存在已实施手术；已找到手术知情同意书，但正文为空或仅为占位内容。',
      detail: '空正文不能支持患者知情与手术同意的核对，因此本项未通过。',
      requirement: '已实施手术应具有内容完整、可核对的手术知情同意书。',
      suggestion: '请补充本次手术知情同意书的有效正文。',
    }
  }
  if (consent.state === 'signature_missing') {
    const roles = consent.missingSignatureRoles
      ?.map((role) => (role === 'patient' ? '患者/授权签字' : '术者签字'))
      .join('、')
    if (!roles) return undefined
    return {
      summary: `已确认本次住院存在已实施手术；手术知情同意书缺少${roles}。`,
      detail: `本项已核对同意书签字要素，缺少：${roles}。`,
      requirement: '手术知情同意书应包含患者/授权签字及术者签字等必要签字要素。',
      suggestion: `请补充或核对本次手术知情同意书中的${roles}。`,
    }
  }
  return {
    summary:
      '已确认本次住院存在已实施手术，但手术知情同意书来源完整性未获证明，暂不能形成确定结论。',
    detail: '本次未将“未找到文书”直接视为缺失，以避免因来源未同步或截断造成误报。',
    requirement: '已实施手术应具有完整、可核对的手术知情同意书。',
    suggestion: '请补充或同步手术知情同意书来源后重新评估。',
  }
}

function severityCourseGapDescriptor(
  facts: CustomerDisplayFacts,
): CustomerReasonDescriptor | undefined {
  const gap = facts.severityCourseGap
  if (!gap) return undefined
  return {
    summary: `病重医嘱起算日为${gap.anchorDate}；${gap.gapStartDate}至${gap.gapEndDate}间隔${gap.gapDays}个自然日，超过每${gap.thresholdDays}个自然日记录一次的要求。`,
    detail: `该区间内未见可计入本项的日常病程记录或上级医师查房记录。评价终点为${gap.horizonDate}；本项仅按文书权威记录日期计算。`,
    requirement: `下达病重医嘱后，每${gap.thresholdDays}个自然日内应至少有一份日常病程记录或上级医师查房记录。`,
    suggestion: `请补充${gap.gapStartDate}至${gap.gapEndDate}期间反映病情和诊疗情况的日常病程记录或上级医师查房记录。`,
  }
}

function criticalDailyCoverageDescriptor(
  facts: CustomerDisplayFacts,
): CustomerReasonDescriptor | undefined {
  const coverage = facts.criticalDailyCoverage
  if (!coverage) return undefined
  const dates = coverage.missingDates.join('、')
  const remaining =
    coverage.missingCount > coverage.missingDates.length
      ? `；另有${coverage.missingCount - coverage.missingDates.length}日未逐项展示`
      : ''
  return {
    summary: `病危期间应每日记录；缺少${coverage.missingCount}日可计入的日常病程或上级医师查房记录。`,
    detail: `病危记录覆盖区间为${coverage.anchorDate || coverage.missingFirstDate}至${coverage.horizonDate || coverage.missingLastDate}。缺失日期：${dates}${remaining}。`,
    requirement: '下达病危医嘱后，应每日有日常病程记录或上级医师查房记录。',
    suggestion: `请补充病危期间${coverage.missingFirstDate}至${coverage.missingLastDate}缺失日期的病程或上级医师查房记录。`,
  }
}

function formatPercentage(value: number): string {
  const percentage = Math.round(value * 1000) / 10
  return `${Number.isInteger(percentage) ? percentage.toFixed(0) : percentage.toFixed(1)}%`
}

function lx016Descriptor(facts: CustomerDisplayFacts): CustomerReasonDescriptor | undefined {
  if (facts.copySimilarity === undefined || facts.copySimilarityThreshold === undefined)
    return undefined
  const similarity = formatPercentage(facts.copySimilarity)
  const threshold = formatPercentage(facts.copySimilarityThreshold)
  return {
    summary: `入院记录现病史与首次病程记录病例特点相似度为${similarity}，超过${threshold}判定阈值。`,
    detail:
      '本次仅比较入院记录的现病史与首次病程记录的病例特点，不比较患者基本信息、文书标题等模板字段。',
    requirement: `上述两部分相似度超过${threshold}时，判定为不合理复制病历。`,
    suggestion:
      '请在首次病程记录中结合本次病情补充病例特点的归纳、分析和诊疗思路，避免直接复制现病史。',
  }
}

function lx017Descriptor(facts: CustomerDisplayFacts): CustomerReasonDescriptor | undefined {
  if (
    !facts.copyDocuments?.length ||
    facts.copySimilarity === undefined ||
    facts.copySimilarityThreshold === undefined
  )
    return undefined
  const documents = facts.copyDocuments.map(
    (item) => `${COPY_DOCUMENT_LABELS[item.source]}（${item.recordTime}）`,
  )
  const similarity = formatPercentage(facts.copySimilarity)
  const threshold = formatPercentage(facts.copySimilarityThreshold)
  return {
    summary: `以下两份病程文书相似度为${similarity}，超过${threshold}阈值。`,
    detail: `对比文书：\n1. ${documents[0]}\n2. ${documents[1]}\n\n系统按相邻、不同日期的病程/查房记录进行全文相似度比较，本次命中阈值。`,
    requirement: `相邻不同日期的病程/查房记录相似度不得超过${threshold}。`,
    suggestion: '请分别补充两次记录当日的病情变化、诊疗措施或疗效，避免机械复制。',
  }
}

function lx007Descriptor(facts: CustomerDisplayFacts): CustomerReasonDescriptor | undefined {
  const interval = facts.courseInterval
  if (!interval) return undefined
  const hours = Number.isInteger(interval.hours) ? `${interval.hours}` : interval.hours.toFixed(2)
  return {
    summary: `从${interval.startTime}至${interval.endTime}间隔${hours}小时，超过${interval.thresholdHours}小时要求。`,
    detail: `在已纳入核对的${COPY_DOCUMENT_LABELS[interval.startSource]}（${interval.startTime}）与${COPY_DOCUMENT_LABELS[interval.endSource]}（${interval.endTime}）之间，未见可计入本项的日常病程记录或上级医师查房记录。`,
    requirement: `病情稳定（未下病危、病重医嘱）患者应每${interval.thresholdHours}小时至少有一份日常病程记录或上级医师查房记录。`,
    suggestion: '请补充该时间段内反映患者病情和诊疗情况的日常病程记录或上级医师查房记录。',
  }
}

function lx019Descriptor(facts: CustomerDisplayFacts): CustomerReasonDescriptor | undefined {
  const sampling = facts.pathologySampling
  if (!sampling) return undefined
  const triggers = sampling.triggerSources
    .map((source) => PATHOLOGY_SOURCE_LABELS[source])
    .join('、')
  const checked = sampling.checkedSources
    .map(
      (item) =>
        `${PATHOLOGY_SOURCE_LABELS[item.source]}（${item.state === 'present' ? '已核对' : '无可用文书'}）`,
    )
    .join('、')
  return {
    summary: '病理相关来源已触发本项核对；在目标文书中未检出取材、送检或标本处理的已实施记录。',
    detail: `触发来源：${triggers}。已核对：${checked}。本结论仅说明上述受控来源未检出取材/送检/标本处理的已实施事实，不表示实际未取材。`,
    requirement: '取材、送检或标本处理的已实施情况应在手术记录或日常病程记录中明确记录。',
    suggestion: '请在对应手术记录或日常病程记录中补充本次取材、送检或标本处理的具体已实施事实。',
  }
}

function lx024Descriptor(facts: CustomerDisplayFacts): CustomerReasonDescriptor | undefined {
  const documentation = facts.lymphNodeDocumentation
  if (!documentation?.checkedSources.length) return undefined
  const checked = documentation.checkedSources
    .map((source) => PATHOLOGY_SOURCE_LABELS[source])
    .join('、')
  return {
    summary: '已确认本次为恶性肿瘤手术；已核对的手术相关文书未记录淋巴结清扫情况。',
    detail: `本项仅在“本次手术已实施”且“恶性肿瘤手术关系已确认”时判定。已核对：${checked}；其中未检出淋巴结清扫范围、部位或未清扫原因等具体记录。`,
    requirement: '恶性肿瘤手术记录应明确记载淋巴结清扫情况。',
    suggestion: '请在本次手术记录中补充淋巴结清扫的范围、部位，或未清扫的具体原因。',
  }
}

function lx028Descriptor(facts: CustomerDisplayFacts): CustomerReasonDescriptor | undefined {
  const duration = facts.prophylaxisDuration
  if (!duration) return undefined
  const interval = `${duration.startTime}至${duration.endTime}，共${duration.durationHours}小时`
  if (duration.failureKind === 'prophylaxis_duration_over_48h') {
    return {
      summary: `Ⅰ/Ⅱ类切口预防用药${interval}，超过48小时上限。`,
      detail:
        '本项仅采用已验证为实际给药与实际停药的时间计算预防用药时长；未以计划医嘱时间替代实际用药时间。',
      requirement:
        'Ⅰ/Ⅱ类切口手术预防性抗菌药物使用时长原则上不超过24小时，特殊情况一般不超过48小时。',
      suggestion: '请核对本次预防性抗菌药物的实际停药时间，并在必要时规范调整用药。',
    }
  }
  return {
    summary: `Ⅰ/Ⅱ类切口预防用药${interval}，超过24小时；未记录延长用药理由。`,
    detail:
      '本项仅采用已验证为实际给药与实际停药的时间计算预防用药时长；本次时长未超过48小时，但未检出延长预防用药的具体理由。',
    requirement: 'Ⅰ/Ⅱ类切口手术预防性抗菌药物超过24小时使用时，应记录延长用药的具体理由。',
    suggestion: '请补充延长预防性抗菌药物使用的具体临床理由，或按规范及时停药。',
  }
}

function anesthesiaDocumentationDescriptor(
  facts: CustomerDisplayFacts,
): CustomerReasonDescriptor | undefined {
  const documentation = facts.anesthesiaDocumentation
  if (!documentation?.missingSources.length) return undefined
  const missing = documentation.missingSources
    .map((source) => ANESTHESIA_SOURCE_LABELS[source])
    .join('、')
  if (documentation.failureKind === 'anesthesia_consent_missing') {
    return {
      summary: '已确认本次实施麻醉；未检出麻醉知情同意书。',
      detail: `本项仅在已确认本次实施麻醉时判定。已核对来源：${missing}；当前未返回可用同意书文书。`,
      requirement: '实施麻醉前应具备麻醉知情同意书。',
      suggestion: '请补充或同步本次麻醉知情同意书后重新核对。',
    }
  }
  if (documentation.failureKind === 'anesthesia_visit_missing') {
    return {
      summary: `已确认本次实施麻醉；未检出：${missing}。`,
      detail: `本项仅在已确认本次实施麻醉且非局部麻醉时判定。当前缺少上述麻醉访视文书，不能以其他病程记录替代。`,
      requirement: '非局部麻醉患者应具备相应的麻醉术前及术后访视记录。',
      suggestion: `请补充或同步${missing}后重新核对。`,
    }
  }
  if (documentation.failureKind === 'preop_discussion_missing') {
    return {
      summary: '已确认本次手术已实施，且未发现急诊抢救例外；未检出术前讨论记录。',
      detail: '本项不评价术者是否参加讨论；当前仅说明已核对术前讨论来源但未返回可用讨论文书。',
      requirement: '四级手术术前应有讨论记录；符合急诊抢救例外时不适用。',
      suggestion: '请补充或同步本次术前讨论记录后重新核对。',
    }
  }
  return undefined
}

function examLabDescriptor(facts: CustomerDisplayFacts): CustomerReasonDescriptor | undefined {
  const examLab = facts.examLab
  if (!examLab) return undefined
  const subject = examLab.subject === 'ct_mri' ? 'CT/MRI检查' : '细菌培养及药敏'
  const sources = examLab.checkedSources.map((source) => EXAM_LAB_SOURCE_LABELS[source]).join('、')
  if (examLab.requirement === 'reason_before_order') {
    return {
      summary: `已确认本次住院存在${subject}医嘱；在医嘱开立前的病程/查房记录中未检出检查原因记录。`,
      detail: `本项只核对检查原因是否在医嘱开立前记录，不能据此推断检查是否已经完成。已核对来源：${sources}。`,
      requirement: '下达CT/MRI检查医嘱前，应在病程记录或上级医师查房记录中记录检查原因。',
      suggestion: '请在检查医嘱开立前的相关病程或上级医师查房记录中补充本次检查原因。',
    }
  }
  if (examLab.requirement === 'result_recording_within_24h') {
    return {
      summary: `已确认本次住院存在${subject}报告；未在报告后24小时内检出结果记录。`,
      detail: `本项核对${subject}报告后的日常病程记录及上级医师查房记录；未检出可计入的结果记录，或记录已超过24小时。已核对来源：${sources}。`,
      requirement: `${subject}结果应在报告后24小时内在病程记录或上级医师查房记录中记录。`,
      suggestion: `请在${subject}报告后24小时内补充结果记录，并注明与本次检查/检验的对应关系。`,
    }
  }
  return {
    summary: `已确认本次住院存在阳性${subject}报告；未在报告后24小时内检出结果分析记录。`,
    detail: `本项仅针对阳性${subject}结果核对分析记录；未检出可计入的结果分析，或分析记录已超过24小时。已核对来源：${sources}。`,
    requirement: `阳性${subject}结果应在报告后24小时内在病程记录或上级医师查房记录中记录并分析。`,
    suggestion: `请在阳性${subject}报告后24小时内补充结果分析及相应诊疗考虑。`,
  }
}

function transfusionDescriptor(facts: CustomerDisplayFacts): CustomerReasonDescriptor | undefined {
  const transfusion = facts.transfusion
  if (!transfusion) return undefined
  const sources = transfusion.checkedSources
    .map((source) => TRANSFUSION_SOURCE_LABELS[source])
    .join('、')
  const descriptions = {
    pretransfusion_assessment: {
      summary: '已确认本次住院存在输血记录；未检出输血前评估记录。',
      detail: `本项只在输血事实已确认时核对输血前评估。已核对来源：${sources}。`,
      requirement: '输血前应完成并记录输血评估。',
      suggestion: '请补充本次输血前的风险评估及相关临床判断记录。',
    },
    purpose_or_indication: {
      summary: '已确认本次住院存在输血记录；未检出输血目的或适应证记录。',
      detail: `本项仅说明已核对的输血记录中未检出目的或适应证，不将“未同步其他文书”直接认定为缺失。已核对来源：${sources}。`,
      requirement: '输血记录应明确输血目的或适应证。',
      suggestion: '请在本次输血记录中补充输血目的或适应证。',
    },
    posttransfusion_evaluation: {
      summary: '已确认输血结束事实；未检出输血后评价记录。',
      detail: `本项只在已取得权威输血结束事实时作出判断，并核对结束后的评价记录。已核对来源：${sources}。`,
      requirement: '输血结束后应记录输血后评价。',
      suggestion: '请补充本次输血结束后的临床评价及相关观察记录。',
    },
    postop_first_course_transfusion: {
      summary: '手术记录已明确术中输血；术后首次病程记录未提及输血事实。',
      detail: `本项只核对已确认术中输血与术后首次病程记录之间的一致性。已核对来源：${sources}。`,
      requirement: '术中发生输血时，术后首次病程记录应明确记录输血事实。',
      suggestion: '请在术后首次病程记录中补充本次术中输血的事实及相关情况。',
    },
  } as const
  return descriptions[transfusion.requirement]
}

function resolveRuleId(raw: RawCustomerQcResult): string {
  return asString(raw.rule_id) ?? asString(raw.rule_code) ?? asString(raw.qc_point_id) ?? 'UNKNOWN'
}

function resolveRawStatus(raw: RawCustomerQcResult): unknown {
  return [raw.result_status, raw.status, raw.canonical_status, raw.display_status].find(
    (value) => typeof value === 'string' && value.trim(),
  )
}

function controlledDescriptorFromSafeDto(
  raw: RawCustomerQcResult,
): CustomerReasonDescriptor | undefined {
  if (
    asString(raw.schema_version) !== SAFE_RESULT_SCHEMA ||
    asString(raw.explanation_contract_version) !== SAFE_EXPLANATION_CONTRACT
  ) {
    return undefined
  }
  const summary = asString(raw.conclusion)
  const detail = asString(raw.detail)
  const requirement = asString(raw.requirement)
  const suggestion = asString(raw.suggestion)
  if (
    !summary ||
    !detail ||
    !requirement ||
    !suggestion ||
    [summary, detail, requirement, suggestion].some((value) => FORBIDDEN_PLACEHOLDERS.has(value))
  ) {
    return undefined
  }
  return { summary, detail, requirement, suggestion }
}

/** 判断批任务结果是否携带完整且可直接展示的后端解释合同。 */
export function hasControlledCustomerExplanation(raw: RawCustomerQcResult): boolean {
  return controlledDescriptorFromSafeDto(raw) !== undefined
}

/**
 * 规则专属的受控说明只能在这一处选择。
 *
 * `hasActionableCustomerExplanation` 与 `normalizeCustomerQcResult` 必须共享同一入口：
 * 否则新增事实描述器时，质量门可能放行、页面却无法渲染（或相反）。
 */
function ruleSpecificDescriptor(
  ruleId: string,
  facts: CustomerDisplayFacts,
): CustomerReasonDescriptor | undefined {
  if (ruleId === 'LX0609-016') return lx016Descriptor(facts)
  if (ruleId === 'LX0609-025') return lx025Descriptor(facts)
  if (ruleId === 'LX0609-024') return lx024Descriptor(facts)
  if (ruleId === 'LX0609-028') return lx028Descriptor(facts)
  if (['LX0609-034', 'LX0609-035', 'LX0609-036', 'LX0609-037', 'LX0609-039'].includes(ruleId)) {
    return anesthesiaDocumentationDescriptor(facts)
  }
  if (['LX0609-029', 'LX0609-030', 'LX0609-032'].includes(ruleId)) {
    return surgeryDocumentDescriptor(facts)
  }
  if (['LX0609-001', 'LX0609-002', 'LX0609-004', 'LX0609-005', 'LX0609-006'].includes(ruleId)) {
    return timelinessDescriptor(facts)
  }
  if (ruleId === 'LX0609-003') return surgeryTimelinessDescriptor(facts)
  if (ruleId === 'LX0609-033') return surgeryConsentDescriptor(facts)
  if (ruleId === 'LX0609-008') return severityCourseGapDescriptor(facts)
  if (ruleId === 'LX0609-009') return criticalDailyCoverageDescriptor(facts)
  if (ruleId === 'LX0609-017') return lx017Descriptor(facts)
  if (ruleId === 'LX0609-007') return lx007Descriptor(facts)
  if (ruleId === 'LX0609-019') return lx019Descriptor(facts)
  if (['LX0609-010', 'LX0609-011', 'LX0609-012', 'LX0609-014', 'LX0609-015'].includes(ruleId)) {
    return examLabDescriptor(facts)
  }
  if (['LX0609-044', 'LX0609-046', 'LX0609-047', 'LX0609-048'].includes(ruleId)) {
    return transfusionDescriptor(facts)
  }
  return undefined
}

/**
 * 客户可解释质量门：只有完整后端解释合同，或具备规则专属受控事实时才可直接展示。
 * 通用“发现问题”占位文案不得通过该质量门。
 */
export function hasActionableCustomerExplanation(raw: RawCustomerQcResult): boolean {
  if (controlledDescriptorFromSafeDto(raw)) return true
  const ruleId = resolveRuleId(raw)
  const facts = extractCustomerDisplayFacts(raw)
  if (
    criterionDescriptor(
      effectiveCriteria(raw),
      extractCustomerDisplayFacts(raw).primaryDiagnosisAvailable,
    )
  )
    return true
  if (
    ruleId === 'LX0609-018' &&
    [
      'complaint_or_primary_diagnosis_unavailable',
      'complaint_too_long',
      'complaint_too_short',
      'complaint_too_short_semantic_unknown',
      'complaint_lacks_diagnostic_clue',
      'complaint_primary_diagnosis_mismatch',
      'threshold_exceeded',
    ].includes(asString(raw.reason_code) || '')
  )
    return true
  return ruleSpecificDescriptor(ruleId, facts) !== undefined
}

function evidenceSourcesFor(facts: CustomerDisplayFacts): CustomerQcEvidenceSource[] {
  if (facts.source) return [facts.source]
  if (facts.lymphNodeDocumentation?.checkedSources.length) {
    return facts.lymphNodeDocumentation.checkedSources.map((source) => ({
      kind: source === 'surgery_record' ? 'surgery_record' : 'other',
      label: PATHOLOGY_SOURCE_LABELS[source],
    }))
  }
  return []
}

/**
 * 客户展示的确定性问题必须能说明具体原因、标准和证据。
 * 旧结果或兼容路径缺少这些事实时，保留后端原始结果用于审计，
 * 但不把它包装成客户可直接处理的“不合规”。
 */
function explanationIncompleteDescriptor(): CustomerReasonDescriptor {
  return {
    summary: '本次结果缺少规则专属、可核对的事实依据，暂不作为确定问题展示。',
    detail:
      '该结果未提供可展示的具体原因、核对标准或证据定位。为避免将无法复核的旧结果误呈现为确定缺陷，请重新质控或补齐该规则的受控解释合同。',
    requirement: '确定性问题应同时提供规则专属原因、核对标准、实际情况及可定位证据。',
    suggestion: '请重新质控；如仍出现该提示，请补齐对应规则的受控事实和证据引用后再确认。',
  }
}

/**
 * 结果解释的唯一入口：从不返回原始对象，也不复制自由文本字段。
 */
export function normalizeCustomerQcResult(raw: RawCustomerQcResult): CustomerQcResult {
  const ruleId = resolveRuleId(raw)
  const rawDecisionStatus = resolveCustomerQcStatus(resolveRawStatus(raw))
  const reasonCode = asString(raw.reason_code)
  const facts = extractCustomerDisplayFacts(raw)
  const criteriaDisplay = criterionDescriptor(
    effectiveCriteria(raw),
    facts.primaryDiagnosisAvailable,
  )
  const effectiveReasonCode = criteriaDisplay?.reasonCode ?? facts.failureKind ?? reasonCode
  const controlledDescriptor = controlledDescriptorFromSafeDto(raw)
  const ruleDescriptor = ruleSpecificDescriptor(ruleId, facts)
  const actionableDescriptor = criteriaDisplay?.descriptor ?? ruleDescriptor ?? controlledDescriptor
  const explanationIncomplete = rawDecisionStatus === 'non_compliant' && !actionableDescriptor
  const decisionStatus = explanationIncomplete ? 'evaluation_unknown' : rawDecisionStatus
  const descriptor =
    actionableDescriptor ??
    (explanationIncomplete
      ? explanationIncompleteDescriptor()
      : resolveCustomerReason(ruleId, effectiveReasonCode, decisionStatus))
  const evidenceSources = criteriaDisplay?.evidenceSources ?? evidenceSourcesFor(facts)
  const actualValue =
    criteriaDisplay?.actualValue ??
    (ruleId === 'LX0609-016' &&
    facts.copySimilarity !== undefined &&
    facts.copySimilarityThreshold !== undefined
      ? `相似度：${formatPercentage(facts.copySimilarity)}；判定阈值：${formatPercentage(facts.copySimilarityThreshold)}；超出阈值：${formatPercentage(Math.max(0, facts.copySimilarity - facts.copySimilarityThreshold)).replace('%', '个百分点')}。`
      : ruleId === 'LX0609-025' && facts.missingFields?.length
        ? `缺失字段：${facts.missingFields.map((value) => IMPLANT_FIELD_LABELS[value]).join('、')}。`
        : ruleId === 'LX0609-024' && facts.lymphNodeDocumentation?.checkedSources.length
          ? `已确认：本次手术已实施且属于恶性肿瘤手术；已核对来源：${facts.lymphNodeDocumentation.checkedSources.map((source) => PATHOLOGY_SOURCE_LABELS[source]).join('、')}。`
          : ruleId === 'LX0609-028' && facts.prophylaxisDuration
            ? `切口类别：${facts.prophylaxisDuration.incisionClass}类；实际预防用药：${facts.prophylaxisDuration.startTime}至${facts.prophylaxisDuration.endTime}，共${facts.prophylaxisDuration.durationHours}小时。`
            : undefined)

  return {
    ruleId,
    decisionStatus,
    evidenceAvailability: resolveEvidenceAvailability(decisionStatus, raw.evidence_problem_type),
    ...(effectiveReasonCode ? { reasonCode: effectiveReasonCode } : {}),
    display: buildCustomerDisplay(descriptor, evidenceSources, actualValue, decisionStatus),
  }
}
