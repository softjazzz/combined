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
}

export interface SemanticRuleWorkspaceQueryState {
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
  discharge_record: '出院记录',
  discharge_summary: '出院小结',
  operation_record: '手术记录',
  preop_summary: '术前小结',
  postop_first_record: '术后首次病程',
  examination_report: '辅助检查',
  consultation_record: '会诊记录',
  consent_form: '知情同意书',
  medical_order: '医嘱',
  case_discussion: '疑难病例讨论',
  transfusion_record: '输血记录',
  anesthesia_record: '麻醉记录',
}

export function getDocTypeZh(value: string): string {
  return CANONICAL_DOC_TYPE_LABELS[value] || value
}

export function getCategoryZh(value: string): string {
  return value
}

export function getSeverityZh(value: string): string {
  return value
}
