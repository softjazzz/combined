import { describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import {
  exportMedicalRecordIndicators,
  getMedicalRecordIndicatorBreakdown,
  getMedicalRecordIndicatorCases,
  getMedicalRecordIndicators,
} from '@/api/medicalRecordIndicators'

describe('medical record indicators API', () => {
  it('keeps summary, breakdown and cases on the same discharged cohort filters', async () => {
    const request = vi
      .spyOn(ApiService, 'requestRaw')
      .mockResolvedValue({ status: 200, data: { success: true, data: {} } } as Awaited<
        ReturnType<typeof ApiService.requestRaw>
      >)
    const filters = {
      discharged_from: '2026-09-01',
      discharged_to: '2026-09-30',
      department: '内科',
    }
    await getMedicalRecordIndicators(filters)
    await getMedicalRecordIndicatorBreakdown(filters, 'MER-TL-01', 'doctor')
    await getMedicalRecordIndicatorCases(filters, 'MER-TL-01', 'unknown', 2)
    expect(request.mock.calls[0]?.[0]).toMatchObject({
      url: '/api/v1/quality-reports/medical-record-indicators',
      params: filters,
    })
    expect(request.mock.calls[1]?.[0].params).toMatchObject({
      ...filters,
      indicator_code: 'MER-TL-01',
      dimension: 'doctor',
    })
    expect(request.mock.calls[2]?.[0].params).toMatchObject({
      ...filters,
      indicator_code: 'MER-TL-01',
      state: 'unknown',
      page: 2,
      page_size: 20,
    })
  })

  it('exports the 27 item contract as a protected blob', async () => {
    const blob = new Blob(['a,b'])
    const request = vi
      .spyOn(ApiService, 'getRaw')
      .mockResolvedValue({ status: 200, data: blob } as Awaited<
        ReturnType<typeof ApiService.getRaw>
      >)
    expect(await exportMedicalRecordIndicators({ doctor: '张医生' })).toMatchObject({
      success: true,
      data: blob,
    })
    expect(request).toHaveBeenCalledWith(
      '/api/v1/quality-reports/medical-record-indicators/export',
      { doctor: '张医生', kind: 'indicators' },
      { responseType: 'blob' },
    )
  })
})
