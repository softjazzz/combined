import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { exportStaffAnalysis, getStaffAnalysis, getStaffAnalysisDetails } from '@/api/staffAnalysis'

describe('staff analysis API', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('保留初审缺陷未知总体、已知明细与覆盖字段', async () => {
    const coverage = {
      initial_review_count: 2,
      covered_initial_review_count: 1,
      missing_initial_review_count: 1,
      known_defect_count: 3,
    }
    const data = {
      metric: 'confirmed_defect_count',
      items: [],
      total: null,
      known_total: 3,
      total_complete: false,
      defect_snapshot_coverage: coverage,
      unavailable_reason: 'snapshot_incomplete',
    }
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue({
      status: 200,
      data: { success: true, data },
    } as Awaited<ReturnType<typeof ApiService.requestRaw>>)
    const result = await getStaffAnalysisDetails(
      'staff',
      { period: 'this_week', scene: 'final' },
      'confirmed_defect_count',
      2,
      1,
    )
    expect(result.data).toEqual(data)
    expect(request).toHaveBeenCalledWith(
      expect.objectContaining({
        params: {
          period: 'this_week',
          scene: 'final',
          metric: 'confirmed_defect_count',
          page: 2,
          page_size: 1,
        },
      }),
    )
  })

  it('passes period and scene to the protected report endpoint', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue({
      status: 200,
      data: {
        success: true,
        data: { scene: 'all', summary: null, staff: [], unavailable_metrics: {} },
      },
    } as Awaited<ReturnType<typeof ApiService.requestRaw>>)
    const result = await getStaffAnalysis({ period: 'last_week', scene: 'all' })
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

    const result = await getStaffAnalysis({ period: 'this_week', scene: 'running' })

    expect(request).toHaveBeenCalledWith(
      expect.objectContaining({
        params: { period: 'this_week', scene: 'running' },
      }),
    )
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
    const result = await getStaffAnalysis({ period: 'this_month', scene: 'running' })
    expect(result).toMatchObject({ success: false, status: 503 })
    expect(result.data).toBeUndefined()
  })

  it('passes the frozen report filters to staff details with encoded user and paging', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue({
      status: 200,
      data: { success: true, data: { items: [], total: 0, page: 2, page_size: 20 } },
    } as Awaited<ReturnType<typeof ApiService.requestRaw>>)
    await getStaffAnalysisDetails(
      'user/1',
      {
        period: 'this_month',
        scene: 'running',
        institute_id: 'H1',
        department: '心内科',
        task_id: 'task-1',
        start_date: '2026-09-01',
        end_date: '2026-09-28',
        as_of: '2026-09-29T00:00:00+08:00',
      },
      'record_review_count',
      2,
      20,
    )
    expect(request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/quality-reports/staff-work/user%2F1/details',
      params: {
        period: 'this_month',
        scene: 'running',
        institute_id: 'H1',
        department: '心内科',
        task_id: 'task-1',
        start_date: '2026-09-01',
        end_date: '2026-09-28',
        as_of: '2026-09-29T00:00:00+08:00',
        metric: 'record_review_count',
        page: 2,
        page_size: 20,
      },
    })
  })

  it('exports the same frozen aggregate filters as CSV blob', async () => {
    const blob = new Blob(['csv'])
    const response: AxiosResponse<Blob> = {
      status: 200,
      statusText: 'OK',
      data: blob,
      headers: new AxiosHeaders({ 'content-type': 'text/csv; charset=utf-8' }),
      config: { headers: new AxiosHeaders() },
    }
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response)
    const result = await exportStaffAnalysis({
      period: 'this_week',
      scene: 'all',
      as_of: '2026-09-28T00:00:00Z',
    })
    expect(request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/quality-reports/staff-work/export',
      params: { period: 'this_week', scene: 'all', as_of: '2026-09-28T00:00:00Z' },
      responseType: 'blob',
    })
    expect(result).toMatchObject({ success: true, data: blob })
  })

  it('does not accept a JSON error blob as a CSV download', async () => {
    const body = new Blob([JSON.stringify({ detail: { message: '筛选范围过大' } })], {
      type: 'application/json',
    })
    const response: AxiosResponse<Blob> = {
      status: 200,
      statusText: 'OK',
      data: body,
      headers: new AxiosHeaders({ 'content-type': 'application/json' }),
      config: { headers: new AxiosHeaders() },
    }
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response)
    const result = await exportStaffAnalysis({ period: 'this_month', scene: 'all' })
    expect(result).toMatchObject({ success: false, message: '筛选范围过大' })
    expect(result.data).toBeUndefined()
  })
})
