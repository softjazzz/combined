import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { getReviewTodoCounts } from '@/api/dashboard'

function mockEnvelope(data: unknown) {
  return { status: 200, data: { success: true, data } } as Awaited<ReturnType<typeof ApiService.requestRaw>>
}

function payload(patch: Record<string, unknown> = {}) {
  return {
    task_stats: { countdown: null, in_progress: null, not_started: null },
    defect_stats: { clinical_appeals: null, pending_review: 4, urged: null },
    record_stats: { pending_review: 3, pending_recheck: 2, total: 18 },
    scene: 'all',
    ...patch,
  }
}

describe('V5 首页审核待办 API 适配', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('只请求 all 范围并透传真实精确计数', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(mockEnvelope(payload()))

    const result = await getReviewTodoCounts()

    expect(request).toHaveBeenCalledWith(expect.objectContaining({
      url: '/api/v1/dashboard/todo-stats',
      params: { scene: 'all' },
    }))
    expect(result).toEqual({
      success: true,
      data: {
        pending_record_review: 3,
        pending_record_recheck: 2,
        pending_manual_defect_review: 4,
        scene: 'all',
      },
    })
  })

  it('保留有效 0 和无权限时的 null，不伪造计数', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(mockEnvelope(payload({
      defect_stats: { clinical_appeals: null, pending_review: null, urged: null },
      record_stats: { pending_review: 0, pending_recheck: 0, total: 18 },
    })))

    const result = await getReviewTodoCounts()

    expect(result.data).toMatchObject({
      pending_record_review: 0,
      pending_record_recheck: 0,
      pending_manual_defect_review: null,
    })
  })

  it.each([
    ['负数', { record_stats: { pending_review: -1, pending_recheck: 0, total: 18 } }],
    ['小数', { record_stats: { pending_review: 1.5, pending_recheck: 0, total: 18 } }],
    ['字符串', { defect_stats: { clinical_appeals: null, pending_review: '4', urged: null } }],
  ])('非法计数按失败处理：%s', async (_label, patch) => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(mockEnvelope(payload(patch)))

    const result = await getReviewTodoCounts()

    expect(result).toEqual({ success: false, message: '审核待办数据格式异常' })
  })

  it.each([
    ['缺少 record_stats', { record_stats: undefined }],
    ['缺少 defect_stats', { defect_stats: undefined }],
    ['服务端返回非 all 范围', { scene: 'running' }],
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
