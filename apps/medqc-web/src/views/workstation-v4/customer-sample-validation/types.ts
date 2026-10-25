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
  inpat_no?: string
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
  patient_sex?: string
  patient_age?: string | number
  mr_no: string
  department: string
  hospitalization_status?: 'active' | 'discharged' | ''
  admission_time?: string
  discharge_time?: string
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
  artifact_freshness?: {
    status?: string
    current_git_head?: string
    artifact_git_heads?: string[]
    artifact_hash_mismatches?: string[]
    bound_artifact_count?: number
  }
  release_gate_summary?: {
    release_ready?: boolean
    source_release_ready?: boolean
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

export type ManualLuxian0609RuleCatalogItem = {
  release_scope?: 'default' | 'acceptance_only'
  rule_id: string
  rule_code?: string
  name: string
  description?: string
  category?: string
  required_documents_label?: string
  applicable_document_labels?: string[]
  mapped_rule_ids?: string[]
  primary_execution_rule_id?: string
}

export type ManualLuxian0609RuleCatalogResult = {
  rule_set_key?: string
  total_rules?: number
  rules: ManualLuxian0609RuleCatalogItem[]
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

export type HospitalizationScopeMode = 'active' | 'discharged' | 'active_and_discharged'
export type SyncPhase =
  | 'resolving'
  | 'primary_sync'
  | 'primary_visibility'
  | 'primary_visible'
  | 'detail_sync'
  | 'bundle_refresh'
  | 'completed'

export type HospitalizationScopePayload = {
  scope_mode: HospitalizationScopeMode
  as_of_date: string
  discharge_start_date?: string | null
  discharge_end_date?: string | null
  departments?: string[]
}

export type HospitalizationScopePreview = {
  scope: {
    mode: HospitalizationScopeMode
    as_of_date: string
    discharge_start_date?: string | null
    discharge_end_date?: string | null
    departments?: string[]
  }
  counts: {
    active: number
    discharged: number
    deduplicated: number
    existing_in_pool: number
    new_to_pool: number
  }
  departments: Array<{
    name: string
    active_count: number
    discharged_count: number
    total_count: number
    basis: string[]
  }>
  sources_used: string[]
  source_status: 'ready' | 'degraded'
  warnings: string[]
}

export type ManualSamplePoolSyncJob = {
  id: string
  pool_id: string
  status: string
  payload?: Record<string, unknown>
  summary?: {
    record_progress?: {
      total?: number
      completed?: number
      remaining?: number
      missing_mr?: number
      detail_only?: number
      basis?: string
      label?: string
    }
    progress?: {
      step_key?: string
      step_label?: string
      phase?: SyncPhase
      primary_visible?: boolean
      primary_completed_at?: string
      total_candidates?: number
      eligible_visits?: number
      record_progress?: {
        total?: number
        completed?: number
        remaining?: number
        missing_mr?: number
        detail_only?: number
        basis?: string
        label?: string
      }
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
    admission_filter?: {
      matched_source_count?: number
      new_count?: number
      existing_count?: number
      failed_count?: number
      filter?: {
        start_date?: string
        end_date?: string
        departments?: string[]
      }
    }
    hospitalization_scope?: {
      matched_source_count?: number
      new_count?: number
      existing_count?: number
      repaired_count?: number
      failed_count?: number
      source_status?: 'ready' | 'degraded'
      warnings?: string[]
      scope?: {
        mode?: HospitalizationScopeMode
        as_of_date?: string
        discharge_start_date?: string | null
        discharge_end_date?: string | null
        departments?: string[]
      }
    }
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
  job_kind?: string
  child_job_ids?: string[]
  child_jobs?: import('../semantic-rules/types').SichuanBatchJob[]
  family_scopes?: Array<{
    key: string
    name: string
    rule_ids: string[]
  }>
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
  operation_ref?: string
  execution_scope_hash?: string
  deduplicated?: boolean
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

export type EditableMedicalRecordSection = {
  key: string
  label: string
  text: string
  source_field?: string
  order_index?: number
}

export type EditableMedicalReportItem = {
  item_no?: string
  item_id?: string
  item_code?: string
  item_name?: string
  result?: string
  abnormal_indicator?: string
  reference_range?: string
  referencevalue_min?: string
  referencevalue_max?: string
  unit?: string
  findings?: string
  impression?: string
  recommendation?: string
}

export type FrontpageDisplayField = { key: string; label: string; value: string | null }
export type FrontpageDisplayTable = {
  columns: Array<{ key: string; label: string }>
  rows: Array<Record<string, string | null>>
}
export type FrontpageDisplay = {
  groups: Array<{ key: string; label: string; fields: FrontpageDisplayField[] }>
  diagnoses: FrontpageDisplayTable
  surgeries: FrontpageDisplayTable
}

export type ManualTestRecordSourceMeta = {
  type: 'customer_source_editable_copy' | string
  source_pool_id?: string
  source_pool_name?: string
  source_record_id?: string
  source_item_ids?: string[]
  source_visit_id?: string
  source_mr_no?: string
  source_patient_name?: string
  source_department?: string
  created_from?: string
}

export type EditableMedicalRecordDocument = ManualTestRecordDocument & {
  key: string
  record_time_source?: string
  execution_domain?: string
  has_content?: boolean
  content_loaded?: boolean
  projection_incomplete?: boolean
  projection_notice?: string
  source_ref?: string
  source_document_id?: string
  source_document_aliases?: Array<{
    source_document_id: string
    source_ref: string
    source_document_type?: string
  }>
  source_table?: string
  sections?: EditableMedicalRecordSection[]
  report_items?: EditableMedicalReportItem[]
  report_metadata?: Record<string, string>
  frontpage_display?: FrontpageDisplay
  order_start_time?: string
  order_id?: string
  order_planned_end_time?: string
  order_stop_time?: string
  order_category?: string
  order_item?: string
  order_specification?: string
  order_dosage?: string
  order_frequency?: string
  order_route?: string
  order_quantity?: string
  order_prescribed_doctor?: string
  order_status?: string
  is_new?: boolean
}

export type EditableMedicalRecordEmptyReason =
  | ''
  | 'bundle_documents_empty'
  | 'bundle_load_failed'
  | 'missing_bundle_identity'
  | 'document_not_found'
  | 'document_empty'

export type EditableMedicalRecordDocumentsResult = {
  current_record?: {
    admission_time: string
    admission_time_source: string
    admission_time_state: string
  }
  visit_id?: string
  empty_reason?: EditableMedicalRecordEmptyReason
  documents: EditableMedicalRecordDocument[]
  raw?: unknown
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
  /** 评价时间点（YYYY-MM-DD）：未出院病例时限规则的评价终点，创建后固定；留空取创建当天 */
  evaluationAsOfDate?: string
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
  source?: ManualTestRecordSourceMeta
  evaluation_as_of_date?: string
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
