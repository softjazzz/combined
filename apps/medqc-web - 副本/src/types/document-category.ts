export interface DocumentPositionInfo {
  startIndex?: number
  endIndex?: number
  fullContent?: string
  [key: string]: unknown
}

export interface DocumentItem {
  id: string
  title?: string
  content?: string
  content_preview?: string
  type?: string
  type_info?: {
    type_id?: string
    type_code?: string
    type_name?: string
    type_description?: string
  }
  ai_classified?: boolean
  classification_confidence?: number
  qc_status?: string
  qc_score?: number
  qc_last_analyzed?: string
  qc_issues_count?: number
  qc_results?: unknown
  position_info?: DocumentPositionInfo
  summary?: string
  tags?: string[]
  metadata?: Record<string, unknown>
  [key: string]: unknown
}

export interface DocumentCategoryItem {
  category_code: string
  category_name: string
  category_description?: string
  document_count: number
  documents: DocumentItem[]
}

export interface ClassificationSummaryEntry {
  name?: string
  count?: number
  types?: Record<string, { name: string; count: number }>
  [key: string]: unknown
}

export interface DocumentApiResponse {
  record_id: string
  total_documents: number
  categories: DocumentCategoryItem[]
  classification_summary: Record<string, ClassificationSummaryEntry>
}

export interface DocumentRule {
  rule_id: string
  name: string
  description?: string
  category?: string
  defect_level?: string
  score_deduction?: number
  complexity?: string
}

export interface AnalysisResultPayload {
  qc_status: string
  qc_score: number
  analysis_time?: string
}

export interface DocumentQCResult {
  qc_status?: string
  qc_score?: number
  analysis_time?: string
  failed_rules?: number
  results?: Array<{ compliant?: boolean; message?: string; severity?: string }>
  suggestions?: string[]
  [key: string]: unknown
}
