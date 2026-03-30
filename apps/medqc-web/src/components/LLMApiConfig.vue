<template>
  <div class="llm-api-config">
    <a-row
      :gutter="24"
      class="master-detail-layout"
    >
      <!-- 左侧：API 服务商列表 (Master) -->
      <a-col
        :xs="24"
        :md="8"
        :lg="6"
        class="master-panel"
      >
        <div class="provider-list">
          <h4 class="panel-title">
            API 服务商
          </h4>
          <div class="provider-items">
            <div
              v-for="config in availableConfigs"
              :key="config.name"
              class="provider-item"
              :class="{ 'provider-item--active': selectedConfig === config.name }"
              @click="handleProviderSelect(config.name)"
            >
              <div class="provider-item__content">
                <div class="provider-item__name">
                  {{ config.displayName }}
                </div>
                <div class="provider-item__desc">
                  {{ config.description }}
                </div>
                <div class="provider-item__features">
                  <a-tag
                    v-for="feature in config.features"
                    :key="feature"
                    size="small"
                    :color="getFeatureColor(feature)"
                  >
                    {{ feature }}
                  </a-tag>
                </div>
              </div>
            </div>
          </div>
        </div>
      </a-col>

      <!-- 右侧：配置详情 (Detail) -->
      <a-col
        :xs="24"
        :md="16"
        :lg="18"
        class="detail-panel"
      >
        <div
          v-if="currentConfig"
          class="config-detail"
        >
          <h4 class="panel-title">
            {{ currentConfig.displayName }} 配置
          </h4>

          <!-- 模型选择和API配置 -->
          <div
            v-if="availableModels.length > 1"
            class="config-section"
          >
            <div class="form-item">
              <label class="form-label">选择模型</label>
              <a-select
                v-model:value="selectedModel"
                style="width: 100%"
                placeholder="请选择模型"
                :dropdown-style="{ maxHeight: '500px' }"
                :option-label-prop="'label'"
                size="large"
                :loading="isLoadingModels"
                :disabled="isLoadingModels"
                @change="handleModelChange"
              >
                <a-select-option
                  v-for="model in availableModels"
                  :key="model.value"
                  :value="model.value"
                  :label="model.label"
                >
                  <span class="model-name">{{ model.label }}</span>
                  <a-tag
                    v-if="model.value === currentConfig.defaultModel"
                    color="blue"
                    size="small"
                    style="margin-left: 8px"
                  >
                    推荐
                  </a-tag>
                  <a-tag
                    v-if="model.qcStatus === 'passed'"
                    color="green"
                    size="small"
                    style="margin-left: 8px"
                  >
                    质控验证
                  </a-tag>
                </a-select-option>
              </a-select>
            </div>

            <!-- 简化的模型信息显示 -->
            <div
              v-if="currentModelInfo"
              class="model-summary"
            >
              <div class="model-summary-content">
                <span class="model-summary-name">{{ currentModelInfo.label }}</span>
                <a-tag
                  v-if="currentModelInfo.value === currentConfig.defaultModel"
                  color="blue"
                  size="small"
                >
                  推荐
                </a-tag>
                <a-tag
                  v-if="currentModelInfo.qcStatus === 'passed'"
                  color="green"
                  size="small"
                >
                  质控验证
                </a-tag>
                <span class="model-summary-desc">{{ currentModelInfo.description }}</span>
              </div>
            </div>
          </div>

          <!-- API密钥配置 -->
          <div class="config-section">
            <div class="form-item">
              <label class="form-label">API密钥配置</label>
              <a-input-password
                v-model:value="apiKey"
                placeholder="请输入API密钥"
                size="large"
                style="width: 100%"
                :visibility-toggle="true"
                @change="handleApiKeyChange"
              >
                <template #prefix>
                  <SearchOutlined style="color: #bfbfbf" />
                </template>
              </a-input-password>
            </div>
          </div>

          <!-- 自定义端点 -->
          <div
            v-if="selectedConfig === 'local'"
            class="config-section"
          >
            <div class="form-item">
              <label class="form-label">自定义端点</label>
              <a-input
                v-model:value="customEndpoint"
                placeholder="http://localhost:8001/v1/chat/completions"
                size="large"
                @change="handleEndpointChange"
              >
                <template #prefix>
                  <LinkOutlined />
                </template>
              </a-input>
            </div>
          </div>

          <!-- 高级参数配置 -->
          <div class="config-section advanced-params-section">
            <a-collapse
              v-model:active-key="advancedParamsExpanded"
              :bordered="false"
              class="advanced-params-collapse"
            >
              <a-collapse-panel
                key="1"
                class="advanced-params-panel"
              >
                <template #header>
                  <div class="advanced-params-header">
                    <SettingOutlined class="header-icon" />
                    <span class="header-title">高级参数</span>
                    <a-tag
                      color="blue"
                      size="small"
                      style="margin-left: 8px"
                    >
                      影响质控稳定性
                    </a-tag>
                  </div>
                </template>

                <div class="advanced-params-content">
                  <!-- Temperature 参数 -->
                  <div class="param-item">
                    <div class="param-header">
                      <label class="param-label">
                        Temperature（温度参数）
                        <a-tooltip
                          title="控制输出的随机性。值越低输出越确定，值越高输出越随机。推荐质控场景使用 0.1-0.3 以提高一致性。"
                        >
                          <QuestionCircleOutlined class="param-help-icon" />
                        </a-tooltip>
                      </label>
                      <div class="param-value-display">
                        <span class="current-value">{{ advancedParams.temperature }}</span>
                        <a-tag
                          v-if="
                            advancedParams.temperature >= 0.1 && advancedParams.temperature <= 0.3
                          "
                          color="green"
                          size="small"
                        >
                          推荐
                        </a-tag>
                        <a-tag
                          v-else
                          color="orange"
                          size="small"
                        >
                          非推荐
                        </a-tag>
                      </div>
                    </div>
                    <a-slider
                      v-model:value="advancedParams.temperature"
                      :min="0"
                      :max="2"
                      :step="0.1"
                      :marks="{ 0: '0', 0.2: '0.2 (推荐)', 1: '1', 2: '2' }"
                      :tooltip="{ formatter: (value: number) => `${value}` }"
                    />
                    <div class="param-description">
                      值越低输出越确定，值越高输出越随机。推荐质控场景使用 0.1-0.3。
                    </div>
                  </div>

                  <!-- Top P 参数 -->
                  <div class="param-item">
                    <div class="param-header">
                      <label class="param-label">
                        Top P（核采样参数）
                        <a-tooltip
                          title="控制输出多样性。与 temperature 配合使用，控制采样范围。通常保持 0.9 即可。"
                        >
                          <QuestionCircleOutlined class="param-help-icon" />
                        </a-tooltip>
                      </label>
                      <div class="param-value-display">
                        <span class="current-value">{{ advancedParams.top_p }}</span>
                      </div>
                    </div>
                    <a-slider
                      v-model:value="advancedParams.top_p"
                      :min="0"
                      :max="1"
                      :step="0.1"
                      :marks="{ 0: '0', 0.5: '0.5', 0.9: '0.9 (推荐)', 1: '1' }"
                      :tooltip="{ formatter: (value: number) => `${value}` }"
                    />
                    <div class="param-description">
                      控制输出多样性。与 temperature 配合使用，通常保持 0.9。
                    </div>
                  </div>

                  <!-- Max Tokens 参数 -->
                  <div class="param-item">
                    <div class="param-header">
                      <label class="param-label">
                        Max Tokens（最大输出长度）
                        <a-tooltip
                          title="控制 LLM 单次输出的最大 token 数量。质控场景推荐 4000-8000。"
                        >
                          <QuestionCircleOutlined class="param-help-icon" />
                        </a-tooltip>
                      </label>
                      <div class="param-value-display">
                        <span class="current-value">{{ advancedParams.max_tokens }}</span>
                      </div>
                    </div>
                    <a-input-number
                      v-model:value="advancedParams.max_tokens"
                      :min="1000"
                      :max="16000"
                      :step="1000"
                      style="width: 100%"
                    />
                    <div class="param-description">
                      控制单次输出的最大 token 数量。质控场景推荐 4000-8000。
                    </div>
                  </div>

                  <!-- 恢复默认值按钮 -->
                  <div class="param-actions">
                    <a-button
                      size="small"
                      @click="resetAdvancedParams"
                    >
                      <template #icon>
                        <ReloadOutlined />
                      </template>
                      恢复默认值
                    </a-button>
                  </div>
                </div>
              </a-collapse-panel>
            </a-collapse>
          </div>

          <!-- 配置状态 -->
          <div class="config-status">
            <a-alert
              :type="configStatus.type"
              :message="configStatus.message"
              show-icon
              :closable="false"
            />
          </div>

          <!-- 测试连接 -->
          <div class="config-actions">
            <a-space>
              <a-button
                :loading="testing"
                :disabled="!configStatus.valid"
                class="elevated-action"
                @click="testConnection"
              >
                <template #icon>
                  <ExperimentOutlined />
                </template>
                测试连接
              </a-button>
              <a-button
                :type="saveSuccess ? 'default' : 'primary'"
                :loading="saving"
                :disabled="!configStatus.valid || saving"
                :class="['elevated-action', { 'save-success': saveSuccess }]"
                @click="saveConfig"
              >
                <template #icon>
                  <SaveOutlined v-if="!saveSuccess" />
                  <span v-else>✅</span>
                </template>
                {{ saving ? '保存中...' : saveSuccess ? '保存成功' : '保存配置' }}
              </a-button>
            </a-space>
          </div>

          <!-- 测试结果 -->
          <div
            v-if="testResult"
            class="test-result"
          >
            <a-alert
              :type="testResult.success ? 'success' : 'error'"
              :message="testResult.message"
              :description="testResult.details"
              show-icon
              :closable="false"
            />
          </div>
        </div>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, reactive } from 'vue'
import { message } from 'ant-design-vue'
import {
  llmConfigService,
  type LLMProvider,
  type LLMModel,
  type UserLLMConfig,
} from '@/services/llmConfigService'
import {
  KeyOutlined,
  InfoCircleOutlined,
  LinkOutlined,
  ExperimentOutlined,
  SaveOutlined,
  SearchOutlined,
  EyeInvisibleOutlined,
  SettingOutlined,
  QuestionCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import {
  ENHANCED_LLM_API_CONFIGS,
  EnhancedLLMApiConfigManager,
  type EnhancedLLMApiConfig,
  type ModelOption,
} from '@/services/llmApiConfig'
import { LLMService } from '@/services/llmServiceNew'
import type { ParseResult } from '@/services/llmService'
import { resolveApiBaseUrl, extractApiData } from '@/utils/api-helpers'
import { authFetch } from '@/utils/auth-fetch'

interface RemoteProvider {
  id?: string
  provider_code?: string
  provider_name?: string
  [key: string]: unknown
}

interface RemoteModel {
  id?: string
  model_code?: string
  model_name?: string
  code?: string
  name?: string
  description?: string
  [key: string]: unknown
}

// 经过质控验证的阿里云模型列表
const QC_SUCCESS_MODELS = new Set<string>([
  'qwen-plus',
  'qwen-turbo',
  'qwen3-30b-a3b',
  'qwen3-4b',
  'qwen3-235b-a22b-instruct-2507',
  'qwen2.5-32b-instruct',
  'qwen2.5-14b-instruct',
])

// 定义组件事件
const emit = defineEmits<{
  'config-updated': [configData: unknown]
  'close-drawer': []
  'close-modal': []
}>()

// 响应式数据
const selectedConfig = ref('alibaba') // 默认选择阿里通义千问
const selectedModel = ref('')
const apiKey = ref('sk-f1fa15b00fb042a9a80943a40e142daf') // 预设API密钥
const customEndpoint = ref('')
const testing = ref(false)
const saving = ref(false)
const saveSuccess = ref(false)

// LLM 高级参数配置
const advancedParams = reactive({
  temperature: 0.2, // 默认值：0.2（推荐用于质控场景）
  top_p: 0.9, // 默认值：0.9
  max_tokens: 4000, // 默认值：4000
})

// 高级参数区域是否展开
const advancedParamsExpanded = ref<string | string[]>(['1'])

// 动态获取的数据
const dynamicProviders = ref<RemoteProvider[]>([])
const dynamicModels = ref<RemoteModel[]>([])
const isLoadingProviders = ref(false)
const isLoadingModels = ref(false)
const testResult = ref<{
  success: boolean
  message: string
  details?: string
} | null>(null)

// 配置管理器
const configManager = new EnhancedLLMApiConfigManager()

// 可用配置
const availableConfigs = computed(() => Object.values(ENHANCED_LLM_API_CONFIGS))

// 当前配置
const currentConfig = computed<EnhancedLLMApiConfig | undefined>(
  () => ENHANCED_LLM_API_CONFIGS[selectedConfig.value],
)

// 可用模型 - 优先使用动态获取的模型列表（兼容多种字段命名）
const availableModels = computed<ModelOption[]>(() => {
  if (dynamicModels.value.length > 0) {
    return dynamicModels.value
      .map((model) => {
        const value = String(model.model_code || model.id || model.code || model.name || '')
        let label = String(model.model_name || model.name || model.id || value)
        if (value.includes('30b-a3b') && value.includes('2507') && !label.includes('2507')) {
          label = `${label} (2507)`
        }
        if (!value) return null
        return {
          label,
          value,
          description: model.description || '',
          qcStatus: QC_SUCCESS_MODELS.has(value) ? 'passed' : undefined,
        }
      })
      .filter(Boolean) as ModelOption[]
  }
  // 回退到硬编码配置（向后兼容）
  return (currentConfig.value?.availableModels || []).map((model) => {
    const nextLabel =
      model.value.includes('30b-a3b') &&
      model.value.includes('2507') &&
      !model.label.includes('2507')
        ? `${model.label} (2507)`
        : model.label
    return {
      ...model,
      label: nextLabel,
      qcStatus: model.qcStatus || (QC_SUCCESS_MODELS.has(model.value) ? 'passed' : undefined),
    }
  })
})

// 当前模型信息（优先从动态模型或可用模型中查找）
const currentModelInfo = computed<ModelOption | null>(() => {
  if (!selectedModel.value) return null
  return availableModels.value.find((model) => model.value === selectedModel.value) || null
})

interface ConfigStatus {
  valid: boolean
  type: 'success' | 'warning' | 'error' | 'info'
  message: string
}

// 配置状态
const configStatus = computed<ConfigStatus>(() => {
  const config = currentConfig.value
  if (!config) {
    return { valid: false, type: 'error', message: '未选择配置' }
  }

  if (config.requiresApiKey && !apiKey.value) {
    return {
      valid: false,
      type: 'warning',
      message: `${config.displayName} 需要配置API密钥`,
    }
  }

  return {
    valid: true,
    type: 'success',
    message: `${config.displayName} 配置完成`,
  }
})

const LLM_API_PREFIX = '/api/v1/llm'

// 从数据库获取模型列表
const loadModelsForProvider = async (providerCode: string) => {
  try {
    isLoadingModels.value = true
    const baseURL = resolveApiBaseUrl()

    // 首先获取提供商信息（兼容 {data:[]} 与 {providers:[]} 两种返回结构）
    const providersResponse = await authFetch(`${baseURL}${LLM_API_PREFIX}/providers`)
    if (!providersResponse.ok) {
      throw new Error(`加载大模型提供商失败: ${providersResponse.status}`)
    }
    const providersRaw = await providersResponse.json()
    const providersData = extractApiData<
      | { data?: RemoteProvider[]; providers?: RemoteProvider[] }
      | RemoteProvider[]
      | null
      | undefined
    >(providersRaw, '加载大模型提供商失败')
    const providerList = Array.isArray(providersData)
      ? providersData
      : ((providersData?.data || providersData?.providers || []) as RemoteProvider[])
    dynamicProviders.value = providerList
    const provider = providerList.find((p) => (p.provider_code || p.id) === providerCode)

    // 加载模型（兼容 {data:[]} 与 {models:[]}；后端可能不支持 provider_id 过滤时回退全量）
    const modelsPath = provider?.id
      ? `${LLM_API_PREFIX}/models?provider_id=${provider.id}`
      : `${LLM_API_PREFIX}/models`
    const modelsResponse = await authFetch(`${baseURL}${modelsPath}`)
    if (!modelsResponse.ok) {
      throw new Error(`加载模型列表失败: ${modelsResponse.status}`)
    }
    const modelsRaw = await modelsResponse.json()
    const modelsData = extractApiData<
      { data?: RemoteModel[]; models?: RemoteModel[] } | RemoteModel[] | null | undefined
    >(modelsRaw, '加载模型列表失败')
    const modelsList = Array.isArray(modelsData)
      ? modelsData
      : ((modelsData?.data || modelsData?.models || []) as RemoteModel[])
    dynamicModels.value = Array.isArray(modelsList) ? modelsList : []
    console.log(`✅ 已加载 ${dynamicModels.value.length} 个模型`)

    // 若当前选择不在新列表中，则回退到默认或第一项
    const values = new Set(availableModels.value.map((model) => model.value))
    if (!values.has(selectedModel.value)) {
      selectedModel.value =
        currentConfig.value?.defaultModel || availableModels.value[0]?.value || ''
    }
  } catch (error) {
    console.error('加载模型列表失败:', error)
    dynamicModels.value = []
  } finally {
    isLoadingModels.value = false
  }
}

// 方法
const handleProviderSelect = async (providerName: string) => {
  selectedConfig.value = providerName
  await handleConfigChange()
}

const handleConfigChange = async () => {
  // 如果选择阿里通义千问，自动设置API密钥
  if (selectedConfig.value === 'alibaba') {
    apiKey.value = 'sk-f1fa15b00fb042a9a80943a40e142daf'
  }

  // 动态加载该提供商的模型列表
  await loadModelsForProvider(selectedConfig.value)

  configManager.switchConfig(selectedConfig.value, apiKey.value)
  // 若无已选模型，回退到推荐或第一个可用模型
  if (!selectedModel.value) {
    selectedModel.value = currentConfig.value?.defaultModel || availableModels.value[0]?.value || ''
  }
  testResult.value = null
}

const handleModelChange = () => {
  // 不再使用硬编码的configManager.switchModel，直接设置模型
  // 因为模型列表已经从数据库动态获取，无需额外验证
  if (selectedModel.value) {
    console.log(`已选择模型: ${selectedModel.value}`)
  }
  testResult.value = null
}

const handleApiKeyChange = () => {
  configManager.setApiKey(apiKey.value)
}

const handleEndpointChange = () => {
  // 更新本地配置的端点
  if (selectedConfig.value === 'local') {
    ENHANCED_LLM_API_CONFIGS.local.endpoint = customEndpoint.value
  }
}

const getFeatureColor = (feature: string): string => {
  const colorMap: Record<string, string> = {
    高准确率: 'green',
    中文优化: 'blue',
    企业级: 'purple',
    医疗专业: 'red',
    开源友好: 'orange',
    数据私有: 'cyan',
    开发测试: 'default',
    高并发: 'purple',
    多模态: 'geekblue',
    安全合规: 'green',
    可本地部署: 'orange',
  }
  return colorMap[feature] || 'default'
}

const getPricingColor = (pricing?: string): string => {
  const colorMap: Record<string, string> = {
    免费: 'green',
    很低: 'cyan',
    低: 'blue',
    中: 'orange',
    高: 'red',
    很高: 'magenta',
  }
  return colorMap[pricing || ''] || 'default'
}

// 恢复高级参数默认值
const resetAdvancedParams = () => {
  advancedParams.temperature = 0.2
  advancedParams.top_p = 0.9
  advancedParams.max_tokens = 4000
  message.success('已恢复默认参数值')
}

const getApiKeyHelp = (): string => {
  const helpMap: Record<string, string> = {
    openai: '在 OpenAI 官网获取 API Key',
    baidu: '在百度智能云控制台获取 Access Token',
    alibaba: '在阿里云控制台获取 API Key',
    tencent: '在腾讯云控制台获取 SecretId 和 SecretKey',
    zhipu: '在智谱AI开放平台获取 API Key',
  }
  return helpMap[selectedConfig.value] || '请联系服务提供商获取API密钥'
}

const testConnection = async () => {
  if (testing.value) return // 防止重复点击

  testing.value = true
  testResult.value = null

  try {
    const cfg = currentConfig.value
    if (!cfg) {
      throw new Error('未选择有效配置')
    }
    // 显示测试中的提示
    message.loading('正在测试连接...', 0)

    // 创建LLM服务实例
    const llmService = new LLMService({
      apiEndpoint: cfg.endpoint,
      apiKey: apiKey.value,
      model: selectedModel.value || cfg.defaultModel,
    })

    // 发送测试请求
    const testPrompt = '请回复"连接测试成功"'
    const result = (await llmService.parseMedicalText(testPrompt, {
      confidenceThreshold: 0.5,
    })) as ParseResult

    if (result.success) {
      testResult.value = {
        success: true,
        message: '连接测试成功',
        details: `响应时间: ${result.processingTime}ms`,
      }

      // 销毁loading消息并显示成功消息
      message.destroy()
      message.success({
        content: `🎉 API连接测试成功！响应时间: ${result.processingTime}ms`,
        duration: 3,
        style: {
          marginTop: '20vh',
        },
      })
    } else {
      throw new Error(result.error || '未知错误')
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : '未知错误'
    testResult.value = {
      success: false,
      message: '连接测试失败',
      details: errorMessage,
    }

    // 销毁loading消息并显示错误消息
    message.destroy()
    message.error({
      content: `❌ API连接测试失败：${errorMessage}`,
      duration: 5,
      style: {
        marginTop: '20vh',
      },
    })
  } finally {
    testing.value = false
  }
}

const saveConfig = async () => {
  if (saving.value) return // 防止重复点击

  saving.value = true
  try {
    console.log('🔄 开始保存配置...', {
      selectedConfig: selectedConfig.value,
      selectedModel: selectedModel.value,
      hasApiKey: !!apiKey.value,
    })

    // 显示开始保存的提示
    message.loading('正在保存配置...', 0)

    // 精简保存逻辑：直接提交 provider_code 与 model_code，由后端解析为ID
    if (!selectedConfig.value) {
      message.destroy()
      message.error('请选择一个API服务商')
      return
    }
    if (!selectedModel.value) {
      message.destroy()
      message.error('请选择一个模型')
      return
    }

    const configData = {
      config_name: 'default',
      provider_code: selectedConfig.value,
      model_code: selectedModel.value,
      api_key: apiKey.value || undefined,
      custom_endpoint: customEndpoint.value || undefined,
      custom_parameters: {
        temperature: advancedParams.temperature,
        top_p: advancedParams.top_p,
        max_tokens: advancedParams.max_tokens,
      },
      is_active: true,
    }
    console.log('💾 保存配置数据(按code):', configData)

    // 添加超时处理
    const timeoutPromise = new Promise((_, reject) => {
      setTimeout(() => reject(new Error('保存配置超时，请检查网络连接')), 30000) // 30秒超时
    })

    const saved = (await Promise.race([
      llmConfigService.saveConfig(configData as any),
      timeoutPromise,
    ])) as any
    console.log('✅ 配置保存成功:', saved)

    // 同步到运行时（可立即测试）
    console.log('🔄 同步配置到运行时...')
    const endpoint = saved.custom_endpoint || saved.provider?.base_endpoint || ''
    if (endpoint) {
      try {
        const { llmService } = await import('@/services/llmServiceNew')
        llmService.updateConfig({
          apiEndpoint: endpoint,
          apiKey: apiKey.value || '',
          model: saved.model?.model_code || '',
        })
        console.log('✅ 运行时配置同步成功')
      } catch (syncError) {
        console.error('⚠️ 运行时配置同步失败:', syncError)
        // 不阻断保存流程
      }
    }

    // 调用后端配置重载 API
    console.log('🔄 通知后端重新加载配置...')
    try {
      const reloadResponse = await authFetch('/api/v1/qc/sichuan/reload-config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (reloadResponse.ok) {
        const reloadResult = await reloadResponse.json()
        if (reloadResult.success) {
          console.log('✅ 后端配置已重载:', reloadResult.data?.current_model)
          message.success({
            content: `✅ 后端配置已更新，当前模型: ${reloadResult.data?.current_model || '未知'}`,
            duration: 2,
            style: {
              marginTop: '20vh',
            },
          })
        } else {
          console.warn('⚠️ 后端配置重载失败:', reloadResult.message)
        }
      } else {
        console.warn('⚠️ 后端配置重载请求失败:', reloadResponse.status)
      }
    } catch (reloadError) {
      console.error('⚠️ 后端配置重载异常:', reloadError)
      // 不阻断保存流程，只记录警告
      message.warning({
        content: '⚠️ 后端配置重载失败，可能需要手动重启后端服务',
        duration: 3,
        style: {
          marginTop: '20vh',
        },
      })
    }

    // 销毁loading消息并显示成功消息
    console.log('🎉 准备显示成功消息...')
    message.destroy()
    message.success({
      content: '✅ LLM配置保存成功！',
      duration: 3,
      style: {
        marginTop: '20vh',
      },
    })

    // 设置保存成功状态
    console.log('✅ 设置保存成功状态')
    saveSuccess.value = true

    // 通知外部和全局
    const payload = {
      selectedConfig: selectedConfig.value,
      selectedModel: selectedModel.value,
      apiKey: apiKey.value,
      customEndpoint: customEndpoint.value,
      timestamp: Date.now(),
    }
    window.dispatchEvent(new CustomEvent('llm-config-updated', { detail: payload }))
    emit('config-updated', payload)

    // 延迟关闭弹窗，让用户看到成功消息
    setTimeout(() => {
      console.log('🔄 准备自动关闭LLM配置页面...')
      saveSuccess.value = false

      // 同时发送两种关闭事件，兼容Modal和Drawer
      emit('close-drawer')
      emit('close-modal')

      // 尝试通过全局事件关闭
      window.dispatchEvent(new CustomEvent('llm-config-close'))

      // 如果是在iframe或特殊环境中，尝试通过postMessage
      if (window.parent !== window) {
        window.parent.postMessage({ type: 'llm-config-close' }, '*')
      }

      console.log('✅ 已发送所有关闭事件 (drawer + modal + global)')
    }, 1000) // 1秒后自动关闭
  } catch (e: unknown) {
    console.error('保存配置失败:', e)
    message.destroy()

    // 显示详细的错误信息
    const errorMessage = e instanceof Error ? e.message : String(e ?? '未知错误')
    message.error({
      content: `❌ 保存失败：${errorMessage}`,
      duration: 5,
      style: {
        marginTop: '20vh',
      },
    })
  } finally {
    console.log('🔄 重置保存状态...')
    saving.value = false
    console.log('✅ 保存状态已重置，saving:', saving.value)
  }
}

const loadConfig = async () => {
  try {
    // 1) 优先从数据库读取默认配置
    // 优先加载用户默认，其次全局默认
    let dbConfig = await llmConfigService.getConfigByName('default')
    if (!dbConfig) dbConfig = await llmConfigService.getConfigByName('default')
    if (dbConfig) {
      // 先设置提供商（provider_code），再设置模型，避免 watcher 覆盖
      selectedConfig.value = dbConfig.provider?.provider_code || 'alibaba'
      selectedModel.value = dbConfig.model?.model_code || ''

      // 如果是阿里通义千问，使用预设API密钥，否则使用数据库中的密钥
      if (selectedConfig.value === 'alibaba') {
        apiKey.value = 'sk-f1fa15b00fb042a9a80943a40e142daf'
      } else {
        apiKey.value = (dbConfig as any).api_key_decrypted || ''
      }

      customEndpoint.value = dbConfig.custom_endpoint || ''

      // 加载高级参数
      const customParams = (dbConfig.custom_parameters || {}) as Record<string, unknown>
      advancedParams.temperature =
        typeof customParams.temperature === 'number' ? customParams.temperature : 0.2
      advancedParams.top_p = typeof customParams.top_p === 'number' ? customParams.top_p : 0.9
      advancedParams.max_tokens =
        typeof customParams.max_tokens === 'number' ? customParams.max_tokens : 4000

      // 加载该提供商的模型列表
      await loadModelsForProvider(selectedConfig.value)

      // 同步到本地管理器（用于测试连接等）
      configManager.switchConfig(selectedConfig.value, apiKey.value)
      // 不再调用switchModel，避免硬编码验证错误
      return
    }

    // 2) 向后兼容：无数据库记录时，尝试从 localStorage 恢复
    const savedConfig =
      typeof localStorage !== 'undefined' ? localStorage.getItem('llm-api-config') : null
    if (savedConfig) {
      const configData = JSON.parse(savedConfig)
      selectedConfig.value = configData.selectedConfig || 'alibaba' // 默认阿里通义千问
      selectedModel.value = configData.selectedModel || ''
      // 如果是阿里通义千问，使用预设API密钥
      apiKey.value =
        selectedConfig.value === 'alibaba'
          ? 'sk-f1fa15b00fb042a9a80943a40e142daf'
          : configData.apiKey || ''
      customEndpoint.value = configData.customEndpoint || ''

      // 加载该提供商的模型列表
      await loadModelsForProvider(selectedConfig.value)

      configManager.switchConfig(selectedConfig.value, apiKey.value)
      // 不再调用switchModel，避免硬编码验证错误
    } else {
      // 没有任何保存的配置，使用阿里通义千问作为默认
      selectedConfig.value = 'alibaba'
      apiKey.value = 'sk-f1fa15b00fb042a9a80943a40e142daf'
      selectedModel.value = ''

      // 加载阿里通义千问的模型列表
      await loadModelsForProvider('alibaba')

      configManager.switchConfig(selectedConfig.value, apiKey.value)
    }
  } catch (error) {
    console.error('加载配置失败:', error)
    // 出错时也使用阿里通义千问作为默认
    selectedConfig.value = 'alibaba'
    apiKey.value = 'sk-f1fa15b00fb042a9a80943a40e142daf'
    selectedModel.value = ''

    // 尝试加载阿里通义千问的模型列表
    try {
      await loadModelsForProvider('alibaba')
    } catch (modelError) {
      console.error('加载默认模型列表失败:', modelError)
    }

    configManager.switchConfig(selectedConfig.value, apiKey.value)
  }
}

// 监听配置变化
watch([selectedConfig, selectedModel, apiKey], () => {
  testResult.value = null
})

// 监听配置变化，自动设置默认模型
watch(selectedConfig, () => {
  if (currentConfig.value && !selectedModel.value) {
    selectedModel.value = currentConfig.value.defaultModel
  }
})

// 组件挂载时加载配置
onMounted(async () => {
  await loadConfig()
  // 加载完成后，确保有可见的已选模型
  if (!selectedModel.value) {
    selectedModel.value = currentConfig.value?.defaultModel || availableModels.value[0]?.value || ''
  }
})
</script>

<style scoped>
.llm-api-config {
  width: 100%;
}

/* Master-Detail 布局 */
.master-detail-layout {
  min-height: 500px;
}

/* 左侧面板 (Master) */
.master-panel {
  border-right: 1px solid rgba(11, 100, 212, 0.12);
  padding-right: 0 !important;
}

.provider-list {
  position: sticky;
  top: 0;
}

.panel-title {
  margin-bottom: 16px;
  padding: 0 16px;
  font-weight: 600;
  color: var(--text-primary, #262626);
  font-size: 16px;
}

.provider-items {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.provider-item {
  padding: 16px;
  cursor: pointer;
  transition: all 0.3s ease;
  border-left: 3px solid transparent;
  background: transparent;
  position: relative;
}

.provider-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: transparent;
  transition: all 0.3s ease;
}

.provider-item:hover {
  background: rgba(24, 144, 255, 0.04);
}

.provider-item:hover::before {
  background: rgba(24, 144, 255, 0.3);
}

.provider-item--active {
  background: linear-gradient(90deg, rgba(24, 144, 255, 0.08) 0%, rgba(24, 144, 255, 0.02) 100%);
}

.provider-item--active::before {
  background: #1890ff;
  box-shadow: 0 0 8px rgba(24, 144, 255, 0.4);
}

.provider-item--active .provider-item__name {
  color: #1890ff;
  font-weight: 600;
}

.provider-item__content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.provider-item__name {
  font-weight: 500;
  font-size: 14px;
  color: var(--text-primary, #262626);
  transition: all 0.3s;
}

.provider-item__desc {
  font-size: 12px;
  color: var(--text-secondary, #8c8c8c);
  line-height: 1.4;
}

.provider-item__features {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 4px;
}

/* 右侧面板 (Detail) */
.detail-panel {
  padding-left: 24px !important;
}

.detail-panel .panel-title {
  padding: 0 0 16px 0;
  margin-bottom: 24px;
  border-bottom: 2px solid rgba(24, 144, 255, 0.1);
  color: #1890ff;
}

.config-detail {
  width: 100%;
}

.config-section {
  margin-bottom: 24px;
}

.config-status {
  margin: 16px 0;
}

.config-actions {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid rgba(11, 100, 212, 0.12);
}

.test-result {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid rgba(11, 100, 212, 0.12);
}

/* 响应式：移动端垂直堆叠 */
@media (max-width: 768px) {
  .master-panel {
    border-right: none;
    border-bottom: 1px solid rgba(11, 100, 212, 0.12);
    padding-right: 24px !important;
    padding-bottom: 24px;
    margin-bottom: 24px;
  }

  .detail-panel {
    padding-left: 24px !important;
  }

  .provider-list {
    position: static;
  }

  .panel-title {
    font-size: 14px;
  }

  .provider-item {
    padding: 12px 16px;
  }
}

:deep(.ant-radio-wrapper) {
  width: 100%;
  align-items: flex-start;
}

:deep(.ant-radio) {
  margin-top: 2px;
}

/* 模型选择相关样式 */
.model-name {
  font-weight: 500;
  color: #262626;
  font-size: 14px;
}

.model-details {
  margin-top: 12px;
  padding: 12px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #f0f0f0;
}

:deep(.ant-select-dropdown) {
  max-height: 500px;
}

:deep(.ant-select-item) {
  padding: 0 !important;
  min-height: 80px !important;
}

:deep(.ant-select-item-option-content) {
  padding: 0 !important;
  width: 100%;
  height: auto;
}

:deep(.ant-select-item-option) {
  padding: 0 !important;
  height: auto !important;
  min-height: 80px !important;
}

:deep(.ant-select-item-option-active) {
  background-color: #f6ffed !important;
}

:deep(.ant-select-item-option-selected) {
  background-color: #e6f7ff !important;
}

/* 确保选择框和输入框高度完全一致 */
:deep(.ant-select-selector) {
  height: 40px !important;
  min-height: 40px !important;
  max-height: 40px !important;
  padding: 6px 11px !important;
  border-width: 1px !important;
  box-sizing: border-box !important;
  display: flex !important;
  align-items: center !important;
  font-size: 14px !important;
  line-height: 1.5715 !important;
}

:deep(.ant-input) {
  height: 40px !important;
  min-height: 40px !important;
  max-height: 40px !important;
  padding: 6px 11px !important;
  border-width: 1px !important;
  box-sizing: border-box !important;
  font-size: 14px !important;
  line-height: 1.5715 !important;
  display: flex !important;
  align-items: center !important;
}

/* 统一输入框内容的显示 */
:deep(.ant-select-selection-item) {
  line-height: 1.5715 !important;
  display: flex !important;
  align-items: center !important;
  height: 26px !important;
  padding: 0 !important;
  margin: 0 !important;
}

:deep(.ant-select-selection-placeholder) {
  line-height: 1.5715 !important;
  display: flex !important;
  align-items: center !important;
  height: 26px !important;
  padding: 0 !important;
  margin: 0 !important;
}

/* 统一前缀和后缀图标的样式 */
:deep(.ant-input-prefix),
:deep(.ant-input-suffix) {
  display: flex !important;
  align-items: center !important;
  height: 26px !important;
}

/* 优化下拉箭头位置 */
:deep(.ant-select-arrow) {
  top: 50% !important;
  transform: translateY(-50%) !important;
  height: 12px !important;
  width: 12px !important;
}

/* 确保选择框在不同状态下高度一致 */
:deep(.ant-select-focused .ant-select-selector),
:deep(.ant-select-open .ant-select-selector) {
  height: 40px !important;
  min-height: 40px !important;
  max-height: 40px !important;
}

/* 确保输入框在不同状态下高度一致 */
:deep(.ant-input:focus),
:deep(.ant-input-focused) {
  height: 40px !important;
  min-height: 40px !important;
  max-height: 40px !important;
}

/* 重置所有可能影响高度的样式 */
:deep(.ant-select),
:deep(.ant-input-affix-wrapper) {
  height: 40px !important;
  min-height: 40px !important;
  max-height: 40px !important;
  display: flex !important;
  align-items: center !important;
}

:deep(.ant-input-affix-wrapper > input.ant-input) {
  height: 26px !important;
  padding: 0 !important;
  border: none !important;
  outline: none !important;
  background: transparent !important;
  display: flex !important;
  align-items: center !important;
  line-height: 26px !important;
}

/* 专门处理输入框占位符文本的垂直居中 */
:deep(.ant-input::placeholder) {
  line-height: 26px !important;
  display: flex !important;
  align-items: center !important;
}

:deep(.ant-input-affix-wrapper input::placeholder) {
  line-height: 26px !important;
  display: flex !important;
  align-items: center !important;
}

/* 确保大尺寸组件的一致性 */
:deep(.ant-select-lg .ant-select-selector),
:deep(.ant-input-lg) {
  height: 40px !important;
  min-height: 40px !important;
  max-height: 40px !important;
  padding: 6px 11px !important;
  font-size: 14px !important;
  line-height: 1.5715 !important;
}

/* 新增样式 */
.form-item {
  margin-bottom: 16px;
}

.form-label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #262626;
  font-size: 14px;
  height: 22px;
  line-height: 22px;
}

.form-help {
  margin-top: 4px;
  font-size: 12px;
  color: #8c8c8c;
  display: flex;
  align-items: center;
}

.model-summary {
  margin-top: 16px;
  padding: 12px;
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  border-radius: 6px;
}

.model-summary-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.model-summary-name {
  font-weight: 600;
  color: #262626;
  font-size: 14px;
}

.model-summary-desc {
  color: #8c8c8c;
  font-size: 12px;
}

/* 强制重置可能影响高度的所有样式 */
.form-item :deep(.ant-select),
.form-item :deep(.ant-input-affix-wrapper),
.form-item :deep(.ant-input) {
  height: 40px !important;
  min-height: 40px !important;
  max-height: 40px !important;
  box-sizing: border-box !important;
  display: flex !important;
  align-items: center !important;
}

/* 确保输入框内的文本和占位符都垂直居中 */
.form-item :deep(.ant-input-affix-wrapper) {
  padding: 6px 11px !important;
}

.form-item :deep(.ant-input-affix-wrapper input) {
  height: 28px !important;
  line-height: 28px !important;
  padding: 0 !important;
  border: none !important;
  background: transparent !important;
  display: block !important;
}

.form-item :deep(.ant-input-affix-wrapper input::placeholder) {
  line-height: 28px !important;
  color: #bfbfbf !important;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .form-item {
    margin-bottom: 12px;
  }

  .model-summary {
    margin-top: 12px;
    padding: 8px;
  }

  .model-summary-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  /* 在移动端也保持高度一致 */
  .form-item :deep(.ant-select),
  .form-item :deep(.ant-input-affix-wrapper),
  .form-item :deep(.ant-input) {
    height: 40px !important;
    min-height: 40px !important;
    max-height: 40px !important;
  }
}

/* 保存成功按钮样式 */
.save-success {
  background-color: #f6ffed !important;
  border-color: #52c41a !important;
  color: #52c41a !important;
  animation: saveSuccessAnimation 0.3s ease-in-out;
}

.save-success:hover {
  background-color: #f6ffed !important;
  border-color: #52c41a !important;
  color: #52c41a !important;
}

.save-success:focus {
  background-color: #f6ffed !important;
  border-color: #52c41a !important;
  color: #52c41a !important;
  box-shadow: 0 0 0 2px rgba(82, 196, 26, 0.2) !important;
}

@keyframes saveSuccessAnimation {
  0% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
  100% {
    transform: scale(1);
  }
}

/* 高级参数配置区域样式 */
.advanced-params-section {
  margin-top: 16px;
}

.advanced-params-collapse {
  background: transparent !important;
  border: none !important;
}

.advanced-params-panel {
  background: #f8f9fa !important;
  border: 1px solid #e8e8e8 !important;
  border-radius: 8px !important;
  overflow: hidden;
}

.advanced-params-header {
  display: flex;
  align-items: center;
  font-weight: 500;
  font-size: 14px;
}

.advanced-params-header .header-icon {
  margin-right: 8px;
  font-size: 16px;
  color: #1890ff;
}

.advanced-params-header .header-title {
  color: #262626;
}

.advanced-params-content {
  padding: 16px 0;
}

.param-item {
  margin-bottom: 24px;
}

.param-item:last-child {
  margin-bottom: 0;
}

.param-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.param-label {
  font-weight: 500;
  font-size: 14px;
  color: #262626;
  display: flex;
  align-items: center;
  gap: 6px;
}

.param-help-icon {
  color: #8c8c8c;
  cursor: help;
  font-size: 14px;
}

.param-value-display {
  display: flex;
  align-items: center;
  gap: 8px;
}

.param-value-display .current-value {
  font-weight: 600;
  font-size: 16px;
  color: #1890ff;
  min-width: 40px;
  text-align: right;
}

.param-description {
  margin-top: 8px;
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.5;
}

.param-actions {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e8e8e8;
  display: flex;
  justify-content: flex-end;
}

/* Slider 样式优化 */
:deep(.ant-slider) {
  margin: 8px 0 16px 0;
}

:deep(.ant-slider-mark-text) {
  font-size: 12px;
  color: #8c8c8c;
}

:deep(.ant-slider-mark-text-active) {
  color: #1890ff;
  font-weight: 500;
}

/* 与系统设置页面统一的按钮样式 */
.elevated-action {
  border-radius: 20px !important;
  padding: 0 18px !important;
  height: 36px;
  font-weight: 500;
}
</style>
