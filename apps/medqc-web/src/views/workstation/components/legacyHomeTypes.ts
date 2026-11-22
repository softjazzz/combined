import type { QueueStatusCode, QueueStatusSource } from '@/types/workflow'

/** 旧版热点、待办及团队摘要面板使用的类型。 */
export interface HomeKpis {
  hotspot_total: number
  high_risk_total: number
  my_pending_total: number
  my_in_progress_total: number
  my_overdue_total: number
  batch_summary_total: number
}

export interface WorkstationHomeDepartmentRiskItem {
  department: string
  count: number
}

export interface WorkstationHomeWorkflowStatusItem {
  workflow_type: string
  pending?: number
  in_progress?: number
  overdue?: number
  running?: number
  failed?: number
  succeeded?: number
}

export interface WorkstationHomeHotspotItem {
  id: string
  record_id: string
  visit_id: string
  patient_id?: string
  patient_name?: string
  patient_age?: number | string | null
  patient_sex?: string | null
  patient_gender?: string | null
  department: string
  workflow_type: 'frontpage' | 'coding' | 'settlement' | string
  severity: string
  title: string
  summary: string
  occurrence_count: number
  unread_count: number
  active_defect_count: number
  latest_qc_score?: number | null
  latest_qc_grade?: string | null
  queue_status?: QueueStatusCode
  queue_status_source?: QueueStatusSource
  latest_created_at?: string
  latest_notification_id?: string
  launch_action?: string
  launch_stage?: string
}

export interface WorkstationHomeTodoItem {
  id: string
  todo_type: string
  record_id: string
  visit_id: string
  patient_id?: string
  patient_name?: string
  patient_age?: number | string | null
  patient_sex?: string | null
  patient_gender?: string | null
  department: string
  workflow_type: 'frontpage' | 'coding' | 'settlement' | string
  task_status: 'pending' | 'in_progress' | 'overdue' | string
  priority: 'critical' | 'high' | 'medium' | 'normal' | string
  due_at?: string | null
  active_defect_count: number
  summary: string
  queue_status?: QueueStatusCode
  queue_status_source?: QueueStatusSource
  latest_qc_score?: number | null
  latest_qc_grade?: string | null
  launch_action?: string
  launch_stage?: string
}

export interface WorkstationHomeBatchSummary {
  id: string
  title: string
  content: string
  created_at?: string
  is_read?: boolean
  type?: string
  workflow_type?: string
}

/** 首页统一任务列表的前端聚合视图模型 */
export interface UnifiedTaskItem {
  id: string
  /** 来源类型：问题集中点 / 个人待办 */
  source_type: 'hotspot' | 'todo'
  record_id: string
  visit_id: string
  patient_name?: string
  patient_age?: number | string | null
  patient_sex?: string | null
  patient_gender?: string | null
  department: string
  workflow_type: string
  severity: string
  priority: string
  summary: string
  title?: string
  active_defect_count: number
  unread_count: number
  task_status?: string
  queue_status?: string
  latest_qc_score?: number | null
  latest_qc_grade?: string | null
  latest_created_at?: string
  due_at?: string | null
  launch_action?: string
  launch_stage?: string
}
