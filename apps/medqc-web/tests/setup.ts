import { afterEach, vi } from 'vitest'

// 全局 Mock fetch 以防止 LLM 单元测试发真实网络请求
global.fetch = vi.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({
      id: "mock-id",
      object: "chat.completion",
      created: 1234567890,
      model: "mock-model",
      choices: [
        {
          index: 0,
          message: {
            role: "assistant",
            content: "mock generated response content"
          },
          finish_reason: "stop"
        }
      ],
      usage: {
        prompt_tokens: 10,
        completion_tokens: 10,
        total_tokens: 20
      }
    }),
    text: () => Promise.resolve('mock response')
  })
) as unknown as typeof fetch

afterEach(() => {
  vi.clearAllMocks()
  vi.resetModules()
  vi.useRealTimers()
})
