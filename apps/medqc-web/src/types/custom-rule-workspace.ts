export type WorkspaceScope = 'all' | 'running' | 'final'
export type WorkspaceDraftStatus = 'draft' | 'published'
export type WorkspaceSeverity = 'critical' | 'major' | 'minor'
export type WorkspaceGenerationMode = 'llm' | 'fallback_template'
export type CustomRuleEditorDrawerMode = 'create' | 'edit' | 'copy'
export type CustomRuleTestResultPanelState = 'single' | 'batch' | 'empty'
export type CustomRuleBatchJobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'canceled'
export type CustomRuleBatchExecutionMode = 'single' | 'multi'
export type CustomRuleBatchRunMode = 'serial' | 'parallel'

export interface CustomRuleDraft {
  id: string
  rule_code: string
  name: string
  description: string
  source_requirement: string
  prompt_template: string
  document_type: string
  applicable_documents: string[]
  severity: WorkspaceSeverity
  defect_level: string
  complexity: string
  scene: 'running' | 'final'
  generation_mode: WorkspaceGenerationMode
  examples: Array<{ title: string; content: string }>
  check_logic: Record<string, unknown>
  last_test_summary?: Record<string, unknown> | null
  status: WorkspaceDraftStatus
  published_rule_id?: string
  created_by: string
  created_at: string
  updated_at: string
  category?: string
  rule_type?: string
  /** 列表接口按服务端固定测试证明计算的可上线标记；旧接口缺失时视为未知。 */
  publish_ready?: boolean
  publish_blocked_reason?: string | null
}

export interface CustomRuleDraftBatchPublishItem {
  draft_id: string
  expected_updated_at: string
  validation_id: string
}

export interface CustomRuleDraftBasicInfo {
  id: string
  rule_code: string
  status: 'draft'
  updated_at: string
  name: string
  category: string
  rule_type: string
  document_type: string
}

export interface CustomRuleDraftBasicInfoInput {
  name: string
  category: string
  rule_type: string
  document_type: string
}

export interface CustomRuleDocumentOption {
  value: string
  label: string
}

export type VisualConditionGroupOperator = 'all' | 'any'
export type VisualConditionValueType = 'string' | 'number' | 'datetime' | 'boolean'
export type VisualConditionTimeUnit = 'minutes' | 'hours' | 'days'

export interface VisualConditionOption {
  value: string
  label: string
}

export interface VisualConditionFieldOperator extends VisualConditionOption {
  value_required: boolean
  value_options?: VisualConditionOption[]
}

export interface VisualConditionFieldOption {
  key: string
  label: string
  value_type: VisualConditionValueType
  operators: VisualConditionFieldOperator[]
  kind: 'record' | 'document'
  document_type?: string
  aggregation?: 'earliest' | 'latest'
}

export interface VisualConditionOptions {
  schema_version: 'visual-condition-v1'
  fields: VisualConditionFieldOption[]
  document_types: VisualConditionOption[]
  group_operators: VisualConditionGroupOperator[]
  limits: {
    max_groups: number
    max_conditions_per_group: number
  }
  result_semantics: {
    true: 'non_compliant'
    false: 'compliant'
    unknown: 'data_gap'
  }
  timeliness: {
    start_fields: VisualConditionOption[]
    end_fields: VisualConditionOption[]
    allowed_pairs: Array<{ start_fact: string; end_fact: string }>
    operators: Array<VisualConditionOption & { value: 'lt' | 'lte' | 'gt' | 'gte' }>
    units: Array<VisualConditionOption & { value: VisualConditionTimeUnit }>
  }
}

export type VisualCondition =
  | { id: string; kind: 'field'; fact_key: string; operator: string; value?: string | string[] | number | boolean }
  | { id: string; kind: 'document_presence'; document_type: string; operator: 'exists' | 'not_exists' }
  | {
    id: string
    kind: 'timeliness'
    start_fact: string
    end_fact: string
    operator: 'lt' | 'lte' | 'gt' | 'gte'
    threshold: { value: number; unit: VisualConditionTimeUnit }
  }

export interface VisualConditionGroup {
  id: string
  operator: VisualConditionGroupOperator
  conditions: VisualCondition[]
}

export interface VisualConditionTree {
  schema_version: 'visual-condition-v1'
  root_operator: VisualConditionGroupOperator
  groups: VisualConditionGroup[]
}

export interface CustomRuleDraftCondition {
  id: string
  rule_code: string
  status: 'draft'
  updated_at: string
  visual_condition: VisualConditionTree | null
}

export type FixedTestValidationStatus =
  | 'compliant'
  | 'non_compliant'
  | 'ai_suggested_compliant'
  | 'ai_suggested_non_compliant'
  | 'data_gap'
  | 'not_applicable'
  | 'not_executed'
  | 'technical_error'
  | 'uncertain'
export type FixedTestValidationUnavailableReason =
  | 'test_records_changed'
  | 'not_tested'
  | 'draft_changed'
  | 'validation_incomplete'
  | 'draft_not_executable'

export interface FixedTestRecordRef {
  institute_id: string
  patient_id: string
  visit_id: string
}

export interface FixedTestValidationResult {
  item_id: string
  item_updated_at: string
  record_ref: FixedTestRecordRef
  status: FixedTestValidationStatus
  issue_count: number
  finding: { description: string; evidence: string }
  condition_trace: string[]
}

export interface FixedTestValidationProof {
  schema_version: 'fixed_test_records_v1'
  validation_id: string
  draft_id: string
  validated_revision: string
  proof_revision: string
  created_at: string
  item_count: number
  success_count: number
  failed_count: number
  issue_records: number
  compliant_records: number
  unknown_count: number
  technical_error_count: number
  selected_items: Array<{
    item_id: string
    item_updated_at: string
    record_ref: FixedTestRecordRef
  }>
  results: FixedTestValidationResult[]
  failures: Array<{ item_id: string; code: string; message: string }>
}

export interface FixedTestValidationState {
  draft_id: string
  draft_updated_at: string
  draft_status: 'draft' | 'published'
  published_rule_id: string | null
  validation: FixedTestValidationProof | null
  publish_ready: boolean
  unavailable_reason: FixedTestValidationUnavailableReason | null
}

export interface FixedTestValidationInput {
  expected_updated_at: string
  items: Array<{ item_id: string; expected_updated_at: string }>
}

export interface CustomRuleDraftPayload {
  name: string
  description: string
  source_requirement?: string
  prompt_template?: string
  document_type: string
  severity: WorkspaceSeverity
  defect_level?: string
  complexity: string
  scene: 'running' | 'final'
  generation_mode?: WorkspaceGenerationMode
  applicable_documents?: string[]
  examples?: Array<{ title: string; content: string }>
  check_logic?: Record<string, unknown>
}

export interface CustomRuleWorkspaceRecordRef {
  institute_id: string
  patient_id: string
  visit_id: string
}

export interface CustomRuleWorkspaceRecord {
  institute_id: string
  patient_id: string
  record_id: string
  visit_id: string
  record_key: string
  patient_name: string
  mr_no?: string
  inpat_no?: string
  scope: WorkspaceScope
  department: string
  doctor: string
  admission_date: string
  discharge_date: string
  status: string
  medical_text_length: number
}

export interface CustomRuleWorkspaceBatchJobCreatePayload {
  draft_id?: string
  draft_ids?: string[]
  execution_mode?: 'single' | 'multi'
  run_mode?: 'serial' | 'parallel'
  scope: WorkspaceScope
  department?: string
  doctor?: string
  date_field: 'admission' | 'discharge'
  start_date?: string
  end_date?: string
  keyword?: string
  record_refs?: CustomRuleWorkspaceRecordRef[]
  temperature?: number
  top_p?: number
  max_tokens?: number
}

export interface CustomRuleWorkspaceFilters {
  departments: string[]
  doctors: string[]
  date_bounds: {
    admission: { min: string; max: string }
    discharge: { min: string; max: string }
  }
}

export interface CustomRuleWorkspaceRecordQuery {
  scope: WorkspaceScope
  department?: string
  doctor?: string
  date_field: 'admission' | 'discharge'
  start_date?: string
  end_date?: string
  keyword?: string
  page: number
  page_size: number
}

export interface CustomRuleWorkspaceTestRecord {
  record_id: string
  visit_id?: string
  patient_name?: string
  department?: string
  doctor?: string
  medical_text?: string
}

export interface CustomRuleSingleTestResult {
  draft_id: string
  rule: {
    name: string
    description: string
    prompt_template: string
    severity: WorkspaceSeverity
    document_type: string
    scene: 'running' | 'final'
    check_logic: Record<string, unknown>
  }
  record: {
    record_id: string
    visit_id?: string
    patient_name?: string
    department?: string
  }
  result: {
    record_id: string
    visit_id?: string
    patient_name?: string
    department?: string
    document_type: string
    status: string
    is_compliant: boolean
    issues: Array<{ description: string; evidence?: string }>
    findings: string
    evidence: string
    suggestion: string
    confidence: number
    performance?: {
      processing_time: number
      token_usage: number
      estimated_cost: number
    }
  }
  summary: Record<string, unknown>
  timestamp: string
  status: string
}

export interface CustomRuleBatchResult {
  draft_id: string
  rule: {
    name: string
    description: string
    prompt_template: string
    severity: WorkspaceSeverity
    document_type: string
    scene: 'running' | 'final'
    check_logic: Record<string, unknown>
  }
  summary: {
    total_records: number
    success_count: number
    failed_count: number
    issue_records: number
    compliant_records: number
    total_tokens: number
    total_processing_time: number
    updated_at?: string
  }
  items: Array<{
    record_id: string
    visit_id?: string
    patient_name?: string
    department?: string
    status: string
    is_compliant: boolean
    findings: string
    evidence: string
    suggestion: string
    confidence: number
  }>
  failed_records: Array<{
    record_id: string
    visit_id?: string
    patient_name?: string
    department?: string
    error: string
  }>
  timestamp: string
  status: string
}

export interface CustomRulePublishResult {
  draft_id: string
  rule_code: string
  published_rule_id: string
  status: 'published'
}

export interface CustomRuleBatchJobSummary {
  total_records: number
  total_tasks?: number
  rule_count?: number
  processed_rule_count?: number
  execution_mode?: CustomRuleBatchExecutionMode
  success_count: number
  failed_count: number
  issue_records: number
  compliant_records: number
  total_tokens: number
  total_processing_time: number
  executor_breakdown?: {
    program: number
    llm: number
  }
  cache_breakdown?: {
    hit: number
    miss: number
  }
  progress?: CustomRuleBatchJobProgress
  rule_results?: CustomRuleBatchJobRuleResult[]
  updated_at?: string
}

export interface CustomRuleBatchJobProgress {
  step_key: string
  rule_index: number
  rule_count: number
  processed_records: number
  total_records: number
}

export interface CustomRuleBatchJobRuleResult {
  id?: string
  draft_id?: string
  rule_code: string
  rule_name: string
  status: CustomRuleBatchJobStatus | string
  progress?: Partial<CustomRuleBatchJobProgress>
  total_records?: number
  success_count?: number
  failed_count?: number
  issue_records?: number
  compliant_records?: number
  total_tokens?: number
  total_processing_time?: number
  executor_breakdown?: {
    program: number
    llm: number
  }
  cache_breakdown?: {
    hit: number
    miss: number
  }
  items?: CustomRuleBatchIssueItem[]
  failed_records?: CustomRuleBatchFailedRecord[]
  updated_at?: string
}

type CustomRuleBatchIssueBase = CustomRuleBatchResult['items'][number]
type CustomRuleBatchFailedRecordBase = CustomRuleBatchResult['failed_records'][number]

export interface CustomRuleBatchIssueItem extends CustomRuleBatchIssueBase {
  draft_id?: string
  rule_code?: string
  rule_name?: string
  metadata?: Record<string, unknown>
  executor_breakdown?: {
    program: number
    llm: number
  }
  cache_breakdown?: {
    hit: number
    miss: number
  }
}

export interface CustomRuleBatchFailedRecord extends CustomRuleBatchFailedRecordBase {
  draft_id?: string
  rule_code?: string
  rule_name?: string
}

export interface CustomRuleBatchJob {
  id: string
  draft_id: string
  draft_ids?: string[]
  rule_code: string
  rule_name: string
  scene: 'running' | 'final'
  scope: WorkspaceScope
  execution_mode?: CustomRuleBatchExecutionMode
  run_mode?: CustomRuleBatchRunMode
  rule_count?: number
  status: CustomRuleBatchJobStatus
  filters: Record<string, unknown>
  record_ids: string[]
  summary?: CustomRuleBatchJobSummary | null
  progress?: CustomRuleBatchJobProgress
  items: CustomRuleBatchIssueItem[]
  failed_records: CustomRuleBatchFailedRecord[]
  rule_results?: CustomRuleBatchJobRuleResult[]
  cancellable?: boolean
  error_message?: string
  created_by: string
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  updated_at: string
  total_records: number
  success_count: number
  failed_count: number
  issue_records: number
  compliant_records: number
  total_tokens: number
  total_processing_time: number
}

export interface CustomRuleBatchJobQuery {
  draft_id?: string
  status?: CustomRuleBatchJobStatus
  scope?: WorkspaceScope
  q?: string
  executor_type?: 'program' | 'llm'
  cache_hit?: 'hit' | 'miss'
  created_start_date?: string
  created_end_date?: string
  page?: number
  page_size?: number
}

export interface CustomRuleBatchJobExport {
  job_id: string
  format?: 'xlsx' | 'csv'
}

export interface CustomRuleWorkspaceScopeSwitchState {
  scope: WorkspaceScope
  label: string
}

export interface CustomRuleWorkspaceSelectionState {
  selectedDraftId: string | null
  selectedRecordKeys: string[]
  resultState: CustomRuleTestResultPanelState
}
