import { beforeEach, describe, expect, it, vi } from 'vitest'
import { dataPipelinesApi } from '@/api/dataPipelines'

const transport = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }))
vi.mock('@/utils/http', () => ({ http: transport }))

describe('双抽取链路API合同', () => {
  beforeEach(() => vi.resetAllMocks())
  it('读取与保存配置只调用链路设置API', async () => {
    const settings = {
      version: 1,
      default_pipeline: 'independent_cdm' as const,
      independent_enabled: true,
    }
    transport.get.mockResolvedValue({ data: { success: true, data: { settings } } })
    transport.put.mockResolvedValue({ data: { success: true, data: { settings } } })
    expect((await dataPipelinesApi.configuration()).settings).toEqual(settings)
    await dataPipelinesApi.save(settings)
    expect(transport.put).toHaveBeenCalledWith('/api/v1/sync/pipelines', settings)
    expect(transport.post).not.toHaveBeenCalled()
  })
  it('任务提交保持幂等标识、原日期与接口范围，不走旧PG或质控接口', async () => {
    const payload = {
      operation_id: '00112233-4455-6677-8899-aabbccddeeff',
      start_date: '2020-10-26',
      end_date: '2020-10-28',
      interfaces: ['web.mr'],
      mode: 'dry' as const,
      publish: false,
    }
    transport.post.mockResolvedValue({
      data: { success: true, data: { job_id: 'job', status: 'queued' } },
    })
    await dataPipelinesApi.submit(payload)
    expect(transport.post).toHaveBeenCalledTimes(1)
    expect(transport.post).toHaveBeenCalledWith('/api/v1/sync/pipelines/independent/jobs', payload)
  })
  it('失败响应与Promise异常不变成空任务或成功', async () => {
    transport.get.mockResolvedValue({ data: { success: false, data: null } })
    await expect(dataPipelinesApi.jobs()).rejects.toThrow()
    transport.post.mockRejectedValue(new Error('503'))
    await expect(dataPipelinesApi.check()).rejects.toThrow('503')
  })
})
