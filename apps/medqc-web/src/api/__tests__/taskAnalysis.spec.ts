import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { getTaskAnalysis } from '@/api/taskAnalysis'

function response(data: unknown) {
  return { status: 200, data: { success: true, data } } as Awaited<ReturnType<typeof ApiService.requestRaw>>
}

function error(status: number, data: unknown) {
  const axiosResponse = {
    status,
    data,
    statusText: '',
    headers: {},
    config: { headers: new AxiosHeaders() },
  } as AxiosResponse
  return new AxiosError('failed', String(status), undefined, undefined, axiosResponse)
}

function validAnalysis(overrides: Record<string, unknown> = {}) {
  return {
    contract_version: 'task-analysis-v1',
    task: {
      id: 'task/1', task_number: 'NO-1', task_name: '任务一', scene: 'running',
      status: 'in_progress', creator_id: 'creator', creator_name: '创建人',
    },
    summary: {
      total_records: 2, completed_records: 1, completion_rate: 50,
      average_score: null, score_known_count: 1, score_unknown_count: 1,
      total_defect_count: null, defect_known_count: 1, defect_unknown_count: 1,
    },
    status_counts: { pending: 1, in_progress: 0, completed: 1, skipped: 0, unknown: 0 },
    assignees: [
      { assignee_id: 'staff-1', assignee_name: '甲', total_records: 2, completed_records: 1, completion_rate: 50 },
    ],
    ...overrides,
  }
}

describe('task analysis API', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('requests the task-scoped endpoint and validates the response', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response(validAnalysis()))
    const result = await getTaskAnalysis('task/1')
    expect(result.success).toBe(true)
    expect(result.data?.summary.score_unknown_count).toBe(1)
    expect(request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/quality-reports/tasks/task%2F1',
    })
  })

  it.each([
    validAnalysis({ summary: { ...validAnalysis().summary, average_score: 90 } }),
    validAnalysis({ status_counts: { pending: 0, in_progress: 0, completed: 1, skipped: 0, unknown: 0 } }),
    validAnalysis({ assignees: [
      { assignee_id: 'staff-1', assignee_name: '甲', total_records: 1, completed_records: 1, completion_rate: 100 },
      { assignee_id: 'staff-1', assignee_name: '乙', total_records: 1, completed_records: 0, completion_rate: 0 },
    ] }),
  ])('fails closed on inconsistent or ambiguous counts', async (payload) => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response(payload))
    const result = await getTaskAnalysis('task/1')
    expect(result).toMatchObject({ success: false, status: undefined })
    expect(result.message).toContain('任务分析响应')
  })

  it('区分未分配和同名特殊字符串账号', async () => {
    const payload = validAnalysis({ assignees: [
      { assignee_id: null, assignee_name: null, total_records: 1, completed_records: 0, completion_rate: 0 },
      { assignee_id: '__unassigned__', assignee_name: '质控员', total_records: 1, completed_records: 1, completion_rate: 100 },
    ] })
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response(payload))
    expect((await getTaskAnalysis('task/1')).success).toBe(true)
  })

  it('preserves a sanitized server error message', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockRejectedValue(
      error(403, { detail: '仅任务创建人或管理员可查看整任务分析' }),
    )
    expect(await getTaskAnalysis('task/1')).toMatchObject({
      success: false,
      status: 403,
      message: '仅任务创建人或管理员可查看整任务分析',
    })
  })
})
