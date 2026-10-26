<template>
  <main class="mq-page">
    <a-spin v-if="loading" />
    <a-result v-else-if="error" status="warning" title="结果暂不可用" :sub-title="error">
      <template #extra
        ><a-button @click="load">重试</a-button
        ><a-button @click="close">返回消息</a-button></template
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
      :export-batch-job-report="exportResult"
      :review-batch-job-result="reviewResult"
      :review-batch-job-loading="reviewing"
      :get-batch-job-status-tag-class="getBatchJobStatusClass"
      :get-batch-job-status-text="getBatchJobStatusText"
      :format-date-time="formatBatchJobDateTime"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { message } from 'ant-design-vue'
import { MESSAGE_CENTER_PATH } from './notificationNavigation'
import {
  getNotificationQcResult,
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

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
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
  return { generation, scope: authScope.value, notice: route.query.notification_id }
}

function isCurrent(context: ReturnType<typeof requestContext>) {
  return (
    !disposed &&
    context.generation === generation &&
    context.scope === authScope.value &&
    context.notice === route.query.notification_id
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
  const id = route.query.notification_id
  if (typeof id !== 'string' || !id.trim() || id.length > 36) {
    loading.value = false
    error.value = '缺少有效的结果通知'
    return
  }
  loading.value = true
  try {
    const result = await getNotificationQcResult(id)
    if (!isCurrent(context)) return
    if (!result.success || !result.data) {
      error.value = result.message || '结果读取失败'
      return
    }
    job.value = result.data
  } catch (cause) {
    if (isCurrent(context)) error.value = cause instanceof Error ? cause.message : '结果读取失败'
  } finally {
    if (isCurrent(context)) loading.value = false
  }
}

// 执行既有抽屉操作前重新核对通知，失效时不回退到最新结果。
async function currentJob(context: ReturnType<typeof requestContext>) {
  const id = context.notice
  if (typeof id !== 'string') throw new Error('缺少有效的结果通知')
  const result = await getNotificationQcResult(id)
  if (!isCurrent(context)) throw new Error('结果通知或账号已切换')
  if (!result.success || !result.data) {
    job.value = null
    error.value = result.message || '结果读取失败'
    throw new Error(error.value)
  }
  return result.data
}

async function fetchDebug(jobId: string, options?: { ruleJobId?: string; itemLimit?: number }) {
  const context = requestContext()
  const request = ++debugRequest
  const active = () => isCurrent(context) && request === debugRequest
  debugLoading.value = true
  try {
    if ((await currentJob(context)).id !== jobId || !active()) return null
    const result = await getSichuanWorkspaceBatchJobDebugSnapshot(jobId, {
      rule_job_id: options?.ruleJobId,
      item_limit: options?.itemLimit,
    })
    if (!active()) return null
    if (!result.success || !result.data) throw new Error(result.message || '调试信息读取失败')
    debugSnapshot.value = result.data
    return result.data
  } catch (cause) {
    if (active()) message.error(cause instanceof Error ? cause.message : '调试信息读取失败')
    return null
  } finally {
    if (active()) debugLoading.value = false
  }
}

async function exportResult(format: 'xlsx' | 'csv' | 'html' = 'html') {
  const context = requestContext()
  try {
    const current = await currentJob(context)
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
    const current = await currentJob(context)
    const result = await reviewSichuanWorkspaceBatchJob(current.id)
    if (!active()) return
    if (!result.success || !result.data?.job) throw new Error(result.message || '复核失败')
    job.value = result.data.job
  } catch (cause) {
    if (active()) message.error(cause instanceof Error ? cause.message : '复核失败')
  } finally {
    if (active()) reviewing.value = false
  }
}

function close() {
  generation += 1
  void router.push(MESSAGE_CENTER_PATH)
}

watch([() => route.query.notification_id, authScope], load, { immediate: true, flush: 'sync' })
onBeforeUnmount(() => {
  disposed = true
  generation += 1
})
</script>
