export interface SemanticRuleCustomerPolicy {
  source_document: string
  qc_point: string
  summary: string
  sources: string[]
}

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
  custom_prompt?: string
  cost_class?: string
  rule_family?: string
  launch_tier?: 'A' | 'B' | 'C' | 'UNKNOWN' | string
  launch_tier_label?: string
  mapped_rule_ids?: string[]
  primary_execution_rule_id?: string
  implementation_status?: string
  dependency_type?: string
  data_status?: string
  trigger_condition?: string
  non_trigger_condition?: string
  rule_basis?: string
  customer_text?: string
  /** 仅 LX0609 规则详情使用的总表客户口径，不从包装器字段回退生成。 */
  customer_policy?: SemanticRuleCustomerPolicy
  standardized_rule?: string
  required_documents_label?: string
  data_dependencies?: string[]
  coverage_level?: string
  included_in_v1?: string
  example_source?: 'synthetic' | 'golden' | string
  positive_example?: SemanticRuleExample
  negative_example?: SemanticRuleExample
  applicable_document_labels?: string[]
}

export interface SemanticRuleExampleSection {
  heading: string
  content: string
}

export interface SemanticRuleExample {
  title: string
  summary: string
  raw_text?: string
  sections: SemanticRuleExampleSection[]
  focusPoints?: string[]
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

export interface Luxian0609ReviewFinding {
  id?: string
  rule_id?: string
  rule_name?: string
  record_ref?: string
  reason_code?: string
  canonical_status?: string
  record_id?: string
  patient_name?: string
  department?: string
  severity?: 'P0' | 'P1' | 'P2' | string
  risk_type?: string
  current_status?: string
  suggested_status?: string
  reason?: string
  customer_message?: string
  evidence_preview?: string
  auto_applied?: boolean
  llm_review?: {
    recommendation?: string
    reason?: string
    confidence?: number
  } | null
}

export interface Luxian0609ReviewReport {
  review_status?: string
  reviewed_at?: string
  scope?: string
  summary?: {
    total_findings?: number
    p0?: number
    p1?: number
    p2?: number
  }
  findings?: Luxian0609ReviewFinding[]
  llm_review_status?: string
}

export interface SichuanBatchJobSummary {
  total_records: number
  success_count: number
  failed_count: number
  failed_record_count?: number
  execution_status?: 'completed' | 'completed_with_record_failures' | 'partial_failed' | 'failed'
  completed_rule_count?: number
  failed_rule_count?: number
  diagnostic_rule_failure_count?: number
  issue_records: number
  uncertain_records?: number
  compliant_records: number
  total_tokens: number
  total_processing_time: number
  wall_clock_time?: number
  performance_profile?: {
    tokens_total?: number
    prompt_tokens?: number
    completion_tokens?: number
    unattributed_tokens?: number
    token_breakdown_complete?: boolean
    wall_clock_time_seconds?: number
    total_processing_time_seconds?: number
    llm_call_count?: number
    program_call_count?: number
    actual_llm_pack_call_count?: number
    context_tokens_estimate?: number
    input_profile?: Record<string, unknown>
    [key: string]: unknown
  }
  rule_count?: number
  customer_rule_count?: number
  execution_rule_count?: number
  processed_rule_count?: number
  progress_percent?: number
  retryable_rule_count?: number
  automatic_failed_rule_retry?: {
    max_attempts?: number
    completed_attempts?: number
    remaining_failure_count?: number
    status?: 'queued' | 'running' | 'completed' | 'exhausted' | 'not_retryable' | string
    should_retry?: boolean
    next_attempt?: number
    delay_seconds?: number
  }
  retry_status?: string
  retry_attempt?: number
  retry_pending_count?: number
  retry_remaining_count?: number
  retry_recovered_count?: number
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
  stream_state?: {
    enabled?: boolean
    processed_records?: number
    total_records?: number
    latest_record_id?: string
    latest_visit_id?: string
    latest_result_count?: number
    partial_item_count?: number
    partial_rule_result_count?: number
    started_at?: string
    updated_at?: string
  }
  updated_at?: string
  review_report?: Luxian0609ReviewReport | null
  history_issue_summaries?: Array<{
    rule_id?: string
    status?: string
    text?: string
  }>
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

export interface SichuanBatchSafeEvidenceRef {
  source_type: string
  source_ref: string
}

export type RecommendationEvidenceRole = 'opinion' | 'execution'

export interface QCRecordCompareEvidence {
  key: string
  source_ref?: string
  source_document_id?: string
  source_document_type?: string
  source_document_name?: string
  source_table?: string
  record_time?: string
  field_path?: string
  /** 仅由客户展示白名单生成的章节锚点；普通 evidence.field_path 无定位权限。 */
  section_field_path?: string
  /** 020/023 逐建议安全引用的建议序号与引用角色。 */
  recommendation_index?: number
  evidence_role?: RecommendationEvidenceRole
  quote: string
}

export interface QCRecordCompareIssue {
  key: string
  rule_code: string
  rule_name: string
  status: string
  status_text: string
  result_kind_text: string
  conclusion: string
  suggestion: string
  /** 已通过客户展示白名单的结果摘要；不得携带病历原文。 */
  summary?: string
  /** 已通过客户展示白名单的判定说明。 */
  detail?: string
  /** 已通过客户展示白名单的核对标准。 */
  requirement?: string
  /** 已通过客户展示白名单的实际值摘要。 */
  actual_value?: string
  target_document_type?: string
  evidences: QCRecordCompareEvidence[]
}

export interface SichuanBatchIssueItem {
  rule_id?: string
  rule_job_id?: string
  rule_code?: string
  rule_name?: string
  record_ref?: string
  reason_code?: string
  customer_display_facts?: Record<string, unknown>
  canonical_status?: string
  record_id?: string
  institute_id?: string
  patient_id?: string
  visit_id?: string
  patient_name?: string
  department?: string
  status: string
  is_compliant: boolean | null
  issues?: Array<{ description: string; evidence?: string }>
  conclusion?: string
  findings?: string
  evidence?: string | SichuanBatchSafeEvidenceRef[]
  suggestion?: string
  /** 原生规则可选的安全展示事实；严禁写入病历正文或模型原文。 */
  metadata?: Record<string, unknown>
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
  first_pass_status?: string
  first_pass_display_status?: string
  adjudicated_display_status?: string
  adjudicator_reason?: string
  adjudicator_supporting_quote?: string
  adjudicator_confidence?: number
  rule_requirement_match?: string
  qc_point_id?: string
  rule_set_key?: string
  rule_set_version?: string
  schema_version?: string
  result_status?: string
  trigger?: Record<string, unknown>
  dependencies?: Record<string, unknown>
  evidence_items?: Array<Record<string, unknown>>
  decision?: Record<string, unknown>
  review?: Record<string, unknown>
  audit?: Record<string, unknown>
}

export interface SichuanBatchFailedItem {
  rule_job_id?: string
  rule_id?: string
  record_id?: string
  record_ref?: string
  visit_id?: string
  patient_name?: string
  department?: string
  status?: string
  reason_code?: string
  failure_status?: string
  trace_id?: string
  rule_version?: string
  prompt_version?: string
  error_phase?: string
  error?: string
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
  wall_clock_time?: number
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

export interface SichuanBatchJobResultTrace {
  job_id?: string
  job_status?: string
  rule_set_key?: string
  rule_set_name?: string
  final_result?: Record<string, unknown>
  aggregation_trace?: Record<string, unknown>
  trigger?: Record<string, unknown>
  dependencies?: Record<string, unknown>
  decision?: Record<string, unknown>
  audit?: Record<string, unknown>
  review?: Record<string, unknown>
  evidence_items?: Array<Record<string, unknown>>
  source_execution_results?: Array<Record<string, unknown>>
  safety?: {
    sensitive_fields_removed?: string[]
    raw_output_returned?: boolean
    note?: string
  }
}

export interface SichuanBatchJob {
  id: string
  read_only?: boolean
  draft_id?: string
  draft_ids?: string[]
  job_kind?: string
  parent_job_id?: string
  child_job_ids?: string[]
  child_jobs?: SichuanBatchJob[]
  children?: SichuanBatchJob[]
  child_summary?: Record<string, unknown>
  family_key?: string
  family_name?: string
  rule_code: string
  rule_name: string
  scene?: string
  scope: 'all' | 'running' | 'final'
  execution_mode?: SichuanBatchExecutionMode
  rule_count?: number
  customer_rule_count?: number
  execution_rule_count?: number
  status: SichuanBatchJobStatus
  filters?: Record<string, unknown>
  record_ids?: string[]
  record_focus?: {
    record_ref?: string
  } | null
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
  wall_clock_time?: number
  rule_results?: SichuanBatchJobRuleResult[]
  idempotency_reused?: boolean
}

export interface SichuanBatchJobQuery {
  status?: SichuanBatchJobStatus
  scope?: 'all' | 'running' | 'final'
  q?: string
  executor_type?: 'program' | 'llm'
  cache_hit?: 'hit' | 'miss'
  created_start_date?: string
  created_end_date?: string
  record_id?: string
  page?: number
  page_size?: number
}

export interface SichuanBatchJobExport {
  job_id: string
  format?: 'xlsx' | 'csv' | 'html'
}

export interface SemanticRuleWorkspaceQueryState {
  ruleSetKey: string
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
  'ruleSetKey',
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
  daily_course_record: '日常病程记录',
  senior_course_record: '上级医师查房记录',
  rescue_record: '抢救记录',
  discharge_record: '出院记录',
  discharge_summary: '出院小结',
  operation_record: '手术记录',
  surgery_record: '手术记录',
  preop_summary: '术前小结',
  presurg_summary: '术前小结',
  presurg_discussion: '术前讨论记录',
  postsurg_firstcourse_record: '术后首次病程记录',
  surgery_safecheck_record: '手术安全核查表',
  surgery_risk_assessment: '手术风险评估',
  postop_first_record: '术后首次病程',
  examination_report: '辅助检查',
  exam_item_report: '检查报告',
  exam_attention_report: '重要检查报告',
  labtest_item_report: '检验报告',
  lab_attention_report: '危急值检验报告',
  consultation_record: '会诊记录',
  consent_form: '知情同意书',
  medical_order: '医嘱',
  case_discussion: '疑难病例讨论',
  transfusion_record: '输血记录',
  bloodtrans_record: '输血记录',
  anesthesia_record: '麻醉记录',
}

export function getDocTypeZh(value: string): string {
  return CANONICAL_DOC_TYPE_LABELS[value] || value
}

export const IMPLEMENTATION_STATUS_LABELS: Record<string, string> = {
  formal_ready: '正式可执行',
  ready_with_data_gap: '可执行，数据待补',
  needs_evidence_hardening: '需强化证据',
  needs_cross_document: '需跨文书补强',
  needs_data_linkage: '需数据联查',
  needs_rule_implementation: '待补规则',
}

export function getImplementationStatusZh(value?: string): string {
  const text = String(value || '')
  return IMPLEMENTATION_STATUS_LABELS[text] || text || '待确认'
}

export const DEPENDENCY_TYPE_LABELS: Record<string, string> = {
  single_document: '单文书判断',
  cross_document: '跨文书比对',
  cross_table: '跨表联查',
}

export function getDependencyTypeZh(value?: string): string {
  const text = String(value || '')
  return DEPENDENCY_TYPE_LABELS[text] || text || '依赖待确认'
}

export const DATA_STATUS_LABELS: Record<string, string> = {
  ready: '数据就绪',
  partial: '部分满足',
  needs_data_linkage: '需数据联查',
  data_gap: '数据待补强',
}

export function getDataStatusZh(value?: string): string {
  const text = String(value || '')
  return DATA_STATUS_LABELS[text] || text || '数据状态待确认'
}

export function getCategoryZh(value: string): string {
  return value
}

export function getSeverityZh(value: string): string {
  return value
}
