import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { getStaffAnalysis } from '@/api/staffAnalysis'

describe('staff analysis API', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('passes period and scene to the protected report endpoint', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue({
      status: 200,
      data: { success: true, data: { scene: 'all', summary: null, staff: [] } },
    } as Awaited<ReturnType<typeof ApiService.requestRaw>>)
    const result = await getStaffAnalysis('last_week', 'all')
    expect(request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/quality-reports/staff-work',
      params: { period: 'last_week', scene: 'all' },
    })
    expect(result.success).toBe(true)
  })

  it('returns the API error instead of a fabricated empty report', async () => {
    const response = {
      status: 503,
      data: { detail: { message: '统计来源暂不可用' } },
      statusText: '',
      headers: {},
      config: { headers: new AxiosHeaders() },
    } as AxiosResponse
    vi.spyOn(ApiService, 'requestRaw').mockRejectedValue(
      new AxiosError('failed', '503', undefined, undefined, response),
    )
    const result = await getStaffAnalysis('this_month', 'running')
    expect(result).toMatchObject({ success: false, status: 503 })
    expect(result.data).toBeUndefined()
  })
})
