import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { getManualDefects } from '@/api/manualDefectReviews'

function response(scene: 'all' | 'running' | 'final' | 'outpatient_emergency') {
  return {
    status: 200,
    data: {
      success: true,
      data: { items: [], total: 0, page: 1, page_size: 20, scene },
    },
  } as Awaited<ReturnType<typeof ApiService.requestRaw>>
}

describe('manual defect review API', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('passes the exact frozen scene to the pending review list', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response('running'))

    const result = await getManualDefects('pending', 2, 20, 'running')

    expect(request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/manual-defects',
      params: { review_status: 'pending', page: 2, page_size: 20, scene: 'running' },
    })
    expect(result.data?.scene).toBe('running')
  })

  it('keeps all as the backward-compatible default scene', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response('all'))

    await getManualDefects()

    expect(request).toHaveBeenCalledWith(expect.objectContaining({
      params: { review_status: 'pending', page: 1, page_size: 20, scene: 'all' },
    }))
  })
})
