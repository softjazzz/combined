<template>
  <a-drawer
    v-model:open="visible"
    title="定时任务计划"
    :width="'min(860px, 100vw)'"
    :body-style="{ padding: '18px 24px' }"
  >
    <TaskScheduleRunsDrawer
      v-model:open="runsOpen"
      :schedule-id="runsSchedule?.id || null"
      :schedule-name="runsSchedule?.name"
      @view-task="emit('view-task', $event)"
    />

    <div class="schedule-toolbar">
      <a-segmented
        v-model:value="viewMode"
        :options="[
          { label: '计划列表', value: 'list' },
          { label: '创建计划', value: 'create' },
        ]"
      />
      <template v-if="viewMode === 'list'">
        <a-select
          v-model:value="stateFilter"
          allow-clear
          placeholder="全部状态"
          :options="stateOptions"
          style="width: 140px"
          @change="handleStateFilter"
        />
        <a-button :loading="loading" title="刷新计划" @click="void loadSchedules()">
          <ReloadOutlined /> 刷新
        </a-button>
      </template>
    </div>

    <template v-if="viewMode === 'list'">
      <a-alert
        v-if="loadError"
        type="error"
        show-icon
        :message="loadError"
        class="schedule-alert"
      />
      <a-spin :spinning="loading">
        <a-empty v-if="!loading && !loadError && !schedules.length" description="暂无定时计划" />
        <div v-else class="schedule-list">
          <article v-for="item in schedules" :key="item.id" class="schedule-row">
            <button class="schedule-summary" type="button" @click="void openDetail(item.id)">
              <span class="schedule-title-line">
                <strong>{{ item.name }}</strong>
                <a-tag :color="stateColor(item.state)">{{ stateLabel(item.state) }}</a-tag>
              </span>
              <span>{{ timingLabel(item.timing_config) }}</span>
              <span>下次执行：{{ formatDateTime(item.next_fire_at) }}</span>
            </button>
            <div class="schedule-actions">
              <a-button size="small" title="查看运行历史" @click="openRuns(item)">
                <HistoryOutlined /> 历史
              </a-button>
              <a-button
                v-if="uncertainIds.has(item.id)"
                size="small"
                :loading="checkingId === item.id"
                @click="void refreshOne(item.id)"
              >
                <ReloadOutlined /> 核对结果
              </a-button>
              <template v-else>
                <a-button
                  v-if="item.state === 'active'"
                  size="small"
                  :loading="writingIds.has(item.id)"
                  :disabled="writingIds.has(item.id)"
                  @click="confirmAction(item, 'pause')"
                >
                  暂停
                </a-button>
                <a-button
                  v-if="item.state === 'paused'"
                  size="small"
                  :loading="writingIds.has(item.id)"
                  :disabled="writingIds.has(item.id)"
                  @click="confirmAction(item, 'resume')"
                >
                  恢复
                </a-button>
                <a-button
                  v-if="item.state === 'active' || item.state === 'paused'"
                  size="small"
                  danger
                  :loading="writingIds.has(item.id)"
                  :disabled="writingIds.has(item.id)"
                  @click="confirmAction(item, 'cancel')"
                >
                  取消
                </a-button>
              </template>
            </div>
          </article>
        </div>
      </a-spin>
      <a-pagination
        v-if="total > pageSize"
        v-model:current="page"
        :page-size="pageSize"
        :total="total"
        :show-size-changer="false"
        class="schedule-pagination"
        @change="void loadSchedules()"
      />
    </template>

    <template v-else>
      <a-alert
        type="info"
        show-icon
        message="计划会冻结所选空草稿的场景、规则版本、抽样和分配配置；后续修改源草稿不会改变计划。"
        class="schedule-alert"
      />
      <a-alert
        v-if="createAttempt"
        type="warning"
        show-icon
        :message="
          createAttemptOwnedByCurrentActor
            ? '上次创建结果未知，禁止重复创建。请使用原请求编号安全核对。'
            : '另一个登录身份存在待核实的计划创建请求，请切回原账号处理。'
        "
        class="schedule-alert"
      >
        <template #action>
          <a-button
            size="small"
            :loading="reconcilingCreate"
            :disabled="!createAttemptOwnedByCurrentActor"
            @click="void reconcileUnknownCreate()"
          >
            使用原请求安全核对
          </a-button>
        </template>
      </a-alert>

      <a-form layout="vertical" class="schedule-form">
        <section aria-labelledby="schedule-source-title">
          <h3 id="schedule-source-title">源任务配置</h3>
          <a-form-item label="空的单次运行/终末草稿" required>
            <a-select
              v-model:value="selectedSourceTaskId"
              show-search
              :loading="sourceListLoading"
              :disabled="creating"
              :options="sourceOptions"
              placeholder="选择将被完整冻结的源草稿"
              @change="handleSourceChange"
            />
          </a-form-item>
          <a-alert
            v-if="sourceListError || sourceDetailError"
            type="error"
            show-icon
            :message="sourceDetailError || sourceListError"
          />
          <a-spin :spinning="sourceDetailLoading">
            <dl v-if="sourceDetail" class="source-facts">
              <div>
                <dt>任务</dt>
                <dd>{{ sourceDetail.task_name }}</dd>
              </div>
              <div>
                <dt>场景</dt>
                <dd>{{ sceneLabel(sourceDetail.scene) }}</dd>
              </div>
              <div>
                <dt>规则集</dt>
                <dd>{{ sourceDetail.rule_set_key }} / {{ sourceDetail.rule_set_version }}</dd>
              </div>
              <div>
                <dt>配置版本</dt>
                <dd>{{ sourceDetail.configuration_version }}</dd>
              </div>
              <div>
                <dt>抽样</dt>
                <dd>{{ samplingLabel }}</dd>
              </div>
              <div>
                <dt>分配</dt>
                <dd>{{ assignLabel }}</dd>
              </div>
            </dl>
          </a-spin>
        </section>

        <section aria-labelledby="schedule-timing-title">
          <h3 id="schedule-timing-title">执行时间</h3>
          <a-form-item label="周期" required>
            <a-radio-group v-model:value="timingKind" :disabled="creating">
              <a-radio-button value="once" :disabled="sourceDetail?.scene === 'final'">
                单次
              </a-radio-button>
              <a-radio-button value="daily"> 每天 </a-radio-button>
              <a-radio-button value="weekly"> 每周 </a-radio-button>
              <a-radio-button value="monthly"> 每月 </a-radio-button>
            </a-radio-group>
          </a-form-item>
          <div class="timing-grid">
            <a-form-item v-if="timingKind === 'once'" label="执行日期" required>
              <a-date-picker v-model:value="onceDate" :disabled="creating" style="width: 100%" />
            </a-form-item>
            <a-form-item v-else label="开始日期" required>
              <a-date-picker v-model:value="startDate" :disabled="creating" style="width: 100%" />
            </a-form-item>
            <a-form-item label="执行时间" required>
              <a-time-picker
                v-model:value="executionTime"
                format="HH:mm"
                :minute-step="5"
                :disabled="creating"
                style="width: 100%"
              />
            </a-form-item>
            <a-form-item v-if="timingKind !== 'once'" label="结束日期">
              <a-date-picker
                v-model:value="endDate"
                allow-clear
                :disabled="creating"
                style="width: 100%"
              />
            </a-form-item>
          </div>
          <a-form-item v-if="timingKind === 'weekly'" label="星期" required>
            <a-checkbox-group
              v-model:value="weekdays"
              :options="weekdayOptions"
              :disabled="creating"
            />
          </a-form-item>
          <a-form-item v-if="timingKind === 'monthly'" label="每月执行日" required>
            <a-input-number
              v-model:value="monthDay"
              :min="1"
              :max="31"
              :precision="0"
              :disabled="creating"
            />
            <span class="field-note">当月不足该日时，在当月最后一日执行。</span>
          </a-form-item>
          <p class="timezone-note">所有执行时间均按 Asia/Shanghai（中国标准时间）保存和计算。</p>
          <p v-if="sourceDetail?.scene === 'final'" class="timezone-note">
            终末计划按触发时点取上一完整自然周期的已出院病历，归档状态未核验。
          </p>
        </section>
      </a-form>

      <div class="create-actions">
        <a-button :disabled="creating" @click="resetCreateForm"> 重置 </a-button>
        <a-button
          type="primary"
          :loading="creating"
          :disabled="!sourceDetail || sourceDetailLoading || sourceLockedByUnknownResult"
          data-testid="create-task-schedule"
          @click="confirmCreate"
        >
          <PlusOutlined /> 创建计划
        </a-button>
      </div>
    </template>

    <a-drawer v-model:open="detailOpen" title="计划详情" :width="'min(620px, 100vw)'">
      <a-spin :spinning="detailLoading">
        <a-alert v-if="detailError" type="error" show-icon :message="detailError" />
        <template v-if="selectedSchedule">
          <a-descriptions bordered :column="1" size="small">
            <a-descriptions-item label="计划名称">
              {{ selectedSchedule.name }}
            </a-descriptions-item>
            <a-descriptions-item label="状态">
              {{ stateLabel(selectedSchedule.state) }}
            </a-descriptions-item>
            <a-descriptions-item label="场景">
              {{ sceneLabel(selectedSchedule.scene) }}
            </a-descriptions-item>
            <a-descriptions-item label="周期">
              {{ timingLabel(selectedSchedule.timing_config) }}
            </a-descriptions-item>
            <a-descriptions-item label="下次执行">
              {{ formatDateTime(selectedSchedule.next_fire_at) }}
            </a-descriptions-item>
            <a-descriptions-item label="上次执行">
              {{ formatDateTime(selectedSchedule.last_fire_at) }}
            </a-descriptions-item>
            <a-descriptions-item label="规则集">
              {{ selectedSchedule.rule_set_key }} / {{ selectedSchedule.rule_set_version }}
            </a-descriptions-item>
            <a-descriptions-item label="源任务">
              {{ selectedSchedule.source_task_id }}
            </a-descriptions-item>
            <a-descriptions-item label="抽样方式">
              {{ samplingMethodLabels[selectedSchedule.task_config.sampling_method] }}
            </a-descriptions-item>
            <a-descriptions-item label="分配方式">
              {{ selectedSchedule.task_config.assign_method }}
            </a-descriptions-item>
          </a-descriptions>
          <div class="detail-actions">
            <a-button @click="openRuns(selectedSchedule)"> <HistoryOutlined /> 运行历史 </a-button>
            <a-button type="primary" @click="openRuns(selectedSchedule)">
              <PlayCircleOutlined /> 立即运行
            </a-button>
          </div>
        </template>
      </a-spin>
    </a-drawer>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import dayjs, { type Dayjs } from 'dayjs'
import { Modal, message } from 'ant-design-vue'
import {
  HistoryOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { getTaskList, type TaskItem, type TaskScene } from '@/api/tasks'
import { getTaskEdit, type TaskEditDetail, type TaskEditField } from '@/api/taskEdits'
import {
  cancelTaskSchedule,
  createTaskSchedule,
  getTaskSchedule,
  listTaskSchedules,
  pauseTaskSchedule,
  resumeTaskSchedule,
  type TaskScheduleCreateRequest,
  type TaskScheduleResponse,
  type TaskScheduleState,
  type TaskScheduleTiming,
} from '@/api/taskSchedules'
import TaskScheduleRunsDrawer from './TaskScheduleRunsDrawer.vue'

const CREATE_ATTEMPT_STORAGE_KEY = 'medqc.taskSchedule.createAttempt.v1'

interface PendingCreateAttempt {
  actorId: string
  sourceTaskId: string
  requestKey: string
  payload: TaskScheduleCreateRequest
}

const props = defineProps<{ open: boolean; sourceTaskId?: string | null }>()
const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
  (event: 'changed', scheduleId: string): void
  (event: 'view-task', taskId: string): void
}>()

const authStore = useAuthStore()
const visible = computed({ get: () => props.open, set: (value) => emit('update:open', value) })
const viewMode = ref<'list' | 'create'>('list')
const schedules = shallowRef<TaskScheduleResponse[]>([])
const loading = ref(false)
const loadError = ref('')
const stateFilter = ref<TaskScheduleState | undefined>()
const page = ref(1)
const pageSize = 20
const total = ref(0)
const uncertainIds = ref(new Set<string>())
const writingIds = ref(new Set<string>())
const checkingId = ref<string | null>(null)
const sourceTasks = ref<TaskItem[]>([])
const sourceListLoading = ref(false)
const sourceListError = ref('')
const selectedSourceTaskId = ref<string | undefined>()
const sourceDetail = ref<TaskEditDetail | null>(null)
const sourceDetailLoading = ref(false)
const sourceDetailError = ref('')
const timingKind = ref<'once' | 'daily' | 'weekly' | 'monthly'>('once')
const onceDate = ref<Dayjs | null>(null)
const startDate = ref<Dayjs | null>(null)
const endDate = ref<Dayjs | null>(null)
const executionTime = ref<Dayjs | null>(dayjs().hour(9).minute(0).second(0))
const weekdays = ref<number[]>([])
const monthDay = ref(1)
const creating = ref(false)
const createAttempts = ref<Record<string, PendingCreateAttempt>>({})
const reconcilingCreate = ref(false)
const detailOpen = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const selectedSchedule = shallowRef<TaskScheduleResponse | null>(null)
const runsOpen = ref(false)
const runsSchedule = shallowRef<TaskScheduleResponse | null>(null)
let lifecycleSequence = 0
let listSequence = 0
let sourceListSequence = 0
let sourceDetailSequence = 0
let detailSequence = 0

const stateOptions = [
  { value: 'active', label: '运行中' },
  { value: 'paused', label: '已暂停' },
  { value: 'ended', label: '已结束' },
  { value: 'cancelled', label: '已取消' },
]
const weekdayOptions = [
  { value: 1, label: '周一' },
  { value: 2, label: '周二' },
  { value: 3, label: '周三' },
  { value: 4, label: '周四' },
  { value: 5, label: '周五' },
  { value: 6, label: '周六' },
  { value: 7, label: '周日' },
]
const sourceOptions = computed(() => {
  const items = sourceTasks.value.map((item) => ({
    value: item.id,
    label: `${item.task_name}（${item.task_number}）`,
  }))
  if (
    selectedSourceTaskId.value &&
    !items.some((item) => item.value === selectedSourceTaskId.value)
  ) {
    items.unshift({
      value: selectedSourceTaskId.value,
      label: `指定源任务（${selectedSourceTaskId.value}）`,
    })
  }
  return items
})
const createAttempt = computed(() => {
  const actorId = authStore.user?.id?.trim()
  const sourceTaskId = selectedSourceTaskId.value
  return actorId && sourceTaskId
    ? createAttempts.value[createAttemptKey(actorId, sourceTaskId)] || null
    : null
})
const sourceLockedByUnknownResult = computed(() => !!createAttempt.value)
const createAttemptOwnedByCurrentActor = computed(() => !!createAttempt.value)
const samplingMethodLabels: Record<import('@/api/tasks').SamplingMethod, string> = {
  all: '全部病历',
  count: '总数抽样',
  percentage: '比例抽样',
  department_count: '每科室定额',
  department_ratio: '每科室比例',
  qc_physician_count: '每质控医师签名定额',
  qc_physician_ratio: '每质控医师签名比例',
  qc_reviewer_count: '每最近审核质控员定额',
  qc_reviewer_ratio: '每最近审核质控员比例',
}
const samplingLabel = computed(() => {
  const detail = sourceDetail.value
  if (!detail?.sampling_method) return '未知'
  if (detail.sampling_method === 'all') {
    return detail.scene === 'final' ? '全部周期内已出院病历' : '全部当前在院病历'
  }
  if (detail.sampling_method === 'count')
    return `按数量 ${String(detail.sampling_config?.total ?? '未知')}`
  if (detail.sampling_method === 'department_count')
    return `每科室固定 ${String(detail.sampling_config?.total ?? '未知')} 份`
  if (detail.sampling_method === 'department_ratio')
    return `每科室 ${String(detail.sampling_config?.percentage ?? '未知')}%，最多 ${String(detail.sampling_config?.max_per_group ?? '未知')} 份`
  if (
    detail.sampling_method.startsWith('qc_physician_') ||
    detail.sampling_method.startsWith('qc_reviewer_')
  ) {
    const group = detail.sampling_method.startsWith('qc_physician_')
      ? '每机构内质控医师签名'
      : '每机构内最近审核质控员'
    return detail.sampling_method.endsWith('_count')
      ? `${group}固定 ${String(detail.sampling_config?.total ?? '未知')} 份`
      : `${group} ${String(detail.sampling_config?.percentage ?? '未知')}%，最多 ${String(detail.sampling_config?.max_per_group ?? '未知')} 份`
  }
  return `按比例 ${String(detail.sampling_config?.percentage ?? '未知')}%`
})
const assignLabel = computed(() => {
  const method = sourceDetail.value?.assign_method
  if (method === 'by_ratio') return '按比例均分'
  if (method === 'by_original_reviewer') return '原质控员'
  if (method === 'by_department') return '按科室'
  return '未知'
})

function stateLabel(state: TaskScheduleState): string {
  return { active: '运行中', paused: '已暂停', ended: '已结束', cancelled: '已取消' }[state]
}

function stateColor(state: TaskScheduleState): string {
  return { active: 'processing', paused: 'warning', ended: 'success', cancelled: 'default' }[state]
}

function sceneLabel(scene: TaskScene): string {
  if (scene === 'final') return '终末病历（已出院，归档未核验）'
  if (scene === 'running') return '运行病历（当前在院）'
  return '门急诊病历'
}

function formatDateTime(value: string | null): string {
  if (!value) return '未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

function timingLabel(timing: TaskScheduleTiming): string {
  if (timing.kind === 'once') return `单次 · ${formatDateTime(timing.run_at)}`
  const dateSuffix = timing.end_date
    ? `${timing.start_date} 至 ${timing.end_date}`
    : `${timing.start_date} 起`
  if (timing.kind === 'daily') return `每天 ${timing.time} · ${dateSuffix}`
  if (timing.kind === 'monthly') return `每月 ${timing.day} 日 ${timing.time} · ${dateSuffix}`
  const dayText = timing.weekdays
    .map((day) => weekdayOptions.find((item) => item.value === day)?.label)
    .join('、')
  return `每周 ${dayText} ${timing.time} · ${dateSuffix}`
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStoredCreateAttempt(value: unknown): value is PendingCreateAttempt {
  if (!isObject(value) || !isObject(value.payload) || !isObject(value.payload.timing_config))
    return false
  const timing = value.payload.timing_config
  return (
    typeof value.actorId === 'string' &&
    !!value.actorId.trim() &&
    typeof value.sourceTaskId === 'string' &&
    !!value.sourceTaskId.trim() &&
    typeof value.requestKey === 'string' &&
    !!value.requestKey.trim() &&
    value.payload.source_task_id === value.sourceTaskId &&
    typeof value.payload.source_configuration_version === 'number' &&
    Number.isInteger(value.payload.source_configuration_version) &&
    value.payload.source_configuration_version >= 1 &&
    timing.timezone === 'Asia/Shanghai' &&
    (timing.kind === 'once' ||
      timing.kind === 'daily' ||
      timing.kind === 'weekly' ||
      timing.kind === 'monthly')
  )
}

function createAttemptKey(actorId: string, sourceTaskId: string): string {
  return JSON.stringify([actorId, sourceTaskId])
}

function restoreCreateAttempt() {
  if (Object.keys(createAttempts.value).length) return
  try {
    const raw = sessionStorage.getItem(CREATE_ATTEMPT_STORAGE_KEY)
    if (!raw) return
    const parsed: unknown = JSON.parse(raw)
    if (!isObject(parsed)) throw new Error('invalid create attempts')
    const restored: Record<string, PendingCreateAttempt> = {}
    for (const [storageKey, value] of Object.entries(parsed)) {
      if (
        !isStoredCreateAttempt(value) ||
        storageKey !== createAttemptKey(value.actorId, value.sourceTaskId)
      )
        continue
      restored[storageKey] = value
    }
    createAttempts.value = restored
  } catch {
    createAttempts.value = {}
    try {
      sessionStorage.removeItem(CREATE_ATTEMPT_STORAGE_KEY)
    } catch {
      // 存储被浏览器策略禁用时保持内存为空；后续写入仍会失败关闭。
    }
  }
}

function saveCreateAttempts(next: Record<string, PendingCreateAttempt>): boolean {
  try {
    sessionStorage.setItem(CREATE_ATTEMPT_STORAGE_KEY, JSON.stringify(next))
    createAttempts.value = next
    return true
  } catch {
    message.error('无法保存安全请求编号，未发起计划创建')
    return false
  }
}

function persistCreateAttempt(attempt: PendingCreateAttempt): boolean {
  return saveCreateAttempts({
    ...createAttempts.value,
    [createAttemptKey(attempt.actorId, attempt.sourceTaskId)]: attempt,
  })
}

function clearCreateAttempt(attempt: PendingCreateAttempt): boolean {
  const next = { ...createAttempts.value }
  delete next[createAttemptKey(attempt.actorId, attempt.sourceTaskId)]
  return saveCreateAttempts(next)
}

async function loadSchedules() {
  const actorId = authStore.user?.id?.trim()
  const sequence = ++listSequence
  loadError.value = ''
  if (!props.open || !actorId) {
    loadError.value = '当前用户身份不可用'
    return
  }
  loading.value = true
  const result = await listTaskSchedules({
    page: page.value,
    page_size: pageSize,
    ...(stateFilter.value ? { state: stateFilter.value } : {}),
  })
  if (sequence !== listSequence || !props.open || authStore.user?.id?.trim() !== actorId) return
  loading.value = false
  if (!result.success || !result.data) {
    loadError.value = result.message || '定时计划读取失败'
    return
  }
  schedules.value = result.data.items
  total.value = result.data.total
  page.value = result.data.page
}

async function loadSourceTasks() {
  const actorId = authStore.user?.id?.trim()
  const sequence = ++sourceListSequence
  sourceTasks.value = []
  sourceListError.value = ''
  if (!props.open || !actorId) return
  sourceListLoading.value = true
  const result = await getTaskList({ tab: 'created', status: 'draft', page: 1, page_size: 100 })
  if (sequence !== sourceListSequence || !props.open || authStore.user?.id?.trim() !== actorId)
    return
  sourceListLoading.value = false
  if (!result.success || !result.data) {
    sourceListError.value = result.message || '源草稿列表读取失败'
    return
  }
  sourceTasks.value = result.data.items.filter(
    (item) =>
      item.task_type === 'one_time' &&
      item.status === 'draft' &&
      (item.scene === 'running' || item.scene === 'final') &&
      item.total_records === 0 &&
      !!item.rule_set_key &&
      !!item.rule_set_version,
  )
}

function sourceIsEligible(detail: TaskEditDetail): boolean {
  const requiredPlanningFields: TaskEditField[] = [
    'date_range',
    'department_filter',
    'record_refs',
    'sampling_method',
    'sampling_config',
    'assign_method',
    'assignee_config',
  ]
  return (
    detail.task_type === 'one_time' &&
    detail.status === 'draft' &&
    (detail.scene === 'running' || detail.scene === 'final') &&
    !!detail.rule_set_key &&
    !!detail.rule_set_version &&
    detail.deadline === null &&
    (detail.scene === 'final' || detail.date_range === null) &&
    (detail.record_refs?.length || 0) === 0 &&
    !!detail.sampling_method &&
    !!detail.sampling_config &&
    (detail.assign_method === 'by_ratio' ||
      detail.assign_method === 'by_original_reviewer' ||
      detail.assign_method === 'by_department') &&
    requiredPlanningFields.every((field) => detail.editable_fields.includes(field))
  )
}

async function loadSourceDetail(taskId: string) {
  const actorId = authStore.user?.id?.trim()
  const sequence = ++sourceDetailSequence
  sourceDetail.value = null
  sourceDetailError.value = ''
  if (!props.open || !actorId) return
  sourceDetailLoading.value = true
  const result = await getTaskEdit(taskId)
  if (
    sequence !== sourceDetailSequence ||
    !props.open ||
    selectedSourceTaskId.value !== taskId ||
    authStore.user?.id?.trim() !== actorId
  )
    return
  sourceDetailLoading.value = false
  if (!result.success || !result.data) {
    sourceDetailError.value = result.message || '源草稿配置读取失败'
    return
  }
  if (!sourceIsEligible(result.data)) {
    sourceDetailError.value = '该任务不是配置完整且未启动的空单次运行/终末草稿'
    return
  }
  sourceDetail.value = result.data
  if (result.data.scene === 'final' && timingKind.value === 'once') {
    timingKind.value = 'daily'
  }
}

function handleSourceChange(value: string) {
  selectedSourceTaskId.value = value
  void loadSourceDetail(value)
}

function buildTiming(): TaskScheduleTiming | null {
  if (!executionTime.value) {
    message.warning('请选择执行时间')
    return null
  }
  const time = executionTime.value.format('HH:mm')
  if (timingKind.value === 'once') {
    if (sourceDetail.value?.scene === 'final') {
      message.warning('终末定时抽样请选择每日、每周或每月周期')
      return null
    }
    if (!onceDate.value) {
      message.warning('请选择执行日期')
      return null
    }
    return {
      kind: 'once',
      timezone: 'Asia/Shanghai',
      run_at: `${onceDate.value.format('YYYY-MM-DD')}T${time}:00+08:00`,
    }
  }
  if (!startDate.value) {
    message.warning('请选择开始日期')
    return null
  }
  if (endDate.value && endDate.value.isBefore(startDate.value, 'day')) {
    message.warning('结束日期不能早于开始日期')
    return null
  }
  const common = {
    timezone: 'Asia/Shanghai' as const,
    time,
    start_date: startDate.value.format('YYYY-MM-DD'),
    end_date: endDate.value?.format('YYYY-MM-DD') || null,
  }
  if (timingKind.value === 'daily') return { kind: 'daily', ...common }
  if (timingKind.value === 'monthly') {
    if (!Number.isInteger(monthDay.value) || monthDay.value < 1 || monthDay.value > 31) {
      message.warning('每月执行日必须在 1 至 31 日之间')
      return null
    }
    return { kind: 'monthly', ...common, day: monthDay.value }
  }
  const normalizedWeekdays = [...new Set(weekdays.value)].sort((left, right) => left - right)
  if (!normalizedWeekdays.length) {
    message.warning('请至少选择一个星期')
    return null
  }
  return { kind: 'weekly', ...common, weekdays: normalizedWeekdays }
}

function confirmCreate() {
  const detail = sourceDetail.value
  const actorId = authStore.user?.id?.trim()
  const timing = buildTiming()
  if (!detail || !actorId || !timing || creating.value || sourceLockedByUnknownResult.value) return
  const context = {
    actorId,
    taskId: detail.id,
    version: detail.configuration_version,
    sequence: lifecycleSequence,
  }
  const payload: TaskScheduleCreateRequest = {
    source_task_id: detail.id,
    source_configuration_version: detail.configuration_version,
    timing_config: timing,
  }
  Modal.confirm({
    title: '确认创建定时计划？',
    content: '系统将冻结源草稿的当前配置，后续修改源草稿不会改变本计划。',
    okText: '确认创建',
    cancelText: '取消',
    async onOk() {
      if (
        context.sequence !== lifecycleSequence ||
        authStore.user?.id?.trim() !== context.actorId ||
        selectedSourceTaskId.value !== context.taskId ||
        sourceDetail.value?.configuration_version !== context.version
      )
        return
      await submitCreate(payload, context)
    },
  })
}

async function submitCreate(
  payload: TaskScheduleCreateRequest,
  context: { actorId: string; taskId: string; version: number; sequence: number },
) {
  if (creating.value || context.sequence !== lifecycleSequence) return
  const requestKey = globalThis.crypto?.randomUUID?.()
  if (!requestKey) {
    message.error('当前环境无法生成安全请求编号，未发起计划创建')
    return
  }
  const attempt: PendingCreateAttempt = {
    actorId: context.actorId,
    sourceTaskId: context.taskId,
    requestKey,
    payload,
  }
  if (!persistCreateAttempt(attempt)) return
  creating.value = true
  const result = await createTaskSchedule(payload, requestKey)
  const storageKey = createAttemptKey(context.actorId, context.taskId)
  const stored = createAttempts.value[storageKey]
  if (stored?.requestKey !== requestKey) {
    if (
      context.sequence === lifecycleSequence &&
      props.open &&
      authStore.user?.id?.trim() === context.actorId
    ) {
      creating.value = false
    }
    return
  }
  const receiptValid =
    result.success &&
    !!result.data &&
    result.data.source_task_id === context.taskId &&
    result.data.version >= 1
  if (receiptValid || (!result.success && !result.uncertain)) {
    clearCreateAttempt(attempt)
  }
  if (
    context.sequence === lifecycleSequence &&
    props.open &&
    authStore.user?.id?.trim() === context.actorId
  ) {
    creating.value = false
  }
  if (
    context.sequence !== lifecycleSequence ||
    !props.open ||
    authStore.user?.id?.trim() !== context.actorId ||
    selectedSourceTaskId.value !== context.taskId
  )
    return
  if (!result.success || !result.data) {
    if (result.uncertain) {
      message.warning('计划创建结果未知，请核对计划列表后再操作')
    } else {
      message.error(result.message || '计划创建失败')
    }
    return
  }
  if (!receiptValid) {
    message.warning('计划创建回执无法核实，请核对计划列表')
    return
  }
  message.success('定时计划已创建')
  emit('changed', result.data.id)
  viewMode.value = 'list'
  page.value = 1
  await loadSchedules()
}

async function reconcileUnknownCreate() {
  const attempt = createAttempt.value
  const taskId = attempt?.sourceTaskId
  const actorId = authStore.user?.id?.trim()
  if (!attempt || !taskId || actorId !== attempt.actorId || reconcilingCreate.value) return
  reconcilingCreate.value = true
  const result = await createTaskSchedule(attempt.payload, attempt.requestKey)
  const stored = createAttempts.value[createAttemptKey(attempt.actorId, attempt.sourceTaskId)]
  if (stored?.requestKey !== attempt.requestKey) {
    reconcilingCreate.value = false
    return
  }
  const receiptValid = result.success && result.data?.source_task_id === taskId
  if (
    (result.success && result.data?.source_task_id === taskId) ||
    (!result.success && !result.uncertain)
  ) {
    clearCreateAttempt(attempt)
  }
  reconcilingCreate.value = false
  if (
    !props.open ||
    authStore.user?.id?.trim() !== actorId ||
    selectedSourceTaskId.value !== taskId
  )
    return
  if (!result.success || !result.data) {
    message.error(result.message || '计划创建结果核对失败')
    return
  }
  const matched = result.data
  if (!receiptValid || matched.source_task_id !== taskId) {
    message.warning('计划创建回执不属于原源任务，仍禁止重复提交')
    return
  }
  clearCreateAttempt(attempt)
  page.value = 1
  viewMode.value = 'list'
  emit('changed', matched.id)
  message.success('已核实计划创建成功')
}

function confirmAction(item: TaskScheduleResponse, action: 'pause' | 'resume' | 'cancel') {
  if (uncertainIds.value.has(item.id) || writingIds.value.has(item.id)) return
  const actorId = authStore.user?.id?.trim()
  if (!actorId) return
  const context = {
    id: item.id,
    version: item.version,
    actorId,
    sequence: lifecycleSequence,
    action,
  }
  const label = { pause: '暂停', resume: '恢复', cancel: '取消' }[action]
  Modal.confirm({
    title: `确认${label}计划？`,
    content:
      action === 'resume' ? '恢复后从当前时间计算下一次执行，不补跑停用期间的批次。' : undefined,
    okText: `确认${label}`,
    cancelText: '返回',
    async onOk() {
      const current = schedules.value.find((value) => value.id === context.id)
      if (
        context.sequence !== lifecycleSequence ||
        authStore.user?.id?.trim() !== context.actorId ||
        current?.version !== context.version
      )
        return
      await executeAction(context)
    },
  })
}

async function executeAction(context: {
  id: string
  version: number
  actorId: string
  sequence: number
  action: 'pause' | 'resume' | 'cancel'
}) {
  if (writingIds.value.has(context.id)) return
  writingIds.value = new Set([...writingIds.value, context.id])
  const call =
    context.action === 'pause'
      ? pauseTaskSchedule
      : context.action === 'resume'
        ? resumeTaskSchedule
        : cancelTaskSchedule
  const result = await call(context.id, { version: context.version })
  if (
    context.sequence !== lifecycleSequence ||
    !props.open ||
    authStore.user?.id?.trim() !== context.actorId
  )
    return
  const remainingWrites = new Set(writingIds.value)
  remainingWrites.delete(context.id)
  writingIds.value = remainingWrites
  if (!result.success || !result.data) {
    if (result.uncertain) {
      uncertainIds.value = new Set([...uncertainIds.value, context.id])
      message.warning('计划状态修改结果未知，请核对详情后再操作')
    } else {
      message.error(result.message || '计划状态修改失败')
    }
    return
  }
  const targetStateValid =
    context.action === 'pause'
      ? result.data.state === 'paused'
      : context.action === 'cancel'
        ? result.data.state === 'cancelled'
        : result.data.state === 'active' || result.data.state === 'ended'
  if (
    result.data.version <= context.version ||
    result.data.id !== context.id ||
    !targetStateValid
  ) {
    uncertainIds.value = new Set([...uncertainIds.value, context.id])
    message.warning('计划状态回执无法核实，请重新读取')
    return
  }
  replaceSchedule(result.data)
  emit('changed', result.data.id)
  message.success('计划状态已更新')
}

function replaceSchedule(schedule: TaskScheduleResponse) {
  const index = schedules.value.findIndex((item) => item.id === schedule.id)
  if (index >= 0) {
    schedules.value = schedules.value.map((item, itemIndex) =>
      itemIndex === index ? schedule : item,
    )
  }
  if (selectedSchedule.value?.id === schedule.id) selectedSchedule.value = schedule
}

async function refreshOne(scheduleId: string) {
  const actorId = authStore.user?.id?.trim()
  if (!actorId) return
  checkingId.value = scheduleId
  const result = await getTaskSchedule(scheduleId)
  if (!props.open || authStore.user?.id?.trim() !== actorId || checkingId.value !== scheduleId)
    return
  checkingId.value = null
  if (!result.success || !result.data) {
    message.error(result.message || '计划详情核对失败')
    return
  }
  replaceSchedule(result.data)
  const next = new Set(uncertainIds.value)
  next.delete(scheduleId)
  uncertainIds.value = next
}

async function openDetail(scheduleId: string) {
  const actorId = authStore.user?.id?.trim()
  const sequence = ++detailSequence
  detailOpen.value = true
  detailLoading.value = true
  detailError.value = ''
  selectedSchedule.value = null
  if (!actorId) return
  const result = await getTaskSchedule(scheduleId)
  if (sequence !== detailSequence || !detailOpen.value || authStore.user?.id?.trim() !== actorId)
    return
  detailLoading.value = false
  if (!result.success || !result.data) {
    detailError.value = result.message || '计划详情读取失败'
    return
  }
  selectedSchedule.value = result.data
}

function openRuns(schedule: TaskScheduleResponse) {
  runsSchedule.value = schedule
  runsOpen.value = true
}

function handleStateFilter() {
  page.value = 1
  void loadSchedules()
}

function resetCreateForm() {
  selectedSourceTaskId.value = props.sourceTaskId?.trim() || undefined
  sourceDetail.value = null
  sourceDetailError.value = ''
  timingKind.value = 'once'
  onceDate.value = null
  startDate.value = null
  endDate.value = null
  executionTime.value = dayjs().hour(9).minute(0).second(0)
  weekdays.value = []
  monthDay.value = 1
  if (selectedSourceTaskId.value) void loadSourceDetail(selectedSourceTaskId.value)
}

watch(
  [() => props.open, () => authStore.user?.id, () => props.sourceTaskId],
  ([open, actorId], [, previousActorId]) => {
    lifecycleSequence += 1
    listSequence += 1
    sourceListSequence += 1
    sourceDetailSequence += 1
    detailSequence += 1
    loading.value = false
    sourceListLoading.value = false
    sourceDetailLoading.value = false
    creating.value = false
    detailLoading.value = false
    detailOpen.value = false
    runsOpen.value = false
    selectedSchedule.value = null
    writingIds.value = new Set()
    schedules.value = []
    total.value = 0
    if (actorId !== previousActorId) {
      uncertainIds.value = new Set()
    }
    if (!open) return
    restoreCreateAttempt()
    viewMode.value = props.sourceTaskId ? 'create' : 'list'
    resetCreateForm()
    void loadSchedules()
    void loadSourceTasks()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  lifecycleSequence += 1
  listSequence += 1
  sourceListSequence += 1
  sourceDetailSequence += 1
  detailSequence += 1
})
</script>

<style scoped>
.schedule-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
}
.schedule-alert {
  margin-bottom: 16px;
}
.schedule-list {
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}
.schedule-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}
.schedule-summary {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: rgba(29, 29, 31, 0.6);
  text-align: left;
  cursor: pointer;
}
.schedule-title-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  color: #1d1d1f;
}
.schedule-title-line strong {
  font-size: 15px;
  font-weight: 600;
}
.schedule-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}
.schedule-pagination {
  margin-top: 18px;
  text-align: right;
}
.schedule-form section {
  padding: 18px 0 4px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}
.schedule-form h3 {
  margin: 0 0 14px;
  color: #1d1d1f;
  font-size: 17px;
  line-height: 22px;
  font-weight: 600;
}
.source-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 18px;
  margin: 6px 0 0;
}
.source-facts div {
  min-width: 0;
}
.source-facts dt {
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
}
.source-facts dd {
  margin: 3px 0 0;
  overflow-wrap: anywhere;
  color: #1d1d1f;
}
.timing-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.timezone-note {
  margin: -4px 0 14px;
  color: rgba(29, 29, 31, 0.6);
}
.field-note {
  display: block;
  margin-top: 6px;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
}
.create-actions,
.detail-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}
@media (max-width: 680px) {
  .schedule-row {
    grid-template-columns: 1fr;
  }
  .schedule-actions {
    justify-content: flex-start;
  }
  .source-facts,
  .timing-grid {
    grid-template-columns: 1fr;
  }
}
</style>
