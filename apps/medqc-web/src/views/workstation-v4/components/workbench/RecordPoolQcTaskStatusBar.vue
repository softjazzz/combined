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
      <div
        class="record-pool-qc-status__indicator"
        aria-hidden="true"
      >
        <LoaderCircle
          v-if="isActive"
          :size="18"
          class="record-pool-qc-status__spinner"
        />
        <CircleCheckBig
          v-else-if="currentJob.status === 'completed'"
          :size="18"
        />
        <CircleAlert
          v-else
          :size="18"
        />
      </div>

      <div class="record-pool-qc-status__content">
        <div class="record-pool-qc-status__heading">
          <strong>{{ statusTitle }}</strong>
          <span>{{ statusBadge }}</span>
        </div>

        <div class="record-pool-qc-status__metrics">
          <span>{{ recordProgressText }}</span>
          <span v-if="ruleProgressText">{{ ruleProgressText }}</span>
          <span v-if="terminalSummary">{{ terminalSummary }}</span>
        </div>

        <div class="record-pool-qc-status__progress">
          <a-progress
            v-if="progressPercent !== null"
            :percent="progressPercent"
            :show-info="false"
            :status="progressStatus"
            size="small"
          />
          <div
            v-else
            class="record-pool-qc-status__indeterminate"
            aria-hidden="true"
          >
            <span />
          </div>
        </div>

        <p class="record-pool-qc-status__stage">
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

    <button
      v-if="!isActive"
      type="button"
      class="record-pool-qc-status__dismiss"
      aria-label="关闭质控任务状态"
      @click="emit('dismiss')"
    >
      <X :size="16" />
    </button>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { CircleAlert, CircleCheckBig, LoaderCircle, X } from 'lucide-vue-next'
import { getSichuanWorkspaceBatchJob } from '@/services/sichuan-rule-workspace-service'
import type { SichuanBatchJob } from '../../semantic-rules/types'

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
let pollTimer: ReturnType<typeof setTimeout> | null = null
let requestSequence = 0

const terminalStatuses = new Set(['completed', 'failed', 'canceled'])
const isActive = computed(() =>
  Boolean(currentJob.value && !terminalStatuses.has(currentJob.value.status)),
)

function finiteCount(value: unknown): number | null {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null
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
    currentJob.value?.summary?.stream_state?.processed_records,
    successRecords.value + failedRecords.value,
  ),
)

const recordProgressText = computed(() => {
  if (totalRecords.value === null) return '正在确认任务范围'
  if (currentJob.value?.status === 'queued') return `待处理 ${totalRecords.value} 份病历`
  return `已处理 ${Math.min(processedRecords.value ?? 0, totalRecords.value)} / ${totalRecords.value} 份病历`
})

const processedRules = computed(() => firstCount(currentJob.value?.summary?.processed_rule_count))
const totalRules = computed(() =>
  firstCount(
    currentJob.value?.summary?.customer_rule_count,
    currentJob.value?.customer_rule_count,
    currentJob.value?.summary?.rule_count,
    currentJob.value?.rule_count,
  ),
)

const ruleProgressText = computed(() => {
  if (processedRules.value === null || totalRules.value === null) return ''
  return `已执行 ${Math.min(processedRules.value, totalRules.value)} / ${totalRules.value} 个质控点`
})

const progressPercent = computed(() => {
  if (currentJob.value?.status === 'completed') return 100
  const reported = finiteCount(currentJob.value?.summary?.progress_percent)
  if (reported !== null && reported > 0) return Math.min(100, reported)
  if (!totalRecords.value) return null
  return Math.min(100, Math.round(((processedRecords.value ?? 0) / totalRecords.value) * 100))
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
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 16px;
  border: 1px solid rgba(0, 102, 204, 0.2);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 4px 16px rgba(0, 70, 140, 0.06);
  color: #1d1d1f;
}

.record-pool-qc-status--success {
  border-color: rgba(16, 185, 129, 0.24);
}

.record-pool-qc-status--danger {
  border-color: rgba(239, 68, 68, 0.22);
}

.record-pool-qc-status__main {
  display: flex;
  min-width: 0;
  flex: 1;
  gap: 12px;
}

.record-pool-qc-status__indicator {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  place-items: center;
  border-radius: 10px;
  background: rgba(0, 102, 204, 0.09);
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

.record-pool-qc-status__metrics {
  margin-top: 4px;
  color: rgba(29, 29, 31, 0.72);
  font-size: 13px;
  line-height: 20px;
  font-weight: 550;
}

.record-pool-qc-status__progress {
  max-width: 560px;
  margin-top: 7px;
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
}
</style>
