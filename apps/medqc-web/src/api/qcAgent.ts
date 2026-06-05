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
  status?: 'passed' | 'failed' | string
  severity?: string
  category?: string
  document_ref?: string
  document_type?: string
  source_table?: string
  check_type?: string
  checked_target?: string
  explanation?: string
  message?: string
  description?: string
  evidence_summary?: string
  matched_documents?: QCAgentMatchedDocument[]
  suggestion?: string
}

export interface QCAgentMatchedDocument {
  document_type?: string
  record_time?: string
  text_length?: number
  source_table?: string
}

export interface QCAgentExecutedRule extends QCAgentRuleIssue {
  status?: 'passed' | 'failed' | string
  check_type?: string
  checked_target?: string
  explanation?: string
  matched_documents?: QCAgentMatchedDocument[]
}

export interface QCAgentSkippedRule {
  rule_id?: string
  rule_name?: string
  source?: string
  reason?: string
  reason_label?: string
  next_step?: string
  severity?: string
}

export interface QCAgentICDCandidate {
  code?: string
  name?: string
  type?: string
  version?: string
  mapped_code?: string
  mapped_name?: string
  confidence?: number
  match_type?: string
}

export interface QCAgentCodingSuggestionItem {
  name?: string
  existing_code?: string
  source?: string
  confidence?: number
  low_confidence?: boolean
  candidates?: QCAgentICDCandidate[]
}

export interface QCAgentGroupingInputSummary {
  city_name?: string
  pdx_code?: string
  adx_count?: number
  proc_count?: number
  primary_diagnosis_code?: string
  secondary_diagnosis_count?: number
  procedure_count?: number
  patient_gender?: string
  patient_age?: number
  los?: number
  total_fee?: number
  total_cost?: number
  region?: string
}

export interface QCAgentRunResult {
  record_summary?: Record<string, unknown>
  document_selection_summary?: Record<string, unknown>
  qc_summary?: QCAgentQCSummary
  issues?: QCAgentRuleIssue[]
  results?: QCAgentRuleIssue[]
  selected_rules?: Array<Record<string, unknown>>
  executed_rules?: QCAgentExecutedRule[]
  skipped_rules?: QCAgentSkippedRule[]
  warnings?: string[]
  query?: string
  code_type?: 'diagnosis' | 'procedure' | 'all' | string
  version?: 'insurance' | 'clinical' | string
  returned?: number
  candidates?: QCAgentICDCandidate[]
  diagnosis_candidates?: QCAgentCodingSuggestionItem[]
  procedure_candidates?: QCAgentCodingSuggestionItem[]
  success?: boolean
  fallback?: boolean
  external_call?: boolean
  error_summary?: string
  input_summary?: QCAgentGroupingInputSummary
  dip_code?: string
  dip_name?: string
  dip_type?: string
  grouping_path?: string
  adrg_code?: string
  adrg_name?: string
  drg_code?: string
  drg_name?: string
  weight?: number
  baseline_payment?: number
  profit_margin?: number
  mapped_code?: string
  mapped_code_name?: string
  grouping_logic?: string
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
