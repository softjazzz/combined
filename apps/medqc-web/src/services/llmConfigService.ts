/**
 * LLM配置服务
 * 处理大模型API配置的持久化存储和管理
 * 通过后端API访问数据，避免CORS问题
 */

import CryptoJS from 'crypto-js'

// API基础URL配置：优先用环境变量；若未设置则使用相对路径，交由 Vite 代理转发
// 使用 nullish 合并，允许将环境变量显式设置为空字符串以启用相对路径
const API_BASE_URL: string = (import.meta as any)?.env?.VITE_API_BASE_URL ?? ''

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
  provider_id: string
  model_code: string
  model_name: string
  description: string
  context_length: number
  pricing_tier: string
  capabilities: string[]
  parameters: any
  is_default: boolean
  is_active: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface UserLLMConfig {
  id: string
  user_id: string | null
  config_name: string
  provider_id: string
  model_id: string
  api_key_encrypted: string | null
  custom_endpoint: string | null
  custom_parameters: any
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
  custom_parameters?: any
  is_active?: boolean
}

class LLMConfigService {
  private readonly ENCRYPTION_KEY = 'medqc-llm-config-key-2024' // 在生产环境中应该使用环境变量

  /**
   * 加密API密钥
   */
  private encryptApiKey(apiKey: string): string {
    return CryptoJS.AES.encrypt(apiKey, this.ENCRYPTION_KEY).toString()
  }

  /**
   * 解密API密钥
   */
  private decryptApiKey(encryptedKey: string): string {
    try {
      // 首先尝试AES解密（原有逻辑）
      const bytes = CryptoJS.AES.decrypt(encryptedKey, this.ENCRYPTION_KEY)
      const decrypted = bytes.toString(CryptoJS.enc.Utf8)
      if (decrypted) {
        return decrypted
      }
    } catch (error) {
      console.warn('AES解密失败，尝试base64解码:', error)
    }

    try {
      // 回退到base64解码（兼容Python脚本保存的密钥）
      return atob(encryptedKey)
    } catch (error) {
      console.error('base64解码也失败:', error)
      return encryptedKey // 返回原始值作为最后的回退
    }
  }

  /**
   * 获取所有可用的LLM提供商
   */
  async getProviders(): Promise<LLMProvider[]> {
    try {
      console.log('🌐 发起请求:', `${API_BASE_URL}/api/llm/providers`)

      // 添加超时控制
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 15000) // 15秒超时

      const response = await fetch(`${API_BASE_URL}/api/llm/providers`, {
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
        }
      })

      clearTimeout(timeoutId)

      console.log('📡 响应状态:', response.status, response.statusText)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const result = await response.json()
      console.log('✅ 获取提供商成功:', result.data?.length || 0, '个')
      return result.data || []
    } catch (error) {
      console.error('❌ 获取LLM提供商失败:', error)
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('请求超时，请检查网络连接')
      }
      throw new Error(`获取LLM提供商失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 获取指定提供商的所有模型
   */
  async getModelsByProvider(providerId: string): Promise<LLMModel[]> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/llm/models?provider_id=${encodeURIComponent(providerId)}`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      const result = await response.json()
      return result.data || []
    } catch (error) {
      console.error('获取LLM模型失败:', error)
      throw new Error(`获取LLM模型失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 获取用户的LLM配置列表
   */
  async getUserConfigs(userId?: string): Promise<UserLLMConfig[]> {
    try {
      const params = new URLSearchParams()
      if (userId) {
        params.append('user_id', userId)
      }

      const url = `${API_BASE_URL}/api/llm/configs${params.toString() ? '?' + params.toString() : ''}`
      const response = await fetch(url)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const result = await response.json()
      const data = result.data || []

      // 解密API密钥
      return data.map((config: any) => ({
        ...config,
        api_key_decrypted: config.api_key_encrypted ? this.decryptApiKey(config.api_key_encrypted) : null
      }))
    } catch (error) {
      console.error('获取用户LLM配置失败:', error)
      throw new Error(`获取用户LLM配置失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 获取指定名称的配置
   */
  async getConfigByName(configName: string, userId?: string): Promise<UserLLMConfig | null> {
    try {
      const params = new URLSearchParams({ config_name: configName })
      if (userId) {
        params.append('user_id', userId)
      }

      const response = await fetch(`${API_BASE_URL}/api/llm/configs/${encodeURIComponent(configName)}?${params}`)
      if (!response.ok) {
        if (response.status === 404) {
          return null
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const result = await response.json()
      const data = result.data

      // 解密API密钥
      if (data && data.api_key_encrypted) {
        (data as any).api_key_decrypted = this.decryptApiKey(data.api_key_encrypted)
      }

      return data
    } catch (error) {
      console.error('获取LLM配置失败:', error)
      throw new Error(`获取LLM配置失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 保存或更新LLM配置
   */
  async saveConfig(config: LLMConfigInput, userId?: string): Promise<UserLLMConfig> {
    try {
      // 准备数据（支持按ID或按code提交，后端负责解析）
      const configData: any = {
        user_id: userId || null,
        config_name: config.config_name,
        // 这两组字段按需传递，后端会优先使用 *_id，否则按 *_code 解析
        ...(config.provider_id ? { provider_id: config.provider_id } : {}),
        ...(config.model_id ? { model_id: config.model_id } : {}),
        ...(config.provider_code ? { provider_code: config.provider_code } : {}),
        ...(config.model_code ? { model_code: config.model_code } : {}),
        custom_endpoint: config.custom_endpoint || null,
        custom_parameters: config.custom_parameters || {},
        is_active: config.is_active !== false,
        updated_at: new Date().toISOString()
      }

      // 由后端进行加密存储：直接发送明文 api_key（后端会写入 api_key_encrypted）
      if (config.api_key) {
        configData.api_key = config.api_key
      }

      // 通过后端API保存配置
      const response = await fetch(`${API_BASE_URL}/api/llm/configs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(configData)
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const result = await response.json()
      const savedConfig = result.data

      // 解密API密钥
      if (savedConfig && savedConfig.api_key_encrypted) {
        (savedConfig as any).api_key_decrypted = this.decryptApiKey(savedConfig.api_key_encrypted)
      }

      return savedConfig
    } catch (error) {
      console.error('保存LLM配置失败:', error)
      throw new Error(`保存LLM配置失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 用户级：获取 LLM 解析优化偏好（指针模式/摘要长度）
   */
  async getUserPointerPrefs(userId?: string): Promise<{ pointerMode: boolean; summaryMaxLength: number } | null> {
    const cfg = await this.getConfigByName('llm_pointer_prefs', userId)
    if (!cfg) return null
    const cp = cfg.custom_parameters || {}
    return {
      pointerMode: !!cp.pointer_mode,
      summaryMaxLength: Number(cp.summary_max_len ?? 80) || 0
    }
  }

  /**
   * 用户级：保存 LLM 解析优化偏好（指针模式/摘要长度）
   */
  async saveUserPointerPrefs(prefs: { pointerMode: boolean; summaryMaxLength: number }, userId?: string) {
    const existing = await this.getConfigByName('llm_pointer_prefs', userId)
    const payload = {
      user_id: userId || null,
      config_name: 'llm_pointer_prefs',
      custom_parameters: {
        pointer_mode: !!prefs.pointerMode,
        summary_max_len: Number(prefs.summaryMaxLength) || 0,
        version: 1
      },
      is_active: true,
      updated_at: new Date().toISOString()
    }

    if (existing) {
      const { error } = await supabase
        .from('user_llm_configs')
        .update(payload)
        .eq('id', existing.id)
      if (error) throw new Error(`保存用户偏好失败: ${error.message}`)
      return existing.id
    } else {
      payload.created_at = new Date().toISOString()
      const { data, error } = await supabase
        .from('user_llm_configs')
        .insert(payload)
        .select('id')
        .single()
      if (error) throw new Error(`保存用户偏好失败: ${error.message}`)
      return data?.id
    }
  }

  /**
   * 删除LLM配置
   */
  async deleteConfig(configId: string): Promise<void> {
    const { error } = await supabase
      .from('user_llm_configs')
      .delete()
      .eq('id', configId)

    if (error) {
      console.error('删除LLM配置失败:', error)
      throw new Error(`删除LLM配置失败: ${error.message}`)
    }
  }

  /**
   * 设置默认配置
   */
  async setDefaultConfig(configId: string, userId?: string): Promise<void> {
    // 首先将所有配置设为非默认
    const { error: updateError } = await supabase
      .from('user_llm_configs')
      .update({ config_name: 'custom' })
      .eq('config_name', 'default')
      .eq('user_id', userId || null)

    if (updateError) {
      console.error('更新默认配置失败:', updateError)
      throw new Error(`更新默认配置失败: ${updateError.message}`)
    }

    // 设置新的默认配置
    const { error } = await supabase
      .from('user_llm_configs')
      .update({ config_name: 'default' })
      .eq('id', configId)

    if (error) {
      console.error('设置默认配置失败:', error)
      throw new Error(`设置默认配置失败: ${error.message}`)
    }
  }

  /**
   * 获取默认配置
   */
  async getDefaultConfig(userId?: string): Promise<UserLLMConfig | null> {
    return await this.getConfigByName('default', userId)
  }
}

export const llmConfigService = new LLMConfigService()
