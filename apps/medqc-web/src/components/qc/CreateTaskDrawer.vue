<template>
  <a-drawer
    v-model:open="visible"
    title="创建质控任务"
    :width="'min(720px, 100vw)'"
    :body-style="{ padding: '24px' }"
    :destroy-on-close="true"
    @close="handleClose"
  >
    <!-- 步骤条 -->
    <a-steps :current="currentStep" size="small" class="mb-8">
      <a-step title="基本信息" />
      <a-step title="病历范围" />
      <a-step title="抽样规则" />
      <a-step title="任务分配" />
      <a-step title="确认提交" />
    </a-steps>

    <div class="mb-5 flex justify-end">
      <a-button
        data-testid="save-current-task-template"
        :disabled="submitting || ruleSetsLoading || rangeMode === 'refs'"
        @click="handleSaveTemplate"
      >
        <SaveOutlined /> 保存当前配置为模板
      </a-button>
    </div>

    <!-- Step 1: 基本信息 -->
    <div v-show="currentStep === 0">
      <a-form :model="formData" layout="vertical">
        <a-form-item label="任务名称" required>
          <a-input
            v-model:value="formData.task_name"
            placeholder="例如：2026年3月终末病历质控"
            :maxlength="100"
            show-count
          />
        </a-form-item>

        <a-form-item label="质控场景" required>
          <a-select
            v-model:value="formData.scene"
            data-testid="task-scene-select"
            placeholder="请选择质控场景"
            :options="sceneOptions"
          />
        </a-form-item>

        <a-form-item label="质控规则集" required>
          <a-select
            v-model:value="formData.rule_set_key"
            data-testid="task-rule-set-select"
            placeholder="请选择规则集"
            :loading="ruleSetsLoading"
            :disabled="
              !formData.scene || ruleSetsLoading || !!ruleSetsError || !matchingRuleSets.length
            "
            :options="ruleSetSelectOptions"
          />
        </a-form-item>
        <a-alert
          v-if="ruleSetsError"
          type="error"
          :message="ruleSetsError"
          show-icon
          class="mb-4"
        />
        <a-alert
          v-else-if="formData.scene && !ruleSetsLoading && !matchingRuleSets.length"
          type="warning"
          :message="`${sceneLabel}暂无可用的匹配规则集，当前不能创建任务。`"
          show-icon
          class="mb-4"
        />

        <a-form-item label="截止日期">
          <a-date-picker
            v-model:value="formData.deadline"
            style="width: 100%"
            :disabled-date="(d: any) => d && d < Date.now() - 86400000"
            placeholder="选择截止日期"
          />
        </a-form-item>

        <a-form-item label="任务说明">
          <a-textarea
            v-model:value="formData.description"
            placeholder="可选的任务备注说明"
            :rows="3"
            :maxlength="500"
            show-count
          />
        </a-form-item>
      </a-form>
    </div>

    <!-- Step 2: 病历范围 -->
    <div v-show="currentStep === 1">
      <a-form layout="vertical">
        <a-form-item
          v-if="requiredCaseScope"
          :label="formData.scene === 'final' ? '终末病历范围' : '运行病历范围'"
          required
        >
          <a-select
            v-model:value="formData.sampling_config.case_scope"
            data-testid="task-case-scope-select"
            :placeholder="formData.scene === 'final' ? '请选择终末病历范围' : '请选择运行病历范围'"
            :options="[{ value: requiredCaseScope, label: caseScopeLabel(requiredCaseScope) }]"
          />
          <div class="text-xs text-gray-500 mt-2" data-testid="task-case-scope-hint">
            {{
              formData.scene === 'final'
                ? '按出院日期抽取已出院病历，归档状态未核验；出院日期范围必填，最多 31 天。'
                : '运行病历仅含当前在院；已出院病历请在终末场景抽样。'
            }}
          </div>
        </a-form-item>
        <a-form-item label="选择方式">
          <a-radio-group v-model:value="rangeMode">
            <a-radio-button value="date"> 按日期范围 </a-radio-button>
            <a-radio-button value="refs"> 指定病历 </a-radio-button>
          </a-radio-group>
        </a-form-item>

        <template v-if="rangeMode === 'date'">
          <a-form-item
            :label="formData.scene === 'final' ? '出院日期范围' : '日期范围'"
            :required="formData.scene === 'final'"
          >
            <a-range-picker
              v-model:value="dateRangeValue"
              style="width: 100%"
              @change="handleDateRangeChange"
            />
          </a-form-item>

          <a-form-item label="科室筛选">
            <a-select
              v-model:value="formData.department_filter"
              mode="multiple"
              placeholder="不选则包含全部科室"
              style="width: 100%"
              :options="departmentOptions"
            />
          </a-form-item>
          <TaskClinicalDoctorFields
            v-model="formData.sampling_config.clinical_doctors"
            :scene="formData.scene"
          />
          <TaskScoreFilterFields
            v-model="formData.sampling_config.score_filter"
            :scene="formData.scene"
          />
        </template>
        <template v-else>
          <a-form-item v-if="formData.scene === 'final'" label="出院日期范围" required>
            <a-range-picker
              v-model:value="dateRangeValue"
              data-testid="task-refs-discharge-range"
              style="width: 100%"
              @change="handleDateRangeChange"
            />
            <div class="text-xs text-gray-500 mt-2">
              指定病历须在该出院日期范围内（最多 31 天）。
            </div>
          </a-form-item>
          <a-form-item label="病历坐标" required>
            <div
              class="hidden sm:grid grid-cols-[repeat(3,minmax(0,1fr))_36px] gap-2 text-xs text-gray-500 mb-2"
            >
              <span>机构 ID</span><span>患者 ID</span><span>就诊 ID</span><span />
            </div>
            <div
              v-for="(recordRef, index) in recordRefs"
              :key="index"
              class="grid grid-cols-1 sm:grid-cols-[repeat(3,minmax(0,1fr))_36px] gap-2 mb-2"
            >
              <a-input
                v-model:value="recordRef.institute_id"
                :aria-label="`第 ${index + 1} 条机构 ID`"
                placeholder="机构 ID"
                :maxlength="100"
              />
              <a-input
                v-model:value="recordRef.patient_id"
                :aria-label="`第 ${index + 1} 条患者 ID`"
                placeholder="患者 ID"
                :maxlength="100"
              />
              <a-input
                v-model:value="recordRef.visit_id"
                :aria-label="`第 ${index + 1} 条就诊 ID`"
                placeholder="就诊 ID"
                :maxlength="100"
              />
              <a-button
                :aria-label="`删除第 ${index + 1} 条病历`"
                :disabled="recordRefs.length === 1"
                title="删除病历"
                @click="removeRecordRef(index)"
              >
                <DeleteOutlined />
              </a-button>
            </div>
            <a-button @click="addRecordRef"> <PlusOutlined /> 添加病历 </a-button>
            <div v-if="recordRefsError" class="text-xs text-red-500 mt-2">
              {{ recordRefsError }}
            </div>
            <div v-else class="text-xs text-gray-500 mt-2">
              已填写 {{ normalizedRecordRefs.length }} 条病历
            </div>
          </a-form-item>
        </template>
      </a-form>
    </div>

    <!-- Step 3: 抽样规则 -->
    <div v-show="currentStep === 2">
      <a-form layout="vertical">
        <a-form-item label="抽样方式">
          <a-radio-group
            v-model:value="formData.sampling_method"
            class="w-full"
            :disabled="rangeMode === 'refs'"
          >
            <div class="grid grid-cols-3 gap-3">
              <div
                v-for="opt in samplingOptions"
                :key="opt.value"
                :class="[
                  'border rounded-xl p-4 cursor-pointer transition-all text-center',
                  formData.sampling_method === opt.value
                    ? 'border-blue-500 bg-blue-50 shadow-sm'
                    : 'border-gray-200 hover:border-blue-200',
                ]"
                @click="rangeMode !== 'refs' && (formData.sampling_method = opt.value)"
              >
                <component
                  :is="opt.icon"
                  class="text-2xl mb-2"
                  :class="
                    formData.sampling_method === opt.value ? 'text-blue-600' : 'text-gray-400'
                  "
                />
                <div class="font-medium text-sm">
                  {{ opt.label }}
                </div>
                <div class="text-xs text-gray-400 mt-1">
                  {{ opt.desc }}
                </div>
              </div>
            </div>
          </a-radio-group>
        </a-form-item>

        <template
          v-if="
            formData.sampling_method === 'count' || formData.sampling_method === 'department_count'
          "
        >
          <a-form-item
            :label="formData.sampling_method === 'department_count' ? '每科室固定份数' : '抽样数量'"
          >
            <a-input-number
              v-model:value="formData.sampling_config.total"
              :min="1"
              :max="10000"
              style="width: 100%"
              placeholder="输入要抽取的病历数量"
            />
          </a-form-item>
          <a-form-item v-if="formData.sampling_method === 'count'">
            <a-checkbox v-model:checked="formData.sampling_config.by_department">
              按科室均匀分配抽样数量
            </a-checkbox>
          </a-form-item>
        </template>

        <template
          v-if="
            formData.sampling_method === 'percentage' ||
            formData.sampling_method === 'department_ratio'
          "
        >
          <a-form-item label="抽样比例">
            <a-slider
              v-model:value="formData.sampling_config.percentage"
              :min="1"
              :max="100"
              :tip-formatter="(val: number) => `${val}%`"
            />
            <div class="text-center text-blue-600 font-bold text-lg">
              {{ formData.sampling_config.percentage }}%
            </div>
          </a-form-item>
          <a-form-item
            v-if="formData.sampling_method === 'department_ratio'"
            label="每科室最多份数"
            required
          >
            <a-input-number
              v-model:value="formData.sampling_config.max_per_group"
              :min="1"
              :max="10000"
              style="width: 100%"
            />
          </a-form-item>
          <a-form-item v-else label="分组依据">
            <a-select
              v-model:value="formData.sampling_config.group_by"
              placeholder="选择分组方式"
              style="width: 100%"
              :options="[{ value: 'department', label: '按科室' }]"
              allow-clear
            />
          </a-form-item>
        </template>
      </a-form>
    </div>

    <!-- Step 4: 任务分配 -->
    <div v-show="currentStep === 3">
      <a-form layout="vertical">
        <a-form-item label="分配方式">
          <a-radio-group v-model:value="formData.assign_method" data-testid="assign-method-group">
            <a-radio
              v-for="opt in assignMethodOptions"
              :key="opt.value"
              :value="opt.value"
              :disabled="opt.disabled"
              :data-testid="`assign-method-${opt.value}`"
            >
              {{ opt.label }}
            </a-radio>
          </a-radio-group>
          <div class="text-xs text-gray-500 mt-2" data-testid="assign-method-record-type-hint">
            病历类型：当前场景病历类型无区分，暂不可用
          </div>
        </a-form-item>

        <a-form-item
          v-if="formData.assign_method === 'by_original_reviewer'"
          label="无原质控员时"
          required
        >
          <a-radio-group
            v-model:value="formData.assign_fallback"
            data-testid="assign-fallback-group"
          >
            <a-radio value="by_ratio"> 按比例分给选定人员 </a-radio>
            <a-radio value="reject"> 拒绝分配 </a-radio>
          </a-radio-group>
          <div
            v-if="!formData.assign_fallback"
            class="text-xs text-red-500 mt-2"
            data-testid="assign-fallback-required"
          >
            请选择病历无原质控员或原质控员未被选定时的处理方式
          </div>
        </a-form-item>

        <a-alert
          v-if="formData.assign_method === 'by_department'"
          data-testid="assign-department-hint"
          type="warning"
          show-icon
          message="受领人按其账号科室匹配病历科室，历史任务缺科室将无法分配"
        />

        <a-alert
          message="抽样后分配质控员"
          description="创建任务时只保存分配策略。执行抽样后，在单任务分配中从真实质控员目录选择人员。"
          type="info"
          show-icon
          class="mt-4"
        />
      </a-form>
    </div>

    <!-- Step 5: 确认提交 -->
    <div v-show="currentStep === 4">
      <a-descriptions title="任务概览" bordered :column="1" size="small">
        <a-descriptions-item label="任务名称">
          {{ formData.task_name || '(未设置)' }}
        </a-descriptions-item>
        <a-descriptions-item label="任务类型"> 单次任务 </a-descriptions-item>
        <a-descriptions-item label="质控场景">
          {{ sceneLabel }}
        </a-descriptions-item>
        <a-descriptions-item label="质控规则集">
          {{ selectedRuleSetLabel }}
        </a-descriptions-item>
        <a-descriptions-item label="截止日期">
          {{ formData.deadline?.format('YYYY-MM-DD') || '无截止日期' }}
        </a-descriptions-item>
        <a-descriptions-item label="病历范围">
          <template v-if="rangeMode === 'date'">
            {{ caseScopePrefix }}日期范围 + {{ formData.department_filter?.length || 0 }} 个科室筛选
          </template>
          <template v-else>
            {{ caseScopePrefix }}指定 {{ normalizedRecordRefs.length }} 条病历
          </template>
        </a-descriptions-item>
        <a-descriptions-item label="抽样方式">
          {{ samplingLabel }}
        </a-descriptions-item>
        <a-descriptions-item label="分配方式">
          {{ assignLabel }}
        </a-descriptions-item>
      </a-descriptions>

      <a-alert
        message="提交后将立即创建任务草稿"
        description="创建后可在任务详情中执行抽样和分配操作。"
        type="warning"
        show-icon
        class="mt-6"
      />
    </div>

    <!-- 底部按钮 -->
    <template #footer>
      <div class="flex justify-between">
        <a-button v-if="currentStep > 0" @click="prevStep"> 上一步 </a-button>
        <div v-else />

        <div class="flex gap-3">
          <a-button @click="handleClose"> 取消 </a-button>
          <a-button v-if="currentStep < 4" type="primary" :disabled="!canProceed" @click="nextStep">
            下一步
          </a-button>
          <a-button v-else type="primary" :loading="submitting" @click="handleSubmit">
            <CheckOutlined /> 创建任务
          </a-button>
        </div>
      </div>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  CheckOutlined,
  DatabaseOutlined,
  NumberOutlined,
  PercentageOutlined,
  PlusOutlined,
  DeleteOutlined,
  SaveOutlined,
} from '@ant-design/icons-vue'
import { createTask, getTaskRuleSets } from '@/api/tasks'
import type {
  AssignFallback,
  TaskAssignableMethod,
  TaskCaseRef,
  TaskCreateData,
  TaskItem,
  TaskRuleSetOption,
  TaskScene,
  TaskTemplateConfig,
} from '@/api/tasks'
import { describeTaskAssignError } from '@/utils/taskAssignment'
import {
  caseScopeLabel,
  dischargedDateRangeError,
  sceneCaseScope,
  type TaskCaseScope,
} from '@/utils/taskCaseScope'
import TaskScoreFilterFields from './TaskScoreFilterFields.vue'
import TaskClinicalDoctorFields from './TaskClinicalDoctorFields.vue'
import type { TaskClinicalDoctorRef } from '@/api/tasks'
import type { TaskScoreFilter } from '@/api/tasks'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'

// ============= Props & Emits =============
const props = defineProps<{
  open: boolean
  initialTemplateConfig?: TaskTemplateConfig | null
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'created', task: TaskItem): void
  (e: 'save-template', config: TaskTemplateConfig): void
}>()

// ============= 状态 =============
const visible = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val),
})

const currentStep = ref(0)
const submitting = ref(false)
const rangeMode = ref<'date' | 'refs'>('date')
watch(rangeMode, (mode) => {
  if (mode === 'refs') formData.value.sampling_method = 'all'
})
const dateRangeValue = ref<[Dayjs, Dayjs] | null>(null)
const blankRecordRef = (): TaskCaseRef => ({ institute_id: '', patient_id: '', visit_id: '' })
const recordRefs = ref<TaskCaseRef[]>([blankRecordRef()])
const ruleSets = ref<TaskRuleSetOption[]>([])
const ruleSetsLoading = ref(false)
const ruleSetsError = ref('')
let ruleSetRequestId = 0
let applyingTemplate = false

// 表单数据
const formData = ref({
  task_name: '',
  scene: null as TaskScene | null,
  rule_set_key: undefined as string | undefined,
  task_type: 'one_time' as 'one_time' | 'scheduled',
  deadline: null as Dayjs | null,
  description: '',
  date_range: null as { start?: string; end?: string } | null,
  department_filter: [] as string[],
  sampling_method: 'all' as import('@/api/tasks').SamplingMethod,
  sampling_config: {
    case_scope: undefined as TaskCaseScope | undefined,
    total: 50,
    percentage: 10,
    by_department: false,
    group_by: null as string | null,
    max_per_group: 50,
    score_filter: undefined as TaskScoreFilter | undefined,
    clinical_doctors: undefined as TaskClinicalDoctorRef[] | undefined,
  },
  assign_method: 'by_ratio' as TaskAssignableMethod,
  // 原质控员策略必选，不给默认值，避免用户未确认即拒绝或兜底
  assign_fallback: undefined as AssignFallback | undefined,
})

// ============= 选项配置 =============
const ASSIGNABLE_METHODS: readonly TaskAssignableMethod[] = [
  'by_ratio',
  'by_original_reviewer',
  'by_department',
]
const assignMethodOptions: Array<{
  value: TaskAssignableMethod | 'by_record_type'
  label: string
  disabled?: boolean
}> = [
  { value: 'by_ratio', label: '按比例均分' },
  { value: 'by_original_reviewer', label: '原质控员' },
  { value: 'by_department', label: '按科室' },
  { value: 'by_record_type', label: '病历类型（暂不可用）', disabled: true },
]
const ASSIGN_LABELS: Record<TaskAssignableMethod, string> = {
  by_ratio: '按比例均分（抽样后选人）',
  by_original_reviewer: '原质控员（抽样后选人）',
  by_department: '按科室（抽样后选人，按账号科室匹配）',
}
const FALLBACK_LABELS: Record<AssignFallback, string> = {
  by_ratio: '无原质控员时按比例分给选定人员',
  reject: '无原质控员时拒绝分配',
}
const sceneOptions: Array<{ value: TaskScene; label: string }> = [
  { value: 'running', label: '运行病历' },
  { value: 'final', label: '终末病历' },
  { value: 'outpatient', label: '门急诊病历' },
]

const departmentOptions = [
  { value: '内科', label: '内科' },
  { value: '外科', label: '外科' },
  { value: '骨科', label: '骨科' },
  { value: '儿科', label: '儿科' },
  { value: '妇产科', label: '妇产科' },
  { value: '肿瘤科', label: '肿瘤科' },
  { value: '心内科', label: '心内科' },
  { value: '神经内科', label: '神经内科' },
  { value: '呼吸内科', label: '呼吸内科' },
  { value: '消化内科', label: '消化内科' },
  { value: '泌尿外科', label: '泌尿外科' },
  { value: '急诊科', label: '急诊科' },
  { value: 'ICU', label: 'ICU' },
]

const samplingOptions: Array<{
  value: import('@/api/tasks').SamplingMethod
  label: string
  desc: string
  icon: unknown
}> = [
  { value: 'all', label: '全部', desc: '取全部匹配病历', icon: DatabaseOutlined },
  { value: 'count', label: '按数量', desc: '随机抽取N条', icon: NumberOutlined },
  { value: 'percentage', label: '按比例', desc: '各组取X%', icon: PercentageOutlined },
  { value: 'department_count', label: '每科室定额', desc: '各科室固定份数', icon: NumberOutlined },
  {
    value: 'department_ratio',
    label: '每科室比例',
    desc: '按比例且不超过上限',
    icon: PercentageOutlined,
  },
]

// ============= 计算属性 =============
const normalizedRecordRefs = computed(() =>
  recordRefs.value.map((item) => ({
    institute_id: item.institute_id.trim(),
    patient_id: item.patient_id.trim(),
    visit_id: item.visit_id.trim(),
  })),
)
const recordRefsError = computed(() => {
  if (
    !recordRefs.value.length ||
    normalizedRecordRefs.value.every(
      (item) => !item.institute_id && !item.patient_id && !item.visit_id,
    )
  )
    return '请至少填写一条完整的病历坐标'
  if (
    normalizedRecordRefs.value.some(
      (item) => !item.institute_id || !item.patient_id || !item.visit_id,
    )
  )
    return '每条病历均须填写机构 ID、患者 ID 和就诊 ID'
  const keys = normalizedRecordRefs.value.map((item) =>
    JSON.stringify([item.institute_id, item.patient_id, item.visit_id]),
  )
  return new Set(keys).size === keys.length ? '' : '存在重复的病历坐标，请合并后继续'
})

const matchingRuleSets = computed(() =>
  ruleSets.value.filter((item) => item.scope === formData.value.scene && item.rule_set_key.trim()),
)
const ruleSetSelectOptions = computed(() =>
  matchingRuleSets.value.map((item) => ({
    value: item.rule_set_key,
    label: `${item.rule_set_name} (${item.rule_set_version})`,
  })),
)
const selectedRuleSetLabel = computed(
  () =>
    ruleSetSelectOptions.value.find((item) => item.value === formData.value.rule_set_key)?.label ||
    '(未选择)',
)
const selectedRuleSetIsValid = computed(
  () =>
    !ruleSetsLoading.value &&
    !ruleSetsError.value &&
    matchingRuleSets.value.some((item) => item.rule_set_key === formData.value.rule_set_key),
)
const assignMethodError = computed(() => {
  const method = formData.value.assign_method
  if (!ASSIGNABLE_METHODS.includes(method)) return '请选择可用的分配方式'
  if (
    method === 'by_original_reviewer' &&
    formData.value.assign_fallback !== 'by_ratio' &&
    formData.value.assign_fallback !== 'reject'
  ) {
    return '请选择“无原质控员时”的处理方式'
  }
  return ''
})

const validSamplingGroup = computed(() => {
  const groupBy = formData.value.sampling_config.group_by
  return groupBy === null || groupBy === undefined || groupBy === 'department'
})

const canProceed = computed(() => {
  switch (currentStep.value) {
    case 0:
      return (
        formData.value.task_name.trim().length > 0 &&
        formData.value.scene !== null &&
        selectedRuleSetIsValid.value
      )
    case 1:
      return caseScopeSatisfied.value && (rangeMode.value !== 'refs' || !recordRefsError.value)
    case 2:
      return formData.value.sampling_method !== 'percentage' || validSamplingGroup.value
    case 3:
      return !assignMethodError.value
    default:
      return true
  }
})

/** 该场景新建任务必须选择的病例范围：运行=当前在院，终末=已出院（未核验归档）。 */
const requiredCaseScope = computed(() => sceneCaseScope(formData.value.scene))
const caseScopeSatisfied = computed(
  () =>
    !requiredCaseScope.value ||
    formData.value.sampling_config.case_scope === requiredCaseScope.value,
)
const caseScopePrefix = computed(() =>
  requiredCaseScope.value && caseScopeSatisfied.value
    ? `${caseScopeLabel(requiredCaseScope.value)} · `
    : '',
)

const sceneLabel = computed(() => {
  return sceneOptions.find((option) => option.value === formData.value.scene)?.label || '(未选择)'
})

const samplingLabel = computed(() => {
  const method = formData.value.sampling_method
  if (method === 'all') return '全部病历'
  if (method === 'count') return `随机抽取 ${formData.value.sampling_config.total} 条`
  if (method === 'percentage') return `各组抽取 ${formData.value.sampling_config.percentage}%`
  if (method === 'department_count') return `每科室抽取 ${formData.value.sampling_config.total} 份`
  if (method === 'department_ratio')
    return `每科室抽取 ${formData.value.sampling_config.percentage}%，最多 ${formData.value.sampling_config.max_per_group} 份`
  return method
})

const assignLabel = computed(() => {
  const method = formData.value.assign_method
  if (!ASSIGNABLE_METHODS.includes(method)) return '暂不可用'
  const fallback = formData.value.assign_fallback
  return method === 'by_original_reviewer' && fallback
    ? `${ASSIGN_LABELS[method]}；${FALLBACK_LABELS[fallback]}`
    : ASSIGN_LABELS[method]
})

watch(
  () => formData.value.scene,
  () => {
    if (applyingTemplate) return
    formData.value.rule_set_key = undefined
    formData.value.sampling_config.case_scope = undefined
    formData.value.sampling_config.score_filter = undefined
    formData.value.sampling_config.clinical_doctors = undefined
  },
)

watch(
  () => props.open,
  async (open) => {
    const requestId = ++ruleSetRequestId
    if (!open) return
    ruleSetsLoading.value = true
    ruleSetsError.value = ''
    ruleSets.value = []
    try {
      const result = await getTaskRuleSets()
      if (requestId !== ruleSetRequestId) return
      if (!result.success || !Array.isArray(result.data?.items)) {
        ruleSetsError.value = result.message || '规则集目录加载失败，请稍后重试'
        return
      }
      ruleSets.value = result.data.items.filter(
        (item) =>
          typeof item.rule_set_key === 'string' &&
          typeof item.rule_set_name === 'string' &&
          typeof item.rule_set_version === 'string' &&
          typeof item.scope === 'string',
      )
      if (props.initialTemplateConfig) {
        await applyTemplateConfig(props.initialTemplateConfig)
      }
    } catch {
      if (requestId === ruleSetRequestId) ruleSetsError.value = '规则集目录加载失败，请稍后重试'
    } finally {
      if (requestId === ruleSetRequestId) ruleSetsLoading.value = false
    }
  },
  { immediate: true },
)

// ============= 方法 =============
const nextStep = () => {
  if (!canProceed.value) return
  if (currentStep.value < 4) currentStep.value++
}

const prevStep = () => {
  if (currentStep.value > 0) currentStep.value--
}

const addRecordRef = () => recordRefs.value.push(blankRecordRef())
const removeRecordRef = (index: number) => {
  if (recordRefs.value.length > 1) recordRefs.value.splice(index, 1)
}

const handleDateRangeChange = (_dates: [Dayjs, Dayjs] | null, dateStrings: [string, string]) => {
  const [start, end] = dateStrings
  formData.value.date_range =
    start || end ? { start: start || undefined, end: end || undefined } : null
}

const activeDateRangeError = (range: { start?: string; end?: string } | null): string => {
  if (!range) return ''
  const start = range.start?.trim()
  const end = range.end?.trim()
  const validDate = (value: string) =>
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    dayjs(value).isValid() &&
    dayjs(value).format('YYYY-MM-DD') === value
  if ((start && !validDate(start)) || (end && !validDate(end)))
    return '入院日期范围格式无效，请选择有效日期'
  const today = dayjs(new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString().slice(0, 10))
  if (start && dayjs(start).isAfter(today, 'day')) return '入院开始日期不能晚于在院截止日期'
  if (start && dayjs(start).isBefore(today.subtract(180, 'day'), 'day'))
    return '入院日期范围最多 180 天'
  if (start && end && dayjs(start).isAfter(dayjs(end), 'day'))
    return '日期范围起始时间不能晚于结束时间'
  return ''
}

const applyTemplateConfig = async (config: TaskTemplateConfig) => {
  const ruleSetAvailable = ruleSets.value.some(
    (item) => item.scope === config.scene && item.rule_set_key === config.rule_set_key,
  )
  if (!ruleSetAvailable) {
    message.warning('模板规则集已不可用，请编辑模板后再套用')
    return
  }
  applyingTemplate = true
  formData.value.scene = config.scene
  formData.value.rule_set_key = config.rule_set_key
  formData.value.date_range = config.date_range
    ? {
        start: config.date_range.start || undefined,
        end: config.date_range.end || undefined,
      }
    : null
  const start = config.date_range?.start
  const end = config.date_range?.end
  dateRangeValue.value = start && end ? [dayjs(start), dayjs(end)] : null
  formData.value.department_filter = [...config.department_filter]
  formData.value.sampling_method = config.sampling_method
  formData.value.sampling_config = {
    case_scope: config.sampling_config.case_scope,
    total: config.sampling_config.total ?? 50,
    percentage: config.sampling_config.percentage ?? 10,
    by_department: config.sampling_config.by_department ?? false,
    group_by: config.sampling_config.group_by ?? null,
    max_per_group: config.sampling_config.max_per_group ?? 50,
    score_filter: config.sampling_config.score_filter
      ? { ...config.sampling_config.score_filter }
      : undefined,
    clinical_doctors: config.sampling_config.clinical_doctors?.map((item) => ({ ...item })),
  }
  formData.value.assign_method = config.assign_method
  formData.value.assign_fallback = config.assignee_config.fallback
  rangeMode.value = 'date'
  recordRefs.value = [blankRecordRef()]
  currentStep.value = 0
  await nextTick()
  applyingTemplate = false
  message.success('模板配置已套用，请填写任务名称和截止日期')
}

const currentTemplateConfig = (): TaskTemplateConfig | null => {
  const scene = formData.value.scene
  const ruleSetKey = formData.value.rule_set_key
  if (!scene || !ruleSetKey || !selectedRuleSetIsValid.value) return null
  if (!caseScopeSatisfied.value) return null
  if (
    assignMethodError.value ||
    (formData.value.sampling_method === 'percentage' && !validSamplingGroup.value)
  ) {
    return null
  }
  const samplingConfig: TaskTemplateConfig['sampling_config'] = {
    ...(formData.value.sampling_config.clinical_doctors
      ? {
          clinical_doctors: formData.value.sampling_config.clinical_doctors.map((item) => ({
            institute_id: item.institute_id.trim(),
            physician_name: item.physician_name.trim(),
          })),
        }
      : {}),
    ...(formData.value.sampling_config.score_filter
      ? { score_filter: { ...formData.value.sampling_config.score_filter } }
      : {}),
    ...(requiredCaseScope.value ? { case_scope: requiredCaseScope.value } : {}),
  }
  if (
    formData.value.sampling_method === 'count' ||
    formData.value.sampling_method === 'department_count'
  ) {
    samplingConfig.total = formData.value.sampling_config.total
    if (formData.value.sampling_method === 'count')
      samplingConfig.by_department = formData.value.sampling_config.by_department
  } else if (formData.value.sampling_method === 'percentage') {
    samplingConfig.percentage = formData.value.sampling_config.percentage
    samplingConfig.group_by =
      formData.value.sampling_config.group_by === 'department' ? 'department' : null
  } else if (formData.value.sampling_method === 'department_ratio') {
    samplingConfig.percentage = formData.value.sampling_config.percentage
    samplingConfig.max_per_group = formData.value.sampling_config.max_per_group
  }
  const start = formData.value.date_range?.start?.trim()
  const end = formData.value.date_range?.end?.trim()
  return {
    scene,
    rule_set_key: ruleSetKey,
    date_range: start || end ? { start: start || null, end: end || null } : null,
    department_filter: [...formData.value.department_filter],
    sampling_method: formData.value.sampling_method,
    sampling_config: samplingConfig,
    assign_method: formData.value.assign_method,
    assignee_config:
      formData.value.assign_method === 'by_original_reviewer' && formData.value.assign_fallback
        ? { fallback: formData.value.assign_fallback }
        : {},
  }
}

const handleSaveTemplate = () => {
  if (rangeMode.value === 'refs') {
    message.warning('指定病历集合不能保存为范围模板')
    return
  }
  const config = currentTemplateConfig()
  if (!config) {
    message.warning('请先填写有效的场景、规则集、抽样和分配配置')
    return
  }
  if (config.scene === 'running') {
    const rangeError = activeDateRangeError(formData.value.date_range)
    if (rangeError) {
      message.warning(rangeError)
      return
    }
  }
  emit('save-template', config)
}

const handleClose = () => {
  visible.value = false
  resetForm()
}

const resetForm = () => {
  currentStep.value = 0
  formData.value = {
    task_name: '',
    scene: null,
    rule_set_key: undefined,
    task_type: 'one_time',
    deadline: null,
    description: '',
    date_range: null,
    department_filter: [],
    sampling_method: 'all',
    sampling_config: {
      case_scope: undefined,
      score_filter: undefined,
      clinical_doctors: undefined,
      total: 50,
      percentage: 10,
      by_department: false,
      group_by: null,
      max_per_group: 50,
    },
    assign_method: 'by_ratio',
    assign_fallback: undefined,
  }
  rangeMode.value = 'date'
  dateRangeValue.value = null
  recordRefs.value = [blankRecordRef()]
}

const handleSubmit = async () => {
  if (submitting.value) return
  const taskName = formData.value.task_name.trim()
  const scene = formData.value.scene
  if (!taskName) {
    message.warning('请输入任务名称')
    return
  }
  if (!scene) {
    message.warning('请选择质控场景')
    return
  }
  if (ruleSetsError.value || ruleSetsLoading.value) {
    message.error(ruleSetsError.value || '规则集目录正在加载，请稍后重试')
    return
  }
  if (!matchingRuleSets.value.length) {
    message.warning(`${sceneLabel.value}暂无可用的匹配规则集，当前不能创建任务`)
    return
  }
  if (!selectedRuleSetIsValid.value || !formData.value.rule_set_key) {
    message.warning('请选择与质控场景匹配的规则集')
    return
  }
  if (rangeMode.value === 'refs' && recordRefsError.value) {
    message.warning(recordRefsError.value)
    return
  }
  if (!caseScopeSatisfied.value) {
    message.warning(scene === 'final' ? '请选择已出院病历范围' : '请选择当前在院病历范围')
    return
  }
  if (scene === 'final') {
    // 终末任务的候选池由出院日期窗决定，指定病历也须在窗口内。
    const rangeError = dischargedDateRangeError(
      formData.value.date_range?.start,
      formData.value.date_range?.end,
    )
    if (rangeError) {
      message.warning(rangeError)
      return
    }
  }
  if (scene === 'running' && rangeMode.value === 'date') {
    const rangeError = activeDateRangeError(formData.value.date_range)
    if (rangeError) {
      message.warning(rangeError)
      return
    }
  }
  if (formData.value.sampling_method === 'percentage' && !validSamplingGroup.value) {
    message.warning('当前仅支持按科室分组或不分组抽样')
    return
  }
  if (assignMethodError.value) {
    message.warning(assignMethodError.value)
    return
  }

  submitting.value = true
  try {
    const submitData: TaskCreateData = {
      task_name: taskName,
      scene,
      rule_set_key: formData.value.rule_set_key,
      task_type: 'one_time',
      deadline: formData.value.deadline?.format('YYYY-MM-DD'),
      sampling_method: rangeMode.value === 'refs' ? 'all' : formData.value.sampling_method,
      sampling_config: {
        ...(rangeMode.value !== 'refs' && formData.value.sampling_config.clinical_doctors
          ? {
              clinical_doctors: formData.value.sampling_config.clinical_doctors.map((item) => ({
                institute_id: item.institute_id.trim(),
                physician_name: item.physician_name.trim(),
              })),
            }
          : {}),
        ...(rangeMode.value !== 'refs' && formData.value.sampling_config.score_filter
          ? { score_filter: { ...formData.value.sampling_config.score_filter } }
          : {}),
        ...(requiredCaseScope.value ? { case_scope: requiredCaseScope.value } : {}),
        ...(rangeMode.value === 'refs'
          ? {}
          : formData.value.sampling_method === 'department_count'
            ? { total: formData.value.sampling_config.total }
            : formData.value.sampling_method === 'department_ratio'
              ? {
                  percentage: formData.value.sampling_config.percentage,
                  max_per_group: formData.value.sampling_config.max_per_group,
                }
              : formData.value.sampling_method === 'count'
                ? {
                    total: formData.value.sampling_config.total,
                    by_department: formData.value.sampling_config.by_department,
                  }
                : formData.value.sampling_method === 'percentage'
                  ? {
                      percentage: formData.value.sampling_config.percentage,
                      group_by: formData.value.sampling_config.group_by,
                    }
                  : {}),
      },
      assign_method: formData.value.assign_method,
    }
    if (formData.value.assign_method === 'by_original_reviewer' && formData.value.assign_fallback) {
      submitData.assignee_config = { fallback: formData.value.assign_fallback }
    }

    if (rangeMode.value === 'refs') {
      submitData.record_refs = normalizedRecordRefs.value.map((item) => ({ ...item }))
      if (scene === 'final' && formData.value.date_range?.start && formData.value.date_range?.end) {
        // 终末候选池由出院日期窗决定：指定病历须在窗口内，窗口随病历一并提交。
        submitData.date_range = {
          start: formData.value.date_range.start.trim(),
          end: formData.value.date_range.end.trim(),
        }
      }
    } else {
      const start = formData.value.date_range?.start?.trim()
      const end = formData.value.date_range?.end?.trim()
      if (start || end) {
        submitData.date_range = { start: start || undefined, end: end || undefined }
      }
      if (formData.value.department_filter.length > 0) {
        submitData.department_filter = [...formData.value.department_filter]
      }
    }

    const res = await createTask(submitData)
    if (res.success && res.data) {
      message.success(`任务「${formData.value.task_name}」创建成功`)
      emit('created', res.data)
      handleClose()
    } else {
      message.error(
        describeTaskAssignError(res.errorDetail, res.status) || res.message || '创建失败',
      )
    }
  } catch (err: unknown) {
    message.error(err instanceof Error ? err.message : '创建任务异常')
  } finally {
    submitting.value = false
  }
}
</script>
