import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { getStaffAnalysis } from '@/api/staffAnalysis'

describe('staff analysis API', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('passes period and scene to the protected report endpoint', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue({
      status: 200,
      data: { success: true, data: { scene: 'all', summary: null, staff: [], unavailable_metrics: {} } },
    } as Awaited<ReturnType<typeof ApiService.requestRaw>>)
    const result = await getStaffAnalysis('last_week', 'all')
    expect(request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/quality-reports/staff-work',
      params: { period: 'last_week', scene: 'all' },
    })
    expect(result.success).toBe(true)
  })

  it('preserves field-level unknown appeal metrics for a concrete scene', async () => {
    const report = {
      period: 'this_week',
      period_label: '本周',
      range: { start: '2026-09-21T00:00:00Z', end: '2026-09-28T00:00:00Z' },
      scene: 'running',
      summary: {
        active_staff_count: 1,
        record_reviewer_count: 1,
        record_review_count: 2,
        reviewed_case_count: 1,
        initial_count: 1,
        recheck_count: 1,
        avg_record_reviews_per_active_staff: 2,
        avg_reviewed_cases_per_reviewer: 1,
        manual_defect_created_count: 1,
        manual_review_approved_count: 1,
        manual_review_rejected_count: 0,
        appeal_approved_count: null,
        appeal_rejected_count: null,
      },
      staff: [],
      unavailable_reason: null,
      unavailable_metrics: {
        appeal_approved_count: 'scene_not_attributable',
        appeal_rejected_count: 'scene_not_attributable',
      },
    } as const
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue({
      status: 200,
      data: { success: true, data: report },
    } as Awaited<ReturnType<typeof ApiService.requestRaw>>)

    const result = await getStaffAnalysis('this_week', 'running')

    expect(request).toHaveBeenCalledWith(expect.objectContaining({
      params: { period: 'this_week', scene: 'running' },
    }))
    expect(result).toMatchObject({
      success: true,
      data: {
        scene: 'running',
        summary: { appeal_approved_count: null, appeal_rejected_count: null },
        unavailable_reason: null,
        unavailable_metrics: {
          appeal_approved_count: 'scene_not_attributable',
          appeal_rejected_count: 'scene_not_attributable',
        },
      },
    })
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
