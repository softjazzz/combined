import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

export type TaskAnalysisStatus = 'pending' | 'in_progress' | 'completed' | 'skipped' | 'unknown'

export interface TaskAnalysisAssignee {
  assignee_id: string | null
  assignee_name: string | null
  total_records: number
  completed_records: number
  completion_rate: number
}

export interface TaskAnalysis {
  contract_version: 'task-analysis-v1'
  task: {
    id: string
    task_number: string
    task_name: string
    scene: string | null
    status: string
    creator_id: string | null
    creator_name: string | null
  }
  summary: {
    total_records: number
    completed_records: number
    completion_rate: number
    average_score: number | null
    score_known_count: number
    score_unknown_count: number
    total_defect_count: number | null
    defect_known_count: number
    defect_unknown_count: number
  }
  status_counts: Record<TaskAnalysisStatus, number>
  assignees: TaskAnalysisAssignee[]
}

export interface TaskAnalysisResult {
  success: boolean
  data?: TaskAnalysis
  message?: string
  status?: number
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}

function isRate(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100
}

function isNullableText(value: unknown): value is string | null {
  return value === null || (typeof value === 'string' && !!value.trim())
}

function parseTaskAnalysis(value: unknown, expectedTaskId: string): TaskAnalysis {
  if (!value || typeof value !== 'object') throw new Error('任务分析响应格式无效')
  const data = value as Record<string, unknown>
  const task = data.task as Record<string, unknown> | undefined
  const summary = data.summary as Record<string, unknown> | undefined
  const statuses = data.status_counts as Record<string, unknown> | undefined
  const assignees = data.assignees
  if (
    data.contract_version !== 'task-analysis-v1'
    || !task || task.id !== expectedTaskId
    || typeof task.task_number !== 'string' || !task.task_number.trim()
    || typeof task.task_name !== 'string' || !task.task_name.trim()
    || !isNullableText(task.scene) || typeof task.status !== 'string' || !task.status.trim()
    || !isNullableText(task.creator_id) || !isNullableText(task.creator_name)
    || !summary || !Array.isArray(assignees) || !statuses
  ) throw new Error('任务分析响应格式无效')

  const countKeys = [
    'total_records', 'completed_records', 'score_known_count', 'score_unknown_count',
    'defect_known_count', 'defect_unknown_count',
  ] as const
  if (countKeys.some((key) => !isCount(summary[key])) || !isRate(summary.completion_rate))
    throw new Error('任务分析响应格式无效')
  if (summary.average_score !== null && (typeof summary.average_score !== 'number' || !Number.isFinite(summary.average_score)))
    throw new Error('任务分析响应格式无效')
  if (summary.total_defect_count !== null && !isCount(summary.total_defect_count))
    throw new Error('任务分析响应格式无效')

  const total = summary.total_records as number
  const completed = summary.completed_records as number
  if (
    completed > total
    || (summary.score_known_count as number) + (summary.score_unknown_count as number) !== total
    || (summary.defect_known_count as number) + (summary.defect_unknown_count as number) !== total
    || ((summary.score_unknown_count as number) > 0 || total === 0) !== (summary.average_score === null)
    || ((summary.defect_unknown_count as number) > 0 || total === 0) !== (summary.total_defect_count === null)
  ) throw new Error('任务分析响应计数不一致')

  const statusKeys: TaskAnalysisStatus[] = ['pending', 'in_progress', 'completed', 'skipped', 'unknown']
  if (statusKeys.some((key) => !isCount(statuses[key]))) throw new Error('任务分析响应格式无效')
  if (statusKeys.reduce((sum, key) => sum + (statuses[key] as number), 0) !== total)
    throw new Error('任务分析响应计数不一致')
  if (statuses.completed !== completed) throw new Error('任务分析响应计数不一致')

  let assigneeTotal = 0
  let assigneeCompleted = 0
  const assigneeIds = new Set<string | null>()
  for (const raw of assignees) {
    if (!raw || typeof raw !== 'object') throw new Error('任务分析响应格式无效')
    const row = raw as Record<string, unknown>
    if (
      !isNullableText(row.assignee_id) || !isNullableText(row.assignee_name)
      || !isCount(row.total_records) || !isCount(row.completed_records)
      || (row.completed_records as number) > (row.total_records as number)
      || !isRate(row.completion_rate)
    ) throw new Error('任务分析响应格式无效')
    const assigneeKey = row.assignee_id as string | null
    if (assigneeIds.has(assigneeKey)) throw new Error('任务分析响应受领人重复')
    assigneeIds.add(assigneeKey)
    assigneeTotal += row.total_records as number
    assigneeCompleted += row.completed_records as number
  }
  if (assigneeTotal !== total || assigneeCompleted !== completed)
    throw new Error('任务分析响应计数不一致')
  return value as TaskAnalysis
}

export async function getTaskAnalysis(taskId: string): Promise<TaskAnalysisResult> {
  try {
    const response = await ApiService.requestRaw<TaskAnalysis>({
      method: 'GET',
      url: `/api/v1/quality-reports/tasks/${encodeURIComponent(taskId)}`,
    })
    const normalized = normalizeApiSuccess<TaskAnalysis>(response.data)
    if (!normalized.success || !normalized.data) {
      return { success: false, status: response.status, message: normalized.message || '任务分析暂不可用' }
    }
    return {
      success: true,
      status: response.status,
      data: parseTaskAnalysis(normalized.data, taskId),
    }
  } catch (error) {
    return {
      success: false,
      status: isAxiosError(error) ? error.response?.status : undefined,
      message: error instanceof Error && !isAxiosError(error)
        ? error.message
        : extractApiErrorMessageFromError(error, '任务分析暂不可用'),
    }
  }
}
