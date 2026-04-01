<template>
  <div class="llm-api-config">
    <a-row
      :gutter="24"
      class="layout"
    >
      <a-col
        :xs="24"
        :lg="7"
      >
        <div class="provider-panel">
          <div class="panel-title">
            MaaS 厂商
          </div>
          <div class="provider-list">
            <button
              v-for="provider in providers"
              :key="provider.id"
              type="button"
              class="provider-card"
              :class="{ 'provider-card--active': provider.provider_code === selectedProviderCode }"
              @click="handleProviderChange(provider)"
            >
              <div class="provider-card__title">
                {{ provider.provider_name }}
              </div>
              <div class="provider-card__desc">
                {{ provider.description || provider.base_endpoint }}
              </div>
            </button>
          </div>
        </div>
      </a-col>

      <a-col
        :xs="24"
        :lg="17"
      >
        <div class="detail-panel">
          <div class="panel-title">
            模型配置
          </div>

          <a-alert
            class="managed-alert"
            type="info"
            show-icon
            message="API 端点和密钥由后端 env 统一托管"
            description="前端仅选择厂商、模型和高级参数。测试连接会走后端真实运行链路。"
          />

          <div class="form-item">
            <label class="form-label">选择模型</label>
            <a-select
              v-model:value="selectedModelCode"
              size="large"
              style="width: 100%"
              :loading="loadingModels"
              :disabled="loadingModels || !models.length"
              placeholder="请选择模型"
            >
              <a-select-option
                v-for="model in models"
                :key="model.model_code"
                :value="model.model_code"
              >
                {{ model.model_name }}
              </a-select-option>
            </a-select>
          </div>

          <div
            v-if="currentModel"
            class="model-summary"
          >
            <div class="model-summary__title">
              {{ currentModel.model_name }}
            </div>
            <div class="model-summary__desc">
              {{ currentModel.description || '当前模型已准备就绪。' }}
            </div>
          </div>

          <div class="advanced-card">
            <div class="advanced-card__title">
              高级参数
            </div>

            <div class="param-block">
              <div class="param-header">
                <span>Temperature</span>
                <span class="param-value">{{ form.temperature }}</span>
              </div>
              <a-slider
                v-model:value="form.temperature"
                :min="0"
                :max="2"
                :step="0.1"
                :marks="{ 0: '0', 0.2: '0.2', 1: '1', 2: '2' }"
              />
            </div>

            <div class="param-block">
              <div class="param-header">
                <span>Top P</span>
                <span class="param-value">{{ form.top_p }}</span>
              </div>
              <a-slider
                v-model:value="form.top_p"
                :min="0"
                :max="1"
                :step="0.1"
                :marks="{ 0: '0', 0.5: '0.5', 0.9: '0.9', 1: '1' }"
              />
            </div>

            <div class="param-block">
              <div class="param-header">
                <span>Max Tokens</span>
                <span class="param-value">{{ form.max_tokens }}</span>
              </div>
              <a-input-number
                v-model:value="form.max_tokens"
                :min="1000"
                :max="32768"
                :step="1000"
                style="width: 100%"
              />
            </div>
          </div>

          <div class="status-row">
            <a-tag color="blue">
              {{ selectedProviderName || '未选择厂商' }}
            </a-tag>
            <a-tag
              v-if="selectedModelCode"
              color="green"
            >
              {{ selectedModelCode }}
            </a-tag>
          </div>

          <div class="actions">
            <a-space>
              <a-button
                class="elevated-action"
                :loading="testing"
                :disabled="!canSubmit"
                @click="testConnection"
              >
                测试连接
              </a-button>
              <a-button
                type="primary"
                class="elevated-action"
                :loading="saving"
                :disabled="!canSubmit"
                @click="saveConfig"
              >
                保存配置
              </a-button>
            </a-space>
          </div>

          <a-alert
            v-if="testResult"
            class="result-alert"
            :type="testResult.success ? 'success' : 'error'"
            :message="testResult.message"
            :description="testResult.description"
            show-icon
          />
        </div>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  llmConfigService,
  type LLMConfigInput,
  type LLMModel,
  type LLMProvider,
} from '@/services/llmConfigService'
import { authFetch } from '@/utils/auth-fetch'

const emit = defineEmits<{
  'config-updated': [configData: unknown]
  'close-drawer': []
  'close-modal': []
}>()

const ALLOWED_PROVIDER_CODES = ['alibaba', 'siliconflow', 'ollama']

const providers = ref<LLMProvider[]>([])
const models = ref<LLMModel[]>([])
const selectedProviderCode = ref<string>('alibaba')
const selectedProviderId = ref<string>('')
const selectedModelCode = ref<string>('')
const loadingModels = ref(false)
const saving = ref(false)
const testing = ref(false)
const testResult = ref<{ success: boolean; message: string; description: string } | null>(null)

const form = reactive({
  temperature: 0.2,
  top_p: 0.9,
  max_tokens: 4000,
})

const selectedProvider = computed(
  () => providers.value.find((item) => item.provider_code === selectedProviderCode.value) || null,
)
const selectedProviderName = computed(() => selectedProvider.value?.provider_name || '')
const currentModel = computed(
  () => models.value.find((item) => item.model_code === selectedModelCode.value) || null,
)
const canSubmit = computed(() => Boolean(selectedProviderCode.value && selectedModelCode.value))

const buildCustomParameters = () => ({
  temperature: form.temperature,
  top_p: form.top_p,
  max_tokens: form.max_tokens,
})

async function loadProviders() {
  const rows = await llmConfigService.getProviders()
  providers.value = rows.filter((item) => ALLOWED_PROVIDER_CODES.includes(item.provider_code))

  if (!providers.value.length) {
    throw new Error('未获取到可用的 LLM 厂商')
  }

  const matched =
    providers.value.find((item) => item.provider_code === selectedProviderCode.value) ||
    providers.value[0]
  selectedProviderCode.value = matched.provider_code
  selectedProviderId.value = matched.id
}

async function loadModels(provider: LLMProvider, preferredModelCode?: string) {
  loadingModels.value = true
  try {
    selectedProviderCode.value = provider.provider_code
    selectedProviderId.value = provider.id
    const rows = await llmConfigService.getModelsByProvider(provider.id)
    models.value = rows
    const matched = rows.find((item) => item.model_code === preferredModelCode) || rows[0] || null
    selectedModelCode.value = matched?.model_code || ''
  } finally {
    loadingModels.value = false
  }
}

async function handleProviderChange(provider: LLMProvider) {
  testResult.value = null
  await loadModels(provider)
}

async function loadSavedConfig() {
  const config = await llmConfigService.getConfigByName('default')
  if (!config?.provider?.provider_code) {
    const fallback = providers.value[0]
    if (fallback) {
      await loadModels(fallback)
    }
    return
  }

  const provider =
    providers.value.find((item) => item.provider_code === config.provider?.provider_code) ||
    providers.value[0]
  if (!provider) return

  const customParams = (config.custom_parameters || {}) as Record<string, unknown>
  form.temperature = typeof customParams.temperature === 'number' ? customParams.temperature : 0.2
  form.top_p = typeof customParams.top_p === 'number' ? customParams.top_p : 0.9
  form.max_tokens = typeof customParams.max_tokens === 'number' ? customParams.max_tokens : 4000

  await loadModels(provider, config.model?.model_code || '')
}

async function testConnection() {
  if (!canSubmit.value) return
  testing.value = true
  testResult.value = null
  try {
    const result = await llmConfigService.testConfig({
      provider_code: selectedProviderCode.value,
      model_code: selectedModelCode.value,
      custom_parameters: buildCustomParameters(),
    })
    testResult.value = {
      success: true,
      message: '连接测试成功',
      description: `${result.provider_code} / ${result.model} 已联通`,
    }
    message.success('连接测试成功')
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error)
    testResult.value = {
      success: false,
      message: '连接测试失败',
      description: text,
    }
    message.error(`连接测试失败：${text}`)
  } finally {
    testing.value = false
  }
}

async function saveConfig() {
  if (!canSubmit.value) return
  saving.value = true
  try {
    const payload: LLMConfigInput = {
      config_name: 'default',
      provider_id: selectedProviderId.value,
      provider_code: selectedProviderCode.value,
      model_code: selectedModelCode.value,
      custom_parameters: buildCustomParameters(),
      is_active: true,
    }
    const saved = await llmConfigService.saveConfig(payload)

    const reloadResponse = await authFetch('/api/v1/qc/sichuan/reload-config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!reloadResponse.ok) {
      throw new Error(`后端配置重载失败: ${reloadResponse.status}`)
    }

    const eventPayload = {
      selectedProviderCode: selectedProviderCode.value,
      selectedModelCode: selectedModelCode.value,
      custom_parameters: buildCustomParameters(),
      timestamp: Date.now(),
    }
    window.dispatchEvent(new CustomEvent('llm-config-updated', { detail: eventPayload }))
    emit('config-updated', saved || eventPayload)
    message.success('LLM 配置保存成功')

    setTimeout(() => {
      emit('close-drawer')
      emit('close-modal')
    }, 600)
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error)
    message.error(`保存配置失败：${text}`)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    await loadProviders()
    await loadSavedConfig()
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error)
    message.error(`加载 LLM 配置失败：${text}`)
  }
})
</script>

<style scoped>
.llm-api-config {
  width: 100%;
}

.layout {
  min-height: 520px;
}

.panel-title {
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #262626);
}

.provider-panel {
  padding-right: 8px;
}

.provider-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.provider-card {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid rgba(11, 100, 212, 0.12);
  border-radius: 14px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.provider-card:hover,
.provider-card--active {
  border-color: #1677ff;
  background: rgba(22, 119, 255, 0.05);
  box-shadow: 0 8px 20px rgba(22, 119, 255, 0.08);
}

.provider-card__title {
  margin-bottom: 6px;
  font-weight: 600;
  color: #262626;
}

.provider-card__desc {
  font-size: 12px;
  line-height: 1.5;
  color: #8c8c8c;
}

.detail-panel {
  padding-left: 8px;
}

.managed-alert {
  margin-bottom: 20px;
}

.form-item {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #262626;
}

.model-summary {
  margin-bottom: 20px;
  padding: 12px 14px;
  border: 1px solid #d9f7be;
  border-radius: 12px;
  background: #f6ffed;
}

.model-summary__title {
  margin-bottom: 4px;
  font-weight: 600;
  color: #262626;
}

.model-summary__desc {
  font-size: 12px;
  color: #595959;
}

.advanced-card {
  margin-bottom: 20px;
  padding: 16px;
  border: 1px solid rgba(11, 100, 212, 0.12);
  border-radius: 14px;
  background: #fafcff;
}

.advanced-card__title {
  margin-bottom: 18px;
  font-weight: 600;
  color: #262626;
}

.param-block {
  margin-bottom: 22px;
}

.param-block:last-child {
  margin-bottom: 0;
}

.param-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 14px;
  color: #262626;
}

.param-value {
  font-weight: 600;
  color: #1677ff;
}

.status-row {
  margin-bottom: 20px;
}

.actions {
  margin-bottom: 20px;
}

.result-alert {
  margin-top: 8px;
}

.elevated-action {
  border-radius: 20px !important;
  padding: 0 18px !important;
  height: 36px;
  font-weight: 500;
}

@media (max-width: 991px) {
  .provider-panel {
    padding-right: 0;
    margin-bottom: 20px;
  }

  .detail-panel {
    padding-left: 0;
  }
}
</style>
