import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { AppealStatus, AppealType } from '@/types/appeal'
import { createAppeal, getAppeal, getAppeals, reviewAppeal, withdrawAppeal } from '@/api/appeal'

const appealDto = {
  id: 'appeal-1', appeal_number: 'AP-1', qc_result_id: 'qc-1', record_id: 'record-1',
  appeal_type: 'defect', defect_item: '缺陷项', reason: '申诉理由达到最低长度', evidence: [{ name: '材料' }],
  status: 'accepted', priority: 'medium', appellant_id: 'user-1', appellant_name: '张医生',
  appellant_department: '内科', reviewer_id: null, reviewer_name: null, review_result: null,
  review_date: null, resolution: null, resolution_date: null, notes: null,
  created_at: '2026-09-23T01:00:00Z', updated_at: '2026-09-23T01:00:00Z',
}

function mockEnvelope(data: unknown) {
  return { status: 200, data: { success: true, data } } as Awaited<ReturnType<typeof ApiService.requestRaw>>
}

describe('appeal API contract', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('maps snake_case list DTO and page metadata, including historical accepted', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(mockEnvelope({
      items: [appealDto], total: 5, page: 2, page_size: 1, total_pages: 5,
    }))
    const result = await getAppeals({ status: 'reviewable', page: 2, pageSize: 1 })
    expect(request).toHaveBeenCalledWith(expect.objectContaining({ params: { status: 'reviewable', page: 2, page_size: 1 } }))
    expect(result.items[0]).toMatchObject({ id: 'appeal-1', status: AppealStatus.ACCEPTED, appealReason: appealDto.reason, appellantId: 'user-1' })
    expect(result).toMatchObject({ total: 5, pageSize: 1, totalPages: 5 })
  })

  it('maps detail and review history', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(mockEnvelope({
      ...appealDto, reviews: [{ id: 'review-1', appeal_id: 'appeal-1', reviewer_id: 'reviewer-1', action: 'approve', created_at: appealDto.created_at }],
    }))
    const result = await getAppeal('appeal-1')
    expect(result.reviews?.[0]).toMatchObject({ appealId: 'appeal-1', action: 'approve' })
  })

  it('accepts historical JSON text evidence without rendering string characters as items', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(mockEnvelope({
      ...appealDto, evidence: '[{"name":"旧证据"}]',
    })).mockResolvedValueOnce(mockEnvelope({
      ...appealDto, evidence: 'invalid-json',
    }))

    expect((await getAppeal('appeal-1')).evidence).toEqual([{ name: '旧证据' }])
    expect((await getAppeal('appeal-1')).evidence).toEqual([])
  })

  it('sends backend create, review and withdraw bodies', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(mockEnvelope(appealDto))
    await createAppeal({ qcResultId: 'qc-1', recordId: 'record-1', defectId: '缺陷项', appealType: AppealType.DEFECT, appealReason: appealDto.reason, evidenceUrls: ['https://example.test/a'] })
    await reviewAppeal('appeal-1', { action: 'reject', comment: '请按原判执行', resolution: '维持质控结果' })
    await withdrawAppeal('appeal-1')
    expect(request.mock.calls[0]?.[0]).toMatchObject({ data: { qc_result_id: 'qc-1', record_id: 'record-1', appeal_type: 'defect', defect_item: '缺陷项', reason: appealDto.reason, evidence: [{ url: 'https://example.test/a' }] } })
    expect(request.mock.calls[1]?.[0]).toMatchObject({ data: { action: 'reject', comment: '请按原判执行', resolution: '维持质控结果' } })
    expect(request.mock.calls[2]?.[0]).toMatchObject({ data: {} })
  })

  it('propagates list and detail errors', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockRejectedValue(new Error('service unavailable'))
    await expect(getAppeals()).rejects.toThrow()
    await expect(getAppeal('appeal-1')).rejects.toThrow()
  })
})
