<template>
  <div class="qc-run-selected-control">
    <Popconfirm
      :open="confirmOpen"
      :title="confirmTitle"
      ok-text="开始质控"
      cancel-text="取消"
      placement="bottomRight"
      overlay-class-name="qc-run-selected-control__popconfirm"
      :disabled="isTriggerDisabled"
      @update:open="handleConfirmOpenChange"
      @confirm="confirmSelectedQc"
      @cancel="cancelSelectedQc"
    >
      <button
        class="qc-run-selected-control__trigger"
        type="button"
        data-testid="run-selected-qc-trigger"
        :disabled="isTriggerDisabled"
      >
        <Play
          :size="15"
          aria-hidden="true"
        />
        质控所选
        <span
          v-if="selectedCount > 0"
          class="qc-run-selected-control__count"
        >
          {{ selectedCount }}
        </span>
      </button>
    </Popconfirm>

    <Teleport
      v-if="statusTarget"
      :to="statusTarget"
      defer
    >
      <div class="qc-run-selected-control__task-status">
        <div
          v-if="state === 'creating' || state === 'failed'"
          class="qc-run-selected-control__inline-message"
          :class="`is-${state}`"
          role="status"
          aria-live="polite"
        >
          <LoaderCircle
            v-if="state === 'creating'"
            :size="15"
            class="is-spinning"
            aria-hidden="true"
          />
          <TriangleAlert
            v-else
            :size="15"
            aria-hidden="true"
          />
          <span>{{ progressMessage }}</span>
        </div>
        <RecordPoolQcTaskStatusBar
          v-if="taskJob"
          :job="taskJob"
          :auto-poll="false"
          :inline-result-viewer="inlineResultViewer"
          @dismiss="handleDismissTask"
          @view-results="handleViewTaskResults"
        />
      </div>
    </Teleport>
    <template v-else>
      <div
        v-if="state === 'creating' || state === 'failed'"
        class="qc-run-selected-control__inline-message"
        :class="`is-${state}`"
        role="status"
        aria-live="polite"
      >
        <LoaderCircle
          v-if="state === 'creating'"
          :size="15"
          class="is-spinning"
          aria-hidden="true"
        />
        <TriangleAlert
          v-else
          :size="15"
          aria-hidden="true"
        />
        <span>{{ progressMessage }}</span>
      </div>
      <RecordPoolQcTaskStatusBar
        v-if="taskJob"
        :job="taskJob"
        :auto-poll="false"
        :inline-result-viewer="inlineResultViewer"
        @dismiss="handleDismissTask"
        @view-results="handleViewTaskResults"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { Popconfirm } from 'ant-design-vue'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { LoaderCircle, Play, TriangleAlert } from 'lucide-vue-next'

import {
  createSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import { useAuthStore } from '@/stores/auth'
import { buildCaseRecordKey } from '../../utils/caseRecordKey'
import {
  getBatchJobRetryMessage,
  isBatchJobFinished,
  isBatchJobPollingActive,
} from '../../semantic-rules/utils/batchJobStatus'
import RecordPoolQcTaskStatusBar from '../workbench/RecordPoolQcTaskStatusBar.vue'
import type { SichuanBatchJob } from '../../semantic-rules/types'

import type { QcRecordCarePhase } from './QcRecordResultTable.vue'

export interface SelectedQcRecordRef {
  institute_id: string
  patient_id: string
  visit_id: string
}

type RunState = 'idle' | 'creating' | 'running' | 'completed' | 'failed'

const props = defineProps<{
  sourceId?: string
  carePhase: QcRecordCarePhase
  recordRefs: SelectedQcRecordRef[]
  selectedCount?: number
  statusTarget?: string
  inlineResultViewer?: boolean
}>()

const emit = defineEmits<{
  completed: []
  'results-updated': []
  'view-results': [payload: { job: SichuanBatchJob; recordRefs: SelectedQcRecordRef[] }]
  'dismiss-task': [jobId: string]
}>()

function handleDismissTask() {
  const dismissedJobId = String(taskJob.value?.id || '').trim()
  taskJob.value = null
  if (dismissedJobId) emit('dismiss-task', dismissedJobId)
}

function handleViewTaskResults(job: SichuanBatchJob) {
  emit('view-results', {
    job,
    recordRefs: frozenRecordRefs.value.map((item) => ({ ...item })),
  })
}

const authStore = useAuthStore()
const POLL_INTERVAL_MS = 3000
const MAX_POLL_FAILURES = 3
const state = ref<RunState>('idle')
const confirmOpen = ref(false)
const progressMessage = ref('')
const frozenRecordRefs = ref<SelectedQcRecordRef[]>([])
const taskJob = ref<SichuanBatchJob | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | null = null
let pollFailures = 0
let disposed = false
let sessionGeneration = 0

const scene = computed<'running' | 'final'>(() =>
  props.carePhase === 'inpatient' ? 'running' : 'final',
)
const isSourcePending = computed(() => props.sourceId === '')
const isBusy = computed(() => state.value === 'creating' || state.value === 'running')
const normalizedRecordRefs = computed(() => normalizeRecordRefs(props.recordRefs))
const confirmRecordCount = computed(() => normalizedRecordRefs.value.length)
const isTriggerDisabled = computed(
  () => isBusy.value || isSourcePending.value || normalizedRecordRefs.value.length === 0,
)
const confirmTitle = computed(
  () => `将对已勾选的 ${confirmRecordCount.value} 份病历执行质控，是否继续？`,
)
const statusTarget = computed(() => String(props.statusTarget || '').trim())

function handleConfirmOpenChange(nextOpen: boolean) {
  confirmOpen.value = nextOpen && !isTriggerDisabled.value
}

function cancelSelectedQc() {
  confirmOpen.value = false
}

function confirmSelectedQc() {
  confirmOpen.value = false
  void startSelectedQc()
}

function normalizeRecordRefs(values: SelectedQcRecordRef[]): SelectedQcRecordRef[] {
  const unique = new Map<string, SelectedQcRecordRef>()
  for (const value of values || []) {
    const instituteId = String(value?.institute_id || '').trim()
    const patientId = String(value?.patient_id || '').trim()
    const visitId = String(value?.visit_id || '').trim()
    const key = buildCaseRecordKey(instituteId, patientId, visitId)
    if (!key) continue
    unique.set(key, {
      institute_id: instituteId,
      patient_id: patientId,
      visit_id: visitId,
    })
  }
  return [...unique.values()]
}

function workflowOwner(): string {
  return String(authStore.user?.id || authStore.user?.email || '').trim()
}

function storageKey(): string {
  const suffix = props.sourceId === 'independent_cdm' ? ':independent_cdm' : ''
  return `medqc:selected-qc:${scene.value}${suffix}`
}

function persistJob(jobId: string, key = storageKey()) {
  const owner = workflowOwner()
  if (!owner) return
  try {
    window.sessionStorage.setItem(key, JSON.stringify({ jobId, owner }))
  } catch {
    // 浏览器禁用存储时仍可在当前页面继续轮询。
  }
}

function clearPersistedJob(key = storageKey()) {
  try {
    window.sessionStorage.removeItem(key)
  } catch {
    // 浏览器禁用存储时无需处理。
  }
}

function clearPollTimer() {
  if (pollTimer === null) return
  clearTimeout(pollTimer)
  pollTimer = null
}

function schedulePoll(jobId: string, generation: number, key: string) {
  clearPollTimer()
  pollTimer = setTimeout(() => void pollJob(jobId, generation, key), POLL_INTERVAL_MS)
}

function fail(message: string, key = storageKey()) {
  clearPollTimer()
  clearPersistedJob(key)
  state.value = 'failed'
  progressMessage.value = message
}

function localDataFailureMessage(message: string): string {
  const detail = message || '质控任务创建失败，请稍后重试。'
  if (!/没有可执行病历|匹配结果不一致|缺少完整三坐标|bundle|资料包|本地病历/i.test(detail)) {
    return detail
  }
  return `${detail}。请先到系统设置同步对应病历资料，再返回本页执行质控。`
}

async function pollJob(jobId: string, generation = sessionGeneration, key = storageKey()) {
  try {
    const response = await getSichuanWorkspaceBatchJob(jobId)
    if (disposed || generation !== sessionGeneration) return
    if (!response.success || !response.data) {
      pollFailures += 1
      if (pollFailures >= MAX_POLL_FAILURES) {
        fail(response.message || '连续获取质控任务状态失败，请稍后刷新结果页查看。', key)
        return
      }
      schedulePoll(jobId, generation, key)
      return
    }
    taskJob.value = response.data as SichuanBatchJob
    pollFailures = 0
    const status = String(response.data.status || '')
      .trim()
      .toLowerCase()
    // failed 可以是后台自动补跑的中间态，此时不能清除轮询或允许重复提交。
    if (isBatchJobPollingActive(response.data)) {
      state.value = 'running'
      progressMessage.value =
        getBatchJobRetryMessage(response.data) ||
        '正在使用本地已同步资料执行质控，完成后会自动刷新结果页。'
      schedulePoll(jobId, generation, key)
      return
    }
    if (isBatchJobFinished(response.data)) emit('results-updated')
    if (status === 'completed') {
      clearPollTimer()
      clearPersistedJob(key)
      state.value = 'completed'
      progressMessage.value = '所选病历质控已完成，当前结果页已刷新。'
      emit('completed')
      return
    }
    if (['failed', 'canceled', 'cancelled'].includes(status)) {
      fail(
        localDataFailureMessage(
          getBatchJobRetryMessage(response.data) ||
            response.data.error_message ||
            '质控任务已停止，已保存的结果仍可查看。',
        ),
        key,
      )
      return
    }
    state.value = 'running'
    progressMessage.value = '正在使用本地已同步资料执行质控，完成后会自动刷新结果页。'
    schedulePoll(jobId, generation, key)
  } catch {
    if (disposed || generation !== sessionGeneration) return
    pollFailures += 1
    if (pollFailures >= MAX_POLL_FAILURES) {
      fail('连续获取质控任务状态失败，请稍后刷新结果页查看。', key)
      return
    }
    schedulePoll(jobId, generation, key)
  }
}

async function startSelectedQc() {
  if (isBusy.value || isSourcePending.value || normalizedRecordRefs.value.length === 0) return
  const generation = sessionGeneration
  const key = storageKey()
  frozenRecordRefs.value = normalizedRecordRefs.value.map((item) => ({ ...item }))
  taskJob.value = null
  state.value = 'creating'
  progressMessage.value = `正在创建 ${frozenRecordRefs.value.length} 份病历的质控任务。`
  try {
    const response = await createSichuanWorkspaceBatchJob({
      rule_set_key: 'luxian_0609_qc_v1',
      scope: scene.value,
      date_field: scene.value === 'running' ? 'admission' : 'discharge',
      record_refs: frozenRecordRefs.value,
    })
    if (disposed || generation !== sessionGeneration) return
    if (!response.success || !response.data?.id) {
      fail(localDataFailureMessage(response.message || '质控任务创建失败，请稍后重试。'), key)
      return
    }
    taskJob.value = response.data as SichuanBatchJob
    state.value = 'running'
    progressMessage.value = response.data.idempotency_reused
      ? '相同质控任务正在执行，已继续跟踪任务进度。'
      : '质控任务已创建，正在使用本地已同步资料执行质控。'
    persistJob(response.data.id, key)
    await pollJob(response.data.id, generation, key)
  } catch {
    if (disposed || generation !== sessionGeneration) return
    fail('质控任务创建失败，请稍后重试。', key)
  }
}

function resetForScopeChange() {
  sessionGeneration += 1
  clearPollTimer()
  pollFailures = 0
  confirmOpen.value = false
  state.value = 'idle'
  progressMessage.value = ''
  frozenRecordRefs.value = []
  taskJob.value = null
}

function restorePersistedJob() {
  if (isSourcePending.value) return
  const generation = sessionGeneration
  const key = storageKey()
  try {
    const raw = window.sessionStorage.getItem(key)
    if (!raw) return
    const persisted = JSON.parse(raw) as { jobId?: unknown; owner?: unknown }
    const jobId = String(persisted.jobId || '').trim()
    if (!jobId || String(persisted.owner || '').trim() !== workflowOwner()) {
      clearPersistedJob(key)
      return
    }
    state.value = 'running'
    progressMessage.value = '正在恢复此前的质控任务进度。'
    void pollJob(jobId, generation, key)
  } catch {
    clearPersistedJob(key)
  }
}

watch(isTriggerDisabled, (disabled) => {
  if (disabled) confirmOpen.value = false
})

watch(
  () => [props.carePhase, props.sourceId] as const,
  () => {
    resetForScopeChange()
    restorePersistedJob()
  },
)

onMounted(() => {
  restorePersistedJob()
})

onUnmounted(() => {
  disposed = true
  sessionGeneration += 1
  clearPollTimer()
})
</script>

<style scoped>
.qc-run-selected-control {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.qc-run-selected-control__task-status {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.qc-run-selected-control__task-status :deep(.record-pool-qc-status) {
  width: 100%;
}

.qc-run-selected-control__inline-message {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  max-width: min(520px, 100%);
  padding: 8px 12px;
  border: 1px solid rgba(10, 108, 255, 0.14);
  border-radius: 9px;
  color: #28567d;
  background: #f1f7fc;
  font-size: 12px;
  line-height: 1.5;
}

.qc-run-selected-control__inline-message.is-failed {
  border-color: rgba(239, 68, 68, 0.18);
  color: #b42318;
  background: #fff4f2;
}

button {
  border: 0;
  font: inherit;
  cursor: pointer;
}

.qc-run-selected-control__trigger,
.qc-run-selected-control__primary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 14px;
  border-radius: 8px;
  color: #fff;
  background: #0a6cff;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 3px 10px rgb(0 102 204 / 18%);
}

.qc-run-selected-control__trigger:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.qc-run-selected-control__count {
  display: inline-grid;
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.18);
  color: #fff;
  font-size: 11px;
  line-height: 18px;
  font-weight: 750;
}

.is-spinning {
  animation: qc-run-selected-spin 0.9s linear infinite;
}

@keyframes qc-run-selected-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
