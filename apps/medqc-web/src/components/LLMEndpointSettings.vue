<template>
  <section
    v-if="canManage"
    class="mq-card mq-card--padded"
  >
    <header class="mq-card__head">
      <div>
        <h3 class="mq-card__title">
          推理服务连接
        </h3>
        <p class="mq-card__desc">
          超级管理员管理地址、密钥和启用状态。保存不调用模型，仅影响后续任务。
        </p>
      </div>
      <a-button
        data-testid="endpoint-open"
        @click="open"
      >
        管理连接
      </a-button>
    </header>
    <a-drawer
      v-model:open="visible"
      title="推理服务连接"
      width="min(560px, 100vw)"
      :destroy-on-close="true"
      @after-open-change="onVisibleChange"
    >
      <a-alert
        v-if="loadError"
        type="error"
        show-icon
        :message="loadError"
      />
      <a-alert
        v-else-if="submitError"
        type="error"
        show-icon
        :message="submitError"
      />
      <a-button
        v-if="loadError || conflictBlocked"
        :loading="busy"
        @click="reload"
      >
        重新读取配置
      </a-button>
      <template v-if="view">
        <a-alert
          v-if="!view.editable"
          type="info"
          show-icon
          message="当前走受控 Gateway，连接与令牌由部署管理，不能改为直连。"
        />
        <a-form
          layout="vertical"
          class="endpoint-form"
        >
          <a-form-item label="推理服务">
            <a-select
              v-model:value="provider"
              :disabled="busy"
              :options="providerOptions"
              @change="select"
            />
          </a-form-item>
          <p>当前来源：{{ selected?.source === 'saved' ? '超级管理员配置' : '部署配置' }} · 版本 {{ view.version }}</p>
          <a-form-item label="沿用部署配置">
            <a-switch
              v-model:checked="draft.use_deployment"
              :disabled="busy || !view.editable"
            />
          </a-form-item>
          <a-form-item label="允许新任务使用此服务">
            <a-switch
              v-model:checked="draft.enabled"
              :disabled="locked"
            />
          </a-form-item>
          <a-form-item label="API 地址（服务根地址，可含 /v1）">
            <a-input
              v-model:value="draft.endpoint"
              :disabled="locked"
              placeholder="http://模型服务器:端口/v1"
              autocomplete="off"
            />
          </a-form-item>
          <a-form-item label="API 密钥">
            <a-input-password
              v-model:value="secret"
              :disabled="locked || draft.clear_key"
              autocomplete="new-password"
              placeholder="留空保留已有密钥"
            />
            <p class="mq-field__hint">
              {{ selected?.key_configured ? '已配置，密钥不回显' : '尚未配置密钥' }}。本地无鉴权服务可不填。
            </p>
          </a-form-item>
          <a-form-item>
            <a-checkbox
              v-model:checked="draft.clear_key"
              :disabled="locked"
              @change="secret = ''"
            >
              明确清除已保存密钥（不回退部署密钥）
            </a-checkbox>
          </a-form-item>
          <p class="mq-field__hint">
            地址从业务服务器访问；127.0.0.1 指业务服务器本机。启用不会启动或安装模型服务。
          </p>
          <a-button
            data-testid="endpoint-save"
            type="primary"
            :disabled="!view.editable || !!loadError || conflictBlocked"
            :loading="busy"
            @click="save"
          >
            保存连接配置
          </a-button>
        </a-form>
        <p class="mq-field__hint">
          保存后在模型配置中选择模型。“测试连接”是独立操作，会实际请求模型服务。
        </p>
      </template>
    </a-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useAuthStore } from '@/stores/auth'
import { llmEndpointService, type EndpointView } from '@/services/llmEndpointService'

const emit = defineEmits<{ saved: [] }>()
const auth = useAuthStore()
const canManage = computed(() => auth.userRoles.some(role => ['sync_admin', 'super_admin'].includes(role)))
const visible = ref(false)
const busy = ref(false)
const loadError = ref('')
const submitError = ref('')
const conflictBlocked = ref(false)
const view = ref<EndpointView>()
const provider = ref('ollama')
const secret = ref('')
const draft = reactive({ use_deployment: true, enabled: false, endpoint: '', clear_key: false })
const providerOptions = computed(() => view.value?.providers.map(row => ({ value: row.provider_code, label: row.name })) ?? [])
const selected = computed(() => view.value?.providers.find(row => row.provider_code === provider.value))
const locked = computed(() => busy.value || !view.value?.editable || draft.use_deployment)

let disposed = false
let requestSeq = 0
let activeController: AbortController | null = null

function clearSubmitError() {
  if (!conflictBlocked.value && submitError.value) {
    submitError.value = ''
  }
}

watch(
  [() => draft.use_deployment, () => draft.enabled, () => draft.endpoint, () => draft.clear_key, secret],
  () => {
    clearSubmitError()
  },
)

function select() {
  const row = selected.value
  secret.value = ''
  if (!conflictBlocked.value) {
    submitError.value = ''
  }
  Object.assign(draft, { use_deployment: row?.source !== 'saved', enabled: row?.enabled ?? false, endpoint: row?.endpoint ?? '', clear_key: false })
}
async function reload() {
  const seq = ++requestSeq
  activeController?.abort()
  const controller = new AbortController()
  activeController = controller
  busy.value = true
  loadError.value = ''
  submitError.value = ''
  conflictBlocked.value = false
  secret.value = ''
  try {
    const loaded = await llmEndpointService.load()
    if (disposed || seq !== requestSeq || controller.signal.aborted) return
    view.value = loaded
    select()
  } catch (err) {
    if (disposed || seq !== requestSeq || controller.signal.aborted) return
    loadError.value = err instanceof Error ? err.message : '配置读取失败'
    view.value = undefined
  } finally {
    if (!disposed && seq === requestSeq && activeController === controller) {
      busy.value = false
      activeController = null
    }
  }
}
async function open() { visible.value = true; await reload() }
function onVisibleChange(opened: boolean) {
  if (!opened) {
    requestSeq += 1
    activeController?.abort()
    activeController = null
    busy.value = false
    secret.value = ''
    submitError.value = ''
    conflictBlocked.value = false
    view.value = undefined
  }
}
async function save() {
  if (!view.value || !view.value.editable || busy.value || loadError.value || conflictBlocked.value) return
  const seq = ++requestSeq
  activeController?.abort()
  const controller = new AbortController()
  activeController = controller
  busy.value = true
  submitError.value = ''
  try {
    const saved = await llmEndpointService.save(provider.value, { version: view.value.version, ...draft, ...(secret.value ? { api_key: secret.value } : {}) })
    if (disposed || seq !== requestSeq || controller.signal.aborted) return
    view.value = saved
    conflictBlocked.value = false
    select()
    message.success('连接配置已保存，未调用模型')
    emit('saved')
  } catch (err) {
    if (disposed || seq !== requestSeq || controller.signal.aborted) return
    const errMsg = err instanceof Error ? err.message : '保存失败'
    submitError.value = errMsg
    conflictBlocked.value = errMsg.includes('配置已变化') || errMsg.includes('409')
  } finally {
    secret.value = ''
    if (!disposed && seq === requestSeq && activeController === controller) {
      busy.value = false
      activeController = null
    }
  }
}

onBeforeUnmount(() => {
  disposed = true
  requestSeq += 1
  activeController?.abort()
  activeController = null
})
</script>

<style scoped src="./LLMEndpointSettings.css"></style>
