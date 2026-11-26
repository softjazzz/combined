<template>
  <div class="qc-runtime-settings">
    <div class="mq-card__head">
      <div>
        <h2 class="mq-card__title">质控运行</h2>
        <p class="mq-card__desc">选择新任务的执行方式，已有任务保持原来的执行方式。</p>
      </div>
      <button class="mq-btn mq-btn--ghost" :disabled="busy" @click="run('load')">刷新配置</button>
    </div>
    <p v-if="error" role="alert" class="runtime-error">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <p v-if="!config">{{ busy ? '正在读取运行配置…' : '配置尚未读取，请刷新后重试。' }}</p>
    <template v-else>
      <div class="mq-inset runtime-mode">
        <div>
          <strong>RabbitMQ 任务分发</strong>
          <p>关闭时仍可质控，由 Web 后端执行；开启后由独立 QC Worker 执行新任务。</p>
        </div>
        <label class="runtime-toggle">
          <input v-model="enabled" type="checkbox" role="switch" :disabled="busy"
            :aria-checked="enabled" aria-label="启用 RabbitMQ 任务分发" />
          {{ enabled ? '开启' : '关闭' }}
        </label>
      </div>
      <p data-testid="effective-mode">当前新任务执行方式：<strong>{{ config.effective_mode === 'rabbitmq' ? 'RabbitMQ / 独立 Worker' : 'Web 后端' }}</strong></p>
      <p class="runtime-hint">配置来源：{{ config.source === 'file' ? '后台设置' : '部署默认值' }} · 配置版本 {{ config.revision }}</p>
      <div class="mq-soft runtime-readiness">
        <strong>配套服务检查</strong>
        <ul>
          <li v-for="check in checks" :key="check.key">
            <span>{{ check.label }}</span>
            <span
              :class="{
                'runtime-error':
                  !(check.key === 'gateway' && !config.readiness.gateway_checked) &&
                  !config.readiness.checks[check.key],
                'runtime-muted':
                  check.key === 'gateway' && !config.readiness.gateway_checked,
              }"
            >
              {{ check.key === 'gateway' && !config.readiness.gateway_checked ? '未检查' : config.readiness.checks[check.key] ? '通过' : '未就绪' }}
            </span>
          </li>
        </ul>
        <p class="runtime-hint">服务状态来自最近 30 秒心跳；仅检查 Gateway 状态，不发起模型请求。服务可能在检查后变化，运行失败仍按原任务恢复机制处理。</p>
      </div>
      <p class="runtime-hint">启用前需部署 RabbitMQ、Publisher、QC Worker 和 LLM Gateway，并完成相应迁移。各进程必须共享运行配置目录。此开关不会安装或启动服务。</p>
      <p class="runtime-hint">本期开关适用于正式 LX0609 单个执行任务；多规则族父子任务暂不支持 MQ。关闭后，已入队任务仍需保留 Publisher 和 Worker 直至完成。</p>
      <div class="runtime-actions">
        <button class="mq-btn mq-btn--ghost" :disabled="busy" @click="run('check')">检查配套服务</button>
        <button class="mq-btn mq-btn--primary" :disabled="busy || enabled === config.rabbitmq_enabled" @click="run('save')">{{ busy ? '处理中…' : '保存设置' }}</button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import { useAuthStore } from '@/stores/auth'
import {
  checkQcRuntimeSettings, getQcRuntimeSettings, saveQcRuntimeSettings,
  type QcRuntimeSettings,
} from '@/api/qcRuntimeSettings'

const auth = useAuthStore()
const config = ref<QcRuntimeSettings | null>(null)
const enabled = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
let generation = 0
let controller: AbortController | undefined
const checks: { key: keyof QcRuntimeSettings['readiness']['checks']; label: string }[] = [
  { key: 'broker_config', label: 'RabbitMQ 部署配置' },
  { key: 'gateway_config', label: 'LLM Gateway 部署配置' },
  { key: 'publisher', label: 'Publisher 就绪心跳' },
  { key: 'worker', label: 'QC Worker 就绪心跳' },
  { key: 'gateway', label: 'Gateway 健康及授权' },
]
const canManage = computed(() => auth.userRoles.some((role: string) => ['admin', 'sync_admin', 'super_admin'].includes(role)) &&
  (auth.user?.is_demo_account !== true || auth.userRoles.some((role: string) => ['sync_admin', 'super_admin'].includes(role))))
const identity = computed(() => JSON.stringify([auth.user?.id, auth.userRoles, auth.user?.is_demo_account]))

function extractConflictReadiness(cause: unknown): QcRuntimeSettings['readiness'] | null {
  if (!isAxiosError(cause) || cause.response?.status !== 409) return null
  const detail = (cause.response?.data as { detail?: unknown } | undefined)?.detail
  if (!detail || typeof detail !== 'object') return null
  const readiness = (detail as { readiness?: unknown }).readiness
  if (!readiness || typeof readiness !== 'object') return null
  const candidate = readiness as Partial<QcRuntimeSettings['readiness']>
  if (typeof candidate.ready !== 'boolean' || !candidate.checks || typeof candidate.checks !== 'object') {
    return null
  }
  return candidate as QcRuntimeSettings['readiness']
}

async function run(action: 'load' | 'check' | 'save') {
  if (!canManage.value || busy.value) return
  const request = ++generation
  controller?.abort()
  controller = new AbortController()
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const result = action === 'save' && config.value
      ? await saveQcRuntimeSettings(enabled.value, config.value.revision, controller.signal)
      : action === 'check' ? await checkQcRuntimeSettings(controller.signal)
        : await getQcRuntimeSettings(controller.signal)
    if (request !== generation || !canManage.value) return
    config.value = result
    if (action !== 'check') {
      enabled.value = result.rabbitmq_enabled
    }
    if (action === 'save') notice.value = '已保存，仅影响新建任务。'
    if (action === 'check') notice.value = result.readiness.ready ? '配套服务检查通过。' : '配套服务尚未全部就绪，请检查部署。'
  } catch (cause) {
    if (request !== generation) return
    // 不回显服务端原始错误、地址或凭据；保存失败时保留当前生效值并刷新冲突时的就绪状态。
    if (action === 'save' && isAxiosError(cause) && cause.response?.status === 409) {
      const conflictReadiness = extractConflictReadiness(cause)
      if (conflictReadiness && config.value) {
        config.value = { ...config.value, readiness: conflictReadiness }
      } else if (controller) {
        try {
          const latest = await getQcRuntimeSettings(controller.signal)
          if (request === generation && canManage.value) {
            config.value = latest
          }
        } catch {
          // 刷新失败时保留原错误提示
        }
      }
    }
    error.value = action === 'save'
      ? '未保存：可能是配套服务未就绪、配置已被更新或无写入权限。请检查服务并刷新配置后重试。'
      : '无法读取运行配置或服务状态，请检查权限和后端连接后重试。'
    if (action === 'save' && config.value) enabled.value = config.value.rabbitmq_enabled
  } finally {
    if (request === generation) busy.value = false
  }
}

watch(identity, () => {
  generation++
  controller?.abort()
  config.value = null
  busy.value = false
  error.value = ''
  notice.value = ''
  if (canManage.value) void run('load')
}, { immediate: true })
onBeforeUnmount(() => { generation++; controller?.abort() })
</script>

<style scoped>
.qc-runtime-settings { padding: 24px; }
.runtime-mode { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 20px; margin-top: 20px; }
.runtime-mode p, .runtime-hint { color: var(--mq-text-secondary); font-size: 13px; line-height: 1.7; }
.runtime-toggle { display: flex; gap: 8px; align-items: center; white-space: nowrap; }
.runtime-toggle input { appearance: none; position: relative; width: 42px; height: 24px; margin: 0; border-radius: 999px; background: var(--mq-border-strong); cursor: pointer; }
.runtime-toggle input::before { content: ''; position: absolute; top: 3px; left: 3px; width: 18px; height: 18px; border-radius: 50%; background: var(--mq-bg-surface); transition: transform 0.15s ease; }
.runtime-toggle input:checked { background: var(--mq-brand-600); }
.runtime-toggle input:checked::before { transform: translateX(18px); }
.runtime-toggle input:focus-visible { outline: 2px solid var(--mq-brand-600); outline-offset: 3px; }
.runtime-toggle input:disabled { opacity: 0.5; cursor: wait; }
.runtime-readiness { padding: 20px; margin: 16px 0; }
.runtime-readiness ul { padding: 0; list-style: none; }
.runtime-readiness li { display: flex; justify-content: space-between; gap: 20px; margin: 10px 0; }
.runtime-error { color: var(--mq-danger-text); }
.runtime-muted { color: var(--mq-text-secondary); }
.runtime-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 12px; margin-top: 20px; }
@media (max-width: 600px) { .qc-runtime-settings { padding: 16px; } .runtime-mode { flex-direction: column; align-items: flex-start; } }
</style>
