export type ManualSamplePool = {
  id: string
  name: string
  source_file: string
  source_sheet: string
  scene: string
  description?: string
  created_by: string
  created_at?: string
  updated_at?: string
  total_items: number
  llm_intrinsic_items: number
  programmatic_items: number
  unsupported_items: number
  matched_items: number
  ambiguous_items: number
  unmatched_items: number
  ready_items: number
  latest_job_id?: string
  latest_job_status?: string
}

export type ManualSamplePoolItem = {
  id: string
  pool_id: string
  row_no: number
  department: string
  patient_name: string
  mr_no: string
  visit_id: string
  manual_issue_text: string
  normalized_issue_text: string
  doctor_name: string
  qc_date?: string
  qc_user: string
  coverage_type: string
  issue_category: string
  expected_scene: string
  candidate_rule_ids: string[]
  include_in_batch_1: boolean
  exclude_reason?: string
  matched_institute_id?: string
  matched_patient_id?: string
  matched_visit_id?: string
  match_status: string
  sync_status: string
  bundle_status: string
  latest_job_id?: string
  latest_match_status?: string
  raw_payload?: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export type ManualSamplePoolRecord = {
  id: string
  matched_institute_id?: string
  matched_patient_id?: string
  matched_visit_id?: string
  patient_name: string
  mr_no: string
  department: string
  match_status: string
  sync_status: string
  bundle_status: string
  coverage_types: string[]
  candidate_rule_ids: string[]
  document_scope_labels: string[]
  issue_count: number
  issue_preview: string[]
  issue_preview_text: string
  sample_item_ids: string[]
  sample_items: ManualSamplePoolItem[]
  created_at?: string
  updated_at?: string
}

export type ManualSampleValidationMode =
  | 'customer'
  | 'sc'
  | 'programmatic'
  | 'formal_fast_screen_full'

export type ManualSampleValidationRuleSet = {
  rule_set_key: string
  rule_set_name: string
  rule_set_version: string
  scope: string
  rule_ids?: string[]
  rule_count: number
  validation_mode: ManualSampleValidationMode | string
  requires_synced?: boolean
  advanced?: boolean
  display_group?: 'main' | 'advanced' | string
  coverage_summary?: Record<string, number>
  coverage_status?: string
  release_gate_summary?: {
    release_ready?: boolean
    passed_checks?: number
    failed_checks?: number
    unverified_checks?: number
    blocking_count?: number
  }
  evaluation_summary?: {
    rule_count?: number
    rules_with_all_case_types?: number
    rules_missing_case_types?: number
    hit_count?: number
    manual_confirmed_correct_count?: number
    false_positive_count?: number
    false_negative_count?: number
    unknown_count?: number
    evidence_missing_count?: number
    launch_status?: Record<string, number>
  }
  work_package_summary?: {
    package_count?: number
    phase_counts?: Record<string, number>
    priority_counts?: Record<string, number>
  }
  page_closure_summary?: {
    page_verified?: boolean
    capability_count?: number
    passed_capabilities?: number
    partial_capabilities?: number
    failed_capabilities?: number
    blocking_count?: number
    status_counts?: Record<string, number>
  }
  execution_strategy?: string
  quality_profile?: string
  bucket_strategy?: string
  description?: string
  note?: string
}

export type ManualSampleValidationRuleSetListResult = {
  items: ManualSampleValidationRuleSet[]
}

export type ManualSamplePoolListResult = {
  items: ManualSamplePool[]
  total: number
  page: number
  page_size: number
}

export type ManualSamplePoolItemsResult = {
  pool: ManualSamplePool
  items: ManualSamplePoolItem[]
  total: number
  page: number
  page_size: number
}

export type ManualSamplePoolRecordsResult = {
  pool: ManualSamplePool
  items: ManualSamplePoolRecord[]
  total: number
  page: number
  page_size: number
}

export type ManualSamplePoolSyncJob = {
  id: string
  pool_id: string
  status: string
  payload?: Record<string, unknown>
  summary?: {
    progress?: {
      step_key?: string
      step_label?: string
      total_candidates?: number
      eligible_visits?: number
      processed_tables?: number
      total_tables?: number
      current_table?: string
      remaining_tables?: number
      matched?: number
      ambiguous?: number
      unmatched?: number
      total_rows_pulled?: number
      total_rows_upserted?: number
    }
    total_rows_pulled?: number
    total_rows_upserted?: number
    matched?: number
    ambiguous?: number
    unmatched?: number
    eligible_visits?: number
  }
  error_message?: string
  created_by?: string
  created_at?: string
  started_at?: string
  finished_at?: string
  updated_at?: string
}

export type ManualSamplePoolRunResult = {
  pool_id: string
  job_id: string
  sample_item_count: number
  selected_record_count: number
  record_count: number
  rule_count: number
  customer_rule_count?: number
  execution_rule_count?: number
  selected_rule_ids?: string[]
  scoped_customer_rule_ids?: string[]
  record_rule_map?: Record<string, string[]>
  record_ids: string[]
  rule_ids: string[]
  validation_mode?: ManualSampleValidationMode | string
  rule_set_key?: string
  rule_set_name?: string
  rule_set_version?: string
}

export type ManualTestRecordDocument = {
  document_type: string
  title: string
  record_time?: string
  submit_time?: string
  content: string
  doctor_name?: string
  doctor_code?: string
  enabled?: boolean
}

export type SyntheticCaseExpectedStatus =
  | 'non_compliant'
  | 'compliant'
  | 'not_applicable'
  | 'data_gap'
  | 'uncertain'

export type SyntheticCaseGoldenAnswer = {
  id?: string
  qc_point_id: string
  expected_status: SyntheticCaseExpectedStatus
  trigger_facts: string[]
  evidence_keywords: string[]
  human_reason?: string
}

export type SyntheticCaseBuilderMode = 'case' | 'rule'

export type SyntheticCaseRuleOption = {
  ruleId: string
  name: string
  requiredDocumentsLabel: string
}

export type SyntheticCaseRuleFamily = {
  key: string
  name: string
  description: string
  templateKey: string
  rules: SyntheticCaseRuleOption[]
}

export type TestRecordDocumentForm = ManualTestRecordDocument & {
  key: string
  enabled: boolean
  originalContent: string
  appliedContent: string
}

export type TestRecordForm = {
  builderMode: SyntheticCaseBuilderMode
  caseTitle: string
  patientName: string
  sex: string
  age: number
  mrNo: string
  department: string
  admissionTime: string
  dischargeTime: string
  mainDiagnosis: string
  otherDiagnosesText: string
  manualIssueText: string
  templateKey?: string
  selectedRuleFamilyKey?: string
  selectedRuleIds: string[]
  goldenAnswers: SyntheticCaseGoldenAnswer[]
  documents: TestRecordDocumentForm[]
}

export type ManualTestRecordCreateRequest = {
  case_title: string
  basic_info: {
    patient_name: string
    sex: string
    age: number
    mr_no?: string
    department: string
    admission_time: string
    discharge_time?: string
    main_diagnosis?: string
    other_diagnoses?: string[]
    doctor_name?: string
    contact_number?: string
    address?: string
  }
  documents: ManualTestRecordDocument[]
  selected_rule_ids?: string[]
  manual_issue_text?: string
  template_key?: string
  golden_answers?: SyntheticCaseGoldenAnswer[]
}

export type ManualTestRecordCreateResult = {
  pool?: ManualSamplePool
  item?: ManualSamplePoolItem
  visit_id: string
  mr_no: string
  patient_id: string
  inserted_tables: Record<string, number>
  bundle_status: string
  bundle_error?: string
}

export type Sheet2ExactReviewBlockedRow = {
  sheet2_row_id: string
  visit_id: string
  patient_name: string
  issue_family: string
  primary_rule_id: string
  manual_issue_text: string
  blocked_reason_type: string
  reason: string
  backlog_category: string
  backlog_reason: string
  next_action: string
}

export type Sheet2ExactReviewBacklogBucket = {
  category: string
  count: number
  definition: string
  next_action: string
  blocked_reason_types: Record<string, number>
  top_issue_families: Array<{
    issue_family: string
    count: number
  }>
  top_primary_rules: Array<{
    primary_rule_id: string
    count: number
  }>
  sample_rows: Sheet2ExactReviewBlockedRow[]
}

export type Sheet2ExactReviewAcceptancePackage = {
  generated_at: string
  total_rows: number
  status_breakdown: {
    exact_confirmed: number
    blocked_with_reason: number
    skip: number
    needs_exact_review: number
  }
  explanations: {
    exact_confirmed: string
    blocked_with_reason: string
    skip: string
    acceptance_note: string
  }
  blocked_reason_breakdown: Record<string, number>
  blocked_backlog_breakdown: Sheet2ExactReviewBacklogBucket[]
  blocked_rows: Sheet2ExactReviewBlockedRow[]
  artifacts?: Record<string, string>
  archive_summary?: {
    archive_dir: string
    archived_file_count: number
  } | null
}
