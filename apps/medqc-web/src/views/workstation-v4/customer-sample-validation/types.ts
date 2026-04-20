export type ManualSamplePool = {
  id: string
  name: string
  source_file: string
  source_sheet: string
  scene: string
  description?: string
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
  latest_job_id?: string
  latest_job_status?: string
}

export type ManualSamplePoolItem = {
  id: string
  pool_id: string
  row_no: number
  department: string
  patient_name: string
  mr_no: string
  manual_issue_text: string
  normalized_issue_text: string
  doctor_name: string
  qc_date?: string
  qc_user: string
  coverage_type: string
  issue_category: string
  expected_scene: string
  candidate_rule_ids: string[]
  include_in_batch_1: boolean
  exclude_reason?: string
  matched_institute_id?: string
  matched_patient_id?: string
  matched_visit_id?: string
  match_status: string
  sync_status: string
  bundle_status: string
  latest_job_id?: string
  latest_match_status?: string
  raw_payload?: Record<string, unknown>
}

export type ManualSamplePoolRecord = {
  id: string
  matched_institute_id?: string
  matched_patient_id?: string
  matched_visit_id?: string
  patient_name: string
  mr_no: string
  department: string
  match_status: string
  sync_status: string
  bundle_status: string
  coverage_types: string[]
  candidate_rule_ids: string[]
  issue_count: number
  issue_preview: string[]
  issue_preview_text: string
  sample_item_ids: string[]
  sample_items: ManualSamplePoolItem[]
}

export type ManualSamplePoolListResult = {
  items: ManualSamplePool[]
  total: number
  page: number
  page_size: number
}

export type ManualSamplePoolItemsResult = {
  pool: ManualSamplePool
  items: ManualSamplePoolItem[]
  total: number
  page: number
  page_size: number
}

export type ManualSamplePoolRecordsResult = {
  pool: ManualSamplePool
  items: ManualSamplePoolRecord[]
  total: number
  page: number
  page_size: number
}
