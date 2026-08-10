import { afterEach, describe, expect, it, vi } from 'vitest'

import { LLMService } from '@/services/llmService'

describe('LLMService 文件解析出口', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('废弃公开方法也只经后端代理，不直连模型厂商', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          data: { documents: [] },
          tokensUsed: 4,
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const service = new LLMService({
      apiEndpoint: 'https://provider-secret.example/v1/files',
      apiKey: 'sk-secret-browser-key',
      model: 'model-observe',
      pointerMode: false,
    })
    const result = await service.parseMedicalFile(
      new File(['record'], 'record.pdf', { type: 'application/pdf' }),
    )

    expect(result.success).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/api/parse-medical-file-public')
    expect(url).not.toContain('provider-secret.example')
    expect(init.headers).toBeUndefined()
  })
})
