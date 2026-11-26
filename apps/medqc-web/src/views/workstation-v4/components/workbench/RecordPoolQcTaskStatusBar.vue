<template>
  <section
    v-if="currentJob"
    class="record-pool-qc-status"
    :class="[`record-pool-qc-status--${tone}`, { 'is-active': isActive, 'is-expanded': detailsOpen }]"
    role="status"
    aria-live="polite"
    data-testid="record-pool-qc-task-status"
  >
    <div class="record-pool-qc-status__bar">
      <div class="record-pool-qc-status__main">
        <div
          v-if="!isActive"
          class="record-pool-qc-status__indicator"
          aria-hidden="true"
        >
          <CircleCheckBig
            v-if="currentJob.status === 'completed'"
            :size="16"
          />
          <CircleAlert
            v-else
            :size="16"
          />
        </div>

        <div class="record-pool-qc-status__heading">
          <i
            v-if="isActive"
            class="record-pool-qc-status__live-dot"
            aria-hidden="true"
          />
          <strong>{{ statusTitle }}</strong>
          <span v-if="isActive" class="record-pool-qc-status__badge">
            {{ currentJob.status === 'queued' ? '排队中' : '执行中' }}
          </span>
        </div>

        <p
          v-if="isActive"
          class="record-pool-qc-status__phase"
          :title="stageText"
        >
          {{ stageText }}
        </p>

        <div class="record-pool-qc-status__metrics">
          <span v-if="ruleProgressText">{{ ruleProgressText }}</span>
          <span v-if="terminalSummary">{{ terminalSummary }}</span>
          <span class="record-pool-qc-status__record-count">{{ recordProgressText }}</span>
        </div>
      </div>

      <div class="record-pool-qc-status__actions">
        <Popconfirm
          v-if="canCancel"
          title="确认停止当前质控任务？已完成的病历结果会保留，未执行的病历将不再继续。"
          ok-text="确认停止"
          cancel-text="继续执行"
          :ok-button-props="{ danger: true, loading: canceling }"
          placement="bottomRight"
          :disabled="canceling"
          @confirm="cancelCurrentBatch"
        >
          <button
            type="button"
            class="record-pool-qc-status__cancel"
            :disabled="canceling"
            data-testid="record-pool-qc-cancel-btn"
          >
            <Square
              :size="11"
              aria-hidden="true"
            />
            <span>{{ canceling ? '停止中…' : '停止' }}</span>
          </button>
        </Popconfirm>

        <button
          type="button"
          class="record-pool-qc-status__details-toggle"
          :aria-expanded="detailsOpen"
          data-testid="record-pool-qc-details-toggle"
          @click="detailsOpen = !detailsOpen"
        >
          <span>{{ detailsOpen ? '收起' : '详情' }}</span>
          <ChevronDown
            :size="14"
            class="record-pool-qc-status__details-chevron"
            :class="{ 'is-open': detailsOpen }"
            aria-hidden="true"
          />
        </button>

        <template v-if="!isActive">
          <button
            v-if="inlineResultViewer && canViewResults"
            type="button"
            class="record-pool-qc-status__detail-link"
            data-testid="qc-task-detail-link"
            @click="emit('view-results', currentJob)"
          >
            {{ confirmedResultsOnly ? '查看本次质控结果' : '查看本次结果与失败原因' }}
          </button>
          <RouterLink
            v-else-if="canViewResults"
            :to="`/workstation-v5/qc-task?job_id=${encodeURIComponent(currentJob.id)}`"
            class="record-pool-qc-status__detail-link"
            data-testid="qc-task-detail-link"
          >
            {{ confirmedResultsOnly ? '查看本次质控结果' : '查看本次结果与失败原因' }}
          </RouterLink>
          <button
            v-if="currentJob.status === 'completed' && !confirmedResultsOnly"
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
            <X :size="15" />
          </button>
        </template>
      </div>
    </div>

    <div
      v-if="isActive && progressPercent !== null"
      class="record-pool-qc-status__progress-group"
    >
      <div
        class="record-pool-qc-status__progress"
        :class="{ 'is-indeterminate': progressPercent === 0 }"
        role="progressbar"
        aria-label="质控执行进度"
        :aria-valuenow="progressPercent"
        :aria-valuemin="0"
        :aria-valuemax="100"
      >
        <span :style="{ width: `${progressPercent}%` }" />
      </div>
      <em class="record-pool-qc-status__percent">{{ progressPercent }}<small>%</small></em>
    </div>

    <p
      v-if="isActive && progressPercent === 100"
      class="record-pool-qc-status__settling"
    >
      处理进度已达 100%，正在等待任务最终确认；完成汇总与保存后将更新任务状态。
    </p>
    <p
      v-if="!isActive && currentJob.status !== 'completed'"
      :class="
        currentJob.status === 'canceled'
          ? 'record-pool-qc-status__settling'
          : 'record-pool-qc-status__refresh-note'
      "
    >
      {{ stageText }}
    </p>
    <p
      v-if="pollError"
      class="record-pool-qc-status__refresh-note"
    >
      进度暂时未更新，正在重试读取任务状态。
    </p>

    <div
      v-show="detailsOpen"
      class="record-pool-qc-status__details-panel"
      data-testid="record-pool-qc-details-panel"
    >
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
    </div>
  </section>
</template>

<script setup lang="ts">
import { Popconfirm, message } from 'ant-design-vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ChevronDown, CircleAlert, CircleCheckBig, Square, X } from 'lucide-vue-next'
import { useQcResultVisibility } from '@/composables/useQcResultVisibility'
import {
  cancelSichuanWorkspaceBatchJob,
  exportSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import type { SichuanBatchJob } from '../../semantic-rules/types'
import {
  getBatchJobRetryMessage,
  isBatchJobFinished,
  isBatchJobPollingActive,
} from '../../semantic-rules/utils/batchJobStatus'
import {
  decidePollReadFailure,
  pollReadFailureMessage,
} from '../../customer-sample-validation/batchJobPollReadPolicy'
import {
  downloadBlob,
  normalizeBatchExportBlob,
} from '../../customer-sample-validation/batchExport'

const props = withDefaults(
  defineProps<{
    job: SichuanBatchJob | null
    pollIntervalMs?: number
    autoPoll?: boolean
    inlineResultViewer?: boolean
  }>(),
  {
    pollIntervalMs: 2000,
    autoPoll: true,
    inlineResultViewer: false,
  },
)

const emit = defineEmits<{
  dismiss: []
  completed: []
  canceled: [job: SichuanBatchJob]
  'results-updated': []
  'view-results': [job: SichuanBatchJob]
}>()

const { confirmedResultsOnly } = useQcResultVisibility()
const currentJob = ref<SichuanBatchJob | null>(null)
const pollError = ref(false)
const resultReadError = ref('')
const exporting = ref(false)
const canceling = ref(false)
const detailsOpen = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | null = null
let requestSequence = 0
let consecutiveReadFailures = 0

const DELIVERY_CONTRACT_ERROR = '历史质控结果交付合同不完整，无法安全展示'

async function cancelCurrentBatch() {
  const jobId = String(currentJob.value?.id || '').trim()
  if (!jobId || !canCancel.value || canceling.value) return
  canceling.value = true
  try {
    const response = await cancelSichuanWorkspaceBatchJob(jobId)
    if (!response.success || !response.data) {
      message.error(response.message || '停止质控任务失败，请稍后重试')
      return
    }
    requestSequence += 1
    clearPollTimer()
    currentJob.value = response.data
    pollError.value = false
    emit('canceled', response.data)
    emit('results-updated')
    message.success('已停止当前质控任务')
  } catch {
    message.error('停止质控任务失败，请稍后重试')
  } finally {
    canceling.value = false
  }
}

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
const canCancel = computed(() => {
  const status = String(currentJob.value?.status || '')
    .trim()
    .toLowerCase()
  return isActive.value && (status === 'queued' || status === 'running')
})
const canViewResults = computed(() => {
  const status = String(currentJob.value?.status || '')
    .trim()
    .toLowerCase()
  if (status !== 'canceled' && status !== 'cancelled') return true
  return (processedRecords.value ?? 0) > 0
})
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

const hasUnfinishedMultiRecords = computed(() => {
  const total = totalRecords.value ?? 0
  if (total <= 1) return false
  const completed = processedRecords.value ?? 0
  const active = multiRecordRuntime.value?.active ?? 0
  const queued = multiRecordRuntime.value?.queued ?? 0
  return completed < total || active > 0 || queued > 0
})

// 多病历并发时，上一份病历刚完成会把 processed_rule_count 留在 76/76；
// 若仍有未完成病历，不能把它当成下一份的实时进度，否则会重复计入并提前显示 100%。
const isStaleCompletedRuleSnapshot = computed(
  () =>
    isActive.value &&
    hasUnfinishedMultiRecords.value &&
    (processedRecords.value ?? 0) > 0 &&
    processedRules.value !== null &&
    totalRules.value !== null &&
    totalRules.value > 0 &&
    processedRules.value >= totalRules.value,
)

const ruleProgressText = computed(() => {
  if (processedRules.value === null || totalRules.value === null) return ''
  if (isStaleCompletedRuleSnapshot.value) return ''
  const prefix = currentJob.value?.summary?.material_failure
    ? '已返回规则结果'
    : (totalRecords.value ?? 0) > 1 ? '当前单份规则进度' : '已执行'
  return `${prefix} ${Math.min(processedRules.value, totalRules.value)} / ${totalRules.value} 个质控点`
})

const progressPercent = computed(() => {
  if (currentJob.value?.status === 'completed') return 100
  const total = totalRecords.value
  const completed = Math.min(processedRecords.value ?? 0, total ?? 0)
  const reported = finiteCount(currentJob.value?.summary?.progress_percent)
  if (reported !== null && reported > 0) {
    if (hasUnfinishedMultiRecords.value && reported >= 100) {
      return Math.min(99, total ? Math.round((completed / total) * 100) : 99)
    }
    return Math.min(100, reported)
  }
  if (!total) return null
  const currentRuleFraction =
    !isStaleCompletedRuleSnapshot.value && processedRules.value !== null && totalRules.value
      ? Math.min(1, processedRules.value / totalRules.value)
      : 0
  const computedPercent = Math.round(((completed + currentRuleFraction) / total) * 100)
  if (hasUnfinishedMultiRecords.value) {
    return Math.min(99, computedPercent)
  }
  return Math.min(100, computedPercent)
})

const statusTitle = computed(() => {
  const status = currentJob.value?.status
  if (resultReadError.value) return '质控结果暂不可查看'
  if (automaticRetrying.value) return '正在自动补跑失败项'
  if (status === 'queued') return '质控任务已进入队列'
  if (status === 'running') return '正在执行质控'
  if (status === 'completed') return '质控任务已完成'
  if (status === 'failed') {
    return currentJob.value?.summary?.execution_status === 'partial_failed'
      ? '质控任务部分执行失败'
      : '质控任务执行失败'
  }
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
  if (status === 'failed') return getBatchJobRetryMessage(currentJob.value)
  if (status === 'queued') return '系统正在分配执行资源，开始后将自动更新病历和质控点进度。'
  if (status === 'completed') return '质控结果已生成，请前往运行病历质控或终末病历质控查看。'
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
  if (currentJob.value?.status === 'completed') {
    return `成功 ${successRecords.value} 份 · 失败 ${failedRecords.value} 份`
  }
  if (!isBatchJobFinished(currentJob.value)) return ''
  const summary = currentJob.value?.summary
  if (summary?.material_failure) {
    return `${summary.material_failed_record_count ?? 0} 份病历资料准备失败，已保存的结果保留`
  }
  const completed = finiteCount(summary?.completed_rule_count)
  const failed = finiteCount(summary?.failed_rule_count)
  if (completed === null || failed === null) return ''
  return completed > 0
    ? `已保留 ${completed} 项有效结果 · ${failed} 项未完成`
    : `尚无有效结果 · ${failed} 项未完成`
})

const tone = computed(() => {
  const status = currentJob.value?.status
  if (resultReadError.value) return 'danger'
  if (status === 'completed') return 'success'
  if (automaticRetrying.value) return 'active'
  if (status === 'canceled') return 'muted'
  if (status === 'failed') return 'danger'
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
    consecutiveReadFailures = 0
    pollError.value = false
    resultReadError.value = ''
    if (isBatchJobFinished(result.data)) emit('results-updated')
    if (result.data.status === 'completed') emit('completed')
  } else {
    consecutiveReadFailures += 1
    const decision = decidePollReadFailure(result.status, consecutiveReadFailures, result.jobStatus)
    // 结果交付不完整等确定性失败（文案或 409/404 状态码）停止轮询，避免无限重复请求
    if (result.message?.includes(DELIVERY_CONTRACT_ERROR) || decision !== 'retry') {
      pollError.value = false
      const errorMessage = result.message || '任务结果暂无法展示'
      resultReadError.value =
        decision === 'stop_exhausted'
          ? pollReadFailureMessage(decision, errorMessage)
          : errorMessage
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
    consecutiveReadFailures = 0
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
/* 单行紧凑质控状态条：不挤占病历表首屏高度，点击「详情」平滑展开 4 阶段步骤与并发信息 */
.record-pool-qc-status {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 14px;
  border: 1px solid rgba(226, 232, 240, 0.95);
  border-radius: 10px;
  background: #f8fafc;
  color: var(--mq-text-primary);
  font-family: 'Microsoft YaHei UI', 'PingFang SC', 'Segoe UI', sans-serif;
  transition:
    background-color 180ms ease,
    border-color 180ms ease;
}

.record-pool-qc-status--success,
.record-pool-qc-status--muted,
.record-pool-qc-status--danger {
  border-color: rgba(226, 232, 240, 0.95);
  background: #f8fafc;
}

.record-pool-qc-status__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px 14px;
  min-height: 30px;
  flex-wrap: wrap;
}

.record-pool-qc-status__main {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 12px;
  flex: 1 1 360px;
  min-width: 0;
}

.record-pool-qc-status__indicator {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  border-radius: 50%;
  color: var(--mq-brand-600);
}

.record-pool-qc-status--success .record-pool-qc-status__indicator {
  background: color-mix(in srgb, var(--mq-success-icon) 12%, transparent);
  color: var(--mq-success-text);
}

.record-pool-qc-status--muted .record-pool-qc-status__indicator {
  background: rgba(100, 116, 139, 0.12);
  color: var(--mq-text-secondary);
}

.record-pool-qc-status--danger .record-pool-qc-status__indicator {
  background: color-mix(in srgb, var(--mq-danger-icon) 12%, transparent);
  color: var(--mq-danger-text);
}

.record-pool-qc-status__heading {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  flex: 0 0 auto;
  white-space: nowrap;
}

.record-pool-qc-status__heading strong {
  font-size: 13px;
  line-height: 20px;
  font-weight: 600;
  color: var(--mq-text-primary);
}

.record-pool-qc-status__badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 7px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--mq-brand-600) 11%, var(--mq-bg-surface));
  color: var(--mq-brand-700);
  font-size: 11px;
  line-height: 18px;
  font-weight: 600;
}

.record-pool-qc-status__live-dot {
  width: 7px;
  height: 7px;
  flex: 0 0 7px;
  border-radius: 50%;
  background: var(--mq-brand-600);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--mq-brand-600) 18%, transparent);
  animation: record-pool-qc-pulse 1.8s ease-in-out infinite;
}

.record-pool-qc-status__phase {
  margin: 0;
  color: var(--mq-text-secondary);
  font-size: 12px;
  line-height: 18px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 240px;
}

.record-pool-qc-status__progress-group {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-width: 0;
}

.record-pool-qc-status__progress {
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
  height: 7px;
  border-radius: 999px;
  overflow: hidden;
  background: color-mix(in srgb, var(--mq-brand-600) 13%, var(--mq-bg-surface));
}

.record-pool-qc-status__progress > span {
  position: relative;
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--mq-brand-600);
  transition: width 240ms ease;
}

/* 0% 刚启动时用流动微光表达任务活跃执行中，避免灰条像卡死 */
.record-pool-qc-status__progress.is-indeterminate::after {
  content: '';
  position: absolute;
  inset: 0;
  width: 30%;
  border-radius: inherit;
  background: linear-gradient(
    90deg,
    transparent 0%,
    color-mix(in srgb, var(--mq-brand-600) 52%, transparent) 50%,
    transparent 100%
  );
  animation: record-pool-qc-shimmer 1.6s ease-in-out infinite;
}

.record-pool-qc-status__percent {
  flex: 0 0 auto;
  min-width: 36px;
  text-align: right;
  color: var(--mq-brand-700);
  font-size: 13px;
  line-height: 18px;
  font-style: normal;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.record-pool-qc-status__percent small {
  font-size: 11px;
  font-weight: 600;
  margin-left: 1px;
}

.record-pool-qc-status__metrics {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 12px;
  margin-left: auto;
  color: var(--mq-text-tertiary);
  font-size: 12px;
  line-height: 18px;
  font-variant-numeric: tabular-nums;
}

.record-pool-qc-status__record-count {
  color: var(--mq-text-secondary);
  font-weight: 500;
}

.record-pool-qc-status__actions {
  display: inline-flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 6px;
  margin-left: auto;
}

.record-pool-qc-status__cancel {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid color-mix(in srgb, var(--mq-danger-icon) 34%, var(--mq-bg-surface));
  border-radius: 7px;
  background: var(--mq-bg-surface);
  color: var(--mq-danger-text);
  font-size: 12px;
  line-height: 1;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition:
    border-color 140ms ease,
    color 140ms ease,
    background-color 140ms ease;
}

.record-pool-qc-status__cancel:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--mq-danger-icon) 58%, var(--mq-bg-surface));
  background: color-mix(in srgb, var(--mq-danger-icon) 7%, var(--mq-bg-surface));
  color: var(--mq-danger-text);
}

.record-pool-qc-status__cancel:disabled {
  cursor: wait;
  opacity: 0.6;
}

.record-pool-qc-status__details-toggle {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  height: 28px;
  padding: 0 9px;
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 14%, var(--mq-bg-surface));
  border-radius: 7px;
  background: var(--mq-bg-surface);
  color: var(--mq-text-secondary);
  font-size: 12px;
  line-height: 1;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition:
    border-color 140ms ease,
    color 140ms ease,
    background-color 140ms ease;
}

.record-pool-qc-status__details-toggle:hover {
  border-color: color-mix(in srgb, var(--mq-brand-600) 35%, var(--mq-bg-surface));
  color: var(--mq-brand-700);
  background: color-mix(in srgb, var(--mq-brand-600) 4%, var(--mq-bg-surface));
}

.record-pool-qc-status__cancel:focus-visible,
.record-pool-qc-status__details-toggle:focus-visible,
.record-pool-qc-status__detail-link:focus-visible,
.record-pool-qc-status__export:focus-visible,
.record-pool-qc-status__dismiss:focus-visible {
  outline: 2px solid var(--mq-brand-600);
  outline-offset: 2px;
}

.record-pool-qc-status__details-chevron {
  transition: transform 180ms ease;
}

.record-pool-qc-status__details-chevron.is-open {
  transform: rotate(180deg);
}

.record-pool-qc-status__detail-link,
.record-pool-qc-status__export {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 11px;
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 17%, var(--mq-bg-surface));
  border-radius: 7px;
  background: var(--mq-bg-surface);
  color: var(--mq-neutral-text);
  font-size: 12px;
  font-weight: 500;
  text-decoration: none;
  white-space: nowrap;
  cursor: pointer;
}

.record-pool-qc-status--success .record-pool-qc-status__detail-link {
  border-color: color-mix(in srgb, var(--mq-brand-600) 35%, var(--mq-bg-surface));
  background: var(--mq-brand-600);
  color: #ffffff;
}

.record-pool-qc-status--success .record-pool-qc-status__detail-link:hover {
  background: var(--mq-brand-700);
  border-color: var(--mq-brand-700);
  color: #ffffff;
}

.record-pool-qc-status__detail-link:hover,
.record-pool-qc-status__export:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--mq-brand-600) 30%, var(--mq-bg-surface));
  background: color-mix(in srgb, var(--mq-brand-600) 4%, var(--mq-bg-surface));
  color: var(--mq-brand-700);
}

.record-pool-qc-status__export:disabled {
  cursor: wait;
  opacity: 0.58;
}

.record-pool-qc-status__dismiss {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  padding: 0;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--mq-text-tertiary);
  cursor: pointer;
}

.record-pool-qc-status__dismiss:hover {
  background: rgba(0, 0, 0, 0.06);
  color: var(--mq-text-primary);
}

.record-pool-qc-status__settling,
.record-pool-qc-status__refresh-note {
  margin: 0;
  font-size: 12px;
  line-height: 18px;
  color: var(--mq-text-secondary);
}

.record-pool-qc-status__refresh-note {
  color: color-mix(in srgb, var(--mq-warning-text) 89%, var(--mq-text-primary));
}

.record-pool-qc-status__details-panel {
  padding-top: 8px;
  border-top: 1px solid color-mix(in srgb, var(--mq-neutral-text) 10%, var(--mq-bg-surface));
}

.record-pool-qc-status__concurrency {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.record-pool-qc-status__concurrency span {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.03);
  color: var(--mq-text-secondary);
  font-size: 12px;
  line-height: 18px;
}

.record-pool-qc-status__concurrency strong {
  color: var(--mq-text-primary);
  font-size: 12px;
  font-weight: 700;
}

.record-pool-qc-status__concurrency span.is-active {
  background: rgba(10, 108, 255, 0.08);
  color: var(--mq-brand-700);
}

.record-pool-qc-status__concurrency span.is-active strong {
  color: var(--mq-brand-700);
}

.record-pool-qc-status__concurrency span.is-complete {
  background: rgba(16, 185, 129, 0.08);
  color: var(--mq-success-text);
}

.record-pool-qc-status__concurrency span.is-complete strong {
  color: var(--mq-success-text);
}

.record-pool-qc-status__stages {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px 14px;
  width: 100%;
  margin: 0;
  padding: 2px 0;
  list-style: none;
}

.record-pool-qc-status__stages li {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
  min-height: 20px;
  color: var(--mq-text-tertiary);
}

.record-pool-qc-status__stage-marker {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  border: 2px solid color-mix(in srgb, var(--mq-neutral-text) 24%, transparent);
  border-radius: 999px;
  background: var(--mq-bg-surface);
}

.record-pool-qc-status__stage-copy {
  display: grid;
  min-width: 0;
}

.record-pool-qc-status__stage-copy strong {
  font-size: 12px;
  line-height: 18px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.record-pool-qc-status__stages li.is-complete {
  color: var(--mq-text-secondary);
}

.record-pool-qc-status__stages li.is-complete .record-pool-qc-status__stage-marker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  background: transparent;
  width: 13px;
  height: 16px;
  flex-basis: 13px;
  color: var(--mq-success-text);
  font-size: 12px;
  font-weight: 700;
}

.record-pool-qc-status__stages li.is-active {
  color: var(--mq-brand-700);
}

.record-pool-qc-status__stages li.is-active .record-pool-qc-status__stage-marker {
  border-color: var(--mq-brand-600);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--mq-brand-600) 14%, transparent);
}

.record-pool-qc-status__stages li.is-error {
  color: var(--mq-danger-text);
}

.record-pool-qc-status__stages li.is-error .record-pool-qc-status__stage-marker {
  border-color: var(--mq-danger-icon);
  background: var(--mq-danger-icon);
}

.record-pool-qc-status__stage {
  margin: 6px 0 0;
  color: var(--mq-text-secondary);
  font-size: 12px;
  line-height: 18px;
}

@keyframes record-pool-qc-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--mq-brand-600) 18%, transparent);
  }
  50% {
    box-shadow: 0 0 0 5px color-mix(in srgb, var(--mq-brand-600) 6%, transparent);
  }
}

@keyframes record-pool-qc-shimmer {
  0% {
    transform: translateX(-110%);
  }
  100% {
    transform: translateX(320%);
  }
}

@media (prefers-reduced-motion: reduce) {
  .record-pool-qc-status__progress > span,
  .record-pool-qc-status__details-chevron {
    transition: none;
  }
  .record-pool-qc-status__live-dot,
  .record-pool-qc-status__progress.is-indeterminate::after {
    animation: none;
  }
}

@media (max-width: 720px) {
  .record-pool-qc-status {
    padding: 10px 12px;
  }
  .record-pool-qc-status__stages {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
