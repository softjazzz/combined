<template>
  <a-drawer
    :open="open"
    title="任务模板"
    :width="'min(760px, 100vw)'"
    :destroy-on-close="true"
    @close="closeDrawer"
  >
    <a-alert
      type="info"
      show-icon
      class="mb-4"
      message="模板仅保存创建配置"
      description="不会保存任务名称、截止日期、病例身份、受领人或运行结果；套用后仍须填写动态内容并通过当前创建校验。"
    />

    <div v-if="editorOpen" data-testid="task-template-editor">
      <div class="mb-4 flex items-center justify-between gap-3">
        <h3 class="m-0 text-base font-semibold text-gray-800">
          {{ editingTemplate ? '编辑模板' : '新建模板' }}
        </h3>
        <a-button :disabled="saving" @click="closeEditor"> 返回列表 </a-button>
      </div>
      <a-form layout="vertical">
        <a-form-item label="模板名称" required>
          <a-input v-model:value="editor.name" :maxlength="50" show-count />
        </a-form-item>
        <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
          <a-form-item label="质控场景" required>
            <a-select
              v-model:value="editor.scene"
              data-testid="template-scene"
              :options="sceneOptions"
              @change="handleEditorSceneChange"
            />
          </a-form-item>
          <a-form-item label="规则集" required>
            <a-select
              v-model:value="editor.rule_set_key"
              data-testid="template-rule-set"
              :loading="ruleSetsLoading"
              :disabled="ruleSetsLoading || !!ruleSetsError || !matchingRuleSets.length"
              :options="
                matchingRuleSets.map((item) => ({
                  value: item.rule_set_key,
                  label: `${item.rule_set_name} (${item.rule_set_version})`,
                }))
              "
            />
          </a-form-item>
        </div>
        <a-alert
          v-if="ruleSetsError"
          type="error"
          show-icon
          class="mb-4"
          :message="ruleSetsError"
        />
        <a-alert
          v-else-if="!ruleSetsLoading && !matchingRuleSets.length"
          type="warning"
          show-icon
          class="mb-4"
          message="当前场景暂无可用规则集"
        />
        <a-form-item label="绝对日期范围">
          <a-range-picker v-model:value="editor.dateRange" style="width: 100%" />
        </a-form-item>
        <a-form-item label="科室筛选">
          <a-select
            v-model:value="editor.department_filter"
            mode="tags"
            :max-tag-count="5"
            placeholder="不填表示全部科室"
          />
        </a-form-item>
        <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
          <a-form-item label="抽样方式">
            <a-select v-model:value="editor.sampling_method" :options="samplingOptions" />
          </a-form-item>
          <a-form-item v-if="editor.sampling_method === 'count'" label="抽样数量" required>
            <a-input-number
              v-model:value="editor.total"
              :min="1"
              :max="10000"
              style="width: 100%"
            />
          </a-form-item>
          <a-form-item
            v-else-if="editor.sampling_method === 'percentage'"
            label="抽样比例"
            required
          >
            <a-input-number
              v-model:value="editor.percentage"
              :min="1"
              :max="100"
              style="width: 100%"
              addon-after="%"
            />
          </a-form-item>
        </div>
        <a-checkbox
          v-if="editor.sampling_method === 'count'"
          v-model:checked="editor.by_department"
          class="mb-4"
        >
          按科室均匀抽样
        </a-checkbox>
        <a-form-item v-if="editor.sampling_method === 'percentage'" label="分组依据">
          <a-select
            v-model:value="editor.group_by"
            allow-clear
            :options="[{ value: 'department', label: '按科室' }]"
          />
        </a-form-item>
        <a-form-item label="分配方式">
          <a-select v-model:value="editor.assign_method" :options="assignOptions" />
        </a-form-item>
        <a-form-item
          v-if="editor.assign_method === 'by_original_reviewer'"
          label="无原质控员时"
          required
        >
          <a-radio-group v-model:value="editor.fallback">
            <a-radio value="by_ratio"> 按比例分配 </a-radio>
            <a-radio value="reject"> 拒绝分配 </a-radio>
          </a-radio-group>
        </a-form-item>
        <a-alert v-if="saveError" type="error" show-icon class="mb-4" :message="saveError" />
      </a-form>
      <div class="flex justify-end gap-3 border-t border-gray-100 pt-4">
        <a-button :disabled="saving" @click="closeEditor"> 取消 </a-button>
        <a-button
          type="primary"
          :loading="saving"
          data-testid="save-task-template"
          @click="saveTemplate"
        >
          保存模板
        </a-button>
      </div>
    </div>

    <div v-else>
      <div class="mb-4 flex items-center justify-between gap-3">
        <span class="text-sm text-gray-500">{{ templates.length }} / {{ maxTemplates }}</span>
        <a-button
          type="primary"
          :disabled="loading || templates.length >= maxTemplates"
          @click="startCreate"
        >
          <PlusOutlined /> 新建模板
        </a-button>
      </div>
      <a-alert v-if="loadError" type="error" show-icon class="mb-4" :message="loadError">
        <template #action>
          <a-button size="small" :loading="loading" @click="loadTemplates"> 重试 </a-button>
        </template>
      </a-alert>
      <div v-if="loading" class="py-12 text-center">
        <a-spin />
      </div>
      <a-empty v-else-if="!templates.length && !loadError" description="暂无任务模板" />
      <div v-else class="space-y-3">
        <div
          v-for="template in templates"
          :key="template.id"
          class="rounded-lg border border-gray-200 bg-white p-4"
          :data-testid="`task-template-${template.id}`"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="truncate font-medium text-gray-800">{{ template.name }}</span>
                <a-tag :color="template.usable ? 'green' : 'orange'">
                  {{ template.usable ? '可套用' : '不可用' }}
                </a-tag>
              </div>
              <p v-if="template.config" class="mb-0 mt-2 text-xs text-gray-500">
                {{ sceneLabel(template.config.scene) }} · {{ template.config.rule_set_key }} ·
                {{ samplingLabel(template.config) }}
              </p>
              <p v-else class="mb-0 mt-2 text-xs text-amber-700">
                {{ template.unavailable_reason || '模板配置当前不可用' }}
              </p>
            </div>
            <div class="flex gap-2">
              <a-button
                size="small"
                :disabled="!template.usable || !template.config"
                @click="applyTemplate(template)"
              >
                套用
              </a-button>
              <a-button
                size="small"
                title="编辑模板"
                aria-label="编辑模板"
                @click="startEdit(template)"
              >
                <EditOutlined />
              </a-button>
              <a-button
                danger
                size="small"
                title="删除模板"
                aria-label="删除模板"
                @click="confirmDelete(template)"
              >
                <DeleteOutlined />
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { sceneCaseScope } from '@/utils/taskCaseScope'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { Modal, message } from 'ant-design-vue'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons-vue'
import dayjs, { type Dayjs } from 'dayjs'
import {
  createTaskTemplate,
  deleteTaskTemplate,
  getTaskRuleSets,
  getTaskTemplates,
  updateTaskTemplate,
} from '@/api/tasks'
import type {
  AssignFallback,
  SamplingMethod,
  TaskAssignableMethod,
  TaskRuleSetOption,
  TaskScene,
  TaskTemplate,
  TaskTemplateConfig,
} from '@/api/tasks'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  open: boolean
  seedConfig?: TaskTemplateConfig | null
}>()

const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
  (event: 'apply', config: TaskTemplateConfig): void
}>()

interface TemplateEditor {
  name: string
  scene: TaskScene
  rule_set_key: string
  dateRange: [Dayjs, Dayjs] | null
  department_filter: string[]
  sampling_method: SamplingMethod
  total: number
  percentage: number
  by_department: boolean
  group_by: 'department' | undefined
  assign_method: TaskAssignableMethod
  fallback: AssignFallback | undefined
}

const authStore = useAuthStore()
const templates = ref<TaskTemplate[]>([])
const maxTemplates = ref(20)
const loading = ref(false)
const loadError = ref('')
const ruleSets = ref<TaskRuleSetOption[]>([])
const ruleSetsLoading = ref(false)
const ruleSetsError = ref('')
const editorOpen = ref(false)
const editingTemplate = ref<TaskTemplate | null>(null)
const saving = ref(false)
const saveError = ref('')
const seedConsumed = ref(false)
let loadRequestId = 0

const editor = reactive<TemplateEditor>({
  name: '',
  scene: 'final',
  rule_set_key: '',
  dateRange: null,
  department_filter: [],
  sampling_method: 'all',
  total: 50,
  percentage: 10,
  by_department: false,
  group_by: undefined,
  assign_method: 'by_ratio',
  fallback: undefined,
})

const sceneOptions = [
  { value: 'running', label: '运行病历' },
  { value: 'final', label: '终末病历' },
  { value: 'outpatient', label: '门急诊病历' },
]
const samplingOptions = [
  { value: 'all', label: '全部' },
  { value: 'count', label: '按数量' },
  { value: 'percentage', label: '按比例' },
]
const assignOptions = [
  { value: 'by_ratio', label: '按比例均分' },
  { value: 'by_original_reviewer', label: '按原质控员' },
  { value: 'by_department', label: '按科室' },
]
const matchingRuleSets = computed(() =>
  ruleSets.value.filter((item) => item.scope === editor.scene),
)

const sceneLabel = (scene: TaskScene) =>
  ({ running: '运行', final: '终末', outpatient: '门急诊' })[scene]
const samplingLabel = (config: TaskTemplateConfig) => {
  if (config.sampling_method === 'count') return `抽取 ${config.sampling_config.total ?? '未知'} 条`
  if (config.sampling_method === 'percentage')
    return `抽取 ${config.sampling_config.percentage ?? '未知'}%`
  return '全部病历'
}

function isTaskTemplateConfig(value: unknown): value is TaskTemplateConfig {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return (
    (item.scene === 'running' || item.scene === 'final' || item.scene === 'outpatient') &&
    typeof item.rule_set_key === 'string' &&
    !!item.rule_set_key.trim() &&
    (item.date_range === null || typeof item.date_range === 'object') &&
    Array.isArray(item.department_filter) &&
    item.department_filter.every((entry) => typeof entry === 'string') &&
    (item.sampling_method === 'all' ||
      item.sampling_method === 'count' ||
      item.sampling_method === 'percentage') &&
    !!item.sampling_config &&
    typeof item.sampling_config === 'object' &&
    (item.assign_method === 'by_ratio' ||
      item.assign_method === 'by_original_reviewer' ||
      item.assign_method === 'by_department') &&
    !!item.assignee_config &&
    typeof item.assignee_config === 'object'
  )
}

function isTaskTemplate(value: unknown): value is TaskTemplate {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return (
    typeof item.id === 'string' &&
    !!item.id.trim() &&
    typeof item.name === 'string' &&
    !!item.name.trim() &&
    typeof item.usable === 'boolean' &&
    Number.isInteger(item.version) &&
    Number(item.version) > 0 &&
    typeof item.created_at === 'string' &&
    typeof item.updated_at === 'string' &&
    (item.config === null || isTaskTemplateConfig(item.config)) &&
    (item.unavailable_reason === null || typeof item.unavailable_reason === 'string') &&
    (item.usable ? isTaskTemplateConfig(item.config) : true)
  )
}

function cloneConfig(config: TaskTemplateConfig): TaskTemplateConfig {
  return {
    scene: config.scene,
    rule_set_key: config.rule_set_key,
    date_range: config.date_range ? { ...config.date_range } : null,
    department_filter: [...config.department_filter],
    sampling_method: config.sampling_method,
    sampling_config: { ...config.sampling_config },
    assign_method: config.assign_method,
    assignee_config: { ...config.assignee_config },
  }
}

function defaultConfig(): TaskTemplateConfig {
  const ruleSet = ruleSets.value.find((item) => item.scope === 'final')
  return {
    scene: 'final',
    rule_set_key: ruleSet?.rule_set_key || '',
    date_range: null,
    department_filter: [],
    sampling_method: 'all',
    sampling_config: {},
    assign_method: 'by_ratio',
    assignee_config: {},
  }
}

function fillEditor(config: TaskTemplateConfig, name = '') {
  editor.name = name
  editor.scene = config.scene
  editor.rule_set_key = config.rule_set_key
  const start = config.date_range?.start
  const end = config.date_range?.end
  editor.dateRange = start && end ? [dayjs(start), dayjs(end)] : null
  editor.department_filter = [...config.department_filter]
  editor.sampling_method = config.sampling_method
  editor.total = config.sampling_config.total ?? 50
  editor.percentage = config.sampling_config.percentage ?? 10
  editor.by_department = config.sampling_config.by_department ?? false
  editor.group_by = config.sampling_config.group_by === 'department' ? 'department' : undefined
  editor.assign_method = config.assign_method
  editor.fallback = config.assignee_config.fallback
}

async function loadTemplates() {
  const requestId = ++loadRequestId
  const ownerId = authStore.user?.id
  if (!props.open || !ownerId) {
    templates.value = []
    loadError.value = ownerId ? '' : '当前用户身份不可用'
    return
  }
  loading.value = true
  ruleSetsLoading.value = true
  loadError.value = ''
  ruleSetsError.value = ''
  const [templateResult, ruleSetResult] = await Promise.all([getTaskTemplates(), getTaskRuleSets()])
  if (requestId !== loadRequestId || authStore.user?.id !== ownerId) return
  if (
    !templateResult.success ||
    !Array.isArray(templateResult.data?.items) ||
    !templateResult.data.items.every(isTaskTemplate)
  ) {
    templates.value = []
    loadError.value = templateResult.message || '任务模板加载失败'
  } else {
    templates.value = templateResult.data.items
    maxTemplates.value =
      Number.isInteger(templateResult.data.max_templates) && templateResult.data.max_templates > 0
        ? templateResult.data.max_templates
        : 20
  }
  if (!ruleSetResult.success || !Array.isArray(ruleSetResult.data?.items)) {
    ruleSets.value = []
    ruleSetsError.value = ruleSetResult.message || '规则集目录加载失败'
  } else {
    ruleSets.value = ruleSetResult.data.items.filter(
      (item) =>
        typeof item.rule_set_key === 'string' &&
        !!item.rule_set_key.trim() &&
        typeof item.rule_set_name === 'string' &&
        typeof item.rule_set_version === 'string' &&
        (item.scope === 'running' || item.scope === 'final' || item.scope === 'outpatient'),
    )
    if (ruleSets.value.length !== ruleSetResult.data.items.length) {
      ruleSets.value = []
      ruleSetsError.value = '规则集目录响应格式无效'
    }
  }
  loading.value = false
  ruleSetsLoading.value = false
  if (props.seedConfig && !seedConsumed.value) {
    seedConsumed.value = true
    fillEditor(cloneConfig(props.seedConfig))
    editorOpen.value = true
  }
}

function startCreate() {
  editingTemplate.value = null
  fillEditor(props.seedConfig ? cloneConfig(props.seedConfig) : defaultConfig())
  saveError.value = ''
  editorOpen.value = true
}

function startEdit(template: TaskTemplate) {
  editingTemplate.value = template
  fillEditor(template.config ? cloneConfig(template.config) : defaultConfig(), template.name)
  saveError.value = ''
  editorOpen.value = true
}

function closeEditor() {
  if (saving.value) return
  editorOpen.value = false
  editingTemplate.value = null
  saveError.value = ''
}

function handleEditorSceneChange() {
  editor.rule_set_key = matchingRuleSets.value[0]?.rule_set_key || ''
}

function editorConfig(): TaskTemplateConfig | null {
  const name = editor.name.trim()
  if (!name) {
    saveError.value = '请输入模板名称'
    return null
  }
  if (!matchingRuleSets.value.some((item) => item.rule_set_key === editor.rule_set_key)) {
    saveError.value = '请选择与场景匹配的当前可用规则集'
    return null
  }
  if (editor.assign_method === 'by_original_reviewer' && !editor.fallback) {
    saveError.value = '请选择无原质控员时的处理方式'
    return null
  }
  const samplingConfig: TaskTemplateConfig['sampling_config'] = {
    ...(sceneCaseScope(editor.scene) ? { case_scope: sceneCaseScope(editor.scene) } : {}),
  }
  if (editor.sampling_method === 'count') {
    samplingConfig.total = editor.total
    samplingConfig.by_department = editor.by_department
  } else if (editor.sampling_method === 'percentage') {
    samplingConfig.percentage = editor.percentage
    samplingConfig.group_by = editor.group_by ?? null
  }
  return {
    scene: editor.scene,
    rule_set_key: editor.rule_set_key,
    date_range: editor.dateRange
      ? {
          start: editor.dateRange[0].format('YYYY-MM-DD'),
          end: editor.dateRange[1].format('YYYY-MM-DD'),
        }
      : null,
    department_filter: [
      ...new Set(editor.department_filter.map((item) => item.trim()).filter(Boolean)),
    ],
    sampling_method: editor.sampling_method,
    sampling_config: samplingConfig,
    assign_method: editor.assign_method,
    assignee_config:
      editor.assign_method === 'by_original_reviewer' && editor.fallback
        ? { fallback: editor.fallback }
        : {},
  }
}

async function saveTemplate() {
  if (saving.value) return
  const config = editorConfig()
  if (!config) return
  saving.value = true
  saveError.value = ''
  const result = editingTemplate.value
    ? await updateTaskTemplate(editingTemplate.value.id, {
        version: editingTemplate.value.version,
        name: editor.name.trim(),
        config,
      })
    : await createTaskTemplate({ name: editor.name.trim(), config })
  saving.value = false
  const responseValid =
    result.data &&
    isTaskTemplate(result.data) &&
    (!editingTemplate.value || result.data.id === editingTemplate.value.id)
  if (!result.success || !responseValid) {
    const unknown =
      result.status === undefined || result.status >= 500 || (result.success && !responseValid)
    if (unknown) {
      message.warning('模板保存结果未知，已刷新列表，请勿直接重复提交')
      editorOpen.value = false
      editingTemplate.value = null
      await loadTemplates()
      return
    }
    saveError.value = result.message || '任务模板保存失败'
    if (result.code === 'version_conflict' || result.code === 'name_conflict') await loadTemplates()
    return
  }
  message.success(editingTemplate.value ? '任务模板已更新' : '任务模板已保存')
  editorOpen.value = false
  editingTemplate.value = null
  await loadTemplates()
}

function applyTemplate(template: TaskTemplate) {
  if (!template.usable || !template.config) return
  emit('apply', cloneConfig(template.config))
  emit('update:open', false)
}

function confirmDelete(template: TaskTemplate) {
  Modal.confirm({
    title: `删除模板“${template.name}”？`,
    content: '删除后不可恢复，不会影响已经创建的任务。',
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      const result = await deleteTaskTemplate(template.id, template.version)
      if (
        !result.success ||
        !result.data ||
        result.data.id !== template.id ||
        result.data.deleted !== true
      ) {
        const unknown = result.status === undefined || result.status >= 500 || result.success
        if (unknown) {
          message.warning('模板删除结果未知，已刷新列表')
          await loadTemplates()
          return
        }
        message.error(result.message || '任务模板删除失败')
        if (result.code === 'version_conflict') await loadTemplates()
        return Promise.reject(new Error('delete_failed'))
      }
      message.success('任务模板已删除')
      await loadTemplates()
    },
  })
}

function closeDrawer() {
  loadRequestId += 1
  emit('update:open', false)
}

watch(
  [() => props.open, () => authStore.user?.id],
  ([open], previous) => {
    const previousOpen = previous?.[0]
    const previousUser = previous?.[1]
    loadRequestId += 1
    templates.value = []
    editorOpen.value = false
    editingTemplate.value = null
    seedConsumed.value = false
    if (open) void loadTemplates()
    else if (previousOpen && previousUser) loadError.value = ''
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  loadRequestId += 1
})
</script>
