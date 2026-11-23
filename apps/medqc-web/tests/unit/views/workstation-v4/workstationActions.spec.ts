import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  persistBatchFrontpageDraft,
  requestCodingQc,
  requestFrontpageDraft,
  requestFrontpageQc,
  requestSettlementQc,
} from '@/views/workstation-v4/workstationActions'
import type { PatientRecord } from '@/views/workstation-v4/types'

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}))

vi.mock('@/services/apiService', () => ({
  default: { isAuthenticated: () => true },
  apiClient: {
    get: mockGet,
    post: mockPost,
  },
}))

const sampleRecord: PatientRecord = {
  id: 'V-100',
  visitId: 'V-100',
  instituteId: 'HOSP-01',
  patientId: 'PAT-01',
  bedNo: '12',
  name: '测试患者',
  sex: '女',
  age: 35,
  insurance: '医保',
  department: '内科',
  admissionDate: '2026-06-01',
  dischargeDate: '2026-06-10',
  days: 9,
  diagnosis: '肺炎',
  diagnosisCode: 'J18.9',
  doctor: '王医师',
  status: 'pending',
}

describe('workstationActions 透传 institute_id 与 patient_id', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('requestFrontpageDraft 支持传入完整病历或 identity 透传 institute_id 与 patient_id', async () => {
    mockPost.mockResolvedValue({ data: { success: true, data: { frontpage: { ok: true } } } })

    await requestFrontpageDraft(sampleRecord)
    expect(mockPost).toHaveBeenNthCalledWith(
      1,
      '/api/v1/frontpage/auto-generate-draft',
      {
        visit_id: 'V-100',
        patient_id: 'PAT-01',
        institute_id: 'HOSP-01',
      },
      expect.objectContaining({ timeout: expect.any(Number) }),
    )

    await requestFrontpageDraft('V-200', { instituteId: 'HOSP-02', patientId: 'PAT-02' })
    expect(mockPost).toHaveBeenNthCalledWith(
      2,
      '/api/v1/frontpage/auto-generate-draft',
      {
        visit_id: 'V-200',
        patient_id: 'PAT-02',
        institute_id: 'HOSP-02',
      },
      expect.objectContaining({ timeout: expect.any(Number) }),
    )
  })

  it('persistBatchFrontpageDraft 透传三键', async () => {
    mockPost.mockResolvedValue({ data: { success: true } })
    await persistBatchFrontpageDraft(sampleRecord, { field: 'val' })

    expect(mockPost).toHaveBeenCalledWith('/api/medical-records/ai-frontpage-draft', {
      institute_id: 'HOSP-01',
      patient_id: 'PAT-01',
      visit_id: 'V-100',
      draft_json: JSON.stringify({ field: 'val' }),
    })
  })

  it('requestCodingQc 透传 institute_id、patient_id、visit_id', async () => {
    mockPost.mockResolvedValue({
      data: { success: true, data: { total_issues: 2, errors: 1 } },
    })

    const res = await requestCodingQc(sampleRecord)
    expect(mockPost).toHaveBeenCalledWith('/api/v1/qc/coding-qc/check', {
      institute_id: 'HOSP-01',
      visit_id: 'V-100',
      patient_id: 'PAT-01',
    })
    expect(res).toMatchObject({ totalIssues: 2, highRiskCount: 1 })
  })

  it('requestFrontpageQc 在拉取首页和执行形式质控时均透传 institute_id', async () => {
    mockGet.mockResolvedValueOnce({ data: { basic_info: { name: '测试患者' } } })
    mockPost.mockResolvedValueOnce({
      data: {
        success: true,
        data: { failed: 1, results: [{ severity: 'error' }] },
      },
    })

    const res = await requestFrontpageQc(sampleRecord)
    expect(mockGet).toHaveBeenCalledWith('/api/medical-records/frontpage-sheet/PAT-01/V-100', {
      params: { institute_id: 'HOSP-01' },
    })
    expect(mockPost).toHaveBeenCalledWith('/api/v1/qc/formal-qc/validate', {
      institute_id: 'HOSP-01',
      patient_id: 'PAT-01',
      visit_id: 'V-100',
      frontpage: { basic_info: { name: '测试患者' } },
    })
    expect(res).toMatchObject({ totalIssues: 1, highRiskCount: 1 })
  })

  it('requestSettlementQc 通过 query params 透传 institute_id', async () => {
    mockPost.mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          results: [{ passed: false, severity: 'high' }],
        },
      },
    })

    const res = await requestSettlementQc(sampleRecord)
    expect(mockPost).toHaveBeenCalledWith(
      '/api/medical-records/settlement/PAT-01/V-100/qc',
      undefined,
      { params: { institute_id: 'HOSP-01' } },
    )
    expect(res).toMatchObject({ totalIssues: 1, highRiskCount: 1 })
  })
})
