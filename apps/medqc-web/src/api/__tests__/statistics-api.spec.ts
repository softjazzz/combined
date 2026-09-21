import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const requestRaw = vi.fn()

vi.mock('@/services/apiService', () => ({
  ApiService: {
    requestRaw,
  },
}))

describe('statistics-api protected report export', () => {
  beforeEach(() => {
    requestRaw.mockReset()
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:qc-export'),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('downloads the private report with the authenticated API client', async () => {
    const report = new Blob(['record_id\nrecord-1\n'], { type: 'text/csv' })
    requestRaw
      .mockResolvedValueOnce({
        data: {
          success: true,
          data: {
            download_url: '/api/v1/reports/qc/export/abc/download',
            count: 1,
          },
        },
      })
      .mockResolvedValueOnce({ data: report })

    const { exportStatisticsReport } = await import('../statistics-api')
    const result = await exportStatisticsReport('excel')

    expect(requestRaw).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        method: 'GET',
        url: '/api/v1/reports/qc/export/abc/download',
        responseType: 'blob',
      }),
    )
    expect(URL.createObjectURL).toHaveBeenCalledWith(report)
    expect(result).toEqual({ count: 1, downloadUrl: 'blob:qc-export' })
  })
})
