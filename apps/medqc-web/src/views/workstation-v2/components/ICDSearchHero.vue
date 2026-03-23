<template>
  <div class="border-b border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.99)_0%,rgba(250,252,255,0.98)_100%)] px-6 py-4">
    <div class="mx-auto flex w-full max-w-7xl flex-col gap-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="inline-flex items-center gap-1.5 rounded-full border border-blue-100 bg-blue-50/60 px-3 py-1 text-[11px] font-semibold text-blue-700">
            编码工作台
          </div>
          <h1 class="mt-3 text-[22px] font-black tracking-[-0.03em] text-slate-900">
            ICD 智能检索
          </h1>
          <p class="mt-2 max-w-[760px] text-[13px] leading-6 text-slate-500">
            ICD-10 诊断与 ICD-9 手术编码的检索、目录浏览和回填统一在同一工作台完成。
          </p>
        </div>

        <div class="flex flex-wrap items-center gap-2.5">
          <span class="metric-pill">
            <span class="metric-dot" />
            ICD-10
            <strong>{{ stats.icd10Count?.toLocaleString() || '--' }}</strong>
          </span>
          <span class="metric-pill">
            <span class="metric-dot metric-dot-light" />
            ICD-9
            <strong>{{ stats.icd9Count?.toLocaleString() || '--' }}</strong>
          </span>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <div class="search-shell">
          <SearchOutlined class="search-icon" />
          <input
            ref="searchInput"
            v-model="localQuery"
            type="text"
            :placeholder="localType === 'icd10' ? '输入诊断名称或 ICD-10 编码...' : '输入手术名称或 ICD-9 编码...'"
            class="search-input"
            @keydown.enter="$emit('search', localQuery)"
            @input="onQueryChange"
          >
          <div class="search-hint">
            <span v-if="localQuery.length > 0">Enter 搜索</span>
            <template v-else>
              <kbd>Ctrl</kbd>
              <kbd>K</kbd>
            </template>
          </div>
        </div>

        <div class="seg-shell">
          <button
            v-for="v in versionTabs"
            :key="v.value"
            :class="['seg-btn', localVersion === v.value ? 'seg-btn-active' : '']"
            @click="localVersion = v.value; $emit('update:codeVersion', v.value)"
          >
            {{ v.label }}
          </button>
        </div>

        <div class="seg-shell">
          <button
            v-for="t in codeTypeTabs"
            :key="t.value"
            :class="['seg-btn', localType === t.value ? 'seg-btn-active' : '']"
            @click="localType = t.value; $emit('update:codeType', t.value)"
          >
            {{ t.label }}
          </button>
        </div>

        <div class="help-pill">
          <span class="help-pill__label">提示</span>
          <span>输入 2 个字符后自动搜索，也支持按章节逐级浏览</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { SearchOutlined } from '@ant-design/icons-vue'

const props = defineProps<{
  codeVersion: string
  codeType: string
  searchQuery: string
  stats: { icd10Count?: number; icd9Count?: number }
}>()

const emit = defineEmits<{
  'update:codeVersion': [value: string]
  'update:codeType': [value: string]
  'update:searchQuery': [value: string]
  search: [value: string]
}>()

const localVersion = ref(props.codeVersion)
const localType = ref(props.codeType)
const localQuery = ref(props.searchQuery)
const searchInput = ref<HTMLInputElement>()

const versionTabs = [
  { label: '临床版 ICD-10', value: 'clinical' },
  { label: '医保版 2.0', value: 'insurance' },
]

const codeTypeTabs = [
  { label: '疾病诊断', value: 'icd10' },
  { label: '手术操作 (ICD-9)', value: 'icd9cm3' },
]

const handleShortcut = (e: KeyboardEvent) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    searchInput.value?.focus()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleShortcut)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleShortcut)
})

watch(() => props.codeVersion, (v) => { localVersion.value = v })
watch(() => props.codeType, (v) => { localType.value = v })
watch(() => props.searchQuery, (v) => { localQuery.value = v })

let debounceTimer: ReturnType<typeof setTimeout> | null = null
function onQueryChange() {
  emit('update:searchQuery', localQuery.value)
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    if (localQuery.value.length >= 2) {
      emit('search', localQuery.value)
    }
  }, 280)
}
</script>

<style scoped>
.metric-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  border: 1px solid rgba(191, 219, 254, 0.95);
  background: rgba(239, 246, 255, 0.9);
  padding: 8px 12px;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
  box-shadow: 0 8px 18px rgba(148, 163, 184, 0.08);
}

.metric-pill strong {
  color: #0f172a;
  font-weight: 800;
}

.metric-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #2563eb;
}

.metric-dot-light {
  background: #60a5fa;
}

.search-shell {
  position: relative;
  flex: 1 1 320px;
  min-width: 280px;
}

.search-icon {
  position: absolute;
  left: 16px;
  top: 50%;
  z-index: 1;
  width: 18px;
  height: 18px;
  color: #94a3b8;
  transform: translateY(-50%);
}

.search-input {
  width: 100%;
  height: 46px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.92);
  background: rgba(255, 255, 255, 0.96);
  padding: 0 98px 0 46px;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  outline: none;
  box-shadow: 0 10px 24px rgba(148, 163, 184, 0.08);
  transition: all 0.18s ease;
}

.search-input:focus {
  border-color: rgba(59, 130, 246, 0.6);
  box-shadow: 0 14px 28px rgba(37, 99, 235, 0.12);
}

.search-hint {
  position: absolute;
  right: 14px;
  top: 50%;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  transform: translateY(-50%);
  color: #94a3b8;
  font-size: 12px;
  font-weight: 600;
}

.search-hint kbd {
  border-radius: 6px;
  border: 1px solid rgba(226, 232, 240, 0.92);
  background: #f8fafc;
  padding: 3px 7px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
}

.seg-shell {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 8px 18px rgba(148, 163, 184, 0.08);
}

.seg-btn {
  border: 0;
  border-radius: 12px;
  padding: 9px 14px;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
  transition: all 0.18s ease;
}

.seg-btn:hover {
  color: #334155;
}

.seg-btn-active {
  background: linear-gradient(180deg, #eff6ff, #dbeafe);
  color: #1d4ed8;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.08);
}

.help-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.92);
  background: rgba(248, 250, 252, 0.92);
  padding: 9px 12px;
  color: #64748b;
  font-size: 12px;
  box-shadow: 0 8px 18px rgba(148, 163, 184, 0.08);
}

.help-pill__label {
  color: #334155;
  font-weight: 800;
}

@media (max-width: 960px) {
  .search-shell {
    flex-basis: 100%;
  }
}
</style>
