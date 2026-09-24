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

describe('statistics overview todo availability', () => {
  beforeEach(() => {
    requestRaw.mockReset()
  })

  it('keeps independent metrics but marks todo-derived counts unavailable after a 503', async () => {
    requestRaw.mockImplementation(async ({ url }: { url: string }) => {
      if (url === '/api/v1/reports/qc/summary') {
        return { data: { success: true, data: { kpis: { total_records: 12, pending: 7, avg_qc_score: 91, pass_rate: 0.75 } } } }
      }
      if (url === '/api/v1/dashboard/overview') {
        return { data: { success: true, data: { total_records: 12, avg_score: 89, pass_rate: 0.7 } } }
      }
      throw new Error('503 Service Unavailable')
    })

    const { getStatisticsOverview } = await import('../statistics-api')
    await expect(getStatisticsOverview()).resolves.toMatchObject({
      totalRecords: 12,
      pendingRecords: null,
      analyzingRecords: null,
      completedRecords: null,
      averageScore: 91,
      passRate: 75,
    })
  })

  it('does not treat a failed todo envelope as an empty successful result', async () => {
    requestRaw.mockImplementation(async ({ url }: { url: string }) => {
      if (url === '/api/v1/reports/qc/summary') {
        return { data: { success: true, data: { kpis: { total_records: 12, pending: 7 } } } }
      }
      if (url === '/api/v1/dashboard/todo-stats') {
        return { data: { success: false, code: 503, message: '待办统计不可用' } }
      }
      return { data: { success: true, data: { total_records: 12, avg_score: 90, pass_rate: 0.8 } } }
    })

    const { getStatisticsOverview } = await import('../statistics-api')
    await expect(getStatisticsOverview()).resolves.toMatchObject({
      totalRecords: 12,
      pendingRecords: null,
      analyzingRecords: null,
      completedRecords: null,
      averageScore: 90,
      passRate: 80,
    })
  })

  it('preserves genuine zero todo counts', async () => {
    requestRaw.mockImplementation(async ({ url }: { url: string }) => {
      if (url === '/api/v1/reports/qc/summary') {
        return { data: { success: true, data: { kpis: { total_records: 12, pending: 7 } } } }
      }
      if (url === '/api/v1/dashboard/todo-stats') {
        return {
          data: {
            success: true,
            data: {
              task_stats: { not_started: 0, in_progress: 0, countdown: 0 },
              record_stats: { pending_review: 5, pending_recheck: 3, total: 12 },
              defect_stats: { clinical_appeals: 0, pending_review: 0, urged: 0 },
            },
          },
        }
      }
      return { data: { success: true, data: { total_records: 12, avg_score: 0, pass_rate: 0 } } }
    })

    const { getStatisticsOverview } = await import('../statistics-api')
    await expect(getStatisticsOverview()).resolves.toMatchObject({
      totalRecords: 12,
      pendingRecords: 0,
      analyzingRecords: 0,
      completedRecords: 12,
    })
  })
})
