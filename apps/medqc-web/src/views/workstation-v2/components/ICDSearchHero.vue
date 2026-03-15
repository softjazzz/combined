<template>
  <div class="bg-white border-b border-slate-200/80 px-8 py-5 flex flex-col items-center sticky top-0 z-20 shadow-sm">
    <!-- 版本切换 + 类型切换：胶囊分段控制器 -->
    <div class="flex items-center gap-6 mb-4">
      <div class="flex bg-slate-100 p-1 rounded-lg">
        <button
          v-for="v in versionTabs"
          :key="v.value"
          :class="[
            localVersion === v.value
              ? 'bg-white text-blue-700 font-bold shadow-sm'
              : 'text-slate-500 hover:text-slate-700',
            'px-4 py-1.5 text-[13px] font-medium rounded transition-all duration-200'
          ]"
          @click="localVersion = v.value; $emit('update:codeVersion', v.value)"
        >
          {{ v.label }}
        </button>
      </div>
      <div class="w-px h-4 bg-slate-300"></div>
      <div class="flex bg-slate-100 p-1 rounded-lg">
        <button
          v-for="t in codeTypeTabs"
          :key="t.value"
          :class="[
            localType === t.value
              ? 'bg-white text-indigo-700 font-bold shadow-sm'
              : 'text-slate-500 hover:text-slate-700',
            'px-4 py-1.5 text-[13px] font-medium rounded transition-all duration-200'
          ]"
          @click="localType = t.value; $emit('update:codeType', t.value)"
        >
          {{ t.label }}
        </button>
      </div>
    </div>

    <!-- 搜索框：悬浮中控台 -->
    <div class="relative w-full max-w-3xl group">
      <SearchOutlined class="absolute left-4 top-1/2 -translate-y-1/2 text-lg text-slate-400 group-focus-within:text-blue-500 transition-colors z-10" />
      <input
        ref="searchInput"
        v-model="localQuery"
        type="text"
        :placeholder="localType === 'icd10' ? '输入诊断名称或 ICD-10 编码进行极速检索...' : '输入手术名称或 ICD-9 编码进行极速检索...'"
        class="w-full pl-11 pr-20 py-3.5 bg-white border-2 border-slate-200 focus:border-blue-500 rounded-xl outline-none text-[15px] shadow-[0_2px_10px_rgba(0,0,0,0.02)] focus:shadow-[0_4px_20px_rgba(59,130,246,0.1)] transition-all placeholder:text-slate-400 font-medium text-slate-800"
        @keydown.enter="$emit('search', localQuery)"
        @input="onQueryChange"
      />
      <div class="absolute right-4 top-1/2 -translate-y-1/2 flex gap-1">
        <span v-if="localQuery.length > 0" class="text-xs text-slate-400 mr-2">Enter 搜索</span>
        <kbd v-else class="px-2 py-1 bg-slate-100 border border-slate-200 rounded text-[10px] font-mono text-slate-500">Ctrl</kbd>
        <kbd v-if="localQuery.length === 0" class="px-2 py-1 bg-slate-100 border border-slate-200 rounded text-[10px] font-mono text-slate-500">K</kbd>
      </div>
    </div>

    <!-- 统计信息：精简标签 -->
    <div class="flex items-center gap-5 mt-3">
      <div class="flex items-center gap-1.5 text-[13px]">
        <span class="w-2 h-2 rounded-full bg-blue-500"></span>
        <span class="text-slate-500">ICD-10</span>
        <span class="font-semibold text-slate-700 tabular-nums">{{ stats.icd10Count?.toLocaleString() || '—' }}</span>
      </div>
      <div class="w-px h-3.5 bg-slate-300"></div>
      <div class="flex items-center gap-1.5 text-[13px]">
        <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
        <span class="text-slate-500">ICD-9-CM-3</span>
        <span class="font-semibold text-slate-700 tabular-nums">{{ stats.icd9Count?.toLocaleString() || '—' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
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

// Ctrl+K 快捷键聚焦搜索
onMounted(() => {
  const handler = (e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault()
      searchInput.value?.focus()
    }
  }
  window.addEventListener('keydown', handler)
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
  }, 300)
}
</script>
