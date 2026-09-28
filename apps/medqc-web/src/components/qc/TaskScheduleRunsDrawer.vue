<template>
  <a-drawer
    v-model:open="visible"
    :title="scheduleName ? `${scheduleName} · 运行历史` : '计划运行历史'"
    :width="'min(760px, 100vw)'"
    :body-style="{ padding: '18px 24px' }"
  >
    <div class="runs-toolbar">
      <a-select
        v-model:value="statusFilter"
        allow-clear
        placeholder="全部状态"
        :options="statusOptions"
        :disabled="loading"
        style="width: 150px"
        @change="handleFilterChange"
      />
      <a-button :loading="loading" title="刷新运行历史" @click="void loadRuns()">
        <ReloadOutlined /> 刷新
      </a-button>
      <a-button
        type="primary"
        :loading="runningNow"
        :disabled="!scheduleId || loading"
        data-testid="run-now"
        @click="confirmRunNow"
      >
        <PlayCircleOutlined /> {{ pendingRunNow ? '安全重试' : '立即运行' }}
      </a-button>
    </div>

    <a-alert
      v-if="loadError"
      type="error"
      show-icon
      :message="loadError"
      class="runs-alert"
    />

    <a-spin :spinning="loading">
      <a-empty v-if="!loading && !loadError && !runs.length" description="暂无运行记录" />
      <div v-else class="run-list">
        <article v-for="item in runs" :key="item.id" class="run-row">
          <div class="run-primary">
            <div class="run-title">
              <a-tag :color="runStatusColor(item.status)">{{ runStatusLabel(item.status) }}</a-tag>
              <span>{{ item.trigger_type === 'manual' ? '手动触发' : '计划触发' }}</span>
              <span class="run-at">{{ formatDateTime(item.scheduled_fire_at) }}</span>
            </div>
            <p v-if="item.error_message" class="run-error">{{ item.error_message }}</p>
            <p v-if="item.generated_task_id">
              生成任务：
              <a-button type="link" size="small" @click="emit('view-task', item.generated_task_id)">
                {{ item.generated_task_id }}
              </a-button>
            </p>
            <p v-else>尚未生成单次任务</p>
          </div>
          <dl class="run-meta">
            <div><dt>尝试次数</dt><dd>{{ item.attempt_count }}</dd></div>
            <div><dt>开始</dt><dd>{{ formatDateTime(item.started_at) }}</dd></div>
            <div><dt>结束</dt><dd>{{ formatDateTime(item.finished_at) }}</dd></div>
          </dl>
          <a-button
            v-if="item.status === 'failed' && !uncertainRetryIds.has(item.id)"
            size="small"
            :loading="retryingIds.has(item.id)"
            @click="confirmRetry(item)"
          >重试</a-button>
          <a-button
            v-else-if="uncertainRetryIds.has(item.id)"
            size="small"
            :loading="loading"
            @click="void loadRuns()"
          >核对重试结果</a-button>
        </article>
      </div>
    </a-spin>

    <a-pagination
      v-if="total > pageSize"
      v-model:current="page"
      :page-size="pageSize"
      :total="total"
      :show-size-changer="false"
      class="runs-pagination"
      @change="void loadRuns()"
    />
  </a-drawer>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch, computed } from 'vue'
import { Modal, message } from 'ant-design-vue'
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import {
  listTaskScheduleRuns,
  retryTaskScheduleRun,
  runTaskScheduleNow,
  type TaskScheduleRunResponse,
  type TaskScheduleRunStatus,
} from '@/api/taskSchedules'

const RUN_ATTEMPTS_STORAGE_KEY = 'medqc.taskSchedule.runAttempts.v1'

interface PendingRunAttempt {
  scheduleId: string
  actorId: string
  key: string
}

const props = defineProps<{
  open: boolean
  scheduleId: string | null
  scheduleName?: string
}>()
const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
  (event: 'view-task', taskId: string): void
  (event: 'run-created', runId: string): void
}>()

const authStore = useAuthStore()
const visible = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})
const runs = ref<TaskScheduleRunResponse[]>([])
const loading = ref(false)
const loadError = ref('')
const statusFilter = ref<TaskScheduleRunStatus | undefined>()
const page = ref(1)
const pageSize = 20
const total = ref(0)
const runningNow = ref(false)
const pendingRunAttempts = ref<Record<string, PendingRunAttempt>>({})
const retryingIds = ref(new Set<string>())
const uncertainRetryIds = ref(new Set<string>())
let lifecycleSequence = 0
let loadSequence = 0

const pendingRunNow = computed(() => {
  const scheduleId = props.scheduleId?.trim()
  const actorId = authStore.user?.id?.trim()
  return scheduleId && actorId ? pendingRunAttempts.value[runAttemptKey(actorId, scheduleId)] || null : null
})

const statusOptions = [
  { value: 'queued', label: '排队中' },
  { value: 'running', label: '运行中' },
  { value: 'succeeded', label: '抽样完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
]

function runStatusLabel(status: TaskScheduleRunStatus): string {
  return ({
    queued: '排队中', running: '运行中', succeeded: '抽样完成', failed: '失败', cancelled: '已取消',
  })[status]
}

function runStatusColor(status: TaskScheduleRunStatus): string {
  return ({ queued: 'blue', running: 'processing', succeeded: 'success', failed: 'error', cancelled: 'default' })[status]
}

function formatDateTime(value: string | null): string {
  if (!value) return '未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).format(date)
}

function runAttemptKey(actorId: string, scheduleId: string): string {
  return JSON.stringify([actorId, scheduleId])
}

function restoreRunAttempts() {
  try {
    const raw = sessionStorage.getItem(RUN_ATTEMPTS_STORAGE_KEY)
    if (!raw) return
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return
    const restored: Record<string, PendingRunAttempt> = {}
    for (const [storageKey, value] of Object.entries(parsed)) {
      if (typeof value !== 'object' || value === null || Array.isArray(value)) continue
      const attempt = value as Record<string, unknown>
      if (typeof attempt.actorId !== 'string' || !attempt.actorId.trim()
        || typeof attempt.scheduleId !== 'string' || !attempt.scheduleId.trim()
        || typeof attempt.key !== 'string' || !attempt.key.trim()
        || storageKey !== runAttemptKey(attempt.actorId, attempt.scheduleId)) continue
      restored[storageKey] = {
        actorId: attempt.actorId, scheduleId: attempt.scheduleId, key: attempt.key,
      }
    }
    pendingRunAttempts.value = restored
  } catch {
    pendingRunAttempts.value = {}
  }
}

function persistRunAttempts(next: Record<string, PendingRunAttempt>): boolean {
  try {
    sessionStorage.setItem(RUN_ATTEMPTS_STORAGE_KEY, JSON.stringify(next))
    pendingRunAttempts.value = next
    return true
  } catch {
    message.error('无法保存请求保护状态，请勿重复操作')
    return false
  }
}

function clearRunAttempt(actorId: string, scheduleId: string) {
  const next = { ...pendingRunAttempts.value }
  delete next[runAttemptKey(actorId, scheduleId)]
  persistRunAttempts(next)
}

async function loadRuns() {
  const scheduleId = props.scheduleId?.trim()
  const actorId = authStore.user?.id?.trim()
  const sequence = ++loadSequence
  runs.value = []
  total.value = 0
  loadError.value = ''
  if (!props.open || !scheduleId || !actorId) {
    loadError.value = actorId ? '未选择定时计划' : '当前用户身份不可用'
    return
  }
  loading.value = true
  const result = await listTaskScheduleRuns(scheduleId, {
    page: page.value, page_size: pageSize, ...(statusFilter.value ? { status: statusFilter.value } : {}),
  })
  if (sequence !== loadSequence
    || !props.open
    || props.scheduleId?.trim() !== scheduleId
    || authStore.user?.id?.trim() !== actorId) return
  loading.value = false
  if (!result.success || !result.data) {
    loadError.value = result.message || '运行历史读取失败'
    return
  }
  runs.value = result.data.items
  total.value = result.data.total
  page.value = result.data.page
  if (pendingRunNow.value) {
    const attempt = pendingRunNow.value
    const key = attempt.key
    const confirmed = runs.value.some((item) =>
      item.trigger_type === 'manual'
      && (item.idempotency_key === key || item.idempotency_key.endsWith(`:${key}`)),
    )
    if (confirmed) clearRunAttempt(attempt.actorId, attempt.scheduleId)
  }
  const nextUncertain = new Set(uncertainRetryIds.value)
  for (const item of runs.value) {
    if (item.status !== 'failed') nextUncertain.delete(item.id)
  }
  uncertainRetryIds.value = nextUncertain
}

function confirmRunNow() {
  const scheduleId = props.scheduleId?.trim()
  const actorId = authStore.user?.id?.trim()
  if (!scheduleId || !actorId || runningNow.value) return
  let key: string | null = pendingRunNow.value?.key || null
  if (!key) {
    key = globalThis.crypto?.randomUUID?.() || null
    if (!key) {
      message.error('当前环境无法生成安全请求编号，未发起立即运行')
      return
    }
  }
  const context = { scheduleId, actorId, key, sequence: lifecycleSequence }
  Modal.confirm({
    title: pendingRunNow.value ? '使用原请求编号安全重试？' : '确认立即运行计划？',
    content: '运行成功只表示抽样已持久化，不表示质控或人工处理完成。',
    okText: '确认运行', cancelText: '取消',
    async onOk() {
      if (context.sequence !== lifecycleSequence
        || props.scheduleId?.trim() !== context.scheduleId
        || authStore.user?.id?.trim() !== context.actorId) return
      await submitRunNow(context)
    },
  })
}

async function submitRunNow(context: { scheduleId: string; actorId: string; key: string; sequence: number }) {
  if (runningNow.value) return
  const attempt: PendingRunAttempt = {
    actorId: context.actorId, scheduleId: context.scheduleId, key: context.key,
  }
  const storageKey = runAttemptKey(context.actorId, context.scheduleId)
  if (!persistRunAttempts({ ...pendingRunAttempts.value, [storageKey]: attempt })) return
  runningNow.value = true
  const result = await runTaskScheduleNow(context.scheduleId, context.key)
  const currentAttempt = pendingRunAttempts.value[storageKey]
  if (currentAttempt?.key !== context.key) return
  const receiptValid = result.success
    && !!result.data
    && result.data.schedule_id === context.scheduleId
    && result.data.trigger_type === 'manual'
  if (receiptValid || (!result.success && !result.uncertain && result.code !== 'request_conflict')) {
    clearRunAttempt(context.actorId, context.scheduleId)
  }
  if (context.sequence !== lifecycleSequence
    || !props.open
    || props.scheduleId?.trim() !== context.scheduleId
    || authStore.user?.id?.trim() !== context.actorId) return
  runningNow.value = false
  if (!result.success || !result.data) {
    if (result.uncertain) {
      message.warning('立即运行结果未知；已保留原请求编号，只能安全重试或刷新历史核对')
    } else {
      message.error(result.message || '立即运行失败')
    }
    return
  }
  if (!receiptValid) {
    message.warning('立即运行回执无法核实，请刷新历史')
    return
  }
  runs.value = [result.data, ...runs.value.filter((item) => item.id !== result.data?.id)]
  emit('run-created', result.data.id)
  message.success('计划运行已入队')
}

function confirmRetry(item: TaskScheduleRunResponse) {
  const actorId = authStore.user?.id?.trim()
  const scheduleId = props.scheduleId?.trim()
  if (!actorId || !scheduleId || retryingIds.value.has(item.id) || uncertainRetryIds.value.has(item.id)) return
  const context = { actorId, scheduleId, runId: item.id, sequence: lifecycleSequence }
  Modal.confirm({
    title: '确认重试失败运行？',
    content: '重试复用原运行与子任务身份，不会新建重复任务。',
    okText: '确认重试', cancelText: '取消',
    async onOk() {
      const current = runs.value.find((runItem) => runItem.id === context.runId)
      if (context.sequence !== lifecycleSequence
        || props.scheduleId?.trim() !== context.scheduleId
        || authStore.user?.id?.trim() !== context.actorId
        || current?.status !== 'failed') return
      await submitRetry(context)
    },
  })
}

async function submitRetry(context: { actorId: string; scheduleId: string; runId: string; sequence: number }) {
  if (retryingIds.value.has(context.runId)) return
  retryingIds.value = new Set([...retryingIds.value, context.runId])
  const result = await retryTaskScheduleRun(context.runId)
  if (context.sequence !== lifecycleSequence
    || !props.open
    || props.scheduleId?.trim() !== context.scheduleId
    || authStore.user?.id?.trim() !== context.actorId) return
  const remaining = new Set(retryingIds.value)
  remaining.delete(context.runId)
  retryingIds.value = remaining
  if (!result.success || !result.data) {
    if (result.uncertain) {
      uncertainRetryIds.value = new Set([...uncertainRetryIds.value, context.runId])
      message.warning('重试结果未知，请刷新历史核对后再操作')
    } else {
      message.error(result.message || '运行重试失败')
    }
    return
  }
  if (result.data.id !== context.runId
    || result.data.schedule_id !== context.scheduleId
    || (result.data.status !== 'queued'
      && result.data.status !== 'running'
      && result.data.status !== 'succeeded')) {
    uncertainRetryIds.value = new Set([...uncertainRetryIds.value, context.runId])
    message.warning('重试回执无法核实，请刷新历史')
    return
  }
  const index = runs.value.findIndex((item) => item.id === context.runId)
  if (index >= 0) runs.value.splice(index, 1, result.data)
  message.success('失败运行已重新入队')
}

function handleFilterChange() {
  page.value = 1
  void loadRuns()
}

watch(
  [() => props.open, () => props.scheduleId, () => authStore.user?.id],
  ([open, scheduleId, actorId], [, previousScheduleId, previousActorId]) => {
    lifecycleSequence += 1
    loadSequence += 1
    runs.value = []
    total.value = 0
    loading.value = false
    runningNow.value = false
    retryingIds.value = new Set()
    loadError.value = ''
    page.value = 1
    if (scheduleId !== previousScheduleId || actorId !== previousActorId) {
      uncertainRetryIds.value = new Set()
    }
    restoreRunAttempts()
    if (open) void loadRuns()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  lifecycleSequence += 1
  loadSequence += 1
})
</script>

<style scoped>
.runs-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
}
.runs-alert { margin-bottom: 16px; }
.run-list { border-top: 1px solid rgba(0, 0, 0, 0.08); }
.run-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 20px;
  padding: 16px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}
.run-title { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; color: #1d1d1f; }
.run-at { color: rgba(29, 29, 31, 0.6); }
.run-primary p { margin: 7px 0 0; color: rgba(29, 29, 31, 0.6); }
.run-primary .run-error { color: #ef4444; }
.run-meta { display: grid; grid-template-columns: repeat(3, auto); gap: 18px; margin: 0; }
.run-meta div { min-width: 82px; }
.run-meta dt { color: rgba(29, 29, 31, 0.6); font-size: 12px; }
.run-meta dd { margin: 3px 0 0; color: #1d1d1f; }
.runs-pagination { margin-top: 18px; text-align: right; }
@media (max-width: 640px) {
  .run-row { grid-template-columns: 1fr; }
  .run-meta { grid-template-columns: 1fr; gap: 8px; }
}
</style>
