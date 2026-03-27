import { beforeEach, describe, expect, it, vi } from 'vitest'

import { batchEvaluateQC, getQCHistoryList, testQCRule } from '@/api/qc'

function mockFetchResponse(payload: unknown, ok = true, status = 200, statusText = 'OK') {
  vi.mocked(global.fetch).mockResolvedValueOnce({
    ok,
    status,
    statusText,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response)
}

describe('qc api envelope compatibility', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('testQCRule 兼容 success/data 响应壳', async () => {
    localStorage.setItem('medqc_access_token', 'tk-qc')
    mockFetchResponse({
      success: true,
      data: { rule_id: 'r1', is_compliant: true },
      trace_id: 'trace-qc-1',
    })

    const result = await testQCRule({ rule_id: 'r1', medical_text: 'abc' })

    expect(result.success).toBe(true)
    expect(result.data?.rule_id).toBe('r1')
    expect(vi.mocked(global.fetch).mock.calls[0]?.[1]).toMatchObject({
      headers: expect.objectContaining({
        Authorization: 'Bearer tk-qc',
      }),
    })
  })

  it('batchEvaluateQC 兼容非响应壳结构', async () => {
    mockFetchResponse({
      document_id: 'doc-1',
      evaluation_summary: { compliance_rate: 88 },
      evaluation_results: [],
    })

    const result = await batchEvaluateQC({
      document_id: 'doc-1',
      document_content: 'x',
      document_type: 'admission',
      rule_ids: ['r1'],
      prompt_mode: 'plan_a',
    })

    expect(result.success).toBe(true)
    expect(result.data?.document_id).toBe('doc-1')
    expect(result.data?.evaluation_summary.compliance_rate).toBe(88)
  })

  it('history 接口在 success=false 响应壳下返回标准失败结构', async () => {
    mockFetchResponse({
      success: false,
      error: 'history unavailable',
      code: 'HISTORY_DOWN',
      trace_id: 'trace-qc-2',
    })

    const result = await getQCHistoryList({ page: 1, page_size: 10 })

    expect(result.success).toBe(false)
    expect(result.message).toBe('history unavailable')
  })
})

