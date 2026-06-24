/**
 * LX33 演示页面类型定义
 */

export interface QCRule {
  rule_id?: string
  rule_code?: string
  name: string
  description: string
  category?: string
  defect_level?: string
  score_deduction?: string | number
  deduction_score?: number
  is_veto_defect?: boolean
  complexity?: string
  applicable_documents?: string[]
  is_enabled?: boolean
  version?: string
  updated_at?: string
  source?: string
  positive_example?: {
    title?: string
    content?: string
    explanation?: string
  }
  negative_example?: {
    title?: string
    content?: string
    explanation?: string
  }
}

// 评估结果
export interface EvaluationResult {
  rule_id: string
  rule_code: string
  rule_name: string
  document_name: string
  compliant: boolean
  confidence: number
  evidence: string
  reasoning: string
  suggestion?: string
  execution_time: number
  medical_text?: string // 进行质控的病历原文
}

// 反馈类型
export type FeedbackType = 'correct' | 'incorrect'

// 错误类型
export type ErrorCategory =
  | 'false_positive'
  | 'false_negative'
  | 'wrong_reasoning'
  | 'incomplete_check'
  | 'rule_ambiguity'
  | 'other'

// 反馈请求
export interface FeedbackRequest {
  evaluation_id?: string
  rule_id: string
  rule_code: string
  rule_name: string
  document_name: string
  evaluation_result: boolean
  feedback_type: FeedbackType
  error_category?: ErrorCategory
  error_detail?: string
  evidence?: string
  feedback_by?: string
  medical_text?: string // 进行质控的病历原文
}

// 反馈记录
export interface FeedbackRecord extends FeedbackRequest {
  feedback_id: string
  created_at: string
}

// 反馈统计
export interface FeedbackStats {
  total_feedbacks: number
  correct_feedbacks: number
  incorrect_feedbacks: number
  accuracy_rate: number
  best_rule?: string
  worst_rule?: string
  by_rule?: RuleFeedbackStat[]
  error_categories?: Record<ErrorCategory, number>
}

// 规则反馈统计
export interface RuleFeedbackStat {
  rule_code: string
  rule_name: string
  total: number
  correct: number
  incorrect: number
  accuracy: number
}
