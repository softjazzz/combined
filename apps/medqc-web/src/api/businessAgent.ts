import { http } from '@/utils/http'

export interface BusinessAgentContext {
  view: 'doctor' | 'manager'
  institute_id?: string
  patient_id?: string
  visit_id?: string
  patient_name?: string
  document_id?: string
  department?: string
  care_phase?: 'inpatient' | 'discharged'
  completed_from?: string
  completed_to?: string
}
export interface BusinessAgentReference {
  id: string
  title: string
  kind: 'saved_result' | 'evidence' | 'guideline' | 'rule' | 'statistics' | 'record'
  text?: string
  locator?: string
  rule_id?: string
  status?: string
  conclusion?: string
  suggestion?: string
  position?: number
  evidence?: {
    source_type: string
    source_ref: string
    record_time?: string
    evidence_excerpt?: string
    excerpt_kind?: string
    field_path?: string
  }[]
}
export interface BusinessEvidenceDocument {
  title: string
  source_view: 'current'
  state:
    | 'located'
    | 'source_not_found'
    | 'source_ambiguous'
    | 'source_type_mismatch'
    | 'quote_not_found'
    | 'quote_ambiguous'
  content?: string
  quote: string
  matched_quote?: string
  match_scope?: 'exact_excerpt' | 'excerpt_prefix'
  note: string
  record_time?: string
  start?: number
  end?: number
  offset_unit?: 'unicode_code_points'
}
export interface BusinessAgentTurn {
  run_id: string
  question: string
  answer: string
  status: 'completed' | 'failed' | 'stopped'
  references: BusinessAgentReference[]
  result_pages?: BusinessResultPage[]
  tool_calls: number
  model_calls?: number
  reference_scope?: 'prior_turns'
  elapsed_ms: number
  usage?: { input_tokens: number; output_tokens: number }
  error?: string
}
export interface BusinessResultPage {
  job_id: string
  record_ref: string
  statuses: string[]
  page: number
  page_size: number
  total: number
  matched_total: number
  returned: number
  has_more: boolean
  status_counts: Record<string, number>
  reference_ids: string[]
}
export interface BusinessAgentSession {
  session_id: string
  context: BusinessAgentContext
  turns: BusinessAgentTurn[]
}
export interface BusinessAgentAccess {
  doctor_case_count: number
  doctor_cases?: { institute_id: string; patient_id: string; visit_id: string }[]
  manager_scopes: { institute_id: string; department: string }[]
}
export const businessAgentApi = {
  async access(): Promise<BusinessAgentAccess> {
    return (await http.get('/api/v1/qc-agent/business/access')).data
  },
  async create(context: BusinessAgentContext): Promise<BusinessAgentSession> {
    return (await http.post('/api/v1/qc-agent/business/sessions', { context })).data
  },
  async restore(sessionId: string): Promise<BusinessAgentSession> {
    return (await http.get(`/api/v1/qc-agent/business/sessions/${sessionId}`)).data
  },
  async chat(
    sessionId: string,
    runId: string,
    message: string,
    signal: AbortSignal,
    referenceId?: string,
  ): Promise<BusinessAgentTurn> {
    return (
      await http.post(
        `/api/v1/qc-agent/business/sessions/${sessionId}/chat`,
        {
          run_id: runId,
          message,
          reference_id: referenceId,
        },
        { signal, timeout: 70000 },
      )
    ).data
  },
  async stop(sessionId: string, runId: string): Promise<void> {
    await http.post(`/api/v1/qc-agent/business/sessions/${sessionId}/stop`, { run_id: runId })
  },
  async reference(sessionId: string, referenceId: string): Promise<BusinessAgentReference> {
    return (
      await http.get(
        `/api/v1/qc-agent/business/sessions/${sessionId}/references/${encodeURIComponent(referenceId)}`,
      )
    ).data
  },
  async evidenceDocument(
    sessionId: string,
    referenceId: string,
    evidenceIndex: number,
  ): Promise<BusinessEvidenceDocument> {
    return (
      await http.get(`/api/v1/qc-agent/business/sessions/${sessionId}/evidence-document`, {
        params: { reference_id: referenceId, evidence_index: evidenceIndex },
        timeout: 60000,
      })
    ).data
  },
}
