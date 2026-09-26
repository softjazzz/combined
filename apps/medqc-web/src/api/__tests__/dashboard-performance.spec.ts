import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { getPerformanceRanking, normalizePerformanceData } from '@/api/dashboard'

const validPayload = {
  period: 'last_week',
  period_label: '上周',
  range: { start: '2026-09-14T00:00:00+08:00', end: '2026-09-21T00:00:00+08:00' },
  scene: 'all',
  defect_ranking: [
    { user_id: 'u1', name: '甲', count: 5, approved_count: 3, rejected_count: 1, rank: 1 },
    { user_id: 7, name: null, count: 5, approved_count: 0, rejected_count: 0, rank: 1 },
  ],
  record_ranking: [],
  unavailable_reason: null,
}

function mockEnvelope(data: unknown) {
  return { status: 200, data: { success: true, data } } as Awaited<ReturnType<typeof ApiService.requestRaw>>
}

describe('工作表现排名 API 合同', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('按合同透传周期与场景参数并规范化 DTO', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(mockEnvelope(validPayload))
    const result = await getPerformanceRanking('last_week', 'all')
    expect(request).toHaveBeenCalledWith(expect.objectContaining({
      url: '/api/v1/dashboard/performance',
      params: { period: 'last_week', scene: 'all' },
    }))
    expect(result.success).toBe(true)
    expect(result.data?.defect_ranking?.[1]).toEqual({
      user_id: '7', name: null, count: 5, approved_count: 0, rejected_count: 0, rank: 1,
    })
    expect(result.data?.record_ranking).toEqual([])
  })

  it('场景不可归属时两个排名为 null 并保留原因', () => {
    const data = normalizePerformanceData({
      ...validPayload,
      scene: 'running',
      defect_ranking: null,
      record_ranking: null,
      unavailable_reason: 'scene_not_attributable',
    })
    expect(data).toMatchObject({ defect_ranking: null, record_ranking: null, unavailable_reason: 'scene_not_attributable' })
  })

  it.each([
    ['排名为 null 却无原因', { defect_ranking: null }],
    ['计数缺失', { record_ranking: [{ user_id: 'u1', name: 'a', count: 2, initial_count: 1, rank: 1 }] }],
    ['计数为负', { defect_ranking: [{ user_id: 'u1', name: 'a', count: -1, approved_count: 0, rejected_count: 0, rank: 1 }] }],
    ['旧版示例结构（无 user_id）', { defect_ranking: [{ name: '张三', count: 12, rank: 1 }] }],
    ['缺少统计区间', { range: undefined }],
    ['未知不可用原因', { unavailable_reason: 'other' }],
  ])('非法响应按失败处理：%s', (_label, patch) => {
    expect(normalizePerformanceData({ ...validPayload, ...patch })).toBeNull()
  })

  it('响应格式不符合合同时返回失败而不是空排名', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(mockEnvelope({ defect_ranking: [], record_ranking: [] }))
    const result = await getPerformanceRanking('this_week', 'all')
    expect(result).toEqual({ success: false, message: '排名数据格式异常' })
  })

  it('请求异常时返回失败', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockRejectedValueOnce(new Error('503'))
    const result = await getPerformanceRanking('this_week', 'all')
    expect(result.success).toBe(false)
    expect(result.data).toBeUndefined()
  })
})
