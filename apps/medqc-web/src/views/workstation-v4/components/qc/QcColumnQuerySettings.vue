<template>
  <details class="column-query">
    <summary title="列筛选与排序" aria-label="列筛选与排序"><ListFilter :size="16" /></summary>
    <form class="column-query__panel" @submit.prevent="apply">
      <strong>列筛选与排序</strong>
      <label v-for="column in columns" :key="column.key" class="column-query__row">
        <input
          v-if="resultView === 'defects'"
          type="checkbox"
          :checked="!hidden.includes(column.key)"
          :aria-label="`显示${column.label}`"
          @change="toggle(column.key)"
        />
        <span>{{ column.label }}</span>
        <input
          v-model="filters[column.key]"
          :aria-label="`${column.label}关键词`"
          :data-testid="`column-filter-${column.key}`"
          type="search"
        />
      </label>
      <label
        >排序列<select v-model="sort" data-testid="column-sort">
          <option value="">默认顺序</option>
          <option v-for="column in columns" :key="column.key" :value="column.key">
            {{ column.label }}
          </option>
        </select></label
      >
      <label
        >方向<select v-model="direction" :disabled="!sort" data-testid="column-direction">
          <option value="asc">升序</option>
          <option value="desc">降序</option>
        </select></label
      >
      <div class="column-query__actions">
        <button type="button" @click="reset">清除筛选与排序</button
        ><button type="submit">查询</button>
      </div>
      <p v-if="storageError" role="alert">列设置无法保存，请检查浏览器存储权限</p>
    </form>
  </details>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ListFilter } from 'lucide-vue-next'

const props = defineProps<{
  userId: string
  carePhase: string
  resultView: 'records' | 'defects'
}>()
export interface ColumnQuery {
  filters: Record<string, string>
  sort: string
  direction: 'asc' | 'desc'
  hidden: string[]
}
const emit = defineEmits<{ change: [query: ColumnQuery] }>()
const columns = computed(() =>
  props.resultView === 'records'
    ? [
        { key: 'patient', label: '患者与病历' },
        { key: 'department', label: '科室' },
        { key: 'admission', label: '入院时间' },
        { key: 'discharge', label: '出院时间' },
        { key: 'latestQc', label: '最近质控' },
        { key: 'score', label: '得分' },
        { key: 'grade', label: '等级' },
        { key: 'review', label: '审核状态' },
      ]
    : [
        { key: 'patient', label: '患者与病历' },
        { key: 'department', label: '科室' },
        { key: 'source', label: '来源' },
        { key: 'rule', label: '质控点' },
        { key: 'document', label: '文书/位置' },
        { key: 'status', label: '状态' },
      ],
)
const filters = reactive<Record<string, string>>({})
const sort = ref('')
const direction = ref<'asc' | 'desc'>('asc')
const hidden = ref<string[]>([])
const storageError = ref(false)
const storageKey = computed(() =>
  props.userId.trim()
    ? `medqc:qc-column-query:v1:${encodeURIComponent(props.userId)}:${props.carePhase}:${props.resultView}`
    : null,
)

function snapshot(): ColumnQuery {
  return {
    filters: Object.fromEntries(
      Object.entries(filters)
        .filter(([, value]) => value.trim())
        .map(([key, value]) => [key, value.trim()]),
    ),
    sort: sort.value,
    direction: direction.value,
    hidden: [...hidden.value],
  }
}
function clear() {
  for (const key of Object.keys(filters)) delete filters[key]
  sort.value = ''
  direction.value = 'asc'
  hidden.value = []
  storageError.value = false
}
watch(
  storageKey,
  () => {
    clear()
    try {
      const raw: unknown = storageKey.value
        ? JSON.parse(localStorage.getItem(storageKey.value) || 'null')
        : null
      if (raw && typeof raw === 'object') {
        const stored = raw as Record<string, unknown>
        const allowed = columns.value.map((column) => column.key)
        if (
          stored.filters &&
          typeof stored.filters === 'object' &&
          !Array.isArray(stored.filters)
        ) {
          for (const [key, value] of Object.entries(stored.filters))
            if (allowed.includes(key) && typeof value === 'string') filters[key] = value
        }
        if (typeof stored.sort === 'string' && allowed.includes(stored.sort))
          sort.value = stored.sort
        if (stored.direction === 'desc') direction.value = 'desc'
        if (Array.isArray(stored.hidden))
          hidden.value = stored.hidden.filter(
            (key): key is string => typeof key === 'string' && allowed.includes(key),
          )
      }
    } catch {
      storageError.value = true
    }
    emit('change', snapshot())
  },
  { immediate: true },
)
function apply() {
  try {
    if (storageKey.value) localStorage.setItem(storageKey.value, JSON.stringify(snapshot()))
    storageError.value = false
  } catch {
    storageError.value = true
  }
  emit('change', snapshot())
}
function toggle(key: string) {
  hidden.value = hidden.value.includes(key)
    ? hidden.value.filter((value) => value !== key)
    : [...hidden.value, key]
  apply()
}
function reset() {
  clear()
  apply()
}
</script>

<style scoped>
.column-query {
  position: relative;
}
summary {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  list-style: none;
}
.column-query__panel {
  position: absolute;
  right: 0;
  top: 40px;
  z-index: 35;
  display: grid;
  gap: 10px;
  width: min(370px, 85vw);
  padding: 16px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 8px 24px #0f172a14;
}
label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.column-query__row span {
  min-width: 86px;
}
input[type='search'],
select {
  min-width: 0;
  flex: 1;
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 5px 8px;
  font: inherit;
}
.column-query__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
button {
  cursor: pointer;
  padding: 5px 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 6px;
  color: #2563eb;
}
p {
  margin: 0;
  color: #b42318;
  font-size: 13px;
}
</style>
