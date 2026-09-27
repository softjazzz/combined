<template>
  <div class="qc-sync-and-run-control">
    <button
      class="qc-sync-and-run-control__trigger"
      type="button"
      data-testid="sync-and-qc-trigger"
      :disabled="isBusy"
      @click="handleTriggerClick"
    >
      <RefreshCw
        :size="15"
        aria-hidden="true"
      />
      {{ retryableQcPayload ? '重试创建质控' : '同步并质控' }}
    </button>

    <div
      v-if="confirmationOpen"
      class="qc-sync-and-run-control__backdrop"
    >
      <section
        class="qc-sync-and-run-control__dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="sync-and-qc-confirm-title"
      >
        <header class="qc-sync-and-run-control__dialog-header">
          <div>
            <p>病历同步</p>
            <h2 id="sync-and-qc-confirm-title">
              同步并质控
            </h2>
          </div>
          <button
            type="button"
            class="qc-sync-and-run-control__icon-button"
            aria-label="关闭同步并质控确认"
            @click="closeConfirmation"
          >
            <X
              :size="18"
              aria-hidden="true"
            />
          </button>
        </header>

        <dl class="qc-sync-and-run-control__scope-list">
          <div>
            <dt>病历范围</dt>
            <dd>{{ sceneLabel }} · {{ sceneDescription }}</dd>
          </div>
          <div>
            <dt>科室</dt>
            <dd>{{ departmentSelectionLabel }}</dd>
          </div>
          <div v-if="scene === 'final'">
            <dt>同步日期</dt>
            <dd>{{ selectedStartDate }} 至 {{ selectedEndDate }}</dd>
          </div>
        </dl>

        <fieldset class="qc-sync-and-run-control__department-selector">
          <legend>选择科室</legend>
          <p
            v-if="departmentLoading"
            class="qc-sync-and-run-control__department-hint"
          >
            正在读取可选科室…
          </p>
          <p
            v-else-if="departmentLoadError"
            class="qc-sync-and-run-control__department-hint is-error"
          >
            {{ departmentLoadError }}
          </p>
          <div class="qc-sync-and-run-control__department-options">
            <label class="qc-sync-and-run-control__department-option">
              <input
                type="checkbox"
                aria-label="全部科室"
                :checked="isAllDepartments"
                @change="selectAllDepartments"
              >
              <span>全部科室</span>
            </label>
            <label
              v-for="departmentOption in departmentOptions"
              :key="departmentOption"
              class="qc-sync-and-run-control__department-option"
            >
              <input
                type="checkbox"
                :aria-label="departmentOption"
                :checked="isDepartmentSelected(departmentOption)"
                @change="toggleDepartment(departmentOption, $event)"
              >
              <span>{{ departmentOption }}</span>
            </label>
          </div>
        </fieldset>

        <fieldset
          v-if="scene === 'final'"
          class="qc-sync-and-run-control__date-selector"
        >
          <legend>同步日期范围</legend>
          <p class="qc-sync-and-run-control__date-hint">
            {{ finalDateRangeHint }}
          </p>
          <div class="qc-sync-and-run-control__date-inputs">
            <label>
              <span>开始日期</span>
              <input
                v-model="selectedStartDate"
                type="date"
                data-testid="sync-and-qc-start-date"
                @change="onFinalDateRangeChange"
              >
            </label>
            <span
              class="qc-sync-and-run-control__date-separator"
              aria-hidden="true"
            > 至 </span>
            <label>
              <span>结束日期</span>
              <input
                v-model="selectedEndDate"
                type="date"
                data-testid="sync-and-qc-end-date"
                @change="onFinalDateRangeChange"
              >
            </label>
          </div>
          <p
            v-if="dateRangeError"
            class="qc-sync-and-run-control__date-hint is-error"
            role="alert"
          >
            {{ dateRangeError }}
          </p>
        </fieldset>

        <p class="qc-sync-and-run-control__description">
          系统将自动同步新病历并刷新已有病历资料，随后对所选范围内本地可见的病历执行质控。
        </p>

        <footer class="qc-sync-and-run-control__dialog-actions">
          <button
            type="button"
            class="qc-sync-and-run-control__secondary-button"
            @click="closeConfirmation"
          >
            取消
          </button>
          <button
            type="button"
            class="qc-sync-and-run-control__primary-button"
            data-testid="sync-and-qc-confirm"
            @click="startSyncAndQc"
          >
            开始同步并质控
          </button>
        </footer>
      </section>
    </div>

    <div
      v-if="progressVisible"
      class="qc-sync-and-run-control__backdrop"
    >
      <section
        class="qc-sync-and-run-control__dialog qc-sync-and-run-control__dialog--progress"
        role="dialog"
        aria-modal="true"
        aria-labelledby="sync-and-qc-progress-title"
      >
        <header class="qc-sync-and-run-control__dialog-header">
          <div>
            <p>病历同步与质控</p>
            <h2 id="sync-and-qc-progress-title">
              {{ progressTitle }}
            </h2>
          </div>
          <button
            v-if="!isBusy"
            type="button"
            class="qc-sync-and-run-control__icon-button"
            aria-label="关闭同步并质控进度"
            @click="closeProgress"
          >
            <X
              :size="18"
              aria-hidden="true"
            />
          </button>
        </header>

        <ol
          class="qc-sync-and-run-control__steps"
          aria-label="同步并质控进度"
        >
          <li
            v-for="step in progressSteps"
            :key="step.key"
            :class="`is-${step.status}`"
          >
            <span
              class="qc-sync-and-run-control__step-mark"
              aria-hidden="true"
            >
              <CheckCircle2
                v-if="step.status === 'completed'"
                :size="15"
              />
              <span v-else>{{ step.order }}</span>
            </span>
            <span>{{ step.label }}</span>
            <small>{{ stepStatusLabel(step.status) }}</small>
          </li>
        </ol>

        <p
          class="qc-sync-and-run-control__progress-summary"
          :class="{ 'is-error': progressState === 'failed', 'is-empty': progressState === 'empty' }"
          role="status"
        >
          {{ progressSummary }}
        </p>

        <footer
          v-if="!isBusy"
          class="qc-sync-and-run-control__dialog-actions"
        >
          <button
            v-if="retryableQcPayload"
            type="button"
            class="qc-sync-and-run-control__primary-button"
            data-testid="retry-qc-creation"
            @click="retryQcCreation"
          >
            重试创建质控
          </button>
          <button
            v-if="retryableQcPayload"
            type="button"
            class="qc-sync-and-run-control__secondary-button"
            @click="closeProgress"
          >
            稍后处理
          </button>
          <button
            v-else
            type="button"
            class="qc-sync-and-run-control__primary-button"
            @click="closeProgress"
          >
            完成
          </button>
        </footer>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { CheckCircle2, RefreshCw, X } from 'lucide-vue-next'

import {
  syncApi,
  type SyncAutoQcSummary,
  type SyncTriggerPayload,
  type SyncTriggerResponse,
} from '@/api/sync'
import { getSichuanWorkspaceBatchJob } from '@/services/sichuan-rule-workspace-service'
import { useAuthStore } from '@/stores/auth'

import type { QcRecordCarePhase } from './QcRecordResultTable.vue'

type ProgressState = 'idle' | 'syncing' | 'qc' | 'completed' | 'empty' | 'failed'
type ProgressStepStatus = 'pending' | 'active' | 'completed' | 'failed' | 'skipped'

interface ProgressStep {
  key: 'preflight' | 'sync' | 'confirm' | 'qc' | 'save'
  order: number
  label: string
  status: ProgressStepStatus
}

interface PersistedQcWorkflow {
  stage: 'qc'
  jobId: string
  owner: string
}

type AutoQcSyncTriggerPayload = SyncTriggerPayload & {
  scene: 'running' | 'final'
  target_departments: string[]
  auto_qc_after_sync: true
  auto_qc_workflow_token: string
}

interface PersistedSyncWorkflow {
  stage: 'syncing'
  payload: AutoQcSyncTriggerPayload
  owner: string
}

type PersistedWorkflow = PersistedQcWorkflow | PersistedSyncWorkflow

interface FinalDateWindow {
  startDate: string
  endDate: string
  usesDefault: boolean
}

const props = defineProps<{
  carePhase: QcRecordCarePhase
  department?: string
  startDate?: string
  endDate?: string
}>()

const emit = defineEmits<{
  completed: []
}>()

const authStore = useAuthStore()
const JOB_POLL_INTERVAL_MS = 3000
const MAX_CONSECUTIVE_JOB_POLL_FAILURES = 3
const MAX_ENQUEUEING_CONFIRMATIONS = 50
// 起止日期差最多30天，含开始、结束日期共31个自然日。
const MAX_FINAL_DATE_RANGE_DAYS = 30
const HOSPITAL_TIME_ZONE = 'Asia/Shanghai'
const confirmationOpen = ref(false)
const progressVisible = ref(false)
const progressState = ref<ProgressState>('idle')
const progressSummary = ref('')
const progressSteps = ref<ProgressStep[]>(createProgressSteps())
const polling = ref(false)
const syncStatusPolling = ref(false)
const departmentLoading = ref(false)
const departmentLoadError = ref('')
const availableDepartments = ref<string[]>([])
const selectedDepartments = ref<string[]>(defaultTargetDepartments())
const selectedStartDate = ref('')
const selectedEndDate = ref('')
const finalDateWindowUsesDefault = ref(false)
const dateRangeError = ref('')
const retryableQcPayload = ref<AutoQcSyncTriggerPayload | null>(null)
let pollTimer: number | null = null
let syncStatusPollTimer: number | null = null
let jobPollFailureCount = 0
let enqueueingConfirmationCount = 0
let disposed = false

const scene = computed<'running' | 'final'>(() =>
  props.carePhase === 'inpatient' ? 'running' : 'final',
)
const sceneLabel = computed(() => (scene.value === 'running' ? '运行病历' : '终末病历'))
const sceneDescription = computed(() => (scene.value === 'running' ? '当前在院' : '已出院'))
const departmentLabel = computed(() => normalizedDepartment(props.department))
const isAllDepartments = computed(() => selectedDepartments.value.includes('*'))
const departmentOptions = computed(() =>
  uniqueDepartments([
    ...availableDepartments.value,
    ...selectedDepartments.value.filter((department) => department !== '*'),
    ...(departmentLabel.value === '全部科室' ? [] : [departmentLabel.value]),
  ]),
)
const departmentSelectionLabel = computed(() => {
  if (isAllDepartments.value) return '全部科室'
  if (selectedDepartments.value.length === 1)
    return selectedDepartments.value[0] || departmentLabel.value
  return `已选择 ${selectedDepartments.value.length} 个科室`
})
const targetDepartments = computed(() =>
  isAllDepartments.value
    ? ['*']
    : selectedDepartments.value.length > 0
      ? [...selectedDepartments.value]
      : defaultTargetDepartments(),
)
const isBusy = computed(() => progressState.value === 'syncing' || progressState.value === 'qc')
const finalDateRangeHint = computed(() =>
  finalDateWindowUsesDefault.value
    ? '未提供完整结果筛选日期，已默认最近7天（含今日），可按需调整。'
    : '已沿用当前结果筛选日期，可按需调整。',
)
const progressTitle = computed(() => {
  if (progressState.value === 'completed') return '质控已完成'
  if (progressState.value === 'empty') return '同步已完成'
  if (progressState.value === 'failed') return '未能完成'
  return '正在同步并质控'
})

function createProgressSteps(): ProgressStep[] {
  return [
    { key: 'preflight', order: 1, label: '检查同步条件', status: 'pending' },
    { key: 'sync', order: 2, label: '同步病历', status: 'pending' },
    { key: 'confirm', order: 3, label: '确认可质控病历', status: 'pending' },
    { key: 'qc', order: 4, label: '执行质控', status: 'pending' },
    { key: 'save', order: 5, label: '汇总并保存结果', status: 'pending' },
  ]
}

function normalizedDepartment(value?: string): string {
  const department = String(value || '').trim()
  return department && department !== '*' ? department : '全部科室'
}

function defaultTargetDepartments(): string[] {
  const department = normalizedDepartment(props.department)
  return department === '全部科室' ? ['*'] : [department]
}

function isValidIsoDate(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return false
  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const date = new Date(Date.UTC(year, month - 1, day))
  return (
    date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
  )
}

function normalizedIsoDate(value: unknown): string {
  const date = String(value || '').trim()
  return isValidIsoDate(date) ? date : ''
}

function dateParts(value: string): [number, number, number] {
  const [year, month, day] = value.split('-').map(Number)
  return [year || 0, month || 0, day || 0]
}

function addDaysToIsoDate(value: string, days: number): string {
  const [year, month, day] = dateParts(value)
  const date = new Date(Date.UTC(year, month - 1, day))
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

function daysBetweenIsoDates(startDate: string, endDate: string): number {
  const [startYear, startMonth, startDay] = dateParts(startDate)
  const [endYear, endMonth, endDay] = dateParts(endDate)
  return Math.round(
    (Date.UTC(endYear, endMonth - 1, endDay) - Date.UTC(startYear, startMonth - 1, startDay)) /
      86_400_000,
  )
}

function currentHospitalDate(): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: HOSPITAL_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const year = parts.find((part) => part.type === 'year')?.value
  const month = parts.find((part) => part.type === 'month')?.value
  const day = parts.find((part) => part.type === 'day')?.value
  if (year && month && day) return `${year}-${month}-${day}`
  return new Date().toISOString().slice(0, 10)
}

function defaultFinalDateWindow(): FinalDateWindow {
  const endDate = currentHospitalDate()
  return {
    startDate: addDaysToIsoDate(endDate, -6),
    endDate,
    usesDefault: true,
  }
}

function resolveFinalDateWindow(startValue: unknown, endValue: unknown): FinalDateWindow {
  const startDate = normalizedIsoDate(startValue)
  const endDate = normalizedIsoDate(endValue)
  if (startDate && endDate) {
    return { startDate, endDate, usesDefault: false }
  }
  return defaultFinalDateWindow()
}

function resetFinalDateWindowSelection() {
  if (scene.value !== 'final') {
    selectedStartDate.value = ''
    selectedEndDate.value = ''
    finalDateWindowUsesDefault.value = false
    dateRangeError.value = ''
    return
  }
  const dateWindow = resolveFinalDateWindow(props.startDate, props.endDate)
  selectedStartDate.value = dateWindow.startDate
  selectedEndDate.value = dateWindow.endDate
  finalDateWindowUsesDefault.value = dateWindow.usesDefault
  dateRangeError.value = ''
}

function onFinalDateRangeChange() {
  finalDateWindowUsesDefault.value = false
  dateRangeError.value = ''
}

function validateFinalDateWindow(): boolean {
  if (scene.value !== 'final') return true
  const startDate = normalizedIsoDate(selectedStartDate.value)
  const endDate = normalizedIsoDate(selectedEndDate.value)
  if (!startDate || !endDate) {
    dateRangeError.value = '请选择有效的开始日期和结束日期。'
    return false
  }
  if (startDate > endDate) {
    dateRangeError.value = '开始日期不能晚于结束日期。'
    return false
  }
  if (daysBetweenIsoDates(startDate, endDate) > MAX_FINAL_DATE_RANGE_DAYS) {
    dateRangeError.value = '终末病历同步日期范围最多31天。'
    return false
  }
  selectedStartDate.value = startDate
  selectedEndDate.value = endDate
  dateRangeError.value = ''
  return true
}

function uniqueDepartments(values: string[]): string[] {
  return [
    ...new Set(
      values
        .map((value) => String(value || '').trim())
        .filter((value) => value && value !== '*' && value !== '全部科室'),
    ),
  ]
}

function resetDepartmentSelection() {
  selectedDepartments.value = defaultTargetDepartments()
  departmentLoadError.value = ''
}

function isDepartmentSelected(department: string): boolean {
  return !isAllDepartments.value && selectedDepartments.value.includes(department)
}

function selectAllDepartments() {
  selectedDepartments.value = ['*']
}

function toggleDepartment(department: string, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  const current = selectedDepartments.value.filter((item) => item !== '*')
  const next = checked ? [...current, department] : current.filter((item) => item !== department)
  selectedDepartments.value = uniqueDepartments(next)
  if (selectedDepartments.value.length === 0) {
    selectedDepartments.value = defaultTargetDepartments()
  }
}

async function loadDepartments() {
  departmentLoading.value = true
  departmentLoadError.value = ''
  try {
    const departments = await syncApi.getDepartments()
    if (disposed) return
    availableDepartments.value = uniqueDepartments(Array.isArray(departments) ? departments : [])
  } catch {
    if (!disposed) {
      availableDepartments.value = []
      departmentLoadError.value = '科室列表加载失败，已保留当前筛选范围。'
    }
  } finally {
    if (!disposed) departmentLoading.value = false
  }
}

function stepStatusLabel(status: ProgressStepStatus): string {
  if (status === 'active') return '进行中'
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '未完成'
  if (status === 'skipped') return '未执行'
  return '等待中'
}

function storageKey(): string {
  return `medqc:sync-and-qc:${scene.value}`
}

function handleTriggerClick() {
  if (isBusy.value) {
    progressVisible.value = true
    return
  }
  if (retryableQcPayload.value) {
    progressVisible.value = true
    void retryQcCreation()
    return
  }
  openConfirmation()
}

function openConfirmation() {
  if (isBusy.value) {
    progressVisible.value = true
    return
  }
  resetDepartmentSelection()
  resetFinalDateWindowSelection()
  confirmationOpen.value = true
  void loadDepartments()
}

function closeConfirmation() {
  confirmationOpen.value = false
}

function closeProgress() {
  if (isBusy.value) return
  progressVisible.value = false
}

function resetProgress() {
  progressSteps.value = createProgressSteps()
  progressSummary.value = ''
  enqueueingConfirmationCount = 0
}

function setStepStatus(index: number, status: ProgressStepStatus) {
  const current = progressSteps.value[index]
  if (!current) return
  progressSteps.value[index] = { ...current, status }
}

function completeStepsThrough(index: number) {
  for (let stepIndex = 0; stepIndex <= index; stepIndex += 1) {
    setStepStatus(stepIndex, 'completed')
  }
}

function markPendingStepsAsSkipped(fromIndex: number) {
  for (let stepIndex = fromIndex; stepIndex < progressSteps.value.length; stepIndex += 1) {
    setStepStatus(stepIndex, 'skipped')
  }
}

function clearPollTimer() {
  if (pollTimer !== null) {
    window.clearTimeout(pollTimer)
    pollTimer = null
  }
}

function clearSyncStatusPollTimer() {
  if (syncStatusPollTimer !== null) {
    window.clearTimeout(syncStatusPollTimer)
    syncStatusPollTimer = null
  }
}

function clearPollingTimers() {
  clearPollTimer()
  clearSyncStatusPollTimer()
}

function persistJob(jobId: string) {
  const owner = workflowOwner()
  if (!owner) return
  try {
    window.sessionStorage.setItem(
      storageKey(),
      JSON.stringify({ stage: 'qc', jobId, owner } satisfies PersistedQcWorkflow),
    )
  } catch {
    // 浏览器禁止存储时仍可在当前页面完成轮询。
  }
}

function persistSyncPayload(payload: AutoQcSyncTriggerPayload) {
  const safePayload = normalizePersistedSyncPayload(payload)
  const owner = workflowOwner()
  if (!safePayload || !owner) return
  try {
    window.sessionStorage.setItem(
      storageKey(),
      JSON.stringify({
        stage: 'syncing',
        payload: safePayload,
        owner,
      } satisfies PersistedSyncWorkflow),
    )
  } catch {
    // 浏览器禁止存储时仍可在当前页面完成轮询。
  }
}

function clearPersistedJob() {
  try {
    window.sessionStorage.removeItem(storageKey())
  } catch {
    // 浏览器禁止存储时无需额外处理。
  }
}

function readPersistedWorkflow(): PersistedWorkflow | null {
  try {
    const raw = window.sessionStorage.getItem(storageKey())
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!isRecord(parsed)) {
      clearPersistedJob()
      return null
    }
    const owner = textValue(parsed.owner)
    if (!owner || owner !== workflowOwner()) {
      clearPersistedJob()
      return null
    }
    const stage = textValue(parsed.stage)
    if (stage === 'qc') {
      const jobId = textValue(parsed.jobId)
      if (!jobId) {
        clearPersistedJob()
        return null
      }
      return { stage: 'qc', jobId, owner }
    }
    if (stage === 'syncing') {
      const payload = normalizePersistedSyncPayload(parsed.payload)
      if (!payload) {
        clearPersistedJob()
        return null
      }
      return { stage: 'syncing', payload, owner }
    }
    clearPersistedJob()
    return null
  } catch {
    clearPersistedJob()
    return null
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function textValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function workflowOwner(): string {
  const user = authStore.user
  return textValue(user?.id) || textValue(user?.email)
}

function isWorkflowToken(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
}

function createWorkflowToken(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (placeholder) => {
    const random = Math.floor(Math.random() * 16)
    const nibble = placeholder === 'x' ? random : (random & 0x3) | 0x8
    return nibble.toString(16)
  })
}

function normalizePersistedSyncPayload(value: unknown): AutoQcSyncTriggerPayload | null {
  if (!isRecord(value)) return null
  const source = textValue(value.source)
  const persistedScene = textValue(value.scene)
  if (source !== 'pg' || (persistedScene !== 'running' && persistedScene !== 'final')) return null

  const workflowToken = textValue(value.auto_qc_workflow_token)
  if (!isWorkflowToken(workflowToken)) return null

  const rawDepartments = Array.isArray(value.target_departments) ? value.target_departments : []
  const targetDepartments = rawDepartments
    .map((department) => textValue(department))
    .filter(Boolean)
  const normalizedTargets = targetDepartments.includes('*')
    ? ['*']
    : uniqueDepartments(targetDepartments)
  if (normalizedTargets.length === 0) return null

  const payload: AutoQcSyncTriggerPayload = {
    source: 'pg',
    scene: persistedScene,
    target_departments: normalizedTargets,
    auto_qc_after_sync: true,
    auto_qc_workflow_token: workflowToken,
  }
  const dateWindow = isRecord(value.date_window) ? value.date_window : null
  const startDate = normalizedIsoDate(dateWindow?.start_date)
  const endDate = normalizedIsoDate(dateWindow?.end_date)
  if (persistedScene === 'final') {
    if (
      !startDate ||
      !endDate ||
      startDate > endDate ||
      daysBetweenIsoDates(startDate, endDate) > MAX_FINAL_DATE_RANGE_DAYS
    ) {
      return null
    }
    payload.date_window = {
      start_date: startDate,
      end_date: endDate,
    }
  }
  return payload
}

function getResponseError(response: SyncTriggerResponse, fallback: string): string {
  return textValue(response.error) || textValue(response.message) || fallback
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) return error.message
  if (isRecord(error)) return textValue(error.message) || textValue(error.error) || fallback
  return fallback
}

function isTimeoutError(error: unknown): boolean {
  if (!isRecord(error)) return false
  const code = textValue(error.code).toLowerCase()
  const message = textValue(error.message).toLowerCase()
  return code === 'econnaborted' || message.includes('timeout') || message.includes('超时')
}

function isPendingSyncResponse(response: SyncTriggerResponse): boolean {
  const status = textValue(response.status).toLowerCase()
  return ['pending', 'running', 'in_progress', 'syncing', 'timeout_polling'].includes(status)
}

function isSyncRunning(statusResponse: unknown): boolean {
  if (!isRecord(statusResponse) || !isRecord(statusResponse.pg_sync)) return false
  const value = statusResponse.pg_sync.is_running
  return value === true || textValue(value).toLowerCase() === 'true'
}

function isAutoQcFailure(autoQc: SyncAutoQcSummary): boolean {
  return ['failed', 'error', 'canceled', 'cancelled', 'not_created'].includes(
    String(autoQc.status || '')
      .trim()
      .toLowerCase(),
  )
}

function isAutoQcEnqueueFailure(autoQc: SyncAutoQcSummary): boolean {
  return (
    String(autoQc.status || '')
      .trim()
      .toLowerCase() === 'enqueue_failed'
  )
}

function isAutoQcPending(autoQc: SyncAutoQcSummary): boolean {
  return ['pending', 'enqueueing', 'running', 'syncing', 'in_progress'].includes(
    String(autoQc.status || '')
      .trim()
      .toLowerCase(),
  )
}

function isAutoQcEnqueueing(autoQc: SyncAutoQcSummary): boolean {
  return (
    String(autoQc.status || '')
      .trim()
      .toLowerCase() === 'enqueueing'
  )
}

function isNoEligibleRecord(autoQc: SyncAutoQcSummary): boolean {
  const status = String(autoQc.status || '')
    .trim()
    .toLowerCase()
  const eligibleRecords = Number(autoQc.eligible_records)
  const queuedRecords = Number(autoQc.queued_records)
  return (
    eligibleRecords === 0 ||
    (!autoQc.job_id && queuedRecords === 0) ||
    [
      'empty',
      'skipped',
      'no_records',
      'no_eligible_records',
      'not_applicable',
      'not_needed',
    ].includes(status)
  )
}

function getAutoQcSummary(response: SyncTriggerResponse): SyncAutoQcSummary | null {
  return isRecord(response.auto_qc) ? (response.auto_qc as SyncAutoQcSummary) : null
}

function finalizeCompletedJob() {
  clearPollingTimers()
  clearPersistedJob()
  retryableQcPayload.value = null
  completeStepsThrough(4)
  progressState.value = 'completed'
  progressSummary.value = '质控已完成，结果已刷新。'
  emit('completed')
}

function finalizeNoEligibleRecord() {
  clearPollingTimers()
  clearPersistedJob()
  retryableQcPayload.value = null
  completeStepsThrough(2)
  markPendingStepsAsSkipped(3)
  progressState.value = 'empty'
  progressSummary.value = '同步已完成，本次未形成可质控病历。'
}

function finalizeRetryableEnqueueFailure(payload: AutoQcSyncTriggerPayload) {
  clearPollingTimers()
  retryableQcPayload.value = payload
  completeStepsThrough(2)
  setStepStatus(3, 'failed')
  setStepStatus(4, 'pending')
  progressState.value = 'failed'
  progressSummary.value = '同步已完成，但质控任务创建失败。请重试创建质控。'
}

function finalizeFailure(message: string, failedStepIndex: number) {
  clearPollingTimers()
  clearPersistedJob()
  retryableQcPayload.value = null
  setStepStatus(failedStepIndex, 'failed')
  progressState.value = 'failed'
  progressSummary.value = message
}

function scheduleJobPoll(jobId: string) {
  clearPollTimer()
  pollTimer = window.setTimeout(() => {
    void pollBatchJob(jobId)
  }, JOB_POLL_INTERVAL_MS)
}

function handleJobPollFailure(jobId: string) {
  jobPollFailureCount += 1
  if (jobPollFailureCount >= MAX_CONSECUTIVE_JOB_POLL_FAILURES) {
    finalizeFailure('质控任务状态连续获取失败，请稍后刷新结果页查看。', 3)
    return
  }
  progressSummary.value = '正在等待质控任务状态更新。'
  scheduleJobPoll(jobId)
}

async function pollBatchJob(jobId: string) {
  if (polling.value || disposed) return
  polling.value = true
  try {
    const response = await getSichuanWorkspaceBatchJob(jobId)
    if (disposed) return
    if (!response.success || !response.data) {
      handleJobPollFailure(jobId)
      return
    }
    jobPollFailureCount = 0

    const status = String(response.data.status || '')
      .trim()
      .toLowerCase()
    if (status === 'completed') {
      finalizeCompletedJob()
      return
    }
    if (['failed', 'canceled', 'cancelled'].includes(status)) {
      clearPersistedJob()
      finalizeFailure(response.data.error_message || '质控未完成，请稍后在结果页重新查看。', 3)
      return
    }

    progressState.value = 'qc'
    completeStepsThrough(2)
    setStepStatus(3, 'active')
    progressSummary.value = '正在执行质控，完成后会自动刷新当前结果页。'
    scheduleJobPoll(jobId)
  } catch {
    if (!disposed) {
      handleJobPollFailure(jobId)
    }
  } finally {
    polling.value = false
  }
}

async function beginBatchJobTracking(jobId: string) {
  clearSyncStatusPollTimer()
  jobPollFailureCount = 0
  persistJob(jobId)
  progressState.value = 'qc'
  completeStepsThrough(2)
  setStepStatus(3, 'active')
  progressSummary.value = '正在执行质控，完成后会自动刷新当前结果页。'
  await pollBatchJob(jobId)
}

function createTriggerPayload(): AutoQcSyncTriggerPayload {
  const payload = {
    source: 'pg' as const,
    scene: scene.value,
    target_departments: targetDepartments.value,
    auto_qc_after_sync: true as const,
    auto_qc_workflow_token: createWorkflowToken(),
  }
  if (scene.value !== 'final') return payload
  return {
    ...payload,
    date_window: {
      start_date: selectedStartDate.value,
      end_date: selectedEndDate.value,
    },
  }
}

function scheduleSyncStatusPoll(payload: AutoQcSyncTriggerPayload) {
  clearSyncStatusPollTimer()
  syncStatusPollTimer = window.setTimeout(() => {
    void pollSyncStatus(payload)
  }, JOB_POLL_INTERVAL_MS)
}

async function pollSyncStatus(payload: AutoQcSyncTriggerPayload) {
  if (syncStatusPolling.value || disposed) return
  syncStatusPolling.value = true
  try {
    const statusResponse = await syncApi.getStatus()
    if (disposed) return
    if (isSyncRunning(statusResponse)) {
      progressSummary.value = '同步仍在后台执行，正在等待同步完成。'
      scheduleSyncStatusPoll(payload)
      return
    }
    progressSummary.value = '同步已结束，正在确认质控任务。'
    await requestSyncResult(payload)
  } catch {
    if (!disposed) {
      progressSummary.value = '同步仍在后台执行，正在等待同步状态更新。'
      scheduleSyncStatusPoll(payload)
    }
  } finally {
    syncStatusPolling.value = false
  }
}

function waitForBackgroundSync(payload: AutoQcSyncTriggerPayload, pollImmediately: boolean) {
  progressState.value = 'syncing'
  completeStepsThrough(0)
  setStepStatus(1, 'active')
  setStepStatus(2, 'pending')
  progressSummary.value = '同步仍在后台执行，正在等待同步完成。'
  if (pollImmediately) {
    void pollSyncStatus(payload)
    return
  }
  scheduleSyncStatusPoll(payload)
}

async function handleTriggerResponse(
  response: SyncTriggerResponse,
  payload: AutoQcSyncTriggerPayload,
) {
  if (response.success === false && isPendingSyncResponse(response)) {
    waitForBackgroundSync(payload, false)
    return
  }
  if (response.success === false) {
    finalizeFailure(`同步未完成，未启动质控：${getResponseError(response, '请稍后重试。')}`, 1)
    return
  }

  completeStepsThrough(1)
  setStepStatus(2, 'active')
  const autoQc = getAutoQcSummary(response)
  if (!autoQc) {
    if (isPendingSyncResponse(response)) {
      waitForBackgroundSync(payload, false)
      return
    }
    finalizeFailure('同步已完成，但未收到自动质控状态，请稍后刷新结果页查看。', 2)
    return
  }
  if (isAutoQcEnqueueing(autoQc) && !textValue(autoQc.job_id)) {
    enqueueingConfirmationCount += 1
    if (enqueueingConfirmationCount >= MAX_ENQUEUEING_CONFIRMATIONS) {
      finalizeFailure('质控任务创建或恢复超时，请稍后重试。', 3)
      return
    }
    waitForBackgroundSync(payload, false)
    progressSummary.value = '质控任务正在创建或恢复，请耐心等待。'
    return
  }
  enqueueingConfirmationCount = 0
  if (isAutoQcEnqueueFailure(autoQc)) {
    finalizeRetryableEnqueueFailure(payload)
    return
  }
  if (isAutoQcFailure(autoQc)) {
    finalizeFailure('同步已完成，但未能启动质控，请稍后重试。', 3)
    return
  }
  if (isAutoQcPending(autoQc)) {
    waitForBackgroundSync(payload, false)
    return
  }
  if (isNoEligibleRecord(autoQc)) {
    finalizeNoEligibleRecord()
    return
  }

  const jobId = textValue(autoQc.job_id)
  if (!jobId) {
    finalizeFailure('同步已完成，但未收到质控任务状态，请稍后刷新结果页查看。', 2)
    return
  }
  await beginBatchJobTracking(jobId)
}

async function requestSyncResult(payload: AutoQcSyncTriggerPayload) {
  try {
    const response = await syncApi.triggerSync(payload)
    await handleTriggerResponse(response, payload)
  } catch (error) {
    if (isTimeoutError(error)) {
      waitForBackgroundSync(payload, true)
      return
    }
    finalizeFailure(`同步未完成，未启动质控：${getErrorMessage(error, '请稍后重试。')}`, 1)
  }
}

async function retryQcCreation() {
  const payload = retryableQcPayload.value
  if (!payload || isBusy.value) return

  clearPollingTimers()
  persistSyncPayload(payload)
  retryableQcPayload.value = null
  progressVisible.value = true
  progressState.value = 'syncing'
  completeStepsThrough(2)
  setStepStatus(3, 'active')
  setStepStatus(4, 'pending')
  progressSummary.value = '正在重试创建质控任务。'
  await requestSyncResult(payload)
}

async function startSyncAndQc() {
  if (isBusy.value) return
  if (!validateFinalDateWindow()) return
  confirmationOpen.value = false
  progressVisible.value = true
  retryableQcPayload.value = null
  resetProgress()
  progressState.value = 'syncing'
  setStepStatus(0, 'active')
  progressSummary.value = '正在检查同步条件。'

  await nextTick()
  setStepStatus(0, 'completed')
  setStepStatus(1, 'active')
  progressSummary.value = '正在同步病历资料。'
  const payload = createTriggerPayload()
  persistSyncPayload(payload)
  await requestSyncResult(payload)
}

async function restorePersistedJob() {
  const persisted = readPersistedWorkflow()
  if (!persisted) return
  progressVisible.value = true
  resetProgress()
  if (persisted.stage === 'syncing') {
    progressState.value = 'syncing'
    completeStepsThrough(0)
    setStepStatus(1, 'active')
    progressSummary.value = '正在恢复此前的同步进度。'
    await pollSyncStatus(persisted.payload)
    return
  }
  progressState.value = 'qc'
  completeStepsThrough(2)
  setStepStatus(3, 'active')
  progressSummary.value = '正在恢复此前的质控进度。'
  await pollBatchJob(persisted.jobId)
}

onMounted(() => {
  void restorePersistedJob()
})

onUnmounted(() => {
  disposed = true
  clearPollingTimers()
})
</script>

<style scoped>
.qc-sync-and-run-control {
  display: inline-flex;
}

.qc-sync-and-run-control__trigger,
.qc-sync-and-run-control__primary-button,
.qc-sync-and-run-control__secondary-button,
.qc-sync-and-run-control__icon-button {
  border: 0;
  font: inherit;
  cursor: pointer;
}

.qc-sync-and-run-control__trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 13px;
  border-radius: 8px;
  color: #fff;
  background: #0a6cff;
  box-shadow: 0 3px 10px rgb(0 102 204 / 18%);
  font-size: 13px;
  font-weight: 600;
  transition:
    background 250ms cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 250ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.qc-sync-and-run-control__trigger:hover:not(:disabled) {
  background: #0059b3;
  transform: translateY(-1px);
}

.qc-sync-and-run-control__trigger:disabled {
  cursor: not-allowed;
  opacity: 0.68;
}

.qc-sync-and-run-control__backdrop {
  position: fixed;
  z-index: 1200;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgb(29 29 31 / 20%);
  backdrop-filter: blur(3px);
}

.qc-sync-and-run-control__dialog {
  width: min(100%, 480px);
  max-height: calc(100dvh - 40px);
  overflow-y: auto;
  border: 1px solid rgb(0 0 0 / 8%);
  border-radius: 16px;
  background: rgb(255 255 255 / 96%);
  box-shadow: 0 18px 50px rgb(0 0 0 / 16%);
  color: #1d1d1f;
  overscroll-behavior: contain;
}

.qc-sync-and-run-control__dialog-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 20px 22px 14px;
}

.qc-sync-and-run-control__dialog-header p {
  margin: 0 0 4px;
  color: rgb(29 29 31 / 60%);
  font-size: 12px;
  font-weight: 600;
}

.qc-sync-and-run-control__dialog-header h2 {
  margin: 0;
  font-size: 18px;
  line-height: 24px;
}

.qc-sync-and-run-control__icon-button {
  display: inline-grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 8px;
  color: rgb(29 29 31 / 60%);
  background: transparent;
}

.qc-sync-and-run-control__icon-button:hover {
  background: rgb(0 0 0 / 4%);
  color: #1d1d1f;
}

.qc-sync-and-run-control__scope-list {
  display: grid;
  gap: 10px;
  margin: 0 22px;
  padding: 13px 14px;
  border: 1px solid rgb(0 0 0 / 6%);
  border-radius: 10px;
  background: #f8fafc;
}

.qc-sync-and-run-control__scope-list div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 24px;
}

.qc-sync-and-run-control__scope-list dt,
.qc-sync-and-run-control__scope-list dd {
  margin: 0;
  font-size: 13px;
  line-height: 20px;
}

.qc-sync-and-run-control__scope-list dt {
  color: rgb(29 29 31 / 60%);
}

.qc-sync-and-run-control__scope-list dd {
  color: #1d1d1f;
  font-weight: 600;
  text-align: right;
}

.qc-sync-and-run-control__department-selector,
.qc-sync-and-run-control__date-selector {
  margin: 14px 22px 0;
  padding: 12px 14px 13px;
  border: 1px solid rgb(0 0 0 / 6%);
  border-radius: 10px;
  background: #fff;
}

.qc-sync-and-run-control__department-selector legend,
.qc-sync-and-run-control__date-selector legend {
  padding: 0 3px;
  color: rgb(29 29 31 / 68%);
  font-size: 12px;
  font-weight: 600;
}

.qc-sync-and-run-control__department-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  max-height: 232px;
  padding-right: 4px;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.qc-sync-and-run-control__department-option {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 22px;
  color: rgb(29 29 31 / 78%);
  font-size: 13px;
  line-height: 20px;
  cursor: pointer;
}

.qc-sync-and-run-control__department-option input {
  width: 14px;
  height: 14px;
  margin: 0;
  accent-color: #0a6cff;
}

.qc-sync-and-run-control__department-hint {
  margin: 0 0 8px;
  color: rgb(29 29 31 / 56%);
  font-size: 12px;
  line-height: 18px;
}

.qc-sync-and-run-control__department-hint.is-error {
  color: #b42318;
}

.qc-sync-and-run-control__date-hint {
  margin: 0 0 8px;
  color: rgb(29 29 31 / 56%);
  font-size: 12px;
  line-height: 18px;
}

.qc-sync-and-run-control__date-hint.is-error {
  margin-top: 8px;
  margin-bottom: 0;
  color: #b42318;
}

.qc-sync-and-run-control__date-inputs {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: end;
  gap: 8px;
}

.qc-sync-and-run-control__date-inputs label {
  display: grid;
  gap: 5px;
  color: rgb(29 29 31 / 64%);
  font-size: 12px;
  line-height: 18px;
}

.qc-sync-and-run-control__date-inputs input {
  width: 100%;
  min-width: 0;
  min-height: 34px;
  padding: 0 8px;
  border: 1px solid rgb(0 0 0 / 12%);
  border-radius: 7px;
  color: #1d1d1f;
  background: #fff;
  font: inherit;
}

.qc-sync-and-run-control__date-inputs input:focus {
  border-color: #0a6cff;
  outline: 2px solid rgb(0 102 204 / 14%);
  outline-offset: 1px;
}

.qc-sync-and-run-control__date-separator {
  padding-bottom: 7px;
  color: rgb(29 29 31 / 48%);
  font-size: 12px;
}

.qc-sync-and-run-control__description,
.qc-sync-and-run-control__progress-summary {
  margin: 14px 22px 0;
  color: rgb(29 29 31 / 68%);
  font-size: 13px;
  line-height: 21px;
}

.qc-sync-and-run-control__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 18px 22px 20px;
}

.qc-sync-and-run-control__primary-button,
.qc-sync-and-run-control__secondary-button {
  min-height: 34px;
  padding: 0 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
}

.qc-sync-and-run-control__primary-button {
  color: #fff;
  background: #0a6cff;
}

.qc-sync-and-run-control__primary-button:hover {
  background: #0059b3;
}

.qc-sync-and-run-control__secondary-button {
  border: 1px solid rgb(0 0 0 / 10%);
  color: rgb(29 29 31 / 74%);
  background: #fff;
}

.qc-sync-and-run-control__secondary-button:hover {
  background: rgb(0 0 0 / 3%);
}

.qc-sync-and-run-control__dialog--progress {
  width: min(100%, 520px);
}

.qc-sync-and-run-control__steps {
  display: grid;
  gap: 0;
  margin: 0 22px;
  padding: 4px 0;
  list-style: none;
}

.qc-sync-and-run-control__steps li {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
  min-height: 38px;
  color: rgb(29 29 31 / 48%);
  font-size: 13px;
}

.qc-sync-and-run-control__steps li.is-active {
  color: #0a6cff;
  font-weight: 600;
}

.qc-sync-and-run-control__steps li.is-completed {
  color: #1d1d1f;
}

.qc-sync-and-run-control__steps li.is-failed {
  color: #c23b31;
}

.qc-sync-and-run-control__step-mark {
  display: inline-grid;
  width: 20px;
  height: 20px;
  place-items: center;
  border: 1px solid currentcolor;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
}

.qc-sync-and-run-control__steps li.is-active .qc-sync-and-run-control__step-mark {
  border-color: #0a6cff;
  background: rgb(0 102 204 / 9%);
}

.qc-sync-and-run-control__steps li.is-completed .qc-sync-and-run-control__step-mark {
  border-color: #10b981;
  color: #10b981;
}

.qc-sync-and-run-control__steps small {
  color: inherit;
  font-size: 11px;
  font-weight: 500;
}

.qc-sync-and-run-control__progress-summary {
  min-height: 21px;
  padding: 11px 12px;
  border-radius: 8px;
  background: #f6f8fb;
}

.qc-sync-and-run-control__progress-summary.is-empty {
  color: #8a5a00;
  background: #fff8e8;
}

.qc-sync-and-run-control__progress-summary.is-error {
  color: #b42318;
  background: #fff1f0;
}

@media (max-width: 640px) {
  .qc-sync-and-run-control__backdrop {
    align-items: end;
    padding: 12px;
  }

  .qc-sync-and-run-control__dialog {
    border-radius: 14px;
  }
}
</style>
