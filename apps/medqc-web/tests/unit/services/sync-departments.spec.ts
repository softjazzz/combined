import { beforeEach, describe, expect, it, vi } from 'vitest'
import { syncApi } from '@/api/sync'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/utils/http', () => ({ http: { get } }))

describe('源科室请求取消及错误合同', () => {
  beforeEach(() => { get.mockReset() })

  it('传递AbortSignal，仍使用原科室接口和应答格式', async () => {
    const controller = new AbortController()
    get.mockResolvedValue({ data: { success: true, data: { items: ['合成科室'] } } })
    expect(await syncApi.getDepartments(controller.signal)).toEqual(['合成科室'])
    expect(get).toHaveBeenCalledWith('/api/v1/sync/departments', { signal: controller.signal })
  })

  it('503保持失败，不转换为空科室列表', async () => {
    const error = new Error('synthetic 503')
    get.mockRejectedValue(error)
    await expect(syncApi.getDepartments()).rejects.toBe(error)
    expect(get).toHaveBeenCalledTimes(1)
  })
})
