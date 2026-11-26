import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import {
  exportFrontpageQualityReport,
  getFrontpageQualityRecords,
  getFrontpageQualityReport,
} from '@/api/frontpageQualityReport'

function error(status: number, data: unknown) {
  const response = {
    status,
    data,
    statusText: '',
    headers: {},
    config: { headers: new AxiosHeaders() },
  } as AxiosResponse
  return new AxiosError('failed', String(status), undefined, undefined, response)
}

describe('frontpage quality report API', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('drops empty filters and forwards drilldown filters', async () => {
    const request = vi
      .spyOn(ApiService, 'requestRaw')
      .mockResolvedValue({ status: 200, data: { success: true, data: {} } } as Awaited<
        ReturnType<typeof ApiService.requestRaw>
      >)
    await getFrontpageQualityReport({ department: '内科', doctor: '' })
    await getFrontpageQualityRecords({
      department: '内科',
      source: 'coding',
      rule_code: 'CR-1',
      problem_only: true,
      page: 2,
      page_size: 20,
    })
    expect(request.mock.calls[0][0]).toMatchObject({
      url: '/api/v1/quality-reports/frontpage-quality',
      params: { department: '内科' },
    })
    expect(request.mock.calls[0][0].params).not.toHaveProperty('doctor')
    expect(request.mock.calls[1][0]).toMatchObject({
      url: '/api/v1/quality-reports/frontpage-quality/records',
      params: {
        department: '内科',
        source: 'coding',
        rule_code: 'CR-1',
        problem_only: true,
        page: 2,
      },
    })
  })

  it('keeps the schema_unavailable code for the page to explain', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockRejectedValue(
      error(503, { detail: { code: 'schema_unavailable', message: '首页质控现代数据源未部署' } }),
    )
    expect(await getFrontpageQualityReport({})).toMatchObject({
      success: false,
      status: 503,
      code: 'schema_unavailable',
    })
  })

  it('exports the requested sheet as blob', async () => {
    const blob = new Blob(['a,b'])
    const getRaw = vi
      .spyOn(ApiService, 'getRaw')
      .mockResolvedValue({ status: 200, data: blob } as Awaited<
        ReturnType<typeof ApiService.getRaw>
      >)
    const result = await exportFrontpageQualityReport(
      { department: '外科', source: 'all' },
      'records',
    )
    expect(result).toMatchObject({ success: true, data: blob })
    expect(getRaw).toHaveBeenCalledWith(
      '/api/v1/quality-reports/frontpage-quality/export',
      { department: '外科', source: 'all', sheet: 'records' },
      expect.objectContaining({ responseType: 'blob', skipErrorToast: true, timeout: 120_000 }),
    )
  })
})
