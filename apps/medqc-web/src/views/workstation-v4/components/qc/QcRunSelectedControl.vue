<template>
  <div class="qc-run-selected-control">
    <button
      class="qc-run-selected-control__trigger"
      type="button"
      data-testid="run-selected-qc-trigger"
      :disabled="
        !canRunSelectedQc || isBusy || effectiveSelectedCount === 0 || Boolean(selectionError)
      "
      @click="prepareSelectedQc"
    >
      <Play :size="15" aria-hidden="true" />
      {{ caseMode ? '重新质控' : '质控所选' }}
      <span v-if="!caseMode && effectiveSelectedCount > 0" class="qc-run-selected-control__count">
        {{ effectiveSelectedCount }}
      </span>
    </button>
    <span v-if="selectionError" class="qc-run-selected-control__scope-note is-error" role="alert">
      {{ selectionError }}
    </span>
    <span
      v-else-if="scene === 'final'"
      class="qc-run-selected-control__scope-note"
      data-testid="final-archive-note"
    >
      终末按已出院病历执行，归档状态未核验。
    </span>

    <a-modal
      :open="confirmOpen"
      :title="caseMode ? '确认重新质控当前病历' : '确认质控所选病历'"
      ok-text="确认并开始"
      cancel-text="取消"
      :confirm-loading="state === 'creating'"
      :closable="state !== 'creating'"
      :mask-closable="state !== 'creating'"
      @ok="confirmSelectedQc"
      @cancel="cancelConfirmation"
    >
      <div class="qc-run-selected-control__confirmation">
        <p>
          将对已冻结的 <strong>{{ frozenRecordRefs.length }}</strong> 份{{
            sceneRecordLabel
          }}执行质控。
        </p>
        <dl>
          <div>
            <dt>规则集</dt>
            <dd>LX0609 内涵质控（luxian_0609_qc_v1）</dd>
          </div>
          <div>
            <dt>执行范围</dt>
            <dd>{{ caseMode ? '仅当前病历的完整三坐标' : '仅本次勾选的完整病历三坐标' }}</dd>
          </div>
        </dl>
      </div>
    </a-modal>

    <Teleport v-if="statusTarget" :to="statusTarget" defer>
      <div class="qc-run-selected-control__task-status">
        <div
          v-if="state === 'creating' || state === 'failed' || state === 'unknown'"
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
          <TriangleAlert v-else :size="15" aria-hidden="true" />
          <span>{{ progressMessage }}</span>
        </div>
        <RecordPoolQcTaskStatusBar
          v-if="taskJob"
          :job="taskJob"
          :auto-poll="false"
          @dismiss="taskJob = null"
        />
      </div>
    </Teleport>
    <template v-else>
      <div
        v-if="state === 'creating' || state === 'failed' || state === 'unknown'"
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
        <TriangleAlert v-else :size="15" aria-hidden="true" />
        <span>{{ progressMessage }}</span>
      </div>
      <RecordPoolQcTaskStatusBar
        v-if="taskJob"
        :job="taskJob"
        :auto-poll="false"
        @dismiss="taskJob = null"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { LoaderCircle, Play, TriangleAlert } from 'lucide-vue-next'

import {
  createSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import { useAuthStore } from '@/stores/auth'
import RecordPoolQcTaskStatusBar from '../workbench/RecordPoolQcTaskStatusBar.vue'
import type { SichuanBatchJob } from '../../semantic-rules/types'

import type { QcRecordCarePhase } from './QcRecordResultTable.vue'

export interface SelectedQcRecordRef {
  institute_id: string
  patient_id: string
  visit_id: string
}

type RunState = 'idle' | 'creating' | 'running' | 'completed' | 'failed' | 'unknown'

const props = defineProps<{
  carePhase: QcRecordCarePhase
  recordRefs: SelectedQcRecordRef[]
  selectedCount?: number
  statusTarget?: string
  mode?: 'selected' | 'case'
}>()

const emit = defineEmits<{
  completed: []
}>()

const authStore = useAuthStore()
const caseMode = computed(() => props.mode === 'case')
const caseContextKey = computed(() => caseMode.value
  ? JSON.stringify(props.recordRefs.map((value) => [value.institute_id, value.patient_id, value.visit_id])) : '')
const POLL_INTERVAL_MS = 3000
const MAX_POLL_FAILURES = 3
const state = ref<RunState>('idle')
const progressMessage = ref('')
const frozenRecordRefs = ref<SelectedQcRecordRef[]>([])
const taskJob = ref<SichuanBatchJob | null>(null)
const confirmOpen = ref(false)
let pollTimer: number | null = null
let pollFailures = 0
let disposed = false
let mounted = false
let operationRevision = 0
let completedJobId = ''

const scene = computed<'running' | 'final'>(() =>
  props.carePhase === 'inpatient' ? 'running' : 'final',
)
const canAnalyze = computed(() => {
  const roles = Array.isArray(authStore.userRoles) ? authStore.userRoles : []
  return roles.some((role) => role === 'admin' || role === 'qc_manager')
})
// 终末口径 B：已出院列表按“已出院（未核验归档）”发起，与在院列表同一 LX0609 结果来源。
const canRunSelectedQc = computed(() => canAnalyze.value)
const sceneRecordLabel = computed(() =>
  scene.value === 'running' ? '在院病历' : '已出院病历（未核验归档）',
)
const isBusy = computed(
  () => state.value === 'creating' || state.value === 'running' || state.value === 'unknown',
)
const effectiveSelectedCount = computed(() => props.selectedCount ?? props.recordRefs.length)
const actorKey = computed(() => {
  const roles = Array.isArray(authStore.userRoles) ? [...authStore.userRoles].sort() : []
  return `${workflowOwner()}|${roles.join(',')}`
})
const selectionValidation = computed(() =>
  validateRecordRefs(props.recordRefs, effectiveSelectedCount.value),
)
const selectionError = computed(() => caseMode.value && props.recordRefs.length !== 1
  ? '当前病历身份不唯一，已停止重新质控' : selectionValidation.value.error)
const statusTarget = computed(() => String(props.statusTarget || '').trim())

function validateRecordRefs(
  values: SelectedQcRecordRef[],
  selectedCount: number,
): {
  refs: SelectedQcRecordRef[]
  error: string
} {
  const unique = new Map<string, SelectedQcRecordRef>()
  for (const value of values || []) {
    const instituteId = String(value?.institute_id || '').trim()
    const patientId = String(value?.patient_id || '').trim()
    const visitId = String(value?.visit_id || '').trim()
    if (!instituteId || !patientId || !visitId) {
      return { refs: [], error: '所选病历存在不完整身份，请刷新列表后重新勾选' }
    }
    const key = JSON.stringify([instituteId, patientId, visitId])
    if (unique.has(key)) return { refs: [], error: '所选病历存在重复身份，请重新勾选' }
    unique.set(key, {
      institute_id: instituteId,
      patient_id: patientId,
      visit_id: visitId,
    })
  }
  const refs = [...unique.values()]
  if (selectedCount !== refs.length) {
    return { refs: [], error: '所选病历数量与身份清单不一致，请刷新列表后重新勾选' }
  }
  return { refs, error: '' }
}

function workflowOwner(): string {
  return String(authStore.user?.id || authStore.user?.email || '').trim()
}

function storageKey(sceneValue: string, actor: string): string {
  return `medqc:selected-qc:${sceneValue}:${encodeURIComponent(actor)}${caseMode.value ? `:case:${encodeURIComponent(caseContextKey.value)}` : ''}`
}

function persistJob(jobId: string, sceneValue: string, actor: string) {
  if (!actor) return
  try {
    window.sessionStorage.setItem(storageKey(sceneValue, actor), JSON.stringify({ jobId, actor }))
  } catch {
    // 浏览器禁用存储时仍可在当前页面继续轮询。
  }
}

function clearPersistedJob(sceneValue: string, actor: string) {
  try {
    window.sessionStorage.removeItem(storageKey(sceneValue, actor))
  } catch {
    // 浏览器禁用存储时无需处理。
  }
}

function clearPollTimer() {
  if (pollTimer === null) return
  window.clearTimeout(pollTimer)
  pollTimer = null
}

function schedulePoll(jobId: string, revision: number, owner: string, sceneValue: string) {
  clearPollTimer()
  pollTimer = window.setTimeout(
    () => void pollJob(jobId, revision, owner, sceneValue),
    POLL_INTERVAL_MS,
  )
}

function contextIsCurrent(revision: number, owner: string, sceneValue: string) {
  return (
    !disposed &&
    revision === operationRevision &&
    owner === workflowOwner() &&
    sceneValue === scene.value
  )
}

function fail(message: string, sceneValue: string, owner: string) {
  clearPollTimer()
  clearPersistedJob(sceneValue, actorKey.value)
  state.value = 'failed'
  progressMessage.value = message
}

function markCreateResultUnknown(detail = '') {
  clearPollTimer()
  state.value = 'unknown'
  const prefix = String(detail || '').trim()
  progressMessage.value = `${prefix ? `${prefix}。` : ''}质控任务创建结果未确认，请先核对任务记录，勿直接重复提交。`
}

function localDataFailureMessage(message: string): string {
  const detail = message || '质控任务创建失败，请稍后重试。'
  if (!/没有可执行病历|匹配结果不一致|缺少完整三坐标|bundle|资料包|本地病历/i.test(detail)) {
    return detail
  }
  return `${detail}。请先到系统设置同步对应病历资料，再返回本页执行质控。`
}

async function pollJob(jobId: string, revision: number, owner: string, sceneValue: string) {
  if (!contextIsCurrent(revision, owner, sceneValue)) return
  try {
    const response = await getSichuanWorkspaceBatchJob(jobId)
    if (!contextIsCurrent(revision, owner, sceneValue)) return
    if (!response.success || !response.data) {
      pollFailures += 1
      if (pollFailures >= MAX_POLL_FAILURES) {
        fail(
          response.message || '连续获取质控任务状态失败，请稍后刷新结果页查看。',
          sceneValue,
          owner,
        )
        return
      }
      schedulePoll(jobId, revision, owner, sceneValue)
      return
    }
    if (String(response.data.id || '').trim() !== jobId) {
      fail('质控任务身份与请求不一致，已停止更新进度', sceneValue, owner)
      return
    }
    taskJob.value = response.data as SichuanBatchJob
    pollFailures = 0
    const status = String(response.data.status || '')
      .trim()
      .toLowerCase()
    if (status === 'completed') {
      if (caseMode.value) {
        const counts = [response.data.total_records, response.data.success_count, response.data.failed_count]
        if (!counts.every((count) => typeof count === 'number' && Number.isSafeInteger(count) && count >= 0)
          || response.data.total_records !== 1) {
          markCreateResultUnknown('当前病历完成计数不完整，结果待核实')
          return
        }
        if (response.data.failed_count !== 0) {
          fail(response.data.error_message || '当前病历质控失败，请核对任务详情后重试。', sceneValue, owner)
          return
        }
        if (!response.data.success_count) {
          markCreateResultUnknown('当前病历未确认成功交付，结果待核实')
          return
        }
      }
      clearPollTimer()
      clearPersistedJob(sceneValue, actorKey.value)
      state.value = 'completed'
      progressMessage.value = '所选病历质控已完成，当前结果页已刷新。'
      emitCompletedOnce(jobId)
      return
    }
    if (['failed', 'canceled', 'cancelled'].includes(status)) {
      fail(
        localDataFailureMessage(
          response.data.error_message || '质控任务未完成，请核对任务详情后重试。',
        ),
        sceneValue,
        owner,
      )
      return
    }
    state.value = 'running'
    progressMessage.value = '正在使用本地已同步资料执行质控，完成后会自动刷新结果页。'
    if (!['queued', 'running'].includes(status)) {
      fail('质控任务返回了未知状态，已停止更新进度', sceneValue, owner)
      return
    }
    schedulePoll(jobId, revision, owner, sceneValue)
  } catch {
    if (!contextIsCurrent(revision, owner, sceneValue)) return
    pollFailures += 1
    if (pollFailures >= MAX_POLL_FAILURES) {
      fail('连续获取质控任务状态失败，请稍后刷新结果页查看。', sceneValue, owner)
      return
    }
    schedulePoll(jobId, revision, owner, sceneValue)
  }
}

function prepareSelectedQc() {
  if (
    !canRunSelectedQc.value ||
    isBusy.value ||
    selectionError.value ||
    selectionValidation.value.refs.length === 0
  )
    return
  frozenRecordRefs.value = selectionValidation.value.refs.map((item) => ({ ...item }))
  confirmOpen.value = true
}

function cancelConfirmation() {
  if (state.value === 'creating') return
  confirmOpen.value = false
  frozenRecordRefs.value = []
}

async function confirmSelectedQc() {
  if (!confirmOpen.value || isBusy.value || frozenRecordRefs.value.length === 0) return
  confirmOpen.value = false
  const revision = ++operationRevision
  const owner = workflowOwner()
  const sceneValue = scene.value
  const recordRefs = frozenRecordRefs.value.map((item) => ({ ...item }))
  if (!owner) {
    state.value = 'failed'
    progressMessage.value = '当前账号不可用，请重新登录后重试。'
    return
  }
  taskJob.value = null
  completedJobId = ''
  pollFailures = 0
  state.value = 'creating'
  progressMessage.value = `正在创建 ${recordRefs.length} 份病历的质控任务。`
  try {
    const response = await createSichuanWorkspaceBatchJob({
      rule_set_key: 'luxian_0609_qc_v1',
      scope: sceneValue,
      date_field: sceneValue === 'running' ? 'admission' : 'discharge',
      record_refs: recordRefs,
    })
    if (!contextIsCurrent(revision, owner, sceneValue)) return
    if (!response.success) {
      if (caseMode.value && [401, 403, 404, 409, 413, 422].includes(response.status || 0)) {
        fail(localDataFailureMessage(response.message || '当前病历重新质控请求被拒绝'), sceneValue, owner)
        return
      }
      markCreateResultUnknown(response.message || '质控任务创建失败')
      return
    }
    const jobId = String(response.data?.id || '').trim()
    if (!jobId) {
      markCreateResultUnknown()
      return
    }
    taskJob.value = response.data as SichuanBatchJob
    state.value = 'running'
    progressMessage.value = response.data.idempotency_reused
      ? '相同质控任务正在执行，已继续跟踪任务进度。'
      : '质控任务已创建，正在使用本地已同步资料执行质控。'
    persistJob(jobId, sceneValue, actorKey.value)
    await pollJob(jobId, revision, owner, sceneValue)
  } catch {
    if (contextIsCurrent(revision, owner, sceneValue)) markCreateResultUnknown()
  }
}

function emitCompletedOnce(jobId: string) {
  if (!jobId || completedJobId === jobId) return
  completedJobId = jobId
  emit('completed')
}

async function recoverPersistedJob() {
  const owner = workflowOwner()
  const sceneValue = scene.value
  if (!owner || !canAnalyze.value) return
  const revision = operationRevision
  const actor = actorKey.value
  try {
    const raw = window.sessionStorage.getItem(storageKey(sceneValue, actor))
    if (!raw) return
    const persisted = JSON.parse(raw) as { jobId?: unknown; actor?: unknown }
    const jobId = String(persisted.jobId || '').trim()
    if (!jobId || String(persisted.actor || '') !== actor || actor !== actorKey.value) {
      clearPersistedJob(sceneValue, actor)
      return
    }
    state.value = 'running'
    progressMessage.value = '正在恢复此前的质控任务进度。'
    await pollJob(jobId, revision, owner, sceneValue)
  } catch {
    clearPersistedJob(sceneValue, actor)
  }
}

function resetForContext() {
  operationRevision += 1
  clearPollTimer()
  pollFailures = 0
  completedJobId = ''
  confirmOpen.value = false
  frozenRecordRefs.value = []
  taskJob.value = null
  state.value = 'idle'
  progressMessage.value = ''
  if (mounted) void recoverPersistedJob()
}

watch([actorKey, scene, caseContextKey, caseMode], resetForContext)

onMounted(() => {
  mounted = true
  void recoverPersistedJob()
})

onUnmounted(() => {
  mounted = false
  disposed = true
  operationRevision += 1
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
  border: 1px solid rgba(43, 108, 246, 0.14);
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
  background: #2b6cf6;
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

.qc-run-selected-control__scope-note {
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  line-height: 18px;
}
.qc-run-selected-control__scope-note.is-error {
  color: #b42318;
}
.qc-run-selected-control__confirmation p {
  margin: 0 0 14px;
}
.qc-run-selected-control__confirmation dl {
  display: grid;
  gap: 10px;
  margin: 0;
}
.qc-run-selected-control__confirmation dl div {
  display: grid;
  grid-template-columns: 76px 1fr;
  gap: 12px;
}
.qc-run-selected-control__confirmation dt {
  color: rgba(29, 29, 31, 0.58);
}
.qc-run-selected-control__confirmation dd {
  margin: 0;
  color: #1d1d1f;
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
