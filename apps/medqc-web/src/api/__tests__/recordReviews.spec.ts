import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  getRecordReviewCurrent,
  getRecordReviewHistory,
  listRecordReviews,
  submitRecordReview,
} from '../recordReviews'

const raw = vi.hoisted(() => vi.fn())
vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: raw } }))
const source = {
  institute_id: 'I',
  patient_id: 'P',
  visit_id: 'V',
  scene: 'running',
  root_job_id: 'J',
  envelope_id: 'E',
  rule_set_key: 'K',
  rule_set_version: '1',
} as const
const review = {
  ...source,
  id: 'review',
  request_id: 'request',
  stage: 'initial',
  decision: 'approved',
  reason: null,
  reviewer_id: 'staff',
  created_at: '2026-10-25',
  case_department: '内科',
}
const detail = {
  ...source,
  state: 'pending_review',
  stage: 'initial',
  current_review: null,
  history: [],
  can_submit: true,
  case_department: '内科',
}
beforeEach(() => raw.mockReset())
describe('病历审核来源与状态边界', () => {
  it('审核提交冻结完整来源、CAS状态和请求ID', async () => {
    raw.mockResolvedValue({ data: { success: true, data: review } })
    await submitRecordReview(source, 'pending_review', 'approved', '', 'request')
    expect(raw).toHaveBeenLastCalledWith(
      expect.objectContaining({
        data: {
          source,
          expected_state: 'pending_review',
          decision: 'approved',
          reason: '',
          request_id: 'request',
        },
      }),
    )
    raw.mockResolvedValue({ data: detail })
    await getRecordReviewCurrent(source)
    expect(raw).toHaveBeenLastCalledWith(expect.objectContaining({ params: source }))
  })
  it.each(['envelope_id', 'rule_set_version', 'patient_id'])('缺少%s拒绝回执', async (key) => {
    raw.mockResolvedValue({ data: { ...review, [key]: null } })
    await expect(
      submitRecordReview(source, 'pending_review', 'approved', '', 'request'),
    ).rejects.toThrow('审核回执无效')
  })
  it('待办未知或计数不一致时拒绝当作零', async () => {
    raw.mockResolvedValue({
      data: { items: [], total: 0, pending_count: null, initial_count: 0, recheck_count: 0 },
    })
    await expect(listRecordReviews()).rejects.toThrow('待办数据无效')
    raw.mockResolvedValue({
      data: { items: [], total: 0, pending_count: 2, initial_count: 0, recheck_count: 0 },
    })
    await expect(listRecordReviews()).rejects.toThrow('待办数据无效')
  })
  it('历史非法或已有决定仍允许提交时拒收', async () => {
    raw.mockResolvedValue({ data: { ...detail, history: [{ id: 'broken' }] } })
    await expect(getRecordReviewHistory('review')).rejects.toThrow('来源或历史无效')
    raw.mockResolvedValue({ data: { ...detail, current_review: review } })
    await expect(getRecordReviewCurrent(source)).rejects.toThrow('审核状态无效')
  })
  it('拒绝迟到或错病例来源、错提交回执和错历史ID', async () => {
    raw.mockResolvedValue({ data: { ...detail, envelope_id: 'other' } })
    await expect(getRecordReviewCurrent(source)).rejects.toThrow('请求来源不一致')
    raw.mockResolvedValue({ data: { ...review, request_id: 'different' } })
    await expect(
      submitRecordReview(source, 'pending_review', 'approved', '', 'request'),
    ).rejects.toThrow('提交内容不一致')
    raw.mockResolvedValue({
      data: { ...detail, state: 'approved', can_submit: false, current_review: review },
    })
    await expect(getRecordReviewHistory('different')).rejects.toThrow('请求事件不一致')
  })
})
