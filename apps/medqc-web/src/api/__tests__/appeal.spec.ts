import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { AppealStatus, AppealType } from '@/types/appeal'
import {
  createAppeal,
  getAppeal,
  getAppealCandidates,
  getAppeals,
  reviewAppeal,
  withdrawAppeal,
} from '@/api/appeal'

const appealDto = {
  id: 'appeal-1',
  appeal_number: 'AP-1',
  qc_result_id: 'qc-1',
  record_id: 'record-1',
  appeal_type: 'defect',
  defect_item: '缺陷项',
  reason: '申诉理由达到最低长度',
  evidence: [{ name: '材料' }],
  status: 'accepted',
  priority: 'medium',
  appellant_id: 'user-1',
  appellant_name: '张医生',
  appellant_department: '内科',
  reviewer_id: null,
  reviewer_name: null,
  review_result: null,
  review_date: null,
  resolution: null,
  resolution_date: null,
  notes: null,
  created_at: '2026-09-23T01:00:00Z',
  updated_at: '2026-09-23T01:00:00Z',
}

function mockEnvelope(data: unknown) {
  return { status: 200, data: { success: true, data } } as Awaited<
    ReturnType<typeof ApiService.requestRaw>
  >
}

describe('appeal API contract', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('maps snake_case list DTO and page metadata, including historical accepted', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(
      mockEnvelope({
        items: [appealDto],
        total: 5,
        page: 2,
        page_size: 1,
        total_pages: 5,
      }),
    )
    const result = await getAppeals({ status: 'reviewable', page: 2, pageSize: 1 })
    expect(request).toHaveBeenCalledWith(
      expect.objectContaining({ params: { status: 'reviewable', page: 2, page_size: 1 } }),
    )
    expect(result.items[0]).toMatchObject({
      id: 'appeal-1',
      status: AppealStatus.ACCEPTED,
      appealReason: appealDto.reason,
      appellantId: 'user-1',
    })
    expect(result).toMatchObject({ total: 5, pageSize: 1, totalPages: 5 })
  })

  it('maps detail and review history', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(
      mockEnvelope({
        ...appealDto,
        reviews: [
          {
            id: 'review-1',
            appeal_id: 'appeal-1',
            reviewer_id: 'reviewer-1',
            action: 'approve',
            created_at: appealDto.created_at,
          },
        ],
      }),
    )
    const result = await getAppeal('appeal-1')
    expect(result.reviews?.[0]).toMatchObject({ appealId: 'appeal-1', action: 'approve' })
  })

  it('accepts historical JSON text evidence without rendering string characters as items', async () => {
    vi.spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce(
        mockEnvelope({
          ...appealDto,
          evidence: '[{"name":"旧证据"}]',
        }),
      )
      .mockResolvedValueOnce(
        mockEnvelope({
          ...appealDto,
          evidence: 'invalid-json',
        }),
      )

    expect((await getAppeal('appeal-1')).evidence).toEqual([{ name: '旧证据' }])
    expect((await getAppeal('appeal-1')).evidence).toEqual([])
  })

  it('sends modern trusted create, review and withdraw bodies without legacy identifiers', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(mockEnvelope(appealDto))
    await createAppeal({
      targetKind: 'canonical_defect',
      instituteId: 'H1',
      patientId: 'P1',
      visitId: 'V1',
      scene: 'running',
      expectedJobId: 'job-1',
      expectedEnvelopeId: 'env-1',
      ruleId: 'LX0609-001',
      appealReason: appealDto.reason,
      evidence: [{ name: '材料' }],
    })
    await reviewAppeal('appeal-1', {
      action: 'reject',
      comment: '请按原判执行',
      resolution: '维持质控结果',
    })
    await withdrawAppeal('appeal-1')
    expect(request.mock.calls[0]?.[0]).toMatchObject({
      url: '/api/v1/appeals/modern',
      data: {
        target_kind: 'canonical_defect',
        institute_id: 'H1',
        patient_id: 'P1',
        visit_id: 'V1',
        scene: 'running',
        expected_job_id: 'job-1',
        expected_envelope_id: 'env-1',
        rule_id: 'LX0609-001',
        reason: appealDto.reason,
        evidence: [{ name: '材料' }],
      },
    })
    expect(request.mock.calls[0]?.[0].data).not.toHaveProperty('record_id')
    expect(request.mock.calls[0]?.[0].data).not.toHaveProperty('qc_result_id')
    expect(request.mock.calls[1]?.[0]).toMatchObject({
      data: { action: 'reject', comment: '请按原判执行', resolution: '维持质控结果' },
    })
    expect(request.mock.calls[2]?.[0]).toMatchObject({ data: {} })
  })

  it('reads candidates by exact three-coordinate identity and rejects mismatched identity', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(
      mockEnvelope({
        institute_id: 'H1',
        patient_id: 'P1',
        visit_id: 'V1',
        case_department: '心内科',
        canonical: {
          state: 'ready',
          scene: 'final',
          job_id: 'job-1',
          envelope_id: 'env-1',
          items: [{ rule_id: 'LX0609-001', rule_name: '入院记录', conclusion: '超时' }],
        },
        manual_defects: [
          {
            defect_id: 'manual-1',
            rule_code: 'MANUAL',
            rule_name: '人工问题',
            description: '说明',
            scene: 'final',
          },
        ],
      }),
    )
    const result = await getAppealCandidates({ instituteId: 'H1', patientId: 'P1', visitId: 'V1' })
    expect(request).toHaveBeenCalledWith(
      expect.objectContaining({ params: { institute_id: 'H1', patient_id: 'P1', visit_id: 'V1' } }),
    )
    expect(result.canonical).toMatchObject({ state: 'ready', jobId: 'job-1', envelopeId: 'env-1' })
    expect(result.manualDefects[0]).toMatchObject({ defectId: 'manual-1', scene: 'final' })

    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(
      mockEnvelope({
        institute_id: 'H2',
        patient_id: 'P1',
        visit_id: 'V1',
        canonical: { state: 'no_result', items: [] },
        manual_defects: [],
      }),
    )
    await expect(
      getAppealCandidates({ instituteId: 'H1', patientId: 'P1', visitId: 'V1' }),
    ).rejects.toThrow('不一致')
  })

  it('fails closed on an unknown appeal status', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(
      mockEnvelope({ ...appealDto, status: 'job_completed' }),
    )
    await expect(getAppeal('appeal-1')).rejects.toThrow('未知状态')
  })

  it('propagates list and detail errors', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockRejectedValue(new Error('service unavailable'))
    await expect(getAppeals()).rejects.toThrow()
    await expect(getAppeal('appeal-1')).rejects.toThrow()
  })
})
