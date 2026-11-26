<template>
  <section class="mq-page notification-qc-result" aria-label="质控结果详情">
    <div v-if="loading" class="notification-qc-result__loading" role="status" aria-live="polite">
      <a-spin size="large" />
      <p class="notification-qc-result__loading-text">正在加载质控结果…</p>
    </div>
    <a-result v-else-if="error" status="warning" title="结果暂不可用" :sub-title="error">
      <template #extra
        ><a-button @click="load">重试</a-button
        ><a-button @click="close">{{ closeTarget.label }}</a-button></template
      >
    </a-result>
    <SemanticRulesBatchResultDrawer
      v-if="job"
      :open="true"
      :batch-job-detail="job"
      :batch-job-detail-loading="loading"
      :batch-job-debug-snapshot="debugSnapshot"
      :batch-job-debug-loading="debugLoading"
      :fetch-batch-job-debug-snapshot="fetchDebug"
      :close="close"
      :back-label="closeTarget.label"
      :export-batch-job-report="exportResult"
      :review-batch-job-result="reviewResult"
      :review-batch-job-loading="reviewing"
      :get-batch-job-status-tag-class="getBatchJobStatusClass"
      :get-batch-job-status-text="getBatchJobStatusText"
      :format-date-time="formatBatchJobDateTime"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useQcResultVisibility } from '@/composables/useQcResultVisibility'
import { message } from 'ant-design-vue'
import {
  resolveAuthorizedWorkstationPath,
  resolveDefaultWorkstationPath,
} from '@/components/layout/workstationNav'
import { effectiveRoles } from '@/utils/effectiveRoles'
import { canUseMessageCenter, MESSAGE_CENTER_PATH } from './notificationNavigation'
import {
  getNotificationQcResult,
  getSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJobDebugSnapshot,
  exportSichuanWorkspaceBatchJob,
  reviewSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import SemanticRulesBatchResultDrawer from '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue'
import type {
  SichuanBatchJob,
  SichuanBatchJobDebugSnapshot,
} from '@/views/workstation-v4/semantic-rules/types'
import {
  downloadBlob,
  normalizeBatchExportBlob,
} from '@/views/workstation-v4/customer-sample-validation/batchExport'
import {
  formatBatchJobDateTime,
  getBatchJobStatusClass,
  getBatchJobStatusText,
} from '@/views/workstation-v4/customer-sample-validation/batchJobPresentation'

const props = withDefaults(defineProps<{ entryMode?: 'notification' | 'task' }>(), {
  entryMode: 'notification',
})
const route = useRoute()
const selectedId = computed(() =>
  props.entryMode === 'task' ? route.query.job_id : route.query.notification_id,
)
const missingIdentityMessage = computed(() =>
  props.entryMode === 'task' ? '缺少有效的任务ID' : '缺少有效的结果通知',
)

// 两种入口各自授权读取；通知404不能回退到任务或最新结果。
async function readResult(id: string, mode: 'notification' | 'task') {
  const result = await (mode === 'task'
    ? getSichuanWorkspaceBatchJob(id)
    : getNotificationQcResult(id))
  if (mode === 'task' && result.success && result.data && result.data.id !== id) {
    throw new Error('返回任务与当前任务不一致')
  }
  return result
}
const router = useRouter()
const authStore = useAuthStore()
const { confirmedResultsOnly } = useQcResultVisibility()
const authScope = computed(() =>
  JSON.stringify([
    authStore.user?.id,
    authStore.user?.institute_id,
    authStore.user?.department,
    authStore.userRoles,
    authStore.user?.is_active,
  ]),
)
const job = ref<SichuanBatchJob | null>(null)
const loading = ref(false)
const error = ref('')
const reviewing = ref(false)
const debugLoading = ref(false)
const debugSnapshot = ref<SichuanBatchJobDebugSnapshot | null>(null)
let generation = 0
let debugRequest = 0
let reviewRequest = 0
let disposed = false

function requestContext() {
  return { generation, scope: authScope.value, notice: selectedId.value, mode: props.entryMode }
}

function isCurrent(context: ReturnType<typeof requestContext>) {
  return (
    !disposed &&
    context.generation === generation &&
    context.scope === authScope.value &&
    context.notice === selectedId.value &&
    context.mode === props.entryMode
  )
}

async function load() {
  generation += 1
  debugRequest += 1
  reviewRequest += 1
  reviewing.value = false
  debugLoading.value = false
  const context = requestContext()
  job.value = null
  debugSnapshot.value = null
  error.value = ''
  if (!authStore.user?.id || authStore.user.is_active === false) {
    loading.value = false
    error.value = '请使用有效账号重新登录'
    return
  }
  const id = selectedId.value
  if (typeof id !== 'string' || !id.trim() || id.length > 36) {
    loading.value = false
    error.value = missingIdentityMessage.value
    return
  }
  loading.value = true
  try {
    const result = await readResult(id, context.mode)
    if (!isCurrent(context)) return
    if (!result.success || !result.data) {
      error.value = result.message || '结果读取失败'
      return
    }
    job.value = result.data
    if (!confirmedResultsOnly.value && result.data.id) {
      void loadDebugSnapshot(result.data.id, undefined, { silent: true })
    }
  } catch (cause) {
    if (isCurrent(context)) error.value = cause instanceof Error ? cause.message : '结果读取失败'
  } finally {
    if (isCurrent(context)) loading.value = false
  }
}

// 复用当前上下文已授权加载的 job，避免每次调试/导出/复核重复触发 FOR UPDATE 读取通知接口。
function resolveLoadedJob(context: ReturnType<typeof requestContext>): SichuanBatchJob {
  if (!isCurrent(context)) throw new Error('结果通知或账号已切换')
  const loaded = job.value
  if (!loaded || !loaded.id) {
    throw new Error(missingIdentityMessage.value)
  }
  return loaded
}

async function loadDebugSnapshot(
  jobId: string,
  options?: { ruleJobId?: string; itemLimit?: number },
  behavior?: { silent?: boolean },
) {
  const context = requestContext()
  const request = ++debugRequest
  const active = () => isCurrent(context) && request === debugRequest
  debugLoading.value = true
  try {
    const current = resolveLoadedJob(context)
    if (current.id !== jobId || !active()) return null
    const result = await getSichuanWorkspaceBatchJobDebugSnapshot(jobId, {
      rule_job_id: options?.ruleJobId,
      item_limit: options?.itemLimit,
    })
    if (!active()) return null
    if (!result.success || !result.data) throw new Error(result.message || '调试信息读取失败')
    debugSnapshot.value = result.data
    return result.data
  } catch (cause) {
    if (active() && !behavior?.silent) {
      message.error(cause instanceof Error ? cause.message : '调试信息读取失败')
    }
    return null
  } finally {
    if (active()) debugLoading.value = false
  }
}

async function fetchDebug(jobId: string, options?: { ruleJobId?: string; itemLimit?: number }) {
  return loadDebugSnapshot(jobId, options, { silent: false })
}

async function exportResult(format: 'xlsx' | 'csv' | 'html' = 'html') {
  const context = requestContext()
  try {
    const current = resolveLoadedJob(context)
    const result = await exportSichuanWorkspaceBatchJob({ job_id: current.id, format })
    if (!isCurrent(context)) return
    if (!result.success || !result.data) throw new Error(result.message || '导出失败')
    const blob = await normalizeBatchExportBlob(result.data, format)
    if (!isCurrent(context)) return
    downloadBlob(blob, `qc-${current.id}.${format}`)
  } catch (cause) {
    if (isCurrent(context)) message.error(cause instanceof Error ? cause.message : '导出失败')
  }
}

async function reviewResult(): Promise<void> {
  const context = requestContext()
  const request = ++reviewRequest
  const active = () => isCurrent(context) && request === reviewRequest
  reviewing.value = true
  try {
    const current = resolveLoadedJob(context)
    const result = await reviewSichuanWorkspaceBatchJob(current.id)
    if (!active()) return
    if (!result.success || !result.data?.job) throw new Error(result.message || '复核失败')
    job.value = result.data.job
    const count = Number(result.data.review_report?.summary?.total_findings || 0)
    message.success(count > 0 ? `复核完成，发现 ${count} 条复核建议` : '复核完成，暂无高风险建议')
  } catch (cause) {
    if (active()) message.error(cause instanceof Error ? cause.message : '复核失败')
  } finally {
    if (active()) reviewing.value = false
  }
}

const RUNNING_QC_ROLES = ['admin', 'qc_manager', 'sync_admin', 'super_admin']
const WORKLIST_ROLES = ['admin', 'qc_manager', 'doctor', 'sync_admin', 'super_admin']

const normalizedUserRoles = computed(() => {
  const raw = Array.isArray(authStore.userRoles)
    ? authStore.userRoles
    : Array.isArray(authStore.user?.roles)
      ? authStore.user.roles
      : authStore.user?.role
        ? [authStore.user.role]
        : []
  return effectiveRoles(raw)
})

const canAccessRunningQc = computed(() =>
  normalizedUserRoles.value.some((role) => RUNNING_QC_ROLES.includes(role)),
)
const canAccessWorklist = computed(() =>
  normalizedUserRoles.value.some((role) => WORKLIST_ROLES.includes(role)),
)
const canAccessMessages = computed(() => canUseMessageCenter(normalizedUserRoles.value))

const closeTarget = computed<{ path: string; label: string }>(() => {
  const roles = normalizedUserRoles.value
  const from = typeof route.query.from === 'string' ? route.query.from.trim() : ''
  const defaultPath =
    resolveAuthorizedWorkstationPath(roles) ?? resolveDefaultWorkstationPath(roles)

  if (props.entryMode === 'notification') {
    if (canAccessMessages.value) {
      return { path: MESSAGE_CENTER_PATH, label: '返回消息中心' }
    }
    return { path: defaultPath, label: '返回工作台' }
  }

  if (from === 'final' && canAccessRunningQc.value) {
    return { path: '/workstation-v5/records/final', label: '返回终末质控' }
  }
  if (from === 'worklist' && canAccessWorklist.value) {
    return { path: '/workstation-v5/worklist', label: '返回病历池' }
  }
  if (from === 'messages' && canAccessMessages.value) {
    return { path: MESSAGE_CENTER_PATH, label: '返回消息中心' }
  }
  if (canAccessRunningQc.value) {
    return { path: '/workstation-v5/records/running', label: '返回运行质控' }
  }
  if (canAccessMessages.value) {
    return { path: MESSAGE_CENTER_PATH, label: '返回消息中心' }
  }
  return { path: defaultPath, label: '返回工作台' }
})

function close() {
  generation += 1
  void router.push(closeTarget.value.path)
}

watch([selectedId, () => props.entryMode, authScope], load, { immediate: true })
onBeforeUnmount(() => {
  disposed = true
  generation += 1
})
</script>

<style scoped>
.notification-qc-result__loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: min(60dvh, 420px);
  padding: 48px 24px;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-14);
}
.notification-qc-result__loading-text {
  margin: 0;
}
</style>
