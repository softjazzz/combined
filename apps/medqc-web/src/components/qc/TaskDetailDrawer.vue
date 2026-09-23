<template>
  <a-drawer
    :open="open"
    :width="drawerWidth"
    :title="drawerTitle"
    placement="right"
    class="task-detail-drawer"
    :body-style="{ padding: 0 }"
    @close="handleClose"
  >
    <div class="task-detail-drawer__body">
      <div
        v-if="loading"
        data-testid="task-detail-loading"
        class="task-detail-drawer__state"
        aria-live="polite"
      >
        <a-skeleton
          active
          :paragraph="{ rows: 8 }"
        />
      </div>

      <div
        v-else-if="error"
        data-testid="task-detail-error"
        class="task-detail-drawer__error"
        role="alert"
      >
        <div>
          <strong>任务详情暂不可用</strong>
          <span>{{ error }}</span>
        </div>
        <a-button
          data-testid="retry-task-detail"
          type="primary"
          ghost
          @click="void loadDetail()"
        >
          <RotateCw
            :size="15"
            aria-hidden="true"
          />
          重试
        </a-button>
      </div>

      <template v-else-if="detail">
        <section
          class="task-detail-drawer__summary"
          aria-labelledby="task-detail-summary-title"
        >
          <div class="task-detail-drawer__section-heading">
            <div>
              <span>全任务口径</span>
              <h3 id="task-detail-summary-title">
                任务信息
              </h3>
            </div>
            <a-tag :color="taskStatusColor(detail.status)">
              {{ taskStatusLabel(detail.status) }}
            </a-tag>
          </div>

          <dl class="task-detail-drawer__metadata">
            <div>
              <dt>任务编号</dt>
              <dd class="task-detail-drawer__breakable">
                {{ detail.task_number || '未记录' }}
              </dd>
            </div>
            <div>
              <dt>场景</dt>
              <dd>{{ sceneLabel(detail.scene) }}</dd>
            </div>
            <div v-if="detail.scene">
              <dt>规则集</dt>
              <dd class="task-detail-drawer__breakable">
                {{ detail.rule_set_key || '未选择' }}
              </dd>
            </div>
            <div>
              <dt>创建人</dt>
              <dd>{{ detail.creator_name || '未记录' }}</dd>
            </div>
            <div>
              <dt>任务类型</dt>
              <dd>{{ detail.task_type === 'one_time' ? '单次任务' : detail.task_type === 'scheduled' ? '定时任务' : '未知' }}</dd>
            </div>
            <div>
              <dt>创建时间</dt>
              <dd>{{ formatDate(detail.created_at) }}</dd>
            </div>
            <div>
              <dt>截止时间</dt>
              <dd>{{ formatDate(detail.deadline) }}</dd>
            </div>
            <div>
              <dt>全任务病历</dt>
              <dd>{{ formatNumber(detail.total_records) }}</dd>
            </div>
            <div>
              <dt>全任务进度</dt>
              <dd>{{ formatPercent(detail.progress) }}</dd>
            </div>
          </dl>
        </section>

        <section
          v-if="isModernTask"
          class="task-detail-drawer__runs"
          aria-labelledby="task-detail-runs-title"
        >
          <div class="task-detail-drawer__section-heading">
            <div>
              <span>按运行批次查看</span>
              <h3 id="task-detail-runs-title">
                质控运行
              </h3>
            </div>
            <a-button
              v-if="canStartRun"
              data-testid="task-start-qc-run"
              type="primary"
              :loading="startingRun"
              @click="void startRun()"
            >
              <Play
                :size="15"
                aria-hidden="true"
              />
              {{ runs.length ? '重新质控' : '启动质控' }}
            </a-button>
          </div>
          <template v-if="canViewRuns">
            <p
              v-if="runsLoading"
              class="task-detail-drawer__muted"
            >
              正在读取运行历史…
            </p>
            <div
              v-else-if="runsError"
              class="task-detail-drawer__run-error"
              role="alert"
            >
              {{ runsError }}
              <a-button
                size="small"
                @click="void loadRuns()"
              >
                重试
              </a-button>
            </div>
            <p
              v-else-if="!runs.length"
              class="task-detail-drawer__muted"
            >
              暂无质控运行
            </p>
            <div
              v-else
              class="task-detail-drawer__run-list"
            >
              <div
                v-for="run in runs"
                :key="run.job_id"
                class="task-detail-drawer__run-row"
              >
                <div>
                  <strong>第 {{ run.run_number }} 次运行</strong>
                  <span>{{ formatDate(run.created_at) }}</span>
                </div>
                <a-button
                  size="small"
                  :data-testid="`task-run-${run.run_number}`"
                  @click="void selectRun(run.job_id)"
                >
                  查看结果
                </a-button>
              </div>
            </div>
            <div
              v-if="selectedJobId"
              class="task-detail-drawer__job"
              data-testid="task-qc-job"
            >
              <div class="task-detail-drawer__job-heading">
                <strong>运行结果</strong>
                <a-button
                  size="small"
                  :loading="jobLoading"
                  @click="void loadJob(selectedJobId)"
                >
                  <RotateCw
                    :size="14"
                    aria-hidden="true"
                  />刷新
                </a-button>
              </div>
              <p
                v-if="jobLoading"
                class="task-detail-drawer__muted"
              >
                正在读取作业状态…
              </p>
              <p
                v-else-if="jobError"
                class="task-detail-drawer__run-error"
                role="alert"
              >
                {{ jobError }}
              </p>
              <template v-else-if="selectedJob">
                <a-tag :color="jobStatusColor(selectedJob.status)">
                  {{ jobStatusLabel(selectedJob.status) }}
                </a-tag>
                <span class="task-detail-drawer__job-id">作业 {{ selectedJob.id }}</span>
                <dl class="task-detail-drawer__job-metrics">
                  <div><dt>病历</dt><dd>{{ formatNumber(selectedJob.summary?.total_records ?? selectedJob.total_records) }}</dd></div>
                  <div><dt>成功</dt><dd>{{ formatNumber(selectedJob.summary?.success_count ?? selectedJob.success_count) }}</dd></div>
                  <div><dt>失败</dt><dd>{{ formatNumber(selectedJob.summary?.failed_count ?? selectedJob.failed_count) }}</dd></div>
                  <div><dt>有问题</dt><dd>{{ formatNumber(selectedJob.summary?.issue_records ?? selectedJob.issue_records) }}</dd></div>
                </dl>
                <p
                  v-if="selectedJob.error_message"
                  class="task-detail-drawer__run-error"
                >
                  {{ selectedJob.error_message }}
                </p>
              </template>
            </div>
          </template>
          <p
            v-else
            class="task-detail-drawer__muted"
          >
            当前范围没有可查看的运行历史
          </p>
          <p
            v-if="!canStartRun && canViewRuns && !runsLoading && !runsError && runUnavailableReason"
            class="task-detail-drawer__muted"
          >
            {{ runUnavailableReason }}
          </p>
        </section>

        <section
          class="task-detail-drawer__records"
          aria-labelledby="task-detail-records-title"
        >
          <div class="task-detail-drawer__section-heading task-detail-drawer__records-heading">
            <div>
              <span>{{ scopeLabel }}</span>
              <h3 id="task-detail-records-title">
                病历清单
              </h3>
            </div>
            <strong data-testid="task-detail-record-count">{{ detail.records.length }} 份</strong>
          </div>

          <div class="task-detail-drawer__filters">
            <a-input
              v-model:value="keyword"
              data-testid="task-detail-keyword"
              allow-clear
              placeholder="搜索机构、患者、就诊、病历号或质控员"
            />
            <a-select
              v-model:value="recordStatus"
              data-testid="task-detail-status"
              allow-clear
              placeholder="全部处理状态"
              :options="recordStatusOptions"
              popup-class-name="task-detail-status-popup"
            />
          </div>

          <a-table
            v-if="filteredRecords.length"
            data-testid="task-detail-record-table"
            :columns="recordColumns"
            :data-source="filteredRecords"
            :pagination="recordPagination"
            :scroll="{ x: 860 }"
            row-key="id"
            size="small"
            @change="handleTableChange"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'caseIdentity'">
                <div
                  v-if="hasCaseIdentity(record)"
                  class="task-detail-drawer__case-identity"
                >
                  <div><span>机构</span><strong>{{ record.institute_id }}</strong></div>
                  <div><span>患者</span><strong>{{ record.patient_id }}</strong></div>
                  <div><span>就诊</span><strong>{{ record.visit_id }}</strong></div>
                </div>
                <span
                  v-else
                  class="task-detail-drawer__missing-identity"
                >未记录病例坐标</span>
                <div
                  v-if="canDisplayLegacyRecordId(record)"
                  class="task-detail-drawer__legacy-id"
                >
                  历史病历号：<span class="task-detail-drawer__record-id">{{ record.record_id || '未记录' }}</span>
                </div>
              </template>
              <template v-else-if="column.key === 'assignee'">
                {{ assigneeLabel(record) }}
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag :color="recordStatusColor(record.status)">
                  {{ recordStatusLabel(record.status) }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'score'">
                {{ formatNumber(record.score) }}
              </template>
              <template v-else-if="column.key === 'defects'">
                {{ formatNumber(record.defect_count) }}
              </template>
              <template v-else-if="column.key === 'completedAt'">
                {{ formatDate(record.completed_at) }}
              </template>
            </template>
          </a-table>

          <a-empty
            v-else
            data-testid="task-detail-record-empty"
            :description="detail.records.length ? '没有符合筛选条件的病历' : emptyDescription"
          />
        </section>
      </template>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { TableColumnsType, TablePaginationConfig } from 'ant-design-vue'
import { Play, RotateCw } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { getSichuanWorkspaceBatchJob } from '@/services/sichuan-rule-workspace-service'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'
import { createTaskQcRun, getTaskDetail, getTaskQcRuns } from '@/api/tasks'
import type {
  TaskDetail,
  TaskQcRun,
  TaskQcRunScope,
  TaskRecordItem,
  TaskScene,
  TaskStatus,
  TaskTab,
} from '@/api/tasks'

const props = defineProps<{
  open: boolean
  taskId?: string | null
  tab: TaskTab
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const detail = ref<TaskDetail | null>(null)
const authStore = useAuthStore()
const runs = ref<TaskQcRun[]>([])
const runsLoading = ref(false)
const runsError = ref('')
const startingRun = ref(false)
const selectedJobId = ref('')
const selectedJob = ref<SichuanBatchJob | null>(null)
const jobLoading = ref(false)
const jobError = ref('')
const loading = ref(false)
const error = ref('')
const keyword = ref('')
const recordStatus = ref<string | undefined>()
const page = ref(1)
const pageSize = ref(10)
let requestSequence = 0
let runSequence = 0
let jobSequence = 0

const drawerWidth = 'min(820px, 100vw)'
const drawerTitle = computed(() => detail.value?.task_name || '任务详情')
const scopeLabel = computed(() => (props.tab === 'received' ? '我的病历' : '任务病历'))
const emptyDescription = computed(() =>
  props.tab === 'received' ? '当前任务没有分配给我的病历' : '当前任务暂无病历',
)
const isModernTask = computed(() => !!detail.value?.scene)
const isCreator = computed(() => !!authStore.user?.id && authStore.user.id === detail.value?.creator_id)
const runScope = computed<TaskQcRunScope | null>(() => {
  if (props.tab === 'received') return authStore.user?.id ? 'assigned' : null
  if ((props.tab === 'created' || props.tab === 'all') && isCreator.value) return 'all'
  return null
})
const canViewRuns = computed(() => isModernTask.value && !!runScope.value)
const canStartRun = computed(() => canViewRuns.value
  && (detail.value?.scene === 'running' || detail.value?.scene === 'final')
  && !!detail.value.rule_set_key
  && (runScope.value === 'assigned'
    ? detail.value.records.some((record) => record.assignee_id === authStore.user?.id)
    : detail.value.total_records > 0)
  && (runScope.value === 'assigned'
    ? ['assigned', 'in_progress', 'completed'].includes(detail.value.status)
    : ['sampling', 'assigned', 'in_progress', 'completed'].includes(detail.value.status))
  && !runsLoading.value
  && !runsError.value
  && !startingRun.value
  && !jobLoading.value
  && (!runs.value.length || selectedJobId.value === runs.value[0]?.job_id)
  && (!runs.value.length || !!selectedJob.value)
  && selectedJob.value?.status !== 'queued'
  && selectedJob.value?.status !== 'running')
const runUnavailableReason = computed(() => {
  if (detail.value?.scene === 'outpatient') return '门急诊场景质控执行尚未接入'
  if (!detail.value?.rule_set_key) return '未选择规则集，无法执行质控'
  if (runScope.value === 'assigned' && !detail.value.records.some((record) => record.assignee_id === authStore.user?.id)) return '当前任务没有分配给我的病历'
  if (!detail.value.total_records) return '请先完成病历抽样'
  if (!['sampling', 'assigned', 'in_progress', 'completed'].includes(detail.value.status)
    || (runScope.value === 'assigned' && detail.value.status === 'sampling')) return '当前任务状态不可执行质控'
  if (selectedJob.value?.status === 'queued' || selectedJob.value?.status === 'running') return '当前质控运行中'
  return ''
})

const recordStatusOptions = [
  { label: '未处理', value: 'pending' },
  { label: '处理中', value: 'in_progress' },
  { label: '已完成', value: 'completed' },
  { label: '已跳过', value: 'skipped' },
]

const recordColumns: TableColumnsType<TaskRecordItem> = [
  { title: '病例身份', key: 'caseIdentity', width: 290 },
  { title: '质控员', dataIndex: 'assignee_name', key: 'assignee', width: 150 },
  { title: '处理状态', dataIndex: 'status', key: 'status', width: 110 },
  { title: '评分', dataIndex: 'score', key: 'score', width: 90 },
  { title: '缺陷数', dataIndex: 'defect_count', key: 'defects', width: 90 },
  { title: '完成时间', dataIndex: 'completed_at', key: 'completedAt', width: 160 },
]

const filteredRecords = computed(() => {
  if (!detail.value) return []
  const normalizedKeyword = keyword.value.trim().toLocaleLowerCase()
  return detail.value.records.filter((record) => {
    if (recordStatus.value && record.status !== recordStatus.value) return false
    if (!normalizedKeyword) return true
    const coordinates = hasCaseIdentity(record)
      ? [record.institute_id, record.patient_id, record.visit_id]
      : []
    const legacyIds = canDisplayLegacyRecordId(record) ? [record.record_id] : []
    return [record.assignee_name, record.assignee_id, ...coordinates, ...legacyIds]
      .some((value) => String(value || '').toLocaleLowerCase().includes(normalizedKeyword))
  })
})

const recordPagination = computed(() => ({
  current: page.value,
  pageSize: pageSize.value,
  total: filteredRecords.value.length,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 份`,
}))

function resetFilters() {
  keyword.value = ''
  recordStatus.value = undefined
  page.value = 1
}

function clearDetail() {
  requestSequence += 1
  runSequence += 1
  jobSequence += 1
  detail.value = null
  runs.value = []
  runsLoading.value = false
  runsError.value = ''
  startingRun.value = false
  selectedJobId.value = ''
  selectedJob.value = null
  jobLoading.value = false
  jobError.value = ''
  loading.value = false
  error.value = ''
  resetFilters()
}

async function loadDetail() {
  const taskId = String(props.taskId || '').trim()
  if (!props.open || !taskId) {
    clearDetail()
    return
  }

  const tab = props.tab
  const currentSequence = ++requestSequence
  runSequence += 1
  jobSequence += 1
  detail.value = null
  runs.value = []
  runsLoading.value = false
  selectedJobId.value = ''
  selectedJob.value = null
  jobLoading.value = false
  startingRun.value = false
  runsError.value = ''
  jobError.value = ''
  error.value = ''
  loading.value = true
  resetFilters()
  try {
    const response = await getTaskDetail(taskId, { tab })
    if (currentSequence !== requestSequence || !props.open) return
    if (String(props.taskId || '').trim() !== taskId || props.tab !== tab) return
    if (
      response.success
      && response.data
      && response.data.id === taskId
      && Array.isArray(response.data.records)
    ) {
      detail.value = response.data
      if (response.data.scene && runScope.value) {
        void loadRuns()
      }
    } else {
      error.value = response.success && response.data?.id !== taskId
        ? '任务详情身份校验失败，请重试'
        : response.message || '获取任务详情失败'
    }
  } catch {
    if (currentSequence !== requestSequence || !props.open) return
    error.value = '网络异常或服务器不可用'
  } finally {
    if (currentSequence === requestSequence) loading.value = false
  }
}

async function loadRuns() {
  const taskId = detail.value?.id
  const scope = runScope.value
  if (!taskId || !scope) return
  const detailSequence = requestSequence
  const sequence = ++runSequence
  jobSequence += 1
  runs.value = []
  selectedJobId.value = ''
  selectedJob.value = null
  jobLoading.value = false
  jobError.value = ''
  runsLoading.value = true
  runsError.value = ''
  try {
    const response = await getTaskQcRuns(taskId, scope)
    if (sequence !== runSequence || detailSequence !== requestSequence || detail.value?.id !== taskId || runScope.value !== scope || !props.open) return
    if (!response.success || !Array.isArray(response.data)) {
      runsError.value = response.message || '获取运行历史失败'
      return
    }
    runs.value = response.data.filter((run) => run.task_id === taskId && run.run_scope === scope && !!run.job_id)
      .sort((a, b) => b.run_number - a.run_number)
    if (runs.value.length) void selectRun(runs.value[0]!.job_id)
  } catch {
    if (sequence === runSequence && detailSequence === requestSequence && detail.value?.id === taskId && runScope.value === scope) runsError.value = '网络异常或服务器不可用'
  } finally {
    if (sequence === runSequence && detailSequence === requestSequence) runsLoading.value = false
  }
}

async function selectRun(jobId: string) {
  if (!runs.value.some((run) => run.job_id === jobId)) return
  selectedJobId.value = jobId
  await loadJob(jobId)
}

async function loadJob(jobId: string) {
  const taskId = detail.value?.id
  if (!taskId || selectedJobId.value !== jobId) return
  const scope = runScope.value
  const detailSequence = requestSequence
  const sequence = ++jobSequence
  selectedJob.value = null
  jobError.value = ''
  jobLoading.value = true
  try {
    const response = await getSichuanWorkspaceBatchJob(jobId)
    if (sequence !== jobSequence || detailSequence !== requestSequence || detail.value?.id !== taskId || runScope.value !== scope || selectedJobId.value !== jobId || !props.open) return
    if (response.success && response.data?.id === jobId) selectedJob.value = response.data
    else jobError.value = response.message || '获取运行结果失败'
  } catch {
    if (sequence === jobSequence && detailSequence === requestSequence && detail.value?.id === taskId && runScope.value === scope) jobError.value = '网络异常或服务器不可用'
  } finally {
    if (sequence === jobSequence && detailSequence === requestSequence) jobLoading.value = false
  }
}

async function startRun() {
  const taskId = detail.value?.id
  const scope = runScope.value
  if (!taskId || !scope || !canStartRun.value) return
  const detailSequence = requestSequence
  startingRun.value = true
  try {
    const response = await createTaskQcRun(taskId, scope)
    if (!props.open || detailSequence !== requestSequence || detail.value?.id !== taskId || runScope.value !== scope) return
    if (!response.success || !response.data?.job_id || response.data.task_id !== taskId || response.data.run_scope !== scope) {
      runsError.value = response.message || '启动质控失败'
      return
    }
    await loadRuns()
  } catch {
    if (detailSequence === requestSequence && detail.value?.id === taskId && runScope.value === scope) runsError.value = '网络异常或服务器不可用'
  } finally {
    if (detailSequence === requestSequence && detail.value?.id === taskId && runScope.value === scope) startingRun.value = false
  }
}

function jobStatusLabel(status: SichuanBatchJob['status']) {
  return { queued: '作业排队中', running: '作业运行中', completed: '作业已完成', failed: '作业失败', canceled: '作业已取消' }[status] || '作业状态未知'
}

function jobStatusColor(status: SichuanBatchJob['status']) {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'running') return 'processing'
  return 'default'
}

function handleClose() {
  clearDetail()
  emit('update:open', false)
}

function handleTableChange(pagination: TablePaginationConfig) {
  page.value = pagination.current || 1
  pageSize.value = pagination.pageSize || 10
}

function formatNumber(value: number | null | undefined) {
  return value === null || value === undefined ? '未记录' : String(value)
}

function formatPercent(value: number | null | undefined) {
  return value === null || value === undefined ? '未记录' : `${value}%`
}

function formatDate(value: string | null | undefined) {
  if (!value) return '未记录'
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value
  const timestamp = Date.parse(value)
  return Number.isNaN(timestamp) ? value : new Date(timestamp).toLocaleString('zh-CN', { hour12: false })
}

function sceneLabel(scene?: TaskScene | null) {
  if (scene === 'running') return '运行'
  if (scene === 'final') return '终末'
  if (scene === 'outpatient') return '门急诊'
  return '未标注'
}

function taskStatusLabel(status: TaskStatus | string | null | undefined) {
  const labels: Record<TaskStatus, string> = {
    draft: '草稿',
    sampling: '抽样中',
    assigned: '已分配',
    in_progress: '进行中',
    completed: '已完成',
    cancelled: '已取消',
  }
  return status && Object.prototype.hasOwnProperty.call(labels, status) ? labels[status as TaskStatus] : '未知'
}

function taskStatusColor(status: TaskStatus | string | null | undefined) {
  if (status === 'completed') return 'success'
  if (status === 'cancelled') return 'error'
  if (status === 'in_progress') return 'processing'
  if (status === 'assigned') return 'warning'
  return 'default'
}

function recordStatusLabel(status: string | null | undefined) {
  const labels: Record<string, string> = {
    pending: '未处理',
    in_progress: '处理中',
    completed: '已完成',
    skipped: '已跳过',
  }
  return status && Object.prototype.hasOwnProperty.call(labels, status) ? labels[status] : '未知'
}

function recordStatusColor(status: string | null | undefined) {
  if (status === 'completed') return 'success'
  if (status === 'in_progress') return 'processing'
  if (status === 'pending') return 'warning'
  return 'default'
}

function assigneeLabel(record: {
  assignee_id?: string | null
  assignee_name?: string | null
}) {
  if (record.assignee_name) return record.assignee_name
  if (record.assignee_id) return `${record.assignee_id}（姓名未记录）`
  return '未分配'
}

function hasCaseIdentity(record: Pick<TaskRecordItem, 'institute_id' | 'patient_id' | 'visit_id'>) {
  return [record.institute_id, record.patient_id, record.visit_id]
    .every((value) => typeof value === 'string' && value.trim().length > 0)
}

function canDisplayLegacyRecordId(record: Pick<TaskRecordItem, 'institute_id' | 'patient_id' | 'visit_id'>) {
  return detail.value?.scene == null
    && [record.institute_id, record.patient_id, record.visit_id].every((value) => value == null)
}

watch([() => props.open, () => props.taskId, () => props.tab], ([open, taskId]) => {
  if (!open || !String(taskId || '').trim()) {
    clearDetail()
    return
  }
  void loadDetail()
}, { immediate: true })

watch([keyword, recordStatus], () => {
  page.value = 1
})
</script>

<style scoped>
.task-detail-drawer__body {
  min-height: 100%;
  background: #f5f5f7;
  color: #1d1d1f;
  font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', 'PingFang SC', sans-serif;
}

.task-detail-drawer__state,
.task-detail-drawer__error {
  margin: 20px;
}

.task-detail-drawer__error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 8px;
  background: #fff;
  color: #b42318;
}

.task-detail-drawer__error div,
.task-detail-drawer__error button {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-detail-drawer__error div {
  align-items: flex-start;
  flex-direction: column;
}

.task-detail-drawer__summary,
.task-detail-drawer__runs,
.task-detail-drawer__records {
  padding: 20px;
  background: #fff;
}

.task-detail-drawer__summary {
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.task-detail-drawer__records {
  margin-top: 10px;
}
.task-detail-drawer__runs {
  margin-top: 10px;
}
.task-detail-drawer__run-list {
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}
.task-detail-drawer__run-row,
.task-detail-drawer__job-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.task-detail-drawer__run-row {
  min-height: 56px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}
.task-detail-drawer__run-row div {
  display: grid;
  gap: 2px;
}
.task-detail-drawer__run-row span,
.task-detail-drawer__muted,
.task-detail-drawer__job-id {
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
}
.task-detail-drawer__job {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}
.task-detail-drawer__job-heading {
  margin-bottom: 10px;
}
.task-detail-drawer__job-id {
  margin-left: 8px;
  overflow-wrap: anywhere;
}
.task-detail-drawer__job-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 12px 0 0;
}
.task-detail-drawer__job-metrics dt { color: rgba(29, 29, 31, 0.6); font-size: 13px; }
.task-detail-drawer__job-metrics dd { margin: 2px 0 0; font-weight: 600; }
.task-detail-drawer__run-error { color: #b42318; }

.task-detail-drawer__section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.task-detail-drawer__section-heading span {
  color: rgba(29, 29, 31, 0.55);
  font-size: 12px;
  line-height: 18px;
}

.task-detail-drawer__section-heading h3 {
  margin: 1px 0 0;
  font-size: 17px;
  line-height: 22px;
  font-weight: 600;
  letter-spacing: 0;
}

.task-detail-drawer__records-heading strong {
  color: #007aff;
  font-size: 14px;
}

.task-detail-drawer__metadata {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px 18px;
  margin: 0;
}

.task-detail-drawer__metadata div {
  min-width: 0;
}

.task-detail-drawer__metadata dt {
  color: rgba(29, 29, 31, 0.55);
  font-size: 13px;
  line-height: 20px;
}

.task-detail-drawer__metadata dd {
  margin: 3px 0 0;
  color: #1d1d1f;
  font-size: 14px;
  line-height: 22px;
  font-weight: 500;
}

.task-detail-drawer__breakable,
.task-detail-drawer__record-id,
.task-detail-drawer__case-identity strong {
  overflow-wrap: anywhere;
  word-break: break-word;
}

.task-detail-drawer__filters {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(160px, 220px);
  gap: 10px;
  margin-bottom: 14px;
}

.task-detail-drawer__record-id {
  display: inline-block;
  color: #1d1d1f;
}

.task-detail-drawer__case-identity {
  display: grid;
  gap: 2px;
}

.task-detail-drawer__case-identity div {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 6px;
  min-width: 0;
}

.task-detail-drawer__case-identity span,
.task-detail-drawer__legacy-id,
.task-detail-drawer__missing-identity {
  color: rgba(29, 29, 31, 0.6);
}

.task-detail-drawer__case-identity strong {
  min-width: 0;
  font-weight: 500;
}

.task-detail-drawer__legacy-id {
  margin-top: 4px;
  font-size: 12px;
  line-height: 18px;
}

@media (max-width: 640px) {
  .task-detail-drawer__summary,
  .task-detail-drawer__runs,
  .task-detail-drawer__records {
    padding: 16px;
  }

  .task-detail-drawer__metadata {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .task-detail-drawer__job-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .task-detail-drawer__filters {
    grid-template-columns: minmax(0, 1fr);
  }

  .task-detail-drawer__error {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
