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
}
export interface BusinessAgentTurn {
  run_id: string
  question: string
  answer: string
  status: 'completed' | 'failed' | 'stopped'
  references: BusinessAgentReference[]
  tool_calls: number
  model_calls?: number
  reference_scope?: 'prior_turns'
  elapsed_ms: number
  usage?: { input_tokens: number; output_tokens: number }
  error?: string
}
export interface BusinessAgentSession {
  session_id: string
  context: BusinessAgentContext
  turns: BusinessAgentTurn[]
}
export const businessAgentApi = {
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
}
