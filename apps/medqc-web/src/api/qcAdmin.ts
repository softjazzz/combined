/**
 * 病案质控管理员端 — 聚合 API 服务
 *
 * 本文件不重复造轮子，复用 defects.ts / tasks.ts / dashboard.ts 中已有的接口，
 * 仅新增管理员端特有的聚合查询和批量操作。
 *
 * @see PRD-病案质控管理员端.md — 补充 C（数据模型映射）
 */

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

function getHeaders(): Record<string, string> {
    const token = localStorage.getItem('medqc_access_token')
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }
    if (token) {
        headers['Authorization'] = `Bearer ${token}`
    }
    return headers
}

async function request<T = any>(url: string, options: RequestInit = {}): Promise<{ success: boolean; data?: T; message?: string }> {
    try {
        const response = await fetch(url, {
            headers: getHeaders(),
            ...options,
        })
        const result = await response.json().catch(() => ({}))

        if (!response.ok) {
            return {
                success: false,
                message: result?.detail || result?.error || result?.message || response.statusText,
            }
        }

        return {
            success: result?.success !== false,
            data: result?.data || result,
            message: result?.message,
        }
    } catch (error: any) {
        return {
            success: false,
            message: error?.message || '网络异常或服务器不可用',
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
    patient_name?: string
    department?: string
    discharge_date?: string
    assignee_id?: string
    assignee_name?: string
    status: BackendDefectStatus | string
    score?: number
    defect_count: number
    severity_summary?: Record<string, number>  // { error: 2, warning: 5 }
    risk_level?: 'high' | 'medium' | 'low'
    completed_at?: string
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

/** 获取管理员端运行病历列表（聚合 task_records + 缺陷统计） */
export async function getAdminRecordList(params?: {
    task_id?: string
    department?: string
    status?: string
    keyword?: string
    start_date?: string
    end_date?: string
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
    // 管理员端暂复用 tasks 列表接口，后续可新增聚合接口
    const url = `${TASKS_URL}${queryParams.toString() ? '?' + queryParams.toString() : ''}`
    return request<{ items: AdminRecordItem[]; total: number; page: number; page_size: number }>(url)
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
    return request<AdminOverviewStats>(url)
}

/**
 * 确认缺陷（管理员标记问题存在）
 * 注意：后端当前无独立 confirm 路由，暂映射为催办（urged）
 * TODO: 后续后端新增 confirm 状态后切换
 */
export async function confirmDefect(defectId: string, data?: ConfirmDefectData) {
    return request(`${DEFECTS_URL}/${defectId}/urge`, {
        method: 'POST',
        body: JSON.stringify({ message: data?.comment || '管理员确认问题', ...data }),
    })
}

/** 标记误报（后端当前无 false-alarm 路由，暂映射为 approve + 备注） */
export async function markFalseAlarm(defectId: string, reason?: string) {
    // 后端无 false-alarm 路由，暂用 approve + comment 标记
    return request(`${DEFECTS_URL}/${defectId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ comment: `[误报] ${reason || '管理员标记为误报'}` }),
    })
}

/** 派发整改任务 */
export async function assignRemediation(defectId: string, data: AssignRemediationData) {
    return request(`${REMEDIATION_URL}`, {
        method: 'POST',
        body: JSON.stringify({
            defect_id: defectId,
            ...data,
        }),
    })
}

/** 批量创建质控任务（批量质控入口） */
export async function batchCreateQCTask(data: {
    task_name: string
    department_filter?: string[]
    date_range?: { start: string; end: string }
    record_ids?: string[]
}) {
    return request(`${TASKS_URL}`, {
        method: 'POST',
        body: JSON.stringify({
            task_type: 'one_time',
            sampling_method: 'all',
            ...data,
        }),
    })
}

/**
 * 获取科室列表（筛选下拉）
 * 后端无独立 /departments 接口，从 dashboard/overview 的 department_stats 键提取
 */
export async function getDepartmentList() {
    const res = await request<any>(`${DASHBOARD_URL}/overview`)
    if (res.success && res.data?.department_stats) {
        const depts = Object.keys(res.data.department_stats).map(name => ({ code: name, name }))
        return { success: true, data: depts }
    }
    // 兜底：返回空列表
    return { success: true, data: [] as Array<{ code: string; name: string }> }
}

// ============= P0: 批量质控任务管理 =============

/** 任务创建请求体（对齐后端 TaskCreateRequest） */
export interface CreateTaskParams {
    task_name: string
    task_type?: 'one_time' | 'scheduled'
    date_range?: { start: string; end: string }
    department_filter?: string[]
    record_ids?: string[]
    sampling_method?: 'all' | 'count' | 'percentage'
    sampling_config?: Record<string, any>
    deadline?: string
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
export async function createQCTaskAndSample(params: CreateTaskParams) {
    // Step 1: 创建任务
    const createRes = await request<any>(`${TASKS_URL}`, {
        method: 'POST',
        body: JSON.stringify({
            task_type: params.task_type || 'one_time',
            sampling_method: params.sampling_method || 'all',
            assign_method: 'keep',
            ...params,
        }),
    })
    if (!createRes.success || !createRes.data?.id) {
        return createRes
    }

    const taskId = createRes.data.id

    // Step 2: 自动执行抽样
    const sampleRes = await request<any>(`${TASKS_URL}/${taskId}/sample`, {
        method: 'POST',
    })

    return {
        success: true,
        data: {
            task_id: taskId,
            task_number: createRes.data.task_number,
            sampled_count: sampleRes.data?.sampled_count || 0,
        },
        message: sampleRes.message || createRes.message,
    }
}

/** 获取任务执行进度（用于轮询） */
export async function fetchTaskProgress(taskId: string) {
    return request<TaskProgressData>(`${TASKS_URL}/${taskId}/progress`)
}

/** 重新质控任务 */
export async function reAnalyzeQCTask(taskId: string) {
    return request<any>(`${TASKS_URL}/${taskId}/re-analyze`, {
        method: 'POST',
    })
}

/** 获取单病历详情（文书内容，用于联审 Drawer） */
export async function getRecordDetail(recordId: string) {
    // 从 medical_records 或后端聚合接口获取病历文书
    return request<any>(`/api/v1/records/${recordId}`)
}
