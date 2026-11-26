<template>
  <div
    class="llm-settings"
    data-testid="llm-settings-v71"
  >
    <section
      class="mq-card mq-card--padded llm-overview"
      aria-labelledby="llm-settings-title"
    >
      <header class="mq-card__head llm-overview__head">
        <div>
          <h2
            id="llm-settings-title"
            class="mq-card__title"
          >
            模型配置治理
          </h2>
          <p class="mq-card__desc">
            选择默认推理模型，并按质控用途分配模型。超级管理员可管理直连服务地址与密钥，未覆盖时沿用部署配置。
          </p>
        </div>
        <span
          class="mq-status"
          :class="dirty ? 'mq-status--warning' : ''"
          role="status"
        >
          {{ loading ? '正在读取' : dirty ? '草稿未保存' : '已同步' }}
        </span>
      </header>
      <dl class="mq-soft llm-summary">
        <div>
          <dt>默认模型</dt>
          <dd class="mq-mono">
            {{ draft.model_code || '未选择模型' }}
          </dd>
        </div>
        <div>
          <dt>角色分工</dt>
          <dd>{{ Object.values(taskRoles).filter((role) => !role).length }} / 3 项继承默认</dd>
        </div>
        <div>
          <dt>配置来源</dt>
          <dd>
            {{
              source === 'env' ? '部署配置' : source.includes('database') ? '已保存配置' : '待确认'
            }}
          </dd>
        </div>
      </dl>
    </section>

    <a-alert
      v-if="isReadonly"
      type="info"
      show-icon
      message="当前为只读模式"
      description="仅系统配置管理员可修改并保存模型配置。"
    />

    <a-alert
      v-if="providerUnavailable"
      data-testid="provider-unavailable-alert"
      type="warning"
      show-icon
      message="当前默认推理服务不可用"
      :description="providerUnavailableDescription"
    />

    <LLMEndpointSettings @saved="reloadAll" />

    <ol
      class="llm-steps"
      aria-label="模型配置步骤"
    >
      <li class="mq-card mq-card--padded llm-step">
        <span
          class="llm-step__number"
          aria-hidden="true"
        >01</span>
        <section
          class="llm-step__content"
          aria-labelledby="llm-default-title"
        >
          <header class="llm-section-head">
            <h3
              id="llm-default-title"
              class="llm-section-title"
            >
              默认推理服务与模型
            </h3>
            <p class="mq-field__hint">
              未单独指定用途时，使用这里选择的模型。
            </p>
          </header>
          <div class="llm-default-fields">
            <div class="mq-field llm-field--wide">
              <span class="mq-field__label">推理方式</span>
              <a-segmented
                class="llm-inference-mode"
                :value="inferenceMode"
                :options="inferenceModeOptions"
                :disabled="isReadonly || loading || saving"
                @change="handleInferenceModeChange"
              />
            </div>
            <div class="mq-field">
              <label
                for="llm-default-provider"
                class="mq-field__label"
              >推理服务</label>
              <a-select
                id="llm-default-provider"
                v-model:value="draft.provider_code"
                class="llm-control"
                :disabled="isReadonly || loading || saving"
                :options="providerOptions"
                @change="handleProviderChange"
              />
            </div>
            <div class="mq-field">
              <label
                for="llm-default-model"
                class="mq-field__label"
              >默认模型</label>
              <a-select
                id="llm-default-model"
                v-model:value="draft.model_code"
                class="llm-control"
                show-search
                option-filter-prop="label"
                :placeholder="inferenceMode === 'local' ? '选择已登记的本地模型' : '选择模型'"
                :loading="loadingModels"
                :disabled="isReadonly || loadingModels || saving || !models.length"
              >
                <a-select-option
                  v-for="item in models"
                  :key="item.model_code"
                  :value="item.model_code"
                  :label="item.model_name"
                >
                  {{ item.model_name }}
                  <span
                    v-if="item.is_custom"
                    class="mq-status llm-custom-badge"
                  >自定义</span>
                </a-select-option>
              </a-select>
            </div>
          </div>
          <a-alert
            v-if="inferenceMode === 'local'"
            data-testid="local-model-status"
            :type="selectionUnavailable ? 'warning' : 'info'"
            show-icon
            :message="selectionUnavailable ? '本地模型尚未就绪' : '本地模型配置已就绪'"
            :description="localSelectionDescription"
            class="llm-local-status"
          />

          <details class="llm-disclosure llm-model-management">
            <summary>
              <span>{{ inferenceMode === 'local' ? '本地模型管理' : '自定义模型' }}</span>
              <span class="mq-field__hint">{{ customModels.length }} 个自定义模型</span>
            </summary>
            <div class="llm-disclosure__body">
              <p class="mq-field__hint">
                {{
                  inferenceMode === 'local'
                    ? '填写服务实际接受的模型 ID，保留大小写。添加后仍需保存才能切换。'
                    : '内置模型不可删除；新增模型名称不会更改 API 地址和密钥。'
                }}
              </p>
              <div class="llm-add-model">
                <a-input
                  v-model:value="newModelCode"
                  class="llm-control"
                  :disabled="
                    isReadonly || loading || saving || addingModel || Boolean(deletingModelCode)
                  "
                  :placeholder="
                    inferenceMode === 'local'
                      ? '输入本地服务实际模型 ID'
                      : '输入模型名，如 Qwen/Qwen3.5-14B'
                  "
                  @press-enter="addCustomModel"
                />
                <a-button
                  class="mq-btn"
                  :disabled="
                    isReadonly ||
                      loading ||
                      saving ||
                      addingModel ||
                      Boolean(deletingModelCode) ||
                      !newModelCode.trim()
                  "
                  :loading="addingModel"
                  @click="addCustomModel"
                >
                  添加
                </a-button>
              </div>
              <ul
                v-if="customModels.length"
                class="llm-custom-models"
              >
                <li
                  v-for="item in customModels"
                  :key="`custom-${item.model_code}`"
                >
                  <span class="mq-mono">{{ item.model_name }}</span>
                  <a-button
                    type="link"
                    size="small"
                    danger
                    :disabled="
                      isReadonly || loading || saving || addingModel || Boolean(deletingModelCode)
                    "
                    :loading="deletingModelCode === item.model_code"
                    @click="removeCustomModel(item)"
                  >
                    删除
                  </a-button>
                </li>
              </ul>
              <p
                v-else
                class="mq-field__hint"
              >
                {{
                  inferenceMode === 'local'
                    ? '尚未登记其他本地模型，可在上方添加。'
                    : '当前厂商暂无自定义模型'
                }}
              </p>
            </div>
          </details>
        </section>
      </li>

      <li class="mq-card mq-card--padded llm-step">
        <span
          class="llm-step__number"
          aria-hidden="true"
        >02</span>
        <section
          class="llm-step__content"
          aria-label="按任务用途选模型"
        >
          <LLMTaskRoleSettings
            v-model:value="taskRoles"
            :providers="providers"
            :local-providers="localProviders"
            :default-provider="draft.provider_code"
            :disabled="isReadonly || loading || saving"
            :catalog-refresh="roleCatalogRefresh"
          />
          <a-alert
            v-if="rolesIncomplete"
            type="warning"
            show-icon
            message="请补齐角色模型选择，并确认本地部署配置已就绪。"
            class="llm-local-status"
          />
        </section>
      </li>

      <li class="mq-card mq-card--padded llm-step">
        <span
          class="llm-step__number"
          aria-hidden="true"
        >03</span>
        <details
          class="llm-disclosure llm-step__content"
          data-testid="llm-advanced-settings"
        >
          <summary>
            <span class="llm-section-title">参数与执行并发</span>
            <span class="mq-field__hint">输出参数、病历并发与模型槽位</span>
          </summary>
          <div class="llm-disclosure__body llm-advanced-fields">
            <div class="llm-parameter-group">
              <h4 class="llm-parameter-title">
                高级参数
              </h4>

              <div class="llm-parameter-row">
                <div class="mq-field">
                  <div class="mq-field__label">
                    Temperature
                  </div>
                  <div class="mq-field__hint">
                    控制输出随机性，值越高越发散。
                  </div>
                </div>
                <div class="slider-wrap">
                  <div class="slider-value">
                    {{ Number(draft.temperature ?? 0.2).toFixed(1) }}
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

              <div class="llm-parameter-row">
                <div class="mq-field">
                  <div class="mq-field__label">
                    Top P
                  </div>
                  <div class="mq-field__hint">
                    核采样阈值，控制候选词覆盖范围。
                  </div>
                </div>
                <div class="slider-wrap">
                  <div class="slider-value">
                    {{ Number(draft.top_p ?? 0.9).toFixed(1) }}
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

              <div class="llm-parameter-row">
                <div class="mq-field">
                  <div class="mq-field__label">
                    Max Tokens
                  </div>
                  <div class="mq-field__hint">
                    单次请求最大输出 token 数。
                  </div>
                </div>
                <a-input-number
                  v-model:value="draft.max_tokens"
                  class="llm-control"
                  :disabled="isReadonly || loading"
                  :min="1000"
                  :max="32768"
                  :step="1000"
                  @blur="normalizeNumericDraftField('max_tokens')"
                />
              </div>
            </div>
            <div class="llm-parameter-group">
              <h4 class="llm-parameter-title">
                执行并发
              </h4>

              <div class="llm-parameter-row">
                <div class="mq-field">
                  <div class="mq-field__label">
                    同时处理病历数
                  </div>
                  <div class="mq-field__hint">
                    单个质控任务同时进入执行链的病历上限。
                  </div>
                </div>
                <a-input-number
                  v-model:value="draft.max_parallel_records"
                  class="llm-control"
                  :disabled="isReadonly || loading"
                  :min="1"
                  :max="32"
                  :step="1"
                  @blur="normalizeNumericDraftField('max_parallel_records')"
                />
              </div>

              <div class="llm-parameter-row">
                <div class="mq-field">
                  <div class="mq-field__label">
                    单病历规则族并发
                  </div>
                  <div class="mq-field__hint">
                    每份病历可同时执行的独立规则族数量，当前安全上限为 4。
                  </div>
                </div>
                <a-input-number
                  v-model:value="draft.family_max_concurrency"
                  class="llm-control"
                  :disabled="isReadonly || loading"
                  :min="1"
                  :max="4"
                  :step="1"
                  @blur="normalizeNumericDraftField('family_max_concurrency')"
                />
              </div>

              <div class="llm-parameter-row">
                <div class="mq-field">
                  <div class="mq-field__label">
                    全局模型 HTTP 槽位
                  </div>
                  <div class="mq-field__hint">
                    客户端 HTTP 请求上限；网关另按服务资源限流，本地 Strata 容量由部署配置控制。
                  </div>
                </div>
                <a-input-number
                  v-model:value="draft.http_max_concurrency"
                  class="llm-control"
                  :disabled="isReadonly || loading"
                  :min="1"
                  :max="64"
                  :step="1"
                  @blur="normalizeNumericDraftField('http_max_concurrency')"
                />
              </div>
            </div>
          </div>
        </details>
      </li>
    </ol>

    <footer
      class="mq-card mq-card--padded llm-actions"
      aria-label="模型配置操作"
    >
      <div class="llm-actions__copy">
        <p>修改仅对新任务生效</p>
        <span class="mq-field__hint">连接测试会实际请求默认模型；保存只校验配置。</span>
        <span
          v-if="testResult"
          role="status"
          class="mq-status"
          :class="testResult.success ? 'mq-status--success' : 'mq-status--danger'"
        >
          {{ testResult.success ? '连接成功' : '连接失败' }}：{{ testResult.description }}
        </span>
      </div>
      <div class="llm-actions__buttons">
        <a-button
          class="mq-btn"
          :disabled="loading || saving || resetting"
          @click="reloadAll"
        >
          刷新
        </a-button>
        <a-button
          class="mq-btn"
          data-testid="llm-reset-default"
          :loading="resetting"
          :disabled="isReadonly || loading || saving || resetting || testing"
          @click="resetDefault"
        >
          恢复默认
        </a-button>
        <a-button
          class="mq-btn"
          :loading="testing"
          :disabled="!canTest || resetting"
          @click="testConnection"
        >
          测试连接
        </a-button>
        <a-button
          class="mq-btn mq-btn--primary"
          type="primary"
          :loading="saving"
          :disabled="isReadonly || loading || resetting || !canTest || !dirty"
          @click="saveDraft"
        >
          保存配置
        </a-button>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, getCurrentInstance, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import * as vueRouter from 'vue-router'
import { message } from 'ant-design-vue'

import { useWorkstationConfirmation } from '@/components/layout/workstationConfirmation'
import { useAuthStore } from '@/stores/auth'
import { canManageSystemConfig } from '@/utils/systemConfigAccess'
import {
  llmConfigService,
  type LLMConfigInput,
  type LLMConfigSummary,
  type LLMExecutionConcurrency,
  type LLMModel,
  type LLMProvider,
  type LLMLocalProvider,
  type LLMTaskRoleModels,
} from '@/services/llmConfigService'
import LLMTaskRoleSettings from './LLMTaskRoleSettings.vue'
import LLMEndpointSettings from './LLMEndpointSettings.vue'
import { authFetch } from '@/utils/auth-fetch'

const emit = defineEmits<{
  'config-updated': [configData: unknown]
  'close-drawer': []
  'close-modal': []
  'dirty-change': [dirty: boolean]
}>()

const authStore = useAuthStore()
const workstationConfirmation = useWorkstationConfirmation()
const loading = ref(false)
const loadingModels = ref(false)
const saving = ref(false)
const resetting = ref(false)
const confirmPending = ref(false)
const testing = ref(false)
const addingModel = ref(false)
const deletingModelCode = ref('')
const newModelCode = ref('')
const source = ref('unknown')
let disposed = false
let modelRequestVersion = 0
let reloadRequestVersion = 0
let reloadController: AbortController | null = null
let modelController: AbortController | null = null
let mutationController: AbortController | null = null
let roleCatalogRefreshSeq = 0
const roleCatalogRefresh = ref<{ provider: string; version: number } | null>(null)

function notifyRoleCatalogChanged(providerCode: string) {
  if (!providerCode || isLocalProvider(providerCode)) return
  roleCatalogRefresh.value = { provider: providerCode, version: ++roleCatalogRefreshSeq }
}

type LLMConfigSummaryWithStatus = LLMConfigSummary & {
  provider_unavailable?: boolean
  provider_unavailable_reason?: string | null
  api_key_configured?: boolean
}

const providers = ref<Array<Pick<LLMProvider, 'provider_code' | 'provider_name'>>>([])
const localProviders = ref<LLMLocalProvider[]>([])
const localOptionsError = ref('')
const inferenceMode = ref<'cloud' | 'local'>('cloud')
const inferenceModeOptions = [
  { label: '云端 API', value: 'cloud' },
  { label: '本地推理', value: 'local' },
]
const isLocalProvider = (code: string) => code === 'strata' || code === 'ollama'
const models = ref<LLMModel[]>([])
const serverSnapshot = ref<LLMConfigSummaryWithStatus | null>(null)
const backendReadonly = ref(false)
const testResult = ref<{ success: boolean; message: string; description: string } | null>(null)

const providerUnavailable = computed(() => Boolean(serverSnapshot.value?.provider_unavailable))
const providerUnavailableDescription = computed(() => {
  const providerCode = serverSnapshot.value?.provider_code || '默认服务'
  const reason = String(serverSnapshot.value?.provider_unavailable_reason || '').trim()
  const reasonNote = reason ? `（原因：${reason}）` : ''
  return `当前已保存或默认的推理服务「${providerCode}」已被禁用或配置不可用${reasonNote}。您可以在上方「推理服务连接」中重新启用该服务，或在下方切换至其他已启用的推理服务与模型并保存配置。`
})

const inheritedRoles = (): LLMTaskRoleModels => ({ fact_extraction: null, judgment_analysis: null, specialty_verification: null })
const cloneRoles = (value: LLMTaskRoleModels = inheritedRoles()): LLMTaskRoleModels => ({
  fact_extraction: value.fact_extraction ? { ...value.fact_extraction } : null,
  judgment_analysis: value.judgment_analysis ? { ...value.judgment_analysis } : null,
  specialty_verification: value.specialty_verification ? { ...value.specialty_verification } : null,
})
const taskRoles = ref<LLMTaskRoleModels>(inheritedRoles())
const rolesIncomplete = computed(() => Object.values(taskRoles.value).some((spec) => {
  if (!spec) return false
  if (!spec.provider_code || !spec.model_code) return true
  if (isLocalProvider(draft.provider_code) && !isLocalProvider(spec.provider_code)) return true
  if (!isLocalProvider(spec.provider_code)) return false
  return localProviders.value.find((item) => item.provider_code === spec.provider_code)?.models
    .find((item) => item.model_code === spec.model_code)?.configuration_ready !== true
}))
const draft = reactive({
  provider_code: '',
  model_code: '',
  temperature: 0.2,
  top_p: 0.9,
  max_tokens: 4000 as number | null,
  max_parallel_records: 16 as number | null,
  family_max_concurrency: 4 as number | null,
  http_max_concurrency: 40 as number | null,
})

function resolveBoundedInt(value: unknown, fallback: number, min: number, max: number): number {
  if (value === null || value === undefined || value === '') return fallback
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return fallback
  return Math.min(max, Math.max(min, Math.trunc(parsed)))
}

function resolveBoundedFloat(value: unknown, fallback: number, min: number, max: number): number {
  if (value === null || value === undefined || value === '') return fallback
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return fallback
  return Math.min(max, Math.max(min, parsed))
}

function snapshotNumericDefaults() {
  const snap = serverSnapshot.value
  return {
    temperature: resolveBoundedFloat(snap?.custom_parameters?.temperature, 0.2, 0, 2),
    top_p: resolveBoundedFloat(snap?.custom_parameters?.top_p, 0.9, 0, 1),
    max_tokens: resolveBoundedInt(snap?.custom_parameters?.max_tokens, 4000, 1000, 32768),
    max_parallel_records: resolveBoundedInt(
      snap?.execution_concurrency?.max_parallel_records,
      16,
      1,
      32,
    ),
    family_max_concurrency: resolveBoundedInt(
      snap?.execution_concurrency?.family_max_concurrency,
      4,
      1,
      4,
    ),
    http_max_concurrency: resolveBoundedInt(
      snap?.execution_concurrency?.http_max_concurrency,
      40,
      1,
      64,
    ),
  }
}

function normalizeNumericDraftField(
  field: 'max_tokens' | 'max_parallel_records' | 'family_max_concurrency' | 'http_max_concurrency',
) {
  const defaults = snapshotNumericDefaults()
  const bounds: Record<typeof field, [number, number]> = {
    max_tokens: [1000, 32768],
    max_parallel_records: [1, 32],
    family_max_concurrency: [1, 4],
    http_max_concurrency: [1, 64],
  }
  const [min, max] = bounds[field]
  draft[field] = resolveBoundedInt(draft[field], defaults[field], min, max)
}

const isAdmin = computed(() => canManageSystemConfig(authStore.userRoles))
const isReadonly = computed(() => backendReadonly.value || !isAdmin.value)
const providerOptions = computed(() =>
  providers.value.filter((item) => isLocalProvider(item.provider_code) === (inferenceMode.value === 'local')).map((item) => ({
    label: item.provider_name || item.provider_code,
    value: item.provider_code,
  })),
)
const customModels = computed(() => models.value.filter((item) => item.is_custom))
const selectedLocalProvider = computed(() => localProviders.value.find((item) => item.provider_code === draft.provider_code))
const selectedLocalModel = computed(() => selectedLocalProvider.value?.models.find((item) => item.model_code === draft.model_code))
const selectionUnavailable = computed(() => isLocalProvider(draft.provider_code) && selectedLocalModel.value?.configuration_ready !== true)
const localSelectionDescription = computed(() => {
  const failureNote = '本地服务不可用时不会自动切到云端。'
  if (localOptionsError.value) return localOptionsError.value
  if (!selectedLocalProvider.value?.enabled) return `该本地推理服务尚未启用，可由超级管理员配置直连服务。可以先登记模型名称；启用前不能保存为当前推理服务或测试连接。${failureNote}`
  if (!models.value.length) return `尚无本地模型，请添加服务实际接受的模型 ID。添加名称不会下载模型或启动服务。${failureNote}`
  if (selectionUnavailable.value) return `所选模型的 API 地址或运行配置尚未齐备，请联系实施人员。模型名称已保留，当前生效配置不受影响。${failureNote}`
  return `可选择并保存此本地模型；API 地址和密钥使用当前有效连接配置。连接状态尚未验证，测试连接会实际请求模型服务。${failureNote}`
})
const canTest = computed(() => !isReadonly.value && !loading.value && !saving.value && !addingModel.value && !deletingModelCode.value && !loadingModels.value && !selectionUnavailable.value && !rolesIncomplete.value && Boolean(draft.provider_code && draft.model_code))
const dirty = computed(() => {
  const snap = serverSnapshot.value
  if (!snap) return false
  const defaults = snapshotNumericDefaults()
  return (
    JSON.stringify(taskRoles.value) !== JSON.stringify(snap.custom_parameters?.task_role_models || inheritedRoles()) ||
    draft.provider_code !== snap.provider_code ||
    draft.model_code !== snap.model_code ||
    resolveBoundedFloat(draft.temperature, defaults.temperature, 0, 2) !== defaults.temperature ||
    resolveBoundedFloat(draft.top_p, defaults.top_p, 0, 1) !== defaults.top_p ||
    resolveBoundedInt(draft.max_tokens, defaults.max_tokens, 1000, 32768) !== defaults.max_tokens ||
    resolveBoundedInt(draft.max_parallel_records, defaults.max_parallel_records, 1, 32) !==
      defaults.max_parallel_records ||
    resolveBoundedInt(draft.family_max_concurrency, defaults.family_max_concurrency, 1, 4) !==
      defaults.family_max_concurrency ||
    resolveBoundedInt(draft.http_max_concurrency, defaults.http_max_concurrency, 1, 64) !==
      defaults.http_max_concurrency
  )
})

function patchDraftFromSummary(summary: LLMConfigSummaryWithStatus) {
  taskRoles.value = cloneRoles(summary.custom_parameters?.task_role_models)
  draft.provider_code = summary.provider_code
  inferenceMode.value = isLocalProvider(summary.provider_code) ? 'local' : 'cloud'
  draft.model_code = summary.model_code
  draft.temperature = resolveBoundedFloat(summary.custom_parameters?.temperature, 0.2, 0, 2)
  draft.top_p = resolveBoundedFloat(summary.custom_parameters?.top_p, 0.9, 0, 1)
  draft.max_tokens = resolveBoundedInt(summary.custom_parameters?.max_tokens, 4000, 1000, 32768)
  draft.max_parallel_records = resolveBoundedInt(
    summary.execution_concurrency?.max_parallel_records,
    16,
    1,
    32,
  )
  draft.family_max_concurrency = resolveBoundedInt(
    summary.execution_concurrency?.family_max_concurrency,
    4,
    1,
    4,
  )
  draft.http_max_concurrency = resolveBoundedInt(
    summary.execution_concurrency?.http_max_concurrency,
    40,
    1,
    64,
  )
}

function buildCustomParameters() {
  const defaults = snapshotNumericDefaults()
  return {
    ...(serverSnapshot.value?.custom_parameters || {}),
    task_role_models: cloneRoles(taskRoles.value),
    temperature: resolveBoundedFloat(draft.temperature, defaults.temperature, 0, 2),
    top_p: resolveBoundedFloat(draft.top_p, defaults.top_p, 0, 1),
    max_tokens: resolveBoundedInt(draft.max_tokens, defaults.max_tokens, 1000, 32768),
  }
}

function buildExecutionConcurrency(): LLMExecutionConcurrency {
  const defaults = snapshotNumericDefaults()
  return {
    max_parallel_records: resolveBoundedInt(
      draft.max_parallel_records,
      defaults.max_parallel_records,
      1,
      32,
    ),
    family_max_concurrency: resolveBoundedInt(
      draft.family_max_concurrency,
      defaults.family_max_concurrency,
      1,
      4,
    ),
    http_max_concurrency: resolveBoundedInt(
      draft.http_max_concurrency,
      defaults.http_max_concurrency,
      1,
      64,
    ),
  }
}

async function loadProviders(signal?: AbortSignal) {
  providers.value = await llmConfigService.getProviders(signal ? { signal } : undefined)
  if (disposed || signal?.aborted) return
  // 本地目录包含未启用的服务，但不改变服务端的运行准入。
  try {
    await refreshLocalProviders(signal)
  } catch (error) {
    if (disposed || signal?.aborted) throw error
    localProviders.value = []
    localOptionsError.value = '本地模型选项读取失败，请刷新重试。云端配置仍可使用。'
  }
  if (disposed || signal?.aborted) return
  for (const item of localProviders.value) {
    if (!providers.value.some((provider) => provider.provider_code === item.provider_code)) {
      providers.value.push({ provider_code: item.provider_code, provider_name: item.provider_name })
    }
  }
}

async function refreshLocalProviders(signal?: AbortSignal) {
  localProviders.value = await llmConfigService.getLocalModelOptions(signal ? { signal } : undefined)
  localOptionsError.value = ''
}

async function loadModelsByProvider(
  providerCode: string,
  preferredModelCode?: string,
  signal?: AbortSignal,
) {
  const requestVersion = ++modelRequestVersion
  modelController?.abort()
  const controller = new AbortController()
  modelController = controller
  const onOuterAbort = () => controller.abort(signal?.reason)
  if (signal) {
    if (signal.aborted) {
      controller.abort(signal.reason)
    } else {
      signal.addEventListener('abort', onOuterAbort, { once: true })
    }
  }
  const requestedModel = preferredModelCode || draft.model_code
  loadingModels.value = true
  models.value = []
  draft.model_code = ''
  try {
    const loaded = isLocalProvider(providerCode)
      ? localProviders.value.find((item) => item.provider_code === providerCode)?.models || []
      : await llmConfigService.getModelsByProvider(providerCode, { signal: controller.signal })
    if (
      disposed ||
      requestVersion !== modelRequestVersion ||
      controller.signal.aborted ||
      draft.provider_code !== providerCode
    ) {
      return
    }
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
    if (
      !disposed &&
      !controller.signal.aborted &&
      requestVersion === modelRequestVersion &&
      draft.provider_code === providerCode
    ) {
      throw error
    }
  } finally {
    signal?.removeEventListener('abort', onOuterAbort)
    if (modelController === controller) {
      modelController = null
    }
    if (!disposed && requestVersion === modelRequestVersion) loadingModels.value = false
  }
}

async function reloadAll() {
  const version = ++reloadRequestVersion
  reloadController?.abort()
  const controller = new AbortController()
  reloadController = controller
  loading.value = true
  try {
    const summary = await llmConfigService.getDefaultSummary({ signal: controller.signal })
    if (disposed || version !== reloadRequestVersion || controller.signal.aborted) return
    source.value = summary.source || 'unknown'
    backendReadonly.value = Boolean(summary.readonly)
    serverSnapshot.value = summary
    patchDraftFromSummary(summary)

    await loadProviders(controller.signal)
    if (disposed || version !== reloadRequestVersion || controller.signal.aborted) return
    if (!draft.provider_code && providers.value.length) {
      draft.provider_code = providers.value[0].provider_code
    }
    await loadModelsByProvider(draft.provider_code, draft.model_code, controller.signal)
  } catch (error) {
    if (disposed || version !== reloadRequestVersion || controller.signal.aborted) return
    const text = error instanceof Error ? error.message : String(error)
    message.error(`加载模型配置失败：${text}`)
  } finally {
    if (!disposed && version === reloadRequestVersion && reloadController === controller) {
      loading.value = false
      reloadController = null
    }
  }
}

async function handleProviderChange(value: string) {
  draft.provider_code = value
  inferenceMode.value = isLocalProvider(value) ? 'local' : 'cloud'
  testResult.value = null
  try {
    const savedModel = serverSnapshot.value?.provider_code === value ? serverSnapshot.value.model_code : undefined
    await loadModelsByProvider(value, savedModel)
  } catch {
    message.error('加载模型列表失败，请重试')
  }
}

async function handleInferenceModeChange(value: string | number) {
  if (value !== 'cloud' && value !== 'local') return
  inferenceMode.value = value
  const saved = serverSnapshot.value?.provider_code
  const next = providerOptions.value.find((item) => item.value === saved)?.value || providerOptions.value[0]?.value || ''
  await handleProviderChange(next)
  // 目录请求失败时没有可选服务，仍保留用户选择的模式与错误提示。
  inferenceMode.value = value
}

async function addCustomModel() {
  const providerCode = draft.provider_code
  const modelCode = newModelCode.value.trim()
  if (isReadonly.value || addingModel.value || deletingModelCode.value || !providerCode || !modelCode) return
  addingModel.value = true
  try {
    await llmConfigService.addCustomModel(providerCode, modelCode, modelCode)
    if (isLocalProvider(providerCode)) {
      await refreshLocalProviders()
    } else {
      notifyRoleCatalogChanged(providerCode)
    }
    if (draft.provider_code === providerCode) {
      await loadModelsByProvider(providerCode, modelCode)
      newModelCode.value = ''
    }
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
  if (isReadonly.value || addingModel.value || deletingModelCode.value || !providerCode || !modelCode) return
  deletingModelCode.value = modelCode
  try {
    await llmConfigService.deleteCustomModel(providerCode, modelCode)
    if (isLocalProvider(providerCode)) {
      await refreshLocalProviders()
    } else {
      notifyRoleCatalogChanged(providerCode)
    }
    const nextRoles = cloneRoles(taskRoles.value)
    let roleCleared = false
    for (const key of Object.keys(nextRoles) as Array<keyof LLMTaskRoleModels>) {
      const spec = nextRoles[key]
      if (spec && spec.provider_code === providerCode && spec.model_code === modelCode) {
        nextRoles[key] = { ...spec, model_code: '' }
        roleCleared = true
      }
    }
    if (roleCleared) {
      taskRoles.value = nextRoles
    }
    if (draft.provider_code === providerCode) {
      const preferred = draft.model_code === modelCode ? '' : draft.model_code
      await loadModelsByProvider(providerCode, preferred)
    }
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
  if (isReadonly.value || loadingModels.value || saving.value || resetting.value || !canTest.value || !dirty.value) return
  reloadController?.abort()
  reloadController = null
  mutationController?.abort()
  const saveController = new AbortController()
  mutationController = saveController
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
    const saved = await llmConfigService.saveConfig(payload, { signal: saveController.signal })
    if (disposed || saveController.signal.aborted) return

    const reloadResponse = await authFetch('/api/v1/qc/sichuan/reload-config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: saveController.signal,
    })
    if (disposed || saveController.signal.aborted) return
    if (!reloadResponse.ok) {
      throw new Error(`后端配置重载失败: ${reloadResponse.status}`)
    }

    await reloadAll()
    if (disposed || saveController.signal.aborted) return
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
    if (disposed || saveController.signal.aborted) return
    const text = error instanceof Error ? error.message : String(error)
    message.error(`保存配置失败：${text}`)
  } finally {
    if (mutationController === saveController) mutationController = null
    if (!disposed) saving.value = false
  }
}

async function resetDefault() {
  if (
    isReadonly.value ||
    loading.value ||
    saving.value ||
    resetting.value ||
    testing.value ||
    confirmPending.value
  ) {
    return
  }

  confirmPending.value = true
  let confirmed = false
  try {
    confirmed = await new Promise<boolean>((resolve) => {
      workstationConfirmation.confirm({
        title: '确认恢复默认模型配置？',
        content: '将把默认推理服务、模型、任务角色分工与执行并发参数恢复为系统默认，未保存草稿将被覆盖。',
        okText: '确认恢复',
        cancelText: '取消',
        okType: 'danger',
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      })
    })
  } finally {
    confirmPending.value = false
  }
  if (!confirmed || disposed || isReadonly.value || saving.value || resetting.value) return

  reloadController?.abort()
  reloadController = null
  mutationController?.abort()
  const resetController = new AbortController()
  mutationController = resetController
  resetting.value = true
  try {
    const summary = (await llmConfigService.resetDefaultSummary({
      signal: resetController.signal,
    })) as LLMConfigSummaryWithStatus
    if (disposed || resetController.signal.aborted) return
    source.value = summary.source || 'database+env'
    backendReadonly.value = Boolean(summary.readonly)
    serverSnapshot.value = summary
    patchDraftFromSummary(summary)
    if (summary.provider_unavailable) {
      await loadProviders(resetController.signal)
      if (disposed || resetController.signal.aborted) return
      await loadModelsByProvider(draft.provider_code, draft.model_code, resetController.signal)
      if (disposed || resetController.signal.aborted) return
      const warnText = '默认推理服务当前不可用，请先重新启用或切换到其他已启用的推理服务'
      if (typeof message.warning === 'function') {
        message.warning(warnText)
      } else {
        message.error(warnText)
      }
      return
    }
    await loadModelsByProvider(draft.provider_code, draft.model_code, resetController.signal)
    if (disposed || resetController.signal.aborted) return

    const reloadResponse = await authFetch('/api/v1/qc/sichuan/reload-config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: resetController.signal,
    })
    if (disposed || resetController.signal.aborted) return
    if (!reloadResponse.ok) {
      throw new Error(`后端配置重载失败: ${reloadResponse.status}`)
    }
    message.success('已恢复默认配置')
  } catch (error) {
    if (disposed || resetController.signal.aborted) return
    const text = error instanceof Error ? error.message : String(error)
    message.error(`恢复默认失败：${text}`)
  } finally {
    if (mutationController === resetController) mutationController = null
    if (!disposed) resetting.value = false
  }
}

async function confirmDiscardChanges(): Promise<boolean> {
  if (!dirty.value) return true
  if (confirmPending.value) return false
  confirmPending.value = true
  try {
    return await new Promise<boolean>((resolve) => {
      workstationConfirmation.confirm({
        title: '有未保存的模型配置草稿',
        content: '当前模型配置草稿尚未保存，离开后修改将丢失。确定要离开吗？',
        okText: '放弃修改并离开',
        cancelText: '继续编辑',
        okType: 'danger',
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      })
    })
  } finally {
    confirmPending.value = false
  }
}

function handleBeforeUnload(event: BeforeUnloadEvent) {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

watch(
  dirty,
  (value) => {
    emit('dirty-change', value)
  },
  { immediate: true },
)

try {
  const hasRouterInstance = Boolean(
    getCurrentInstance()?.appContext?.config?.globalProperties?.$router,
  )
  const beforeLeaveFn = vueRouter.onBeforeRouteLeave as
    | ((guard: () => Promise<boolean> | boolean) => void)
    | undefined
  const isMockedGuard = Boolean(beforeLeaveFn && 'mock' in beforeLeaveFn)
  if ((hasRouterInstance || isMockedGuard) && typeof beforeLeaveFn === 'function') {
    beforeLeaveFn(async () => {
      if (!dirty.value) return true
      return await confirmDiscardChanges()
    })
  }
} catch {
  // 无路由实例的单测环境下忽略导航守卫注册
}

defineExpose({
  dirty,
  hasUnsavedChanges: dirty,
  confirmDiscardChanges,
})

onMounted(() => {
  if (typeof window !== 'undefined') {
    window.addEventListener('beforeunload', handleBeforeUnload)
  }
  void reloadAll()
})
onBeforeUnmount(() => {
  disposed = true
  ++modelRequestVersion
  ++reloadRequestVersion
  reloadController?.abort()
  reloadController = null
  modelController?.abort()
  modelController = null
  mutationController?.abort()
  mutationController = null
  if (typeof window !== 'undefined') {
    window.removeEventListener('beforeunload', handleBeforeUnload)
  }
})
</script>

<style scoped>
.llm-settings {
  display: grid;
  gap: var(--mq-space-4);
  min-width: 0;
  container: model-settings / inline-size;
}
.llm-overview__head {
  flex-wrap: wrap;
}
.llm-overview__head > div {
  flex: 1 1 320px;
}
.llm-summary {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--mq-space-4);
  padding: var(--mq-space-4);
  margin: var(--mq-space-5) 0 0;
}
.llm-summary dt {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}
.llm-summary dd {
  margin: var(--mq-space-2) 0 0;
  color: var(--mq-text-primary);
  font-size: var(--mq-font-14);
  font-weight: 600;
  overflow-wrap: anywhere;
}
.llm-summary dd.mq-mono {
  font-size: var(--mq-font-13);
}
.llm-steps {
  display: grid;
  gap: var(--mq-space-4);
  margin: 0;
  padding: 0;
  list-style: none;
}
.llm-step {
  position: relative;
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: var(--mq-space-4);
}
.llm-step:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 64px;
  bottom: -17px;
  left: 44px;
  border-left: 1px solid var(--mq-brand-200);
  pointer-events: none;
}
.llm-step__number {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--mq-info-border);
  border-radius: var(--mq-radius-tag);
  background: var(--mq-info-bg);
  color: var(--mq-brand-600);
  font-family: var(--mq-font-mono);
  font-size: var(--mq-font-13);
  font-weight: 600;
}
.llm-step__content {
  min-width: 0;
}
.llm-section-head {
  margin-bottom: var(--mq-space-5);
}
.llm-section-title {
  margin: 0;
  font-size: var(--mq-font-16);
  font-weight: 600;
  color: var(--mq-text-primary);
  line-height: 1.5;
}
.llm-section-head p {
  margin: var(--mq-space-1) 0 0;
}
.llm-default-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--mq-space-4);
}
.llm-field--wide {
  grid-column: 1 / -1;
}
.llm-inference-mode {
  width: fit-content;
  max-width: 100%;
}
.llm-control {
  width: 100%;
  min-width: 0;
}
.llm-custom-badge {
  margin-left: var(--mq-space-2);
  padding-block: 0;
}
.llm-local-status {
  margin-top: var(--mq-space-4);
}
.llm-disclosure > summary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--mq-space-2);
  cursor: pointer;
  color: var(--mq-text-primary);
  font-size: var(--mq-font-13);
  font-weight: 600;
  list-style: none;
}
.llm-disclosure > summary::before {
  content: '›';
  flex: 0 0 14px;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-20);
  line-height: 24px;
  transition: transform 160ms ease;
}
.llm-disclosure[open] > summary::before {
  transform: rotate(90deg);
}
.llm-disclosure > summary:focus-visible {
  outline: 2px solid var(--mq-brand-600);
  outline-offset: 4px;
  border-radius: var(--mq-radius-control);
}
.llm-disclosure__body {
  padding-top: var(--mq-space-4);
}
.llm-model-management {
  margin-top: var(--mq-space-5);
  padding-top: var(--mq-space-4);
  border-top: 1px solid var(--mq-border);
}
.llm-add-model {
  display: flex;
  align-items: start;
  gap: var(--mq-space-2);
  margin: var(--mq-space-3) 0;
}
.llm-custom-models {
  margin: 0;
  padding: 0;
  list-style: none;
}
.llm-custom-models li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--mq-space-3);
  padding-block: var(--mq-space-2);
  border-bottom: 1px solid var(--mq-border);
}
.llm-custom-models .mq-mono {
  min-width: 0;
  overflow-wrap: anywhere;
}
.llm-advanced-fields {
  display: grid;
  gap: var(--mq-space-6);
}
.llm-parameter-group {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--mq-space-5);
}
.llm-parameter-title {
  grid-column: 1 / -1;
  margin: 0;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-14);
  font-weight: 600;
}
.llm-parameter-row {
  display: flex;
  flex-direction: column;
  gap: var(--mq-space-3);
  min-width: 0;
}
.slider-wrap {
  padding: 0 var(--mq-space-2) var(--mq-space-4);
}
.slider-value {
  text-align: right;
  color: var(--mq-brand-600);
  font-family: var(--mq-font-mono);
  font-size: var(--mq-font-13);
}
.llm-actions {
  position: sticky;
  bottom: var(--mq-space-4);
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--mq-space-4);
}
.llm-actions__copy {
  display: grid;
  gap: var(--mq-space-1);
  min-width: 0;
}
.llm-actions__copy p {
  margin: 0;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
  font-weight: 600;
}
.llm-actions__buttons {
  display: flex;
  flex-wrap: wrap;
  gap: var(--mq-space-2);
}
@container model-settings (max-width: 680px) {
  .llm-default-fields {
    grid-template-columns: minmax(0, 1fr);
  }
  .llm-summary {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }
  .llm-summary > div:first-child {
    grid-column: 1 / -1;
  }
  .llm-parameter-group {
    grid-template-columns: minmax(0, 1fr);
  }
  .llm-actions__buttons {
    width: 100%;
    justify-content: flex-end;
  }
}
@media (prefers-reduced-motion: reduce) {
  .llm-disclosure > summary::before {
    transition: none;
  }
}
</style>
