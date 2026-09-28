import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import {
  getTaskEdit,
  updateTaskDraftConfiguration,
  updateTaskMetadata,
  type TaskEditDetail,
} from '@/api/taskEdits'

function response(data: unknown, success = true) {
  return {
    status: 200,
    data: { success, data, message: success ? 'ok' : 'failed' },
  } as Awaited<ReturnType<typeof ApiService.requestRaw>>
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

const detail: TaskEditDetail = {
  id: 'task/1',
  task_number: 'QC-001',
  task_name: '九月运行质控',
  task_type: 'one_time',
  status: 'draft',
  scene: 'running',
  rule_set_key: 'luxian-0609',
  rule_set_version: 'v1',
  deadline: '2026-10-10',
  date_range: { start: '2026-09-01', end: '2026-09-30' },
  department_filter: ['内科'],
  record_refs: [],
  sampling_method: 'count',
  sampling_config: { case_scope: 'active', total: 20, by_department: true },
  assign_method: 'by_original_reviewer',
  assignee_config: { fallback: 'by_ratio' },
  configuration_version: 3,
  editable_fields: [
    'task_name', 'deadline', 'date_range', 'department_filter', 'record_refs',
    'sampling_method', 'sampling_config', 'assign_method', 'assignee_config',
  ],
  updated_at: '2026-09-27T10:00:00Z',
}

describe('task edits API', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('读取任务编辑详情并严格核对任务 ID 与字段合同', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response(detail))
    const result = await getTaskEdit('task/1')
    expect(result).toMatchObject({ success: true, data: detail })
    expect(request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/task-edits/task%2F1',
    })
  })

  it.each([
    { ...detail, id: 'other' },
    { ...detail, configuration_version: 0 },
    { ...detail, editable_fields: ['scene'] },
    { ...detail, record_refs: [{ institute_id: 'H', patient_id: '', visit_id: 'V' }] },
    { ...detail, sampling_config: [] },
  ])('坏 200 响应失败关闭并标为需刷新', async (payload) => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response(payload))
    const result = await getTaskEdit('task/1')
    expect(result).toMatchObject({ success: false, uncertain: true })
    expect(result.message).toContain('响应格式无效')
  })

  it('接受历史元数据任务的空冻结字段、空配置与旧分配方式', async () => {
    const legacy = {
      ...detail,
      scene: null,
      rule_set_key: null,
      rule_set_version: null,
      updated_at: null,
      date_range: null,
      department_filter: null,
      record_refs: null,
      sampling_method: null,
      sampling_config: null,
      assign_method: 'by_type',
      assignee_config: null,
      editable_fields: ['task_name', 'deadline'],
    }
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response(legacy))
    const result = await getTaskEdit('task/1')
    expect(result).toMatchObject({ success: true, data: legacy })
  })

  it('PUT 只发送版本与十个规划字段，不携带冻结或遗留字段', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(
      response({ ...detail, configuration_version: 4 }),
    )
    const payload = {
      configuration_version: 3,
      task_name: '新名称',
      deadline: null,
      date_range: null,
      department_filter: [],
      record_refs: [{ institute_id: 'H', patient_id: 'P', visit_id: 'V' }],
      sampling_method: 'all' as const,
      sampling_config: { case_scope: 'active' },
      assign_method: 'by_ratio' as const,
      assignee_config: {},
    }
    const result = await updateTaskDraftConfiguration('task/1', payload)
    expect(result.success).toBe(true)
    expect(request).toHaveBeenCalledWith({
      method: 'PUT',
      url: '/api/v1/task-edits/task%2F1/draft-configuration',
      data: payload,
    })
    const sent = request.mock.calls[0][0].data as Record<string, unknown>
    expect(sent).not.toHaveProperty('scene')
    expect(sent).not.toHaveProperty('rule_set_key')
    expect(sent).not.toHaveProperty('rule_set_version')
    expect(sent).not.toHaveProperty('record_ids')
    expect(sent).not.toHaveProperty('description')
  })

  it('PATCH 支持显式清除 deadline 且至少更新一个元数据字段', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(
      response({ ...detail, deadline: null, configuration_version: 4 }),
    )
    await updateTaskMetadata('task/1', { configuration_version: 3, deadline: null })
    expect(request).toHaveBeenCalledWith({
      method: 'PATCH',
      url: '/api/v1/task-edits/task%2F1/metadata',
      data: { configuration_version: 3, deadline: null },
    })

    const invalid = await updateTaskMetadata('task/1', { configuration_version: 3 })
    expect(invalid).toMatchObject({ success: false, uncertain: false })
    expect(request).toHaveBeenCalledTimes(1)
  })

  it('保留结构化业务错误；网络与 5xx 标为结果未知', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw')
    request.mockRejectedValueOnce(error(409, {
      detail: { code: 'version_conflict', message: '配置版本已变化' },
    }))
    expect(await updateTaskMetadata('task/1', {
      configuration_version: 3, task_name: '新名称',
    })).toMatchObject({
      success: false, status: 409, code: 'version_conflict', uncertain: false,
      message: '配置版本已变化',
    })

    request.mockRejectedValueOnce(error(503, { detail: '服务暂不可用' }))
    expect(await getTaskEdit('task/1')).toMatchObject({ success: false, status: 503, uncertain: true })

    request.mockRejectedValueOnce(new Error('network'))
    expect(await getTaskEdit('task/1')).toMatchObject({ success: false, uncertain: true })
  })
})
