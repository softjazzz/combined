import { describe, expect, it } from 'vitest'
import { AppealStatus, AppealType, canReviewAppeal, canWithdrawAppeal, type Appeal } from '@/types/appeal'

const appeal: Appeal = {
  id: 'appeal-1', appealNumber: null, qcResultId: 'qc-1', recordId: 'record-1',
  appealType: AppealType.DEFECT, defectItem: null, appealReason: '申诉理由达到最低长度',
  evidence: [], status: AppealStatus.PENDING, priority: 'medium',
  appellantId: 'doctor-1', appellantName: null, appellantDepartment: null,
  reviewerId: null, reviewerName: null, reviewResult: null, reviewedAt: null,
  resolution: null, resolutionDate: null, notes: null,
  createdAt: '2026-09-23T00:00:00Z', updatedAt: '2026-09-23T00:00:00Z',
}

describe('appeal action visibility', () => {
  it('only reviewer roles may review pending or reviewing appeals', () => {
    expect(canReviewAppeal(appeal, ['doctor'])).toBe(false)
    expect(canReviewAppeal(appeal, ['qc_staff'])).toBe(false)
    expect(canReviewAppeal(appeal, ['qc_manager'])).toBe(true)
    expect(canReviewAppeal({ ...appeal, status: AppealStatus.REVIEWING }, ['admin'])).toBe(true)
    expect(canReviewAppeal({ ...appeal, status: AppealStatus.ACCEPTED }, ['admin'])).toBe(false)
  })

  it('only appellant may withdraw nonterminal appeals', () => {
    expect(canWithdrawAppeal(appeal, 'doctor-2')).toBe(false)
    expect(canWithdrawAppeal(appeal, undefined)).toBe(false)
    expect(canWithdrawAppeal(appeal, 'doctor-1')).toBe(true)
    expect(canWithdrawAppeal({ ...appeal, status: AppealStatus.ACCEPTED }, 'doctor-1')).toBe(false)
  })
})
