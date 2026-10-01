<template>
  <a-drawer
    v-model:open="visible"
    title="编辑质控任务"
    :width="'min(720px, 100vw)'"
    :body-style="{ padding: '20px 24px' }"
    :destroy-on-close="true"
    @close="closeDrawer"
  >
    <a-spin :spinning="loading">
      <a-alert v-if="loadError" type="error" show-icon :message="loadError" class="task-edit-alert">
        <template #action>
          <a-button size="small" @click="void refresh()"> <ReloadOutlined /> 重新读取 </a-button>
        </template>
      </a-alert>

      <a-alert
        v-if="refreshRequired"
        type="warning"
        show-icon
        message="上次保存结果无法确认，请刷新任务后再继续编辑。"
        class="task-edit-alert"
      >
        <template #action>
          <a-button size="small" @click="void refresh()"> <ReloadOutlined /> 刷新任务 </a-button>
        </template>
      </a-alert>

      <template v-if="detail">
        <a-descriptions bordered size="small" :column="2" class="task-edit-summary">
          <a-descriptions-item label="任务编号">
            {{ detail.task_number }}
          </a-descriptions-item>
          <a-descriptions-item label="任务状态">
            {{ statusLabel }}
          </a-descriptions-item>
          <a-descriptions-item label="质控场景">
            {{ sceneLabel }}
          </a-descriptions-item>
          <a-descriptions-item label="任务类型">
            {{ taskTypeLabel }}
          </a-descriptions-item>
          <a-descriptions-item label="规则集">
            {{ detail.rule_set_key || '未标注' }}
          </a-descriptions-item>
          <a-descriptions-item label="规则版本">
            {{ detail.rule_set_version || '未标注' }}
          </a-descriptions-item>
        </a-descriptions>

        <a-alert
          v-if="!hasEditableFields"
          type="info"
          show-icon
          message="当前任务状态不允许修改。"
          class="task-edit-alert"
        />
        <a-alert
          v-else-if="!fullConfigurationEditable"
          type="info"
          show-icon
          message="任务已进入处理流程，仅可修改任务名称和截止日期。"
          class="task-edit-alert"
        />

        <a-form layout="vertical" class="task-edit-form">
          <section aria-labelledby="task-edit-basic-title">
            <h3 id="task-edit-basic-title">基本信息</h3>
            <a-form-item label="任务名称" required>
              <a-input
                v-model:value="form.task_name"
                :disabled="!canEdit('task_name') || saving || refreshRequired"
                :maxlength="200"
                show-count
              />
            </a-form-item>
            <a-form-item label="截止日期">
              <a-date-picker
                v-model:value="form.deadline"
                :disabled="!canEdit('deadline') || saving || refreshRequired"
                style="width: 100%"
                placeholder="不设置截止日期"
                @change="deadlineTouched = true"
              />
              <p v-if="detail.deadline && !deadlineTouched" class="field-source-value">
                当前值：{{ detail.deadline }}
              </p>
            </a-form-item>
          </section>

          <template v-if="fullConfigurationEditable">
            <section aria-labelledby="task-edit-range-title">
              <h3 id="task-edit-range-title">病历范围</h3>
              <a-form-item label="选择方式">
                <a-radio-group v-model:value="rangeMode" :disabled="saving || refreshRequired">
                  <a-radio value="date">按日期范围</a-radio>
                  <a-radio value="refs">指定病历</a-radio>
                </a-radio-group>
              </a-form-item>
              <template v-if="rangeMode === 'date'">
                <a-form-item
                  :label="form.scene === 'final' ? '出院日期范围' : '日期范围'"
                  :required="form.scene === 'final'"
                >
                  <a-range-picker
                    v-model:value="form.dateRange"
                    style="width: 100%"
                    :disabled="saving || refreshRequired"
                    @change="dateRangeTouched = true"
                  />
                </a-form-item>
                <a-form-item label="科室筛选">
                  <a-select
                    v-model:value="form.department_filter"
                    mode="tags"
                    :disabled="saving || refreshRequired"
                    placeholder="不选则包含全部科室"
                  />
                </a-form-item>
                <TaskScoreFilterFields
                  v-model="scoreFilter"
                  :scene="form.scene"
                  :disabled="saving || refreshRequired"
                />
                <TaskClinicalDoctorFields
                  v-model="clinicalDoctors"
                  :scene="form.scene"
                  :disabled="saving || refreshRequired"
                />
              </template>
              <template v-else>
                <a-form-item v-if="form.scene === 'final'" label="出院日期范围" required>
                  <a-range-picker
                    v-model:value="form.dateRange"
                    data-testid="task-edit-refs-discharge-range"
                    style="width: 100%"
                    :disabled="saving || refreshRequired"
                    @change="dateRangeTouched = true"
                  />
                </a-form-item>
                <a-form-item label="病历坐标" required>
                  <div class="record-ref-heading" aria-hidden="true">
                    <span>机构 ID</span><span>患者 ID</span><span>就诊 ID</span><span />
                  </div>
                  <div v-for="(recordRef, index) in recordRefs" :key="index" class="record-ref-row">
                    <a-input
                      v-model:value="recordRef.institute_id"
                      :disabled="saving || refreshRequired"
                      :aria-label="`第 ${index + 1} 条机构 ID`"
                      placeholder="机构 ID"
                    />
                    <a-input
                      v-model:value="recordRef.patient_id"
                      :disabled="saving || refreshRequired"
                      :aria-label="`第 ${index + 1} 条患者 ID`"
                      placeholder="患者 ID"
                    />
                    <a-input
                      v-model:value="recordRef.visit_id"
                      :disabled="saving || refreshRequired"
                      :aria-label="`第 ${index + 1} 条就诊 ID`"
                      placeholder="就诊 ID"
                    />
                    <a-button
                      :disabled="saving || refreshRequired || recordRefs.length === 1"
                      :aria-label="`删除第 ${index + 1} 条病历`"
                      title="删除病历"
                      @click="removeRecordRef(index)"
                    >
                      <DeleteOutlined />
                    </a-button>
                  </div>
                  <a-button :disabled="saving || refreshRequired" @click="addRecordRef">
                    <PlusOutlined /> 添加病历
                  </a-button>
                </a-form-item>
              </template>
            </section>

            <section aria-labelledby="task-edit-sampling-title">
              <h3 id="task-edit-sampling-title">抽样规则</h3>
              <a-form-item label="抽样方式">
                <a-radio-group
                  v-model:value="form.sampling_method"
                  :disabled="saving || refreshRequired || rangeMode === 'refs'"
                >
                  <a-radio value="all">全部</a-radio>
                  <a-radio value="count">按数量</a-radio>
                  <a-radio value="percentage">按比例</a-radio>
                  <a-radio value="department_count">每科室定额</a-radio>
                  <a-radio value="department_ratio">每科室比例</a-radio>
                </a-radio-group>
              </a-form-item>
              <template
                v-if="
                  form.sampling_method === 'count' || form.sampling_method === 'department_count'
                "
              >
                <a-form-item
                  :label="
                    form.sampling_method === 'department_count' ? '每科室固定份数' : '抽样数量'
                  "
                  required
                >
                  <a-input-number
                    v-model:value="form.total"
                    :min="1"
                    :max="10000"
                    :disabled="saving || refreshRequired"
                    style="width: 100%"
                  />
                </a-form-item>
                <a-form-item v-if="form.sampling_method === 'count'">
                  <a-checkbox
                    v-model:checked="form.by_department"
                    :disabled="saving || refreshRequired"
                  >
                    按科室均匀分配抽样数量
                  </a-checkbox>
                </a-form-item>
              </template>
              <template
                v-else-if="
                  form.sampling_method === 'percentage' ||
                  form.sampling_method === 'department_ratio'
                "
              >
                <a-form-item label="抽样比例" required>
                  <a-slider
                    v-model:value="form.percentage"
                    :min="1"
                    :max="100"
                    :disabled="saving || refreshRequired"
                  />
                  <p class="sampling-value">{{ form.percentage }}%</p>
                </a-form-item>
                <a-form-item
                  v-if="form.sampling_method === 'department_ratio'"
                  label="每科室最多份数"
                  required
                >
                  <a-input-number
                    v-model:value="form.max_per_group"
                    :min="1"
                    :max="10000"
                    :disabled="saving || refreshRequired"
                    style="width: 100%"
                  />
                </a-form-item>
                <a-form-item v-else label="分组依据">
                  <a-select
                    v-model:value="form.group_by"
                    allow-clear
                    :disabled="saving || refreshRequired"
                    :options="[{ value: 'department', label: '按科室' }]"
                  />
                </a-form-item>
              </template>
            </section>

            <section aria-labelledby="task-edit-assignment-title">
              <h3 id="task-edit-assignment-title">任务分配</h3>
              <a-form-item label="分配方式">
                <a-radio-group
                  v-model:value="form.assign_method"
                  :disabled="saving || refreshRequired"
                >
                  <a-radio value="by_ratio">按比例均分</a-radio>
                  <a-radio value="by_original_reviewer">原质控员</a-radio>
                  <a-radio value="by_department">按科室</a-radio>
                </a-radio-group>
              </a-form-item>
              <a-form-item
                v-if="form.assign_method === 'by_original_reviewer'"
                label="无原质控员时"
                required
              >
                <a-radio-group v-model:value="form.fallback" :disabled="saving || refreshRequired">
                  <a-radio value="by_ratio">按比例分配</a-radio>
                  <a-radio value="reject">拒绝分配</a-radio>
                </a-radio-group>
              </a-form-item>
            </section>
          </template>
        </a-form>
      </template>
    </a-spin>

    <template #footer>
      <div class="task-edit-footer">
        <a-button :disabled="saving" @click="closeDrawer">取消</a-button>
        <a-button
          type="primary"
          :loading="saving"
          :disabled="!detail || !hasEditableFields || refreshRequired || loading"
          data-testid="save-task-edit"
          @click="confirmSave"
        >
          <SaveOutlined /> 保存修改
        </a-button>
      </div>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { Modal, message } from 'ant-design-vue'
import { DeleteOutlined, PlusOutlined, ReloadOutlined, SaveOutlined } from '@ant-design/icons-vue'
import dayjs, { type Dayjs } from 'dayjs'
import { dischargedDateRangeError } from '@/utils/taskCaseScope'
import { useAuthStore } from '@/stores/auth'
import {
  getTaskEdit,
  updateTaskDraftConfiguration,
  updateTaskMetadata,
  type TaskDraftConfigurationUpdate,
  type TaskEditCaseRef,
  type TaskEditDetail,
  type TaskEditableAssignMethod,
  type TaskEditField,
  type TaskEditResult,
  type TaskEditSamplingMethod,
  type TaskMetadataUpdate,
} from '@/api/taskEdits'

import TaskScoreFilterFields from './TaskScoreFilterFields.vue'
import TaskClinicalDoctorFields from './TaskClinicalDoctorFields.vue'
import type { TaskClinicalDoctorRef } from '@/api/tasks'
import type { TaskScoreFilter } from '@/api/tasks'

const scoreFilter = ref<TaskScoreFilter | undefined>()
const clinicalDoctors = ref<TaskClinicalDoctorRef[] | undefined>()
const props = defineProps<{ open: boolean; taskId: string | null }>()
const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
  (event: 'saved', taskId: string): void
}>()

const authStore = useAuthStore()
const visible = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})
const detail = ref<TaskEditDetail | null>(null)
const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const refreshRequired = ref(false)
const rangeMode = ref<'date' | 'refs'>('date')
const recordRefs = ref<TaskEditCaseRef[]>([blankRecordRef()])
const dateRangeTouched = ref(false)
const deadlineTouched = ref(false)
const planningBaseline = ref('')
let requestSequence = 0

const form = reactive({
  task_name: '',
  scene: null as TaskEditDetail['scene'],
  rule_set_key: '',
  deadline: null as Dayjs | null,
  dateRange: null as [Dayjs, Dayjs] | null,
  department_filter: [] as string[],
  sampling_method: null as TaskEditSamplingMethod | null,
  total: 1,
  percentage: 10,
  by_department: false,
  max_per_group: 50,
  group_by: undefined as 'department' | undefined,
  assign_method: null as TaskEditableAssignMethod | null,
  fallback: undefined as 'by_ratio' | 'reject' | undefined,
})

const hasEditableFields = computed(() => !!detail.value?.editable_fields.length)
const fullConfigurationEditable = computed(
  () =>
    !!detail.value?.editable_fields.some(
      (field) => !(['task_name', 'deadline'] as TaskEditField[]).includes(field),
    ),
)
const sceneLabel = computed(() =>
  detail.value?.scene
    ? { running: '运行病历', final: '终末病历', outpatient: '门急诊病历' }[detail.value.scene]
    : '未标注',
)
const taskTypeLabel = computed(
  () =>
    ({ one_time: '单次任务', scheduled: '定期任务' })[detail.value?.task_type || ''] ||
    detail.value?.task_type ||
    '未知',
)
const statusLabel = computed(
  () =>
    ({
      draft: '草稿',
      sampling: '抽样中',
      assigned: '已分配',
      in_progress: '进行中',
      completed: '已完成',
      cancelled: '已取消',
    })[detail.value?.status || ''] ||
    detail.value?.status ||
    '未知',
)

function blankRecordRef(): TaskEditCaseRef {
  return { institute_id: '', patient_id: '', visit_id: '' }
}

function canEdit(field: string): boolean {
  return !!detail.value?.editable_fields.includes(field as TaskEditField)
}

function resetForm() {
  scoreFilter.value = undefined
  clinicalDoctors.value = undefined
  form.task_name = ''
  form.scene = null
  form.rule_set_key = ''
  form.deadline = null
  form.dateRange = null
  form.department_filter = []
  form.sampling_method = null
  form.total = 1
  form.percentage = 10
  form.by_department = false
  form.max_per_group = 50
  form.group_by = undefined
  form.assign_method = null
  form.fallback = undefined
  rangeMode.value = 'date'
  recordRefs.value = [blankRecordRef()]
  dateRangeTouched.value = false
  deadlineTouched.value = false
  planningBaseline.value = ''
}

function calendarDay(value: string): Dayjs {
  const calendar = /^\d{4}-\d{2}-\d{2}/.exec(value)?.[0]
  return dayjs(calendar || value)
}

function fillForm(value: TaskEditDetail) {
  form.task_name = value.task_name
  form.scene = value.scene
  form.rule_set_key = value.rule_set_key
  form.deadline = value.deadline ? calendarDay(value.deadline) : null
  form.dateRange =
    value.date_range?.start && value.date_range.end
      ? [calendarDay(value.date_range.start), calendarDay(value.date_range.end)]
      : null
  form.department_filter = [...(value.department_filter || [])]
  form.sampling_method = value.sampling_method
  form.total = typeof value.sampling_config?.total === 'number' ? value.sampling_config.total : 1
  form.percentage =
    typeof value.sampling_config?.percentage === 'number' ? value.sampling_config.percentage : 10
  form.by_department = value.sampling_config?.by_department === true
  const rawScore = value.sampling_config?.score_filter
  const rawDoctors = value.sampling_config?.clinical_doctors
  clinicalDoctors.value = Array.isArray(rawDoctors)
    ? rawDoctors.flatMap((item) =>
        item &&
        typeof item === 'object' &&
        typeof item.institute_id === 'string' &&
        typeof item.physician_name === 'string'
          ? [{ institute_id: item.institute_id, physician_name: item.physician_name }]
          : [],
      )
    : undefined
  scoreFilter.value =
    rawScore &&
    typeof rawScore === 'object' &&
    'standard_id' in rawScore &&
    typeof rawScore.standard_id === 'string'
      ? {
          standard_id: rawScore.standard_id,
          ...('score_min' in rawScore && typeof rawScore.score_min === 'number'
            ? { score_min: rawScore.score_min }
            : {}),
          ...('score_max' in rawScore && typeof rawScore.score_max === 'number'
            ? { score_max: rawScore.score_max }
            : {}),
        }
      : undefined
  form.max_per_group =
    typeof value.sampling_config?.max_per_group === 'number'
      ? value.sampling_config.max_per_group
      : 50
  form.group_by = value.sampling_config?.group_by === 'department' ? 'department' : undefined
  form.assign_method =
    value.assign_method === 'by_ratio' ||
    value.assign_method === 'by_original_reviewer' ||
    value.assign_method === 'by_department'
      ? value.assign_method
      : null
  form.fallback =
    value.assignee_config?.fallback === 'by_ratio' || value.assignee_config?.fallback === 'reject'
      ? value.assignee_config.fallback
      : undefined
  rangeMode.value = value.record_refs?.length ? 'refs' : 'date'
  if (rangeMode.value === 'refs') form.sampling_method = 'all'
  recordRefs.value = value.record_refs?.length
    ? value.record_refs.map((item) => ({ ...item }))
    : [blankRecordRef()]
  dateRangeTouched.value = false
  deadlineTouched.value = false
  planningBaseline.value = planningFingerprint()
}

function clearState() {
  detail.value = null
  loadError.value = ''
  refreshRequired.value = false
  loading.value = false
  saving.value = false
  resetForm()
}

async function refresh() {
  const taskId = props.taskId?.trim()
  const actorId = authStore.user?.id?.trim()
  const sequence = ++requestSequence
  detail.value = null
  resetForm()
  loadError.value = ''
  if (!props.open || !taskId || !actorId) {
    loadError.value = actorId ? '未选择要编辑的任务' : '当前用户身份不可用'
    return
  }
  loading.value = true
  const result = await getTaskEdit(taskId)
  if (
    sequence !== requestSequence ||
    !props.open ||
    props.taskId?.trim() !== taskId ||
    authStore.user?.id?.trim() !== actorId
  )
    return
  loading.value = false
  if (!result.success || !result.data) {
    loadError.value = result.message || '任务编辑详情读取失败'
    return
  }
  detail.value = result.data
  fillForm(result.data)
  refreshRequired.value = false
}

function addRecordRef() {
  recordRefs.value.push(blankRecordRef())
}

function removeRecordRef(index: number) {
  if (recordRefs.value.length > 1) recordRefs.value.splice(index, 1)
}

function normalizedRefs(): TaskEditCaseRef[] | null {
  const refs = recordRefs.value.map((item) => ({
    institute_id: item.institute_id.trim(),
    patient_id: item.patient_id.trim(),
    visit_id: item.visit_id.trim(),
  }))
  if (refs.some((item) => !item.institute_id || !item.patient_id || !item.visit_id)) return null
  const keys = refs.map(
    (item) => `${item.institute_id}\u0000${item.patient_id}\u0000${item.visit_id}`,
  )
  return new Set(keys).size === refs.length ? refs : null
}

function buildDraftPayload(): TaskDraftConfigurationUpdate | null {
  if (!detail.value) return null
  const taskName = form.task_name.trim()
  if (!taskName) {
    message.warning('请输入任务名称')
    return null
  }
  let refs: TaskEditCaseRef[] = []
  if (rangeMode.value === 'refs') {
    const normalized = normalizedRefs()
    if (!normalized) {
      message.warning('每条病历均须填写唯一且完整的机构、患者和就诊 ID')
      return null
    }
    refs = normalized
  }
  if (!form.sampling_method) {
    message.warning('请选择抽样方式')
    return null
  }
  const samplingConfig: Record<string, unknown> = { ...(detail.value.sampling_config || {}) }
  if (detail.value.sampling_config?.case_scope === 'active') samplingConfig.case_scope = 'active'
  delete samplingConfig.total
  delete samplingConfig.by_department
  delete samplingConfig.percentage
  delete samplingConfig.group_by
  delete samplingConfig.max_per_group
  delete samplingConfig.score_filter
  delete samplingConfig.clinical_doctors
  if (rangeMode.value !== 'refs' && clinicalDoctors.value)
    samplingConfig.clinical_doctors = clinicalDoctors.value.map((item) => ({
      institute_id: item.institute_id.trim(),
      physician_name: item.physician_name.trim(),
    }))
  if (rangeMode.value !== 'refs' && scoreFilter.value)
    samplingConfig.score_filter = { ...scoreFilter.value }
  if (
    rangeMode.value !== 'refs' &&
    (form.sampling_method === 'count' || form.sampling_method === 'department_count')
  ) {
    if (!Number.isInteger(form.total) || form.total < 1 || form.total > 10000) {
      message.warning('抽样数量须为 1 至 10000 的整数')
      return null
    }
    samplingConfig.total = form.total
    if (form.sampling_method === 'count') samplingConfig.by_department = form.by_department
  } else if (
    rangeMode.value !== 'refs' &&
    (form.sampling_method === 'percentage' || form.sampling_method === 'department_ratio')
  ) {
    if (!Number.isFinite(form.percentage) || form.percentage < 1 || form.percentage > 100) {
      message.warning('抽样比例须在 1% 至 100% 之间')
      return null
    }
    samplingConfig.percentage = form.percentage
    if (form.sampling_method === 'percentage') samplingConfig.group_by = form.group_by ?? null
    else {
      if (
        !Number.isInteger(form.max_per_group) ||
        form.max_per_group < 1 ||
        form.max_per_group > 10000
      ) {
        message.warning('每科室最多份数须为 1 至 10000 的整数')
        return null
      }
      samplingConfig.max_per_group = form.max_per_group
    }
  }
  if (!form.assign_method) {
    message.warning('请选择可用的分配方式')
    return null
  }
  if (form.assign_method === 'by_original_reviewer' && !form.fallback) {
    message.warning('请选择无原质控员时的处理方式')
    return null
  }
  let dateRange: TaskDraftConfigurationUpdate['date_range'] = null
  if (rangeMode.value === 'date' || form.scene === 'final') {
    const original = detail.value.date_range
    const unchanged =
      !!form.dateRange &&
      !!original?.start &&
      !!original.end &&
      form.dateRange[0].format('YYYY-MM-DD') === calendarDay(original.start).format('YYYY-MM-DD') &&
      form.dateRange[1].format('YYYY-MM-DD') === calendarDay(original.end).format('YYYY-MM-DD')
    dateRange = unchanged
      ? { start: original.start, end: original.end }
      : form.dateRange
        ? {
            start: form.dateRange[0].format('YYYY-MM-DD'),
            end: form.dateRange[1].format('YYYY-MM-DD'),
          }
        : !dateRangeTouched.value && original
          ? { ...original }
          : null
  }
  if (form.scene === 'final' && samplingConfig.case_scope === 'discharged') {
    const error = dischargedDateRangeError(dateRange?.start, dateRange?.end)
    if (error) {
      message.warning(error)
      return null
    }
  }
  return {
    configuration_version: detail.value.configuration_version,
    task_name: taskName,
    deadline: normalizedDeadline(),
    date_range: dateRange,
    department_filter:
      rangeMode.value === 'date'
        ? [...new Set(form.department_filter.map((item) => item.trim()).filter(Boolean))]
        : [],
    record_refs: refs,
    sampling_method: rangeMode.value === 'refs' ? 'all' : form.sampling_method,
    sampling_config: samplingConfig,
    assign_method: form.assign_method,
    assignee_config: (() => {
      const config = { ...(detail.value?.assignee_config || {}) }
      if (form.assign_method === 'by_original_reviewer' && form.fallback)
        config.fallback = form.fallback
      else delete config.fallback
      return config
    })(),
  }
}

function buildMetadataPayload(): TaskMetadataUpdate | null {
  if (!detail.value) return null
  const payload: TaskMetadataUpdate = { configuration_version: detail.value.configuration_version }
  if (canEdit('task_name') && form.task_name.trim() !== detail.value.task_name) {
    if (!form.task_name.trim()) {
      message.warning('请输入任务名称')
      return null
    }
    payload.task_name = form.task_name.trim()
  }
  const deadline = normalizedDeadline()
  if (canEdit('deadline') && deadline !== detail.value.deadline) payload.deadline = deadline
  if (
    !Object.prototype.hasOwnProperty.call(payload, 'task_name') &&
    !Object.prototype.hasOwnProperty.call(payload, 'deadline')
  ) {
    message.warning('没有需要保存的修改')
    return null
  }
  return payload
}

function normalizedDeadline(): string | null {
  if (!detail.value) return null
  if (!form.deadline) return null
  if (
    detail.value.deadline &&
    form.deadline.format('YYYY-MM-DD') === calendarDay(detail.value.deadline).format('YYYY-MM-DD')
  ) {
    return detail.value.deadline
  }
  return form.deadline.format('YYYY-MM-DD')
}

function planningFingerprint(): string {
  return JSON.stringify({
    rangeMode: rangeMode.value,
    dateRange: form.dateRange?.map((item) => item.format('YYYY-MM-DD')) || null,
    departments: form.department_filter,
    recordRefs: recordRefs.value.map((item) => ({
      institute_id: item.institute_id.trim(),
      patient_id: item.patient_id.trim(),
      visit_id: item.visit_id.trim(),
    })),
    samplingMethod: form.sampling_method,
    scoreFilter: rangeMode.value === 'refs' ? null : (scoreFilter.value ?? null),
    clinicalDoctors: rangeMode.value === 'refs' ? null : (clinicalDoctors.value ?? null),
    total: form.total,
    percentage: form.percentage,
    byDepartment: form.by_department,
    maxPerGroup: form.max_per_group,
    groupBy: form.group_by ?? null,
    assignMethod: form.assign_method,
    fallback: form.fallback ?? null,
  })
}

function confirmSave() {
  if (!detail.value || saving.value || refreshRequired.value || !hasEditableFields.value) return
  const operation =
    fullConfigurationEditable.value && planningFingerprint() !== planningBaseline.value
      ? 'draft'
      : 'metadata'
  const payload = operation === 'draft' ? buildDraftPayload() : buildMetadataPayload()
  if (!payload) return
  const context = {
    taskId: props.taskId?.trim() || '',
    actorId: authStore.user?.id?.trim() || '',
    version: detail.value.configuration_version,
    sequence: requestSequence,
  }
  Modal.confirm({
    title: '确认保存任务修改？',
    content: '系统会校验任务状态、关联病例和配置版本；冻结的场景与规则集不会改变。',
    okText: '确认保存',
    cancelText: '取消',
    async onOk() {
      if (
        !context.taskId ||
        !context.actorId ||
        context.sequence !== requestSequence ||
        props.taskId?.trim() !== context.taskId ||
        authStore.user?.id?.trim() !== context.actorId ||
        detail.value?.configuration_version !== context.version
      )
        return
      await save(payload, context, operation)
    },
  })
}

function explainError(result: TaskEditResult): string {
  const labels: Partial<Record<NonNullable<TaskEditResult['code']>, string>> = {
    task_not_found: '任务不存在或已被删除',
    task_edit_forbidden: '当前账号无权编辑该任务',
    version_conflict: '任务配置已被其他操作更新，请刷新后重试',
    state_conflict: '任务状态已变化，请刷新后重试',
    association_conflict: '任务已关联病例，完整配置不可再修改',
    task_edit_invalid: '任务配置不符合要求',
    task_edit_unavailable: '任务编辑服务暂不可用',
  }
  return (result.code && labels[result.code]) || result.message || '任务保存失败'
}

async function save(
  payload: TaskDraftConfigurationUpdate | TaskMetadataUpdate,
  context: { taskId: string; actorId: string; version: number; sequence: number },
  operation: 'draft' | 'metadata',
) {
  if (!detail.value || saving.value) return
  if (
    context.sequence !== requestSequence ||
    props.taskId?.trim() !== context.taskId ||
    authStore.user?.id?.trim() !== context.actorId ||
    detail.value.configuration_version !== context.version
  )
    return
  const previousVersion = context.version
  const sequence = ++requestSequence
  saving.value = true
  const result =
    operation === 'draft'
      ? await updateTaskDraftConfiguration(context.taskId, payload as TaskDraftConfigurationUpdate)
      : await updateTaskMetadata(context.taskId, payload as TaskMetadataUpdate)
  if (
    sequence !== requestSequence ||
    !props.open ||
    props.taskId?.trim() !== context.taskId ||
    authStore.user?.id?.trim() !== context.actorId
  )
    return
  saving.value = false
  const receipt = result.data
  const receiptValid =
    result.success &&
    receipt?.id === context.taskId &&
    Number.isInteger(receipt.configuration_version) &&
    receipt.configuration_version > previousVersion
  if (!receiptValid) {
    if (result.uncertain || result.success) {
      refreshRequired.value = true
      message.warning('任务保存结果未知，请刷新任务后再继续操作')
      return
    }
    const conflict =
      result.code === 'version_conflict' ||
      result.code === 'state_conflict' ||
      result.code === 'association_conflict'
    if (conflict) refreshRequired.value = true
    message.error(explainError(result))
    return
  }
  if (!receipt) return
  detail.value = receipt
  fillForm(receipt)
  message.success('任务修改已保存')
  emit('saved', context.taskId)
}

function closeDrawer() {
  if (saving.value) return
  requestSequence += 1
  emit('update:open', false)
}

watch(rangeMode, (mode) => {
  if (mode === 'refs') form.sampling_method = 'all'
})
watch(
  [() => props.open, () => props.taskId, () => authStore.user?.id],
  ([open, taskId]) => {
    requestSequence += 1
    clearState()
    if (open && taskId) void refresh()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  requestSequence += 1
})
</script>

<style scoped>
.task-edit-alert {
  margin-bottom: 16px;
}
.task-edit-summary {
  margin-bottom: 20px;
}
.task-edit-form section {
  padding: 18px 0 4px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}
.task-edit-form h3 {
  margin: 0 0 14px;
  color: #1d1d1f;
  font-size: 17px;
  font-weight: 600;
  line-height: 22px;
}
.record-ref-heading,
.record-ref-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr)) 36px;
  gap: 8px;
}
.record-ref-heading {
  margin-bottom: 6px;
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
}
.record-ref-row {
  margin-bottom: 8px;
}
.sampling-value {
  margin: 4px 0 0;
  color: #007aff;
  font-size: 17px;
  font-weight: 600;
  text-align: center;
}
.task-edit-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
@media (max-width: 560px) {
  .record-ref-heading {
    display: none;
  }
  .record-ref-row {
    grid-template-columns: minmax(0, 1fr) 36px;
  }
  .record-ref-row :deep(.ant-input) {
    grid-column: 1;
  }
  .record-ref-row :deep(.ant-btn) {
    grid-column: 2;
    grid-row: 1 / span 3;
    align-self: center;
  }
}
</style>
