/**
 * 病案质控管理员端 — 聚合 API 服务
 *
 * 本文件不重复造轮子，复用 defects.ts / tasks.ts / dashboard.ts 中已有的接口，
 * 仅新增管理员端特有的聚合查询和批量操作。
 *
 * @see PRD-病案质控管理员端.md — 补充 C（数据模型映射）
 */

import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import type { TaskItem, TaskScene } from './tasks'

// ============= 复用已有 API =============
// 直接从各模块 re-export，方便管理员页面统一导入

export {
  getDefectList,
  getDefectStats,
  urgeDefect,
  approveDefect,
  rejectDefect,
  batchDefectAction,
  exportDefects,
  markDefectRemediated,
  type DefectItem,
  type DefectListResponse,
  type DefectStats,
} from './defects'

export {
  getTaskList,
  getTaskStats,
  getTaskDetail,
  createTask,
  getTaskProgress,
  reAnalyzeTask,
  type TaskItem,
  type TaskListResponse,
  type TaskCreateData,
  type TaskProgress,
  type TaskStats,
} from './tasks'

export {
  getTodoStats,
  getDashboardOverview,
  type TodoStats,
  type DashboardOverview,
} from './dashboard'

// ============= 通用请求封装 =============

// 后端实际路由前缀（来源：各 router APIRouter prefix）
// defects:     /api/v1/qc/defects  (defects.py:41)
// tasks:       /api/v1/tasks       (tasks.py:42)
// dashboard:   /api/v1/dashboard   (dashboard_api.py:23)
// remediation: /api/v1/remediation (remediation.py:41)
const DEFECTS_URL = '/api/v1/qc/defects'
const TASKS_URL = '/api/v1/tasks'
const DASHBOARD_URL = '/api/v1/dashboard'
const REMEDIATION_URL = '/api/v1/remediation'
const RECORDS_URL = '/api/v1/records'

async function request<T = any>(
  config: Parameters<typeof ApiService.requestRaw>[0],
): Promise<{ success: boolean; data?: T; message?: string }> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    const normalized = normalizeApiSuccess<T>(response.data)
    return {
      success: normalized.success,
      data: normalized.data,
      message: normalized.message,
    }
  } catch (error) {
    return {
      success: false,
      message: extractApiErrorMessageFromError(error, '网络异常或服务器不可用'),
    }
  }
}

// ============= 管理员端新增类型 =============

/**
 * 后端缺陷状态枚举（来源：schemas/defects.py DefectStatus）
 * pending     → 待处理
 * urged       → 已催办
 * remediated  → 已整改
 * approved    → 审核通过
 * rejected    → 审核存疑（退回）
 */
export type BackendDefectStatus = 'pending' | 'urged' | 'remediated' | 'approved' | 'rejected'

/** 运行病历列表项（对应 qc_task_records 视图） */
export interface AdminRecordItem {
  id: string
  task_id: string
  record_id: string
  visit_type?: string
  patient_name?: string
  department?: string
  discharge_date?: string
  assignee_id?: string
  assignee_name?: string
  status: BackendDefectStatus | string
  score?: number
  defect_count: number
  severity_summary?: Record<string, number> // { error: 2, warning: 5 }
  risk_level?: 'high' | 'medium' | 'low'
  completed_at?: string
  created_at: string
}

/** 终末病历列表查询参数 */
export interface FinalRecordListQuery {
  keyword?: string
  department?: string
  status?: 'unverified'
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}

/** 旧终末列表过渡项：三坐标可信，旧单键质控归属和结果尚未核实。 */
export interface FinalRecordItem {
  id: string
  task_id: string
  record_id: string
  institute_id: string
  patient_id: string
  visit_id: string
  visit_type: string
  patient_name: string
  department: string
  discharge_date: string | null
  identity_status: 'unverified'
  status: 'unverified'
  score: null
  defect_count: null
  created_at: string
}

/** 管理员统计概览（KPI 卡片） */
export interface AdminOverviewStats {
  total_records: number
  archived_count: number
  pending_count: number
  pass_rate: number
  total_defects: number
  defects_by_severity: Record<string, number>
}

/** 确认缺陷请求 */
export interface ConfirmDefectData {
  comment?: string
}

/** 派发整改请求 */
export interface AssignRemediationData {
  assignee_id: string
  assignee_name: string
  assignee_department?: string
  remediation_requirement: string
  deadline?: string
}

// ============= 管理员端新增 API =============

/** 旧管理员入口的病历列表；运行/终末试跑尚无可信单病历资料链。 */
export async function getAdminRecordList(params?: {
  scene?: 'running' | 'final' | 'outpatient_emergency'
  task_id?: string
  department?: string
  status?: string
  keyword?: string
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}) {
  if (params?.scene !== 'outpatient_emergency') {
    return {
      success: false,
      data: undefined,
      message: '此旧试跑入口无法确认运行/终末病历的单病历资料链，请前往病历质控列表查看',
    }
  }
  const queryParams = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, String(value))
      }
    })
  }
  const url = `${RECORDS_URL}/outpatient-emergency${queryParams.toString() ? '?' + queryParams.toString() : ''}`
  return request<{ items: AdminRecordItem[]; total: number; page: number; page_size: number }>({
    method: 'GET',
    url,
  })
}

/** 获取终末病历分页列表（专用于终末病历页） */
export async function getFinalRecordList(params?: FinalRecordListQuery) {
  const queryParams = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, String(value))
      }
    })
  }
  const url = `${RECORDS_URL}/final${queryParams.toString() ? '?' + queryParams.toString() : ''}`
  return request<{ items: FinalRecordItem[]; total: number; page: number; page_size: number }>({
    method: 'GET',
    url,
  })
}

/** 获取门急诊病历分页列表（主链路接口） */
export async function getOutpatientEmergencyRecordList(params?: {
  keyword?: string
  department?: string
  status?: string
  start_date?: string
  end_date?: string
  scoring_standard?: string
  page?: number
  page_size?: number
}) {
  const queryParams = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, String(value))
      }
    })
  }
  const url = `${RECORDS_URL}/outpatient-emergency${queryParams.toString() ? '?' + queryParams.toString() : ''}`
  return request<{ items: AdminRecordItem[]; total: number; page: number; page_size: number }>({
    method: 'GET',
    url,
  })
}

/** 获取管理员端统计概览 */
export async function getAdminOverview(params?: {
  department?: string
  start_date?: string
  end_date?: string
}) {
  const queryParams = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, String(value))
      }
    })
  }
  // 复用 dashboard/overview 接口
  const url = `${DASHBOARD_URL}/overview${queryParams.toString() ? '?' + queryParams.toString() : ''}`
  return request<AdminOverviewStats>({ method: 'GET', url })
}

/**
 * 确认缺陷（管理员标记问题存在）
 * 注意：后端当前无独立 confirm 路由，暂映射为催办（urged）
 * TODO: 后续后端新增 confirm 状态后切换
 */
export async function confirmDefect(defectId: string, data?: ConfirmDefectData) {
  return request({
    method: 'POST',
    url: `${DEFECTS_URL}/${defectId}/urge`,
    data: { message: data?.comment || '管理员确认问题', ...data },
  })
}

/** 标记误报（后端当前无 false-alarm 路由，暂映射为 approve + 备注） */
export async function markFalseAlarm(defectId: string, reason?: string) {
  // 后端无 false-alarm 路由，暂用 approve + comment 标记
  return request({
    method: 'POST',
    url: `${DEFECTS_URL}/${defectId}/approve`,
    data: { comment: `[误报] ${reason || '管理员标记为误报'}` },
  })
}

/** 派发整改任务 */
export async function assignRemediation(defectId: string, data: AssignRemediationData) {
  return request({
    method: 'POST',
    url: `${REMEDIATION_URL}`,
    data: {
      defect_id: defectId,
      ...data,
    },
  })
}

/** 批量创建质控任务（批量质控入口） */
export async function batchCreateQCTask(data: {
  task_name: string
  department_filter?: string[]
  date_range?: { start: string; end: string }
  record_ids?: string[]
}) {
  return request({
    method: 'POST',
    url: `${TASKS_URL}`,
    data: {
      task_type: 'one_time',
      sampling_method: 'all',
      ...data,
    },
  })
}

/**
 * 获取科室列表（筛选下拉）
 * 后端无独立 /departments 接口，从 dashboard/overview 的 department_stats 键提取
 */
export async function getDepartmentList() {
  const res = await request<any>({ method: 'GET', url: `${DASHBOARD_URL}/overview` })
  if (res.success && res.data?.department_stats) {
    const depts = Object.keys(res.data.department_stats).map((name) => ({ code: name, name }))
    return { success: true, data: depts }
  }
  // 兜底：返回空列表
  return { success: true, data: [] as Array<{ code: string; name: string }> }
}

// ============= P0: 批量质控任务管理 =============

/** 任务创建请求体（对齐后端 TaskCreateRequest） */
export interface CreateTaskParams {
  task_name: string
  scene: TaskScene
  rule_set_key: string
  task_type?: 'one_time' | 'scheduled'
  date_range?: { start: string; end: string }
  department_filter?: string[]
  record_ids?: string[]
  sampling_method?: 'all' | 'count' | 'percentage'
  sampling_config?: Record<string, any>
  deadline?: string
}

export interface CreateTaskAndSampleData {
  task_id: string
  task_number: string
  sampled: boolean
  sampled_count: number
}

type CreatedTaskResponse = Pick<TaskItem, 'id' | 'task_number'>

interface SampleTaskResponse {
  sampled_count: number
}

/** 任务进度响应 */
export interface TaskProgressData {
  task_id: string
  task_name: string
  total_records: number
  completed_records: number
  progress_pct: number
  pending_count: number
  working_count: number
  done_count: number
  avg_score?: number
  total_defects: number
}

/**
 * 创建质控任务 + 自动触发抽样（组合操作）
 * 后端流程：POST /tasks → POST /tasks/{id}/sample
 */
export async function createQCTaskAndSample(
  params: CreateTaskParams,
): Promise<{ success: boolean; data?: CreateTaskAndSampleData; message?: string }> {
  // Step 1: 创建任务
  const createRes = await request<CreatedTaskResponse>({
    method: 'POST',
    url: `${TASKS_URL}`,
    data: {
      task_type: params.task_type || 'one_time',
      sampling_method: params.sampling_method || 'all',
      assign_method: 'by_ratio',
      ...params,
    },
  })
  if (!createRes.success || !createRes.data?.id) {
    return {
      success: false,
      message: createRes.message || '任务创建失败',
    }
  }

  const taskId = createRes.data.id
  const taskNumber = createRes.data.task_number

  // Step 2: 自动执行抽样
  const sampleRes = await request<SampleTaskResponse>({
    method: 'POST',
    url: `${TASKS_URL}/${taskId}/sample`,
  })
  const sampledCount = sampleRes.data?.sampled_count

  // 抽样失败或返回无效计数时保留草稿标识，不误报已完成。
  if (
    !sampleRes.success ||
    typeof sampledCount !== 'number' ||
    !Number.isInteger(sampledCount) ||
    sampledCount < 0
  ) {
    return {
      success: false,
      data: {
        task_id: taskId,
        task_number: taskNumber,
        sampled: false,
        sampled_count: 0,
      },
      message: sampleRes.success
        ? '抽样结果缺少有效数量'
        : sampleRes.message || '抽样执行失败',
    }
  }

  return {
    success: true,
    data: {
      task_id: taskId,
      task_number: taskNumber,
      sampled: true,
      sampled_count: sampledCount,
    },
    message: sampleRes.message || createRes.message,
  }
}

/** 获取任务执行进度（用于轮询） */
export async function fetchTaskProgress(taskId: string) {
  return request<TaskProgressData>({ method: 'GET', url: `${TASKS_URL}/${taskId}/progress` })
}

/** 重新质控任务 */
export async function reAnalyzeQCTask(taskId: string) {
  return request<any>({ method: 'POST', url: `${TASKS_URL}/${taskId}/re-analyze` })
}

/** 仅按旧病历表主键读取文书；调用方必须证明 ID 来自旧病历列表。 */
export async function getRecordDetail(recordId: string, source: 'legacy_medical_records') {
  return request<any>({
    method: 'GET',
    url: `${RECORDS_URL}/${encodeURIComponent(recordId)}/qc-detail`,
    params: { source },
  })
}

// ============= P1: 整改闭环 =============

/** 整改任务项 */
export interface RemediationItem {
  id: string
  qc_result_id: string
  record_id: string
  defect_type: string
  defect_description: string
  severity: string
  status: string // pending/in_progress/submitted/approved/rejected/overdue/closed
  assignee_id?: string
  assignee_name?: string
  assignee_department?: string
  remediation_requirement?: string
  deadline?: string
  submitted_at?: string
  reviewed_at?: string
  closed_at?: string
  created_at: string
}

/** 获取整改任务列表 */
export async function getRemediationList(params?: {
  status?: string
  severity?: string
  assignee_id?: string
  is_overdue?: boolean
  page?: number
  page_size?: number
}) {
  const queryParams = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, String(value))
      }
    })
  }
  const url = `${REMEDIATION_URL}${queryParams.toString() ? '?' + queryParams.toString() : ''}`
  return request<{ items: RemediationItem[]; total: number }>({ method: 'GET', url })
}

/** 获取整改统计 */
export async function getRemediationStats() {
  return request<any>({ method: 'GET', url: `${REMEDIATION_URL}/statistics/summary` })
}

/** 验收整改（通过/驳回） */
export async function reviewRemediation(
  taskId: string,
  data: { action: 'approve' | 'reject'; review_comment?: string },
) {
  return request({
    method: 'POST',
    url: `${REMEDIATION_URL}/${taskId}/review`,
    data,
  })
}

/** 关闭整改任务 */
export async function closeRemediation(taskId: string, reason?: string) {
  return request({
    method: 'POST',
    url: `${REMEDIATION_URL}/${taskId}/close`,
    data: { reason },
  })
}

// ============= P1: 批量派发整改 =============

/** 批量创建整改任务（从选中的缺陷列表生成） */
export async function batchCreateRemediation(data: {
  defect_ids: string[]
  assignee_id: string
  assignee_name: string
  assignee_department?: string
  remediation_requirement: string
  deadline?: string
}) {
  // 逐条创建整改任务（后端暂无 batch 接口）
  const results: any[] = []
  for (const defectId of data.defect_ids) {
    const res = await request({
      method: 'POST',
      url: `${REMEDIATION_URL}`,
      data: {
        defect_id: defectId,
        assignee_id: data.assignee_id,
        assignee_name: data.assignee_name,
        assignee_department: data.assignee_department,
        remediation_requirement: data.remediation_requirement,
        deadline: data.deadline,
      },
    })
    results.push(res)
  }
  const successCount = results.filter((r) => r.success).length
  return {
    success: successCount > 0,
    data: {
      total: data.defect_ids.length,
      success: successCount,
      failed: data.defect_ids.length - successCount,
    },
    message: `派发完成：${successCount}/${data.defect_ids.length} 成功`,
  }
}

// ============= P1: 导出 =============

/** 导出缺陷报告（触发下载） */
export async function exportDefectsDownload(params?: {
  department?: string
  status?: string
  start_date?: string
  end_date?: string
}) {
  const queryParams = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, String(value))
      }
    })
  }
  const url = `${DEFECTS_URL}/export${queryParams.toString() ? '?' + queryParams.toString() : ''}`

  try {
    const response = await ApiService.getRaw<Blob>(url, undefined, { responseType: 'blob' })
    const blob = response.data
    const downloadUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = downloadUrl
    a.download = `质控缺陷报告_${new Date().toISOString().slice(0, 10)}.xlsx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(downloadUrl)
    return { success: true, message: '导出成功' }
  } catch (error) {
    return { success: false, message: extractApiErrorMessageFromError(error, '导出失败，请重试') }
  }
}
