import { beforeEach, describe, expect, it, vi } from 'vitest'

const { post } = vi.hoisted(() => ({
  post: vi.fn(),
}))

vi.mock('@/services/apiService', () => ({
  apiClient: {
    post,
  },
}))

import { llmConfigService } from '@/services/llmConfigService'

describe('llmConfigService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    post.mockResolvedValue({
      data: {
        data: {
          id: 'cfg-default',
          config_name: 'default',
        },
      },
    })
  })

  it('保存模型配置时独立提交三层执行并发', async () => {
    await llmConfigService.saveConfig({
      config_name: 'default',
      provider_code: 'alibaba',
      model_code: 'qwen3.8-flash',
      custom_parameters: {
        temperature: 0.2,
        thinking_budget: 256,
      },
      execution_concurrency: {
        max_parallel_records: 16,
        family_max_concurrency: 4,
        http_max_concurrency: 40,
      },
    })

    expect(post).toHaveBeenCalledWith(
      '/api/v1/llm/configs',
      expect.objectContaining({
        custom_parameters: {
          temperature: 0.2,
          thinking_budget: 256,
        },
        execution_concurrency: {
          max_parallel_records: 16,
          family_max_concurrency: 4,
          http_max_concurrency: 40,
        },
      }),
    )
  })
})
