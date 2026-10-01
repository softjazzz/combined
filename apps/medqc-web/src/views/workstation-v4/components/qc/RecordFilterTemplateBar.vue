<template>
  <div class="record-filter-template-bar" aria-label="快捷筛选与筛选模板">
    <div class="record-filter-template-bar__quick" role="group" aria-label="快捷筛选">
      <span class="record-filter-template-bar__label">快捷筛选</span>
      <button
        v-for="option in visibleQuickOptions"
        :key="option.key"
        type="button"
        :data-testid="`quick-filter-${option.key}`"
        :class="{ 'is-active': activeQuickKey === option.key }"
        :aria-pressed="activeQuickKey === option.key"
        :disabled="disabled"
        @click="applyQuick(option)"
      >
        {{ option.label }}
      </button>
    </div>

    <div class="record-filter-template-bar__templates" role="group" aria-label="筛选模板">
      <span class="record-filter-template-bar__label">筛选模板</span>
      <template v-if="loadFailed">
        <span
          class="record-filter-template-bar__unavailable"
          data-testid="filter-template-unavailable"
        >
          筛选模板暂不可用
        </span>
        <button type="button" :disabled="busy" @click="loadTemplates">重新加载</button>
      </template>
      <template v-else>
        <select
          aria-label="选择筛选模板"
          data-testid="filter-template-select"
          :value="activeTemplateId"
          :disabled="disabled || busy || loading"
          @change="handleTemplateSelect"
        >
          <option value="">
            {{ templates.length > 0 ? '选择模板…' : '暂无模板' }}
          </option>
          <option v-for="template in templates" :key="template.id" :value="template.id">
            {{ templateOptionLabel(template) }}
          </option>
        </select>
        <span
          v-if="activeTemplate && activeTemplateModified"
          class="record-filter-template-bar__hint"
        >
          已修改
        </span>
        <button
          type="button"
          data-testid="filter-template-save-as"
          :disabled="disabled || busy || loading"
          @click="openSaveAs"
        >
          另存为
        </button>
        <button
          type="button"
          data-testid="filter-template-update"
          :disabled="disabled || busy || !activeTemplate || !activeTemplateModified"
          @click="updateActiveFilters"
        >
          更新当前模板
        </button>
        <button
          type="button"
          data-testid="filter-template-toggle-default"
          :disabled="disabled || busy || !activeTemplate"
          @click="toggleActiveDefault"
        >
          {{ activeTemplate?.is_default ? '取消默认' : '设为默认' }}
        </button>
        <button
          type="button"
          class="is-danger"
          data-testid="filter-template-delete"
          :disabled="disabled || busy || !activeTemplate"
          @click="confirmingDelete = true"
        >
          删除
        </button>
      </template>
      <button
        type="button"
        data-testid="filter-template-reset"
        :disabled="disabled || busy"
        @click="resetToDefault"
      >
        重置
      </button>
    </div>

    <form
      v-if="savingAs"
      class="record-filter-template-bar__inline"
      data-testid="filter-template-save-as-form"
      @submit.prevent="submitSaveAs"
    >
      <label>
        <span>模板名称</span>
        <input
          v-model="newTemplateName"
          type="text"
          maxlength="50"
          aria-label="模板名称"
          placeholder="例如：本科室待审核"
        />
      </label>
      <label class="record-filter-template-bar__checkbox">
        <input v-model="newTemplateDefault" type="checkbox" aria-label="设为默认模板" />
        设为默认
      </label>
      <button type="submit" class="is-primary" :disabled="busy || !newTemplateName.trim()">
        保存
      </button>
      <button type="button" :disabled="busy" @click="savingAs = false">取消</button>
    </form>

    <div
      v-if="confirmingDelete && activeTemplate"
      class="record-filter-template-bar__inline"
      data-testid="filter-template-delete-confirm"
    >
      <span>确认删除模板「{{ activeTemplate.name }}」？删除后不可恢复。</span>
      <button type="button" class="is-danger-solid" :disabled="busy" @click="deleteActive">
        确认删除
      </button>
      <button type="button" :disabled="busy" @click="confirmingDelete = false">取消</button>
    </div>

    <p v-if="notice" class="record-filter-template-bar__notice" role="status">
      {{ notice }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import {
  createFilterTemplate,
  listFilterTemplates,
  removeFilterTemplate,
  updateFilterTemplate,
  type FilterTemplate,
  type FilterTemplateApiResult,
  type FilterTemplatePageKey,
} from '@/api/filterTemplates'
import { useAuthStore } from '@/stores/auth'
import {
  isSameRecordFilter,
  normalizeRecordFilter,
  type RecordFilterSnapshot,
} from '../../composables/recordFilterQuery'
import type { RecordLatestReviewState } from '../../types'

const props = defineProps<{
  pageKey: FilterTemplatePageKey
  /** 当前生效筛选（来自 URL query）。 */
  currentFilters: RecordFilterSnapshot
  /** URL 未显式给出筛选时，由本组件在模板加载后决定初始筛选（默认模板优先于系统默认）。 */
  resolveInitialFilters: boolean
  disabled?: boolean
  defectView?: boolean
}>()

const emit = defineEmits<{
  /**
   * 写入新的完整筛选；由父组件写入 URL query 并请求列表。
   * reviewScopeAll：true 表示审核角色显式选择“全部”（写入前端标记），false 表示移除该标记。
   */
  apply: [filters: RecordFilterSnapshot, reviewScopeAll: boolean]
  defaultResolved: [hasUserDefault: boolean]
}>()

type QuickKey =
  | 'all'
  | 'pending_review'
  | 'pending_recheck'
  | 'reviewing'
  | 'clinical_appeal'
  | 'pending_rectification'
  | 'pending_work'

interface QuickOption {
  key: QuickKey
  label: string
  states: RecordLatestReviewState[]
  reviewOnly: boolean
}

const QUICK_OPTIONS: QuickOption[] = [
  { key: 'all', label: '全部', states: [], reviewOnly: false },
  { key: 'pending_review', label: '待审核', states: ['pending_review'], reviewOnly: true },
  { key: 'pending_recheck', label: '待复审', states: ['pending_recheck'], reviewOnly: true },
  {
    key: 'reviewing',
    label: '审核中',
    states: ['pending_review', 'pending_recheck'],
    reviewOnly: true,
  },
]

const CONFLICT_MESSAGES = {
  name_conflict: '已存在同名模板，请换一个名称',
  limit_reached: '本页最多保存 20 个模板，请先删除不再使用的模板',
  version_conflict: '模板已在别处被修改，已刷新模板列表，请确认后重试',
} as const

const authStore = useAuthStore()
const canReview = computed(() => authStore.hasRole('admin') || authStore.hasRole('qc_manager'))

const templates = ref<FilterTemplate[]>([])
const loading = ref(false)
const loadFailed = ref(false)
const busy = ref(false)
const notice = ref('')
const activeTemplateId = ref('')
const savingAs = ref(false)
const newTemplateName = ref('')
const newTemplateDefault = ref(false)
const confirmingDelete = ref(false)
let loadSequence = 0

const visibleQuickOptions = computed(() =>
  props.defectView
    ? ([
        QUICK_OPTIONS[0],
        { key: 'pending_work', label: '待处理', states: [], reviewOnly: false },
        { key: 'clinical_appeal', label: '临床申诉（待处理）', states: [], reviewOnly: false },
        { key: 'pending_rectification', label: '待整改（已派发）', states: [], reviewOnly: false },
      ] as QuickOption[])
    : QUICK_OPTIONS.filter((option) => !option.reviewOnly || canReview.value),
)

/** 快捷筛选只作用于审核状态，其他筛选项保持不变。 */
const activeQuickKey = computed<QuickKey | ''>(() => {
  if (props.defectView) return props.currentFilters.defect_workflow ?? 'all'
  const current = (normalizeRecordFilter(props.currentFilters).review_state ?? []).join(',')
  const matched = visibleQuickOptions.value.find((option) => option.states.join(',') === current)
  return matched?.key ?? ''
})

const activeTemplate = computed(
  () => templates.value.find((template) => template.id === activeTemplateId.value) ?? null,
)
const activeTemplateModified = computed(() => {
  const template = activeTemplate.value
  if (!template) return false
  const snapshot = templateSnapshot(template)
  return snapshot ? !isSameRecordFilter(snapshot, props.currentFilters) : true
})

const UNAVAILABLE_TEMPLATE_NOTICE = '该模板内容不可用，未应用；可用当前筛选更新或删除该模板'

function templateOptionLabel(template: FilterTemplate): string {
  const suffix = [template.is_default ? '默认' : '', template.filters ? '' : '内容不可用']
    .filter(Boolean)
    .join('，')
  return suffix ? `${template.name}（${suffix}）` : template.name
}

/** 系统默认：审核角色为“审核中”（待审核+待复审），其他角色为“全部”。 */
function systemDefaultFilters(): RecordFilterSnapshot {
  if (props.defectView) return { result_view: 'defects', defect_workflow: 'pending_work' }
  return canReview.value ? { review_state: ['pending_review', 'pending_recheck'] } : {}
}

/** 模板只取本页暴露的筛选键；date_field/inpatient_sort 由页面固定。内容不可用时返回 null。 */
function templateSnapshot(template: FilterTemplate): RecordFilterSnapshot | null {
  if (!template.filters) return null
  const {
    dept,
    doctor,
    keyword,
    start_date,
    end_date,
    review_state,
    standard_id,
    score_status,
    grade,
    score_min,
    score_max,
    result_view,
    defect_source,
    defect_workflow,
    has_defect,
  } = template.filters
  return normalizeRecordFilter({
    dept,
    doctor,
    keyword,
    start_date,
    end_date,
    review_state,
    standard_id,
    score_status,
    grade,
    score_min,
    score_max,
    result_view,
    defect_source,
    defect_workflow,
    has_defect,
  })
}

function defaultTemplate(): FilterTemplate | null {
  return templates.value.find((template) => template.is_default) ?? null
}

async function loadTemplates(): Promise<boolean> {
  const sequence = ++loadSequence
  loading.value = true
  const result = await listFilterTemplates(props.pageKey)
  if (sequence !== loadSequence) return false
  loading.value = false
  if (!result.success || !result.data) {
    loadFailed.value = true
    templates.value = []
    activeTemplateId.value = ''
    emit('defaultResolved', false)
    return false
  }
  loadFailed.value = false
  templates.value = result.data
  const preferred = defaultTemplate()
  emit('defaultResolved', Boolean(preferred && templateSnapshot(preferred)))
  if (activeTemplateId.value && !activeTemplate.value) activeTemplateId.value = ''
  return true
}

async function initialize() {
  activeTemplateId.value = ''
  let initial = systemDefaultFilters()
  try {
    const loaded = await loadTemplates()
    const preferred = loaded ? defaultTemplate() : null
    const preferredSnapshot = preferred ? templateSnapshot(preferred) : null
    if (preferred && props.resolveInitialFilters) {
      if (preferredSnapshot) {
        initial = preferredSnapshot
        activeTemplateId.value = preferred.id
      } else {
        notice.value = '默认模板内容不可用，已按系统默认筛选'
      }
    }
  } finally {
    // 模板加载失败不阻塞列表：仍按系统默认发出初始筛选。
    if (props.resolveInitialFilters) emit('apply', initial, false)
  }
}

function applyQuick(option: QuickOption) {
  if (props.defectView) {
    const workflow =
      option.key === 'clinical_appeal' ||
      option.key === 'pending_rectification' ||
      option.key === 'pending_work'
        ? option.key
        : 'all'
    emit(
      'apply',
      normalizeRecordFilter({
        ...props.currentFilters,
        result_view: 'defects',
        defect_workflow: workflow,
        review_state: undefined,
        has_defect: undefined,
      }),
      false,
    )
    return
  }
  const states = option.states
  emit(
    'apply',
    normalizeRecordFilter({ ...props.currentFilters, review_state: states }),
    states.length === 0 && canReview.value,
  )
}

function handleTemplateSelect(event: Event) {
  const id = (event.target as HTMLSelectElement).value
  confirmingDelete.value = false
  const template = templates.value.find((item) => item.id === id)
  activeTemplateId.value = template?.id ?? ''
  if (!template) return
  const snapshot = templateSnapshot(template)
  if (!snapshot) {
    notice.value = UNAVAILABLE_TEMPLATE_NOTICE
    return
  }
  notice.value = ''
  emit('apply', snapshot, false)
}

function resetToDefault() {
  confirmingDelete.value = false
  savingAs.value = false
  notice.value = ''
  const preferred = loadFailed.value ? null : defaultTemplate()
  const preferredSnapshot = preferred ? templateSnapshot(preferred) : null
  activeTemplateId.value = preferredSnapshot && preferred ? preferred.id : ''
  if (preferred && !preferredSnapshot) notice.value = '默认模板内容不可用，已按系统默认筛选'
  emit('apply', preferredSnapshot ?? systemDefaultFilters(), false)
}

function openSaveAs() {
  confirmingDelete.value = false
  newTemplateName.value = ''
  newTemplateDefault.value = false
  savingAs.value = true
}

/** 统一处理写操作结果：409 提示并刷新列表；其他失败只提示。 */
async function handleWriteResult<T>(
  result: FilterTemplateApiResult<T>,
  successNotice: string,
): Promise<boolean> {
  if (result.success) {
    notice.value = successNotice
    await loadTemplates()
    return true
  }
  if (result.status === 409) {
    notice.value = result.code
      ? CONFLICT_MESSAGES[result.code]
      : result.message || '模板已冲突，已刷新模板列表'
    await loadTemplates()
    return false
  }
  notice.value = result.message || '筛选模板操作失败，请稍后重试'
  return false
}

async function submitSaveAs() {
  const name = newTemplateName.value.trim()
  if (!name || busy.value) return
  busy.value = true
  try {
    const result = await createFilterTemplate({
      page_key: props.pageKey,
      name,
      filters: normalizeRecordFilter(props.currentFilters),
      is_default: newTemplateDefault.value,
    })
    if (await handleWriteResult(result, `已保存模板「${name}」`)) {
      savingAs.value = false
      if (result.data?.id) activeTemplateId.value = result.data.id
    }
  } finally {
    busy.value = false
  }
}

async function updateActiveFilters() {
  const template = activeTemplate.value
  if (!template || busy.value) return
  busy.value = true
  try {
    const result = await updateFilterTemplate(template.id, {
      version: template.version,
      filters: normalizeRecordFilter(props.currentFilters),
    })
    await handleWriteResult(result, `已更新模板「${template.name}」`)
  } finally {
    busy.value = false
  }
}

async function toggleActiveDefault() {
  const template = activeTemplate.value
  if (!template || busy.value) return
  busy.value = true
  try {
    const nextDefault = !template.is_default
    const result = await updateFilterTemplate(template.id, {
      version: template.version,
      is_default: nextDefault,
    })
    await handleWriteResult(
      result,
      nextDefault ? `已将「${template.name}」设为默认` : `已取消「${template.name}」的默认`,
    )
  } finally {
    busy.value = false
  }
}

async function deleteActive() {
  const template = activeTemplate.value
  if (!template || busy.value) return
  busy.value = true
  try {
    const result = await removeFilterTemplate(template.id, template.version)
    if (result.success) activeTemplateId.value = ''
    await handleWriteResult(result, `已删除模板「${template.name}」`)
    confirmingDelete.value = false
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  void initialize()
})

watch(
  () => props.pageKey,
  () => {
    savingAs.value = false
    confirmingDelete.value = false
    notice.value = ''
    void loadTemplates()
  },
)
</script>

<style scoped>
.record-filter-template-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 20px;
  padding: 10px 12px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 10px;
  background: #f7f9fc;
  font-size: 13px;
}

.record-filter-template-bar__quick,
.record-filter-template-bar__templates,
.record-filter-template-bar__inline {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.record-filter-template-bar__label {
  color: #5b6475;
  font-weight: 600;
  white-space: nowrap;
}

.record-filter-template-bar button,
.record-filter-template-bar select,
.record-filter-template-bar input[type='text'] {
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid rgba(0, 0, 0, 0.09);
  border-radius: 8px;
  background: #fff;
  color: #1f2937;
  font: inherit;
  font-size: 13px;
  white-space: nowrap;
}

.record-filter-template-bar select {
  min-width: 160px;
  max-width: 240px;
}

.record-filter-template-bar button {
  color: #2b6cf6;
  cursor: pointer;
  font-weight: 600;
}

.record-filter-template-bar__quick button.is-active {
  border-color: #2b6cf6;
  background: #eaf1ff;
}

.record-filter-template-bar button.is-primary {
  border-color: #2b6cf6;
  background: #2b6cf6;
  color: #fff;
}

.record-filter-template-bar button.is-danger {
  color: #c2410c;
}

.record-filter-template-bar button.is-danger-solid {
  border-color: #dc2626;
  background: #dc2626;
  color: #fff;
}

.record-filter-template-bar button:disabled,
.record-filter-template-bar select:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.record-filter-template-bar__inline {
  flex-basis: 100%;
  padding-top: 8px;
  border-top: 1px dashed rgba(0, 0, 0, 0.08);
}

.record-filter-template-bar__inline label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #5b6475;
}

.record-filter-template-bar__hint {
  color: #b45309;
  font-size: 12px;
}

.record-filter-template-bar__unavailable {
  color: #8a94a6;
}

.record-filter-template-bar__notice {
  flex-basis: 100%;
  margin: 0;
  color: #475569;
}
</style>
