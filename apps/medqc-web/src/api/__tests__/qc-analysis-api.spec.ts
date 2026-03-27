import { beforeEach, describe, expect, it, vi } from 'vitest'

const postRaw = vi.fn()

vi.mock('@/services/apiService', () => ({
  ApiService: {
    postRaw,
  },
}))

describe('qc-analysis-api', () => {
  beforeEach(() => {
    postRaw.mockReset()
  })

  it('routes health checks through backend proxy without browser-side secrets', async () => {
    postRaw.mockResolvedValue({
      data: {
        choices: [{ message: { content: '连接正常' } }],
      },
    })

    const { healthCheck } = await import('../qc-analysis-api')
    const result = await healthCheck()

    expect(result.status).toBe('ok')
    expect(postRaw).toHaveBeenCalledTimes(1)
    expect(postRaw).toHaveBeenCalledWith(
      '/api/v1/llm/parse-text',
      expect.objectContaining({
        requestBody: expect.objectContaining({
          model: 'deepseek-v3',
        }),
      }),
    )
    const payload = postRaw.mock.calls[0]?.[1] as Record<string, unknown>
    expect(payload).not.toHaveProperty('apiConfig')
  })
})
