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
    <a-steps
      :current="currentStep"
      size="small"
      class="mb-8"
    >
      <a-step title="基本信息" />
      <a-step title="病历范围" />
      <a-step title="抽样规则" />
      <a-step title="任务分配" />
      <a-step title="确认提交" />
    </a-steps>

    <!-- Step 1: 基本信息 -->
    <div v-show="currentStep === 0">
      <a-form
        :model="formData"
        layout="vertical"
      >
        <a-form-item
          label="任务名称"
          required
        >
          <a-input
            v-model:value="formData.task_name"
            placeholder="例如：2026年3月终末病历质控"
            :maxlength="100"
            show-count
          />
        </a-form-item>

        <a-form-item
          label="质控场景"
          required
        >
          <a-select
            v-model:value="formData.scene"
            data-testid="task-scene-select"
            placeholder="请选择质控场景"
            :options="sceneOptions"
          />
        </a-form-item>

        <a-form-item
          label="质控规则集"
          required
        >
          <a-select
            v-model:value="formData.rule_set_key"
            data-testid="task-rule-set-select"
            placeholder="请选择规则集"
            :loading="ruleSetsLoading"
            :disabled="!formData.scene || ruleSetsLoading || !!ruleSetsError || !matchingRuleSets.length"
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

        <a-form-item label="任务类型">
          <a-radio-group v-model:value="formData.task_type">
            <a-radio-button value="one_time">
              <ThunderboltOutlined /> 单次任务
            </a-radio-button>
            <a-radio-button value="scheduled">
              <ClockCircleOutlined /> 定期任务
            </a-radio-button>
          </a-radio-group>
        </a-form-item>

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
          v-if="formData.scene === 'running'"
          label="运行病历范围"
          required
        >
          <a-select
            v-model:value="formData.sampling_config.case_scope"
            data-testid="task-case-scope-select"
            placeholder="请选择运行病历范围"
            :options="[{ value: 'active', label: '当前在院' }]"
          />
          <div class="text-xs text-gray-500 mt-2">
            出院未归档病历暂不可抽样。
          </div>
        </a-form-item>
        <a-form-item label="选择方式">
          <a-radio-group v-model:value="rangeMode">
            <a-radio-button value="date">
              按日期范围
            </a-radio-button>
            <a-radio-button value="refs">
              指定病历
            </a-radio-button>
          </a-radio-group>
        </a-form-item>

        <template v-if="rangeMode === 'date'">
          <a-form-item label="日期范围">
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
        </template>

        <template v-else>
          <a-form-item
            label="病历坐标"
            required
          >
            <div class="hidden sm:grid grid-cols-[repeat(3,minmax(0,1fr))_36px] gap-2 text-xs text-gray-500 mb-2">
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
            <a-button @click="addRecordRef">
              <PlusOutlined /> 添加病历
            </a-button>
            <div
              v-if="recordRefsError"
              class="text-xs text-red-500 mt-2"
            >
              {{ recordRefsError }}
            </div>
            <div
              v-else
              class="text-xs text-gray-500 mt-2"
            >
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
                @click="formData.sampling_method = opt.value"
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

        <template v-if="formData.sampling_method === 'count'">
          <a-form-item label="抽样数量">
            <a-input-number
              v-model:value="formData.sampling_config.total"
              :min="1"
              :max="10000"
              style="width: 100%"
              placeholder="输入要抽取的病历数量"
            />
          </a-form-item>
          <a-form-item>
            <a-checkbox v-model:checked="formData.sampling_config.by_department">
              按科室均匀分配抽样数量
            </a-checkbox>
          </a-form-item>
        </template>

        <template v-if="formData.sampling_method === 'percentage'">
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
          <a-form-item label="分组依据">
            <a-select
              v-model:value="formData.sampling_config.group_by"
              placeholder="选择分组方式"
              style="width: 100%"
              :options="[
                { value: 'department', label: '按科室' },
                { value: 'doctor_name', label: '按主治医生' },
              ]"
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
          <a-radio-group v-model:value="formData.assign_method">
            <a-radio value="by_ratio">
              按比例均分
            </a-radio>
            <a-radio value="keep" disabled>
              保持原有分配（暂不可用）
            </a-radio>
            <a-radio value="by_department" disabled>
              按科室分配（暂不可用）
            </a-radio>
          </a-radio-group>
        </a-form-item>

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
      <a-descriptions
        title="任务概览"
        bordered
        :column="1"
        size="small"
      >
        <a-descriptions-item label="任务名称">
          {{ formData.task_name || '(未设置)' }}
        </a-descriptions-item>
        <a-descriptions-item label="任务类型">
          {{ formData.task_type === 'one_time' ? '单次任务' : '定期任务' }}
        </a-descriptions-item>
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
            {{ formData.scene === 'running' && formData.sampling_config.case_scope === 'active' ? '当前在院 · ' : '' }}日期范围 + {{ formData.department_filter?.length || 0 }} 个科室筛选
          </template>
          <template v-else>
            {{ formData.scene === 'running' && formData.sampling_config.case_scope === 'active' ? '当前在院 · ' : '' }}指定 {{ normalizedRecordRefs.length }} 条病历
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
        <a-button
          v-if="currentStep > 0"
          @click="prevStep"
        >
          上一步
        </a-button>
        <div v-else />

        <div class="flex gap-3">
          <a-button @click="handleClose">
            取消
          </a-button>
          <a-button
            v-if="currentStep < 4"
            type="primary"
            :disabled="!canProceed"
            @click="nextStep"
          >
            下一步
          </a-button>
          <a-button
            v-else
            type="primary"
            :loading="submitting"
            @click="handleSubmit"
          >
            <CheckOutlined /> 创建任务
          </a-button>
        </div>
      </div>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  ThunderboltOutlined,
  ClockCircleOutlined,
  CheckOutlined,
  DatabaseOutlined,
  NumberOutlined,
  PercentageOutlined,
  PlusOutlined,
  DeleteOutlined,
} from '@ant-design/icons-vue'
import { createTask, getTaskRuleSets } from '@/api/tasks'
import type { TaskCaseRef, TaskCreateData, TaskItem, TaskRuleSetOption, TaskScene } from '@/api/tasks'
import type { Dayjs } from 'dayjs'

// ============= Props & Emits =============
const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'created', task: TaskItem): void
}>()

// ============= 状态 =============
const visible = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val),
})

const currentStep = ref(0)
const submitting = ref(false)
const rangeMode = ref<'date' | 'refs'>('date')
const dateRangeValue = ref<[Dayjs, Dayjs] | null>(null)
const blankRecordRef = (): TaskCaseRef => ({ institute_id: '', patient_id: '', visit_id: '' })
const recordRefs = ref<TaskCaseRef[]>([blankRecordRef()])
const ruleSets = ref<TaskRuleSetOption[]>([])
const ruleSetsLoading = ref(false)
const ruleSetsError = ref('')
let ruleSetRequestId = 0

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
  sampling_method: 'all' as 'all' | 'count' | 'percentage',
  sampling_config: {
    case_scope: undefined as 'active' | undefined,
    total: 50,
    percentage: 10,
    by_department: false,
    group_by: null as string | null,
  },
  assign_method: 'by_ratio' as 'keep' | 'by_department' | 'by_ratio',
})

// ============= 选项配置 =============
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
  value: 'all' | 'count' | 'percentage'
  label: string
  desc: string
  icon: unknown
}> = [
  { value: 'all', label: '全部', desc: '取全部匹配病历', icon: DatabaseOutlined },
  { value: 'count', label: '按数量', desc: '随机抽取N条', icon: NumberOutlined },
  { value: 'percentage', label: '按比例', desc: '各组取X%', icon: PercentageOutlined },
]

// ============= 计算属性 =============
const normalizedRecordRefs = computed(() => recordRefs.value.map((item) => ({
  institute_id: item.institute_id.trim(),
  patient_id: item.patient_id.trim(),
  visit_id: item.visit_id.trim(),
})))
const recordRefsError = computed(() => {
  if (!recordRefs.value.length || normalizedRecordRefs.value.every((item) =>
    !item.institute_id && !item.patient_id && !item.visit_id)) return '请至少填写一条完整的病历坐标'
  if (normalizedRecordRefs.value.some((item) =>
    !item.institute_id || !item.patient_id || !item.visit_id)) return '每条病历均须填写机构 ID、患者 ID 和就诊 ID'
  const keys = normalizedRecordRefs.value.map((item) =>
    JSON.stringify([item.institute_id, item.patient_id, item.visit_id]))
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
const selectedRuleSetLabel = computed(() =>
  ruleSetSelectOptions.value.find((item) => item.value === formData.value.rule_set_key)?.label || '(未选择)',
)
const selectedRuleSetIsValid = computed(() =>
  !ruleSetsLoading.value && !ruleSetsError.value &&
  matchingRuleSets.value.some((item) => item.rule_set_key === formData.value.rule_set_key),
)

const canProceed = computed(() => {
  switch (currentStep.value) {
    case 0:
      return formData.value.task_name.trim().length > 0 &&
        formData.value.scene !== null && selectedRuleSetIsValid.value
    case 1:
      return (formData.value.scene !== 'running' || formData.value.sampling_config.case_scope === 'active') &&
        (rangeMode.value !== 'refs' || !recordRefsError.value)
    case 2:
      return true
    case 3:
      return formData.value.assign_method === 'by_ratio'
    default:
      return true
  }
})

const sceneLabel = computed(() => {
  return sceneOptions.find((option) => option.value === formData.value.scene)?.label || '(未选择)'
})

const samplingLabel = computed(() => {
  const method = formData.value.sampling_method
  if (method === 'all') return '全部病历'
  if (method === 'count') return `随机抽取 ${formData.value.sampling_config.total} 条`
  if (method === 'percentage') return `各组抽取 ${formData.value.sampling_config.percentage}%`
  return method
})

const assignLabel = computed(() => {
  return formData.value.assign_method === 'by_ratio' ? '按比例均分（抽样后选人）' : '暂不可用'
})

watch(() => formData.value.scene, () => {
  formData.value.rule_set_key = undefined
  formData.value.sampling_config.case_scope = undefined
})

watch(() => props.open, async (open) => {
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
    ruleSets.value = result.data.items.filter((item) =>
      typeof item.rule_set_key === 'string' &&
      typeof item.rule_set_name === 'string' &&
      typeof item.rule_set_version === 'string' &&
      typeof item.scope === 'string',
    )
  } catch {
    if (requestId === ruleSetRequestId) ruleSetsError.value = '规则集目录加载失败，请稍后重试'
  } finally {
    if (requestId === ruleSetRequestId) ruleSetsLoading.value = false
  }
}, { immediate: true })

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
  formData.value.date_range = start || end ? { start: start || undefined, end: end || undefined } : null
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
    sampling_config: { case_scope: undefined, total: 50, percentage: 10, by_department: false, group_by: null },
    assign_method: 'by_ratio',
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
  if (scene === 'running' && formData.value.sampling_config.case_scope !== 'active') {
    message.warning('请选择当前在院病历范围')
    return
  }
  if (formData.value.assign_method !== 'by_ratio') {
    message.warning('当前仅支持按比例均分，抽样后再选择质控员')
    return
  }

  submitting.value = true
  try {
    const submitData: TaskCreateData = {
      task_name: taskName,
      scene,
      rule_set_key: formData.value.rule_set_key,
      task_type: formData.value.task_type,
      deadline: formData.value.deadline?.format('YYYY-MM-DD'),
      sampling_method: formData.value.sampling_method,
      sampling_config: {
        ...(scene === 'running' && formData.value.sampling_config.case_scope === 'active'
          ? { case_scope: 'active' }
          : {}),
        ...(formData.value.sampling_method === 'count'
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

    if (rangeMode.value === 'refs') {
      submitData.record_refs = normalizedRecordRefs.value.map((item) => ({ ...item }))
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
      message.error(res.message || '创建失败')
    }
  } catch (err: unknown) {
    message.error(err instanceof Error ? err.message : '创建任务异常')
  } finally {
    submitting.value = false
  }
}
</script>
