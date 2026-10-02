<template>
  <section class="outpatient-filter-template-bar" aria-label="门急诊筛选模板">
    <span class="outpatient-filter-template-bar__label">快捷筛选</span>

    <template v-if="loadFailed">
      <span class="outpatient-filter-template-bar__unavailable">筛选模板暂不可用</span>
      <button type="button" :disabled="busy" @click="loadTemplates">重新加载</button>
    </template>
    <template v-else>
      <select
        aria-label="选择门急诊筛选模板"
        data-testid="outpatient-filter-template-select"
        :value="activeTemplateId"
        :disabled="disabled || busy || loading"
        @change="applySelectedTemplate"
      >
        <option value="">{{ templates.length ? '选择模板…' : '暂无模板' }}</option>
        <option v-for="template in templates" :key="template.id" :value="template.id">
          {{ optionLabel(template) }}
        </option>
      </select>
      <span v-if="activeTemplate && activeTemplateModified" class="outpatient-filter-template-bar__modified">
        已修改
      </span>
      <button
        type="button"
        data-testid="outpatient-filter-template-save-as"
        :disabled="disabled || busy || loading"
        @click="openSaveAs"
      >
        新建筛选
      </button>
      <button
        type="button"
        data-testid="outpatient-filter-template-update"
        :disabled="disabled || busy || !activeTemplate || !activeTemplateModified"
        @click="updateActiveTemplate"
      >
        保存修改
      </button>
      <button
        type="button"
        data-testid="outpatient-filter-template-default"
        :disabled="disabled || busy || !activeTemplate"
        @click="toggleDefault"
      >
        {{ activeTemplate?.is_default ? '取消默认' : '设为默认' }}
      </button>
      <button
        type="button"
        class="is-danger"
        data-testid="outpatient-filter-template-delete"
        :disabled="disabled || busy || !activeTemplate"
        @click="confirmingDelete = true"
      >
        删除
      </button>
    </template>

    <button
      type="button"
      data-testid="outpatient-filter-template-reset"
      :disabled="disabled || busy"
      @click="resetFilters"
    >
      重置筛选
    </button>

    <form
      v-if="savingAs"
      class="outpatient-filter-template-bar__inline"
      data-testid="outpatient-filter-template-form"
      @submit.prevent="saveAsTemplate"
    >
      <label>
        <span>模板名称</span>
        <input
          v-model="newTemplateName"
          aria-label="门急诊筛选模板名称"
          maxlength="50"
          placeholder="例如：本周本科室门诊"
        />
      </label>
      <label class="outpatient-filter-template-bar__checkbox">
        <input v-model="newTemplateDefault" type="checkbox" />
        设为默认
      </label>
      <button type="submit" class="is-primary" :disabled="busy || !newTemplateName.trim()">
        保存
      </button>
      <button type="button" :disabled="busy" @click="savingAs = false">取消</button>
    </form>

    <div
      v-if="confirmingDelete && activeTemplate"
      class="outpatient-filter-template-bar__inline"
      data-testid="outpatient-filter-template-delete-confirm"
    >
      <span>确认删除模板「{{ activeTemplate.name }}」？</span>
      <button type="button" class="is-danger-solid" :disabled="busy" @click="deleteActiveTemplate">
        确认删除
      </button>
      <button type="button" :disabled="busy" @click="confirmingDelete = false">取消</button>
    </div>

    <p v-if="notice" class="outpatient-filter-template-bar__notice" role="status">{{ notice }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  createFilterTemplate,
  listFilterTemplates,
  removeFilterTemplate,
  updateFilterTemplate,
  type FilterTemplate,
  type FilterTemplateApiResult,
  type FilterTemplateFilters,
} from '@/api/filterTemplates'
import { useAuthStore } from '@/stores/auth'

export interface OutpatientFilterSnapshot {
  keyword?: string
  scoring_standard?: string
  department?: string
  start_date?: string
  end_date?: string
}

const props = defineProps<{
  currentFilters: OutpatientFilterSnapshot
  disabled?: boolean
}>()

const emit = defineEmits<{
  apply: [filters: OutpatientFilterSnapshot]
}>()

const PAGE_KEY = 'v5_records_outpatient_emergency' as const
const ALLOWED_FILTER_KEYS = new Set(['keyword', 'dept', 'start_date', 'end_date', 'date_field', 'scoring_standard'])
const CONFLICT_MESSAGES = {
  name_conflict: '已存在同名模板，请换一个名称',
  limit_reached: '本页最多保存 20 个模板，请先删除不再使用的模板',
  version_conflict: '模板已在别处被修改，已刷新模板列表，请确认后重试',
} as const

const templates = ref<FilterTemplate[]>([])
const authStore = useAuthStore()
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

function normalizeSnapshot(filters: OutpatientFilterSnapshot): OutpatientFilterSnapshot {
  const normalized: OutpatientFilterSnapshot = {}
  const keyword = filters.keyword?.trim()
  const department = filters.department?.trim()
  const scoringStandard = filters.scoring_standard?.trim()
  if (keyword) normalized.keyword = keyword
  if (department) normalized.department = department
  if (scoringStandard) normalized.scoring_standard = scoringStandard
  if (filters.start_date) normalized.start_date = filters.start_date
  if (filters.end_date) normalized.end_date = filters.end_date
  return normalized
}

function toApiFilters(filters: OutpatientFilterSnapshot): FilterTemplateFilters {
  const normalized = normalizeSnapshot(filters)
  return {
    keyword: normalized.keyword,
    dept: normalized.department,
    start_date: normalized.start_date,
    end_date: normalized.end_date,
    date_field: 'visit',
    ...(normalized.scoring_standard ? { scoring_standard: normalized.scoring_standard } : {}),
  }
}

function fromApiFilters(filters: FilterTemplateFilters | null): OutpatientFilterSnapshot | null {
  if (!filters || Object.keys(filters).some((key) => !ALLOWED_FILTER_KEYS.has(key))) return null
  if (filters.date_field !== 'visit') return null
  if (Boolean(filters.start_date) !== Boolean(filters.end_date)) return null
  return normalizeSnapshot({
    keyword: filters.keyword,
    scoring_standard: filters.scoring_standard,
    department: filters.dept,
    start_date: filters.start_date,
    end_date: filters.end_date,
  })
}

function sameFilters(left: OutpatientFilterSnapshot, right: OutpatientFilterSnapshot): boolean {
  return JSON.stringify(normalizeSnapshot(left)) === JSON.stringify(normalizeSnapshot(right))
}

const activeTemplate = computed(
  () => templates.value.find((template) => template.id === activeTemplateId.value) ?? null,
)
const activeTemplateModified = computed(() => {
  if (!activeTemplate.value) return false
  const snapshot = fromApiFilters(activeTemplate.value.filters)
  return snapshot ? !sameFilters(snapshot, props.currentFilters) : true
})

function optionLabel(template: FilterTemplate): string {
  const invalid = !fromApiFilters(template.filters)
  const suffix = [template.is_default ? '默认' : '', invalid ? '内容不可用' : '']
    .filter(Boolean)
    .join('，')
  return suffix ? `${template.name}（${suffix}）` : template.name
}

async function loadTemplates(): Promise<boolean> {
  const sequence = ++loadSequence
  loading.value = true
  const result = await listFilterTemplates(PAGE_KEY)
  if (sequence !== loadSequence) return false
  loading.value = false
  if (!result.success || !result.data) {
    loadFailed.value = true
    templates.value = []
    activeTemplateId.value = ''
    return false
  }
  loadFailed.value = false
  templates.value = result.data
  if (activeTemplateId.value && !activeTemplate.value) activeTemplateId.value = ''
  return true
}

async function initialize() {
  const loaded = await loadTemplates()
  if (!loaded) return
  const preferred = templates.value.find((template) => template.is_default)
  if (!preferred) return
  const snapshot = fromApiFilters(preferred.filters)
  if (!snapshot) {
    notice.value = '默认模板内容不可用，未改变当前筛选'
    return
  }
  activeTemplateId.value = preferred.id
  emit('apply', snapshot)
}

function clearTemplateState() {
  loadSequence += 1
  templates.value = []
  loading.value = false
  loadFailed.value = false
  busy.value = false
  activeTemplateId.value = ''
  savingAs.value = false
  confirmingDelete.value = false
  notice.value = ''
}

function applySelectedTemplate(event: Event) {
  confirmingDelete.value = false
  const id = (event.target as HTMLSelectElement).value
  activeTemplateId.value = id
  const template = templates.value.find((item) => item.id === id)
  if (!template) return
  const snapshot = fromApiFilters(template.filters)
  if (!snapshot) {
    notice.value = '该模板内容不适用于门急诊筛选，未应用'
    return
  }
  notice.value = ''
  emit('apply', snapshot)
}

function resetFilters() {
  savingAs.value = false
  confirmingDelete.value = false
  notice.value = ''
  const preferred = loadFailed.value ? undefined : templates.value.find((template) => template.is_default)
  const snapshot = preferred ? fromApiFilters(preferred.filters) : null
  activeTemplateId.value = preferred && snapshot ? preferred.id : ''
  if (preferred && !snapshot) notice.value = '默认模板内容不可用，已清空筛选'
  emit('apply', snapshot ?? {})
}

function openSaveAs() {
  confirmingDelete.value = false
  newTemplateName.value = ''
  newTemplateDefault.value = false
  savingAs.value = true
}

async function handleWriteResult<T>(result: FilterTemplateApiResult<T>, successMessage: string) {
  if (result.success) {
    notice.value = successMessage
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

async function saveAsTemplate() {
  const name = newTemplateName.value.trim()
  if (!name || busy.value) return
  busy.value = true
  try {
    const result = await createFilterTemplate({
      page_key: PAGE_KEY,
      name,
      filters: toApiFilters(props.currentFilters),
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

async function updateActiveTemplate() {
  const template = activeTemplate.value
  if (!template || busy.value) return
  busy.value = true
  try {
    await handleWriteResult(
      await updateFilterTemplate(template.id, {
        version: template.version,
        filters: toApiFilters(props.currentFilters),
      }),
      `已保存对模板「${template.name}」的修改`,
    )
  } finally {
    busy.value = false
  }
}

async function toggleDefault() {
  const template = activeTemplate.value
  if (!template || busy.value) return
  busy.value = true
  try {
    const nextDefault = !template.is_default
    await handleWriteResult(
      await updateFilterTemplate(template.id, {
        version: template.version,
        is_default: nextDefault,
      }),
      nextDefault ? `已将「${template.name}」设为默认` : `已取消「${template.name}」的默认`,
    )
  } finally {
    busy.value = false
  }
}

async function deleteActiveTemplate() {
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

onMounted(initialize)

watch(
  () => authStore.user?.id,
  (nextOwnerId, previousOwnerId) => {
    if (nextOwnerId === previousOwnerId) return
    clearTemplateState()
    if (nextOwnerId) void initialize()
  },
)

onBeforeUnmount(() => {
  loadSequence += 1
})
</script>

<style scoped>
.outpatient-filter-template-bar {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  line-height: 22px;
}

.outpatient-filter-template-bar__label {
  color: rgba(29, 29, 31, 0.6);
}

.outpatient-filter-template-bar select,
.outpatient-filter-template-bar input,
.outpatient-filter-template-bar button {
  min-height: 34px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.86);
  padding: 5px 10px;
  color: #1d1d1f;
  font: inherit;
}

.outpatient-filter-template-bar select {
  min-width: 190px;
}

.outpatient-filter-template-bar button:not(:disabled) {
  cursor: pointer;
}

.outpatient-filter-template-bar button:hover:not(:disabled) {
  border-color: rgba(0, 122, 255, 0.28);
  color: #007aff;
}

.outpatient-filter-template-bar button:disabled {
  cursor: not-allowed;
  opacity: 0.46;
}

.outpatient-filter-template-bar button.is-primary {
  border-color: #007aff;
  background: #007aff;
  color: #fff;
}

.outpatient-filter-template-bar button.is-danger,
.outpatient-filter-template-bar button.is-danger-solid {
  color: #ef4444;
}

.outpatient-filter-template-bar button.is-danger-solid {
  border-color: #ef4444;
}

.outpatient-filter-template-bar__modified,
.outpatient-filter-template-bar__unavailable,
.outpatient-filter-template-bar__notice {
  color: rgba(29, 29, 31, 0.6);
}

.outpatient-filter-template-bar__inline {
  display: flex;
  flex-basis: 100%;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding-top: 4px;
}

.outpatient-filter-template-bar__inline label {
  display: flex;
  align-items: center;
  gap: 8px;
}

.outpatient-filter-template-bar__checkbox input {
  min-height: auto;
}

.outpatient-filter-template-bar__notice {
  flex-basis: 100%;
  margin: 0;
}
</style>
