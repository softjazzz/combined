<template>
  <div class="task-record-sync-control">
    <a-button
      data-testid="task-sync-records"
      :disabled="!canSubmit"
      :loading="syncing"
      @click="void submit()"
    >
      <RotateCw
        :size="15"
        aria-hidden="true"
      />
      同步病历
    </a-button>
    <p
      v-if="unavailableReason"
      class="task-record-sync-control__muted"
      data-testid="task-sync-unavailable"
    >
      {{ unavailableReason }}
    </p>
    <p
      v-if="syncing"
      class="task-record-sync-control__muted"
      role="status"
    >
      正在同步任务病历…
    </p>
    <div
      v-else-if="error"
      class="task-record-sync-control__error"
      role="alert"
      data-testid="task-sync-error"
    >
      {{ error }}
      <a-button
        v-if="needsVerification"
        data-testid="task-sync-verify"
        size="small"
        @click="void verify()"
      >
        重新查询
      </a-button>
    </div>
    <div
      v-else-if="result && (result.status === 'completed' || result.status === 'failed')"
      :class="result.failed_count ? 'task-record-sync-control__error' : 'task-record-sync-control__muted'"
      role="status"
      data-testid="task-sync-result"
    >
      已就绪 {{ result.ready_count }} / {{ result.total }} 份；失败 {{ result.failed_count }} 份{{ result.failed_count ? '，可重试同步' : '。可手动启动质控' }}
      <ul
        v-if="result.failed_count"
        class="task-record-sync-control__failures"
      >
        <li
          v-for="item in result.records.filter((entry) => entry.status === 'failed')"
          :key="item.task_record_id"
        >
          第 {{ task.records.findIndex((record) => record.id === item.task_record_id) + 1 }} 份：{{ failureLabel(item.reason_code) }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RotateCw } from 'lucide-vue-next'
import { getLatestTaskRecordSyncJob, getTaskRecordSyncJob, syncTaskRecords } from '@/api/tasks'
import type { TaskDetail, TaskRecordSyncResult } from '@/api/tasks'

const props = defineProps<{
  task: TaskDetail
  open: boolean
  disabled: boolean
}>()
const emit = defineEmits<{ busy: [value: boolean] }>()

const syncing = ref(false)
const lookupLoading = ref(false)
const needsVerification = ref(false)
const jobId = ref('')
const error = ref('')
const result = ref<TaskRecordSyncResult | null>(null)
let sequence = 0
let pollTimer: ReturnType<typeof setTimeout> | null = null

const unavailableReason = computed(() => {
  if (!props.task.records.length) return '任务暂无病历，无法同步'
  if (props.task.records.length > 100) return '单次最多同步 100 份病历'
  if (props.task.total_records !== props.task.records.length) return '任务抽样数量不一致，无法同步'
  if (!['sampling', 'assigned', 'in_progress', 'completed'].includes(props.task.status)) return '当前任务状态不可同步'
  if (!props.task.records.every((record) => record.task_id === props.task.id
    && [record.institute_id, record.patient_id, record.visit_id]
      .every((value) => typeof value === 'string' && value.trim().length > 0))) {
    return '存在未记录病例坐标的病历，无法同步'
  }
  return ''
})
const canSubmit = computed(() => props.open && !props.disabled && !unavailableReason.value
  && !syncing.value && !lookupLoading.value && !needsVerification.value)
const busy = computed(() => syncing.value || lookupLoading.value || needsVerification.value)

watch(busy, (value) => emit('busy', value), { immediate: true })

function clear() {
  sequence += 1
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = null
  syncing.value = false
  lookupLoading.value = false
  needsVerification.value = false
  jobId.value = ''
  error.value = ''
  result.value = null
}

function isCurrent(taskId: string, currentSequence: number) {
  return currentSequence === sequence && props.open && props.task.id === taskId
}

function validResult(value: TaskRecordSyncResult, taskId: string, expectedJobId?: string) {
  const records = props.task.records
  if (props.task.id !== taskId || typeof value.job_id !== 'string' || !value.job_id.trim()
    || (expectedJobId && value.job_id !== expectedJobId)
    || !['queued', 'running', 'completed', 'failed'].includes(value.status)
    || value.contract_version !== 'task-record-sync-v1'
    || !Number.isInteger(value.total) || value.total !== records.length
    || !Number.isInteger(value.ready_count) || value.ready_count < 0
    || !Number.isInteger(value.failed_count) || value.failed_count < 0
    || !Array.isArray(value.records) || value.records.length > value.total
    || value.ready_count + value.failed_count > value.total
    || new Set(value.records.map((item) => item.task_record_id)).size !== value.records.length
    || value.records.some((item) => !records.some((record) => record.id === item.task_record_id)
      || !['ready', 'failed'].includes(item.status))) return false
  if (value.status === 'completed') {
    return value.ready_count === value.total && value.failed_count === 0
      && value.records.length === value.total && value.records.every((item) => item.status === 'ready')
  }
  if (value.status === 'failed') return value.ready_count + value.failed_count === value.total
  return true
}

function accept(taskId: string, currentSequence: number, value: TaskRecordSyncResult, expectedJobId?: string) {
  if (!isCurrent(taskId, currentSequence)) return
  if (!validResult(value, taskId, expectedJobId)) {
    needsVerification.value = true
    syncing.value = false
    error.value = '同步状态校验失败，请重新查询'
    return
  }
  jobId.value = value.job_id
  result.value = value
  error.value = ''
  needsVerification.value = false
  syncing.value = value.status === 'queued' || value.status === 'running'
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = syncing.value
    ? setTimeout(() => { void query(taskId, value.job_id, currentSequence) }, 1500)
    : null
}

async function query(taskId: string, queriedJobId: string, currentSequence: number) {
  if (!isCurrent(taskId, currentSequence)) return
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = null
  lookupLoading.value = true
  try {
    const response = await getTaskRecordSyncJob(taskId, queriedJobId)
    if (!isCurrent(taskId, currentSequence)) return
    if (response.success && response.data) accept(taskId, currentSequence, response.data, queriedJobId)
    else {
      syncing.value = false
      needsVerification.value = true
      error.value = '同步状态暂不可确认，请重新查询'
    }
  } catch {
    if (isCurrent(taskId, currentSequence)) {
      syncing.value = false
      needsVerification.value = true
      error.value = '网络异常，同步状态未知，请重新查询'
    }
  } finally {
    if (isCurrent(taskId, currentSequence)) lookupLoading.value = false
  }
}

async function loadLatest(taskId: string) {
  const currentSequence = ++sequence
  lookupLoading.value = true
  try {
    const response = await getLatestTaskRecordSyncJob(taskId)
    if (!isCurrent(taskId, currentSequence)) return
    if (response.status === 404) {
      needsVerification.value = false
      syncing.value = false
      error.value = ''
      return
    }
    if (response.success && response.data) accept(taskId, currentSequence, response.data)
    else {
      needsVerification.value = true
      error.value = '同步状态暂不可确认，请重新查询'
    }
  } catch {
    if (isCurrent(taskId, currentSequence)) {
      needsVerification.value = true
      error.value = '网络异常，同步状态未知，请重新查询'
    }
  } finally {
    if (isCurrent(taskId, currentSequence)) lookupLoading.value = false
  }
}

function verify() {
  if (lookupLoading.value || !needsVerification.value) return
  if (jobId.value) void query(props.task.id, jobId.value, sequence)
  else void loadLatest(props.task.id)
}

async function submit() {
  if (!canSubmit.value) return
  const taskId = props.task.id
  const currentSequence = ++sequence
  syncing.value = true
  error.value = ''
  result.value = null
  try {
    const response = await syncTaskRecords(taskId)
    if (!isCurrent(taskId, currentSequence)) return
    const started = response.data
    if (!response.success && response.status && [400, 401, 403, 404, 409, 422, 429].includes(response.status)) {
      syncing.value = false
      needsVerification.value = false
      const labels: Record<number, string> = {
        400: '同步请求无效，请刷新任务后重试',
        401: '登录已失效，请重新登录',
        403: '没有同步任务病历的权限',
        404: '任务不存在或已不可访问',
        409: '当前任务状态冲突，请刷新后重试',
        422: '任务病例不满足同步条件，请核对清单',
        429: '同步队列繁忙，请稍后重试',
      }
      error.value = labels[response.status] || '同步请求未被接受'
      return
    }
    if (!response.success || !started || typeof started.job_id !== 'string' || !started.job_id.trim()
      || !['queued', 'running'].includes(started.status) || typeof started.reused !== 'boolean') {
      syncing.value = false
      needsVerification.value = true
      error.value = '同步提交状态未知，请重新查询'
      return
    }
    jobId.value = started.job_id
    void query(taskId, started.job_id, currentSequence)
  } catch {
    if (isCurrent(taskId, currentSequence)) {
      syncing.value = false
      needsVerification.value = true
      error.value = '网络异常，同步提交状态未知，请重新查询'
    }
  }
}

function failureLabel(reasonCode?: string | null) {
  const labels: Record<string, string> = {
    source_primary_missing: '源端未返回主记录',
    source_detail_unavailable: '源端资料集不完整',
    workspace_not_ready: '本地病历资料尚未就绪',
  }
  return reasonCode && Object.prototype.hasOwnProperty.call(labels, reasonCode)
    ? labels[reasonCode]! : '同步未完成'
}

watch([() => props.task.id, () => props.open], ([taskId, open]) => {
  clear()
  if (open) void loadLatest(taskId)
}, { immediate: true })
onBeforeUnmount(clear)
</script>

<style scoped>
.task-record-sync-control { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.task-record-sync-control__muted { color: rgba(29, 29, 31, 0.6); }
.task-record-sync-control__error { color: #b42318; }
.task-record-sync-control__failures { margin: 4px 0 0; padding-left: 20px; }
</style>
