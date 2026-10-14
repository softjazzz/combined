<template>
  <section
    v-if="currentJob"
    class="record-pool-qc-status"
    :class="[`record-pool-qc-status--${tone}`, { 'is-active': isActive }]"
    role="status"
    aria-live="polite"
    data-testid="record-pool-qc-task-status"
  >
    <div class="record-pool-qc-status__main">
      <div
        v-if="!isActive"
        class="record-pool-qc-status__indicator"
        aria-hidden="true"
      >
        <CircleCheckBig
          v-if="currentJob.status === 'completed'"
          :size="18"
        />
        <CircleAlert
          v-else
          :size="18"
        />
      </div>

      <div class="record-pool-qc-status__content">
        <div class="record-pool-qc-status__heading">
          <i
            v-if="isActive"
            class="record-pool-qc-status__live-dot"
            aria-hidden="true"
          />
          <strong>{{ statusTitle }}</strong>
          <span v-if="isActive">{{ currentJob.status === 'queued' ? '排队中' : '执行中' }}</span>
          <em v-if="isActive && progressPercent !== null">{{ progressPercent }}<small>%</small></em>
        </div>
        <p
          v-if="isActive"
          class="record-pool-qc-status__phase"
        >
          {{ stageText }}
        </p>

        <div
          v-if="isActive && progressPercent !== null"
          class="record-pool-qc-status__progress"
          role="progressbar"
          aria-label="质控执行进度"
          :aria-valuenow="progressPercent"
          :aria-valuemin="0"
          :aria-valuemax="100"
        >
          <span :style="{ width: `${progressPercent}%` }" />
        </div>

        <div class="record-pool-qc-status__metrics">
          <span v-if="ruleProgressText">{{ ruleProgressText }}</span>
          <span v-if="terminalSummary">{{ terminalSummary }}</span>
          <span class="record-pool-qc-status__record-count">{{ recordProgressText }}</span>
        </div>

        <p
          v-if="isActive && progressPercent === 100"
          class="record-pool-qc-status__settling"
        >
          处理进度已达 100%，正在等待任务最终确认；完成汇总与保存后将更新任务状态。
        </p>

        <details class="record-pool-qc-status__details">
          <summary>{{ isActive ? '查看执行详情' : '查看任务详情' }}</summary>
          <div
            v-if="multiRecordRuntime"
            class="record-pool-qc-status__concurrency"
            data-testid="record-pool-qc-concurrency"
            aria-label="多病历并发执行状态"
          >
            <span>并发 <strong>{{ multiRecordRuntime.parallel }}</strong> 份</span>
            <span class="is-active">执行中 <strong>{{ multiRecordRuntime.active }}</strong> 份</span>
            <span class="is-complete">已完成 <strong>{{ multiRecordRuntime.completed }}</strong> 份</span>
            <span>排队 <strong>{{ multiRecordRuntime.queued }}</strong> 份</span>
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
              :title="stage.detail"
            >
              <span
                class="record-pool-qc-status__stage-marker"
                aria-hidden="true"
              >{{
                stage.state === 'complete' ? '✓' : ''
              }}</span>
              <span class="record-pool-qc-status__stage-copy">
                <strong>{{ stage.label }}</strong>
              </span>
            </li>
          </ol>

          <p
            v-if="stageText.startsWith('当前：')"
            class="record-pool-qc-status__stage"
          >
            {{ stageText }}
          </p>
        </details>
        <p
          v-if="!isActive && currentJob.status !== 'completed'"
          class="record-pool-qc-status__refresh-note"
        >
          {{ stageText }}
        </p>
        <p
          v-if="pollError"
          class="record-pool-qc-status__refresh-note"
        >
          进度暂时未更新，系统将自动重试。
        </p>
      </div>
    </div>

    <div
      v-if="!isActive"
      class="record-pool-qc-status__actions"
    >
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
import { CircleAlert, CircleCheckBig, X } from 'lucide-vue-next'
import {
  exportSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import type { SichuanBatchJob } from '../../semantic-rules/types'
import { isBatchJobPollingActive } from '../../semantic-rules/utils/batchJobStatus'
import { decidePollReadFailure } from '../../customer-sample-validation/batchJobPollReadPolicy'
import {
  downloadBlob,
  normalizeBatchExportBlob,
} from '../../customer-sample-validation/batchExport'

const props = withDefaults(
  defineProps<{
    job: SichuanBatchJob | null
    pollIntervalMs?: number
    autoPoll?: boolean
  }>(),
  {
    pollIntervalMs: 2000,
    autoPoll: true,
  },
)

const emit = defineEmits<{
  dismiss: []
  completed: []
}>()

const currentJob = ref<SichuanBatchJob | null>(null)
const pollError = ref(false)
const resultReadError = ref('')
const exporting = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | null = null
let requestSequence = 0

const DELIVERY_CONTRACT_ERROR = '历史质控结果交付合同不完整，无法安全展示'

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

const isActive = computed(() => !resultReadError.value && isBatchJobPollingActive(currentJob.value))
const automaticRetrying = computed(() => isActive.value && currentJob.value?.status === 'failed')

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
  if (resultReadError.value) return '质控结果暂不可查看'
  if (automaticRetrying.value) return '正在自动补跑失败项'
  if (status === 'queued') return '质控任务已进入队列'
  if (status === 'running') return '正在执行质控'
  if (status === 'completed') return '质控任务已完成'
  if (status === 'failed') return '质控任务未完成'
  if (status === 'canceled') return '质控任务已停止'
  return '正在准备质控任务'
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
  const terminalError = !automaticRetrying.value && (status === 'failed' || status === 'canceled')
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
  if (resultReadError.value) return resultReadError.value
  if (automaticRetrying.value) return '部分规则输出无效，系统正在自动补跑，已有有效结果会继续保留。'
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
  if (resultReadError.value) return 'danger'
  if (status === 'completed') return 'success'
  if (automaticRetrying.value) return 'active'
  if (status === 'failed' || status === 'canceled') return 'danger'
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
    const wasCompleted = currentJob.value?.status === 'completed'
    currentJob.value = result.data
    pollError.value = false
    resultReadError.value = ''
    if (!wasCompleted && result.data.status === 'completed') emit('completed')
  } else {
    // 结果交付不完整等确定性失败（文案或 409/404 状态码）停止轮询，避免无限重复请求
    if (
      result.message?.includes(DELIVERY_CONTRACT_ERROR) ||
      decidePollReadFailure(result.status, 0, result.jobStatus) === 'stop_terminal'
    ) {
      pollError.value = false
      resultReadError.value = result.message || '任务结果暂无法展示'
      clearPollTimer()
      return
    }
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
    resultReadError.value = ''
    if (job && props.autoPoll && isBatchJobPollingActive(job)) void refreshJob(requestSequence)
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
  gap: 20px;
  overflow: hidden;
  padding: 16px 20px;
  border: 1px solid rgba(10, 108, 255, 0.13);
  border-radius: 10px;
  background: #fff;
  box-shadow: none;
  color: #1d1d1f;
}

.record-pool-qc-status::before {
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: #0a6cff;
  content: none;
}

/* 执行态沿用客户样本验证状态条的视觉层级，任务数据仍由原组件负责。 */
.record-pool-qc-status.is-active {
  padding: 16px;
  border-color: rgba(10, 108, 255, 0.18);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 8px 22px rgba(37, 99, 235, 0.08);
}
.record-pool-qc-status__live-dot {
  width: 9px;
  height: 9px;
  flex: none;
  margin: 0 5px;
  border-radius: 50%;
  background: #0a6cff;
  box-shadow: 0 0 0 5px rgba(10, 108, 255, 0.1);
}
.record-pool-qc-status__phase {
  margin: -4px 0 2px 28px;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  line-height: 20px;
}
.record-pool-qc-status.is-active .record-pool-qc-status__heading strong {
  font-size: 16px;
  line-height: 24px;
  font-weight: 650;
}
.record-pool-qc-status.is-active .record-pool-qc-status__progress {
  height: 8px;
  border-radius: 999px;
  background: rgba(10, 108, 255, 0.1);
}
.record-pool-qc-status__percent {
  color: #175d9c;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}

.record-pool-qc-status--success {
  border-color: #e3eaf2;
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
  gap: 14px;
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
  border: 1px solid #dde5ef;
  border-radius: 9px;
  background: #fff;
  color: #52677f;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}
.record-pool-qc-status__export:hover:not(:disabled) {
  border-color: #bbd2ec;
  background: #f5f8fc;
  color: #0a6cff;
}

.record-pool-qc-status__export:disabled {
  cursor: wait;
  opacity: 0.58;
}

.record-pool-qc-status__indicator {
  display: grid;
  width: 24px;
  height: 24px;
  flex: 0 0 24px;
  place-items: center;
  border: 0;
  border-radius: 12px;
  background: transparent;
  color: #0a6cff;
}

.record-pool-qc-status--success .record-pool-qc-status__indicator {
  background: transparent;
  color: #66819e;
}

.record-pool-qc-status--danger .record-pool-qc-status__indicator {
  background: rgba(239, 68, 68, 0.09);
  color: #dc2626;
}

.record-pool-qc-status__content {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 8px;
  min-width: 0;
  flex: 1;
}
.record-pool-qc-status__heading,
.record-pool-qc-status__progress,
.record-pool-qc-status__concurrency,
.record-pool-qc-status__stage,
.record-pool-qc-status__refresh-note {
  grid-column: 1 / -1;
}
.record-pool-qc-status__progress {
  height: 4px;
  border-radius: 4px;
  overflow: hidden;
  background: #edf1f6;
}
.record-pool-qc-status__progress > span {
  display: block;
  height: 100%;
  background: #0a6cff;
  border-radius: inherit;
  transition: width 200ms ease;
}
.record-pool-qc-status--danger .record-pool-qc-status__progress > span {
  background: #c45151;
}
.record-pool-qc-status--success .record-pool-qc-status__progress > span {
  background: #398577;
}

.record-pool-qc-status__heading,
.record-pool-qc-status__metrics {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
}

.record-pool-qc-status__heading strong {
  font-size: 14px;
  line-height: 22px;
  font-weight: 600;
}

.record-pool-qc-status__heading span {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(10, 108, 255, 0.08);
  color: #0a6cff;
  font-size: 12px;
  line-height: 18px;
  font-weight: 600;
}

.record-pool-qc-status__heading em {
  margin-left: auto;
  color: #253247;
  font-size: 14px;
  line-height: 20px;
  font-style: normal;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.record-pool-qc-status--success .record-pool-qc-status__heading em {
  color: #047857;
}

.record-pool-qc-status--danger .record-pool-qc-status__heading em {
  color: #b91c1c;
}

.record-pool-qc-status__metrics {
  margin-top: 0;
  color: #76808c;
  font-size: 12px;
  line-height: 20px;
  font-weight: 400;
}
.record-pool-qc-status__record-count {
  margin-left: auto;
}
.record-pool-qc-status__details {
  font-size: 12px;
  color: #76808c;
}
.record-pool-qc-status__details summary {
  cursor: pointer;
  width: fit-content;
}
.record-pool-qc-status__details[open] {
  padding-top: 8px;
  border-top: 1px solid #edf1f6;
}
.record-pool-qc-status__details .record-pool-qc-status__stages {
  justify-content: flex-start;
  margin-top: 10px;
}
@media (prefers-reduced-motion: reduce) {
  .record-pool-qc-status__progress > span {
    transition: none;
  }
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
  border-color: rgba(10, 108, 255, 0.14);
  background: rgba(10, 108, 255, 0.07);
  color: #0055aa;
}

.record-pool-qc-status__concurrency span.is-active strong {
  color: #0a6cff;
}

.record-pool-qc-status__concurrency span.is-complete {
  border-color: rgba(16, 185, 129, 0.14);
  background: rgba(16, 185, 129, 0.065);
  color: #047857;
}

.record-pool-qc-status__concurrency span.is-complete strong {
  color: #047857;
}

.record-pool-qc-status__stages {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px 16px;
  width: 100%;
  margin: 0;
  padding: 0;
  list-style: none;
}

.record-pool-qc-status__stages li {
  position: relative;
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  min-height: 20px;
  padding: 0;
  border: 0;
  background: transparent;
  color: rgba(29, 29, 31, 0.48);
}

.record-pool-qc-status__stage-marker {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  z-index: 1;
  margin-top: 0;
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

.record-pool-qc-status__stage-progress {
  position: absolute;
  top: -11px;
  right: 12px;
  padding: 3px 8px;
  border: 1px solid rgba(10, 108, 255, 0.2);
  border-radius: 999px;
  background: #fff;
  color: #0a6cff;
  font-size: 11px;
  line-height: 16px;
  font-weight: 700;
  box-shadow: 0 3px 10px rgba(10, 108, 255, 0.1);
}

.record-pool-qc-status__stages li.is-complete {
  color: #728599;
}

.record-pool-qc-status__stages li.is-complete .record-pool-qc-status__stage-marker {
  border: 0;
  background: transparent;
  width: 12px;
  height: 16px;
  flex-basis: 12px;
  line-height: 16px;
}

.record-pool-qc-status__stages li.is-active {
  border-color: rgba(10, 108, 255, 0.42);
  background: transparent;
  color: #0055aa;
}

.record-pool-qc-status__stages li.is-active .record-pool-qc-status__stage-marker {
  border-color: #0a6cff;
  box-shadow: 0 0 0 3px rgba(10, 108, 255, 0.1);
}

.record-pool-qc-status__stages li.is-error {
  border-color: rgba(239, 68, 68, 0.28);
  background: transparent;
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

@media (max-width: 720px) {
  .record-pool-qc-status {
    padding: 12px;
  }

  .record-pool-qc-status__metrics {
    display: grid;
    gap: 2px;
  }

  .record-pool-qc-status__stages {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }
}
/* 任务面板：以文字层次与细进度条呈现执行情况。 */
.record-pool-qc-status,
.record-pool-qc-status.is-active {
  padding: 20px 24px;
  border: 1px solid #e3e8f0;
  border-radius: 16px;
  background: #fafbfe;
  box-shadow: none;
  font-family: 'Microsoft YaHei UI', 'PingFang SC', 'Segoe UI', sans-serif;
}
.record-pool-qc-status__main {
  flex: 1;
  min-width: 0;
}
.record-pool-qc-status__content {
  width: 100%;
  min-width: 0;
}
.record-pool-qc-status__heading {
  gap: 10px;
}
.record-pool-qc-status.is-active .record-pool-qc-status__heading strong {
  font-size: 15px;
  font-weight: 600;
}
.record-pool-qc-status__heading em {
  font-size: 24px;
  line-height: 30px;
  color: #0a6cff;
  letter-spacing: -0.5px;
}
.record-pool-qc-status__heading em small {
  font-size: 13px;
  margin-left: 3px;
}
.record-pool-qc-status__heading span {
  background: #eaf3ff;
  color: #3474b7;
  font-weight: 400;
}
.record-pool-qc-status__live-dot {
  width: 7px;
  height: 7px;
  margin: 0 3px;
  background: #0a6cff;
  box-shadow: 0 0 0 4px #e5efff;
}
.record-pool-qc-status__phase {
  margin: 0;
  color: #6e7684;
  font-size: 13px;
}
.record-pool-qc-status.is-active .record-pool-qc-status__progress {
  height: 5px;
  margin: 6px 0;
  background: #e6ebf3;
  border-radius: 99px;
}
.record-pool-qc-status__progress > span {
  background: #0a6cff;
}
.record-pool-qc-status__metrics {
  gap: 8px 20px;
  font-size: 13px;
  color: #667085;
}
.record-pool-qc-status__record-count {
  font-weight: 500;
  color: #344054;
}
.record-pool-qc-status__details {
  margin-top: 8px;
}
.record-pool-qc-status__details summary {
  padding: 5px 0;
  color: #55708f;
  font-size: 12px;
}
.record-pool-qc-status__details summary:focus-visible {
  outline: 2px solid #0a6cff;
  outline-offset: 3px;
  border-radius: 4px;
}
.record-pool-qc-status__details[open] {
  border-top-color: #e5e9f0;
}
.record-pool-qc-status__stages {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  padding: 10px 0;
}
.record-pool-qc-status__stage-copy strong {
  font-size: 12px;
  font-weight: 400;
  white-space: normal;
}
.record-pool-qc-status__concurrency span {
  border: 0;
  border-radius: 6px;
  font-weight: 400;
}
.record-pool-qc-status__settling {
  margin: 0;
  font-size: 12px;
  line-height: 20px;
  color: #6e7684;
}
.record-pool-qc-status--danger {
  background: #fffaf7;
  border-color: #efdfd4;
}
.record-pool-qc-status--success {
  background: #f6fbf8;
  border-color: #deebe4;
}
.record-pool-qc-status__refresh-note {
  line-height: 20px;
}
@media (max-width: 700px) {
  .record-pool-qc-status,
  .record-pool-qc-status.is-active {
    padding: 16px;
  }
  .record-pool-qc-status__stages {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .record-pool-qc-status__record-count {
    margin-left: 0;
  }
}
</style>
