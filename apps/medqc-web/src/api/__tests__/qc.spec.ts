import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiService } from '@/services/apiService'
import { batchEvaluateQC, getQCHistoryList, testQCRule } from '@/api/qc'

describe('qc api envelope compatibility', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('testQCRule 兼容 success/data 响应壳', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce({
      status: 200,
      data: {
        success: true,
        data: { rule_id: 'r1', is_compliant: true },
      },
    } as any)

    const result = await testQCRule({ rule_id: 'r1', medical_text: 'abc' })
    expect(result.success).toBe(true)
    expect(result.data?.rule_id).toBe('r1')
  })

  it('batchEvaluateQC 兼容非响应壳结构', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce({
      status: 200,
      data: {
        document_id: 'doc-1',
        evaluation_summary: { compliance_rate: 88 },
        evaluation_results: [],
      },
    } as any)

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

  it('history 接口在 requestRaw 抛错时返回标准失败结构', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockRejectedValueOnce({
      response: {
        status: 503,
        data: {
          success: false,
          error: 'history unavailable',
          code: 'HISTORY_DOWN',
        },
      },
      message: 'Network Error',
    })

    const result = await getQCHistoryList({ page: 1, page_size: 10 })
    expect(result.success).toBe(false)
    expect(result.message).toBe('history unavailable')
  })
})
