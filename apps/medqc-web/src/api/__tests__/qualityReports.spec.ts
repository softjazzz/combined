import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import {
  exportRecordQualityReport,
  getRecordQualityRecords,
  getRecordQualityReport,
} from '@/api/qualityReports'

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

describe('quality reports API', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('uses the same scoped filters for summary and drilldown', async () => {
    const request = vi
      .spyOn(ApiService, 'requestRaw')
      .mockResolvedValue({ status: 200, data: { success: true, data: {} } } as Awaited<
        ReturnType<typeof ApiService.requestRaw>
      >)
    await getRecordQualityReport({
      scene: 'running',
      department: '内科',
      doctor: '',
      defect_source: 'manual',
    })
    await getRecordQualityRecords({
      scene: 'running',
      department: '内科',
      rule_id: 'LX0609-001',
      page: 2,
      page_size: 20,
    })
    expect(request.mock.calls[0]?.[0]).toMatchObject({
      url: '/api/v1/quality-reports/record-quality',
      params: { scene: 'running', department: '内科', defect_source: 'manual' },
    })
    expect(request.mock.calls[0]?.[0].params).not.toHaveProperty('doctor')
    expect(request.mock.calls[1]?.[0]).toMatchObject({
      url: '/api/v1/quality-reports/record-quality/records',
      params: {
        scene: 'running',
        department: '内科',
        rule_id: 'LX0609-001',
        page: 2,
        page_size: 20,
      },
    })
  })

  it('preserves the final archive blocker code', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockRejectedValue(
      error(409, { error: { code: 'archive_scope_unverified', message: '归档范围未核实' } }),
    )
    expect(await getRecordQualityReport({ scene: 'final' })).toMatchObject({
      success: false,
      status: 409,
      code: 'archive_scope_unverified',
    })
  })

  it('requests a protected blob export with current filters', async () => {
    const blob = new Blob(['a,b'])
    const request = vi
      .spyOn(ApiService, 'getRaw')
      .mockResolvedValue({ status: 200, data: blob } as Awaited<
        ReturnType<typeof ApiService.getRaw>
      >)
    const result = await exportRecordQualityReport(
      { scene: 'running', doctor: '张医生', rule_id: 'LX0609-001' },
      'records',
    )
    expect(result).toMatchObject({ success: true, data: blob })
    expect(request).toHaveBeenCalledWith(
      '/api/v1/quality-reports/record-quality/export',
      { scene: 'running', doctor: '张医生', rule_id: 'LX0609-001', sheet: 'records' },
      { responseType: 'blob' },
    )
  })
})
