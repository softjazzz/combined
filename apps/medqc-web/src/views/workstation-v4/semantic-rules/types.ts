export interface SemanticRuleItem {
  rule_id: string
  rule_code?: string
  name: string
  description: string
  category: string
  complexity: string
  defect_level: string
  score_deduction: number
  applicable_documents: string[]
  medical_domain: string
  requires_rag: boolean
  requires_cot: boolean
  executor_type?: 'llm' | 'program' | string
  execution_domain?: string
  doc_scope?: string
  rule_version?: string
  prompt_version?: string
  cost_class?: string
  rule_family?: string
  launch_tier?: 'A' | 'B' | 'C' | 'UNKNOWN' | string
  launch_tier_label?: string
}

export interface SichuanRuleSetOption {
  rule_set_key: string
  rule_set_name: string
  rule_set_version: string
  scope: string
  rule_ids: string[]
  rule_count: number
  execution_strategy?: string
  quality_profile?: string
  bucket_strategy?: string
  enable_selective_refine?: boolean
  refine_confidence_threshold?: number
  batch_output_mode?: string
  max_refine_candidates?: number
  description?: string
}

export interface SemanticRuleStats {
  total_rules: number
  rule_categories: string[]
  complexity_distribution: Record<string, number>
  defect_level_distribution: Record<string, number>
}

export interface SemanticRuleTestResult {
  is_compliant: boolean
  confidence: number
  findings: string
  evidence: string
  suggestion: string
  status?: string
  trace_id?: string
  error_message?: string
  error_detail?: string
  status_code?: number
  error_category?: string
  executor_type?: string
  model_version?: string
  cache_hit?: boolean
  tokens_used?: number
  api_time?: number
}

export type SichuanBatchJobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'canceled'
export type SichuanBatchExecutionMode = 'single' | 'batch'

export interface SichuanBatchJobSummary {
  total_records: number
  success_count: number
  failed_count: number
  failed_record_count?: number
  issue_records: number
  uncertain_records?: number
  compliant_records: number
  total_tokens: number
  total_processing_time: number
  rule_count?: number
  processed_rule_count?: number
  progress_percent?: number
  retryable_rule_count?: number
  progress?: Record<string, unknown>
  status_breakdown?: Record<string, number>
  postprocess_summary?: {
    total?: number
    raw_status_counts?: Record<string, number>
    display_status_counts?: Record<string, number>
    postprocess_label_counts?: Record<string, number>
    confirmed_defect_count?: number
    qc_review_candidate_count?: number
    needs_review_count?: number
    data_quality_gap_count?: number
    rejected_by_system_count?: number
    technical_error_internal_count?: number
    non_compliant_downgraded_count?: number
  }
  confirmed_defect_count?: number
  qc_review_candidate_count?: number
  needs_review_count?: number
  data_quality_gap_count?: number
  rejected_by_system_count?: number
  technical_error_internal_count?: number
  non_compliant_downgraded_count?: number
  display_status_counts?: Record<string, number>
  postprocess_label_counts?: Record<string, number>
  rule_set_key?: string
  rule_set_name?: string
  rule_set_version?: string
  execution_strategy?: string
  quality_profile?: string
  bucket_strategy?: string
  batch_output_mode?: string
  enable_selective_refine?: boolean
  refine_confidence_threshold?: number
  max_refine_candidates?: number
  refined_rule_count?: number
  refine_summary?: {
    enabled?: boolean
    candidate_count?: number
    eligible_candidate_count?: number
    refined_rule_count?: number
    refine_failed_count?: number
    budget_applied?: number
    budget_skipped_count?: number
    refine_reasons?: Record<string, number>
  }
  pack_metrics?: {
    quality_profile?: string
    bucket_strategy?: string
    batch_output_mode?: string
    total_packs?: number
    avg_pack_size?: number
    fallback_packs?: number
    single_rule_retries?: number
    pack_parse_retry_count?: number
    context_tokens_estimate?: number
  }
  current_rule?: {
    rule_job_id?: string
    rule_code?: string
    rule_name?: string
    progress?: Record<string, unknown>
  } | null
  executor_breakdown?: {
    program: number
    llm: number
  }
  cache_breakdown?: {
    hit: number
    miss: number
  }
  result_aggregation?: SichuanBatchResultAggregation
  updated_at?: string
}

export interface SichuanBatchAggregationCluster {
  cluster_key: string
  sample_evidence?: string
  records: number
  rules: Array<{
    rule_id: string
    rule_name: string
  }>
  document_types?: Record<string, number>
  executor_types?: Record<string, number>
  defect_levels?: Record<string, number>
  status_breakdown?: Record<string, number>
}

export interface SichuanBatchAggregationBreakdownItem {
  key: string
  count: number
}

export interface SichuanBatchResultAggregation {
  cluster_count: number
  duplicate_hits: number
  clusters: SichuanBatchAggregationCluster[]
  rule_breakdown?: Array<{
    rule_id: string
    rule_name: string
    hits: number
  }>
  executor_breakdown?: SichuanBatchAggregationBreakdownItem[]
  document_breakdown?: SichuanBatchAggregationBreakdownItem[]
  defect_level_breakdown?: SichuanBatchAggregationBreakdownItem[]
  status_breakdown?: SichuanBatchAggregationBreakdownItem[]
}

export interface SichuanBatchIssueItem {
  rule_id?: string
  rule_job_id?: string
  rule_code?: string
  rule_name?: string
  record_id: string
  institute_id?: string
  patient_id?: string
  visit_id?: string
  patient_name?: string
  department?: string
  status: string
  is_compliant: boolean
  issues?: Array<{ description: string; evidence?: string }>
  findings?: string
  evidence?: string
  suggestion?: string
  rewrite_example?: string
  confidence?: number
  llm_raw_output?: string
  executor_type?: string
  rule_version?: string
  prompt_version?: string
  model_version?: string
  evidence_source?: string
  cache_hit?: boolean
  trace_id?: string
  cache_key?: string
  execution_domain?: string
  doc_scope?: string
  rule_family?: string
  cost_class?: string
  document_type?: string
  target_document_type?: string
  defect_level?: string
  llm_fallback?: boolean
  quality_profile?: string
  bucket_strategy?: string
  batch_output_mode?: string
  refined?: boolean
  refine_reason?: string
  screening_status?: string
  final_decision_source?: string
  display_status?: string
  display_bucket?: string
  postprocess_label?: string
  postprocess_reason?: string
  evidence_problem_type?: string
  can_show_as_defect?: boolean
  can_show_to_doctor?: boolean
  internal_only?: boolean
  postprocess_mode?: string
}

export interface SichuanBatchFailedItem {
  rule_job_id?: string
  record_id?: string
  visit_id?: string
  patient_name?: string
  department?: string
  trace_id?: string
  rule_version?: string
  prompt_version?: string
  error_phase?: string
  error: string
}

export interface SichuanBatchJobRuleResult {
  id?: string
  job_id?: string
  draft_id?: string
  rule_code: string
  rule_name: string
  scene?: string
  status: SichuanBatchJobStatus
  summary?: SichuanBatchJobSummary | null
  items?: SichuanBatchIssueItem[]
  failed_records?: SichuanBatchFailedItem[]
  error_message?: string
  created_at?: string
  started_at?: string | null
  finished_at?: string | null
  updated_at?: string
  total_records?: number
  success_count?: number
  failed_count?: number
  issue_records?: number
  compliant_records?: number
  total_tokens?: number
  total_processing_time?: number
}

export interface SichuanBatchJobDebugSnapshot {
  job_id: string
  status: SichuanBatchJobStatus | string
  scope: 'all' | 'running' | 'final' | string
  execution_mode?: SichuanBatchExecutionMode | string
  rule_count?: number
  filtered_rule_count?: number
  summary?: SichuanBatchJobSummary | null
  current_rule?: {
    rule_job_id?: string
    rule_code?: string
    rule_name?: string
    progress?: Record<string, unknown>
  } | null
  rules: Array<{
    rule_job_id: string
    rule_code: string
    rule_name: string
    status: string
    progress?: Record<string, unknown>
    debug?: Record<string, unknown>
    total_records?: number
    success_count?: number
    failed_count?: number
    issue_records?: number
    compliant_records?: number
    total_tokens?: number
    total_processing_time?: number
    error_message?: string
    updated_at?: string
  }>
  recent_items: SichuanBatchIssueItem[]
  recent_failed_records: SichuanBatchFailedItem[]
  updated_at?: string
}

export interface SichuanBatchJob {
  id: string
  draft_id?: string
  draft_ids?: string[]
  rule_code: string
  rule_name: string
  scene?: string
  scope: 'all' | 'running' | 'final'
  execution_mode?: SichuanBatchExecutionMode
  rule_count?: number
  status: SichuanBatchJobStatus
  filters?: Record<string, unknown>
  record_ids?: string[]
  progress?: Record<string, unknown>
  summary?: SichuanBatchJobSummary | null
  rule_set_key?: string
  rule_set_name?: string
  rule_set_version?: string
  execution_strategy?: string
  quality_profile?: string
  bucket_strategy?: string
  batch_output_mode?: string
  max_refine_candidates?: number
  refine_summary?: SichuanBatchJobSummary['refine_summary'] | null
  items?: SichuanBatchIssueItem[]
  failed_records?: SichuanBatchFailedItem[]
  error_message?: string
  created_by?: string
  created_at?: string
  started_at?: string | null
  finished_at?: string | null
  updated_at?: string
  total_records?: number
  success_count?: number
  failed_count?: number
  issue_records?: number
  compliant_records?: number
  total_tokens?: number
  total_processing_time?: number
  rule_results?: SichuanBatchJobRuleResult[]
}

export interface SichuanBatchJobQuery {
  status?: SichuanBatchJobStatus
  scope?: 'all' | 'running' | 'final'
  q?: string
  executor_type?: 'program' | 'llm'
  cache_hit?: 'hit' | 'miss'
  created_start_date?: string
  created_end_date?: string
  page?: number
  page_size?: number
}

export interface SichuanBatchJobExport {
  job_id: string
  format?: 'xlsx' | 'csv'
}

export interface SemanticRuleWorkspaceQueryState {
  keyword: string
  complexity: string
  defectLevel: string
  documentType: string
  page: number
  pageSize: number
}

export type SemanticStatusTone = 'brand' | 'danger' | 'warning' | 'safe' | 'neutral'

export interface SemanticKpiCard {
  key: string
  label: string
  value: string
  desc: string
  tone: SemanticStatusTone
}

export interface SemanticRuleRowStatusModel {
  primaryLabel: string
  primaryTone: SemanticStatusTone
  secondaryLabel: string
  secondaryTone: SemanticStatusTone
}

export interface SemanticRuleRowActionModel {
  primaryLabel: '查看结果'
  secondaryLabel: '评估'
}

export const SEMANTIC_RULE_QUERY_KEYS = [
  'keyword',
  'complexity',
  'defectLevel',
  'documentType',
  'page',
  'pageSize',
] as const

export type SemanticRuleQueryKey = (typeof SEMANTIC_RULE_QUERY_KEYS)[number]

export const CANONICAL_DOC_TYPE_LABELS: Record<string, string> = {
  admission_record: '入院记录',
  progress_note: '病程记录',
  first_course_record: '首次病程记录',
  discharge_record: '出院记录',
  discharge_summary: '出院小结',
  operation_record: '手术记录',
  preop_summary: '术前小结',
  postop_first_record: '术后首次病程',
  examination_report: '辅助检查',
  consultation_record: '会诊记录',
  consent_form: '知情同意书',
  medical_order: '医嘱',
  case_discussion: '疑难病例讨论',
  transfusion_record: '输血记录',
  anesthesia_record: '麻醉记录',
}

export function getDocTypeZh(value: string): string {
  return CANONICAL_DOC_TYPE_LABELS[value] || value
}

export function getCategoryZh(value: string): string {
  return value
}

export function getSeverityZh(value: string): string {
  return value
}
