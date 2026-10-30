<template>
  <div class="ds-root">
    <div class="ds-split">
      <div class="ds-split__aside">
        <div class="ds-aside-card">
          <div class="ds-aside-eyebrow">
            模型与参数
          </div>
          <h2 class="ds-section-title">
            模型配置治理
          </h2>
          <p class="ds-section-desc">
            统一管理云端 API、本地推理与运行参数。服务地址和密钥由部署配置提供，
            此处维护推理服务与模型选择。
          </p>

          <div class="ds-meta-list">
            <div class="ds-meta-card">
              <span class="ds-meta__label">当前来源</span>
              <a-tag color="blue">
                {{ source }}
              </a-tag>
            </div>
            <div class="ds-meta-card">
              <span class="ds-meta__label">配置状态</span>
              <a-tag :color="dirty ? 'orange' : 'green'">
                {{ dirty ? '草稿未保存' : '已同步' }}
              </a-tag>
            </div>
          </div>

          <div class="ds-aside-note">
            推荐流程：先选推理服务与模型，再调高级参数，最后做连接验证并统一保存。
          </div>
        </div>
      </div>

      <div class="ds-split__main">
        <a-alert
          v-if="isReadonly"
          type="info"
          show-icon
          message="当前为只读模式"
          description="仅系统配置管理员可修改并保存模型配置。"
          class="mb-3"
        />

        <div class="ds-hero">
          <div class="ds-hero__content">
            <div class="ds-hero__label">
              当前草稿
            </div>
            <div class="ds-hero__title">
              {{ draft.provider_code || '未选择厂商' }} / {{ draft.model_code || '未选择模型' }}
            </div>
            <div class="ds-hero__desc">
              高级参数：Temperature {{ draft.temperature.toFixed(1) }}，Top P
              {{ draft.top_p.toFixed(1) }}，Max Tokens {{ draft.max_tokens }}
            </div>
          </div>
          <div class="ds-hero__state">
            <a-tag :color="dirty ? 'orange' : 'green'">
              {{ dirty ? '待保存' : '已同步' }}
            </a-tag>
          </div>
        </div>

        <div class="ds-card">
          <div class="ds-card__body ds-divide">
            <div class="ds-group">
              <div class="ds-group__title">
                推理服务与模型
              </div>

              <div class="ds-row">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    推理服务
                  </div>
                  <div class="ds-row__hint">
                    可选择云端 API 或本地推理，地址与密钥由部署配置统一托管。
                  </div>
                </div>
                <a-select
                  v-model:value="draft.provider_code"
                  class="ds-select"
                  style="width: 260px"
                  :disabled="isReadonly || loading || saving"
                  :options="providerOptions"
                  @change="handleProviderChange"
                />
              </div>

              <a-alert
                v-if="draft.provider_code === 'strata'"
                type="info"
                show-icon
                message="本地 Strata"
                description="请选用已部署的模型名称；请求经统一网关控制容量。本地服务不可用时不会自动切到云端，前缀缓存默认关闭。"
              />

              <div class="ds-row">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    模型
                  </div>
                  <div class="ds-row__hint">
                    内置模型不可删除，自定义模型支持增删。
                  </div>
                </div>
                <a-select
                  v-model:value="draft.model_code"
                  class="ds-select"
                  style="width: 360px"
                  :loading="loadingModels"
                  :disabled="isReadonly || loadingModels || saving || !models.length"
                >
                  <a-select-option
                    v-for="item in models"
                    :key="item.model_code"
                    :value="item.model_code"
                  >
                    {{ item.model_name }}
                    <a-tag
                      v-if="item.is_custom"
                      color="purple"
                      class="ml-1"
                    >
                      自定义
                    </a-tag>
                  </a-select-option>
                </a-select>
              </div>

              <div class="ds-row ds-row--top">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    自定义模型
                  </div>
                  <div class="ds-row__hint">
                    仅新增/删除模型名称，不变更 endpoint 与 key。
                  </div>
                </div>
                <div class="custom-model-panel">
                  <a-space-compact style="width: 100%">
                    <a-input
                      v-model:value="newModelCode"
                      class="ds-input"
                      :disabled="isReadonly || loading"
                      placeholder="输入模型名，如 Qwen/Qwen3.5-14B"
                      @press-enter="addCustomModel"
                    />
                    <a-button
                      :disabled="isReadonly || loading || !newModelCode.trim()"
                      :loading="addingModel"
                      @click="addCustomModel"
                    >
                      添加
                    </a-button>
                  </a-space-compact>

                  <div
                    v-if="customModels.length"
                    class="custom-model-list"
                  >
                    <div
                      v-for="item in customModels"
                      :key="`custom-${item.model_code}`"
                      class="custom-model-item"
                    >
                      <span>{{ item.model_name }}</span>
                      <a-button
                        type="link"
                        size="small"
                        danger
                        :disabled="isReadonly || loading"
                        :loading="deletingModelCode === item.model_code"
                        @click="removeCustomModel(item)"
                      >
                        删除
                      </a-button>
                    </div>
                  </div>
                  <div
                    v-else
                    class="custom-model-empty"
                  >
                    当前厂商暂无自定义模型
                  </div>
                </div>
              </div>
            </div>

            <div class="ds-group">
              <div class="ds-group__title">
                高级参数
              </div>

              <div class="ds-row ds-row--top">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    Temperature
                  </div>
                  <div class="ds-row__hint">
                    控制输出随机性，值越高越发散。
                  </div>
                </div>
                <div class="slider-wrap">
                  <div class="slider-value">
                    {{ draft.temperature.toFixed(1) }}
                  </div>
                  <a-slider
                    v-model:value="draft.temperature"
                    :disabled="isReadonly || loading"
                    :min="0"
                    :max="2"
                    :step="0.1"
                    :marks="{ 0: '0', 0.2: '0.2', 1: '1', 2: '2' }"
                  />
                </div>
              </div>

              <div class="ds-row ds-row--top">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    Top P
                  </div>
                  <div class="ds-row__hint">
                    核采样阈值，控制候选词覆盖范围。
                  </div>
                </div>
                <div class="slider-wrap">
                  <div class="slider-value">
                    {{ draft.top_p.toFixed(1) }}
                  </div>
                  <a-slider
                    v-model:value="draft.top_p"
                    :disabled="isReadonly || loading"
                    :min="0"
                    :max="1"
                    :step="0.1"
                    :marks="{ 0: '0', 0.5: '0.5', 0.9: '0.9', 1: '1' }"
                  />
                </div>
              </div>

              <div class="ds-row">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    Max Tokens
                  </div>
                  <div class="ds-row__hint">
                    单次请求最大输出 token 数。
                  </div>
                </div>
                <a-input-number
                  v-model:value="draft.max_tokens"
                  class="ds-input-number"
                  :disabled="isReadonly || loading"
                  :min="1000"
                  :max="32768"
                  :step="1000"
                  style="width: 220px"
                />
              </div>
            </div>

            <div class="ds-group">
              <div class="ds-group__title">
                执行并发
              </div>

              <div class="ds-row">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    同时处理病历数
                  </div>
                  <div class="ds-row__hint">
                    单个质控任务同时进入执行链的病历上限，已按完整链验证推荐 16。
                  </div>
                </div>
                <a-input-number
                  v-model:value="draft.max_parallel_records"
                  class="ds-input-number"
                  :disabled="isReadonly || loading"
                  :min="1"
                  :max="32"
                  :step="1"
                  style="width: 220px"
                />
              </div>

              <div class="ds-row">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    单病历规则族并发
                  </div>
                  <div class="ds-row__hint">
                    每份病历可同时执行的独立规则族数量，当前安全上限为 4。
                  </div>
                </div>
                <a-input-number
                  v-model:value="draft.family_max_concurrency"
                  class="ds-input-number"
                  :disabled="isReadonly || loading"
                  :min="1"
                  :max="4"
                  :step="1"
                  style="width: 220px"
                />
              </div>

              <div class="ds-row">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    全局模型 HTTP 槽位
                  </div>
                  <div class="ds-row__hint">
                    客户端 HTTP 请求上限；网关另按服务资源限流，本地 Strata 容量由部署配置控制。
                  </div>
                </div>
                <a-input-number
                  v-model:value="draft.http_max_concurrency"
                  class="ds-input-number"
                  :disabled="isReadonly || loading"
                  :min="1"
                  :max="64"
                  :step="1"
                  style="width: 220px"
                />
              </div>
            </div>

            <div class="ds-group">
              <div class="ds-group__title">
                连接验证
              </div>

              <div class="ds-row">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    测试连接
                  </div>
                  <div class="ds-row__hint">
                    测试草稿配置，不依赖是否已保存。
                  </div>
                </div>
                <a-button
                  class="ds-test-btn"
                  :loading="testing"
                  :disabled="!canTest"
                  @click="testConnection"
                >
                  测试连接
                </a-button>
              </div>

              <div
                v-if="testResult"
                class="ds-row ds-row--result"
              >
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    最近一次结果
                  </div>
                  <div class="ds-row__hint">
                    {{ testResult.description }}
                  </div>
                </div>
                <a-tag :color="testResult.success ? 'green' : 'red'">
                  {{ testResult.success ? '成功' : '失败' }}
                </a-tag>
              </div>
            </div>
          </div>

          <div class="ds-card__footer">
            <span class="ds-footer-meta">来源：{{ source }}</span>
            <div class="ds-actions">
              <a-button
                :disabled="loading"
                @click="reloadAll"
              >
                刷新
              </a-button>
              <a-button
                :disabled="isReadonly || loading"
                @click="resetDefault"
              >
                恢复默认
              </a-button>
              <a-button
                type="primary"
                :loading="saving"
                :disabled="isReadonly || loading || loadingModels || !draft.model_code || !dirty"
                @click="saveDraft"
              >
                保存配置
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'

import { useAuthStore } from '@/stores/auth'
import { canManageSystemConfig } from '@/utils/systemConfigAccess'
import {
  llmConfigService,
  type LLMConfigInput,
  type LLMConfigSummary,
  type LLMExecutionConcurrency,
  type LLMModel,
  type LLMProvider,
} from '@/services/llmConfigService'
import { authFetch } from '@/utils/auth-fetch'

const emit = defineEmits<{
  'config-updated': [configData: unknown]
  'close-drawer': []
  'close-modal': []
}>()

const authStore = useAuthStore()
const loading = ref(false)
const loadingModels = ref(false)
const saving = ref(false)
const testing = ref(false)
const addingModel = ref(false)
const deletingModelCode = ref('')
const newModelCode = ref('')
const source = ref('unknown')
let modelRequestVersion = 0

const providers = ref<LLMProvider[]>([])
const models = ref<LLMModel[]>([])
const serverSnapshot = ref<LLMConfigSummary | null>(null)
const backendReadonly = ref(false)
const testResult = ref<{ success: boolean; message: string; description: string } | null>(null)

const draft = reactive({
  provider_code: '',
  model_code: '',
  temperature: 0.2,
  top_p: 0.9,
  max_tokens: 4000,
  max_parallel_records: 16,
  family_max_concurrency: 4,
  http_max_concurrency: 40,
})

const isAdmin = computed(() => canManageSystemConfig(authStore.userRoles))
const isReadonly = computed(() => backendReadonly.value || !isAdmin.value)
const providerOptions = computed(() =>
  providers.value.map((item) => ({
    label: item.provider_name || item.provider_code,
    value: item.provider_code,
  })),
)
const customModels = computed(() => models.value.filter((item) => item.is_custom))
const canTest = computed(() => !loadingModels.value && Boolean(draft.provider_code && draft.model_code))
const dirty = computed(() => {
  const snap = serverSnapshot.value
  if (!snap) return false
  return (
    draft.provider_code !== snap.provider_code ||
    draft.model_code !== snap.model_code ||
    Number(draft.temperature) !== Number(snap.custom_parameters?.temperature ?? 0.2) ||
    Number(draft.top_p) !== Number(snap.custom_parameters?.top_p ?? 0.9) ||
    Number(draft.max_tokens) !== Number(snap.custom_parameters?.max_tokens ?? 4000) ||
    Number(draft.max_parallel_records) !==
      Number(snap.execution_concurrency?.max_parallel_records ?? 16) ||
    Number(draft.family_max_concurrency) !==
      Number(snap.execution_concurrency?.family_max_concurrency ?? 4) ||
    Number(draft.http_max_concurrency) !==
      Number(snap.execution_concurrency?.http_max_concurrency ?? 40)
  )
})

function patchDraftFromSummary(summary: LLMConfigSummary) {
  draft.provider_code = summary.provider_code
  draft.model_code = summary.model_code
  draft.temperature = Number(summary.custom_parameters?.temperature ?? 0.2)
  draft.top_p = Number(summary.custom_parameters?.top_p ?? 0.9)
  draft.max_tokens = Number(summary.custom_parameters?.max_tokens ?? 4000)
  draft.max_parallel_records = Number(summary.execution_concurrency?.max_parallel_records ?? 16)
  draft.family_max_concurrency = Number(summary.execution_concurrency?.family_max_concurrency ?? 4)
  draft.http_max_concurrency = Number(summary.execution_concurrency?.http_max_concurrency ?? 40)
}

function buildCustomParameters() {
  return {
    ...(serverSnapshot.value?.custom_parameters || {}),
    temperature: Number(draft.temperature),
    top_p: Number(draft.top_p),
    max_tokens: Number(draft.max_tokens),
  }
}

function buildExecutionConcurrency(): LLMExecutionConcurrency {
  return {
    max_parallel_records: Number(draft.max_parallel_records),
    family_max_concurrency: Number(draft.family_max_concurrency),
    http_max_concurrency: Number(draft.http_max_concurrency),
  }
}

async function loadProviders() {
  providers.value = await llmConfigService.getProviders()
}

async function loadModelsByProvider(providerCode: string, preferredModelCode?: string) {
  const requestVersion = ++modelRequestVersion
  const requestedModel = preferredModelCode || draft.model_code
  loadingModels.value = true
  models.value = []
  draft.model_code = ''
  try {
    const loaded = await llmConfigService.getModelsByProvider(providerCode)
    if (requestVersion !== modelRequestVersion || draft.provider_code !== providerCode) return
    models.value = loaded
    if (!models.value.length) {
      draft.model_code = ''
      return
    }
    const next =
      models.value.find((item) => item.model_code === requestedModel)?.model_code ||
      models.value[0].model_code
    draft.model_code = String(next || '')
  } catch (error) {
    if (requestVersion === modelRequestVersion && draft.provider_code === providerCode) throw error
  } finally {
    if (requestVersion === modelRequestVersion) loadingModels.value = false
  }
}

async function reloadAll() {
  loading.value = true
  try {
    const summary = await llmConfigService.getDefaultSummary()
    source.value = summary.source || 'unknown'
    backendReadonly.value = Boolean(summary.readonly)
    serverSnapshot.value = summary
    patchDraftFromSummary(summary)

    await loadProviders()
    if (!draft.provider_code && providers.value.length) {
      draft.provider_code = providers.value[0].provider_code
    }
    await loadModelsByProvider(draft.provider_code, draft.model_code)
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error)
    message.error(`加载模型配置失败：${text}`)
  } finally {
    loading.value = false
  }
}

async function handleProviderChange(value: string) {
  draft.provider_code = value
  testResult.value = null
  try {
    await loadModelsByProvider(value)
  } catch {
    message.error('加载模型列表失败，请重试')
  }
}

async function addCustomModel() {
  const providerCode = draft.provider_code
  const modelCode = newModelCode.value.trim()
  if (!providerCode || !modelCode) return
  addingModel.value = true
  try {
    await llmConfigService.addCustomModel(providerCode, modelCode, modelCode)
    await loadModelsByProvider(providerCode, modelCode)
    newModelCode.value = ''
    message.success('自定义模型添加成功')
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error)
    message.error(`添加模型失败：${text}`)
  } finally {
    addingModel.value = false
  }
}

async function removeCustomModel(model: LLMModel) {
  const providerCode = draft.provider_code
  const modelCode = String(model.model_code || '').trim()
  if (!providerCode || !modelCode) return
  deletingModelCode.value = modelCode
  try {
    await llmConfigService.deleteCustomModel(providerCode, modelCode)
    const preferred = draft.model_code === modelCode ? '' : draft.model_code
    await loadModelsByProvider(providerCode, preferred)
    message.success('自定义模型已删除')
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error)
    message.error(`删除模型失败：${text}`)
  } finally {
    deletingModelCode.value = ''
  }
}

async function testConnection() {
  if (!canTest.value) return
  testing.value = true
  testResult.value = null
  try {
    const result = await llmConfigService.testConfig({
      provider_code: draft.provider_code,
      model_code: draft.model_code,
      custom_parameters: buildCustomParameters(),
    })
    testResult.value = {
      success: true,
      message: '连接测试成功',
      description: `${result.provider_code} / ${result.model} 已联通`,
    }
    message.success('连接测试成功')
  } catch {
    testResult.value = {
      success: false,
      message: '连接测试失败',
      description: '连接未成功，请检查模型服务配置或联系实施人员。',
    }
    message.error('连接测试失败，请检查模型服务配置')
  } finally {
    testing.value = false
  }
}

async function saveDraft() {
  if (isReadonly.value || loadingModels.value || !canTest.value || !dirty.value) return
  saving.value = true
  try {
    const payload: LLMConfigInput = {
      config_name: 'default',
      provider_code: draft.provider_code,
      model_code: draft.model_code,
      custom_parameters: buildCustomParameters(),
      execution_concurrency: buildExecutionConcurrency(),
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

    await reloadAll()
    const eventPayload = {
      selectedProviderCode: draft.provider_code,
      selectedModelCode: draft.model_code,
      custom_parameters: buildCustomParameters(),
      timestamp: Date.now(),
    }
    window.dispatchEvent(new CustomEvent('llm-config-updated', { detail: eventPayload }))
    emit('config-updated', saved || eventPayload)
    message.success('LLM 配置保存成功')
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error)
    message.error(`保存配置失败：${text}`)
  } finally {
    saving.value = false
  }
}

async function resetDefault() {
  saving.value = true
  try {
    const summary = await llmConfigService.resetDefaultSummary()
    source.value = summary.source || 'database+env'
    backendReadonly.value = Boolean(summary.readonly)
    serverSnapshot.value = summary
    patchDraftFromSummary(summary)
    await loadModelsByProvider(draft.provider_code, draft.model_code)

    const reloadResponse = await authFetch('/api/v1/qc/sichuan/reload-config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!reloadResponse.ok) {
      throw new Error(`后端配置重载失败: ${reloadResponse.status}`)
    }
    message.success('已恢复默认配置')
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error)
    message.error(`恢复默认失败：${text}`)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void reloadAll()
})
onBeforeUnmount(() => { ++modelRequestVersion })
</script>

<style scoped>
.ds-root {
  max-width: 1100px;
  padding: 4px 2px 16px;
}

.ds-split {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

@media (min-width: 960px) {
  .ds-split {
    grid-template-columns: 280px 1fr;
    gap: 18px;
  }
}

.ds-aside-card {
  position: sticky;
  top: 12px;
  padding: 16px 14px;
  border: 1px solid #d8e3f2;
  border-radius: 18px;
  background:
    radial-gradient(circle at top right, rgba(96, 165, 250, 0.18), transparent 36%),
    linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.06);
}

.ds-aside-eyebrow {
  margin-bottom: 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: #2563eb;
}

.ds-section-title {
  font-size: 21px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
  margin: 0 0 8px;
}

.ds-section-desc {
  margin: 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.65;
}

.ds-meta-list {
  margin-top: 12px;
  display: grid;
  gap: 8px;
}

.ds-meta-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.92);
}

.ds-meta__label {
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}

.ds-aside-note {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.ds-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
  padding: 14px 16px;
  border: 1px solid #dbe7f5;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(239, 246, 255, 0.95), rgba(248, 250, 252, 0.98)), #fff;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
}

.ds-hero__label {
  margin-bottom: 4px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #2563eb;
}

.ds-hero__title {
  font-size: 18px;
  line-height: 1.25;
  font-weight: 700;
  color: #0f172a;
}

.ds-hero__desc {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

.ds-card {
  background: #fff;
  border: 1px solid #dbe7f5;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.06);
}

.ds-divide > * {
  border-bottom: 1px solid #f1f5f9;
}

.ds-divide > *:last-child {
  border-bottom: none;
}

.ds-group {
  padding: 2px 0;
}

.ds-group__title {
  font-size: 12px;
  font-weight: 700;
  color: #2563eb;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 12px 16px 6px;
}

.ds-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 10px 16px;
}

.ds-row--top {
  align-items: flex-start;
}

.ds-row--result {
  background: #fbfdff;
}

.ds-row__left {
  min-width: 0;
  flex: 1;
}

.ds-row__label {
  font-size: 13px;
  color: #0f172a;
  font-weight: 600;
}

.ds-row__hint {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.55;
  color: #94a3b8;
}

.slider-wrap {
  width: 360px;
  padding: 8px 12px 4px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: linear-gradient(180deg, #fff 0%, #f8fafc 100%);
}

.slider-value {
  text-align: right;
  font-size: 12px;
  color: #2563eb;
  font-weight: 700;
  margin-bottom: 4px;
}

.custom-model-panel {
  width: 360px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: linear-gradient(180deg, #fff 0%, #fbfdff 100%);
}

.custom-model-list {
  margin-top: 6px;
  border: 1px solid #edf2f7;
  border-radius: 8px;
  padding: 4px 8px;
  background: #fff;
}

.custom-model-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 30px;
}

.custom-model-empty {
  margin-top: 6px;
  font-size: 12px;
  color: #94a3b8;
}

.ds-select :deep(.ant-select-selector),
.ds-input :deep(.ant-input),
.ds-input-number :deep(.ant-input-number) {
  border-radius: 12px !important;
}

.ds-test-btn {
  border-radius: 12px;
}

.ds-card__footer {
  padding: 10px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(180deg, #fcfdff 0%, #f8fafc 100%);
  border-top: 1px solid #e2e8f0;
}

.ds-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ds-footer-meta {
  font-size: 12px;
  color: #94a3b8;
}

.ml-1 {
  margin-left: 6px;
}

@media (max-width: 959px) {
  .ds-aside-card {
    position: static;
  }

  .ds-hero,
  .ds-row,
  .ds-card__footer {
    flex-direction: column;
    align-items: stretch;
  }

  .slider-wrap,
  .custom-model-panel {
    width: 100%;
  }
}
</style>
