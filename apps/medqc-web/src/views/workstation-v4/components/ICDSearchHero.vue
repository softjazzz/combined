<template>
  <div class="icd-search-hero px-6 py-5">
    <div class="mx-auto flex w-full max-w-7xl flex-col gap-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="icd-hero-eyebrow">
            分析 · 编码工作台
          </div>
          <h1 class="mt-1">
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
            :placeholder="
              localType === 'icd10'
                ? '输入诊断名称或 ICD-10 编码...'
                : '输入手术名称或 ICD-9 编码...'
            "
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
            @click="selectVersion(v.value)"
          >
            {{ v.label }}
          </button>
        </div>

        <div class="seg-shell">
          <button
            v-for="t in codeTypeTabs"
            :key="t.value"
            :class="['seg-btn', localType === t.value ? 'seg-btn-active' : '']"
            @click="selectCodeType(t.value)"
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

watch(
  () => props.codeVersion,
  (v) => {
    localVersion.value = v
  },
)
watch(
  () => props.codeType,
  (v) => {
    localType.value = v
  },
)
watch(
  () => props.searchQuery,
  (v) => {
    localQuery.value = v
  },
)

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

function selectVersion(value: string) {
  localVersion.value = value
  emit('update:codeVersion', value)
}

function selectCodeType(value: string) {
  localType.value = value
  emit('update:codeType', value)
}
</script>

<style scoped>
/* v7.1：页头不再是白色横带，眉标灰色、标题 40px */
.icd-search-hero {
  border-bottom: 0;
  background: transparent;
}

.icd-hero-eyebrow {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-13);
  font-weight: 600;
}

.icd-search-hero h1 {
  color: var(--mq-text-primary) !important;
  font-family: var(--mq-font-display);
  font-size: var(--mq-font-title) !important;
  font-weight: 700 !important;
  letter-spacing: -0.03em !important;
  line-height: 1.1 !important;
}

.icd-search-hero p {
  color: rgba(29, 29, 31, 0.56) !important;
}

.metric-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  border: 1px solid rgba(10, 108, 255, 0.14);
  background: rgba(10, 108, 255, 0.07);
  padding: 7px 11px;
  color: rgba(29, 29, 31, 0.62);
  font-size: 12px;
  font-weight: 700;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.75);
}

.metric-pill strong {
  color: #0a6cff;
  font-weight: 700;
}

.metric-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #0a6cff;
}

.metric-dot-light {
  background: rgba(10, 108, 255, 0.45);
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
  color: rgba(29, 29, 31, 0.38);
  transform: translateY(-50%);
}

.search-input {
  width: 100%;
  height: 42px;
  border-radius: 12px;
  border: 1px solid rgba(29, 29, 31, 0.1);
  background: rgba(255, 255, 255, 0.94);
  padding: 0 98px 0 46px;
  font-size: 14px;
  font-weight: 500;
  color: #1d1d1f;
  outline: none;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 1px 1px rgba(0, 0, 0, 0.035);
  transition: all 0.18s ease;
}

.search-input:focus {
  border-color: rgba(10, 108, 255, 0.42);
  box-shadow:
    0 0 0 3px rgba(10, 108, 255, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.search-hint {
  position: absolute;
  right: 14px;
  top: 50%;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  transform: translateY(-50%);
  color: rgba(29, 29, 31, 0.38);
  font-size: 12px;
  font-weight: 600;
}

.search-hint kbd {
  border-radius: 6px;
  border: 1px solid rgba(29, 29, 31, 0.1);
  background: rgba(245, 245, 247, 0.92);
  padding: 3px 7px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
}

.seg-shell {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border-radius: 12px;
  border: 1px solid rgba(29, 29, 31, 0.08);
  background: rgba(245, 245, 247, 0.86);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.76);
}

.seg-btn {
  border: 0;
  border-radius: 9px;
  padding: 8px 13px;
  color: rgba(29, 29, 31, 0.56);
  font-size: 13px;
  font-weight: 600;
  transition: all 0.18s ease;
}

.seg-btn:hover {
  color: #1d1d1f;
}

.seg-btn-active {
  background: rgba(255, 255, 255, 0.96);
  color: #0a6cff;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 2px 7px rgba(10, 108, 255, 0.08);
}

.help-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 12px;
  border: 1px solid rgba(29, 29, 31, 0.08);
  background: rgba(245, 245, 247, 0.86);
  padding: 8px 11px;
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.76);
}

.help-pill__label {
  color: #1d1d1f;
  font-weight: 600;
}

@media (max-width: 960px) {
  .search-shell {
    flex-basis: 100%;
  }
}
</style>
