/** 全病历质控首页的权威聚合范围。三坐标只在下钻时使用，首页不以单一 visit_id 识别病历。 */
export interface ClinicalQcHomeScope {
  hospital_scope: 'all' | string
  department: string | null
  scene: string
  rule_set_key: string
  rule_set_version: string
  generated_at: string
}

export interface ClinicalQcHomePriorityItem {
  record_key: string
  institute_id: string
  patient_id: string
  visit_id: string
  patient_name?: string
  department: string
  priority_kind: 'non_compliant' | 'data_gap' | 'uncertain' | string
  status_counts: Record<string, number>
  completed_at?: string | null
}

export interface ClinicalQcHomeDepartmentItem {
  department: string
  records_total: number
  completed_record_total: number
  high_risk_review_total: number
  data_gap_record_total: number
  uncertain_record_total: number
  defect_total: number
  average_defect_count: number
}

export interface ClinicalQcHomePhysicianItem {
  physician: string
  records_total: number
  completed_record_total: number
  high_risk_review_total: number
  data_gap_record_total: number
  uncertain_record_total: number
  defect_total: number
  average_defect_count: number
}

export interface ClinicalQcHomeProjection {
  scope: ClinicalQcHomeScope
  kpis: {
    records_total: number
    qc_pending_total: number
    qc_completed_total: number
    qc_partial_failed_total?: number
    qc_failed_total?: number
    high_risk_review_total: number
  }
  data_health: {
    source_sync_status: 'unknown' | string
    source_error_total: number
    technical_error_total: number
    running_task_total: number | null
    running_task_state: 'unknown' | string
    last_successful_qc_at: string | null
  }
  canonical_status_counts: Record<string, number>
  priority_items: ClinicalQcHomePriorityItem[]
  department_distribution: ClinicalQcHomeDepartmentItem[]
  physician_distribution: ClinicalQcHomePhysicianItem[]
  rule_family_distribution: unknown[]
  trend: unknown | null
  comparison: unknown | null
}

/** GET /api/v1/workstation/qc-home 返回的全病历质控首页数据。 */
export interface ClinicalQcHomePayload {
  department_options: string[]
  scope: ClinicalQcHomeScope
  clinical_qc: ClinicalQcHomeProjection
}
