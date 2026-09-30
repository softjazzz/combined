import { beforeEach, describe, expect, it, vi } from 'vitest'

const requestRaw = vi.fn()
vi.mock('@/services/apiService', () => ({
  ApiService: { requestRaw: (...args: unknown[]) => requestRaw(...args) },
}))

import {
  deleteWorkspaceDraftChecked,
  publishWorkspaceDraftsBatch,
} from '@/services/custom-rule-workspace-service'

const items = [
  { draft_id: 'd1', expected_updated_at: '2026-09-30T01:00:00', validation_id: 'v1' },
  { draft_id: 'd2', expected_updated_at: '2026-09-30T02:00:00', validation_id: 'v2' },
]
const published = (id: string) => ({ draft_id: id, rule_code: `LXE-${id}`, published_rule_id: `r-${id}`, status: 'published' })

describe('自定义草稿删除与批量上线服务', () => {
  beforeEach(() => requestRaw.mockReset())

  it('删除携带草稿版本并校验回执ID', async () => {
    requestRaw.mockResolvedValue({ data: { success: true, data: { id: 'd1' } } })
    expect(await deleteWorkspaceDraftChecked('d1', '2026-09-30T01:00:00')).toEqual({
      success: true, resultUnknown: false, conflict: false,
    })
    expect(requestRaw).toHaveBeenCalledWith({
      method: 'DELETE', url: '/api/v1/custom-qc/workspace/drafts/d1',
      params: { expected_updated_at: '2026-09-30T01:00:00' },
    })
    requestRaw.mockResolvedValue({ data: { success: true, data: { id: 'other' } } })
    expect(await deleteWorkspaceDraftChecked('d1', 'x')).toMatchObject({ success: false, resultUnknown: true })
  })

  it('删除 409 为确定冲突，网络错误为结果未知', async () => {
    requestRaw.mockRejectedValueOnce({ response: { status: 409, data: { detail: '已上线草稿不能删除' } } })
    expect(await deleteWorkspaceDraftChecked('d1', 'x')).toEqual({
      success: false, resultUnknown: false, conflict: true, message: '已上线草稿不能删除',
    })
    requestRaw.mockRejectedValueOnce(new Error('Network Error'))
    expect(await deleteWorkspaceDraftChecked('d1', 'x')).toMatchObject({ success: false, resultUnknown: true, conflict: false })
  })

  it('批量上线要求回执逐项覆盖所选草稿且均已发布', async () => {
    requestRaw.mockResolvedValue({ data: { success: true, data: { items: [published('d2'), published('d1')] } } })
    const ok = await publishWorkspaceDraftsBatch(items)
    expect(ok.success).toBe(true)
    expect(requestRaw).toHaveBeenCalledWith({
      method: 'POST', url: '/api/v1/custom-qc/workspace/drafts/publish-batch', data: { items },
    })
    for (const bad of [
      [published('d1')],
      [published('d1'), published('d1')],
      [published('d1'), { ...published('d2'), status: 'draft' }],
      [published('d1'), published('d3')],
    ]) {
      requestRaw.mockResolvedValue({ data: { success: true, data: { items: bad } } })
      expect(await publishWorkspaceDraftsBatch(items)).toMatchObject({ success: false, resultUnknown: true })
    }
  })

  it('批量上线 409/422 为整批确定拒绝，5xx 为结果未知', async () => {
    requestRaw.mockRejectedValueOnce({ response: { status: 409, data: { detail: '草稿 d2：测试证明已更新，请刷新后重试' } } })
    expect(await publishWorkspaceDraftsBatch(items)).toEqual({
      success: false, resultUnknown: false, conflict: true, message: '草稿 d2：测试证明已更新，请刷新后重试',
    })
    requestRaw.mockRejectedValueOnce({ response: { status: 422, data: { detail: '批量上线列表存在重复草稿' } } })
    expect(await publishWorkspaceDraftsBatch(items)).toMatchObject({ success: false, resultUnknown: false, conflict: false })
    requestRaw.mockRejectedValueOnce({ response: { status: 502, data: {} } })
    expect(await publishWorkspaceDraftsBatch(items)).toMatchObject({ success: false, resultUnknown: true })
  })
})
