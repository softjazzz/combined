import { http } from '@/utils/http'

export type QCAgentStatus =
  | 'completed'
  | 'needs_clarification'
  | 'needs_confirmation'
  | 'unsupported'
  | string

export interface QCAgentUserContext {
  visit_id?: string
  patient_id?: string
  name?: string
  patient_name?: string
  department?: string
  dept?: string
  mr_no?: string
}

export interface QCAgentConfirmSelection {
  visit_id: string
  patient_id?: string
}

export interface QCAgentChatRequest {
  message: string
  session_id?: string
  user_context?: QCAgentUserContext
  confirm_selection?: QCAgentConfirmSelection
  dry_run?: boolean
}

export interface QCAgentPlanStep {
  tool_name?: string
  status?: string
  arguments?: Record<string, unknown>
  summary?: Record<string, unknown>
}

export interface QCAgentCandidate {
  visit_id?: string
  patient_id?: string
  patient_name?: string
  department?: string
  doctor?: string
  admission_date?: string
  discharge_date?: string
  mr_no?: string
}

export interface QCAgentQCSummary {
  issue_count?: number
  passed_count?: number
  skipped_count?: number
  rule_count?: number
  total_rules?: number
  passed?: number
  failed?: number
  pass_rate?: number
}

export interface QCAgentRuleIssue {
  rule_id?: string
  rule_name?: string
  passed?: boolean
  severity?: string
  category?: string
  document_ref?: string
  message?: string
  description?: string
  evidence_summary?: string
  suggestion?: string
}

export interface QCAgentSkippedRule {
  rule_id?: string
  rule_name?: string
  source?: string
  reason?: string
  severity?: string
}

export interface QCAgentRunResult {
  record_summary?: Record<string, unknown>
  document_selection_summary?: Record<string, unknown>
  qc_summary?: QCAgentQCSummary
  issues?: QCAgentRuleIssue[]
  results?: QCAgentRuleIssue[]
  selected_rules?: Array<Record<string, unknown>>
  executed_rules?: Array<Record<string, unknown>>
  skipped_rules?: QCAgentSkippedRule[]
  warnings?: string[]
}

export interface QCAgentChatResponse {
  status: QCAgentStatus
  parsed_intent?: Record<string, unknown>
  plan?: QCAgentPlanStep[]
  candidates?: QCAgentCandidate[]
  result?: QCAgentRunResult
  warnings?: string[]
  run_id?: string
  session_id?: string
}

export const qcAgentApi = {
  async chat(request: QCAgentChatRequest): Promise<QCAgentChatResponse> {
    const response = await http.post('/api/v1/qc-agent/chat', request, {
      timeout: 120000,
    })
    return response.data
  },
}

export default qcAgentApi
