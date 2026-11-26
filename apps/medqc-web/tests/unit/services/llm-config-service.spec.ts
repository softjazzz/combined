import fs from 'node:fs'
import path from 'node:path'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, del } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  del: vi.fn(),
}))

vi.mock('@/services/apiService', () => ({
  apiClient: {
    get,
    post,
    delete: del,
  },
}))

import { llmConfigService } from '@/services/llmConfigService'

describe('llmConfigService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    get.mockResolvedValue({
      data: {
        data: [],
      },
    })
    post.mockResolvedValue({
      data: {
        data: {
          id: 'cfg-default',
          config_name: 'default',
        },
      },
    })
    del.mockResolvedValue({ data: { success: true } })
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

  it('所有核心接口均支持透传 AbortSignal 并移除死硬编码 AES 密钥逻辑', async () => {
    const controller = new AbortController()
    await llmConfigService.getDefaultSummary({ signal: controller.signal })
    expect(get).toHaveBeenCalledWith('/api/v1/llm/configs/default/summary', {
      signal: controller.signal,
    })

    await llmConfigService.getModelsByProvider('alibaba', { signal: controller.signal })
    expect(get).toHaveBeenCalledWith('/api/v1/llm/models', {
      params: { provider_id: 'alibaba' },
      signal: controller.signal,
    })

    await llmConfigService.getLocalModelOptions({ signal: controller.signal })
    expect(get).toHaveBeenCalledWith('/api/v1/llm/local-options', {
      signal: controller.signal,
    })

    await llmConfigService.saveConfig(
      { config_name: 'default', provider_code: 'alibaba', model_code: 'qwen3.8-flash' },
      { signal: controller.signal },
    )
    expect(post).toHaveBeenCalledWith(
      '/api/v1/llm/configs',
      expect.objectContaining({ provider_code: 'alibaba' }),
      { signal: controller.signal },
    )

    await llmConfigService.resetDefaultSummary({ signal: controller.signal })
    expect(post).toHaveBeenCalledWith('/api/v1/llm/configs/default/reset', undefined, {
      signal: controller.signal,
    })

    // 外部 signal 中止 getProviders 时联动中止内部 signal
    let forwardedSignal: AbortSignal | undefined
    get.mockImplementationOnce((_url: string, config?: { signal?: AbortSignal }) => {
      forwardedSignal = config?.signal
      return new Promise((_resolve, reject) => {
        config?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
      })
    })
    const providerAbort = new AbortController()
    const pending = llmConfigService.getProviders({ signal: providerAbort.signal })
    providerAbort.abort()
    await expect(pending).rejects.toThrow()
    expect(forwardedSignal?.aborted).toBe(true)

    const src = fs.readFileSync(
      path.resolve(__dirname, '../../../src/services/llmConfigService.ts'),
      'utf-8',
    )
    expect(src).not.toContain('medqc-llm-config-key-2024')
    expect(src).not.toContain('CryptoJS')
  })
})
