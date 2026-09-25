import { AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { createQCTaskAndSample } from '@/api/qcAdmin'

vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: vi.fn() } }))

function response<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  }
}

const params = {
  task_name: '运行病历任务',
  scene: 'running' as const,
  rule_set_key: 'running-v1',
  sampling_method: 'count' as const,
  sampling_config: { total: 12 },
}

describe('createQCTaskAndSample 两阶段合同', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('创建和抽样均成功时返回 sampled=true，并在创建请求中保留场景', async () => {
    vi.mocked(ApiService.requestRaw)
      .mockResolvedValueOnce(
        response({ success: true, data: { id: 'task-1', task_number: 'QC-001' } }),
      )
      .mockResolvedValueOnce(
        response({ success: true, data: { sampled_count: 12 }, message: '抽样完成' }),
      )

    await expect(createQCTaskAndSample(params)).resolves.toEqual({
      success: true,
      data: {
        task_id: 'task-1',
        task_number: 'QC-001',
        sampled: true,
        sampled_count: 12,
      },
      message: '抽样完成',
    })
    expect(ApiService.requestRaw).toHaveBeenNthCalledWith(1, {
      method: 'POST',
      url: '/api/v1/tasks',
      data: expect.objectContaining({ scene: 'running', rule_set_key: 'running-v1', sampling_config: { total: 12 }, assign_method: 'by_ratio' }),
    })
    expect(ApiService.requestRaw).toHaveBeenNthCalledWith(2, {
      method: 'POST',
      url: '/api/v1/tasks/task-1/sample',
    })
  })

  it('草稿已创建但抽样失败时保留任务标识并返回 sampled=false', async () => {
    vi.mocked(ApiService.requestRaw)
      .mockResolvedValueOnce(
        response({ success: true, data: { id: 'task-2', task_number: 'QC-002' } }),
      )
      .mockResolvedValueOnce(response({ success: false, message: '场景候选尚未接通' }))

    await expect(createQCTaskAndSample(params)).resolves.toEqual({
      success: false,
      data: {
        task_id: 'task-2',
        task_number: 'QC-002',
        sampled: false,
        sampled_count: 0,
      },
      message: '场景候选尚未接通',
    })
  })

  it.each([
    ['缺少抽样数据', { success: true, message: '抽样成功' }],
    ['抽样数量为负数', { success: true, data: { sampled_count: -1 } }],
    ['抽样数量不是整数', { success: true, data: { sampled_count: 1.5 } }],
  ])('%s 时不能把零条病历伪报为抽样完成', async (_case, sampleResponse) => {
    vi.mocked(ApiService.requestRaw)
      .mockResolvedValueOnce(
        response({ success: true, data: { id: 'task-3', task_number: 'QC-003' } }),
      )
      .mockResolvedValueOnce(response(sampleResponse))

    await expect(createQCTaskAndSample(params)).resolves.toEqual({
      success: false,
      data: {
        task_id: 'task-3',
        task_number: 'QC-003',
        sampled: false,
        sampled_count: 0,
      },
      message: '抽样结果缺少有效数量',
    })
  })

  it('创建响应没有任务 ID 时明确失败且不调用抽样', async () => {
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(
      response({ success: true, data: { task_number: 'QC-BROKEN' } }),
    )

    await expect(createQCTaskAndSample(params)).resolves.toEqual({
      success: false,
      message: '任务创建失败',
    })
    expect(ApiService.requestRaw).toHaveBeenCalledTimes(1)
  })
})
