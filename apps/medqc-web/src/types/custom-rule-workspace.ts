export type WorkspaceScope = 'all' | 'running' | 'final'
export type WorkspaceDraftStatus = 'draft' | 'published'
export type WorkspaceSeverity = 'critical' | 'major' | 'minor'
export type WorkspaceGenerationMode = 'llm' | 'fallback_template'
export type CustomRuleEditorDrawerMode = 'create' | 'edit' | 'copy'
export type CustomRuleTestResultPanelState = 'single' | 'batch' | 'empty'
export type CustomRuleBatchJobStatus = 'queued' | 'running' | 'completed' | 'failed'

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

export interface CustomRuleWorkspaceRecord {
  record_id: string
  visit_id: string
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
  success_count: number
  failed_count: number
  issue_records: number
  compliant_records: number
  total_tokens: number
  total_processing_time: number
  updated_at?: string
}

export interface CustomRuleBatchJob {
  id: string
  draft_id: string
  rule_code: string
  rule_name: string
  scene: 'running' | 'final'
  scope: WorkspaceScope
  status: CustomRuleBatchJobStatus
  filters: Record<string, unknown>
  record_ids: string[]
  summary?: CustomRuleBatchJobSummary | null
  items: CustomRuleBatchResult['items']
  failed_records: CustomRuleBatchResult['failed_records']
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
