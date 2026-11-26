/**
 * LLM配置服务
 * 处理大模型API配置的持久化存储和管理
 * 通过后端API访问数据，避免CORS问题
 */

import { API_REQUEST_TIMEOUT_MS } from '@/config/requestTimeouts'
import { apiClient } from '@/services/apiService'

// API基础URL配置：优先用环境变量；若未设置则使用相对路径，交由 Vite 代理转发
// 使用 nullish 合并，允许将环境变量显式设置为空字符串以启用相对路径
const API_BASE_URL: string = (import.meta as any)?.env?.VITE_API_BASE_URL ?? ''
const LLM_API_PREFIX = '/api/v1/llm'

// 类型定义
export interface LLMProvider {
  id: string
  provider_code: string
  provider_name: string
  base_endpoint: string
  request_format: 'openai' | 'baidu' | 'custom'
  requires_api_key: boolean
  description: string
  features: string[]
  is_active: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface LLMModel {
  id: string
  provider_id?: string
  provider?: string
  model_code: string
  model_name: string
  description?: string
  context_length?: number
  pricing_tier?: string
  capabilities?: string[]
  parameters?: Record<string, unknown>
  is_default?: boolean
  is_active?: boolean
  sort_order?: number
  created_at?: string
  updated_at?: string
  is_custom?: boolean
}

export interface LLMLocalModel extends LLMModel {
  configuration_ready: boolean
  unavailable_reason: '' | 'provider_not_enabled' | 'model_configuration_incomplete'
}

export interface LLMLocalProvider {
  provider_code: string
  provider_name: string
  enabled: boolean
  models: LLMLocalModel[]
}

export interface UserLLMConfig {
  id: string
  user_id: string | null
  config_name: string
  provider_id: string
  model_id: string
  api_key_encrypted: string | null
  api_key_decrypted?: string | null
  custom_endpoint: string | null
  custom_parameters: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at: string
  // 关联数据
  provider?: LLMProvider
  model?: LLMModel
}

export interface LLMConfigInput {
  config_name: string
  // 二选一：按ID或按code提交
  provider_id?: string
  model_id?: string
  provider_code?: string
  model_code?: string
  api_key?: string
  custom_endpoint?: string
  custom_parameters?: Record<string, unknown>
  execution_concurrency?: LLMExecutionConcurrency
  is_active?: boolean
}

export interface LLMExecutionConcurrency {
  max_parallel_records: number
  family_max_concurrency: number
  http_max_concurrency: number
}

export type LLMTaskRole = 'fact_extraction' | 'judgment_analysis' | 'specialty_verification'
export type LLMTaskRoleModels = Record<LLMTaskRole, { provider_code: string; model_code: string } | null>

export interface LLMConnectionTestInput {
  provider_code: string
  model_code: string
  custom_parameters?: Record<string, unknown>
}

export interface LLMConfigSummary {
  provider_code: string
  model_code: string
  custom_parameters: {
    temperature: number
    top_p: number
    max_tokens: number
    enable_thinking?: boolean
    thinking_budget?: number | null
    reasoning_effort?: string
    task_role_models?: LLMTaskRoleModels
    [key: string]: unknown
  }
  execution_concurrency?: LLMExecutionConcurrency
  source: string
  readonly: boolean
}

export interface LLMRequestOptions {
  signal?: AbortSignal
}

class LLMConfigService {
  /**
   * 获取所有可用的LLM提供商
   */
  async getProviders(options?: LLMRequestOptions): Promise<LLMProvider[]> {
    const controller = new AbortController()
    let timedOut = false
    const onExternalAbort = () => controller.abort(options?.signal?.reason)
    if (options?.signal) {
      if (options.signal.aborted) {
        controller.abort(options.signal.reason)
      } else {
        options.signal.addEventListener('abort', onExternalAbort, { once: true })
      }
    }
    const timeoutId = setTimeout(() => {
      timedOut = true
      controller.abort()
    }, API_REQUEST_TIMEOUT_MS)

    try {
      console.log('🌐 发起请求:', `${API_BASE_URL}${LLM_API_PREFIX}/providers`)

      const response = await apiClient.get(`${LLM_API_PREFIX}/providers`, {
        signal: controller.signal,
      })

      console.log('📡 响应状态:', response.status, response.statusText)
      const result = response.data
      console.log('✅ 获取提供商成功:', result.data?.length || 0, '个')
      return result.data || []
    } catch (error) {
      if (options?.signal?.aborted) {
        throw error
      }
      console.error('❌ 获取LLM提供商失败:', error)
      if (timedOut || (error instanceof Error && error.name === 'AbortError')) {
        throw new Error('请求超时，请检查网络连接')
      }
      throw new Error(
        `获取LLM提供商失败: ${error instanceof Error ? error.message : String(error)}`,
      )
    } finally {
      clearTimeout(timeoutId)
      options?.signal?.removeEventListener('abort', onExternalAbort)
    }
  }

  /**
   * 获取指定提供商的所有模型
   */
  async getModelsByProvider(providerId: string, options?: LLMRequestOptions): Promise<LLMModel[]> {
    try {
      const response = await apiClient.get(`${LLM_API_PREFIX}/models`, {
        params: { provider_id: providerId },
        ...(options?.signal ? { signal: options.signal } : {}),
      })
      const result = response.data
      return result.data || []
    } catch (error) {
      if (options?.signal?.aborted) {
        throw error
      }
      console.error('获取LLM模型失败:', error)
      throw new Error(`获取LLM模型失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  async getLocalModelOptions(options?: LLMRequestOptions): Promise<LLMLocalProvider[]> {
    const response = options?.signal
      ? await apiClient.get(`${LLM_API_PREFIX}/local-options`, { signal: options.signal })
      : await apiClient.get(`${LLM_API_PREFIX}/local-options`)
    return response.data?.data || []
  }

  async getDefaultSummary(options?: LLMRequestOptions): Promise<LLMConfigSummary> {
    const response = options?.signal
      ? await apiClient.get(`${LLM_API_PREFIX}/configs/default/summary`, { signal: options.signal })
      : await apiClient.get(`${LLM_API_PREFIX}/configs/default/summary`)
    return response.data?.data as LLMConfigSummary
  }

  async resetDefaultSummary(options?: LLMRequestOptions): Promise<LLMConfigSummary> {
    const response = options?.signal
      ? await apiClient.post(`${LLM_API_PREFIX}/configs/default/reset`, undefined, {
          signal: options.signal,
        })
      : await apiClient.post(`${LLM_API_PREFIX}/configs/default/reset`)
    return response.data?.data as LLMConfigSummary
  }

  async addCustomModel(
    providerCode: string,
    modelCode: string,
    modelName?: string,
    options?: LLMRequestOptions,
  ): Promise<void> {
    const payload = {
      provider_code: providerCode,
      model_code: modelCode,
      model_name: modelName || modelCode,
    }
    if (options?.signal) {
      await apiClient.post(`${LLM_API_PREFIX}/models/custom`, payload, { signal: options.signal })
    } else {
      await apiClient.post(`${LLM_API_PREFIX}/models/custom`, payload)
    }
  }

  async deleteCustomModel(
    providerCode: string,
    modelCode: string,
    options?: LLMRequestOptions,
  ): Promise<void> {
    await apiClient.delete(`${LLM_API_PREFIX}/models/custom`, {
      params: {
        provider_code: providerCode,
        model_code: modelCode,
      },
      ...(options?.signal ? { signal: options.signal } : {}),
    })
  }

  /**
   * 获取用户的LLM配置列表
   */
  async getUserConfigs(userId?: string, options?: LLMRequestOptions): Promise<UserLLMConfig[]> {
    try {
      const params = new URLSearchParams()
      if (userId) {
        params.append('user_id', userId)
      }

      const response = await apiClient.get(`${LLM_API_PREFIX}/configs`, {
        params: params.toString() ? Object.fromEntries(params.entries()) : undefined,
        ...(options?.signal ? { signal: options.signal } : {}),
      })
      const result = response.data
      const raw = result.data
      const data = (Array.isArray(raw) ? raw : raw?.items || []) as UserLLMConfig[]

      return data.map((config) => ({
        ...config,
        api_key_decrypted: null,
      }))
    } catch (error) {
      if (options?.signal?.aborted) {
        throw error
      }
      console.error('获取用户LLM配置失败:', error)
      throw new Error(
        `获取用户LLM配置失败: ${error instanceof Error ? error.message : String(error)}`,
      )
    }
  }

  /**
   * 获取指定名称的配置
   */
  async getConfigByName(
    configName: string,
    userId?: string,
    options?: LLMRequestOptions,
  ): Promise<UserLLMConfig | null> {
    try {
      const params = new URLSearchParams({ config_name: configName })
      if (userId) {
        params.append('user_id', userId)
      }

      const response = await apiClient.get(
        `${LLM_API_PREFIX}/configs/${encodeURIComponent(configName)}`,
        {
          params: Object.fromEntries(params.entries()),
          validateStatus: (status) => status === 404 || (status >= 200 && status < 300),
          ...(options?.signal ? { signal: options.signal } : {}),
        },
      )
      if (response.status === 404) {
        return null
      }

      const result = response.data
      return (result.data as UserLLMConfig | null) ?? null
    } catch (error) {
      if (options?.signal?.aborted) {
        throw error
      }
      console.error('获取LLM配置失败:', error)
      throw new Error(`获取LLM配置失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 保存或更新LLM配置
   */
  async saveConfig(
    config: LLMConfigInput,
    userIdOrOptions?: string | LLMRequestOptions,
    options?: LLMRequestOptions,
  ): Promise<UserLLMConfig> {
    const resolvedUserId = typeof userIdOrOptions === 'string' ? userIdOrOptions : undefined
    const resolvedOptions =
      typeof userIdOrOptions === 'object' && userIdOrOptions !== null ? userIdOrOptions : options
    try {
      // 准备数据（支持按ID或按code提交，后端负责解析）
      const configData: Record<string, unknown> = {
        user_id: resolvedUserId || null,
        config_name: config.config_name,
        // 这两组字段按需传递，后端会优先使用 *_id，否则按 *_code 解析
        ...(config.provider_id ? { provider_id: config.provider_id } : {}),
        ...(config.model_id ? { model_id: config.model_id } : {}),
        ...(config.provider_code ? { provider_code: config.provider_code } : {}),
        ...(config.model_code ? { model_code: config.model_code } : {}),
        custom_endpoint: config.custom_endpoint || null,
        custom_parameters: config.custom_parameters || {},
        ...(config.execution_concurrency
          ? { execution_concurrency: config.execution_concurrency }
          : {}),
        is_active: config.is_active !== false,
        updated_at: new Date().toISOString(),
      }

      // 由后端进行加密存储：直接发送明文 api_key（后端会写入 api_key_encrypted）
      if (config.api_key) {
        configData.api_key = config.api_key
      }

      // 通过后端API保存配置
      const response = resolvedOptions?.signal
        ? await apiClient.post(`${LLM_API_PREFIX}/configs`, configData, {
            signal: resolvedOptions.signal,
          })
        : await apiClient.post(`${LLM_API_PREFIX}/configs`, configData)
      const result = response.data
      return result.data
    } catch (error) {
      if (resolvedOptions?.signal?.aborted) {
        throw error
      }
      console.error('保存LLM配置失败:', error)
      throw new Error(`保存LLM配置失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 使用后端 env 中的真实 endpoint/key 测试连接
   */
  async testConfig(
    input: LLMConnectionTestInput,
    options?: LLMRequestOptions,
  ): Promise<{
    provider_code: string
    model: string
    api_endpoint: string
    content_preview: string
    stats: Record<string, unknown>
  }> {
    try {
      const response = options?.signal
        ? await apiClient.post(`${LLM_API_PREFIX}/test`, input, { signal: options.signal })
        : await apiClient.post(`${LLM_API_PREFIX}/test`, input)
      const result = response.data
      if (!result.success) {
        throw new Error(result.error || result.message || `HTTP ${response.status}`)
      }
      return result.data
    } catch (error: any) {
      if (options?.signal?.aborted) {
        throw error
      }
      const detail =
        error?.response?.data?.detail ||
        error?.response?.data?.error ||
        error?.response?.data?.message ||
        error?.message ||
        '连接测试失败'
      throw new Error(String(detail))
    }
  }

  /**
   * 用户级：获取 LLM 解析优化偏好（指针模式/摘要长度）
   */
  async getUserPointerPrefs(
    userId?: string,
  ): Promise<{ pointerMode: boolean; summaryMaxLength: number } | null> {
    const cfg = await this.getConfigByName('llm_pointer_prefs', userId)
    if (!cfg) return null
    const cp = cfg.custom_parameters || {}
    return {
      pointerMode: !!cp.pointer_mode,
      summaryMaxLength: Number(cp.summary_max_len ?? 80) || 0,
    }
  }

  /**
   * 用户级：保存 LLM 解析优化偏好（指针模式/摘要长度）
   */
  async saveUserPointerPrefs(
    prefs: { pointerMode: boolean; summaryMaxLength: number },
    userId?: string,
  ) {
    const payload: {
      user_id: string | null
      config_name: string
      custom_parameters: {
        pointer_mode: boolean
        summary_max_len: number
        version: number
      }
      is_active: boolean
      updated_at: string
      created_at?: string
    } = {
      user_id: userId || null,
      config_name: 'llm_pointer_prefs',
      custom_parameters: {
        pointer_mode: !!prefs.pointerMode,
        summary_max_len: Number(prefs.summaryMaxLength) || 0,
        version: 1,
      },
      is_active: true,
      updated_at: new Date().toISOString(),
    }
    const response = await apiClient.post(`${LLM_API_PREFIX}/configs`, payload)
    const result = response.data
    if (!result?.success) {
      throw new Error(result?.error || result?.message || '保存用户偏好失败')
    }
    return result?.data?.id || null
  }

  /**
   * 删除LLM配置
   */
  async deleteConfig(configId: string): Promise<void> {
    throw new Error(`删除LLM配置失败: 当前版本未开放删除接口（configId=${configId}）`)
  }

  /**
   * 设置默认配置
   */
  async setDefaultConfig(configId: string, userId?: string): Promise<void> {
    void userId
    throw new Error(`设置默认配置失败: 当前版本未开放该接口（configId=${configId}）`)
  }

  /**
   * 获取默认配置
   */
  async getDefaultConfig(userId?: string): Promise<UserLLMConfig | null> {
    return await this.getConfigByName('default', userId)
  }
}

export const llmConfigService = new LLMConfigService()
