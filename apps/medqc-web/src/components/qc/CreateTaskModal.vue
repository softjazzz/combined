<template>
  <a-modal
    :open="visible"
    title="新建质控任务"
    width="560px"
    :confirm-loading="submitting"
    :ok-button-props="{ disabled: !canSubmit }"
    :mask-closable="false"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <div class="py-2 space-y-5">
      <!-- 任务名称 -->
      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1.5">
          任务名称 <span class="text-rose-500">*</span>
        </label>
        <a-input
          v-model:value="form.task_name"
          placeholder="例如：2025年8月出院病历首页质控"
          size="large"
          class="!rounded-lg"
        />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1.5">
          质控规则集 <span class="text-rose-500">*</span>
        </label>
        <a-select
          v-model:value="form.rule_set_key"
          data-testid="legacy-task-rule-set-select"
          placeholder="请选择规则集"
          class="w-full"
          size="large"
          :loading="ruleSetsLoading"
          :disabled="ruleSetsLoading || !!ruleSetsError || !matchingRuleSets.length"
          :options="ruleSetOptions"
        />
        <a-alert v-if="ruleSetsError" type="error" :message="ruleSetsError" show-icon class="mt-2" />
        <a-alert
          v-else-if="!ruleSetsLoading && !matchingRuleSets.length"
          type="warning"
          message="当前场景暂无可用的匹配规则集，不能创建任务。"
          show-icon
          class="mt-2"
        />
      </div>

      <div v-if="scene === 'running'">
        <label class="block text-sm font-medium text-slate-700 mb-1.5">
          运行病历范围 <span class="text-rose-500">*</span>
        </label>
        <a-select
          v-model:value="form.case_scope"
          data-testid="legacy-task-case-scope-select"
          placeholder="请选择运行病历范围"
          class="w-full"
          size="large"
          :options="[{ value: 'active', label: '当前在院' }]"
        />
        <div class="text-xs text-slate-500 mt-2">
          出院未归档病历暂不可抽样。
        </div>
      </div>

      <!-- 日期范围 -->
      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1.5">入院日期范围</label>
        <a-range-picker
          v-model:value="form.dateRange"
          class="w-full !rounded-lg"
          size="large"
          :placeholder="['开始日期', '结束日期']"
        />
      </div>

      <!-- 科室筛选 -->
      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1.5">科室范围</label>
        <a-select
          v-model:value="form.department_filter"
          mode="multiple"
          placeholder="留空表示全部科室"
          class="w-full"
          size="large"
          :options="departmentOptions"
          allow-clear
        />
      </div>

      <!-- 抽样方式 -->
      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1.5">抽样方式</label>
        <a-radio-group
          v-model:value="form.sampling_method"
          class="w-full"
        >
          <a-radio-button
            value="all"
            class="!rounded-l-lg"
          >
            全部
          </a-radio-button>
          <a-radio-button value="count">
            按数量
          </a-radio-button>
          <a-radio-button
            value="percentage"
            class="!rounded-r-lg"
          >
            按比例
          </a-radio-button>
        </a-radio-group>
        <div
          v-if="form.sampling_method === 'count'"
          class="mt-2"
        >
          <a-input-number
            v-model:value="form.sampling_count"
            :min="1"
            :max="500"
            placeholder="抽样数量（上限 500）"
            class="w-full"
          />
        </div>
        <div
          v-if="form.sampling_method === 'percentage'"
          class="mt-2"
        >
          <a-slider
            v-model:value="form.sampling_pct"
            :min="1"
            :max="100"
            :tip-formatter="(v: number) => `${v}%`"
          />
        </div>
      </div>

      <!-- 截止日期 -->
      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1.5">质控截止日期</label>
        <a-date-picker
          v-model:value="form.deadline"
          class="w-full !rounded-lg"
          size="large"
          placeholder="选择截止日期（可选）"
        />
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, type PropType } from 'vue'
import { message } from 'ant-design-vue'
import {
  createQCTaskAndSample,
  getDepartmentList,
  type CreateTaskAndSampleData,
  type CreateTaskParams,
} from '@/api/qcAdmin'
import { getTaskRuleSets, type TaskRuleSetOption, type TaskScene } from '@/api/tasks'
import type { Dayjs } from 'dayjs'

const props = defineProps({
  visible: { type: Boolean, required: true },
  scene: {
    type: String as PropType<TaskScene>,
    required: true,
    validator: (value: string) => ['running', 'final', 'outpatient'].includes(value),
  },
})

const isTaskScene = (value: unknown): value is TaskScene =>
  typeof value === 'string' && ['running', 'final', 'outpatient'].includes(value)

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'created', data: CreateTaskAndSampleData): void
}>()

const submitting = ref(false)
const departmentOptions = ref<Array<{ label: string; value: string }>>([])
const ruleSets = ref<TaskRuleSetOption[]>([])
const ruleSetsLoading = ref(false)
const ruleSetsError = ref('')
let ruleSetRequestId = 0

const form = reactive({
  task_name: '',
  rule_set_key: undefined as string | undefined,
  case_scope: undefined as 'active' | undefined,
  dateRange: null as [Dayjs, Dayjs] | null,
  department_filter: [] as string[],
  sampling_method: 'all' as 'all' | 'count' | 'percentage',
  sampling_count: 50,
  sampling_pct: 20,
  deadline: null as Dayjs | null,
})

const matchingRuleSets = computed(() =>
  ruleSets.value.filter((item) => item.scope === props.scene && item.rule_set_key.trim()),
)
const ruleSetOptions = computed(() => matchingRuleSets.value.map((item) => ({
  value: item.rule_set_key,
  label: `${item.rule_set_name} (${item.rule_set_version})`,
})))
const selectedRuleSetIsValid = computed(() =>
  !ruleSetsLoading.value && !ruleSetsError.value &&
  matchingRuleSets.value.some((item) => item.rule_set_key === form.rule_set_key),
)
const canSubmit = computed(() =>
  !submitting.value && !!form.task_name.trim() && isTaskScene(props.scene) && selectedRuleSetIsValid.value &&
  (props.scene !== 'running' || form.case_scope === 'active'),
)

watch(() => [props.visible, props.scene] as const, async ([visible]) => {
  const requestId = ++ruleSetRequestId
  form.rule_set_key = undefined
  form.case_scope = undefined
  ruleSets.value = []
  ruleSetsError.value = ''
  if (!visible) {
    ruleSetsLoading.value = false
    return
  }
  ruleSetsLoading.value = true
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

/** 加载科室选项 */
const loadDepartments = async () => {
  const res = await getDepartmentList()
  if (res.success && res.data) {
    departmentOptions.value = res.data.map((d: any) => ({
      label: d.name,
      value: d.code,
    }))
  }
}

/** 提交创建 */
const handleSubmit = async () => {
  if (submitting.value) return
  if (!form.task_name.trim()) {
    message.warning('请输入任务名称')
    return
  }
  if (!isTaskScene(props.scene)) {
    message.warning('请选择有效的质控场景')
    return
  }
  if (!selectedRuleSetIsValid.value || !form.rule_set_key) {
    message.warning(ruleSetsError.value || '请选择与质控场景匹配的规则集')
    return
  }
  if (props.scene === 'running' && form.case_scope !== 'active') {
    message.warning('请选择当前在院病历范围')
    return
  }

  const params: CreateTaskParams = {
    task_name: form.task_name.trim(),
    scene: props.scene,
    rule_set_key: form.rule_set_key,
    sampling_method: form.sampling_method,
    department_filter: form.department_filter.length > 0 ? form.department_filter : undefined,
    deadline: form.deadline?.format('YYYY-MM-DD'),
  }

  // 日期范围
  if (form.dateRange && form.dateRange[0] && form.dateRange[1]) {
    params.date_range = {
      start: form.dateRange[0].format('YYYY-MM-DD'),
      end: form.dateRange[1].format('YYYY-MM-DD'),
    }
  }

  // 抽样配置
  if (form.sampling_method === 'count') {
    params.sampling_config = { total: form.sampling_count }
  } else if (form.sampling_method === 'percentage') {
    params.sampling_config = { percentage: form.sampling_pct }
  }
  if (props.scene === 'running' && form.case_scope === 'active') {
    params.sampling_config = { ...params.sampling_config, case_scope: 'active' }
  }

  submitting.value = true
  try {
    const res = await createQCTaskAndSample(params)
    if (res.success && res.data?.sampled) {
      message.success(res.message || `任务创建成功，已抽样 ${res.data.sampled_count} 条病历`)
      emit('created', res.data)
      emit('update:visible', false)
      resetForm()
    } else if (res.data?.task_id && !res.data.sampled) {
      message.warning(`任务已创建，抽样未完成：${res.message || '请在任务列表中继续处理'}`)
      emit('created', res.data)
      emit('update:visible', false)
      resetForm()
    } else {
      message.error(res.message || '创建失败')
    }
  } catch {
    message.error('创建任务失败，请重试')
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  emit('update:visible', false)
}

const resetForm = () => {
  form.task_name = ''
  form.rule_set_key = undefined
  form.case_scope = undefined
  form.dateRange = null
  form.department_filter = []
  form.sampling_method = 'all'
  form.sampling_count = 50
  form.sampling_pct = 20
  form.deadline = null
}

onMounted(loadDepartments)
</script>
