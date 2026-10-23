import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { getReviewTodoCounts } from '@/api/dashboard'

function mockEnvelope(data: unknown) {
  return { status: 200, data: { success: true, data } } as Awaited<
    ReturnType<typeof ApiService.requestRaw>
  >
}

function payload(patch: Record<string, unknown> = {}) {
  return {
    defect_stats: { pending_review: 4 },
    record_stats: { pending_review: 3, pending_recheck: 2 },
    scene: 'all',
    ...patch,
  }
}

describe('V5 首页审核待办 API 适配', () => {
  beforeEach(() => vi.restoreAllMocks())

  it.each(['all', 'running', 'final'] as const)('请求 %s 场景并透传真实精确计数', async (scene) => {
    const request = vi
      .spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce(mockEnvelope(payload({ scene })))

    const result = await getReviewTodoCounts(scene)

    expect(request).toHaveBeenCalledWith(
      expect.objectContaining({
        url: '/api/v1/dashboard/review-todo-stats',
        params: { scene },
      }),
    )
    expect(result).toEqual({
      success: true,
      data: {
        pending_record_review: 3,
        pending_record_recheck: 2,
        pending_manual_defect_review: 4,
        scene,
      },
    })
  })

  it('保留有效 0 和无权限时的 null，不伪造计数', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(
      mockEnvelope(
        payload({
          defect_stats: { clinical_appeals: null, pending_review: null, urged: null },
          record_stats: { pending_review: 0, pending_recheck: 0, total: 18 },
        }),
      ),
    )

    const result = await getReviewTodoCounts()

    expect(result.data).toMatchObject({
      pending_record_review: 0,
      pending_record_recheck: 0,
      pending_manual_defect_review: null,
    })
  })

  it('审核来源未接通时保留明确null，同时保留人工缺陷计数', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(
      mockEnvelope(
        payload({
          scene: 'outpatient_emergency',
          record_stats: {
            pending_review: null,
            pending_recheck: null,
            total: 18,
            unavailable_reason: 'review_source_unavailable',
          },
        }),
      ),
    )
    expect(await getReviewTodoCounts('outpatient_emergency')).toMatchObject({
      success: true,
      data: {
        pending_record_review: null,
        pending_record_recheck: null,
        pending_manual_defect_review: 4,
        record_unavailable_reason: 'review_source_unavailable',
        scene: 'outpatient_emergency',
      },
    })
  })

  it.each([
    ['负数', { record_stats: { pending_review: -1, pending_recheck: 0, total: 18 } }],
    ['小数', { record_stats: { pending_review: 1.5, pending_recheck: 0, total: 18 } }],
    ['未知无原因', { record_stats: { pending_review: null, pending_recheck: null, total: 18 } }],
    [
      '不可用仍有计数',
      {
        record_stats: {
          pending_review: 0,
          pending_recheck: 0,
          unavailable_reason: 'review_source_unavailable',
        },
      },
    ],
    [
      '不可用混合计数',
      {
        record_stats: {
          pending_review: null,
          pending_recheck: 0,
          unavailable_reason: 'review_source_unavailable',
        },
      },
    ],
    ['字符串', { defect_stats: { clinical_appeals: null, pending_review: '4', urged: null } }],
  ])('非法计数按失败处理：%s', async (_label, patch) => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(mockEnvelope(payload(patch)))

    const result = await getReviewTodoCounts()

    expect(result).toEqual({ success: false, message: '审核待办数据格式异常' })
  })

  it.each([
    ['缺少 record_stats', { record_stats: undefined }],
    ['缺少 defect_stats', { defect_stats: undefined }],
    ['服务端返回非请求范围', { scene: 'running' }],
  ])('结构或范围异常按失败处理：%s', async (_label, patch) => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(mockEnvelope(payload(patch)))

    const result = await getReviewTodoCounts()

    expect(result).toEqual({ success: false, message: '审核待办数据格式异常' })
  })

  it('请求失败不返回降级计数', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockRejectedValueOnce(new Error('503'))

    const result = await getReviewTodoCounts()

    expect(result.success).toBe(false)
    expect(result.data).toBeUndefined()
  })
})
