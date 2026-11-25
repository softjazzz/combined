import { RUN_CREATE_TIMEOUT_MS } from '@/config/requestTimeouts'
import { ApiService, type ApiRequestConfig } from './apiService'

/** 规则验收接口（/api/v1/qc/rule-validation）的数据契约，与后端 rule_validation 路由一一对应。 */

export type ExpectedStatus = 'compliant' | 'non_compliant' | 'not_applicable' | 'data_gap' | 'data_quality_gap'
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
export type Comparison = 'same' | 'different' | 'missing' | 'ambiguous' | 'pending' | 'failed' | 'baseline_missing'

/** 上线影响范围：共享抽取批次的规则须按“上线后范围”运行并回归同族保护集 */
export type ImpactKind = 'independent' | 'shared_batch' | 'unverified'
export type RuleImpact = {
  impact: ImpactKind
  label: string
  executor_key: string
  basis: string
  peer_rule_ids: string[]
}

export type RuleInfo = {
  rule_id: string
  name: string
  source_document: string
  release_scope: 'default' | 'acceptance_only'
  policy_summary: string
  impact?: RuleImpact | null
  rule_set_key?: string
  publication_supported?: boolean
  publication_note?: string
  execution_mode?: 'full_pack'
  execution_rule_ids?: string[]
}

export type RegressionGap = { rule_id: string; name: string; reason: string }

export type CoverageCounts = Partial<Record<ExpectedStatus, Record<SourceKind, number>>>
export type Coverage = { counts: CoverageCounts; gaps: ExpectedStatus[]; acceptance_cases: number }

export type RecordRef = { institute_id: string; patient_id: string; visit_id: string }

export type ValidationCase = {
  item_id: string
  case_title: string
  record_ref: RecordRef
  department?: string
  source_kind: SourceKind
  evaluation_as_of_date: string | null
  expected_status: ExpectedStatus
  human_reason: string
  purpose: CasePurpose
  answer_revision: number
  labeled_by?: string | null
  labeled_at?: string | null
}

export type CandidateCase = Pick<
  ValidationCase,
  'item_id' | 'case_title' | 'source_kind' | 'evaluation_as_of_date'
>

export type ExecutionVersion = {
  rule_set_key?: string
  lx0609_task_runtime?: {
    implementation?: { kind: string; build_id?: string; git_commit?: string; id?: string }
    first_pass?: { provider?: string; model?: string }
  }
}

export type ValidationRun = {
  id: string
  rule_id: string
  cases: ValidationCase[]
  /** 同族已上线规则的保护集病例（rule_id 为同族规则） */
  regression_cases: (ValidationCase & { rule_id: string })[]
  scope_rule_ids: string[]
  regression_gaps: RegressionGap[]
  impact: RuleImpact | null
  job_id: string | null
  state: 'creating' | 'bound' | 'creation_failed'
  execution_version: ExecutionVersion | null
  build_kind: 'release' | 'development' | null
  created_by: string
  created_at: string
}

/** 结果的客户安全投影，仅用于逐例核对展示。 */
export type CaseResult = {
  document_anchors?: Record<string, unknown>[]
  status?: string
  display_status?: string
  reason_code?: string
  customer_conclusion?: string
  conclusion?: string
  customer_suggestion?: string
  suggestion?: string
  customer_display_facts?: Record<string, unknown>
  criterion_results?: import('@/views/workstation-v4/customer-sample-validation/single-record-result-model').SingleRecordQcCriterionResult[]
  findings?: unknown
  evidence?: unknown
}

export type ComparisonRow = ValidationCase & {
  rule_id: string
  role: 'candidate' | 'regression'
  actual_status: string | null
  comparison: Comparison
  result?: CaseResult
  regression_comparison?: {
    baseline_run_id: string | null
    baseline_job_id: string | null
    baseline: CaseResult | null
    status: 'same' | 'different' | 'baseline_missing'
    changed_fields: string[]
    metrics: {
      basis: 'whole_job'
      baseline: RegressionMetrics
      current: RegressionMetrics
      delta: RegressionMetrics | null
      baseline_scope: { rule_ids: string[]; record_count: number }
      current_scope: { rule_ids: string[]; record_count: number }
      comparable: boolean
      reason: string
    }
  }
}

export type RegressionMetrics = { llm_calls: number | null; tokens: number | null; elapsed_seconds: number | null }

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
  regression_gaps: RegressionGap[]
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

export const listValidationRules = (
  includeReleased = false,
  ruleSetKey = 'luxian_0609_qc_v1',
  config?: ApiRequestConfig,
) =>
  ApiService.get<{ items: RuleListItem[] }>(
    `${BASE}/rules`,
    {
      include_released: includeReleased,
      rule_set_key: ruleSetKey,
    },
    config,
  )
export const getValidationRule = (ruleId: string, config?: ApiRequestConfig) =>
  ApiService.get<RuleDetail>(rule(ruleId), undefined, config)
export const listCandidateCases = (ruleId: string, config?: ApiRequestConfig) =>
  ApiService.get<{ items: CandidateCase[] }>(`${rule(ruleId)}/candidate-cases`, undefined, config)
export const saveCaseAnswer = (
  ruleId: string,
  itemId: string,
  payload: CaseAnswerPayload,
  config?: ApiRequestConfig,
) => ApiService.put<ValidationCase>(`${rule(ruleId)}/cases/${encodeURIComponent(itemId)}`, payload, config)
export const removeCaseAnswer = (ruleId: string, itemId: string, revision: number) =>
  ApiService.delete<{ removed: boolean }>(`${rule(ruleId)}/cases/${encodeURIComponent(itemId)}`, {
    params: { revision },
  })
/** 创建运行要走正式任务创建链路（实测约 25 秒），不能用默认 15 秒超时，否则前端报错而后台已建成 */
export { RUN_CREATE_TIMEOUT_MS }
export const startValidationRun = (
  ruleId: string,
  itemIds?: string[],
  config?: ApiRequestConfig,
) =>
  ApiService.post<{ run_id: string; job_id: string }>(
    `${rule(ruleId)}/runs`,
    { item_ids: itemIds ?? null },
    { timeout: RUN_CREATE_TIMEOUT_MS, ...config },
  )
export const getValidationRun = (runId: string, config?: ApiRequestConfig) =>
  ApiService.get<RunDetail>(`${BASE}/runs/${encodeURIComponent(runId)}`, undefined, config)
export const reviewCase = (
  runId: string,
  itemId: string,
  decision: 'confirmed' | 'problem',
  note: string,
) =>
  ApiService.post<ValidationEvent>(
    `${BASE}/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(itemId)}/reviews`,
    { decision, note },
  )
export const concludeRule = (
  ruleId: string,
  payload: { run_id: string; decision: 'accepted' | 'rejected'; note: string; gap_ack: string },
  config?: ApiRequestConfig,
) => ApiService.post<ValidationEvent>(`${rule(ruleId)}/conclusion`, payload, config)
export const approveRule = (ruleId: string, decision: 'approved' | 'rejected', note: string) =>
  ApiService.post<ValidationEvent>(`${rule(ruleId)}/approval`, { decision, note })
