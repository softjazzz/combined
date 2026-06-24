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

// jsdom 不提供 ResizeObserver，图表组件（如 vue-echarts）测试需要最小实现
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (!('ResizeObserver' in globalThis)) {
  ;(globalThis as unknown as { ResizeObserver: typeof MockResizeObserver }).ResizeObserver = MockResizeObserver
}

afterEach(() => {
  vi.clearAllMocks()
  vi.resetModules()
  vi.useRealTimers()
})
