import { ApiService } from './apiService'

/** 规则验收接口（/api/v1/qc/rule-validation）的数据契约，与后端 rule_validation 路由一一对应。 */

export type ExpectedStatus = 'compliant' | 'non_compliant' | 'not_applicable' | 'data_gap'
export type CasePurpose = 'development' | 'acceptance'
export type SourceKind = 'synthetic' | 'real_copy'
export type ValidationStage =
  | 'preparing'
  | 'ready_to_run'
  | 'running'
  | 'reviewing'
  | 'pending_conclusion'
  | 'pending_approval'
  | 'approved_pending_release'
  | 'released'
  | 'rejected'
export type Comparison = 'same' | 'different' | 'missing' | 'ambiguous' | 'pending' | 'failed'

export type RuleInfo = {
  rule_id: string
  name: string
  source_document: string
  release_scope: 'default' | 'acceptance_only'
  policy_summary: string
  impact_class?: string
}

export type CoverageCounts = Record<ExpectedStatus, Record<SourceKind, number>>
export type Coverage = { counts: CoverageCounts; gaps: ExpectedStatus[]; acceptance_cases: number }

export type RecordRef = { institute_id: string; patient_id: string; visit_id: string }

export type ValidationCase = {
  item_id: string
  case_title: string
  record_ref: RecordRef
  source_kind: SourceKind
  evaluation_as_of_date: string | null
  expected_status: ExpectedStatus
  human_reason: string
  purpose: CasePurpose
  answer_revision: number
  labeled_by?: string | null
  labeled_at?: string | null
}

export type CandidateCase = Pick<ValidationCase, 'item_id' | 'case_title' | 'source_kind' | 'evaluation_as_of_date'>

export type ExecutionVersion = {
  lx0609_task_runtime?: {
    implementation?: { kind: string; build_id?: string; git_commit?: string; id?: string }
    first_pass?: { provider?: string; model?: string }
  }
}

export type ValidationRun = {
  id: string
  rule_id: string
  cases: ValidationCase[]
  job_id: string | null
  state: 'creating' | 'bound' | 'creation_failed'
  execution_version: ExecutionVersion | null
  build_kind: 'release' | 'development' | null
  created_by: string
  created_at: string
}

/** 结果的客户安全投影，仅用于逐例核对展示。 */
export type CaseResult = {
  status?: string
  display_status?: string
  reason_code?: string
  customer_conclusion?: string
  conclusion?: string
  customer_suggestion?: string
  suggestion?: string
  findings?: unknown
  evidence?: unknown
}

export type ComparisonRow = ValidationCase & {
  actual_status: string | null
  comparison: Comparison
  result?: CaseResult
}

export type ValidationEvent = {
  id: string
  rule_id: string
  run_id: string | null
  item_id: string | null
  kind: 'case_review' | 'conclusion' | 'approval'
  decision: string
  note: string
  payload: Record<string, unknown>
  actor: string
  created_at: string
}

export type RuleListItem = RuleInfo & {
  stage: ValidationStage
  case_count: number
  coverage: Coverage
  latest_run: ValidationRun | null
}

export type RuleDetail = {
  rule: RuleInfo
  stage: ValidationStage
  cases: ValidationCase[]
  coverage: Coverage
  runs: ValidationRun[]
  latest_run_rows: ComparisonRow[] | null
  acceptance_blockers: string[]
  events: ValidationEvent[]
}

export type RunDetail = { run: ValidationRun; rows: ComparisonRow[]; reviews: ValidationEvent[] }

export type CaseAnswerPayload = {
  revision: number
  expected_status: ExpectedStatus
  human_reason: string
  purpose: CasePurpose
}

const BASE = '/api/v1/qc/rule-validation'
const rule = (id: string) => `${BASE}/rules/${encodeURIComponent(id)}`

export const listValidationRules = (includeReleased = false) =>
  ApiService.get<{ items: RuleListItem[] }>(`${BASE}/rules`, { include_released: includeReleased })
export const getValidationRule = (ruleId: string) => ApiService.get<RuleDetail>(rule(ruleId))
export const listCandidateCases = (ruleId: string) =>
  ApiService.get<{ items: CandidateCase[] }>(`${rule(ruleId)}/candidate-cases`)
export const saveCaseAnswer = (ruleId: string, itemId: string, payload: CaseAnswerPayload) =>
  ApiService.put<ValidationCase>(`${rule(ruleId)}/cases/${encodeURIComponent(itemId)}`, payload)
export const removeCaseAnswer = (ruleId: string, itemId: string, revision: number) =>
  ApiService.delete<{ removed: boolean }>(`${rule(ruleId)}/cases/${encodeURIComponent(itemId)}`, {
    params: { revision },
  })
export const startValidationRun = (ruleId: string, itemIds?: string[]) =>
  ApiService.post<{ run_id: string; job_id: string }>(`${rule(ruleId)}/runs`, { item_ids: itemIds ?? null })
export const getValidationRun = (runId: string) =>
  ApiService.get<RunDetail>(`${BASE}/runs/${encodeURIComponent(runId)}`)
export const reviewCase = (runId: string, itemId: string, decision: 'confirmed' | 'problem', note: string) =>
  ApiService.post<ValidationEvent>(
    `${BASE}/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(itemId)}/reviews`,
    { decision, note },
  )
export const concludeRule = (
  ruleId: string,
  payload: { run_id: string; decision: 'accepted' | 'rejected'; note: string; gap_ack: string },
) => ApiService.post<ValidationEvent>(`${rule(ruleId)}/conclusion`, payload)
export const approveRule = (ruleId: string, decision: 'approved' | 'rejected', note: string) =>
  ApiService.post<ValidationEvent>(`${rule(ruleId)}/approval`, { decision, note })
