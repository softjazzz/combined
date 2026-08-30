<template>
  <div class="qc-run-selected-control">
    <button
      class="qc-run-selected-control__trigger"
      type="button"
      data-testid="run-selected-qc-trigger"
      :disabled="isBusy || normalizedRecordRefs.length === 0"
      @click="openConfirmation"
    >
      <Play :size="15" aria-hidden="true" />
      质控所选
    </button>

    <Teleport to="body">
      <div v-if="confirmationOpen" class="qc-run-selected-control__backdrop">
        <section
          class="qc-run-selected-control__dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="run-selected-qc-confirm-title"
        >
          <header class="qc-run-selected-control__header">
            <div>
              <p>所选病历质控</p>
              <h2 id="run-selected-qc-confirm-title">确认执行质控</h2>
            </div>
            <button
              class="qc-run-selected-control__icon-button"
              type="button"
              aria-label="关闭质控确认"
              @click="confirmationOpen = false"
            >
              <X :size="18" aria-hidden="true" />
            </button>
          </header>

          <dl class="qc-run-selected-control__scope-list">
            <div>
              <dt>病历范围</dt>
              <dd>{{ sceneLabel }} · 已勾选 {{ frozenRecordRefs.length }} 份</dd>
            </div>
            <div>
              <dt>资料来源</dt>
              <dd>使用本地已同步资料</dd>
            </div>
          </dl>

          <p class="qc-run-selected-control__description">
            本次只对勾选病历执行质控，不重新查询源库，也不会扩大到当前筛选范围。
          </p>

          <footer class="qc-run-selected-control__actions">
            <button
              class="qc-run-selected-control__secondary-button"
              type="button"
              @click="confirmationOpen = false"
            >
              取消
            </button>
            <button
              class="qc-run-selected-control__primary-button"
              type="button"
              data-testid="run-selected-qc-confirm"
              @click="startSelectedQc"
            >
              开始质控
            </button>
          </footer>
        </section>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="progressOpen" class="qc-run-selected-control__backdrop">
        <section
          class="qc-run-selected-control__dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="run-selected-qc-progress-title"
        >
          <header class="qc-run-selected-control__header">
            <div>
              <p>所选病历质控</p>
              <h2 id="run-selected-qc-progress-title">
                {{ progressTitle }}
              </h2>
            </div>
            <button
              v-if="!isBusy"
              class="qc-run-selected-control__icon-button"
              type="button"
              aria-label="关闭质控进度"
              @click="progressOpen = false"
            >
              <X :size="18" aria-hidden="true" />
            </button>
          </header>

          <div class="qc-run-selected-control__status" :class="`is-${state}`">
            <LoaderCircle v-if="isBusy" :size="22" class="is-spinning" aria-hidden="true" />
            <CheckCircle2 v-else-if="state === 'completed'" :size="22" aria-hidden="true" />
            <TriangleAlert v-else :size="22" aria-hidden="true" />
            <p role="status">
              {{ progressMessage }}
            </p>
          </div>

          <footer v-if="!isBusy" class="qc-run-selected-control__actions">
            <button
              class="qc-run-selected-control__primary-button"
              type="button"
              @click="progressOpen = false"
            >
              完成
            </button>
          </footer>
        </section>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { CheckCircle2, LoaderCircle, Play, TriangleAlert, X } from 'lucide-vue-next'

import {
  createSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import { useAuthStore } from '@/stores/auth'

import type { QcRecordCarePhase } from './QcRecordResultTable.vue'

export interface SelectedQcRecordRef {
  institute_id: string
  patient_id: string
  visit_id: string
}

type RunState = 'idle' | 'creating' | 'running' | 'completed' | 'failed'

const props = defineProps<{
  carePhase: QcRecordCarePhase
  recordRefs: SelectedQcRecordRef[]
}>()

const emit = defineEmits<{
  completed: []
}>()

const authStore = useAuthStore()
const POLL_INTERVAL_MS = 3000
const MAX_POLL_FAILURES = 3
const confirmationOpen = ref(false)
const progressOpen = ref(false)
const state = ref<RunState>('idle')
const progressMessage = ref('')
const frozenRecordRefs = ref<SelectedQcRecordRef[]>([])
let pollTimer: number | null = null
let pollFailures = 0
let disposed = false

const scene = computed<'running' | 'final'>(() =>
  props.carePhase === 'inpatient' ? 'running' : 'final',
)
const sceneLabel = computed(() => (scene.value === 'running' ? '运行病历' : '终末病历'))
const isBusy = computed(() => state.value === 'creating' || state.value === 'running')
const progressTitle = computed(() => {
  if (state.value === 'completed') return '质控已完成'
  if (state.value === 'failed') return '质控未完成'
  return '正在执行质控'
})
const normalizedRecordRefs = computed(() => normalizeRecordRefs(props.recordRefs))

function normalizeRecordRefs(values: SelectedQcRecordRef[]): SelectedQcRecordRef[] {
  const unique = new Map<string, SelectedQcRecordRef>()
  for (const value of values || []) {
    const instituteId = String(value?.institute_id || '').trim()
    const patientId = String(value?.patient_id || '').trim()
    const visitId = String(value?.visit_id || '').trim()
    if (!instituteId || !patientId || !visitId) continue
    const key = JSON.stringify([instituteId, patientId, visitId])
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
  return `medqc:selected-qc:${scene.value}`
}

function persistJob(jobId: string) {
  const owner = workflowOwner()
  if (!owner) return
  try {
    window.sessionStorage.setItem(storageKey(), JSON.stringify({ jobId, owner }))
  } catch {
    // 浏览器禁用存储时仍可在当前页面继续轮询。
  }
}

function clearPersistedJob() {
  try {
    window.sessionStorage.removeItem(storageKey())
  } catch {
    // 浏览器禁用存储时无需处理。
  }
}

function clearPollTimer() {
  if (pollTimer === null) return
  window.clearTimeout(pollTimer)
  pollTimer = null
}

function schedulePoll(jobId: string) {
  clearPollTimer()
  pollTimer = window.setTimeout(() => void pollJob(jobId), POLL_INTERVAL_MS)
}

function fail(message: string) {
  clearPollTimer()
  clearPersistedJob()
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

async function pollJob(jobId: string) {
  try {
    const response = await getSichuanWorkspaceBatchJob(jobId)
    if (disposed) return
    if (!response.success || !response.data) {
      pollFailures += 1
      if (pollFailures >= MAX_POLL_FAILURES) {
        fail(response.message || '连续获取质控任务状态失败，请稍后刷新结果页查看。')
        return
      }
      schedulePoll(jobId)
      return
    }
    pollFailures = 0
    const status = String(response.data.status || '')
      .trim()
      .toLowerCase()
    if (status === 'completed') {
      clearPollTimer()
      clearPersistedJob()
      state.value = 'completed'
      progressMessage.value = '所选病历质控已完成，当前结果页已刷新。'
      emit('completed')
      return
    }
    if (['failed', 'canceled', 'cancelled'].includes(status)) {
      fail(
        localDataFailureMessage(
          response.data.error_message || '质控任务未完成，请核对任务详情后重试。',
        ),
      )
      return
    }
    state.value = 'running'
    progressMessage.value = '正在使用本地已同步资料执行质控，完成后会自动刷新结果页。'
    schedulePoll(jobId)
  } catch {
    if (disposed) return
    pollFailures += 1
    if (pollFailures >= MAX_POLL_FAILURES) {
      fail('连续获取质控任务状态失败，请稍后刷新结果页查看。')
      return
    }
    schedulePoll(jobId)
  }
}

function openConfirmation() {
  if (isBusy.value || normalizedRecordRefs.value.length === 0) return
  frozenRecordRefs.value = normalizedRecordRefs.value.map((item) => ({ ...item }))
  confirmationOpen.value = true
}

async function startSelectedQc() {
  if (isBusy.value || frozenRecordRefs.value.length === 0) return
  confirmationOpen.value = false
  progressOpen.value = true
  state.value = 'creating'
  progressMessage.value = `正在创建 ${frozenRecordRefs.value.length} 份病历的质控任务。`
  try {
    const response = await createSichuanWorkspaceBatchJob({
      rule_set_key: 'luxian_0609_qc_v1',
      scope: scene.value,
      date_field: scene.value === 'running' ? 'admission' : 'discharge',
      record_refs: frozenRecordRefs.value,
    })
    if (!response.success || !response.data?.id) {
      fail(localDataFailureMessage(response.message || '质控任务创建失败，请稍后重试。'))
      return
    }
    state.value = 'running'
    progressMessage.value = response.data.idempotency_reused
      ? '相同质控任务正在执行，已继续跟踪任务进度。'
      : '质控任务已创建，正在使用本地已同步资料执行质控。'
    persistJob(response.data.id)
    await pollJob(response.data.id)
  } catch {
    fail('质控任务创建失败，请稍后重试。')
  }
}

onMounted(() => {
  try {
    const raw = window.sessionStorage.getItem(storageKey())
    if (!raw) return
    const persisted = JSON.parse(raw) as { jobId?: unknown; owner?: unknown }
    const jobId = String(persisted.jobId || '').trim()
    if (!jobId || String(persisted.owner || '').trim() !== workflowOwner()) {
      clearPersistedJob()
      return
    }
    progressOpen.value = true
    state.value = 'running'
    progressMessage.value = '正在恢复此前的质控任务进度。'
    void pollJob(jobId)
  } catch {
    clearPersistedJob()
  }
})

onUnmounted(() => {
  disposed = true
  clearPollTimer()
})
</script>

<style scoped>
.qc-run-selected-control {
  display: inline-flex;
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
  background: #0066cc;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 3px 10px rgb(0 102 204 / 18%);
}

.qc-run-selected-control__trigger:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.qc-run-selected-control__backdrop {
  position: fixed;
  z-index: 1200;
  inset: 0;
  display: grid;
  place-items: start center;
  overflow-y: auto;
  padding: 20px;
  padding-top: clamp(72px, 12vh, 132px);
  padding-bottom: 32px;
  background: rgb(15 23 42 / 42%);
  backdrop-filter: blur(4px);
}

.qc-run-selected-control__dialog {
  width: min(520px, 100%);
  max-height: calc(100vh - 104px);
  overflow-y: auto;
  border: 1px solid rgb(255 255 255 / 72%);
  border-radius: 18px;
  background: #fff;
  box-shadow:
    0 24px 70px rgb(15 23 42 / 28%),
    0 4px 18px rgb(15 23 42 / 12%);
  animation: qc-run-selected-dialog-in 220ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.qc-run-selected-control__header,
.qc-run-selected-control__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
}

.qc-run-selected-control__header {
  border-bottom: 1px solid #edf2f7;
  background: linear-gradient(180deg, #fbfdff 0%, #fff 100%);
}

.qc-run-selected-control__header p,
.qc-run-selected-control__header h2,
.qc-run-selected-control__status p {
  margin: 0;
}

.qc-run-selected-control__header p {
  color: #6b7f95;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.qc-run-selected-control__header h2 {
  margin-top: 6px;
  color: #0f2740;
  font-size: 20px;
  font-weight: 650;
  letter-spacing: -0.01em;
}

.qc-run-selected-control__icon-button {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border: 1px solid #e3ebf3;
  border-radius: 10px;
  color: #58708a;
  background: #f7fafd;
  transition: 180ms ease;
}

.qc-run-selected-control__icon-button:hover {
  color: #0f5fae;
  border-color: #c9dff3;
  background: #edf6ff;
}

.qc-run-selected-control__scope-list {
  display: grid;
  gap: 0;
  margin: 18px 24px 14px;
  padding: 4px 16px;
  border: 1px solid #e7eef5;
  border-radius: 12px;
  background: #f8fafc;
}

.qc-run-selected-control__scope-list div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 18px;
  padding: 12px 0;
}

.qc-run-selected-control__scope-list div + div {
  border-top: 1px solid #e8eef4;
}

.qc-run-selected-control__scope-list dt {
  flex: 0 0 auto;
  color: #718399;
  font-size: 12px;
  font-weight: 600;
}

.qc-run-selected-control__scope-list dd {
  margin: 0;
  color: #173653;
  font-size: 14px;
  font-weight: 600;
  text-align: right;
}

.qc-run-selected-control__description {
  margin: 0 24px 4px;
  padding: 13px 16px;
  border: 1px solid #e3edf7;
  border-radius: 11px;
  color: #45627d;
  background: #f3f8fd;
  font-size: 13px;
  line-height: 1.65;
}

.qc-run-selected-control__actions {
  justify-content: flex-end;
  margin-top: 16px;
  border-top: 1px solid #edf2f7;
}

.qc-run-selected-control__secondary-button {
  min-height: 40px;
  padding: 0 18px;
  border: 1px solid #cfdeec;
  border-radius: 8px;
  color: #35536e;
  background: #fff;
  font-size: 13px;
  font-weight: 600;
}

.qc-run-selected-control__secondary-button:hover {
  border-color: #a9c9e5;
  background: #f6faff;
}

.qc-run-selected-control__primary-button {
  min-height: 40px;
  padding: 0 20px;
  border-radius: 9px;
  font-size: 13px;
  box-shadow: 0 5px 14px rgb(0 102 204 / 22%);
}

.qc-run-selected-control__status {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 24px;
  padding: 18px 16px;
  border: 1px solid #deebf7;
  border-radius: 12px;
  color: #28567d;
  background: #f1f7fc;
  font-size: 14px;
  line-height: 1.6;
}

.qc-run-selected-control__status.is-completed {
  color: #137a4a;
  background: #effaf5;
}

.qc-run-selected-control__status.is-failed {
  color: #b42318;
  background: #fff4f2;
}

.is-spinning {
  animation: qc-run-selected-spin 0.9s linear infinite;
}

@keyframes qc-run-selected-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes qc-run-selected-dialog-in {
  from {
    opacity: 0;
    transform: translateY(-8px) scale(0.985);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (max-width: 560px) {
  .qc-run-selected-control__backdrop {
    padding-right: 12px;
    padding-left: 12px;
  }

  .qc-run-selected-control__header,
  .qc-run-selected-control__actions {
    padding-right: 18px;
    padding-left: 18px;
  }

  .qc-run-selected-control__scope-list,
  .qc-run-selected-control__description,
  .qc-run-selected-control__status {
    margin-right: 18px;
    margin-left: 18px;
  }
}
</style>
