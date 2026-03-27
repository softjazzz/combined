import { beforeEach, describe, expect, it, vi } from 'vitest'

import { panelApi } from '@/api/panel'

const fetchMock = vi.fn<{
  (input: unknown, init?: unknown): Promise<Response>
}>()

function mockFetchResponse(payload: unknown, ok = true, status = 200, statusText = 'OK') {
  fetchMock.mockResolvedValueOnce({
    ok,
    status,
    statusText,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response)
}

describe('panelApi', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    fetchMock.mockReset()
    localStorage.clear()
  })

  it('支持响应壳并透传 data', async () => {
    localStorage.setItem('medqc_access_token', 'token-123')
    mockFetchResponse({
      success: true,
      data: { total_alerts: 8, severe_alerts: 2 },
      trace_id: 'trace-1',
    })

    const result = await panelApi.getMonitoringStats()

    expect(result.total_alerts).toBe(8)
    expect(result.severe_alerts).toBe(2)
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      headers: expect.objectContaining({
        Authorization: 'Bearer token-123',
      }),
    })
  })

  it('非响应壳也可正常解析', async () => {
    mockFetchResponse({ labels: ['D1'], values: [1], benchmark: 1.1 })
    const result = await panelApi.getCmiTrend(1)
    expect(result.labels).toEqual(['D1'])
  })

  it('错误时抛出标准错误消息', async () => {
    mockFetchResponse({ error: 'forbidden' }, false, 403, 'Forbidden')
    await expect(panelApi.getMessageSummary()).rejects.toThrow('forbidden')
  })
})
