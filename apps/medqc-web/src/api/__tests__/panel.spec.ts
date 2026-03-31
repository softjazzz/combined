import { beforeEach, describe, expect, it, vi } from 'vitest'

import { panelApi } from '@/api/panel'
import { ApiService } from '@/services/apiService'

describe('panelApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('支持响应壳并透传 data', async () => {
    vi.spyOn(ApiService, 'getRaw').mockResolvedValueOnce({
      status: 200,
      data: {
        success: true,
        data: { total_alerts: 8, severe_alerts: 2 },
      },
    } as any)

    const result = await panelApi.getMonitoringStats()
    expect(result.total_alerts).toBe(8)
    expect(result.severe_alerts).toBe(2)
  })

  it('非响应壳也可正常解析', async () => {
    vi.spyOn(ApiService, 'getRaw').mockResolvedValueOnce({
      status: 200,
      data: { labels: ['D1'], values: [1], benchmark: 1.1 },
    } as any)

    const result = await panelApi.getCmiTrend(1)
    expect(result.labels).toEqual(['D1'])
  })

  it('错误时抛出标准错误消息', async () => {
    vi.spyOn(ApiService, 'getRaw').mockRejectedValueOnce({
      response: {
        status: 403,
        data: { error: 'forbidden' },
      },
      message: 'Network Error',
    })

    await expect(panelApi.getMessageSummary()).rejects.toThrow('forbidden')
  })
})
