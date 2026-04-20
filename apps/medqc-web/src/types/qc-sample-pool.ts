export type SamplePoolScene = 'running' | 'final' | string

export type SampleCoverageType = 'llm_intrinsic' | 'programmatic' | 'unsupported' | string

export type SampleMatchStatus = 'matched' | 'ambiguous' | 'unmatched' | string

export interface SamplePool {
  id: string
  name: string
  source_file: string
  source_sheet: string
  scene: SamplePoolScene
  description: string
  created_by: string
  created_at?: string
  updated_at?: string
  total_items: number
  llm_intrinsic_items: number
  programmatic_items: number
  unsupported_items: number
  matched_items: number
  ambiguous_items: number
  unmatched_items: number
  ready_items: number
  latest_job_id: string
  latest_job_status: string
}

export interface SamplePoolItem {
  id: string
  pool_id: string
  row_no: number
  department: string
  patient_name: string
  mr_no: string
  manual_issue_text: string
  normalized_issue_text: string
  doctor_name: string
  qc_date: string
  qc_user: string
  coverage_type: SampleCoverageType
  issue_category: string
  expected_scene: SamplePoolScene
  candidate_rule_ids: string[]
  include_in_batch_1: boolean
  exclude_reason: string
  matched_institute_id: string
  matched_patient_id: string
  matched_visit_id: string
  match_status: SampleMatchStatus
  sync_status: string
  bundle_status: string
  latest_job_id: string
  latest_match_status: string
  raw_payload: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface SamplePoolListResponse {
  items: SamplePool[]
  total: number
  page: number
  page_size: number
}

export interface SamplePoolItemsResponse {
  pool: SamplePool
  items: SamplePoolItem[]
  total: number
  page: number
  page_size: number
}
