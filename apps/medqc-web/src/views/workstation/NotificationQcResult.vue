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
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
const job = ref<SichuanBatchJob | null>(null)
const loading = ref(false)
const error = ref('')
const reviewing = ref(false)
const debugLoading = ref(false)
const debugSnapshot = ref<SichuanBatchJobDebugSnapshot | null>(null)
let generation = 0

async function load() {
  const token = ++generation
  job.value = null
  debugSnapshot.value = null
  error.value = ''
  const id = route.query.notification_id
  if (typeof id !== 'string' || !id.trim() || id.length > 36) {
    loading.value = false
    error.value = '缺少有效的结果通知'
    return
  }
  loading.value = true
  const result = await getNotificationQcResult(id)
  if (token !== generation) return
  loading.value = false
  if (!result.success || !result.data) {
    error.value = result.message || '结果读取失败'
    return
  }
  job.value = result.data
}

// 执行既有抽屉操作前重新核对通知，失效时不回退到最新结果。
async function currentJob() {
  const token = generation
  const id = route.query.notification_id
  if (typeof id !== 'string') throw new Error('缺少有效的结果通知')
  const result = await getNotificationQcResult(id)
  if (token !== generation) throw new Error('结果通知已切换')
  if (!result.success || !result.data) {
    job.value = null
    error.value = result.message || '结果读取失败'
    throw new Error(error.value)
  }
  return result.data
}

async function fetchDebug(jobId: string, options?: { ruleJobId?: string; itemLimit?: number }) {
  debugLoading.value = true
  try {
    if ((await currentJob()).id !== jobId) return null
    const result = await getSichuanWorkspaceBatchJobDebugSnapshot(jobId, {
      rule_job_id: options?.ruleJobId,
      item_limit: options?.itemLimit,
    })
    if (!result.success || !result.data) throw new Error(result.message || '调试信息读取失败')
    debugSnapshot.value = result.data
    return result.data
  } catch (cause) {
    message.error(cause instanceof Error ? cause.message : '调试信息读取失败')
    return null
  } finally {
    debugLoading.value = false
  }
}

async function exportResult(format: 'xlsx' | 'csv' | 'html' = 'html') {
  try {
    const current = await currentJob()
    const result = await exportSichuanWorkspaceBatchJob({ job_id: current.id, format })
    if (!result.success || !result.data) throw new Error(result.message || '导出失败')
    downloadBlob(await normalizeBatchExportBlob(result.data, format), `qc-${current.id}.${format}`)
  } catch (cause) {
    message.error(cause instanceof Error ? cause.message : '导出失败')
  }
}

async function reviewResult(): Promise<void> {
  reviewing.value = true
  try {
    const current = await currentJob()
    const result = await reviewSichuanWorkspaceBatchJob(current.id)
    if (!result.success || !result.data?.job) throw new Error(result.message || '复核失败')
    job.value = result.data.job
  } catch (cause) {
    message.error(cause instanceof Error ? cause.message : '复核失败')
  } finally {
    reviewing.value = false
  }
}

function close() {
  generation += 1
  void router.push(MESSAGE_CENTER_PATH)
}

watch(() => route.query.notification_id, load, { immediate: true })
</script>
