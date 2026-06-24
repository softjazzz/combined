import type { Database } from '@/types/database-schema'

export type QCRuleInsert = Database['public']['Tables']['qc_rules']['Insert']

export type CustomQcScene = 'running' | 'final'

export interface CustomQcDraftRule {
  name: string
  description: string
  prompt_template: string
  severity: 'critical' | 'major' | 'minor'
  document_type: string
  scene?: CustomQcScene
  check_logic?: Record<string, unknown>
}

export interface CustomQcPromptGenerationResult {
  prompt_template: string
  generation_mode: 'llm' | 'fallback_template'
  summary: string
  check_points: string[]
  examples: Array<{
    title: string
    content: string
  }>
}

export interface CustomQcCandidateRecord {
  id?: string
  record_id: string
  visit_id?: string
  patient_name?: string
  department?: string
  discharge_date?: string
  status?: string
  score?: number
  defect_count?: number
}

export interface CustomQcRecordPayload {
  record_id: string
  visit_id?: string
  patient_name?: string
  department?: string
  medical_text: string
}

export interface CustomQcSingleTestResult {
  rule: CustomQcDraftRule
  record: Omit<CustomQcRecordPayload, 'medical_text'>
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
    evidence_verified?: boolean
    applicability?: Record<string, unknown>
    metadata?: Record<string, unknown>
    performance?: {
      processing_time: number
      token_usage: number
      estimated_cost: number
    }
  }
  timestamp: string
  status: string
}

export interface CustomQcBatchItemResult {
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

export interface CustomQcBatchTestResult {
  rule: CustomQcDraftRule
  summary: {
    total_records: number
    success_count: number
    failed_count: number
    issue_records: number
    compliant_records: number
    total_tokens: number
    total_processing_time: number
  }
  items: CustomQcBatchItemResult[]
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

export interface CustomQcPublishPayload extends QCRuleInsert {}
