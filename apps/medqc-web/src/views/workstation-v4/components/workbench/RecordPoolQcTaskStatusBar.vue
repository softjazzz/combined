<template>
  <section
    v-if="currentJob"
    class="record-pool-qc-status"
    :class="`record-pool-qc-status--${tone}`"
    role="status"
    aria-live="polite"
    data-testid="record-pool-qc-task-status"
  >
    <div class="record-pool-qc-status__main">
      <div class="record-pool-qc-status__indicator" aria-hidden="true">
        <LoaderCircle v-if="isActive" :size="18" class="record-pool-qc-status__spinner" />
        <CircleCheckBig v-else-if="currentJob.status === 'completed'" :size="18" />
        <CircleAlert v-else :size="18" />
      </div>

      <div class="record-pool-qc-status__content">
        <div class="record-pool-qc-status__eyebrow">
          <span>批量质控</span>
          <span class="record-pool-qc-status__eyebrow-dot" aria-hidden="true" />
          <span>实时任务进度</span>
        </div>
        <div class="record-pool-qc-status__heading">
          <strong>{{ statusTitle }}</strong>
          <span>{{ statusBadge }}</span>
          <em v-if="progressPercent !== null">{{ progressPercent }}%</em>
        </div>

        <div class="record-pool-qc-status__metrics">
          <span>{{ recordProgressText }}</span>
          <span v-if="ruleProgressText">{{ ruleProgressText }}</span>
          <span v-if="terminalSummary">{{ terminalSummary }}</span>
        </div>

        <div
          v-if="multiRecordRuntime"
          class="record-pool-qc-status__concurrency"
          data-testid="record-pool-qc-concurrency"
          aria-label="多病历并发执行状态"
        >
          <span
            >并发 <strong>{{ multiRecordRuntime.parallel }}</strong> 份</span
          >
          <span class="is-active"
            >执行中 <strong>{{ multiRecordRuntime.active }}</strong> 份</span
          >
          <span class="is-complete"
            >已完成 <strong>{{ multiRecordRuntime.completed }}</strong> 份</span
          >
          <span
            >排队 <strong>{{ multiRecordRuntime.queued }}</strong> 份</span
          >
        </div>

        <div class="record-pool-qc-status__progress">
          <a-progress
            v-if="progressPercent !== null"
            :percent="progressPercent"
            :show-info="false"
            :status="progressStatus"
            size="small"
          />
          <div v-else class="record-pool-qc-status__indeterminate" aria-hidden="true">
            <span />
          </div>
        </div>

        <ol
          class="record-pool-qc-status__stages"
          data-testid="record-pool-qc-task-stages"
          aria-label="质控任务执行阶段"
        >
          <li
            v-for="stage in workflowStages"
            :key="stage.key"
            :class="`is-${stage.state}`"
            :data-stage-key="stage.key"
          >
            <span class="record-pool-qc-status__stage-marker" aria-hidden="true" />
            <span class="record-pool-qc-status__stage-copy">
              <strong>{{ stage.label }}</strong>
              <small>{{ stage.detail }}</small>
            </span>
          </li>
        </ol>

        <p class="record-pool-qc-status__stage">
          {{ stageText }}
        </p>
        <p v-if="pollError" class="record-pool-qc-status__refresh-note">
          进度暂时未更新，系统将自动重试。
        </p>
      </div>
    </div>

    <div v-if="!isActive" class="record-pool-qc-status__actions">
      <button
        v-if="currentJob.status === 'completed'"
        type="button"
        class="record-pool-qc-status__export"
        :disabled="exporting"
        @click="exportCurrentBatch"
      >
        {{ exporting ? '正在导出…' : '导出本次结果 HTML' }}
      </button>
      <button
        type="button"
        class="record-pool-qc-status__dismiss"
        aria-label="关闭质控任务状态"
        @click="emit('dismiss')"
      >
        <X :size="16" />
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { CircleAlert, CircleCheckBig, LoaderCircle, X } from 'lucide-vue-next'
import {
  exportSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import type { SichuanBatchJob } from '../../semantic-rules/types'
import {
  downloadBlob,
  normalizeBatchExportBlob,
} from '../../customer-sample-validation/batchExport'

const props = withDefaults(
  defineProps<{
    job: SichuanBatchJob | null
    pollIntervalMs?: number
  }>(),
  {
    pollIntervalMs: 2000,
  },
)

const emit = defineEmits<{
  dismiss: []
}>()

const currentJob = ref<SichuanBatchJob | null>(null)
const pollError = ref(false)
const exporting = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | null = null
let requestSequence = 0

async function exportCurrentBatch() {
  const jobId = String(currentJob.value?.id || '').trim()
  if (!jobId || currentJob.value?.status !== 'completed' || exporting.value) return
  exporting.value = true
  try {
    const response = await exportSichuanWorkspaceBatchJob({ job_id: jobId, format: 'html' })
    if (!response.success || !response.data) {
      message.error(response.message || '导出本次质控结果失败')
      return
    }
    const blob = await normalizeBatchExportBlob(response.data, 'html')
    downloadBlob(blob, '本次批量质控结果.html')
    message.success('本次批量质控结果已开始下载')
  } catch {
    message.error('导出本次质控结果失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

const terminalStatuses = new Set(['completed', 'failed', 'canceled'])
const isActive = computed(() =>
  Boolean(currentJob.value && !terminalStatuses.has(currentJob.value.status)),
)

function finiteCount(value: unknown): number | null {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean')
    return null
  const count = Number(value)
  return Number.isFinite(count) && count >= 0 ? Math.trunc(count) : null
}

function firstCount(...values: unknown[]): number | null {
  for (const value of values) {
    const count = finiteCount(value)
    if (count !== null) return count
  }
  return null
}

const totalRecords = computed(() =>
  firstCount(
    currentJob.value?.total_records,
    currentJob.value?.summary?.total_records,
    currentJob.value?.summary?.progress?.total_records,
    currentJob.value?.summary?.stream_state?.total_records,
  ),
)

const successRecords = computed(
  () => firstCount(currentJob.value?.success_count, currentJob.value?.summary?.success_count) ?? 0,
)

const failedRecords = computed(
  () =>
    firstCount(
      currentJob.value?.summary?.failed_record_count,
      currentJob.value?.failed_count,
      currentJob.value?.summary?.failed_count,
    ) ?? 0,
)

const processedRecords = computed(() =>
  firstCount(
    currentJob.value?.summary?.progress?.processed_records,
    currentJob.value?.summary?.stream_state?.processed_records,
    successRecords.value + failedRecords.value,
  ),
)

const recordProgressText = computed(() => {
  if (totalRecords.value === null) return '正在确认任务范围'
  if (currentJob.value?.status === 'queued') return `待处理 ${totalRecords.value} 份病历`
  return `已处理 ${Math.min(processedRecords.value ?? 0, totalRecords.value)} / ${totalRecords.value} 份病历`
})

const processedRules = computed(() =>
  firstCount(
    currentJob.value?.summary?.progress?.processed_rule_count,
    currentJob.value?.summary?.processed_rule_count,
  ),
)
const totalRules = computed(() =>
  firstCount(
    currentJob.value?.summary?.customer_rule_count,
    currentJob.value?.customer_rule_count,
    currentJob.value?.summary?.rule_count,
    currentJob.value?.rule_count,
    currentJob.value?.summary?.progress?.rule_count,
  ),
)

const ruleProgressText = computed(() => {
  if (processedRules.value === null || totalRules.value === null) return ''
  const prefix = (totalRecords.value ?? 0) > 1 ? '当前单份规则进度' : '已执行'
  return `${prefix} ${Math.min(processedRules.value, totalRules.value)} / ${totalRules.value} 个质控点`
})

const multiRecordRuntime = computed(() => {
  if (!currentJob.value || currentJob.value.status !== 'running' || (totalRecords.value ?? 0) <= 1)
    return null
  const progress = currentJob.value.summary?.progress
  const parallel = firstCount(progress?.max_parallel_records)
  const active = firstCount(progress?.active_record_count)
  const queued = firstCount(progress?.queued_record_count)
  if (parallel === null || active === null || queued === null) return null
  return {
    parallel,
    active,
    completed: Math.min(processedRecords.value ?? 0, totalRecords.value ?? 0),
    queued,
  }
})

const progressPercent = computed(() => {
  if (currentJob.value?.status === 'completed') return 100
  const reported = finiteCount(currentJob.value?.summary?.progress_percent)
  if (reported !== null && reported > 0) return Math.min(100, reported)
  if (!totalRecords.value) return null
  const currentRuleFraction =
    processedRules.value !== null && totalRules.value
      ? Math.min(1, processedRules.value / totalRules.value)
      : 0
  return Math.min(
    100,
    Math.round((((processedRecords.value ?? 0) + currentRuleFraction) / totalRecords.value) * 100),
  )
})

const statusTitle = computed(() => {
  const status = currentJob.value?.status
  if (status === 'queued') return '质控任务已进入队列'
  if (status === 'running') return '正在执行质控'
  if (status === 'completed') return '质控任务已完成'
  if (status === 'failed') return '质控任务未完成'
  if (status === 'canceled') return '质控任务已停止'
  return '正在准备质控任务'
})

const statusBadge = computed(() => {
  const status = currentJob.value?.status
  if (status === 'queued') return '等待执行'
  if (status === 'running') return '执行中'
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '执行失败'
  if (status === 'canceled') return '已停止'
  return '准备中'
})

const stepLabels: Record<string, string> = {
  queued: '等待执行',
  prepare: '准备病历资料',
  filter: '确认病历范围',
  run: '执行质控规则',
  aggregate: '汇总质控结果',
  completed: '生成最终结果',
  failed: '执行未完成',
  canceled: '任务已停止',
}

type WorkflowStageState = 'complete' | 'active' | 'pending' | 'error'

interface WorkflowStageItem {
  key: 'scope' | 'records' | 'rules' | 'result'
  label: string
  detail: string
  state: WorkflowStageState
}

const workflowStages = computed<WorkflowStageItem[]>(() => {
  const status = currentJob.value?.status
  const stepKey = String(currentJob.value?.summary?.progress?.step_key || '').trim()
  const activeStageIndex =
    status === 'queued' || !stepKey
      ? 0
      : stepKey === 'filter'
        ? 0
        : stepKey === 'prepare'
          ? 1
          : stepKey === 'aggregate'
            ? 3
            : stepKey === 'completed' || stepKey === 'failed' || stepKey === 'canceled'
              ? 3
              : 2
  const terminalCompleted = status === 'completed'
  const terminalError = status === 'failed' || status === 'canceled'
  const stateFor = (index: number): WorkflowStageState => {
    if (terminalCompleted) return 'complete'
    if (index < activeStageIndex) return 'complete'
    if (index === activeStageIndex) return terminalError ? 'error' : 'active'
    return 'pending'
  }
  const ruleDetail =
    processedRules.value !== null && totalRules.value !== null
      ? `${Math.min(processedRules.value, totalRules.value)} / ${totalRules.value} 个质控点`
      : stateFor(2) === 'active'
        ? '正在逐项执行'
        : '等待执行'

  return [
    {
      key: 'scope',
      label: '确认质控范围',
      detail: totalRecords.value === null ? '正在确认病历' : `本次共 ${totalRecords.value} 份病历`,
      state: stateFor(0),
    },
    {
      key: 'records',
      label: '准备病历资料',
      detail: stateFor(1) === 'complete' ? '质控资料已准备' : '正在整理质控资料',
      state: stateFor(1),
    },
    {
      key: 'rules',
      label: '执行质控规则',
      detail: ruleDetail,
      state: stateFor(2),
    },
    {
      key: 'result',
      label: '汇总并保存结果',
      detail: terminalCompleted
        ? '结果已保存'
        : stateFor(3) === 'active'
          ? '正在生成最终结果'
          : '等待规则执行完成',
      state: stateFor(3),
    },
  ]
})

const stageText = computed(() => {
  const status = currentJob.value?.status
  if (status === 'queued') return '系统正在分配执行资源，开始后将自动更新病历和质控点进度。'
  if (status === 'completed') return '质控结果已生成，请前往运行病历质控或终末病历质控查看。'
  if (status === 'failed') return '部分或全部病历未完成质控，请稍后重新发起或联系管理员。'
  if (status === 'canceled') return '任务已停止，未完成的病历不会继续执行。'
  const currentRule = currentJob.value?.summary?.current_rule
  const ruleCode = String(currentRule?.rule_code || '').trim()
  const ruleName = String(currentRule?.rule_name || '').trim()
  if (ruleCode || ruleName) return `当前：${[ruleCode, ruleName].filter(Boolean).join(' ')}`
  const progress = currentJob.value?.summary?.progress
  const stepKey = String(progress?.step_key || '').trim()
  if (stepLabels[stepKey]) return `当前阶段：${stepLabels[stepKey]}`
  return '正在处理病历和质控规则，结果会自动更新。'
})

const terminalSummary = computed(() => {
  if (currentJob.value?.status !== 'completed') return ''
  return `成功 ${successRecords.value} 份 · 失败 ${failedRecords.value} 份`
})

const tone = computed(() => {
  const status = currentJob.value?.status
  if (status === 'completed') return 'success'
  if (status === 'failed' || status === 'canceled') return 'danger'
  return 'active'
})

const progressStatus = computed(() => {
  if (currentJob.value?.status === 'completed') return 'success'
  if (currentJob.value?.status === 'failed') return 'exception'
  return 'active'
})

function clearPollTimer() {
  if (!pollTimer) return
  clearTimeout(pollTimer)
  pollTimer = null
}

function schedulePoll(sequence: number) {
  clearPollTimer()
  if (!isActive.value) return
  pollTimer = setTimeout(() => void refreshJob(sequence), Math.max(500, props.pollIntervalMs))
}

async function refreshJob(sequence: number) {
  const jobId = String(currentJob.value?.id || '').trim()
  if (!jobId || sequence !== requestSequence || !isActive.value) return
  const result = await getSichuanWorkspaceBatchJob(jobId)
  if (sequence !== requestSequence) return
  if (result.success && result.data) {
    currentJob.value = result.data
    pollError.value = false
  } else {
    pollError.value = true
  }
  schedulePoll(sequence)
}

watch(
  () => props.job,
  (job) => {
    requestSequence += 1
    clearPollTimer()
    currentJob.value = job
    pollError.value = false
    if (job && !terminalStatuses.has(job.status)) void refreshJob(requestSequence)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  requestSequence += 1
  clearPollTimer()
})
</script>

<style scoped>
.record-pool-qc-status {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  overflow: hidden;
  padding: 16px 18px 15px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow:
    0 2px 10px rgba(29, 29, 31, 0.04),
    0 8px 24px rgba(0, 70, 140, 0.045);
  color: #1d1d1f;
}

.record-pool-qc-status::before {
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: #0066cc;
  content: '';
}

.record-pool-qc-status--success {
  border-color: rgba(16, 185, 129, 0.2);
}

.record-pool-qc-status--success::before {
  background: #10b981;
}

.record-pool-qc-status--danger {
  border-color: rgba(239, 68, 68, 0.2);
}

.record-pool-qc-status--danger::before {
  background: #ef4444;
}

.record-pool-qc-status__main {
  display: flex;
  min-width: 0;
  flex: 1;
  gap: 12px;
}

.record-pool-qc-status__actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
}

.record-pool-qc-status__export {
  min-height: 34px;
  padding: 0 13px;
  border: 1px solid rgba(5, 150, 105, 0.22);
  border-radius: 9px;
  background: rgba(5, 150, 105, 0.08);
  color: #047857;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
}

.record-pool-qc-status__export:disabled {
  cursor: wait;
  opacity: 0.58;
}

.record-pool-qc-status__indicator {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  place-items: center;
  border: 1px solid rgba(0, 102, 204, 0.12);
  border-radius: 11px;
  background: #f1f6ff;
  color: #0066cc;
}

.record-pool-qc-status--success .record-pool-qc-status__indicator {
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}

.record-pool-qc-status--danger .record-pool-qc-status__indicator {
  background: rgba(239, 68, 68, 0.09);
  color: #dc2626;
}

.record-pool-qc-status__content {
  min-width: 0;
  flex: 1;
}

.record-pool-qc-status__eyebrow {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
  color: rgba(29, 29, 31, 0.42);
  font-size: 11px;
  line-height: 16px;
  font-weight: 650;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.record-pool-qc-status__eyebrow-dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: currentColor;
}

.record-pool-qc-status__heading,
.record-pool-qc-status__metrics {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
}

.record-pool-qc-status__heading strong {
  font-size: 15px;
  line-height: 22px;
  font-weight: 650;
}

.record-pool-qc-status__heading span {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
  font-size: 12px;
  line-height: 18px;
  font-weight: 600;
}

.record-pool-qc-status__heading em {
  margin-left: auto;
  color: #0066cc;
  font-size: 14px;
  line-height: 20px;
  font-style: normal;
  font-weight: 750;
}

.record-pool-qc-status--success .record-pool-qc-status__heading em {
  color: #047857;
}

.record-pool-qc-status--danger .record-pool-qc-status__heading em {
  color: #b91c1c;
}

.record-pool-qc-status__metrics {
  margin-top: 4px;
  color: rgba(29, 29, 31, 0.72);
  font-size: 13px;
  line-height: 20px;
  font-weight: 550;
}

.record-pool-qc-status__progress {
  max-width: 760px;
  margin-top: 9px;
}

.record-pool-qc-status__progress :deep(.ant-progress-inner) {
  background: rgba(0, 0, 0, 0.06);
}

.record-pool-qc-status__progress :deep(.ant-progress-bg) {
  height: 6px !important;
  border-radius: 999px;
}

.record-pool-qc-status__concurrency {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.record-pool-qc-status__concurrency span {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  padding: 4px 9px;
  border: 1px solid rgba(0, 0, 0, 0.07);
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.025);
  color: rgba(29, 29, 31, 0.62);
  font-size: 12px;
  line-height: 18px;
  font-weight: 550;
}

.record-pool-qc-status__concurrency strong {
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 700;
}

.record-pool-qc-status__concurrency span.is-active {
  border-color: rgba(0, 102, 204, 0.14);
  background: rgba(0, 102, 204, 0.07);
  color: #0055aa;
}

.record-pool-qc-status__concurrency span.is-active strong {
  color: #0066cc;
}

.record-pool-qc-status__concurrency span.is-complete {
  border-color: rgba(16, 185, 129, 0.14);
  background: rgba(16, 185, 129, 0.065);
  color: #047857;
}

.record-pool-qc-status__concurrency span.is-complete strong {
  color: #047857;
}

.record-pool-qc-status__indeterminate {
  height: 4px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.1);
}

.record-pool-qc-status__indeterminate span {
  display: block;
  width: 34%;
  height: 100%;
  border-radius: inherit;
  background: #0066cc;
  animation: record-pool-qc-progress 1.35s ease-in-out infinite;
}

.record-pool-qc-status__stages {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  max-width: 820px;
  margin: 13px 0 0;
  padding: 0;
  list-style: none;
}

.record-pool-qc-status__stages li {
  position: relative;
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px 8px 0;
  color: rgba(29, 29, 31, 0.48);
}

.record-pool-qc-status__stages li:not(:last-child)::after {
  position: absolute;
  top: 14px;
  right: 10px;
  left: 17px;
  height: 1px;
  background: rgba(29, 29, 31, 0.1);
  content: '';
}

.record-pool-qc-status__stage-marker {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  z-index: 1;
  margin-top: 4px;
  border: 2px solid rgba(29, 29, 31, 0.18);
  border-radius: 999px;
  background: #fff;
}

.record-pool-qc-status__stage-copy {
  display: grid;
  min-width: 0;
  gap: 1px;
}

.record-pool-qc-status__stage-copy strong {
  overflow: hidden;
  font-size: 13px;
  line-height: 19px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-pool-qc-status__stage-copy small {
  overflow: hidden;
  font-size: 12px;
  line-height: 18px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-pool-qc-status__stages li.is-complete {
  color: #047857;
}

.record-pool-qc-status__stages li.is-complete .record-pool-qc-status__stage-marker {
  border-color: #10b981;
  background: #10b981;
}

.record-pool-qc-status__stages li.is-active {
  color: #0055aa;
}

.record-pool-qc-status__stages li.is-active .record-pool-qc-status__stage-marker {
  border-color: #0066cc;
  box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.1);
}

.record-pool-qc-status__stages li.is-error {
  color: #b91c1c;
}

.record-pool-qc-status__stages li.is-error .record-pool-qc-status__stage-marker {
  border-color: #ef4444;
  background: #ef4444;
}

.record-pool-qc-status__stage,
.record-pool-qc-status__refresh-note {
  margin: 5px 0 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  line-height: 18px;
}

.record-pool-qc-status__refresh-note {
  color: #b45309;
}

.record-pool-qc-status__dismiss {
  display: grid;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  cursor: pointer;
  place-items: center;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: rgba(29, 29, 31, 0.48);
}

.record-pool-qc-status__dismiss:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #1d1d1f;
}

.record-pool-qc-status__spinner {
  animation: record-pool-qc-spin 1s linear infinite;
}

@keyframes record-pool-qc-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes record-pool-qc-progress {
  from {
    transform: translateX(-110%);
  }
  to {
    transform: translateX(300%);
  }
}

@media (max-width: 720px) {
  .record-pool-qc-status {
    padding: 12px;
  }

  .record-pool-qc-status__metrics {
    display: grid;
    gap: 2px;
  }

  .record-pool-qc-status__stages {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 4px 0;
  }

  .record-pool-qc-status__stages li:not(:last-child)::after {
    display: none;
  }
}
</style>
