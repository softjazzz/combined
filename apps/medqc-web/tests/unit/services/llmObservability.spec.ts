import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getLlmObservabilityOverview, getLlmRecordCallAttempts } from '@/services/llmObservability'

const authFetch = vi.fn()

vi.mock('@/utils/auth-fetch', () => ({
  authFetch: (...args: unknown[]) => authFetch(...args),
}))

describe('llmObservability service', () => {
  beforeEach(() => {
    authFetch.mockReset()
  })

  it('通过鉴权 GET 获取范围聚合并传递筛选参数', async () => {
    authFetch.mockResolvedValue(
      new Response(
        JSON.stringify({
          success: true,
          data: {
            range: {
              start_at: '2026-08-03T00:00:00Z',
              end_at: '2026-08-10T00:00:00Z',
              timezone: 'Asia/Shanghai',
            },
            kpis: {
              logical_calls: 8,
              http_attempts: 9,
              record_count: 2,
              input_tokens: 1200,
              output_tokens: 300,
              total_tokens: 1500,
              avg_latency_ms: 1200,
              p95_latency_ms: 1800,
              peak_concurrency: 3,
              retry_attempts: 1,
              successful_attempts: 8,
              failed_attempts: 1,
              unknown_usage_attempts: 0,
            },
            trends: [],
            models: [],
            safe_errors: [],
            records: { items: [], total: 0, page: 1, page_size: 20 },
          },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    const result = await getLlmObservabilityOverview({
      start_at: '2026-08-03T00:00:00Z',
      end_at: '2026-08-10T00:00:00Z',
      provider_code: 'openai-compatible',
      model: 'medical-model',
      business_scene: 'luxian_0609_qc',
      page: 2,
      page_size: 10,
    })

    const requestedUrl = String(authFetch.mock.calls[0][0])
    expect(requestedUrl).toContain('/api/v1/system/llm-observability/overview?')
    expect(requestedUrl).toContain('provider_code=openai-compatible')
    expect(requestedUrl).toContain('model=medical-model')
    expect(requestedUrl).toContain('business_scene=luxian_0609_qc')
    expect(requestedUrl).toContain('page=2')
    expect(result.kpis.logical_calls).toBe(8)
  })

  it('对病历哈希编码后读取 HTTP 尝试明细', async () => {
    authFetch.mockResolvedValue(
      new Response(
        JSON.stringify({
          success: true,
          data: {
            record_key_hash: 'hash/with+special',
            items: [],
            total: 0,
            page: 1,
            page_size: 20,
          },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    await getLlmRecordCallAttempts('hash/with+special', {
      start_at: '2026-08-03T00:00:00Z',
      end_at: '2026-08-10T00:00:00Z',
      provider_code: 'alibaba',
      model: 'qwen-plus',
      business_scene: 'luxian_0609_qc',
      page: 1,
      page_size: 20,
    })

    const requestedUrl = String(authFetch.mock.calls[0][0])
    expect(requestedUrl).toContain(
      '/api/v1/system/llm-observability/records/hash%2Fwith%2Bspecial/calls?',
    )
    expect(requestedUrl).toContain('start_at=2026-08-03T00%3A00%3A00Z')
    expect(requestedUrl).toContain('end_at=2026-08-10T00%3A00%3A00Z')
    expect(requestedUrl).toContain('provider_code=alibaba')
    expect(requestedUrl).toContain('model=qwen-plus')
    expect(requestedUrl).toContain('business_scene=luxian_0609_qc')
  })

  it('接口失败时只抛出稳定客户文案，不回显后端异常原文', async () => {
    authFetch.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'password=secret SQL SELECT * FROM patient' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await expect(getLlmObservabilityOverview()).rejects.toThrow('模型性能数据暂不可用')
  })

  it('拒绝未使用 success_response.data 合同的裸 200 响应', async () => {
    authFetch.mockResolvedValue(
      new Response(JSON.stringify({ kpis: { logical_calls: 999 } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await expect(getLlmObservabilityOverview()).rejects.toThrow('模型性能数据暂不可用')
  })
})
