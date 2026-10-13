<template>
  <div class="icd-search-hero px-6 py-5">
    <div class="mx-auto flex w-full max-w-7xl flex-col gap-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="icd-hero-eyebrow mq-page-eyebrow">分析 · 编码工作台</div>
          <h1 class="mt-1">ICD 智能检索</h1>
          <p class="mt-2 max-w-[760px] text-[13px] leading-6 text-[var(--mq-text-secondary)]">
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
          <MqIcon name="search" class="search-icon" />
          <input
            ref="searchInput"
            v-model="localQuery"
            type="text"
            :placeholder="
              localType === 'icd10'
                ? '输入诊断名称或 ICD-10 编码...'
                : '输入手术名称或 ICD-9 编码...'
            "
            class="search-input mq-input"
            @keydown.enter="$emit('search', localQuery)"
            @input="onQueryChange"
          />
          <div class="search-hint">
            <span v-if="localQuery.length > 0">Enter 搜索</span>
            <template v-else>
              <kbd>Ctrl</kbd>
              <kbd>K</kbd>
            </template>
          </div>
        </div>

        <div class="seg-shell mq-segmented">
          <button
            v-for="v in versionTabs"
            :key="v.value"
            :class="[
              'seg-btn mq-segmented__item',
              localVersion === v.value ? 'seg-btn-active' : '',
            ]"
            @click="selectVersion(v.value)"
          >
            {{ v.label }}
          </button>
        </div>

        <div class="seg-shell mq-segmented">
          <button
            v-for="t in codeTypeTabs"
            :key="t.value"
            :class="['seg-btn mq-segmented__item', localType === t.value ? 'seg-btn-active' : '']"
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
import MqIcon from '@/components/icons/MqIcon.vue'
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'

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

<style scoped src="../styles/icd-search-hero.css"></style>
