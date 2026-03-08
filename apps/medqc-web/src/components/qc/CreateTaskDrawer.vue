<template>
  <a-drawer
    v-model:open="visible"
    title="创建质控任务"
    :width="720"
    :bodyStyle="{ padding: '24px' }"
    @close="handleClose"
    :destroyOnClose="true"
  >
    <!-- 步骤条 -->
    <a-steps :current="currentStep" size="small" class="mb-8">
      <a-step title="基本信息" />
      <a-step title="病历范围" />
      <a-step title="抽样规则" />
      <a-step title="任务分配" />
      <a-step title="确认提交" />
    </a-steps>

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
            :disabledDate="(d: any) => d && d < Date.now() - 86400000"
            placeholder="选择截止日期"
          />
        </a-form-item>

        <a-form-item label="任务说明" >
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
        <a-form-item label="选择方式">
          <a-radio-group v-model:value="rangeMode">
            <a-radio-button value="date">按日期范围</a-radio-button>
            <a-radio-button value="ids">指定病案号</a-radio-button>
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
          <a-form-item label="病案号列表">
            <a-textarea
              v-model:value="recordIdsText"
              placeholder="每行输入一个病案号，例如：&#10;MR-2026-001&#10;MR-2026-002&#10;MR-2026-003"
              :rows="8"
            />
            <div class="text-xs text-gray-400 mt-1">
              已输入 {{ parsedRecordIds.length }} 个病案号
            </div>
          </a-form-item>
        </template>
      </a-form>
    </div>

    <!-- Step 3: 抽样规则 -->
    <div v-show="currentStep === 2">
      <a-form layout="vertical">
        <a-form-item label="抽样方式">
          <a-radio-group v-model:value="formData.sampling_method" class="w-full">
            <div class="grid grid-cols-3 gap-3">
              <div
                v-for="opt in samplingOptions"
                :key="opt.value"
                :class="[
                  'border rounded-xl p-4 cursor-pointer transition-all text-center',
                  formData.sampling_method === opt.value
                    ? 'border-blue-500 bg-blue-50 shadow-sm'
                    : 'border-gray-200 hover:border-blue-200'
                ]"
                @click="formData.sampling_method = opt.value"
              >
                <component :is="opt.icon" class="text-2xl mb-2" :class="formData.sampling_method === opt.value ? 'text-blue-600' : 'text-gray-400'" />
                <div class="font-medium text-sm">{{ opt.label }}</div>
                <div class="text-xs text-gray-400 mt-1">{{ opt.desc }}</div>
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
              :tipFormatter="(val: number) => `${val}%`"
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
              allowClear
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
            <a-radio value="keep">保持原有分配</a-radio>
            <a-radio value="by_department">按科室分配</a-radio>
            <a-radio value="by_ratio">按比例均分</a-radio>
          </a-radio-group>
        </a-form-item>

        <template v-if="formData.assign_method !== 'keep'">
          <a-form-item label="质控员列表">
            <a-select
              v-model:value="selectedAssignees"
              mode="multiple"
              placeholder="选择或搜索质控员"
              style="width: 100%"
              :options="assigneeOptions"
            />
          </a-form-item>
        </template>

        <a-alert
          v-if="formData.assign_method === 'keep'"
          message="保持原有分配"
          description="任务将保持现有的科室-质控员分配关系，不做额外调整。"
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
        <a-descriptions-item label="任务类型">
          {{ formData.task_type === 'one_time' ? '单次任务' : '定期任务' }}
        </a-descriptions-item>
        <a-descriptions-item label="截止日期">
          {{ formData.deadline || '无截止日期' }}
        </a-descriptions-item>
        <a-descriptions-item label="病历范围">
          <template v-if="rangeMode === 'date'">
            日期范围 + {{ formData.department_filter?.length || 0 }} 个科室筛选
          </template>
          <template v-else>
            指定 {{ parsedRecordIds.length }} 个病案号
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
        <a-button v-if="currentStep > 0" @click="prevStep">
          上一步
        </a-button>
        <div v-else></div>

        <div class="flex gap-3">
          <a-button @click="handleClose">取消</a-button>
          <a-button
            v-if="currentStep < 4"
            type="primary"
            @click="nextStep"
            :disabled="!canProceed"
          >
            下一步
          </a-button>
          <a-button
            v-else
            type="primary"
            @click="handleSubmit"
            :loading="submitting"
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
} from '@ant-design/icons-vue'
import { createTask } from '@/api/tasks'

// ============= Props & Emits =============
const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'created', task: any): void
}>()

// ============= 状态 =============
const visible = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val),
})

const currentStep = ref(0)
const submitting = ref(false)
const rangeMode = ref<'date' | 'ids'>('date')
const dateRangeValue = ref<any>(null)
const recordIdsText = ref('')
const selectedAssignees = ref<string[]>([])

// 表单数据
const formData = ref({
  task_name: '',
  task_type: 'one_time' as 'one_time' | 'scheduled',
  deadline: null as string | null,
  description: '',
  date_range: null as { start?: string; end?: string } | null,
  department_filter: [] as string[],
  record_ids: [] as string[],
  sampling_method: 'all' as 'all' | 'count' | 'percentage',
  sampling_config: {
    total: 50,
    percentage: 10,
    by_department: false,
    group_by: null as string | null,
  },
  assign_method: 'keep' as 'keep' | 'by_department' | 'by_ratio',
  assignee_config: {} as Record<string, any>,
})

// ============= 选项配置 =============
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

const assigneeOptions = [
  { value: 'qc_user_1', label: '王质控' },
  { value: 'qc_user_2', label: '张质控' },
  { value: 'qc_user_3', label: '李质控' },
  { value: 'qc_user_4', label: '赵质控' },
  { value: 'qc_user_5', label: '陈质控' },
]

const samplingOptions = [
  { value: 'all', label: '全部', desc: '取全部匹配病历', icon: DatabaseOutlined },
  { value: 'count', label: '按数量', desc: '随机抽取N条', icon: NumberOutlined },
  { value: 'percentage', label: '按比例', desc: '各组取X%', icon: PercentageOutlined },
]

// ============= 计算属性 =============
const parsedRecordIds = computed(() => {
  return recordIdsText.value
    .split('\n')
    .map(id => id.trim())
    .filter(id => id.length > 0)
})

const canProceed = computed(() => {
  switch (currentStep.value) {
    case 0: return formData.value.task_name.trim().length > 0
    case 1: return rangeMode.value === 'ids' ? parsedRecordIds.value.length > 0 : true
    case 2: return true
    case 3: return true
    default: return true
  }
})

const samplingLabel = computed(() => {
  const method = formData.value.sampling_method
  if (method === 'all') return '全部病历'
  if (method === 'count') return `随机抽取 ${formData.value.sampling_config.total} 条`
  if (method === 'percentage') return `各组抽取 ${formData.value.sampling_config.percentage}%`
  return method
})

const assignLabel = computed(() => {
  const method = formData.value.assign_method
  if (method === 'keep') return '保持原有分配'
  if (method === 'by_department') return '按科室分配'
  if (method === 'by_ratio') return `按比例均分给 ${selectedAssignees.value.length} 名质控员`
  return method
})

// ============= 方法 =============
const nextStep = () => {
  if (currentStep.value < 4) currentStep.value++
}

const prevStep = () => {
  if (currentStep.value > 0) currentStep.value--
}

const handleDateRangeChange = (_: any, dateStrings: [string, string]) => {
  formData.value.date_range = {
    start: dateStrings[0],
    end: dateStrings[1],
  }
}

const handleClose = () => {
  visible.value = false
  resetForm()
}

const resetForm = () => {
  currentStep.value = 0
  formData.value = {
    task_name: '',
    task_type: 'one_time',
    deadline: null,
    description: '',
    date_range: null,
    department_filter: [],
    record_ids: [],
    sampling_method: 'all',
    sampling_config: { total: 50, percentage: 10, by_department: false, group_by: null },
    assign_method: 'keep',
    assignee_config: {},
  }
  rangeMode.value = 'date'
  dateRangeValue.value = null
  recordIdsText.value = ''
  selectedAssignees.value = []
}

const handleSubmit = async () => {
  submitting.value = true
  try {
    // 处理病案号
    if (rangeMode.value === 'ids') {
      formData.value.record_ids = parsedRecordIds.value
    }

    // 处理分配人员
    if (formData.value.assign_method !== 'keep' && selectedAssignees.value.length > 0) {
      formData.value.assignee_config = {
        assignees: selectedAssignees.value.map(id => {
          const opt = assigneeOptions.find(o => o.value === id)
          return { user_id: id, user_name: opt?.label || id }
        }),
      }
    }

    // 处理截止日期
    const submitData = {
      ...formData.value,
      deadline: formData.value.deadline
        ? (typeof formData.value.deadline === 'string'
          ? formData.value.deadline
          : (formData.value.deadline as any).format?.('YYYY-MM-DD'))
        : undefined,
      sampling_config: {
        ...(formData.value.sampling_method === 'count'
          ? { total: formData.value.sampling_config.total, by_department: formData.value.sampling_config.by_department }
          : formData.value.sampling_method === 'percentage'
            ? { percentage: formData.value.sampling_config.percentage, group_by: formData.value.sampling_config.group_by }
            : {}),
      },
    }

    const res = await createTask(submitData)
    if (res.success) {
      message.success(`任务「${formData.value.task_name}」创建成功`)
      emit('created', res.data)
      handleClose()
    } else {
      message.error(res.message || '创建失败')
    }
  } catch (err: any) {
    message.error(err?.message || '创建任务异常')
  } finally {
    submitting.value = false
  }
}
</script>
